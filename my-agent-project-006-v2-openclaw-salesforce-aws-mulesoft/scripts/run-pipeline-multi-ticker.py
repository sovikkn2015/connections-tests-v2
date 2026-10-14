#!/usr/bin/env python3
"""
Run the 23-stage pipeline across multiple tickers to populate MetaClaw lessons.

Modes:
  --agentcore   Invoke each query via AgentCore SDK (default, production path)
  --local       Run via local Python import (dev only)

Usage:
  export SF_TARGET_ORG=new-org
  python3 scripts/run-pipeline-multi-ticker.py              # AgentCore (default)
  python3 scripts/run-pipeline-multi-ticker.py --local      # local dev

For --local mode, also set:
  export MCP_GATEWAY_URL=https://YOUR_API_GATEWAY.execute-api.us-east-1.amazonaws.com/prod
  export MCP_API_KEY=<your key>
  export LANGFUSE_SECRET_KEY=<key>
  export LANGFUSE_PUBLIC_KEY=<key>
  export LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

SF_ACCESS_TOKEN is auto-fetched from sf CLI if not set.
Each run takes 2-5 minutes. 10 runs = ~30-50 minutes total.
"""
import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("multi-ticker-runner")

# 10 runs: 8 unique tickers from the L3/L4 eval matrix + 2 repeats
RUNS = [
    ("NVDA", "Deep dive on NVIDIA ahead of earnings", "Sarah Chen"),
    ("AAPL", "Full research brief on Apple — focus on services growth", "Sarah Chen"),
    ("TSLA", "Tesla investment thesis — FSD and energy storage", "Mike Rodriguez"),
    ("MSFT", "Microsoft Azure and AI capex — is the spend justified?", "Sarah Chen"),
    ("AMD", "AMD vs NVDA in the AI chip cycle — who wins?", "Sarah Chen"),
    ("AMZN", "Amazon cloud and retail — where's the value?", "Mike Rodriguez"),
    ("JPM", "JPMorgan rate sensitivity — what if Fed holds?", "Lisa Sharma"),
    ("TSMC", "TSMC fab expansion and geopolitical risk", "Sarah Chen"),
    ("NVDA", "NVIDIA DCF with Monte Carlo — bear case if AI capex slows", "Sarah Chen"),
    ("AAPL", "Apple comps vs big tech peers — is it overvalued?", "Mike Rodriguez"),
]


def ensure_sf_token():
    if os.environ.get('SF_ACCESS_TOKEN'):
        return
    target_org = os.environ.get('SF_TARGET_ORG', 'new-org')
    result = subprocess.run(
        ['sf', 'org', 'display', '--target-org', target_org, '--json'],
        capture_output=True, text=True,
    )
    sf_data = json.loads(result.stdout)
    os.environ['SF_ACCESS_TOKEN'] = sf_data['result']['accessToken']
    logger.info("SF token fetched: %s...", os.environ['SF_ACCESS_TOKEN'][:20])


def check_env():
    required = ['SF_INSTANCE_URL', 'MCP_GATEWAY_URL', 'MCP_API_KEY',
                'LANGFUSE_SECRET_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_BASE_URL']
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error("Missing env vars: %s", missing)
        sys.exit(1)


def run_single_agentcore(ticker, query, analyst, run_num, total):
    """Invoke a single query via AgentCore SDK (production path)."""
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

    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"multi-{ticker}-{int(time.time())}-{run_num}"))
    payload = json.dumps({"prompt": query}).encode("utf-8")

    logger.info("[%d/%d] AgentCore invocation for %s — session=%s", run_num, total, ticker, session_id)
    start = time.time()

    try:
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

        status = "completed" if text and not text.startswith("ERROR") else "failed"
        logger.info("[%d/%d] %s %s in %.0fs — %d chars",
                    run_num, total, ticker, status, elapsed, len(text))
        return {'ticker': ticker, 'status': status, 'elapsed': round(elapsed),
                'run_id': session_id, 'errors': 0}

    except Exception as exc:
        elapsed = time.time() - start
        logger.error("[%d/%d] %s EXCEPTION after %.0fs: %s",
                     run_num, total, ticker, elapsed, exc)
        return {'ticker': ticker, 'status': 'exception',
                'elapsed': round(elapsed), 'error': str(exc)[:200]}


async def run_single(ticker, query, analyst, run_num, total):
    """Run a single pipeline via local Python import (dev mode)."""
    # Add skill dirs to path (local mode only)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'skills', 'fsi-research'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'skills', 'financial-analysis'))
    from pipeline import FSIResearchPipeline
    pipeline = FSIResearchPipeline(ticker=ticker, query=query, analyst=analyst)
    logger.info("[%d/%d] Starting %s — run_id=%s", run_num, total, ticker, pipeline.run_id)
    start = time.time()

    try:
        result = await pipeline.run()

        # Auto-approve all HITL gates
        while result.get('status') == 'paused':
            stage = result['paused_at_stage']
            logger.info("[%d/%d] %s paused at HITL gate %d — auto-approving",
                        run_num, total, ticker, stage)
            result = await pipeline.resume(
                from_stage=stage + 1,
                approval={'approved': True,
                          'notes': 'Auto-approved for MetaClaw seeding',
                          'analyst': analyst},
            )

        elapsed = time.time() - start
        status = result.get('status', 'unknown')
        rating = (result.get('rating', '') or '')[:50]
        target = result.get('target_price', '')
        errors = len(result.get('errors', []))

        logger.info("[%d/%d] %s %s in %.0fs — rating=%s target=$%s errors=%d",
                    run_num, total, ticker, status, elapsed, rating, target, errors)
        return {'ticker': ticker, 'status': status, 'elapsed': round(elapsed),
                'run_id': pipeline.run_id, 'errors': errors}

    except Exception as exc:
        elapsed = time.time() - start
        logger.error("[%d/%d] %s EXCEPTION after %.0fs: %s",
                     run_num, total, ticker, elapsed, exc)
        return {'ticker': ticker, 'status': 'exception',
                'elapsed': round(elapsed), 'error': str(exc)[:200]}


async def main(use_agentcore: bool = True):
    if not use_agentcore:
        # Local mode: need SF token and env vars
        ensure_sf_token()
        check_env()

    results = []
    for i, (ticker, query, analyst) in enumerate(RUNS, 1):
        if use_agentcore:
            r = run_single_agentcore(ticker, query, analyst, i, len(RUNS))
        else:
            r = await run_single(ticker, query, analyst, i, len(RUNS))
        results.append(r)
        if i < len(RUNS):
            time.sleep(3)

    # Summary
    print(f"\n{'='*70}")
    print(f"{'TICKER':<8} {'STATUS':<12} {'TIME':<8} {'RUN_ID':<20} {'ERRORS'}")
    print('-' * 70)
    for r in results:
        print(f"{r['ticker']:<8} {r['status']:<12} {r['elapsed']:<8}s "
              f"{r.get('run_id',''):<20} {r.get('errors','')}")

    completed = sum(1 for r in results if r['status'] == 'completed')
    failed = sum(1 for r in results if r['status'] in ('failed', 'exception'))
    print(f"\nCompleted: {completed}/{len(results)}, Failed: {failed}/{len(results)}")

    # Count MetaClaw lessons
    lessons_dir = os.path.join(os.path.dirname(__file__),
                               '..', 'openclaw', 'metaclaw_lessons')
    if os.path.isdir(lessons_dir):
        n = len([f for f in os.listdir(lessons_dir) if f.endswith('.json')])
        print(f"MetaClaw lessons on disk: {n}")

    # Save summary
    out = os.path.join(os.path.dirname(__file__),
                       '..', 'evaluation', 'pipeline-multi-ticker-results.json')
    with open(out, 'w') as f:
        json.dump({'runs': results, 'completed': completed, 'failed': failed},
                  f, indent=2)
    print(f"Results saved to {out}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Multi-ticker pipeline runner")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--agentcore', action='store_true', default=True,
                       help='Invoke via AgentCore SDK (default)')
    group.add_argument('--local', action='store_true',
                       help='Run via local Python import (dev only)')
    args = parser.parse_args()

    asyncio.run(main(use_agentcore=not args.local))
