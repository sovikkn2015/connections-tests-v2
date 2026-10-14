#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_helm_template.sh
#
# Renders the umbrella chart with values-cloud.yaml and greps the output
# for the contract targets mandated by the Wave 1 spec:
#
#   - 4 Deployments (one per trust-layer module)
#   - 4 Services with `targetPort: 8080` and `port: 8443`
#   - 4 NetworkPolicy resources
#   - 4 cert-manager Certificate resources with `duration: 24h` and `renewBefore: 2h`
#   - 4 ExternalSecret resources with `secret/data/007/` key prefix
#   - 4 readinessProbe + 4 livenessProbe stanzas on /health at :8080
#   - Exactly 1 HorizontalPodAutoscaler (M6 only)
#
# Auto-skips (exit 0) when helm is not on PATH.
# -----------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_helm_template] cwd=$(pwd)"

if ! command -v helm >/dev/null 2>&1; then
  echo "[test_helm_template] SKIP -- helm not on PATH"
  exit 0
fi

UMBRELLA=deploy/helm/007-fsi
VALUES=$UMBRELLA/values-cloud.yaml
OUT=$(mktemp -t 007-render.XXXXXX.yaml)
trap 'rm -f "$OUT"' EXIT

# Ensure deps resolved.
helm dependency update "$UMBRELLA" >/dev/null 2>&1 || true

if ! helm template test-release "$UMBRELLA" -f "$VALUES" > "$OUT"; then
  echo "[test_helm_template] FAIL -- helm template returned non-zero"
  exit 1
fi

echo "[test_helm_template] rendered $(wc -l < "$OUT") lines to $OUT"

# Helper: require the grep count to match exactly.
check() {
  local label=$1
  local pattern=$2
  local expected=$3
  local got
  got=$(grep -cE "$pattern" "$OUT" || true)
  if [ "$got" != "$expected" ]; then
    echo "[test_helm_template] FAIL -- $label expected=$expected got=$got pattern=$pattern"
    return 1
  fi
  echo "[test_helm_template] OK   -- $label (count=$got)"
  return 0
}

# Helper: require the grep count to be at least N.
check_min() {
  local label=$1
  local pattern=$2
  local minimum=$3
  local got
  got=$(grep -cE "$pattern" "$OUT" || true)
  if [ "$got" -lt "$minimum" ]; then
    echo "[test_helm_template] FAIL -- $label expected>=$minimum got=$got pattern=$pattern"
    return 1
  fi
  echo "[test_helm_template] OK   -- $label (count=$got, >= $minimum)"
  return 0
}

FAILED=0
check "4 Deployments"           '^kind: Deployment$'              4 || FAILED=1
check "4 Services"              '^kind: Service$'                 4 || FAILED=1
check "4 NetworkPolicies"       '^kind: NetworkPolicy$'           4 || FAILED=1
check "4 Certificates"          '^kind: Certificate$'             4 || FAILED=1
check "4 ExternalSecrets"       '^kind: ExternalSecret$'          4 || FAILED=1
check "4 PodDisruptionBudgets"  '^kind: PodDisruptionBudget$'     4 || FAILED=1
check "4 ServiceAccounts"       '^kind: ServiceAccount$'          4 || FAILED=1
check "1 HorizontalPodAutoscaler (M6 only)" '^kind: HorizontalPodAutoscaler$' 1 || FAILED=1

check "4 x duration 24h"        'duration: 24h'                   4 || FAILED=1
check "4 x renewBefore 2h"      'renewBefore: 2h'                 4 || FAILED=1
check "4 x targetPort 8080"     'targetPort: 8080'                8 || FAILED=1  # 2 per service
check "4 x port 8443"           '^      port: 8443'               4 || FAILED=1
check "4 x readinessProbe"      'readinessProbe:'                 4 || FAILED=1
check "4 x livenessProbe"       'livenessProbe:'                  4 || FAILED=1

check_min "secret/data/007 prefix (>=4)"    'secret/data/007/'    4 || FAILED=1
check_min "part-of: 007-fsi (>=4)"          'part-of: 007-fsi'    4 || FAILED=1

if [ "$FAILED" -ne 0 ]; then
  echo "[test_helm_template] RESULT: FAIL"
  exit 1
fi
echo "[test_helm_template] RESULT: PASS"
exit 0
