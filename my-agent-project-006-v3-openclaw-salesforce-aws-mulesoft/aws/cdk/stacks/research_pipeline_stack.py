"""V3 research pipeline stack.

SF Platform Event -> EventBridge Partner Event Source -> SQS -> CDC Lambda -> Aurora.

The Aurora SG and its client_sg are owned by AuroraPgVectorStack. This
stack takes `aurora_client_sg` as a constructor arg and attaches it to the
CDC Lambda. No cross-stack ingress rule is created — the ingress rule
(client_sg -> aurora_sg port 5432) lives in the Aurora stack.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_event_sources as events_sources,
    aws_sqs as sqs,
    aws_rds as rds,
)
from constructs import Construct


class ResearchPipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        aurora_cluster: rds.DatabaseCluster,
        aurora_client_sg: ec2.SecurityGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        dlq = sqs.Queue(
            self,
            "CdcDlq",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )
        queue = sqs.Queue(
            self,
            "CdcQueue",
            visibility_timeout=Duration.seconds(200),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=dlq),
            removal_policy=RemovalPolicy.DESTROY,
        )

        lambda_code_path = (
            Path(__file__).parent.parent.parent / "data-pipelines" / "research-corpus"
        )

        cdc_fn = lambda_.Function(
            self,
            "CdcHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.cdc_handler.lambda_handler",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[aurora_client_sg],
            timeout=Duration.minutes(3),
            memory_size=1024,
            environment={
                "AURORA_HOST": aurora_cluster.cluster_endpoint.hostname,
                "AURORA_DB": "research",
                "AURORA_SECRET_ARN": aurora_cluster.secret.secret_arn,  # type: ignore[union-attr]
                "SF_INSTANCE_URL": "https://placeholder.my.salesforce.com",
                "SF_ACCESS_TOKEN_SECRET": f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:/006-v3/salesforce/access-token",
                "EMBED_MODEL_ID": "amazon.titan-embed-text-v2:0",
            },
        )
        aurora_cluster.secret.grant_read(cdc_fn)  # type: ignore[union-attr]

        cdc_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:/006-v3/salesforce/*"
                ],
            )
        )
        cdc_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )

        cdc_fn.add_event_source(
            events_sources.SqsEventSource(queue, batch_size=10)
        )

        CfnOutput(self, "ResearchCdcQueueUrl", value=queue.queue_url)
        CfnOutput(self, "ResearchCdcQueueArn", value=queue.queue_arn)
        CfnOutput(self, "ResearchCdcDlqUrl", value=dlq.queue_url)
        CfnOutput(self, "ResearchCdcFn", value=cdc_fn.function_name)
