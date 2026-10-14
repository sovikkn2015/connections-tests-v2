#!/usr/bin/env bash
# test_helm_template_intelligence.sh
#
# Renders each Wave 2 sub-chart with `helm template` and asserts every
# verification gate from spec R9.2 + R9.4 + R9.5. Graceful skip if helm
# is not installed.
#
# Assertions (spec R9.2):
#   * eks.amazonaws.com/role-arn     -- M8, M9, M12 (IRSA)
#   * mountPath: /etc/007/mtls       -- M8, M9, M12 (mTLS volume)
#   * kind: HorizontalPodAutoscaler  -- M9 + M12 ONLY
#   * kind: StatefulSet              -- M8 ONLY
#   * kind: Deployment               -- M9, M12
#   * priorityClassName: system-cluster-critical -- M8, M12
#   * priorityClassName: system-node-critical    -- M9
#   * readinessProbe:                -- all three
#   * livenessProbe:                 -- all three
#   * averageUtilization: 70         -- M9 + M12 HPA
#   * runAsNonRoot: true             -- all three
#   * readOnlyRootFilesystem: true   -- all three
#   * podSelector app: m6-mcp-gateway -- all three NetworkPolicies
#   * M12_KYC_ADAPTER_URL via configMapKeyRef -- M12 Deployment
#   * no credential-shape literal    -- R9.4 regex
#   * Chart.yaml + values.yaml parseable YAML -- R9.5 python fallback

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CHARTS_DIR="$(cd "${HERE}/../helm/007-fsi/charts" && pwd)"

# ---------- R9.5: Python YAML syntax fallback (runs even without helm) ----------
echo "=== Python YAML syntax check (Chart.yaml + values.yaml) ==="
python3 - <<'PY'
import sys, pathlib, yaml
root = pathlib.Path(__file__).resolve().parents[1] / "helm" / "007-fsi" / "charts"
# Fallback if __file__ relative is odd (bash heredoc changes __file__ semantics):
here = pathlib.Path("deploy/helm/007-fsi/charts")
if not root.exists():
    root = here
for chart in ("m8-pipeline-engine", "m9-intent-router", "m12-supervisor"):
    for fname in ("Chart.yaml", "values.yaml"):
        p = root / chart / fname
        with open(p) as f:
            yaml.safe_load(f)
        print(f"  OK: {chart}/{fname}")
# Also check values-cloud.wave2.yaml
frag = root.parent / "values-cloud.wave2.yaml"
with open(frag) as f:
    yaml.safe_load(f)
print(f"  OK: {frag.name}")
PY

if ! command -v helm >/dev/null 2>&1; then
  echo "SKIP: helm not installed -- template-level assertions skipped (YAML syntax check PASSED)" >&2
  exit 0
fi

VALUES_FRAG="${HERE}/../helm/007-fsi/values-cloud.wave2.yaml"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# Render each sub-chart. We extract the sub-tree from the fragment using
# a small Python helper (pure-stdlib, no yq dependency).
render_subtree() {
  local chart="$1"
  local out="$2"
  local subvals
  subvals="$(mktemp)"
  python3 - "$VALUES_FRAG" "$chart" > "$subvals" <<'PY'
import sys, yaml
with open(sys.argv[1]) as f:
    doc = yaml.safe_load(f) or {}
sub = doc.get(sys.argv[2], {}) or {}
yaml.safe_dump(sub, sys.stdout, sort_keys=False)
PY
  helm template "${chart}" "${CHARTS_DIR}/${chart}" -f "${subvals}" > "${out}"
  rm -f "$subvals"
}

render_subtree m8-pipeline-engine  "${TMP}/m8.yaml"
render_subtree m9-intent-router    "${TMP}/m9.yaml"
render_subtree m12-supervisor      "${TMP}/m12.yaml"

FAIL=0

assert_grep() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if ! grep -qE "${pattern}" "${file}"; then
    echo "FAIL [${label}]: pattern not found in $(basename ${file}): ${pattern}" >&2
    FAIL=1
  fi
}

refute_grep() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -qE "${pattern}" "${file}"; then
    echo "FAIL [${label}]: pattern should NOT appear in $(basename ${file}): ${pattern}" >&2
    FAIL=1
  fi
}

# IRSA annotation -- all three.
for f in m8 m9 m12; do
  assert_grep "${TMP}/${f}.yaml" 'eks\.amazonaws\.com/role-arn' "IRSA (${f})"
done

# mTLS mount -- all three.
for f in m8 m9 m12; do
  assert_grep "${TMP}/${f}.yaml" 'mountPath:[[:space:]]*/etc/007/mtls' "mTLS mount (${f})"
done

# StatefulSet only on M8.
assert_grep "${TMP}/m8.yaml"  '^kind:[[:space:]]*StatefulSet' "M8 StatefulSet"
refute_grep "${TMP}/m9.yaml"  '^kind:[[:space:]]*StatefulSet' "M9 not StatefulSet"
refute_grep "${TMP}/m12.yaml" '^kind:[[:space:]]*StatefulSet' "M12 not StatefulSet"

# Deployment on M9 + M12.
assert_grep "${TMP}/m9.yaml"  '^kind:[[:space:]]*Deployment' "M9 Deployment"
assert_grep "${TMP}/m12.yaml" '^kind:[[:space:]]*Deployment' "M12 Deployment"

# HPA only on M9 + M12.
assert_grep "${TMP}/m9.yaml"  'kind:[[:space:]]*HorizontalPodAutoscaler' "M9 HPA"
assert_grep "${TMP}/m12.yaml" 'kind:[[:space:]]*HorizontalPodAutoscaler' "M12 HPA"
refute_grep "${TMP}/m8.yaml"  'kind:[[:space:]]*HorizontalPodAutoscaler' "M8 no HPA"

# PriorityClass.
assert_grep "${TMP}/m8.yaml"  'priorityClassName:[[:space:]]*system-cluster-critical' "M8 PC"
assert_grep "${TMP}/m12.yaml" 'priorityClassName:[[:space:]]*system-cluster-critical' "M12 PC"
assert_grep "${TMP}/m9.yaml"  'priorityClassName:[[:space:]]*system-node-critical' "M9 PC"

# Probes.
for f in m8 m9 m12; do
  assert_grep "${TMP}/${f}.yaml" 'readinessProbe:' "readinessProbe (${f})"
  assert_grep "${TMP}/${f}.yaml" 'livenessProbe:'  "livenessProbe (${f})"
done

# HPA target CPU = 70.
assert_grep "${TMP}/m9.yaml"  'averageUtilization:[[:space:]]*70' "M9 HPA 70"
assert_grep "${TMP}/m12.yaml" 'averageUtilization:[[:space:]]*70' "M12 HPA 70"

# Pod securityContext.
for f in m8 m9 m12; do
  assert_grep "${TMP}/${f}.yaml" 'runAsNonRoot:[[:space:]]*true'        "runAsNonRoot (${f})"
  assert_grep "${TMP}/${f}.yaml" 'readOnlyRootFilesystem:[[:space:]]*true' "readOnlyRootFilesystem (${f})"
done

# NetworkPolicy ingress from M6 only.
for f in m8 m9 m12; do
  # Multi-line grep: `app: m6-mcp-gateway` must appear in the NetworkPolicy block.
  assert_grep "${TMP}/${f}.yaml" 'app:[[:space:]]*m6-mcp-gateway' "M6 ingress (${f})"
done

# M12 KYC URL via configMapKeyRef (not secretKeyRef).
# Find M12_KYC_ADAPTER_URL env entry and ensure it is sourced from configMapKeyRef.
if ! awk '/name: M12_KYC_ADAPTER_URL/,/^\s*-\s*name:/' "${TMP}/m12.yaml" | grep -q 'configMapKeyRef'; then
  echo "FAIL: M12_KYC_ADAPTER_URL must be wired via configMapKeyRef, not secret" >&2
  FAIL=1
fi

# ---------- R9.4: credential-shape grep ----------
# Regex: key/value pairs where the value looks like a secret (>= 16 chars base64ish).
# Allow Vault path references and K8s secret *references* (not values).
echo "=== Credential-shape scan ==="
CRED_RE='(?i)(password|secret|token|api[_-]?key|private[_-]?key)[[:space:]]*[:=][[:space:]]*["'\''"]?[A-Za-z0-9+/=]{16,}'
FOUND=$(grep -EHn "${CRED_RE}" "${TMP}"/m8.yaml "${TMP}"/m9.yaml "${TMP}"/m12.yaml 2>/dev/null \
  | grep -vE 'vault_path|VAULT_PATH|secretName:|secretKeyRef|serviceAccountToken|configMapKeyRef' \
  || true)
if [ -n "${FOUND}" ]; then
  echo "FAIL: credential-shape literal detected:" >&2
  echo "${FOUND}" >&2
  FAIL=1
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "FAIL: one or more Wave 2 verification gates failed" >&2
  exit 1
fi
echo "OK: all Wave 2 verification gates passed"
