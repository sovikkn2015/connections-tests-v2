"""
Gap 2 — Liability Provenance — Unit Tests.

Covers spec .kiro/specs/gap2-liability-provenance.md tasks T2.1..T2.26.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest \\
        my-agent-project-007-fsi-interoperability/tests/unit/test_gap2_liability_provenance.py -v

GOLDEN_HEX_DIGEST bootstrap:
    First run - test T2.17a prints the computed hex.
    Paste that hex into GOLDEN_HEX_DIGEST below, then tests will pass
    on subsequent runs. Any future change to canonical JSON output
    breaks T2.17b - that's the intent (drift detection).
"""

from __future__ import annotations

import ast
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from m3_schema_registry import ProvenanceStage

from compliance.gap2_liability_provenance import (
    ErrorAttribution,
    ErrorCategory,
    LiabilityReport,
    LiabilitySummary,
    REPORT_SCHEMA_VERSION,
    StageClassification,
    WarrantyBoundary,
    WarrantyCategory,
    WarrantyClassification,
    WarrantyReason,
)


# =============================================================================
# Constants + fixtures
# =============================================================================

UTC = timezone.utc


def _ts(year=2026, month=4, day=14, hour=12, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _stage(stage_name, module, hash_char="0", minute=0):
    return ProvenanceStage(
        stage=stage_name,
        module=module,
        hash=hash_char * 64,
        timestamp=_ts(hour=11, minute=minute, second=0),
    )


# Golden hex pinned after running T2.17a once. See module docstring.
GOLDEN_HEX_DIGEST = (
    "6c2b88193787f4b6f13e6493919f31cdb20af92f5370de85d4472650a7e31af0"
)


# =============================================================================
# T2.1 — WarrantyCategory + ordered_rank
# =============================================================================


def test_T2_1_warranty_category_ordered_rank_ordering():
    assert WarrantyCategory.warranted.ordered_rank() == 0
    assert WarrantyCategory.best_effort.ordered_rank() == 1
    assert WarrantyCategory.unknown.ordered_rank() == 2
    assert (
        WarrantyCategory.warranted.ordered_rank()
        < WarrantyCategory.best_effort.ordered_rank()
        < WarrantyCategory.unknown.ordered_rank()
    )


def test_T2_1_warranty_category_has_three_members():
    assert {c.value for c in WarrantyCategory} == {
        "warranted",
        "best_effort",
        "unknown",
    }


# =============================================================================
# T2.2 — WarrantyReason enum
# =============================================================================


def test_T2_2_warranty_reason_has_five_codes():
    assert {r.value for r in WarrantyReason} == {
        "deterministic_code_007",
        "deterministic_opa_007",
        "llm_007",
        "external_vendor",
        "unknown_module",
    }


# =============================================================================
# T2.3 — WarrantyClassification frozen + JSON-safe
# =============================================================================


def test_T2_3_warranty_classification_model_dump_json_safe():
    c = WarrantyClassification(
        module="m1",
        category=WarrantyCategory.warranted,
        reason=WarrantyReason.deterministic_code_007,
    )
    dumped = c.model_dump(mode="json")
    assert dumped == {
        "module": "m1",
        "category": "warranted",
        "reason": "deterministic_code_007",
    }


def test_T2_3_warranty_classification_frozen():
    c = WarrantyClassification(
        module="m1",
        category=WarrantyCategory.warranted,
        reason=WarrantyReason.deterministic_code_007,
    )
    with pytest.raises(ValidationError):
        c.module = "m2"  # type: ignore[misc]


# =============================================================================
# T2.4 — WarrantyBoundary.classify table golden
# =============================================================================


_EXPECTED_TABLE = {
    "m1": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m2": (WarrantyCategory.warranted, WarrantyReason.deterministic_opa_007),
    "m3": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m4": (WarrantyCategory.warranted, WarrantyReason.deterministic_opa_007),
    "m5": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m6": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m7": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m8": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
    "m9": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
    "m10": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
    "m11": (WarrantyCategory.best_effort, WarrantyReason.external_vendor),
    "m12": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
    "m13": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
}


@pytest.mark.parametrize("module,expected", list(_EXPECTED_TABLE.items()))
def test_T2_4_classify_golden_table(module, expected):
    boundary = WarrantyBoundary()
    c = boundary.classify(module)
    assert c.module == module
    assert c.category == expected[0]
    assert c.reason == expected[1]


def test_T2_4_classify_deterministic():
    import json

    boundary = WarrantyBoundary()
    a = boundary.classify("m1")
    b = boundary.classify("m1")
    assert a == b
    assert (
        json.dumps(a.model_dump(mode="json"), sort_keys=True)
        == json.dumps(b.model_dump(mode="json"), sort_keys=True)
    )


# =============================================================================
# T2.5 — classify unknown inputs
# =============================================================================


@pytest.mark.parametrize(
    "bad_module",
    ["M1", "m14", "", "m1 ", " m1", "m1.verify", "M13", "m0", "foo"],
)
def test_T2_5_classify_unknown_modules(bad_module):
    boundary = WarrantyBoundary()
    c = boundary.classify(bad_module)
    assert c.category == WarrantyCategory.unknown
    assert c.reason == WarrantyReason.unknown_module
    assert c.module == bad_module


# =============================================================================
# T2.6 — classify_all() immutable
# =============================================================================


def test_T2_6_classify_all_is_immutable_mapping():
    boundary = WarrantyBoundary()
    mapping = boundary.classify_all()
    with pytest.raises(TypeError):
        mapping["m1"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        del mapping["m1"]  # type: ignore[misc]


def test_T2_6_classify_all_contents():
    boundary = WarrantyBoundary()
    mapping = boundary.classify_all()
    assert set(mapping.keys()) == set(_EXPECTED_TABLE.keys())
    for mod, (cat, reason) in _EXPECTED_TABLE.items():
        assert mapping[mod].category == cat
        assert mapping[mod].reason == reason


# =============================================================================
# T2.7 — TABLE coupling with M10's m1..m13 namespace
# =============================================================================


def test_T2_7_warranty_table_coupling_with_m10_namespace():
    # Must match M10's _MODULE_PATTERN m1..m13. If M10 expands the
    # namespace, this test must be updated in the same PR.
    assert set(WarrantyBoundary.TABLE.keys()) == {
        "m1", "m2", "m3", "m4", "m5", "m6", "m7",
        "m8", "m9", "m10", "m11", "m12", "m13",
    }


# =============================================================================
# T2.8 — ErrorCategory 6 members
# =============================================================================


def test_T2_8_error_category_has_exactly_six_members():
    assert {c.value for c in ErrorCategory} == {
        "source_data_error",
        "schema_translation_error",
        "policy_evaluation_error",
        "llm_synthesis_error",
        "human_approval_error",
        "compliance_rule_error",
    }


# =============================================================================
# T2.9 — ErrorAttribution tz-aware validator
# =============================================================================


def test_T2_9_error_attribution_tz_aware_required():
    with pytest.raises(ValidationError):
        ErrorAttribution(
            category=ErrorCategory.source_data_error,
            stage="m1.verify",
            module="m1",
            reason="vendor down",
            occurred_at=datetime(2026, 4, 14, 12, 0, 0),  # naive
        )


def test_T2_9_error_attribution_tz_aware_accepted():
    att = ErrorAttribution(
        category=ErrorCategory.source_data_error,
        stage="m1.verify",
        module="m1",
        reason="vendor down",
        occurred_at=_ts(),
    )
    assert att.occurred_at.tzinfo is timezone.utc


# =============================================================================
# T2.10 — PII validation on reason (R2.4)
# =============================================================================


@pytest.mark.parametrize(
    "bad_reason,pattern_code",
    [
        ("client SSN 123-45-6789 failed", "ssn"),
        ("account 123456789012 mismatch", "account_number"),
        ("email bounce john.smith@example.com", "email"),
        ("IBAN GB29NWBK60161331926819 declined", "iban"),
    ],
)
def test_T2_10_error_attribution_reason_rejects_pii(bad_reason, pattern_code):
    with pytest.raises(ValidationError) as exc_info:
        ErrorAttribution(
            category=ErrorCategory.source_data_error,
            stage="m11.fetch",
            module="m11",
            reason=bad_reason,
            occurred_at=_ts(),
        )
    assert pattern_code in str(exc_info.value)


def test_T2_10_error_attribution_clean_reason_accepted():
    att = ErrorAttribution(
        category=ErrorCategory.source_data_error,
        stage="m11.fetch",
        module="m11",
        reason="vendor timeout after 5s",
        occurred_at=_ts(),
    )
    assert "vendor timeout" in att.reason


# =============================================================================
# T2.11 — attribute_from_chain
# =============================================================================


def test_T2_11_attribute_from_chain_happy():
    chain = [_stage("m1.verify", "m1"), _stage("m6.dispatch", "m6", minute=1)]
    att = ErrorAttribution.attribute_from_chain(
        chain=chain,
        failing_stage_name="m6.dispatch",
        category=ErrorCategory.policy_evaluation_error,
        reason="opa denied malformed request",
        occurred_at=_ts(),
    )
    assert att.stage == "m6.dispatch"
    assert att.module == "m6"


def test_T2_11_attribute_from_chain_empty_chain():
    with pytest.raises(ValueError, match="chain is empty"):
        ErrorAttribution.attribute_from_chain(
            chain=[],
            failing_stage_name="m1.verify",
            category=ErrorCategory.source_data_error,
            reason="x",
            occurred_at=_ts(),
        )


def test_T2_11_attribute_from_chain_not_found():
    chain = [_stage("m1.verify", "m1")]
    with pytest.raises(ValueError, match="not in chain"):
        ErrorAttribution.attribute_from_chain(
            chain=chain,
            failing_stage_name="m99.unknown",
            category=ErrorCategory.source_data_error,
            reason="x",
            occurred_at=_ts(),
        )


def test_T2_11_attribute_from_chain_duplicate():
    chain = [
        _stage("m1.verify", "m1"),
        _stage("m1.verify", "m1", minute=1),
    ]
    with pytest.raises(ValueError, match="appears more than once"):
        ErrorAttribution.attribute_from_chain(
            chain=chain,
            failing_stage_name="m1.verify",
            category=ErrorCategory.source_data_error,
            reason="x",
            occurred_at=_ts(),
        )


# =============================================================================
# T2.12 — StageClassification frozen
# =============================================================================


def test_T2_12_stage_classification_frozen():
    sc = StageClassification(
        stage=_stage("m1.verify", "m1"),
        classification=WarrantyClassification(
            module="m1",
            category=WarrantyCategory.warranted,
            reason=WarrantyReason.deterministic_code_007,
        ),
        is_failing=False,
    )
    with pytest.raises(ValidationError):
        sc.is_failing = True  # type: ignore[misc]


# =============================================================================
# T2.13 — LiabilitySummary counters
# =============================================================================


def test_T2_13_liability_summary_counters_mixed_chain():
    boundary = WarrantyBoundary()
    chain = [
        _stage("m1.verify", "m1"),
        _stage("m8.synth", "m8", minute=1),
        _stage("m14.ghost", "m14", minute=2),  # unknown module
    ]
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
        boundary=boundary,
    )
    assert report.summary.stage_count == 3
    assert report.summary.warranted_count == 1
    assert report.summary.best_effort_count == 1
    assert report.summary.unknown_count == 1
    assert report.summary.failing_stage is None


# =============================================================================
# T2.14 — LiabilityReport.build happy path (all warranted)
# =============================================================================


def test_T2_14_build_happy_all_warranted():
    chain = [_stage("m1.verify", "m1"), _stage("m6.dispatch", "m6", minute=1)]
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
    )
    assert report.overall_warranty is WarrantyCategory.warranted
    assert report.is_clean() is True
    assert report.error_attribution is None
    assert len(report.stage_classifications) == 2
    assert all(sc.is_failing is False for sc in report.stage_classifications)


# =============================================================================
# T2.15 — build invalid inputs
# =============================================================================


def test_T2_15_build_empty_trace_id():
    with pytest.raises(ValueError, match="trace_id"):
        LiabilityReport.build(
            trace_id="",
            chain=[_stage("m1.verify", "m1")],
            chain_verified=True,
            generated_at=_ts(),
        )


def test_T2_15_build_empty_chain():
    with pytest.raises(ValueError, match="chain"):
        LiabilityReport.build(
            trace_id="trace-1",
            chain=[],
            chain_verified=True,
            generated_at=_ts(),
        )


def test_T2_15_build_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        LiabilityReport.build(
            trace_id="trace-1",
            chain=[_stage("m1.verify", "m1")],
            chain_verified=True,
            generated_at=datetime(2026, 4, 14, 12, 0, 0),  # naive
        )


# =============================================================================
# T2.16 — build attribution.stage not in chain
# =============================================================================


def test_T2_16_build_attribution_unknown_stage():
    chain = [_stage("m1.verify", "m1")]
    err = ErrorAttribution(
        category=ErrorCategory.source_data_error,
        stage="m99.nonsense",
        module="m99",
        reason="x",
        occurred_at=_ts(),
    )
    with pytest.raises(ValueError, match="unknown stage"):
        LiabilityReport.build(
            trace_id="trace-1",
            chain=chain,
            chain_verified=True,
            generated_at=_ts(),
            error=err,
        )


# =============================================================================
# T2.17 — Golden hex determinism (R3.5)
# =============================================================================


def _golden_fixture_report():
    """Spec R3.5 fixture."""
    chain = [
        ProvenanceStage(
            stage="m1.verify",
            module="m1",
            hash="0" * 64,
            timestamp=datetime(2026, 4, 14, 11, 59, 0, tzinfo=UTC),
        ),
        ProvenanceStage(
            stage="m6.dispatch",
            module="m6",
            hash="1" * 64,
            timestamp=datetime(2026, 4, 14, 11, 59, 30, tzinfo=UTC),
        ),
    ]
    return LiabilityReport.build(
        trace_id="trace-fixed-001",
        chain=chain,
        chain_verified=True,
        generated_at=datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC),
    )


def test_T2_17a_byte_identical_two_builds():
    a = _golden_fixture_report()
    b = _golden_fixture_report()
    assert a.to_canonical_json() == b.to_canonical_json()
    assert a.sha256_digest() == b.sha256_digest()


def test_T2_17b_golden_hex_pinned():
    r = _golden_fixture_report()
    hex_now = r.sha256_digest()
    independent = hashlib.sha256(
        r.to_canonical_json().encode("utf-8")
    ).hexdigest()
    assert hex_now == independent, "sha256_digest != independent recompute"
    assert (
        hex_now == GOLDEN_HEX_DIGEST
    ), f"GOLDEN_HEX_DIGEST drift: got {hex_now!r}"


def test_T2_17c_schema_version_in_json():
    r = _golden_fixture_report()
    assert REPORT_SCHEMA_VERSION in r.to_canonical_json()


# =============================================================================
# T2.18 — chain_verified=False + no error -> unknown
# =============================================================================


def test_T2_18_chain_verified_false_no_error_is_unknown():
    chain = [_stage("m1.verify", "m1")]
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=False,
        generated_at=_ts(),
    )
    assert report.is_clean() is False
    assert report.overall_warranty is WarrantyCategory.unknown


# =============================================================================
# T2.19 — warranted chain + error -> best_effort
# =============================================================================


def test_T2_19_warranted_chain_with_error_is_best_effort():
    chain = [_stage("m1.verify", "m1"), _stage("m6.dispatch", "m6", minute=1)]
    err = ErrorAttribution(
        category=ErrorCategory.source_data_error,
        stage="m1.verify",
        module="m1",
        reason="vendor returned stale data",
        occurred_at=_ts(),
    )
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
        error=err,
    )
    assert report.overall_warranty is WarrantyCategory.best_effort
    assert report.is_clean() is False
    assert report.summary.failing_stage == "m1.verify"
    assert report.summary.failing_module == "m1"
    assert report.summary.failing_category is ErrorCategory.source_data_error


# =============================================================================
# T2.20 — Every ErrorCategory member exercised
# =============================================================================


@pytest.mark.parametrize("category", list(ErrorCategory))
def test_T2_20_every_error_category_exercised(category):
    chain = [_stage("m1.verify", "m1")]
    err = ErrorAttribution(
        category=category,
        stage="m1.verify",
        module="m1",
        reason="test coverage",
        occurred_at=_ts(),
    )
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
        error=err,
    )
    assert report.summary.failing_category is category


# =============================================================================
# T2.21 — all best_effort, no error -> best_effort + clean
# =============================================================================


def test_T2_21_all_best_effort_is_clean():
    chain = [
        _stage("m8.synth", "m8"),
        _stage("m11.fetch", "m11", minute=1),
    ]
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
    )
    assert report.overall_warranty is WarrantyCategory.best_effort
    assert report.is_clean() is True  # best_effort IS clean per R3.6


# =============================================================================
# T2.22 — report_schema_version mutation-proof (Literal)
# =============================================================================


def test_T2_22_schema_version_pinned_literal():
    chain = [_stage("m1.verify", "m1")]
    with pytest.raises(ValidationError):
        LiabilityReport(
            report_schema_version="2.0.0",  # type: ignore[arg-type]
            trace_id="trace-1",
            generated_at=_ts(),
            chain=tuple(chain),
            chain_verified=True,
            stage_classifications=(),
            overall_warranty=WarrantyCategory.warranted,
            summary=LiabilitySummary(
                stage_count=0,
                warranted_count=0,
                best_effort_count=0,
                unknown_count=0,
            ),
        )


# =============================================================================
# T2.23 — is_failing invariant
# =============================================================================


def test_T2_23_is_failing_invariant_with_error():
    chain = [
        _stage("m1.verify", "m1"),
        _stage("m6.dispatch", "m6", minute=1),
        _stage("m10.log", "m10", minute=2),
    ]
    err = ErrorAttribution(
        category=ErrorCategory.source_data_error,
        stage="m6.dispatch",
        module="m6",
        reason="x",
        occurred_at=_ts(),
    )
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
        error=err,
    )
    failing = [sc for sc in report.stage_classifications if sc.is_failing]
    assert len(failing) == 1
    assert failing[0].stage.stage == "m6.dispatch"


def test_T2_23_is_failing_invariant_no_error():
    chain = [_stage("m1.verify", "m1"), _stage("m6.dispatch", "m6", minute=1)]
    report = LiabilityReport.build(
        trace_id="trace-1",
        chain=chain,
        chain_verified=True,
        generated_at=_ts(),
    )
    assert all(sc.is_failing is False for sc in report.stage_classifications)


# =============================================================================
# T2.24 — Public API exports
# =============================================================================


def test_T2_24_public_api_exports():
    import compliance.gap2_liability_provenance as g2

    for name in [
        "WarrantyCategory", "WarrantyReason", "WarrantyClassification",
        "WarrantyBoundary", "ErrorCategory", "ErrorAttribution",
        "LiabilityReport", "LiabilitySummary", "StageClassification",
        "REPORT_SCHEMA_VERSION",
    ]:
        assert hasattr(g2, name), f"missing public export: {name}"


# =============================================================================
# T2.25 — AST import scan (forbidden imports)
# =============================================================================


_FORBIDDEN_IMPORTS = {
    "openai", "anthropic", "langchain", "langfuse",
    "boto3", "requests", "httpx", "spacy", "transformers",
    # all m*_ except m3_schema_registry:
    "m1_identity", "m2_m4_policy_engine", "m5_config_loader",
    "m6_mcp_gateway", "m7_translators", "m8_pipeline_engine",
    "m9_intent_router", "m10_audit_logger", "m11_adapters",
    "m12_runtime", "m13_fix_bridge",
}


def _gap2_src_files():
    root = (
        Path(__file__).parents[2]
        / "src"
        / "compliance"
        / "gap2_liability_provenance"
    )
    return sorted(root.glob("*.py"))


def test_T2_25_no_forbidden_imports_in_gap2_source():
    violations: list[tuple[str, str]] = []
    for path in _gap2_src_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _FORBIDDEN_IMPORTS:
                        violations.append((str(path), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in _FORBIDDEN_IMPORTS:
                        violations.append((str(path), node.module))
    assert not violations, f"forbidden imports: {violations}"


# =============================================================================
# T2.26 — extra="forbid" on every model
# =============================================================================


@pytest.mark.parametrize(
    "model_cls,required_kwargs",
    [
        (
            WarrantyClassification,
            dict(
                module="m1",
                category=WarrantyCategory.warranted,
                reason=WarrantyReason.deterministic_code_007,
            ),
        ),
        (
            ErrorAttribution,
            dict(
                category=ErrorCategory.source_data_error,
                stage="m1",
                module="m1",
                reason="clean",
                occurred_at=_ts(),
            ),
        ),
        (
            LiabilitySummary,
            dict(
                stage_count=0,
                warranted_count=0,
                best_effort_count=0,
                unknown_count=0,
            ),
        ),
    ],
)
def test_T2_26_extra_forbid_rejects_unknown_kwargs(model_cls, required_kwargs):
    with pytest.raises(ValidationError):
        model_cls(**required_kwargs, unknown_field="x")  # type: ignore
