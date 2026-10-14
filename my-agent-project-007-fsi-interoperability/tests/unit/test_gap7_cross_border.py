"""
Gap 7 — Cross-Border Regulatory Enforcement — Unit Tests.

Covers spec .kiro/specs/gap7-cross-border.md tasks T7.1..T7.12 and
acceptance criteria AC7.1..AC7.12.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
      python3 -m pytest \\
      my-agent-project-007-fsi-interoperability/tests/unit/test_gap7_cross_border.py -v
"""

from __future__ import annotations

import ast
import itertools
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from m5_config_loader import Jurisdiction

from compliance.gap7_cross_border import (
    ALLOWED_WSP_SECTIONS,
    COMPLEX_PRODUCTS,
    EGRESS_DECISION_SCHEMA_VERSION,
    EU_PII_FIELDS,
    HK_SFC_MNPI_FIELDS,
    JURISDICTION_MATRIX,
    MAS_RESTRICTED_RETAIL_PRODUCTS,
    AuditClient,
    AuditWriteFailed,
    EgressDecision,
    EgressGate,
    EgressRequest,
    GDPRLawfulBasis,
    InMemoryAuditClient,
    MiFIDClientClassification,
    RegoManifestError,
    UndefinedJurisdictionPair,
    evaluate_hkma_sfc,
    evaluate_mas_notice_626,
    gdpr_evaluate,
    load_manifest,
    matrix_lookup,
    mifid2_evaluate,
    scan_cross_border_mnpi,
)

# =============================================================================
# Helpers
# =============================================================================

_TRACE = "trace-7-00001"
_REQ = "advisor-777"


def _r(**overrides) -> EgressRequest:
    base = dict(
        trace_id=_TRACE,
        primary_jurisdiction=Jurisdiction.us,
        data_residency=Jurisdiction.us,
        target_vendor_jurisdiction=Jurisdiction.us,
        requested_by=_REQ,
    )
    base.update(overrides)
    return EgressRequest(**base)


@pytest.fixture
def audit_client() -> InMemoryAuditClient:
    return InMemoryAuditClient()


@pytest.fixture
def gate(audit_client: InMemoryAuditClient) -> EgressGate:
    return EgressGate(audit_client=audit_client)


# =============================================================================
# R1 — Jurisdiction matrix (AC7.1, AC7.2)
# =============================================================================


class TestJurisdictionMatrix:
    def test_matrix_has_25_cells(self):
        assert len(JURISDICTION_MATRIX) == 25

    @pytest.mark.parametrize(
        "primary,residency",
        list(itertools.product(list(Jurisdiction), list(Jurisdiction))),
    )
    def test_every_pair_resolvable(self, primary, residency):
        # AC7.1 — every ordered pair has a defined cell
        cell = matrix_lookup(primary, residency)
        assert cell.baseline in {"ALLOW", "REQUIRE_SCC", "DENY"}

    def test_same_jurisdiction_is_allow(self):
        for jx in Jurisdiction:
            cell = matrix_lookup(jx, jx)
            assert cell.baseline == "ALLOW", (
                f"{jx.value} same-jurisdiction must be ALLOW"
            )

    def test_eu_to_sg_is_deny(self):
        cell = matrix_lookup(Jurisdiction.eu, Jurisdiction.sg)
        assert cell.baseline == "DENY"

    def test_eu_to_hk_is_deny(self):
        cell = matrix_lookup(Jurisdiction.eu, Jurisdiction.hk)
        assert cell.baseline == "DENY"

    def test_hk_to_eu_is_deny(self):
        cell = matrix_lookup(Jurisdiction.hk, Jurisdiction.eu)
        assert cell.baseline == "DENY"

    def test_us_to_eu_requires_scc(self):
        cell = matrix_lookup(Jurisdiction.us, Jurisdiction.eu)
        assert cell.baseline == "REQUIRE_SCC"

    def test_undefined_pair_raises(self):
        # AC7.2 — Remove a key from a local copy to simulate drift;
        # we can't mutate the frozen dict, so we use a fake enum-like.
        class FakeJx:
            value = "zz"

        with pytest.raises(UndefinedJurisdictionPair):
            matrix_lookup(FakeJx(), Jurisdiction.us)  # type: ignore[arg-type]


# =============================================================================
# R2 — GDPR lawful-basis truth table (AC7.3)
# =============================================================================


class TestGdprTruthTable:
    def test_consent_missing(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.consent,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "REQUIRE_CONSENT"

    def test_consent_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.consent,
            involves_eu_data_subject=True,
            consent_on_file=True,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"

    def test_contract_eu_no_scc(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.contract,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "REQUIRE_SCC"

    def test_contract_eu_scc_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.contract,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=True,
        )
        assert r.outcome == "ALLOW"

    def test_contract_non_eu(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.contract,
            involves_eu_data_subject=False,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"

    def test_legal_obligation_always_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.legal_obligation,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"

    def test_vital_interests_always_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.vital_interests,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"

    def test_public_task_always_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.public_task,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"

    def test_legitimate_interests_eu_no_scc(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.legitimate_interests,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "REQUIRE_SCC"

    def test_legitimate_interests_eu_scc_ok(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.legitimate_interests,
            involves_eu_data_subject=True,
            consent_on_file=False,
            scc_on_file=True,
        )
        assert r.outcome == "ALLOW"

    def test_legitimate_interests_non_eu(self):
        r = gdpr_evaluate(
            basis=GDPRLawfulBasis.legitimate_interests,
            involves_eu_data_subject=False,
            consent_on_file=False,
            scc_on_file=False,
        )
        assert r.outcome == "ALLOW"


# =============================================================================
# R3 — MiFID II (AC7.4)
# =============================================================================


class TestMifidII:
    def test_retail_complex_no_assessment_denies(self):
        r = mifid2_evaluate(
            classification=MiFIDClientClassification.retail,
            product_type="derivatives",
            knowledge_experience_assessed=False,
        )
        assert r.outcome == "DENY"
        assert r.wsp_section == "MiFID II Art. 25(2)"

    def test_retail_no_assessment_simple_product_denies(self):
        r = mifid2_evaluate(
            classification=MiFIDClientClassification.retail,
            product_type="generic",
            knowledge_experience_assessed=False,
        )
        assert r.outcome == "DENY"
        assert r.wsp_section == "MiFID II Art. 25(3)"

    def test_retail_with_assessment_ok(self):
        r = mifid2_evaluate(
            classification=MiFIDClientClassification.retail,
            product_type="generic",
            knowledge_experience_assessed=True,
        )
        assert r.outcome == "ALLOW"

    def test_professional_always_ok(self):
        r = mifid2_evaluate(
            classification=MiFIDClientClassification.professional,
            product_type="derivatives",
            knowledge_experience_assessed=False,
        )
        assert r.outcome == "ALLOW"

    def test_eligible_counterparty_ok(self):
        r = mifid2_evaluate(
            classification=MiFIDClientClassification.eligible_counterparty,
            product_type="derivatives",
            knowledge_experience_assessed=False,
        )
        assert r.outcome == "ALLOW"


# =============================================================================
# R4 — MAS + HKMA (AC7.5)
# =============================================================================


class TestMasHkma:
    def test_mas_retail_crypto_denies(self):
        r = evaluate_mas_notice_626(
            classification=MiFIDClientClassification.retail,
            marketing_channel="retail_mass",
            product_type="crypto",
        )
        assert r.outcome == "DENY"

    def test_mas_retail_leveraged_fx_denies(self):
        r = evaluate_mas_notice_626(
            classification=MiFIDClientClassification.retail,
            marketing_channel="direct_solicitation",
            product_type="leveraged_fx",
        )
        assert r.outcome == "DENY"

    def test_mas_no_channel_is_allow(self):
        r = evaluate_mas_notice_626(
            classification=MiFIDClientClassification.retail,
            marketing_channel="none",
            product_type="crypto",
        )
        assert r.outcome == "ALLOW"

    def test_mas_professional_allowed(self):
        r = evaluate_mas_notice_626(
            classification=MiFIDClientClassification.professional,
            marketing_channel="direct_solicitation",
            product_type="crypto",
        )
        assert r.outcome == "ALLOW"

    def test_hkma_complex_no_kyc_denies(self):
        r = evaluate_hkma_sfc(
            classification=MiFIDClientClassification.retail,
            product_type="derivatives",
            kyc_on_file=False,
        )
        assert r.outcome == "DENY"

    def test_hkma_complex_with_kyc_ok(self):
        r = evaluate_hkma_sfc(
            classification=MiFIDClientClassification.retail,
            product_type="derivatives",
            kyc_on_file=True,
        )
        assert r.outcome == "ALLOW"

    def test_hkma_professional_ok(self):
        r = evaluate_hkma_sfc(
            classification=MiFIDClientClassification.professional,
            product_type="derivatives",
            kyc_on_file=False,
        )
        assert r.outcome == "ALLOW"


# =============================================================================
# R5 — Cross-border MNPI (AC7.6)
# =============================================================================


class TestCrossBorderMnpi:
    def test_eu_to_us_with_national_id_denies(self):
        r = scan_cross_border_mnpi(
            payload_fields=("national_id", "name"),
            src_jx=Jurisdiction.eu,
            dst_jx=Jurisdiction.us,
        )
        assert r.outcome == "DENY"
        assert "national_id" in r.matched_fields

    def test_hk_to_us_with_sfc_order_denies(self):
        r = scan_cross_border_mnpi(
            payload_fields=("sfc_order_id",),
            src_jx=Jurisdiction.hk,
            dst_jx=Jurisdiction.us,
        )
        assert r.outcome == "DENY"
        assert r.wsp_section == "SFC Part XIVA"

    def test_same_jurisdiction_ok(self):
        r = scan_cross_border_mnpi(
            payload_fields=("national_id", "sfc_order_id"),
            src_jx=Jurisdiction.eu,
            dst_jx=Jurisdiction.eu,
        )
        assert r.outcome == "ALLOW"

    def test_no_restricted_fields_ok(self):
        r = scan_cross_border_mnpi(
            payload_fields=("name", "account_id"),
            src_jx=Jurisdiction.eu,
            dst_jx=Jurisdiction.us,
        )
        assert r.outcome == "ALLOW"


# =============================================================================
# R6 — Egress gate end-to-end
# =============================================================================


class TestEgressGate:
    def test_us_to_us_allow(
        self, gate: EgressGate, audit_client: InMemoryAuditClient
    ):
        d = gate.evaluate(_r())
        assert d.outcome == "ALLOW"
        assert d.layered_outcome == "ALLOW"
        # Audited (AC7.8)
        assert len(audit_client.records) == 1
        assert audit_client.records[0]["gap"] == "gap7"

    def test_us_to_eu_requires_scc(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.eu,
            )
        )
        # matrix baseline is REQUIRE_SCC; caller didn't set EU subject/basis,
        # so layered remains REQUIRE_SCC from the matrix, outcome=ALLOW.
        assert d.outcome == "ALLOW"
        assert d.layered_outcome == "REQUIRE_SCC"

    def test_eu_to_sg_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.sg,
                target_vendor_jurisdiction=Jurisdiction.sg,
            )
        )
        assert d.outcome == "DENY"
        assert d.rule_ids == ("gap7.matrix.baseline_deny",)

    def test_eu_subject_no_basis_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.eu,
                involves_eu_data_subject=True,
                lawful_basis=None,
            )
        )
        assert d.outcome == "DENY"
        assert "gap7.gdpr.basis_missing" in d.rule_ids

    def test_consent_missing_yields_require_consent(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.eu,
                involves_eu_data_subject=True,
                lawful_basis=GDPRLawfulBasis.consent,
                consent_on_file=False,
            )
        )
        assert d.outcome == "ALLOW"
        assert d.layered_outcome == "REQUIRE_CONSENT"

    def test_retail_no_assessment_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.eu,
                lawful_basis=GDPRLawfulBasis.contract,
                scc_on_file=True,
                client_classification=MiFIDClientClassification.retail,
                product_type="derivatives",
                knowledge_experience_assessed=False,
            )
        )
        assert d.outcome == "DENY"
        assert any("mifid2" in rid for rid in d.rule_ids)

    def test_sg_retail_crypto_marketing_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.sg,
                data_residency=Jurisdiction.sg,
                target_vendor_jurisdiction=Jurisdiction.sg,
                client_classification=MiFIDClientClassification.retail,
                marketing_channel="retail_mass",
                product_type="crypto",
            )
        )
        assert d.outcome == "DENY"
        assert any("gap7.mas" in rid for rid in d.rule_ids)

    def test_hk_retail_complex_no_kyc_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.hk,
                data_residency=Jurisdiction.hk,
                target_vendor_jurisdiction=Jurisdiction.hk,
                client_classification=MiFIDClientClassification.retail,
                product_type="derivatives",
                kyc_on_file=False,
            )
        )
        assert d.outcome == "DENY"
        assert any("gap7.hkma" in rid for rid in d.rule_ids)

    def test_eu_pii_cross_border_denies(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.us,
                payload_fields=("national_id",),
                lawful_basis=GDPRLawfulBasis.contract,
                scc_on_file=True,
            )
        )
        assert d.outcome == "DENY"
        assert any("gap7.mnpi.eu_pii_egress" == rid for rid in d.rule_ids)

    def test_rationale_charset(self, gate: EgressGate):
        d = gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.us,
                payload_fields=("national_id",),
                lawful_basis=GDPRLawfulBasis.contract,
                scc_on_file=True,
            )
        )
        assert re.match(r"^[A-Za-z0-9 _\-\.\(\)/§,:=]+$", d.rationale)

    def test_audit_write_failure_raises(self):
        class _Boom:
            def write(self, payload):
                raise RuntimeError("sink down")

        g = EgressGate(audit_client=_Boom())
        with pytest.raises(AuditWriteFailed) as excinfo:
            g.evaluate(_r())
        assert str(excinfo.value) == "audit_write_failed"

    def test_undefined_pair_caught_as_deny(
        self, gate: EgressGate, audit_client: InMemoryAuditClient, monkeypatch
    ):
        # Force matrix_lookup to raise UndefinedJurisdictionPair by
        # patching it in the egress_gate module's namespace.
        import compliance.gap7_cross_border.egress_gate as eg_mod

        def _raise(*_args, **_kwargs):
            raise UndefinedJurisdictionPair("forced")

        monkeypatch.setattr(eg_mod, "matrix_lookup", _raise)

        d = gate.evaluate(_r())
        assert d.outcome == "DENY"
        assert d.rule_ids == ("gap7.matrix.undefined_pair",)
        # Audit still emitted even on the fail-closed path
        assert any(
            r["decision"]["rule_ids"] == ["gap7.matrix.undefined_pair"]
            for r in audit_client.records
        )


# =============================================================================
# AC7.7 — Rego wsp_section coverage
# =============================================================================


class TestRegoAnnotations:
    def test_manifest_loads_clean(self):
        bundle_root = (
            Path(__file__).resolve().parents[2]
            / "opa-bundles"
            / "jurisdiction"
        )
        manifest = load_manifest(bundle_root)
        assert manifest["bundle"] == "jurisdiction"
        assert manifest["gap"] == 7
        # At least one rule per jurisdiction
        assert len(manifest["rules"]) >= 10

    def test_all_rego_files_have_wsp(self):
        # AC7.7
        bundle_root = (
            Path(__file__).resolve().parents[2]
            / "opa-bundles"
            / "jurisdiction"
        )
        rego_files = list(bundle_root.rglob("*.rego"))
        assert len(rego_files) >= 5
        for rego in rego_files:
            text = rego.read_text(encoding="utf-8")
            assert "wsp_section:" in text, (
                f"{rego.relative_to(bundle_root)} missing wsp_section"
            )

    def test_manifest_rejects_unknown_wsp(self, tmp_path: Path):
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "bad.rego").write_text(
            '# wsp_section: "Not In Vocab"\npackage x\nrule_a := true\n'
        )
        (bundle / "manifest.json").write_text(
            json.dumps(
                {
                    "bundle": "x",
                    "rules": [
                        {
                            "file": "bad.rego",
                            "wsp_section": "Not In Vocab",
                        }
                    ],
                }
            )
        )
        with pytest.raises(RegoManifestError):
            load_manifest(bundle)


# =============================================================================
# AC7.9 — audit fail-closed covered above, double-check
# =============================================================================


class TestAuditEmission:
    def test_allow_emits_full_envelope(
        self, gate: EgressGate, audit_client: InMemoryAuditClient
    ):
        gate.evaluate(_r())
        rec = audit_client.records[0]
        assert rec["schema_version"] == EGRESS_DECISION_SCHEMA_VERSION
        assert rec["primary_jurisdiction"] == "us"
        assert rec["data_residency"] == "us"
        assert rec["target_vendor_jurisdiction"] == "us"

    def test_deny_emits_full_envelope(
        self, gate: EgressGate, audit_client: InMemoryAuditClient
    ):
        gate.evaluate(
            _r(
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.sg,
                target_vendor_jurisdiction=Jurisdiction.sg,
            )
        )
        rec = audit_client.records[0]
        assert rec["decision"]["outcome"] == "DENY"


# =============================================================================
# AC7.10 — No LLM SDK imports
# =============================================================================


class TestNoLlmImports:
    def test_no_llm_sdk(self):
        forbidden = {
            "anthropic",
            "openai",
            "bedrock",
            "boto3",
            "langchain",
            "transformers",
            "spacy",
        }
        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "compliance"
            / "gap7_cross_border"
        )
        for py in src.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        assert top not in forbidden, (
                            f"{py} imports forbidden LLM SDK {top}"
                        )
                if isinstance(node, ast.ImportFrom):
                    if node.module is not None:
                        top = node.module.split(".")[0]
                        assert top not in forbidden, (
                            f"{py} imports from forbidden LLM SDK {top}"
                        )


# =============================================================================
# AC7.11 — No credential literals
# =============================================================================


class TestNoCredentials:
    def test_no_secret_patterns(self):
        patterns = [
            re.compile(r"AKIA[A-Z0-9]{16}"),
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"),
            re.compile(r"-----BEGIN"),
            re.compile(r"ghp_[A-Za-z0-9]{36,}"),
        ]
        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "compliance"
            / "gap7_cross_border"
        )
        for py in src.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for pat in patterns:
                assert not pat.search(text), (
                    f"{py} contains credential-shaped literal"
                )


# =============================================================================
# AC7.12 — Module boundary
# =============================================================================


class TestModuleBoundary:
    def test_only_m5_cross_module_import(self):
        allowed_top = {
            "m5_config_loader",
            "compliance",
            "pydantic",
        }
        stdlib_top = {
            "re",
            "json",
            "pathlib",
            "dataclasses",
            "enum",
            "typing",
            "__future__",
        }
        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "compliance"
            / "gap7_cross_border"
        )
        for py in src.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    top = node.module.split(".")[0]
                    if top in allowed_top or top in stdlib_top:
                        continue
                    assert False, (
                        f"{py} imports disallowed cross-module "
                        f"'{node.module}'"
                    )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in allowed_top or top in stdlib_top:
                            continue
                        assert False, (
                            f"{py} imports disallowed module '{alias.name}'"
                        )


# =============================================================================
# Request validation
# =============================================================================


class TestRequestValidation:
    def test_invalid_trace_id(self):
        with pytest.raises(ValidationError):
            _r(trace_id="has spaces")

    def test_invalid_product_type_char(self):
        with pytest.raises(ValidationError):
            _r(product_type="derivatives & swaps")

    def test_allowed_wsp_vocabulary(self):
        # Spot-check that each wsp_section emitted by the Python engine
        # is in the allowed vocabulary (R7.2).
        expected = {
            "GDPR Art. 6(1)(a)",
            "GDPR Art. 6(1)(b)",
            "GDPR Art. 6(1)(f)",
            "GDPR Art. 46",
            "MiFID II Art. 25(2)",
            "MiFID II Art. 25(3)",
            "MAS Notice 626 §9",
            "SFC Code of Conduct §5.1A",
            "SFC Part XIVA",
            "Reg BI §15l-1",
        }
        assert expected.issubset(ALLOWED_WSP_SECTIONS)


# =============================================================================
# Protocol compliance
# =============================================================================


class TestProtocolCompliance:
    def test_inmemory_audit_client_is_audit_client(self):
        c = InMemoryAuditClient()
        assert isinstance(c, AuditClient)
