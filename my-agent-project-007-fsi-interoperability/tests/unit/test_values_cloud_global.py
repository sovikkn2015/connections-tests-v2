"""B11 — Helm values-cloud.yaml top-level `global:` block invariants.

This test exists because `values-cloud.yaml` previously declared
`global:` twice (lines 14 + 128). PyYAML / Helm silently keeps the LAST
one, which meant `topology`, `namespace`, `imageRegistry`,
`tenantRoleArn`, `labels`, and `certManager` were dropped at every
production render. Rule 21 (cert duration 24h), Rule 23 (tenantRoleArn
for per-tenant KMS), Rule 25 (namespace isolation) all failed in prod
without any test catching it.

The assertions below lock the merged `global:` shape so a future
accidental re-splitting of the block (or a drift away from the expected
sub-keys) fails at CI time instead of at deploy time.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repo-relative path. tests/unit -> repo root is 2 parents up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALUES_PATH = (
    _REPO_ROOT
    / "deploy"
    / "helm"
    / "007-fsi"
    / "values-cloud.yaml"
)


def _load_values() -> dict:
    """Load values-cloud.yaml with the same semantics Helm uses."""
    assert _VALUES_PATH.exists(), f"values file missing: {_VALUES_PATH}"
    with _VALUES_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), "values-cloud.yaml must parse to a mapping"
    return data


# ---------------------------------------------------------------------------
# B11.1 -- exactly one top-level `global:` mapping
# ---------------------------------------------------------------------------


def test_values_cloud_has_single_global_block() -> None:
    """PyYAML collapses duplicate top-level keys -- but we need the SOURCE to have one."""
    raw = _VALUES_PATH.read_text(encoding="utf-8")
    top_level_global_lines = [
        line for line in raw.splitlines()
        if line.startswith("global:")
    ]
    assert len(top_level_global_lines) == 1, (
        "values-cloud.yaml must declare exactly ONE top-level 'global:' block; "
        f"found {len(top_level_global_lines)}. Historical duplicate bug -- see B11."
    )


# ---------------------------------------------------------------------------
# B11.2 -- merged global contains all expected sub-keys
# ---------------------------------------------------------------------------


def test_global_contains_all_expected_subkeys() -> None:
    data = _load_values()
    g = data["global"]
    assert isinstance(g, dict), "global must be a mapping"

    expected = {
        "topology",
        "namespace",
        "imageRegistry",
        "tenantRoleArn",
        "labels",
        "certManager",
        "networkPolicy",
        "privateLinkCidrs",
    }
    missing = expected - set(g.keys())
    assert not missing, f"global missing keys: {sorted(missing)}"


def test_global_topology_is_cloud() -> None:
    g = _load_values()["global"]
    assert g["topology"] == "cloud"


def test_global_namespace_is_trust_layer() -> None:
    g = _load_values()["global"]
    assert g["namespace"] == "trust-layer"


def test_global_image_registry_is_set() -> None:
    g = _load_values()["global"]
    assert isinstance(g["imageRegistry"], str)
    assert len(g["imageRegistry"]) > 0


def test_global_tenant_role_arn_is_set() -> None:
    g = _load_values()["global"]
    assert isinstance(g["tenantRoleArn"], str)
    assert g["tenantRoleArn"].startswith("arn:aws:iam::")


def test_global_labels_has_part_of_and_managed_by() -> None:
    g = _load_values()["global"]
    labels = g["labels"]
    assert isinstance(labels, dict)
    assert labels.get("app.kubernetes.io/part-of") == "007-fsi"
    assert labels.get("app.kubernetes.io/managed-by") == "helm"


# ---------------------------------------------------------------------------
# B11.3 -- certManager.duration is 24h (Rule 21)
# ---------------------------------------------------------------------------


def test_global_cert_manager_duration_is_24h() -> None:
    g = _load_values()["global"]
    cm = g["certManager"]
    assert isinstance(cm, dict)
    assert cm["duration"] == "24h", (
        "Steering Rule 21 requires 24h mTLS rotation on the trust layer."
    )
    assert cm["renewBefore"] == "2h"
    assert cm["issuerName"] == "letsencrypt-prod"
    assert cm["issuerKind"] == "ClusterIssuer"


# ---------------------------------------------------------------------------
# Network policy + PrivateLink CIDRs (the bits that already survived)
# ---------------------------------------------------------------------------


def test_global_network_policy_egress_mode_is_allowlist() -> None:
    g = _load_values()["global"]
    np = g["networkPolicy"]
    assert isinstance(np, dict)
    assert np["egressMode"] == "allowlist"


def test_global_private_link_cidrs_has_bedrock_runtime() -> None:
    g = _load_values()["global"]
    plc = g["privateLinkCidrs"]
    assert isinstance(plc, dict)
    assert "bedrockRuntime" in plc
    # CIDR shape check -- not an equality check on the exact prefix because
    # operators may override; shape invariant: non-empty string containing "/".
    cidr = plc["bedrockRuntime"]
    assert isinstance(cidr, str) and "/" in cidr


# ---------------------------------------------------------------------------
# B11.6 -- sub-chart blocks retain their structure post-merge
# ---------------------------------------------------------------------------


def test_sub_chart_blocks_intact() -> None:
    """Every Wave-1 + Wave-4 sub-chart key is still a top-level entry."""
    data = _load_values()
    expected_subcharts = {
        "externalSecrets",
        "m1-identity",
        "m2-m4-policy-engine",
        "m6-mcp-gateway",
        "m10-audit-logger",
        "m8-pipeline-engine",
        "m9-intent-router",
        "m12-supervisor",
        "m11-blpapi-adapter",
        "m11-grpc-adapter",
        "m13-fix-bridge",
    }
    missing = expected_subcharts - set(data.keys())
    assert not missing, f"sub-chart top-level blocks missing: {sorted(missing)}"


def test_trust_layer_egress_allowlists_present() -> None:
    """The ops-hardening-wave4 egress allowlists survived the merge."""
    data = _load_values()

    # M1 Vault + cert-manager
    m1 = data["m1-identity"]
    assert isinstance(m1.get("egressAllowlist"), list)
    assert any(e.get("host") == "10.0.0.10" for e in m1["egressAllowlist"])

    # M6 intra-cluster trust peers
    m6 = data["m6-mcp-gateway"]
    assert isinstance(m6.get("egressAllowlist"), list)
    pod_labels = [
        e.get("podLabels", {}).get("app.kubernetes.io/name")
        for e in m6["egressAllowlist"]
    ]
    assert "m1-identity" in pod_labels
    assert "m2-m4-policy-engine" in pod_labels
    assert "m10-audit-logger" in pod_labels

    # M10 egress hits Langfuse + WORM + CRM + Vault
    m10 = data["m10-audit-logger"]
    assert isinstance(m10.get("egressAllowlist"), list)
    hosts = {e.get("host") for e in m10["egressAllowlist"]}
    # Langfuse, S3/MinIO, CRM, Vault
    expected_host_count = 4
    assert len(hosts) == expected_host_count, (
        f"M10 egress should cover Langfuse + S3 + CRM + Vault (4 hosts); "
        f"got {sorted(hosts)}"
    )
