#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_helm_template_hybrid.sh
#
# Wave 4 deliverable. Spec: .kiro/specs/ops-hardening-wave4-hybrid-topology.md.
#
# Renders the umbrella chart with values-cloud.yaml + values-hybrid.yaml
# and asserts the hybrid topology contract (AC1.2, AC2.2, AC2.3, AC3.*,
# AC4.1, AC4.3, AC5.3).
#
# Skips gracefully (exit 0) when helm is not on PATH so CI envs without
# K8s tooling stay green. Always runs a Python YAML syntax check first
# so the file-level invariant is enforced even without helm.
# -----------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_helm_template_hybrid] cwd=$(pwd)"

# ---------- Phase 1: YAML syntax check (runs always) ----------
echo "[test_helm_template_hybrid] YAML syntax check"
python3 - <<'PY'
import pathlib, sys, yaml
root = pathlib.Path("deploy/helm/007-fsi")
for fname in ("values-cloud.yaml", "values-hybrid.yaml"):
    path = root / fname
    if not path.exists():
        print(f"[test_helm_template_hybrid] MISSING: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        doc = yaml.safe_load(f)
    assert isinstance(doc, dict), f"{fname} must be a mapping"
    print(f"  OK: {fname}")

# Load and verify the hybrid-specific keys exist.
with open(root / "values-hybrid.yaml") as f:
    hybrid = yaml.safe_load(f)

g = hybrid.get("global", {})
assert g.get("topology") == "hybrid", "global.topology must be 'hybrid'"
assert g.get("runtime") == "strands_sdk", "global.runtime must be 'strands_sdk' (Steering Rule 1)"

mesh = g.get("mesh", {})
assert mesh.get("bridgeAssumed") is True, "global.mesh.bridgeAssumed must be true"
assert mesh.get("bridgeKind") in ("istio-east-west", "linkerd-multicluster"), \
    f"global.mesh.bridgeKind must be one of the two supported stacks"

ann = g.get("topologyAnnotations", {})
assert ann.get("007.fsi/topology") == "hybrid", "topology annotation missing"
assert ann.get("007.fsi/runtime") == "strands_sdk", "runtime annotation missing"

onp = hybrid.get("onPrem", {})
assert onp.get("enabled") is True, "onPrem.enabled must be true in hybrid"
cert = onp.get("certBundle", {})
assert cert.get("secretName"), "onPrem.certBundle.secretName must be set"
rotation = cert.get("rotationDays")
assert isinstance(rotation, int) and 1 <= rotation <= 180, \
    "rotationDays sanity: 1..180"

adapters = onp.get("adapters", [])
assert isinstance(adapters, list) and len(adapters) >= 1, \
    "onPrem.adapters must list at least one on-prem adapter"
for a in adapters:
    assert a.get("name"), "adapter.name required"
    assert ":" in a.get("ingestEndpoint", ""), "adapter.ingestEndpoint must be host:port"

# M6 egress allowlist must include the on-prem adapter ingest FQDN (AC4.3).
m6 = hybrid.get("m6-mcp-gateway", {})
m6_allow = m6.get("egressAllowlist", [])
assert any(
    e.get("host", "").endswith(".internal")
    and e.get("port") == 8443
    for e in m6_allow
), "M6 egressAllowlist must include the on-prem adapter ingest FQDN"

# Intelligence-layer sub-charts must be enabled in hybrid.
for sc in ("m8-pipeline-engine", "m9-intent-router", "m12-supervisor"):
    assert hybrid.get(sc, {}).get("enabled") is True, \
        f"{sc}.enabled must be true in hybrid"

print("[test_helm_template_hybrid] YAML contract: OK")
PY

# ---------- Phase 2: helm template + contract greps ----------
if ! command -v helm >/dev/null 2>&1; then
  echo "[test_helm_template_hybrid] SKIP -- helm not on PATH (YAML contract OK)"
  exit 0
fi

HELM_VER=$(helm version --short 2>/dev/null || echo "unknown")
echo "[test_helm_template_hybrid] helm=$HELM_VER"

UMBRELLA=deploy/helm/007-fsi
VALUES_CLOUD=$UMBRELLA/values-cloud.yaml
VALUES_HYBRID=$UMBRELLA/values-hybrid.yaml
OUT=$(mktemp -t 007-hybrid.XXXXXX.yaml)
trap 'rm -f "$OUT"' EXIT

# Ensure deps resolved.
helm dependency update "$UMBRELLA" >/dev/null 2>&1 || true

if ! helm template test-hybrid "$UMBRELLA" \
    -f "$VALUES_CLOUD" -f "$VALUES_HYBRID" > "$OUT" 2>&1; then
  # In some environments the egress-narrowing wave's template may
  # require additional values. If so, report the failure but don't
  # fail the skip-graceful contract: operator runs helm directly.
  echo "[test_helm_template_hybrid] helm template failed -- dumping:"
  cat "$OUT"
  exit 1
fi

echo "[test_helm_template_hybrid] rendered $(wc -l < "$OUT") lines"

FAILED=0

assert_grep() {
  local label=$1
  local pattern=$2
  local minimum=$3
  local got
  got=$(grep -cE "$pattern" "$OUT" || true)
  if [ "$got" -lt "$minimum" ]; then
    echo "[test_helm_template_hybrid] FAIL -- $label expected>=$minimum got=$got pattern=$pattern"
    FAILED=1
    return
  fi
  echo "[test_helm_template_hybrid] OK   -- $label (count=$got, >= $minimum)"
}

refute_grep() {
  local label=$1
  local pattern=$2
  if grep -qE "$pattern" "$OUT"; then
    echo "[test_helm_template_hybrid] FAIL -- $label unexpected match for pattern=$pattern"
    FAILED=1
    return
  fi
  echo "[test_helm_template_hybrid] OK   -- $label (no match)"
}

# AC3.1-4: 4 trust-layer Deployments (M1, M2/M4, M6, M10).
assert_grep "4 trust-layer Deployments"     '^kind: Deployment' 4

# AC3.4: M10 audit-logger present.
assert_grep "M10 audit-logger Deployment"   'name: .*-m10-audit-logger' 1
assert_grep "M6 mcp-gateway Deployment"     'name: .*-m6-mcp-gateway'   1

# AC4.1 + AC5.3: no m7 or m11 pods rendered cloud-side in hybrid.
refute_grep "no m7- resources"              '^  name: .*-m7-'
refute_grep "no m11- resources"             '^  name: .*-m11-'

# AC4.3: the on-prem adapter ingest FQDN appears somewhere (most likely
# in the M6 NetworkPolicy egress block once the egress-narrowing wave
# is wired; grep leniently).
assert_grep "on-prem adapter ingest FQDN"   'adapters\.ingest\.example-firm\.internal' 1

if [ "$FAILED" -ne 0 ]; then
  echo "[test_helm_template_hybrid] RESULT: FAIL"
  exit 1
fi
echo "[test_helm_template_hybrid] RESULT: PASS"
exit 0
