"""
Gap 3 — Unit tests.

Covers T3.1..T3.33 (minus integration T3.31..T3.33 which live in
tests/integration/). Maps 1:1 to acceptance criteria in
.kiro/specs/gap3-wsp-to-yaml.md §4.
"""

from __future__ import annotations

import ast
import sys
import textwrap
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from m2_m4_policy_engine import (
    RULE_APPLIED_RE as M2_RULE_RE,
    WSP_SECTION_RE as M2_WSP_RE,
    AuthorityPolicy,
)

from compliance.gap3_wsp_to_yaml import (
    SECTION_SCHEMA_VERSION,
    WSP_SECTION_RE,
    CoverageReport,
    FileReader,
    InMemoryFileReader,
    LocalFileReader,
    MappingRegistry,
    RegoRuleAnchor,
    RuleAnchor,
    SupervisoryFrequency,
    SupervisoryRole,
    WspIngestError,
    WspMapping,
    WspSection,
    build_coverage_report,
    generate_manifest,
    ingest_wsp_yaml,
    scan_rego_directory,
    scan_rego_file,
    sha256_digest,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_section(
    section_id: str = "WSP-TRD-3.1",
    *,
    title: str = "Restricted List",
    body: str = "Firm maintains a restricted list.",
    role: SupervisoryRole = SupervisoryRole.compliance_officer,
    freq: SupervisoryFrequency = SupervisoryFrequency.real_time,
    escalation: tuple[str, ...] = ("compliance_officer",),
    last_reviewed: date | None = None,
    wsp_id: str = "WSP-ACME-2026",
) -> WspSection:
    return WspSection(
        wsp_id=wsp_id,
        section_id=section_id,
        title=title,
        body=body,
        supervisory_role=role,
        frequency=freq,
        escalation_path=escalation,
        last_reviewed=last_reviewed,
    )


_FIXTURE_GENERATED_AT = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
_FIXTURE_UPDATED_BY = "compliance_sme"


@pytest.fixture
def three_sections() -> list[WspSection]:
    return [
        _make_section(
            section_id="WSP-TRD-3.1",
            title="Restricted List",
            last_reviewed=date(2026, 7, 1),
            escalation=("compliance_officer", "chief_compliance_officer"),
        ),
        _make_section(
            section_id="WSP-TRD-3.2",
            title="Trading Window",
            body="Trading windows are enforced.",
            role=SupervisoryRole.principal,
            freq=SupervisoryFrequency.daily,
            escalation=("principal",),
        ),
        _make_section(
            section_id="WSP-ADV-1.1",
            title="Advisor reads own clients",
            body="Own-clients-only policy.",
            escalation=("compliance_officer",),
        ),
    ]


# =============================================================================
# T3.1 — Enums
# =============================================================================


def test_t3_1a_supervisory_role_values():
    expected = {
        "chief_compliance_officer",
        "compliance_officer",
        "principal",
        "registered_rep",
        "operations",
        "cco_designee",
        "audit_committee",
    }
    assert {r.value for r in SupervisoryRole} == expected


def test_t3_1b_supervisory_frequency_values():
    expected = {
        "real_time",
        "intraday",
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "ad_hoc",
    }
    assert {f.value for f in SupervisoryFrequency} == expected


# =============================================================================
# T3.2 — WspSection frozen + round-trip
# =============================================================================


def test_t3_2_wspsection_frozen_and_roundtrip():
    sec = _make_section()
    assert sec.schema_version == "1.0.0"
    assert sec.section_id == "WSP-TRD-3.1"
    with pytest.raises(ValidationError):
        sec.title = "mutated"  # type: ignore[misc]

    dumped = sec.model_dump(mode="json")
    # Round-trip via constructor.
    sec2 = WspSection(**dumped)
    assert sec2 == sec


def test_t3_2_section_id_must_match_regex():
    with pytest.raises(ValidationError):
        _make_section(section_id="bogus-1")


def test_t3_2_last_reviewed_accepts_iso_string():
    sec = WspSection(
        wsp_id="WSP-X-1",
        section_id="WSP-TRD-3.1",
        title="t",
        body="b",
        supervisory_role=SupervisoryRole.compliance_officer,
        frequency=SupervisoryFrequency.real_time,
        escalation_path=("compliance_officer",),
        last_reviewed="2026-07-01",  # type: ignore[arg-type]
    )
    assert sec.last_reviewed == date(2026, 7, 1)


# =============================================================================
# T3.3 — Coupling: WSP_SECTION_RE pattern == M2's
# =============================================================================


def test_t3_3_wsp_section_regex_coupling():
    assert WSP_SECTION_RE.pattern == M2_WSP_RE.pattern


def test_t3_3_rule_applied_regex_coupling():
    from compliance.gap3_wsp_to_yaml.models import RULE_APPLIED_RE as G3_RE

    assert G3_RE.pattern == M2_RULE_RE.pattern


# =============================================================================
# T3.4 — escalation_path validation
# =============================================================================


def test_t3_4_escalation_path_empty_rejected():
    with pytest.raises(ValidationError):
        _make_section(escalation=())


def test_t3_4_escalation_path_too_long_rejected():
    with pytest.raises(ValidationError):
        _make_section(escalation=tuple(["compliance_officer"] * 11))


def test_t3_4_escalation_path_unknown_role_rejected():
    with pytest.raises(ValidationError):
        _make_section(escalation=("chief_wizard",))


def test_t3_4_escalation_path_duplicate_allowed():
    sec = _make_section(escalation=("principal", "principal"))
    assert sec.escalation_path == ("principal", "principal")


# =============================================================================
# T3.5 — PII regex on title / body / last_updated_by
# =============================================================================


@pytest.mark.parametrize(
    "bad",
    [
        "Contact ssn 123-45-6789 for review",
        "Alt contact alice@example.com",
        "Routing 123456789012345",
        "IBAN DE89370400440532013000",
    ],
)
def test_t3_5_pii_rejected_in_title(bad):
    with pytest.raises(ValidationError):
        _make_section(title=bad)


@pytest.mark.parametrize(
    "bad",
    [
        "Escalate to 123-45-6789.",
        "Email compliance@firm.com",
        "Account 123456789012",
        "See IBAN DE89370400440532013000",
    ],
)
def test_t3_5_pii_rejected_in_body(bad):
    with pytest.raises(ValidationError):
        _make_section(body=bad)


def test_t3_5_clean_body_accepted():
    # Role names instead of emails — the canonical pattern.
    _make_section(body="Escalate to compliance_officer then principal.")


# =============================================================================
# T3.6 — RuleAnchor coupling to M2
# =============================================================================


def test_t3_6_rule_anchor_happy_path():
    a = RuleAnchor(
        rule_applied="authority/advisor/restricted_list.v1",
        opa_bundle="authority",
        rego_file="authority/restricted_list.rego",
        rego_rule="restricted_list",
    )
    assert a.rule_applied == "authority/advisor/restricted_list.v1"


def test_t3_6_rule_applied_bad_shape_rejected():
    with pytest.raises(ValidationError):
        RuleAnchor(
            rule_applied="not-a-rule-path",
            opa_bundle="authority",
            rego_file="authority/x.rego",
            rego_rule="x",
        )


def test_t3_6_rego_file_bad_shape_rejected():
    with pytest.raises(ValidationError):
        RuleAnchor(
            rule_applied="authority/advisor/x.v1",
            opa_bundle="authority",
            rego_file="authority/X.rego",  # capital letter rejected
            rego_rule="x",
        )


# =============================================================================
# T3.7 — WspMapping empty rules allowed
# =============================================================================


def test_t3_7_wsp_mapping_empty_rules_allowed():
    sec = _make_section()
    m = WspMapping(wsp_section=sec, rules=())
    assert m.rules == ()


# =============================================================================
# T3.8 — ingest_wsp_yaml happy path
# =============================================================================


_GOOD_YAML = textwrap.dedent(
    """
    wsp_id: "WSP-ACME-2026"
    sections:
      - section_id: "WSP-TRD-3.1"
        title: "Restricted List"
        body: "Firm maintains a restricted list."
        supervisory_role: "compliance_officer"
        frequency: "real_time"
        escalation_path:
          - compliance_officer
          - chief_compliance_officer
        last_reviewed: "2026-07-01"
      - section_id: "WSP-TRD-3.2"
        title: "Trading Window"
        body: "Trading windows are enforced."
        supervisory_role: "principal"
        frequency: "daily"
        escalation_path:
          - principal
      - section_id: "WSP-ADV-1.1"
        title: "Advisor reads own clients"
        body: "Own-clients-only policy."
        supervisory_role: "compliance_officer"
        frequency: "real_time"
        escalation_path:
          - compliance_officer
    """
)


def test_t3_8_ingest_happy_path():
    reader = InMemoryFileReader({"wsp.yaml": _GOOD_YAML})
    sections = ingest_wsp_yaml(reader, "wsp.yaml")
    assert len(sections) == 3
    assert [s.section_id for s in sections] == [
        "WSP-TRD-3.1",
        "WSP-TRD-3.2",
        "WSP-ADV-1.1",
    ]
    assert sections[0].last_reviewed == date(2026, 7, 1)


# =============================================================================
# T3.9 — ingest error paths
# =============================================================================


def test_t3_9_missing_file():
    reader = InMemoryFileReader({})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "no.yaml")


def test_t3_9_non_yaml_bytes():
    reader = InMemoryFileReader({"w.yaml": "not: yaml: [["})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "w.yaml")


def test_t3_9_yaml_is_list_at_top_level():
    reader = InMemoryFileReader({"w.yaml": "- just-a-list\n"})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "w.yaml")


def test_t3_9_missing_required_field():
    bad = textwrap.dedent(
        """
        wsp_id: "WSP-X-1"
        sections:
          - section_id: "WSP-TRD-3.1"
            title: "t"
            supervisory_role: "compliance_officer"
            frequency: "real_time"
            escalation_path: ["compliance_officer"]
        """
    )
    reader = InMemoryFileReader({"w.yaml": bad})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "w.yaml")


def test_t3_9_duplicate_section_id():
    dup = textwrap.dedent(
        """
        wsp_id: "WSP-X-1"
        sections:
          - section_id: "WSP-TRD-3.1"
            title: "A"
            body: "b"
            supervisory_role: "compliance_officer"
            frequency: "real_time"
            escalation_path: ["compliance_officer"]
          - section_id: "WSP-TRD-3.1"
            title: "B"
            body: "b"
            supervisory_role: "compliance_officer"
            frequency: "real_time"
            escalation_path: ["compliance_officer"]
        """
    )
    reader = InMemoryFileReader({"w.yaml": dup})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "w.yaml")


def test_t3_9_invalid_enum_value():
    bad = textwrap.dedent(
        """
        wsp_id: "WSP-X-1"
        sections:
          - section_id: "WSP-TRD-3.1"
            title: "t"
            body: "b"
            supervisory_role: "chief_wizard"
            frequency: "real_time"
            escalation_path: ["compliance_officer"]
        """
    )
    reader = InMemoryFileReader({"w.yaml": bad})
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, "w.yaml")


def test_t3_9_local_file_reader_missing(tmp_path):
    reader = LocalFileReader()
    with pytest.raises(WspIngestError):
        ingest_wsp_yaml(reader, str(tmp_path / "nope.yaml"))


# =============================================================================
# T3.10 — MappingRegistry.from_m2
# =============================================================================


def test_t3_10_from_m2_happy_path(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    # 3 mappings + 3 anchored rules among 11 M2 rules.
    assert len(reg.mappings) == 3
    assert len(reg.all_rule_applieds) == 11
    # 3 sections mapped => 8 orphans.
    assert len(reg.orphan_rule_applieds) == 8


def test_t3_10_from_m2_sections_with_no_rule_match():
    sec = _make_section(
        section_id="WSP-NONEXIST-9.9",
        title="Unmapped",
        body="No anchor yet.",
    )
    reg = MappingRegistry.from_m2(AuthorityPolicy(), [sec])
    assert reg.by_wsp("WSP-NONEXIST-9.9") == ()
    assert reg.unmapped_section_ids() == ("WSP-NONEXIST-9.9",)


def test_t3_10_from_m2_rejects_non_policy():
    class Fake:
        def rule_table(self):
            return []

    with pytest.raises(TypeError):
        MappingRegistry.from_m2(Fake(), [])  # type: ignore[arg-type]


# =============================================================================
# T3.11 — by_wsp / by_rule round-trip
# =============================================================================


def test_t3_11_bidirectional_lookup(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)

    anchors = reg.by_wsp("WSP-TRD-3.1")
    assert len(anchors) == 1
    assert anchors[0].rule_applied == "authority/advisor/restricted_list.v1"

    sids = reg.by_rule("authority/advisor/restricted_list.v1")
    assert sids == ("WSP-TRD-3.1",)

    # Orphan rule returns empty tuple.
    assert reg.by_rule("authority/meta/excludes_check.v1") == ()


def test_t3_11_many_to_many_supported():
    # Two sections anchored by the same rule_applied.
    sections = [
        _make_section(section_id="WSP-TRD-3.1"),
        _make_section(section_id="WSP-TRD-3.2", title="t2", body="b2"),
    ]
    rules = [
        {
            "rule_applied": "authority/advisor/restricted_list.v1",
            "wsp_section": "WSP-TRD-3.1",
        },
        {
            "rule_applied": "authority/advisor/trading_window.v1",
            "wsp_section": "WSP-TRD-3.2",
        },
        # same rule_applied appears twice (dedup expected)
        {
            "rule_applied": "authority/advisor/restricted_list.v1",
            "wsp_section": "WSP-TRD-3.1",
        },
    ]
    reg = MappingRegistry.build(sections=sections, rules=rules)
    assert len(reg.all_rule_applieds) == 2  # dedup


# =============================================================================
# T3.12 — Golden manifest digest
# =============================================================================


# Pinned after first passing run. Any drift intentionally fails this test.
GOLDEN_MANIFEST_DIGEST: str = (
    "76aac9a36ea81d032f82d23310c583e0f4140e7517292128332a109769f9be9b"
)


def test_t3_12_manifest_byte_identical(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    m1 = generate_manifest(
        reg,
        generated_at=_FIXTURE_GENERATED_AT,
        last_updated_by=_FIXTURE_UPDATED_BY,
    )
    m2 = generate_manifest(
        reg,
        generated_at=_FIXTURE_GENERATED_AT,
        last_updated_by=_FIXTURE_UPDATED_BY,
    )
    assert m1 == m2
    assert sha256_digest(m1) == sha256_digest(m2)


def test_t3_12_golden_digest_matches(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    manifest = generate_manifest(
        reg,
        generated_at=_FIXTURE_GENERATED_AT,
        last_updated_by=_FIXTURE_UPDATED_BY,
    )
    digest = sha256_digest(manifest)
    assert digest == GOLDEN_MANIFEST_DIGEST, (
        "Canonical YAML drift — update GOLDEN_MANIFEST_DIGEST deliberately "
        f"to {digest!r} if this change is intentional."
    )


# =============================================================================
# T3.13 / T3.14 / T3.15 — generator error paths
# =============================================================================


def test_t3_13_empty_registry_rejected():
    reg = MappingRegistry.build(sections=[], rules=[])
    with pytest.raises(ValueError):
        generate_manifest(
            reg,
            generated_at=_FIXTURE_GENERATED_AT,
            last_updated_by=_FIXTURE_UPDATED_BY,
        )


def test_t3_14_naive_generated_at_rejected(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    with pytest.raises(ValueError):
        generate_manifest(
            reg,
            generated_at=datetime(2026, 4, 14, 12, 0, 0),
            last_updated_by=_FIXTURE_UPDATED_BY,
        )


@pytest.mark.parametrize(
    "bad",
    [
        "alice@example.com",
        "ssn 123-45-6789 sme",
        "acct 123456789012 sme",
    ],
)
def test_t3_15_pii_in_last_updated_by_rejected(three_sections, bad):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    with pytest.raises(ValueError):
        generate_manifest(
            reg,
            generated_at=_FIXTURE_GENERATED_AT,
            last_updated_by=bad,
        )


# =============================================================================
# T3.16 / T3.17 / T3.18 / T3.19 / T3.20 — CoverageReport
# =============================================================================


def test_t3_16_coverage_all_mapped():
    sections = [
        _make_section(section_id="WSP-TRD-3.1"),
        _make_section(section_id="WSP-TRD-3.2", title="t2", body="b2"),
    ]
    rules = [
        {
            "rule_applied": "authority/advisor/restricted_list.v1",
            "wsp_section": "WSP-TRD-3.1",
        },
        {
            "rule_applied": "authority/advisor/trading_window.v1",
            "wsp_section": "WSP-TRD-3.2",
        },
    ]
    reg = MappingRegistry.build(sections=sections, rules=rules)
    report = build_coverage_report(reg)
    assert report.exit_code == 0
    assert report.coverage_pct == 100.000
    assert report.unmapped_sections == ()
    assert report.orphan_rules == ()


def test_t3_17_coverage_unmapped_section_sorted():
    sections = [
        _make_section(section_id="WSP-TRD-3.1"),
        _make_section(section_id="WSP-ADV-1.1", title="t2", body="b2"),
    ]
    rules = [
        {
            "rule_applied": "authority/advisor/restricted_list.v1",
            "wsp_section": "WSP-TRD-3.1",
        },
    ]
    reg = MappingRegistry.build(sections=sections, rules=rules)
    report = build_coverage_report(reg)
    assert report.exit_code == 1
    assert report.unmapped_sections == ("WSP-ADV-1.1",)
    # Sorting is ASCII ascending.
    assert list(report.unmapped_sections) == sorted(report.unmapped_sections)


def test_t3_18_coverage_orphan_rules_sorted():
    sections = [_make_section(section_id="WSP-TRD-3.1")]
    rules = [
        {
            "rule_applied": "authority/advisor/restricted_list.v1",
            "wsp_section": "WSP-TRD-3.1",
        },
        {
            "rule_applied": "authority/advisor/trading_window.v1",
            "wsp_section": "WSP-UNKNOWN-9.9",
        },
        {
            "rule_applied": "authority/advisor/chinese_wall.v1",
            "wsp_section": "WSP-OTHER-9.9",
        },
    ]
    reg = MappingRegistry.build(sections=sections, rules=rules)
    report = build_coverage_report(reg)
    assert report.exit_code == 1
    assert report.orphan_rules == (
        "authority/advisor/chinese_wall.v1",
        "authority/advisor/trading_window.v1",
    )


def test_t3_19_coverage_strict_orphan_exit_2(three_sections):
    reg = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    # Non-strict: exit 1 (orphans exist for 8 unmapped rules).
    assert build_coverage_report(reg, strict=False).exit_code == 1
    # Strict: exit 2.
    assert build_coverage_report(reg, strict=True).exit_code == 2


def test_t3_20_coverage_empty_registry_exit_2():
    reg = MappingRegistry.build(sections=[], rules=[])
    report = build_coverage_report(reg)
    assert report.exit_code == 2
    assert report.coverage_pct == 0.000
    assert report.total_wsp_sections == 0


def test_t3_rounding_banker_matches_round(three_sections):
    # Build a scenario that produces a repeating decimal to verify
    # round(x, 3) is actually applied.
    sections = [
        _make_section(section_id=f"WSP-X-{i}.0", title=f"t{i}", body=f"b{i}")
        for i in range(3)  # 3 sections
    ]
    rule_names = ["alpha_rule", "beta_rule"]
    rules = [
        {
            "rule_applied": f"authority/advisor/{rule_names[i]}.v1",
            "wsp_section": f"WSP-X-{i}.0",
        }
        for i in range(2)  # 2 of 3 mapped
    ]
    reg = MappingRegistry.build(sections=sections, rules=rules)
    report = build_coverage_report(reg)
    # 2/3 * 100 = 66.66666... -> 66.667
    assert report.coverage_pct == 66.667


# =============================================================================
# T3.21 / T3.22 — Rego scanner
# =============================================================================


def test_t3_21_scan_rego_file_with_annotation(tmp_path):
    rego = textwrap.dedent(
        """
        # METADATA
        # title: Restricted list check
        # custom:
        #   wsp_section: "WSP-TRD-3.1"
        #   gap: 3
        package authority.restricted_list

        import rego.v1

        check_restricted_list := {"decision": "DENY"}
        """
    )
    f = tmp_path / "restricted_list.rego"
    f.write_text(rego, encoding="utf-8")
    anchor = scan_rego_file(f)
    assert anchor.package == "authority.restricted_list"
    assert anchor.wsp_sections == ("WSP-TRD-3.1",)


def test_t3_21_scan_rego_file_without_annotation(tmp_path):
    rego = textwrap.dedent(
        """
        package authority.foo

        default allow := false
        """
    )
    f = tmp_path / "foo.rego"
    f.write_text(rego, encoding="utf-8")
    anchor = scan_rego_file(f)
    assert anchor.wsp_sections == ()
    assert anchor.package == "authority.foo"


def test_t3_22_scan_rego_directory_sorted(tmp_path):
    (tmp_path / "b.rego").write_text(
        '# custom:\n#   wsp_section: "WSP-B-1.0"\npackage b\n',
        encoding="utf-8",
    )
    (tmp_path / "a.rego").write_text(
        '# custom:\n#   wsp_section: "WSP-A-1.0"\npackage a\n',
        encoding="utf-8",
    )
    # Nested dir.
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.rego").write_text(
        '# custom:\n#   wsp_section: "WSP-C-1.0"\npackage c\n',
        encoding="utf-8",
    )

    anchors = scan_rego_directory(tmp_path)
    # Deterministic ordering by path.
    assert [a.package for a in anchors] == ["a", "b", "c"]


# =============================================================================
# T3.23 / T3.24 / T3.25 / T3.26 — CLI
# =============================================================================


def _write_good_wsp(tmp_path: Path) -> Path:
    path = tmp_path / "wsp.yaml"
    path.write_text(_GOOD_YAML, encoding="utf-8")
    return path


def test_t3_23_cli_scan_and_report_happy(tmp_path, capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    wsp_path = _write_good_wsp(tmp_path)
    # 3 sections all map to M2 rules; 8 M2 rules orphan → exit 1.
    code = main(["scan-and-report", "--wsp-file", str(wsp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "total_wsp=3" in captured.out
    assert "mapped=3" in captured.out
    assert captured.err == ""


def test_t3_24_cli_unmapped_section_exit_1(tmp_path, capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    # Use a section that has no matching M2 rule.
    yaml_text = textwrap.dedent(
        """
        wsp_id: "WSP-X-1"
        sections:
          - section_id: "WSP-ZZZ-9.9"
            title: "Orphan procedure"
            body: "Has no Rego anchor."
            supervisory_role: "compliance_officer"
            frequency: "real_time"
            escalation_path: ["compliance_officer"]
        """
    )
    wsp_path = tmp_path / "wsp.yaml"
    wsp_path.write_text(yaml_text, encoding="utf-8")
    code = main(["scan-and-report", "--wsp-file", str(wsp_path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "unmapped=1" in out


def test_t3_25_cli_strict_orphan_exit_2(tmp_path, capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    wsp_path = _write_good_wsp(tmp_path)
    code = main(["scan-and-report", "--wsp-file", str(wsp_path), "--strict"])
    assert code == 2


def test_t3_26_cli_argument_parse_failure(capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    # Missing --wsp-file → argparse exit.
    code = main(["scan-and-report"])
    assert code == 5
    err = capsys.readouterr().err
    assert "gap3: argument_parse_failed" in err


def test_t3_26_cli_ingest_failure(tmp_path, capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    bad_path = tmp_path / "missing.yaml"
    code = main(["scan-and-report", "--wsp-file", str(bad_path)])
    assert code == 3
    err = capsys.readouterr().err
    assert "gap3: wsp_ingest_failed" in err


def test_t3_26_cli_write_manifest(tmp_path, capsys):
    from compliance.gap3_wsp_to_yaml.cli import main

    wsp_path = _write_good_wsp(tmp_path)
    out_path = tmp_path / "out.yaml"
    code = main(
        [
            "scan-and-report",
            "--wsp-file",
            str(wsp_path),
            "--output",
            str(out_path),
        ]
    )
    assert code == 1  # orphans remain
    assert out_path.exists()
    content = out_path.read_text()
    assert "schema_version: 1.0.0" in content
    assert "WSP-TRD-3.1" in content


# =============================================================================
# T3.27 — AST import scan (module boundary)
# =============================================================================


def test_t3_27_imports_restricted_to_allowed_modules():
    allowed_prefixes = {
        "compliance.gap3_wsp_to_yaml",
        "m2_m4_policy_engine",
        "pydantic",
        "yaml",
        # stdlib roots used in this package
        "__future__",
        "argparse",
        "datetime",
        "enum",
        "hashlib",
        "io",
        "json",
        "pathlib",
        "re",
        "sys",
        "types",
        "typing",
    }
    import compliance.gap3_wsp_to_yaml as pkg

    pkg_path = Path(pkg.__file__).parent
    violations: list[tuple[str, str]] = []
    for py_file in pkg_path.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name not in allowed_prefixes and not any(
                        alias.name.startswith(p) for p in allowed_prefixes
                    ):
                        violations.append((py_file.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top = mod.split(".")[0]
                if top not in allowed_prefixes and not any(
                    mod.startswith(p) for p in allowed_prefixes
                ):
                    violations.append((py_file.name, mod))
    assert not violations, f"forbidden imports found: {violations}"


# =============================================================================
# T3.28 — extra='forbid' on every model
# =============================================================================


def test_t3_28_forbid_extra_wsp_section():
    with pytest.raises(ValidationError):
        WspSection(
            wsp_id="WSP-X-1",
            section_id="WSP-TRD-3.1",
            title="t",
            body="b",
            supervisory_role=SupervisoryRole.compliance_officer,
            frequency=SupervisoryFrequency.real_time,
            escalation_path=("compliance_officer",),
            unknown_field="x",  # type: ignore[call-arg]
        )


def test_t3_28_forbid_extra_rule_anchor():
    with pytest.raises(ValidationError):
        RuleAnchor(
            rule_applied="authority/advisor/restricted_list.v1",
            opa_bundle="authority",
            rego_file="authority/restricted_list.rego",
            rego_rule="restricted_list",
            unknown="x",  # type: ignore[call-arg]
        )


def test_t3_28_forbid_extra_wsp_mapping():
    with pytest.raises(ValidationError):
        WspMapping(
            wsp_section=_make_section(),
            rules=(),
            unknown="x",  # type: ignore[call-arg]
        )


def test_t3_28_forbid_extra_coverage_report():
    with pytest.raises(ValidationError):
        CoverageReport(
            total_wsp_sections=0,
            total_rules=0,
            mapped_sections=0,
            coverage_pct=0.0,
            orphan_pct=0.0,
            exit_code=2,
            unknown="x",  # type: ignore[call-arg]
        )


# =============================================================================
# T3.29 — schema_version mutation-proof
# =============================================================================


def test_t3_29_schema_version_mutation_rejected():
    with pytest.raises(ValidationError):
        WspSection(
            wsp_id="WSP-X-1",
            section_id="WSP-TRD-3.1",
            title="t",
            body="b",
            supervisory_role=SupervisoryRole.compliance_officer,
            frequency=SupervisoryFrequency.real_time,
            escalation_path=("compliance_officer",),
            schema_version="2.0.0",
        )


# =============================================================================
# T3.30 — Determinism property
# =============================================================================


def test_t3_30_registry_repr_stable(three_sections):
    r1 = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    r2 = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    assert repr(r1) == repr(r2)


def test_t3_30_mapping_order_stable_under_input_shuffle(three_sections):
    shuffled = list(reversed(three_sections))
    r1 = MappingRegistry.from_m2(AuthorityPolicy(), three_sections)
    r2 = MappingRegistry.from_m2(AuthorityPolicy(), shuffled)
    # Mappings are sorted by section_id, so output order is stable
    # regardless of input order.
    assert [m.wsp_section.section_id for m in r1.mappings] == [
        m.wsp_section.section_id for m in r2.mappings
    ]


# =============================================================================
# Exports sanity — Gap 3 public API (supports the compliance.__init__
# expectation that Gap 3 exports are importable at gap level).
# =============================================================================


def test_public_api_exports():
    import compliance.gap3_wsp_to_yaml as g3

    for name in [
        "WspSection",
        "SupervisoryRole",
        "SupervisoryFrequency",
        "RuleAnchor",
        "WspMapping",
        "CoverageReport",
        "MappingRegistry",
        "FileReader",
        "LocalFileReader",
        "InMemoryFileReader",
        "WspIngestError",
        "ingest_wsp_yaml",
        "generate_manifest",
        "sha256_digest",
        "build_coverage_report",
        "scan_rego_file",
        "scan_rego_directory",
        "RegoRuleAnchor",
        "WSP_SECTION_RE",
        "SECTION_SCHEMA_VERSION",
    ]:
        assert hasattr(g3, name), f"missing export: {name}"


def test_section_schema_version_constant():
    assert SECTION_SCHEMA_VERSION == "1.0.0"
