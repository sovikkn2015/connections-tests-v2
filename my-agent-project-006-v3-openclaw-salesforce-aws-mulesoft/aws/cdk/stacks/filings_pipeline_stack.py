"""V3 filings pipeline stack.

Wires together the EDGAR ingestion Lambda, EventBridge daily schedule,
DynamoDB dedup table, Textract integration, and permissions to the S3
buckets + KB provisioned in other stacks.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as ddb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_sns as sns,
)
from constructs import Construct


class FilingsPipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        raw_bucket: s3.Bucket,
        chunks_bucket: s3.Bucket,
        knowledge_base_id: str,
        kb_data_source_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Drag-drop bucket lives in this stack (not KbStack) to avoid a
        # cross-stack S3 notification reference that would make KbStack
        # depend on this stack's Textract Lambda.
        drag_drop_bucket = s3.Bucket(
            self,
            "DragDropBucket",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        dedup = ddb.Table(
            self,
            "FilingsDedup",
            partition_key=ddb.Attribute(name="cik_accession", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        lambda_code_path = (
            Path(__file__).parent.parent.parent / "data-pipelines" / "filings-corpus"
        )
        common_env = {
            "WATCHLIST_SSM_PARAM": "/006-v3/watchlist/tickers",
            "DEDUP_TABLE": dedup.table_name,
            "S3_RAW_BUCKET": raw_bucket.bucket_name,
            "S3_CHUNKS_BUCKET": chunks_bucket.bucket_name,
            "KB_ID": knowledge_base_id,
            "KB_DATA_SOURCE_ID": kb_data_source_id,
            "EMBED_MODEL_ID": "amazon.titan-embed-text-v2:0",
            "USER_AGENT": "OpenClaw V3 research@example.com",
        }

        ingest_fn = lambda_.Function(
            self,
            "IngestHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.ingest_handler.lambda_handler",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment=common_env,
        )
        dedup.grant_read_write_data(ingest_fn)
        raw_bucket.grant_put(ingest_fn)
        chunks_bucket.grant_put(ingest_fn)
        ingest_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:StartIngestionJob",
                    "bedrock:GetIngestionJob",
                    "bedrock-agent:StartIngestionJob",
                    "bedrock-agent:GetIngestionJob",
                ],
                resources=["*"],
            )
        )
        ingest_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/006-v3/watchlist/*"
                ],
            )
        )
        ingest_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )

        # Daily 04:00 America/New_York = 08:00 UTC (no DST logic; acceptable for demo)
        events.Rule(
            self,
            "DailyEdgarScan",
            schedule=events.Schedule.cron(hour="8", minute="0"),
            targets=[targets.LambdaFunction(ingest_fn)],
        )

        # -------- Textract drag-drop path --------
        textract_topic = sns.Topic(self, "TextractCompletionTopic")
        textract_role = iam.Role(
            self,
            "TextractRole",
            assumed_by=iam.ServicePrincipal("textract.amazonaws.com"),
        )
        textract_topic.grant_publish(textract_role)

        start_fn = lambda_.Function(
            self,
            "TextractStart",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.textract_handler.on_s3_create",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            timeout=Duration.seconds(30),
            environment={
                "TEXTRACT_SNS_TOPIC_ARN": textract_topic.topic_arn,
                "TEXTRACT_ROLE_ARN": textract_role.role_arn,
            },
        )
        drag_drop_bucket.grant_read(start_fn)
        start_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["textract:StartDocumentTextDetection"],
                resources=["*"],
            )
        )
        drag_drop_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(start_fn),
            s3.NotificationKeyFilter(prefix="drops/", suffix=".pdf"),
        )

        complete_fn = lambda_.Function(
            self,
            "TextractComplete",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.textract_handler.on_textract_complete",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment=common_env,
        )
        complete_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["textract:GetDocumentTextDetection"],
                resources=["*"],
            )
        )
        chunks_bucket.grant_put(complete_fn)
        complete_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )
        complete_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agent:StartIngestionJob"],
                resources=["*"],
            )
        )
        textract_topic.add_subscription(
            # subscribe complete_fn to the SNS topic
            __import__("aws_cdk.aws_sns_subscriptions", fromlist=["LambdaSubscription"]).LambdaSubscription(complete_fn)
        )

        CfnOutput(self, "FilingsDedupTable", value=dedup.table_name)
        CfnOutput(self, "IngestFunctionName", value=ingest_fn.function_name)
        CfnOutput(self, "TextractSnsTopicArn", value=textract_topic.topic_arn)
        CfnOutput(self, "DragDropBucketName", value=drag_drop_bucket.bucket_name)
