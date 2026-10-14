#!/usr/bin/env bash
# Run13 targeted eval driver — 40 queries that failed in run11.
set -u
cd "$(dirname "$0")"

export EVAL_AUTH_TOKEN="${EVAL_AUTH_TOKEN:-$(openssl rand -hex 16)}"
export AGENTCORE_AGENT_ARN="arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/fsi_research_agent-Sr1m3j3MUh"
export AWS_REGION="us-east-1"

mkdir -p run13-targeted

QIDS=(3 4 5 6 7 10 12 13 14 17 21 22 23 25 26 27 28 29 31 32 33 34 37 38 44 45 47 48 49 50 51 52 53 54 55 56 57 58 60 150)

for qid in "${QIDS[@]}"; do
  if [[ -f "run13-targeted/q${qid}.json" ]]; then
    echo "=== Q${qid}: skip (already done) ==="
    continue
  fi
  echo "=== Q${qid} $(date '+%H:%M:%S') ==="
  python3 run_suite.py --query-id "${qid}" --output "run13-targeted/q${qid}.json" 2>&1 | tail -3
  sleep 2
done

echo "=== DONE $(date '+%H:%M:%S') ==="
