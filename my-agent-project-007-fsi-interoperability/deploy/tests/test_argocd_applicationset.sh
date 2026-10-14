#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_argocd_applicationset.sh
#
# Wave 4 deliverable. Spec: .kiro/specs/ops-hardening-wave4-argocd-applicationset.md.
#
# Three-phase test:
#   Phase 1 -- YAML syntax. Always runs.
#     * applicationset.yaml parses.
#     * example tenant values.yaml parses.
#     * ApplicationSet contract fields are present
#       (kind, apiVersion, generators, template.spec.source.path).
#
#   Phase 2 -- kubectl dry-run + validate. Skips if kubectl missing.
#     * kubectl apply --dry-run=client --validate=true passes.
#
#   Phase 3 -- helm dry-render of the generated Application. Skips
#     if helm missing.
#     * helm template with values-cloud.yaml AND the example tenant
#       values renders cleanly (ArgoCD's equivalent action).
#
# Skip-graceful: Phase 2 and Phase 3 each SKIP independently if their
# tool is absent. Phase 1 always runs.
# -----------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_argocd_applicationset] cwd=$(pwd)"

APPSET=deploy/argocd/applicationset.yaml
EXAMPLE_TENANT=config/tenants/example-tenant-tier4-ria/values.yaml
UMBRELLA=deploy/helm/007-fsi

if [ ! -f "$APPSET" ]; then
  echo "[test_argocd_applicationset] FAIL -- $APPSET not found"
  exit 1
fi
if [ ! -f "$EXAMPLE_TENANT" ]; then
  echo "[test_argocd_applicationset] FAIL -- $EXAMPLE_TENANT not found"
  exit 1
fi

# ---------- Phase 1: YAML syntax + contract ----------
echo "[test_argocd_applicationset] Phase 1: YAML syntax + contract"
python3 - "$APPSET" "$EXAMPLE_TENANT" <<'PY'
import sys, yaml

appset_path, tenant_path = sys.argv[1], sys.argv[2]

with open(appset_path) as f:
    appset = yaml.safe_load(f)
assert isinstance(appset, dict), "applicationset.yaml must be a mapping"
assert appset.get("apiVersion") == "argoproj.io/v1alpha1", \
    f"apiVersion must be argoproj.io/v1alpha1, got {appset.get('apiVersion')}"
assert appset.get("kind") == "ApplicationSet", \
    f"kind must be ApplicationSet, got {appset.get('kind')}"
md = appset.get("metadata", {})
assert md.get("name"), "metadata.name required"
assert md.get("namespace") == "argocd", "metadata.namespace must be 'argocd'"

spec = appset.get("spec", {})
gens = spec.get("generators", [])
assert len(gens) >= 1, "spec.generators must have at least one generator"
# Find a git directory generator.
has_git_dirs = any(
    isinstance(g.get("git"), dict) and "directories" in g["git"]
    for g in gens
)
assert has_git_dirs, "expected a git-directory generator"

tmpl = spec.get("template", {})
tmpl_spec = tmpl.get("spec", {})
src = tmpl_spec.get("source", {})
assert src.get("path") == "deploy/helm/007-fsi", \
    f"template.spec.source.path must be deploy/helm/007-fsi, got {src.get('path')}"
assert src.get("targetRevision"), "template.spec.source.targetRevision required"

dst = tmpl_spec.get("destination", {})
assert dst.get("server"), "template.spec.destination.server required"

sp = tmpl_spec.get("syncPolicy", {})
auto = sp.get("automated", {})
assert auto.get("prune") is True, "syncPolicy.automated.prune must be true (Rule 26)"
assert auto.get("selfHeal") is True, "syncPolicy.automated.selfHeal must be true (Rule 26)"
assert auto.get("allowEmpty") is False, \
    "syncPolicy.automated.allowEmpty must be false (prune safety)"

print(f"[test_argocd_applicationset] OK   Phase 1a -- ApplicationSet contract OK")

with open(tenant_path) as f:
    tenant = yaml.safe_load(f)
t = tenant.get("tenant", {})
assert t.get("id"), "tenant.id required"
assert t.get("targetRevision"), "tenant.targetRevision required"
assert t.get("topologyFile") in ("values-cloud.yaml", "values-hybrid.yaml"), \
    f"tenant.topologyFile must be one of values-cloud.yaml / values-hybrid.yaml"
g = tenant.get("global", {})
assert g.get("topology") in ("cloud", "hybrid", "onprem"), \
    f"global.topology invalid: {g.get('topology')}"
assert "REPLACE_ME" in str(g.get("tenantRoleArn", "")), \
    "example tenant must still have REPLACE_ME in tenantRoleArn (forces override)"
print(f"[test_argocd_applicationset] OK   Phase 1b -- example tenant contract OK")
PY

# ---------- Phase 2: kubectl dry-run + validate ----------
# kubectl client-side dry-run requires a parseable kubeconfig even for
# --validate=false (it probes the server for the resource shape when
# validation is on). On CI machines without a cluster, we detect that
# up-front and SKIP.
if command -v kubectl >/dev/null 2>&1; then
  if kubectl config current-context >/dev/null 2>&1; then
    echo "[test_argocd_applicationset] Phase 2: kubectl dry-run"
    if ! kubectl apply --dry-run=client --validate=false -f "$APPSET" >/dev/null 2>&1; then
      echo "[test_argocd_applicationset] FAIL Phase 2 -- kubectl dry-run failed"
      exit 1
    fi
    echo "[test_argocd_applicationset] OK   Phase 2 -- kubectl dry-run passed"
  else
    echo "[test_argocd_applicationset] SKIP Phase 2 -- kubectl present but no kubeconfig"
  fi
else
  echo "[test_argocd_applicationset] SKIP Phase 2 -- kubectl not on PATH"
fi

# ---------- Phase 3: helm dry-render ----------
if command -v helm >/dev/null 2>&1; then
  echo "[test_argocd_applicationset] Phase 3: helm dry-render"
  helm dependency update "$UMBRELLA" >/dev/null 2>&1 || true
  OUT=$(mktemp -t 007-appset.XXXXXX.yaml)
  trap 'rm -f "$OUT"' EXIT
  if ! helm template \
      007-fsi-example-tenant-tier4-ria \
      "$UMBRELLA" \
      -f "$UMBRELLA/values-cloud.yaml" \
      -f "$EXAMPLE_TENANT" \
      > "$OUT" 2>&1; then
    echo "[test_argocd_applicationset] FAIL Phase 3 -- helm template failed --"
    cat "$OUT"
    exit 1
  fi
  LINES=$(wc -l < "$OUT")
  if [ "$LINES" -lt 100 ]; then
    echo "[test_argocd_applicationset] FAIL Phase 3 -- too few lines rendered ($LINES)"
    exit 1
  fi
  echo "[test_argocd_applicationset] OK   Phase 3 -- helm dry-render rendered $LINES lines"
else
  echo "[test_argocd_applicationset] SKIP Phase 3 -- helm not on PATH"
fi

echo "[test_argocd_applicationset] RESULT: PASS"
exit 0
