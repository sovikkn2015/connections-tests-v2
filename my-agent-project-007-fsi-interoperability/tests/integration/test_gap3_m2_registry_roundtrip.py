"""
Gap 3 — Integration tests.

Cross-module round-trips with M2 (real AuthorityPolicy) and verification
that Gap 3 does NOT accidentally reach into M10 or other modules.

Maps to T3.31 / T3.32 / T3.33 in .kiro/specs/gap3-wsp-to-yaml.md.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from m2_m4_policy_engine import AuthorityPolicy

from compliance.gap3_wsp_to_yaml import (
    MappingRegistry,
    SupervisoryFrequency,
    SupervisoryRole,
    WspSection,
    build_coverage_report,
    generate_manifest,
)


def _section(
    section_id: str,
    title: str = "t",
    body: str = "b",
) -> WspSection:
    return WspSection(
        wsp_id="WSP-ACME-2026",
        section_id=section_id,
        title=title,
        body=body,
        supervisory_role=SupervisoryRole.compliance_officer,
        frequency=SupervisoryFrequency.real_time,
        escalation_path=("compliance_officer",),
    )


# =============================================================================
# T3.31 — AuthorityPolicy.rule_table() cross-module round-trip.
# =============================================================================


def test_t3_31_m2_rule_table_matches_registry():
    """Every rule M2 exposes via rule_table() must surface in the
    registry's all_rule_applieds (mapped or orphan)."""
    authority = AuthorityPolicy()
    # Anchor every M2 WSP section to its own WspSection.
    m2_rows = authority.rule_table()
    wsp_sections = {row["wsp_section"] for row in m2_rows}
    sections = [_section(wsp) for wsp in sorted(wsp_sections)]
    reg = MappingRegistry.from_m2(authority, sections)
    # Every rule surfaced.
    assert set(reg.all_rule_applieds) == {
        row["rule_applied"] for row in m2_rows
    }
    # Full coverage, no orphans.
    report = build_coverage_report(reg)
    assert report.exit_code == 0
    assert report.orphan_rules == ()
    assert report.unmapped_sections == ()


# =============================================================================
# T3.32 — Gap 3 does NOT import M10 (module-boundary guarantee).
# =============================================================================


def test_t3_32_gap3_does_not_import_m10():
    """Gap 3's source must not import m10_audit_logger.

    This is an AST-level module-boundary guarantee: Gap 3's own
    Python sources must not name m10_audit_logger in any `import`
    or `from ... import ...` statement. The parent `compliance`
    aggregator may re-export other gaps that DO touch M10; that
    aggregation does not violate Gap 3's boundary.
    """
    import ast

    import compliance.gap3_wsp_to_yaml as pkg

    pkg_path = Path(pkg.__file__).parent
    offending: list[tuple[str, str]] = []
    for py_file in pkg_path.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("m10_audit_logger"):
                        offending.append((py_file.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("m10_audit_logger"):
                    offending.append((py_file.name, node.module))
    assert offending == [], (
        f"Gap 3 must not import m10_audit_logger — found: {offending}"
    )


# =============================================================================
# T3.33 — Full manifest round-trip via AuthorityPolicy: parseable YAML
# and stable digest under two independent AuthorityPolicy instances.
# =============================================================================


def test_t3_33_full_manifest_roundtrip_independent_policies():
    policy_a = AuthorityPolicy()
    policy_b = AuthorityPolicy()

    rows = policy_a.rule_table()
    wsp_ids = sorted({row["wsp_section"] for row in rows})
    sections = [
        _section(
            wsp_id,
            title=f"Section {wsp_id}",
            body=f"Procedure anchoring rule under {wsp_id}.",
        )
        for wsp_id in wsp_ids
    ]

    r1 = MappingRegistry.from_m2(policy_a, sections)
    r2 = MappingRegistry.from_m2(policy_b, sections)

    # Two independent policies produce the same registry structure.
    assert repr(r1) == repr(r2)

    manifest1 = generate_manifest(
        r1,
        generated_at=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
        last_updated_by="compliance_sme",
    )
    manifest2 = generate_manifest(
        r2,
        generated_at=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
        last_updated_by="compliance_sme",
    )
    assert manifest1 == manifest2

    # Manifest parses as YAML and has the required top-level keys.
    import yaml

    parsed = yaml.safe_load(manifest1)
    assert parsed["schema_version"] == "1.0.0"
    assert parsed["wsp_document_id"] == "WSP-ACME-2026"
    assert isinstance(parsed["mappings"], list)
    assert len(parsed["mappings"]) == len(wsp_ids)
    # All M2 WSP sections covered; no orphans.
    report = build_coverage_report(r1)
    assert report.exit_code == 0
