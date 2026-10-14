#!/usr/bin/env python3
"""V3 CDK entrypoint.

Stack dependency order:
  VpcStack -> AuroraPgVectorStack -> ResearchPipelineStack
  (independent) BedrockKnowledgeBaseStack -> FilingsPipelineStack

Deploy all with: cdk deploy --all --require-approval never
"""

from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.vpc_stack import VpcStack
from stacks.aurora_stack import AuroraPgVectorStack
from stacks.bedrock_kb_stack import BedrockKnowledgeBaseStack
from stacks.filings_pipeline_stack import FilingsPipelineStack
from stacks.research_pipeline_stack import ResearchPipelineStack
from stacks.risk_alerts_stack import RiskAlertsStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

vpc_stack = VpcStack(app, "Openclaw006V3-Vpc", env=env)

aurora_stack = AuroraPgVectorStack(
    app, "Openclaw006V3-Aurora", vpc=vpc_stack.vpc, env=env
)
aurora_stack.add_dependency(vpc_stack)

kb_stack = BedrockKnowledgeBaseStack(app, "Openclaw006V3-Kb", env=env)

filings_stack = FilingsPipelineStack(
    app,
    "Openclaw006V3-FilingsPipeline",
    raw_bucket=kb_stack.raw_bucket,
    chunks_bucket=kb_stack.chunks_bucket,
    knowledge_base_id=kb_stack.knowledge_base.attr_knowledge_base_id,
    kb_data_source_id=kb_stack.data_source.attr_data_source_id,
    env=env,
)
filings_stack.add_dependency(kb_stack)

research_stack = ResearchPipelineStack(
    app,
    "Openclaw006V3-ResearchPipeline",
    vpc=vpc_stack.vpc,
    aurora_cluster=aurora_stack.cluster,
    aurora_client_sg=aurora_stack.client_sg,
    env=env,
)
research_stack.add_dependency(aurora_stack)

risk_alerts_stack = RiskAlertsStack(app, "Openclaw006V3-RiskAlerts", env=env)

app.synth()
