"""V3 Bedrock Knowledge Base stack.

Creates:
  - S3 buckets for raw filings and pre-chunked KB inputs
  - OpenSearch Serverless collection + security policies
  - OSS vector index (created via custom-resource Lambda; CloudFormation
    has no native OSS index primitive and Bedrock KB refuses to create
    itself if the target index does not yet exist)
  - Bedrock KB with Titan v2 embeddings (1024 dim, normalized)
  - IAM service role for KB -> S3 + KB -> Bedrock + KB -> OSS
"""

from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    custom_resources as cr,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_opensearchserverless as oss,
    aws_s3 as s3,
)
from constructs import Construct


# Inline code for the OSS index creator. Runs on stack create/update.
# Uses urllib3 + botocore SigV4Auth, both bundled with the Lambda runtime.
_INDEX_CREATOR_SRC = r"""
import json
import os
import time
import urllib3

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


def _sign_and_send(method, url, body, region):
    session = boto3.session.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    req = AWSRequest(method=method, url=url, data=body,
                     headers={"Content-Type": "application/json"})
    SigV4Auth(credentials, "aoss", region).add_auth(req)
    http = urllib3.PoolManager()
    return http.request(method, url, body=body, headers=dict(req.headers))


def handler(event, context):
    endpoint = os.environ["OSS_ENDPOINT"].rstrip("/")
    index_name = os.environ["INDEX_NAME"]
    region = os.environ["AWS_REGION"]
    url = f"{endpoint}/{index_name}"

    mapping = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "engine": "faiss",
                        "name": "hnsw",
                        "space_type": "l2",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                "text": {"type": "text"},
                "metadata": {"type": "text", "index": False},
            }
        },
    }
    body = json.dumps(mapping).encode("utf-8")

    # AOSS DataAccessPolicy propagation can take 3-5 min after CFN reports
    # CREATE_COMPLETE on the collection + access policy. IAM role credentials
    # can also take 30-90s to propagate. Sleep once up front so we don't burn
    # the first dozen attempts on guaranteed 403s.
    time.sleep(90)

    # Retry for up to ~13 minutes on 403 (access policy propagation) or 404
    # (DNS warm-up). 200/201 = created, 400 "already_exists" = idempotent ok.
    last = None
    for attempt in range(75):
        try:
            resp = _sign_and_send("PUT", url, body, region)
            status = resp.status
            data = resp.data.decode("utf-8", errors="replace")
            last = (status, data)
            if status in (200, 201):
                return {"ok": True, "status": status, "attempts": attempt + 1}
            # Already exists = fine (idempotent).
            if status == 400 and "resource_already_exists_exception" in data:
                return {"ok": True, "status": status, "attempts": attempt + 1,
                        "note": "index_already_exists"}
            # 403 during IAM propagation, 404 before DNS warmed — retry.
        except Exception as exc:  # noqa: BLE001
            last = ("exception", repr(exc))
        time.sleep(10)
    raise RuntimeError(f"Failed to create index {index_name}: {last}")
"""


class BedrockKnowledgeBaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------- S3 buckets ----------
        self.raw_bucket = s3.Bucket(
            self,
            "RawFilingsBucket",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )
        self.chunks_bucket = s3.Bucket(
            self,
            "ChunksBucket",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ---------- OpenSearch Serverless collection ----------
        coll_name = "openclaw-v3-kb"
        index_name = f"{coll_name}-index"

        network_policy = oss.CfnSecurityPolicy(
            self,
            "KbNetworkPolicy",
            name=f"{coll_name}-net",
            type="network",
            policy=(
                '[{"Rules":[{"Resource":["collection/' + coll_name + '"],'
                '"ResourceType":"collection"},'
                '{"Resource":["collection/' + coll_name + '"],"ResourceType":"dashboard"}'
                '],"AllowFromPublic":true}]'
            ),
        )
        encryption_policy = oss.CfnSecurityPolicy(
            self,
            "KbEncryptionPolicy",
            name=f"{coll_name}-enc",
            type="encryption",
            policy=(
                '{"Rules":[{"Resource":["collection/' + coll_name
                + '"],"ResourceType":"collection"}],"AWSOwnedKey":true}'
            ),
        )

        coll = oss.CfnCollection(
            self,
            "KbCollection",
            name=coll_name,
            type="VECTORSEARCH",
        )
        # Security policies must exist BEFORE the collection is created.
        coll.add_dependency(encryption_policy)
        coll.add_dependency(network_policy)

        # ---------- Index-creator Lambda ----------
        index_creator_role = iam.Role(
            self,
            "KbIndexCreatorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        index_creator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[coll.attr_arn],
            )
        )

        index_creator_fn = lambda_.Function(
            self,
            "KbIndexCreatorFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(_INDEX_CREATOR_SRC),
            timeout=Duration.minutes(15),
            role=index_creator_role,
            environment={
                "OSS_ENDPOINT": coll.attr_collection_endpoint,
                "INDEX_NAME": index_name,
            },
        )

        # ---------- Bedrock KB service role ----------
        kb_role = iam.Role(
            self,
            "KbServiceRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            inline_policies={
                "KbAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["s3:GetObject", "s3:ListBucket"],
                            resources=[
                                self.chunks_bucket.bucket_arn,
                                f"{self.chunks_bucket.bucket_arn}/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["aoss:APIAccessAll"],
                            resources=[coll.attr_arn],
                        ),
                    ]
                )
            },
        )

        # Data-access policy lists BOTH principals (KB service role reads/
        # writes, Lambda creates the index). Grant "aoss:*" on the Lambda's
        # index-creator role to avoid per-action matchup bugs. The index
        # creator only runs once at stack-create time.
        access_policy = oss.CfnAccessPolicy(
            self,
            "KbDataAccessPolicy",
            name=f"{coll_name}-data",
            type="data",
            policy=(
                '[{"Rules":[{"Resource":["index/' + coll_name + '/*"],'
                '"Permission":["aoss:*"],'
                '"ResourceType":"index"},'
                '{"Resource":["collection/' + coll_name + '"],'
                '"Permission":["aoss:*"],'
                '"ResourceType":"collection"}],'
                '"Principal":["' + kb_role.role_arn + '",'
                '"' + index_creator_role.role_arn + '"]}]'
            ),
        )
        access_policy.add_dependency(coll)
        access_policy.node.add_dependency(kb_role)
        access_policy.node.add_dependency(index_creator_role)

        # ---------- Custom resource: create the index ----------
        create_index = cr.AwsCustomResource(
            self,
            "CreateKbIndex",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": index_creator_fn.function_name,
                    "Payload": '{"action": "create"}',
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"kb-index-{coll_name}"
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": index_creator_fn.function_name,
                    "Payload": '{"action": "create"}',
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"kb-index-{coll_name}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["lambda:InvokeFunction"],
                        resources=[index_creator_fn.function_arn],
                    )
                ]
            ),
            timeout=Duration.minutes(15),
            install_latest_aws_sdk=False,
        )
        create_index.node.add_dependency(coll)
        create_index.node.add_dependency(access_policy)
        create_index.node.add_dependency(index_creator_fn)

        # ---------- Bedrock Knowledge Base ----------
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "FilingsKb",
            name="openclaw-v3-filings",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=(
                        f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                    ),
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=(
                    bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                        collection_arn=coll.attr_arn,
                        vector_index_name=index_name,
                        field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                            vector_field="embedding",
                            text_field="text",
                            metadata_field="metadata",
                        ),
                    )
                ),
            ),
        )
        self.knowledge_base.add_dependency(coll)
        # KB refuses to stand up until the OSS index exists.
        self.knowledge_base.node.add_dependency(create_index)

        self.data_source = bedrock.CfnDataSource(
            self,
            "ChunksDataSource",
            name="openclaw-v3-chunks",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.chunks_bucket.bucket_arn,
                    inclusion_prefixes=["kb-chunks/"],
                ),
            ),
            vector_ingestion_configuration=(
                bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                    chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                        chunking_strategy="NONE",  # we pre-chunked
                    ),
                )
            ),
        )

        CfnOutput(self, "RawFilingsBucketName", value=self.raw_bucket.bucket_name)
        CfnOutput(self, "ChunksBucketName", value=self.chunks_bucket.bucket_name)
        CfnOutput(self, "KnowledgeBaseId", value=self.knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "KbDataSourceId", value=self.data_source.attr_data_source_id)
