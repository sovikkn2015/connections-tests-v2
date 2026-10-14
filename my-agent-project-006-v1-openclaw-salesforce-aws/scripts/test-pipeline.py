#!/usr/bin/env python3
"""
Test runner for FSIResearchPipeline — runs the actual 23-stage pipeline.

Modes:
  --agentcore   Invoke via AgentCore SDK (default, production path)
  --local       Run via local Python import (dev only)

All credentials are loaded from environment variables or the Salesforce CLI.
No secrets are stored in this file.

Required env vars for --local mode:
  SF_INSTANCE_URL, MCP_GATEWAY_URL, MCP_API_KEY,
  LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL

Required env vars for --agentcore mode:
  AWS credentials (via profile or env), AGENTCORE_AGENT_ARN (optional override)

SF_ACCESS_TOKEN is auto-fetched from `sf org display` if not set (local mode).
"""
import argparse
import asyncio
import os
import sys
import json
import logging
import time

# Verbose logging so we see every stage
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def _ensure_sf_token():
    """Fetch a fresh SF access token via the Salesforce CLI if not already set."""
    if os.environ.get('SF_ACCESS_TOKEN'):
        return
    import subprocess
    target_org = os.environ.get('SF_TARGET_ORG', 'my-org')
    result = subprocess.run(
        ['sf', 'org', 'display', '--target-org', target_org, '--json'],
        capture_output=True, text=True,
    )
    sf_data = json.loads(result.stdout)
    os.environ['SF_ACCESS_TOKEN'] = sf_data['result']['accessToken']
    print(f"SF Token fetched: {os.environ['SF_ACCESS_TOKEN'][:20]}...")


def _check_env():
    """Verify all required environment variables are set (local mode only)."""
    required = [
        'SF_INSTANCE_URL', 'MCP_GATEWAY_URL', 'MCP_API_KEY',
        'LANGFUSE_SECRET_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_BASE_URL',
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"ERROR: Missing env vars: {missing}")
        sys.exit(1)


def run_via_agentcore(query: str, ticker: str):
    """Invoke the pipeline via AgentCore SDK (production path)."""
    import boto3
    import uuid
    from botocore.config import Config

    agentcore_arn = os.environ.get(
        "AGENTCORE_AGENT_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/fsi_research_agent-Sr1m3j3MUh",
    )
    region = os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=300, connect_timeout=30, retries={"max_attempts": 2}),
    )

    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"test-pipeline-{int(time.time())}"))
    payload = json.dumps({"prompt": query}).encode("utf-8")

    print(f'\n{"="*60}')
    print(f'=== AgentCore invocation for {ticker} ===')
    print(f'=== ARN: {agentcore_arn} ===')
    print(f'=== Session: {session_id} ===')
    print(f'{"="*60}\n')

    start = time.time()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agentcore_arn,
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
        payload=payload,
    )
    response_body = resp["response"].read().decode("utf-8")
    elapsed = time.time() - start

    try:
        parsed = json.loads(response_body)
        text = parsed.get("response", parsed.get("text", response_body))
    except json.JSONDecodeError:
        text = response_body

    print(f'Response ({elapsed:.1f}s):\n{text[:500]}')
    if len(text) > 500:
        print(f'... ({len(text)} chars total)')
    return {"status": "completed", "text": text, "elapsed": round(elapsed)}


async def run_via_local():
    """Run the pipeline via local Python import (dev mode)."""
    # Add the skill directories to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'skills', 'fsi-research'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'skills', 'financial-analysis'))

    _ensure_sf_token()
    _check_env()

    from pipeline import FSIResearchPipeline  # noqa: E402

    pipeline = FSIResearchPipeline(
        ticker='NVDA',
        query='Deep dive on NVIDIA ahead of earnings next week',
        analyst='Sarah Chen',
    )

    print(f'\n{"="*60}')
    print(f'=== Starting 23-stage pipeline for NVDA (local) ===')
    print(f'=== Run ID: {pipeline.run_id} ===')
    print(f'{"="*60}\n')

    result = await pipeline.run()

    print(f'\nStatus: {result["status"]}')
    print(f'Completed stages: {result.get("completed_stages", [])}')

    if result['status'] == 'paused':
        print(f'\nPaused at HITL gate: Stage {result["paused_at_stage"]}')
        print(f'Gate context: {result["gate"]["context"][:200]}')

        # Auto-approve for testing
        print('\n=== Auto-approving HITL gate for test ===')
        result = await pipeline.resume(
            from_stage=result['paused_at_stage'] + 1,
            approval={
                'approved': True,
                'notes': 'Auto-approved for testing',
                'analyst': 'Sarah Chen',
            },
        )
        print(f'Status after resume: {result["status"]}')
        print(f'Completed stages: {result.get("completed_stages", [])}')

        # Keep resuming through all HITL gates
        while result['status'] == 'paused':
            print(f'\nPaused at HITL gate: Stage {result["paused_at_stage"]}')
            print(f'Gate context: {result["gate"]["context"][:200]}')
            print('=== Auto-approving ===')
            result = await pipeline.resume(
                from_stage=result['paused_at_stage'] + 1,
                approval={
                    'approved': True,
                    'notes': 'Auto-approved for testing',
                    'analyst': 'Sarah Chen',
                },
            )
            print(f'Status: {result["status"]}')
            print(f'Completed stages: {result.get("completed_stages", [])}')

    if result['status'] == 'completed':
        print(f'\n{"="*60}')
        print('=== PIPELINE COMPLETED ===')
        print(f'{"="*60}')
        print(f'Ticker: {result.get("ticker")}')
        print(f'Rating: {result.get("rating", "")[:100]}')
        print(f'Target Price: ${result.get("target_price")}')
        print(f'Data Sources: {result.get("data_sources", [])}')
        print(f'Errors: {result.get("errors", [])}')
    elif result['status'] == 'failed':
        print(f'\n{"="*60}')
        print('=== PIPELINE FAILED ===')
        print(f'{"="*60}')
        print(f'Failed at stage: {result.get("failed_at_stage")}')
        print(f'Errors: {json.dumps(result.get("errors", []), indent=2)}')

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Test FSI Research Pipeline")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--agentcore', action='store_true', default=True,
                       help='Invoke via AgentCore SDK (default)')
    group.add_argument('--local', action='store_true',
                       help='Run via local Python import (dev only)')
    args = parser.parse_args()

    if args.local:
        result = asyncio.run(run_via_local())
    else:
        result = run_via_agentcore(
            query='Deep dive on NVIDIA ahead of earnings next week',
            ticker='NVDA',
        )
