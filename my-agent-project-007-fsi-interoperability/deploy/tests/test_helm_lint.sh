#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_helm_lint.sh
#
# Runs `helm lint` on the umbrella chart and each of the four Wave 1
# trust-layer sub-charts.
#
# Exit codes:
#   0 -- all charts lint clean (OR helm not installed -- skipped)
#   1 -- at least one chart failed lint
#
# Usage:
#   bash deploy/tests/test_helm_lint.sh
#
# CI-friendly: auto-skips (exit 0) when helm is not on PATH so pipelines
# without K8s tooling still pass. The Python test suite is the lower-
# level invariant; this script is the deploy-layer invariant.
# -----------------------------------------------------------------------------
set -euo pipefail

# Path-resilient: work from any cwd.
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_helm_lint] cwd=$(pwd)"

if ! command -v helm >/dev/null 2>&1; then
  echo "[test_helm_lint] SKIP -- helm not on PATH"
  exit 0
fi

HELM_VER=$(helm version --short 2>/dev/null || echo "unknown")
echo "[test_helm_lint] helm=$HELM_VER"

UMBRELLA=deploy/helm/007-fsi
SUBCHARTS=(
  deploy/helm/007-fsi/charts/m1-identity
  deploy/helm/007-fsi/charts/m2-m4-policy-engine
  deploy/helm/007-fsi/charts/m6-mcp-gateway
  deploy/helm/007-fsi/charts/m10-audit-logger
  deploy/helm/007-fsi/charts/m11-blpapi-adapter
  deploy/helm/007-fsi/charts/m11-grpc-adapter
  deploy/helm/007-fsi/charts/m13-fix-bridge
)

FAILED=0

# Ensure umbrella dependencies are resolved before linting the umbrella.
if [ -f "$UMBRELLA/Chart.yaml" ]; then
  echo "[test_helm_lint] resolving umbrella deps..."
  helm dependency update "$UMBRELLA" >/dev/null 2>&1 || {
    echo "[test_helm_lint] WARN -- helm dependency update failed (continuing)"
  }
fi

for sc in "${SUBCHARTS[@]}"; do
  echo "---"
  echo "[test_helm_lint] linting sub-chart: $sc"
  if ! helm lint "$sc"; then
    echo "[test_helm_lint] FAIL -- $sc"
    FAILED=1
  fi
done

echo "---"
echo "[test_helm_lint] linting umbrella: $UMBRELLA (with values-cloud.yaml)"
if ! helm lint "$UMBRELLA" -f "$UMBRELLA/values-cloud.yaml"; then
  echo "[test_helm_lint] FAIL -- umbrella"
  FAILED=1
fi

if [ "$FAILED" -ne 0 ]; then
  echo "[test_helm_lint] RESULT: FAIL"
  exit 1
fi
echo "[test_helm_lint] RESULT: PASS"
exit 0
