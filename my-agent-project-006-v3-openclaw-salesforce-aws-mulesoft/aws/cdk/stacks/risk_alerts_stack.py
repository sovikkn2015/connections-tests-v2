"""V3 risk-alerts stack (Narrative 3).

Self-contained stack that provisions the price-shock detection loop:

    EventBridge cron(*/5) -> MarketPriceMonitor Lambda -> SQS -> SweepDispatcher Lambda -> AgentCore HTTPS

Resources:
    * DynamoDB PriceShockEvents      (idempotency for the market monitor)
    * DynamoDB ComplianceSweepEvents (idempotency + audit for the dispatcher)
    * SQS ComplianceSweepQueue + DLQ (maxReceiveCount=5)
    * Lambda MarketPriceMonitor      (EventBridge-triggered, 5 min)
    * Lambda SweepDispatcher         (SQS-triggered, batch=1)
    * EventBridge rule               (cron */5 13-21 UTC Mon-Fri)

No cross-stack refs; everything external comes from SSM + Secrets Manager
by name at invoke time.
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
    aws_lambda_event_sources as lambda_events,
    aws_sqs as sqs,
)
from constructs import Construct


class RiskAlertsStack(Stack):
    """Provisions the price-shock -> compliance-sweep async pipeline."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------
        # DynamoDB — idempotency tables
        # ------------------------------------------------------------------
        shock_events = ddb.Table(
            self,
            "PriceShockEvents",
            partition_key=ddb.Attribute(name="event_key", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        sweep_events = ddb.Table(
            self,
            "ComplianceSweepEvents",
            partition_key=ddb.Attribute(name="event_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ------------------------------------------------------------------
        # SQS — compliance sweep queue with DLQ
        # ------------------------------------------------------------------
        sweep_dlq = sqs.Queue(
            self,
            "ComplianceSweepDLQ",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )

        sweep_queue = sqs.Queue(
            self,
            "ComplianceSweepQueue",
            visibility_timeout=Duration.minutes(6),  # > sweep Lambda timeout
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=sweep_dlq,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ------------------------------------------------------------------
        # Lambda assets
        # ------------------------------------------------------------------
        lambda_code_path = (
            Path(__file__).parent.parent.parent / "data-pipelines" / "risk-alerts"
        )

        # ------------------------------------------------------------------
        # Market-price-monitor Lambda
        # ------------------------------------------------------------------
        # Wildcard ARN pattern — the concrete secret is created out-of-band
        # (operator creates `/006-v3/vendors/finnhub` in Secrets Manager).
        finnhub_secret_arn_pattern = (
            f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:/006-v3/vendors/finnhub*"
        )
        agentcore_secret_arn_pattern = (
            f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:/006-v3/agentcore/system-token*"
        )

        monitor_fn = lambda_.Function(
            self,
            "MarketPriceMonitor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.monitor.lambda_handler",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "WATCHLIST_SSM_PARAM": "/006-v3/watchlist/tickers",
                "FINNHUB_API_KEY_SECRET": finnhub_secret_arn_pattern.rstrip("*"),
                "PRICE_SHOCK_THRESHOLD_PCT": "3.0",
                "SHOCK_EVENTS_TABLE": shock_events.table_name,
                "COMPLIANCE_SWEEP_QUEUE_URL": sweep_queue.queue_url,
            },
        )

        shock_events.grant_read_write_data(monitor_fn)
        sweep_queue.grant_send_messages(monitor_fn)
        monitor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/006-v3/watchlist/*"
                ],
            )
        )
        monitor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[finnhub_secret_arn_pattern],
            )
        )

        # ------------------------------------------------------------------
        # Sweep dispatcher Lambda
        # ------------------------------------------------------------------
        dispatcher_fn = lambda_.Function(
            self,
            "SweepDispatcher",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambdas.sweep_dispatcher.lambda_handler",
            code=lambda_.Code.from_asset(str(lambda_code_path)),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                # AGENTCORE_URL is injected post-deploy by the operator (or via
                # `aws lambda update-function-configuration`) once AgentCore is up.
                "AGENTCORE_URL": "",
                "AGENTCORE_TOKEN_SECRET": agentcore_secret_arn_pattern.rstrip("*"),
                "SWEEP_EVENTS_TABLE": sweep_events.table_name,
            },
        )

        sweep_events.grant_read_write_data(dispatcher_fn)
        dispatcher_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[agentcore_secret_arn_pattern],
            )
        )

        # Wire SQS -> dispatcher. batch_size=1 keeps first-touch semantics
        # obvious (one shock = one invocation = one AgentCore call).
        dispatcher_fn.add_event_source(
            lambda_events.SqsEventSource(sweep_queue, batch_size=1)
        )

        # ------------------------------------------------------------------
        # EventBridge schedule
        # ------------------------------------------------------------------
        # cron(*/5 13-21 ? * MON-FRI *) — every 5 min, 13:00-21:00 UTC
        # That window covers 09:00-17:00 ET (buffer around 09:30-16:00).
        # The Lambda itself re-checks market hours in America/New_York so
        # DST shifts don't leak pre-open or post-close invocations through.
        schedule_rule = events.Rule(
            self,
            "MarketPriceMonitorSchedule",
            schedule=events.Schedule.expression("cron(*/5 13-21 ? * MON-FRI *)"),
            description="Every 5 minutes during US trading window (Mon-Fri, 13:00-21:00 UTC).",
        )
        schedule_rule.add_target(targets.LambdaFunction(monitor_fn))

        # ------------------------------------------------------------------
        # Outputs
        # ------------------------------------------------------------------
        CfnOutput(self, "PriceShockEventsTable", value=shock_events.table_name)
        CfnOutput(self, "ComplianceSweepEventsTable", value=sweep_events.table_name)
        CfnOutput(self, "ComplianceSweepQueueUrl", value=sweep_queue.queue_url)
        CfnOutput(self, "ComplianceSweepDLQUrl", value=sweep_dlq.queue_url)
        CfnOutput(self, "MarketPriceMonitorFunction", value=monitor_fn.function_name)
        CfnOutput(self, "SweepDispatcherFunction", value=dispatcher_fn.function_name)
        CfnOutput(self, "MarketPriceMonitorScheduleName", value=schedule_rule.rule_name)
