#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_helm_template_egress.sh
#
# Wave 4 egress-narrowing verification.
# Spec: .kiro/specs/ops-hardening-wave4-egress-narrowing.md.
#
# Assertions:
#   Phase A (helm-default, NO values file):
#     * Rendered trust-layer NetworkPolicies contain `- {}` (AC8.1 compat).
#
#   Phase B (values-cloud.yaml, allowlist mode):
#     * No rendered NetworkPolicy contains `- {}` (AC1.1, AC5.1).
#     * Every NetworkPolicy has a kube-dns egress rule (AC3.*).
#     * Every NetworkPolicy has `policyTypes:` including `Egress` (AC5.1).
#
#   Phase C (negative test):
#     * `helm template` fails when egressMode=allowlist and a sub-chart
#       has an empty egressAllowlist (without the PrivateLink shortcut).
#
# Skips gracefully (exit 0) when helm is not on PATH.
# -----------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_helm_template_egress] cwd=$(pwd)"

if ! command -v helm >/dev/null 2>&1; then
  echo "[test_helm_template_egress] SKIP -- helm not on PATH"
  exit 0
fi

UMBRELLA=deploy/helm/007-fsi
VALUES_CLOUD=$UMBRELLA/values-cloud.yaml

helm dependency update "$UMBRELLA" >/dev/null 2>&1 || true

FAILED=0

# ============================================================================
# Phase A -- helm-default install (NO values file).
#
# Umbrella values.yaml pins global.networkPolicy.egressMode=allow-all so
# trust-layer NetworkPolicies still render `- {}` (Wave 1 compat gate).
# ============================================================================
OUT_A=$(mktemp -t 007-egress-A.XXXXXX.yaml)
trap 'rm -f "$OUT_A" "$OUT_B" "$OUT_C"' EXIT

if ! helm template default-install "$UMBRELLA" > "$OUT_A" 2>&1; then
  echo "[test_helm_template_egress] Phase A: helm template default FAILED --"
  cat "$OUT_A"
  exit 1
fi

if ! grep -qE '^    - \{\}\s*$' "$OUT_A"; then
  echo "[test_helm_template_egress] FAIL Phase A -- helm-default install did NOT render '- {}' (Wave 1 compat)"
  FAILED=1
else
  echo "[test_helm_template_egress] OK   Phase A -- helm-default install renders '- {}' as expected (Wave 1 compat)"
fi

# ============================================================================
# Phase B -- values-cloud.yaml (allowlist mode).
# ============================================================================
OUT_B=$(mktemp -t 007-egress-B.XXXXXX.yaml)

if ! helm template prod-install "$UMBRELLA" -f "$VALUES_CLOUD" > "$OUT_B" 2>&1; then
  echo "[test_helm_template_egress] Phase B: helm template with values-cloud FAILED --"
  cat "$OUT_B"
  exit 1
fi

# Split the render into one file per NetworkPolicy so we can per-policy assert.
# Extract NetworkPolicy docs into individual files via Python (awk can't
# handle nested YAML).
SPLIT_DIR=$(mktemp -d -t 007-egress-split.XXXXXX)
python3 - "$OUT_B" "$SPLIT_DIR" <<'PY'
import sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text()
outdir = pathlib.Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
# The render is a multi-document YAML stream. Split on '---' then keep
# only NetworkPolicy docs.
docs = src.split("\n---\n")
count = 0
for i, d in enumerate(docs):
    d = d.strip()
    if not d:
        continue
    # naive shape detection: look for 'kind: NetworkPolicy' in the doc.
    if any(line.strip() == "kind: NetworkPolicy" for line in d.splitlines()):
        count += 1
        (outdir / f"np-{count:02d}.yaml").write_text(d + "\n")
print(f"split {count} NetworkPolicy docs")
PY

# There should be at least 4 NetworkPolicies (Wave 1 trust layer); Wave 2
# intelligence layer is disabled in values-cloud.yaml so those don't render.
NP_COUNT=$(ls "$SPLIT_DIR" | wc -l | tr -d ' ')
if [ "$NP_COUNT" -lt 4 ]; then
  echo "[test_helm_template_egress] FAIL Phase B -- expected >=4 NetworkPolicies, got $NP_COUNT"
  FAILED=1
else
  echo "[test_helm_template_egress] OK   Phase B -- $NP_COUNT NetworkPolicies rendered"
fi

# Per-NP assertions.
for np in "$SPLIT_DIR"/*.yaml; do
  name="$(basename "$np")"

  # AC1.1, AC5.1: no '- {}' marker in allowlist mode.
  if grep -qE '^    - \{\}\s*$' "$np"; then
    echo "[test_helm_template_egress] FAIL Phase B -- '$name' still contains allow-all marker '- {}'"
    FAILED=1
    continue
  fi

  # AC3.*: kube-dns egress rule present.
  if ! grep -qE 'k8s-app:\s*kube-dns' "$np"; then
    echo "[test_helm_template_egress] FAIL Phase B -- '$name' missing kube-dns egress rule"
    FAILED=1
    continue
  fi

  # AC5.1: policyTypes includes Egress.
  if ! awk '/^  policyTypes:/,/^  ingress:/ { print }' "$np" | grep -q "Egress"; then
    echo "[test_helm_template_egress] FAIL Phase B -- '$name' missing 'Egress' in policyTypes"
    FAILED=1
    continue
  fi

  echo "[test_helm_template_egress] OK   Phase B -- '$name' narrowed + DNS + policyTypes"
done

# ============================================================================
# Phase C -- negative test: empty allowlist in allowlist mode must fail.
# ============================================================================
OUT_C=$(mktemp -t 007-egress-C.XXXXXX.yaml)
NEG_VALUES=$(mktemp -t 007-neg-values.XXXXXX.yaml)
trap 'rm -f "$NEG_VALUES"' EXIT INT TERM

cat > "$NEG_VALUES" <<EOF
global:
  networkPolicy:
    egressMode: allowlist
m1-identity:
  egressAllowlist: []
EOF

if helm template neg-install "$UMBRELLA" -f "$NEG_VALUES" > "$OUT_C" 2>&1; then
  echo "[test_helm_template_egress] FAIL Phase C -- expected helm template to fail on empty allowlist + allowlist mode"
  FAILED=1
else
  # Must fail with the expected message.
  if grep -q "egressAllowlist must be non-empty" "$OUT_C"; then
    echo "[test_helm_template_egress] OK   Phase C -- empty allowlist in allowlist mode fails as expected"
  else
    echo "[test_helm_template_egress] FAIL Phase C -- helm template failed but without the expected message"
    cat "$OUT_C"
    FAILED=1
  fi
fi

rm -f "$NEG_VALUES"
rm -rf "$SPLIT_DIR"

if [ "$FAILED" -ne 0 ]; then
  echo "[test_helm_template_egress] RESULT: FAIL"
  exit 1
fi
echo "[test_helm_template_egress] RESULT: PASS"
exit 0
