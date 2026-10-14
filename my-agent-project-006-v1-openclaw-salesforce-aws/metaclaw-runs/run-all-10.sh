#!/bin/bash
# Batch runner: 10 sequential pipeline runs for MetaClaw lesson population
# All credentials must be set in the environment BEFORE running this script.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${SCRIPT_DIR}/metaclaw-runs"

# Verify required env vars are set (no values printed)
for var in SF_TARGET_ORG SF_INSTANCE_URL MCP_GATEWAY_URL MCP_API_KEY LANGFUSE_BASE_URL LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY; do
  if [ -z "${!var}" ]; then
    echo "ERROR: $var is not set. Export all required env vars before running."
    exit 1
  fi
done

echo "=== MetaClaw Population: 10 Pipeline Runs ==="
echo "Started at: $(date)"
echo "All env vars verified."
echo ""

for i in $(seq 1 10); do
  echo "=== Pipeline run $i/10 === ($(date))"
  
  # Run with 10-minute timeout
  timeout 600 python3 "${SCRIPT_DIR}/scripts/test-pipeline.py" > "${LOG_DIR}/run-${i}.log" 2>&1
  EXIT_CODE=$?
  
  echo "  Exit code: ${EXIT_CODE}"
  
  if [ $EXIT_CODE -eq 124 ]; then
    echo "  Status: TIMEOUT (killed after 10 minutes)"
  elif grep -q "PIPELINE COMPLETED" "${LOG_DIR}/run-${i}.log" 2>/dev/null; then
    echo "  Status: COMPLETED"
    grep "Rating:" "${LOG_DIR}/run-${i}.log" | head -1 || true
    grep "Target Price:" "${LOG_DIR}/run-${i}.log" | head -1 || true
  elif grep -q "PIPELINE FAILED" "${LOG_DIR}/run-${i}.log" 2>/dev/null; then
    echo "  Status: FAILED"
    grep "Failed at stage:" "${LOG_DIR}/run-${i}.log" | head -1 || true
  else
    echo "  Status: UNKNOWN (check log)"
    tail -5 "${LOG_DIR}/run-${i}.log" || true
  fi
  
  LESSON_COUNT=$(ls "${SCRIPT_DIR}/openclaw/metaclaw_lessons/"*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "  MetaClaw lessons total: ${LESSON_COUNT}"
  echo ""
  
  # Brief pause between runs to avoid throttling
  if [ $i -lt 10 ]; then
    echo "  Sleeping 10s before next run..."
    sleep 10
  fi
done

echo "=== All 10 runs complete at $(date) ==="
echo "DONE" > "${LOG_DIR}/batch-complete.flag"
