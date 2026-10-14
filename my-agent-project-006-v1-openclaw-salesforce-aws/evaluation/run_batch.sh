#!/usr/bin/env bash
# Run 40 targeted queries; each with a per-query timeout of 5m.
# Expects env vars already set (see ../.run12-env.sh).
set -u

: "${AGENTCORE_AGENT_ARN:?must be set}"
: "${AWS_REGION:?must be set}"
: "${LANGFUSE_SECRET_KEY:?must be set}"
: "${LANGFUSE_PUBLIC_KEY:?must be set}"
: "${LANGFUSE_BASE_URL:?must be set}"

QIDS="3 4 5 6 7 10 12 13 14 17 21 22 23 25 26 27 28 29 31 32 33 34 37 38 44 45 47 48 49 50 51 52 53 54 55 56 57 58 60 150"

mkdir -p run12-targeted

for qid in $QIDS; do
  out=run12-targeted/q${qid}.json
  if [ -f "$out" ]; then
    echo "=== Q${qid} SKIP (already done) ==="
    continue
  fi
  echo "=== Q${qid} ==="
  ( python3 run_suite.py --query-id "${qid}" --output "$out" 2>&1 | tail -3 ) &
  pid=$!
  SECONDS=0
  while kill -0 $pid 2>/dev/null; do
    if [ $SECONDS -ge 300 ]; then
      echo "TIMEOUT Q${qid}, killing"
      kill -9 $pid 2>/dev/null
      echo '{"results":[{"query_id":'${qid}',"status":"ERROR","avg_score":0,"flags":["TIMEOUT"],"level":"?"}]}' > "$out"
      break
    fi
    sleep 2
  done
  wait $pid 2>/dev/null
  sleep 2
done

echo "BATCH DONE"
ls -1 run12-targeted/ | wc -l
