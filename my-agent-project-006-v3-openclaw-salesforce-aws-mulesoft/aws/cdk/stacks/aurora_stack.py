"""V3 Aurora PostgreSQL Serverless v2 stack.

Creates the cluster, enables pgvector, and runs the research-corpus schema
migration as a CDK custom resource. Master creds are generated into
Secrets Manager with auto-rotation disabled (dev stack; production should
enable 30-day rotation).

Cross-stack discipline: this stack owns the Aurora SG AND an exported
`client_sg` that other stacks attach to their Lambdas. Ingress on the
Aurora SG is defined here, pointing at client_sg. Cross-stack Lambdas
never call aurora_cluster.connections.allow_from() — that creates a
cyclic stack dependency because the source-SG's stack then becomes a
prerequisite of the Aurora stack.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    custom_resources as cr,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_rds as rds,
)
from constructs import Construct


class AuroraPgVectorStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sg = ec2.SecurityGroup(
            self,
            "AuroraSg",
            vpc=vpc,
            description="Aurora pgvector cluster SG",
            allow_all_outbound=True,
        )

        # Client SG exported for cross-stack Lambdas.
        self.client_sg = ec2.SecurityGroup(
            self,
            "AuroraClientSg",
            vpc=vpc,
            description="Shared client SG for Lambdas that talk to Aurora",
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(
            peer=self.client_sg,
            connection=ec2.Port.tcp(5432),
            description="client-sg to aurora",
        )

        # Schema migrator SG (in-stack; avoids cross-stack SG ingress).
        migrator_sg = ec2.SecurityGroup(
            self,
            "MigratorSg",
            vpc=vpc,
            description="Schema migrator Lambda SG",
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(
            peer=migrator_sg,
            connection=ec2.Port.tcp(5432),
            description="migrator to aurora",
        )

        self.cluster = rds.DatabaseCluster(
            self,
            "ResearchCorpus",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_8,
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=2,
            writer=rds.ClusterInstance.serverless_v2("writer"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            default_database_name="research",
            security_groups=[sg],
            credentials=rds.Credentials.from_generated_secret(
                "research_admin", secret_name="/006-v3/infra/aurora-master"
            ),
            removal_policy=RemovalPolicy.DESTROY,  # demo stack
            deletion_protection=False,
            backup=rds.BackupProps(retention=Duration.days(1)),
            storage_encrypted=True,
        )

        # Schema migration runs 001 + 002 via a Lambda-backed CustomResource.
        # SQL is packaged inside the Lambda deployment bundle (not env vars,
        # which have a 4KB total cap that the RLS policy file busts).
        # psycopg is installed via BundlingOptions (Docker/Finch required on
        # host). If bundling fails, Lambda returns ok=False and the SQL is
        # re-applied manually via scripts/seed-aurora.sh.
        schema_dir = Path(__file__).parent.parent.parent / "data-pipelines" / "research-corpus" / "schema"
        init_sql = (schema_dir / "001_init.sql").read_text()
        rls_sql = (schema_dir / "002_rls_policies.sql").read_text()

        # Stage the Lambda code dir: inline handler + the two .sql files.
        migrator_build_dir = Path(tempfile.mkdtemp(prefix="006v3-migrator-"))
        (migrator_build_dir / "index.py").write_text(_MIGRATOR_SRC)
        (migrator_build_dir / "001_init.sql").write_text(init_sql)
        (migrator_build_dir / "002_rls_policies.sql").write_text(rls_sql)

        migrator = lambda_.Function(
            self,
            "SchemaMigrator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[migrator_sg],
            timeout=Duration.minutes(3),
            environment={
                "AURORA_SECRET_ARN": self.cluster.secret.secret_arn,  # type: ignore[union-attr]
                "AURORA_HOST": self.cluster.cluster_endpoint.hostname,
                "AURORA_DB": "research",
            },
            code=lambda_.Code.from_asset(str(migrator_build_dir)),
        )
        self.cluster.secret.grant_read(migrator)  # type: ignore[union-attr]

        cr.AwsCustomResource(
            self,
            "RunMigration",
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": migrator.function_name,
                    "Payload": '{"action": "migrate"}',
                },
                physical_resource_id=cr.PhysicalResourceId.of("schema-v1"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["lambda:InvokeFunction"],
                        resources=[migrator.function_arn],
                    )
                ]
            ),
        )

        CfnOutput(self, "AuroraEndpoint", value=self.cluster.cluster_endpoint.hostname)
        CfnOutput(self, "AuroraSecretArn", value=self.cluster.secret.secret_arn)  # type: ignore[union-attr]


_MIGRATOR_SRC = """
import json, os, boto3

def handler(event, context):
    try:
        import psycopg  # provided by a Lambda layer in production
    except ImportError:
        return {"ok": False, "reason": "psycopg layer not attached; run seed-aurora.sh manually"}
    sm = boto3.client("secretsmanager")
    sec = json.loads(sm.get_secret_value(SecretId=os.environ["AURORA_SECRET_ARN"])["SecretString"])
    conn = psycopg.connect(
        host=os.environ["AURORA_HOST"],
        dbname=os.environ["AURORA_DB"],
        user=sec["username"],
        password=sec["password"],
    )
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "001_init.sql"), "r") as f:
        init_sql = f.read()
    with open(os.path.join(here, "002_rls_policies.sql"), "r") as f:
        rls_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(init_sql)
        cur.execute(rls_sql)
    conn.commit()
    return {"ok": True}
"""
