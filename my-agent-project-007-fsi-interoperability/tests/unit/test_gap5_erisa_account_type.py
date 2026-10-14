"""
Gap 5 — ERISA Account-Type Gating — Unit Tests.

Covers spec .kiro/specs/gap5-erisa-account-type.md tasks T5.1..T5.9
and acceptance criteria AC5.1..AC5.11.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
      python3 -m pytest \\
      my-agent-project-007-fsi-interoperability/tests/unit/test_gap5_erisa_account_type.py -v
"""

from __future__ import annotations

import ast
import itertools
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from m5_config_loader import SuitabilityStandard

from compliance.gap5_erisa_account_type import (
    ACCOUNT_TYPE_DECISION_SCHEMA_VERSION,
    ALLOWED_WSP_SECTIONS,
    ERISA_GOVERNED_SET,
    RETIREMENT_SET,
    RULE_ID_FIDUCIARY_GATE,
    RULE_ID_PTE_2020_02,
    AccountType,
    AccountTypeDecision,
    AccountTypeEngine,
    AccountTypeRequest,
    AuditClient,
    AuditWriteFailed,
    InMemoryAuditClient,
    Outcome,
    RegoManifestError,
    WSP_FIDUCIARY_GATE,
    WSP_PTE_2020_02,
    fiduciary_gate,
    is_erisa_governed,
    is_retirement,
    is_tax_deferred,
    load_manifest,
    pte_2020_02_gate,
)

# =============================================================================
# Fixtures
# =============================================================================

_TRACE_ID = "trace-0000-0001"
_REQUESTER = "advisor-001"


def _req(
    *,
    account_type: AccountType,
    suitability: SuitabilityStandard = SuitabilityStandard.fiduciary,
    doc_path: str = "reg_bi",
    is_rollover: bool = False,
) -> AccountTypeRequest:
    return AccountTypeRequest(
        trace_id=_TRACE_ID,
        account_type=account_type,
        suitability_standard=suitability,
        proposed_doc_path=doc_path,
        is_rollover=is_rollover,
        requested_by=_REQUESTER,
    )


@pytest.fixture
def audit_client() -> InMemoryAuditClient:
    return InMemoryAuditClient()


@pytest.fixture
def engine(audit_client: InMemoryAuditClient) -> AccountTypeEngine:
    return AccountTypeEngine(audit_client=audit_client)


# =============================================================================
# R1 — Taxonomy (AC5.5 precursor)
# =============================================================================


class TestTaxonomy:
    def test_16_account_types(self):
        # R1.1 — exactly 16 values
        assert len(list(AccountType)) == 16

    def test_retirement_set_cardinality(self):
        # R1.2 — 9 retirement accounts
        assert len(RETIREMENT_SET) == 9

    def test_erisa_governed_subset(self):
        # R1.3 — 5 ERISA accounts, subset of retirement
        assert len(ERISA_GOVERNED_SET) == 5
        assert ERISA_GOVERNED_SET.issubset(RETIREMENT_SET)

    def test_taxable_not_retirement(self):
        assert not is_retirement(AccountType.taxable_brokerage)
        assert not is_erisa_governed(AccountType.taxable_brokerage)

    def test_401k_is_both_retirement_and_erisa(self):
        assert is_retirement(AccountType.k401)
        assert is_erisa_governed(AccountType.k401)

    def test_traditional_ira_retirement_not_erisa(self):
        assert is_retirement(AccountType.traditional_ira)
        assert not is_erisa_governed(AccountType.traditional_ira)

    def test_trusts_not_retirement(self):
        assert not is_retirement(AccountType.trust_revocable)
        assert not is_retirement(AccountType.trust_irrevocable)

    def test_tax_deferred_helper(self):
        assert is_tax_deferred(AccountType.hsa)
        assert is_tax_deferred(AccountType.account_529)
        assert not is_tax_deferred(AccountType.roth_ira)  # Roth is tax-exempt

    def test_canonical_string_values(self):
        # R1.1 — enum values use regulatory names
        assert AccountType.k401.value == "401k"
        assert AccountType.k403b.value == "403b"
        assert AccountType.k457.value == "457"
        assert AccountType.account_529.value == "529"


# =============================================================================
# R3 — Fiduciary gate truth table (AC5.3)
# =============================================================================


class TestFiduciaryGate:
    def test_non_retirement_never_fires(self):
        f = fiduciary_gate(
            account_type=AccountType.taxable_brokerage,
            suitability_standard=SuitabilityStandard.fiduciary,
            proposed_doc_path="reg_bi",
        )
        assert not f.triggered

    def test_retirement_reg_bi_standard_passes(self):
        f = fiduciary_gate(
            account_type=AccountType.traditional_ira,
            suitability_standard=SuitabilityStandard.reg_bi,
            proposed_doc_path="reg_bi",
        )
        assert not f.triggered

    def test_retirement_fiduciary_reg_bi_blocks(self):
        f = fiduciary_gate(
            account_type=AccountType.traditional_ira,
            suitability_standard=SuitabilityStandard.fiduciary,
            proposed_doc_path="reg_bi",
        )
        assert f.triggered
        assert f.rule_id == RULE_ID_FIDUCIARY_GATE
        assert f.wsp_section == WSP_FIDUCIARY_GATE

    def test_retirement_fiduciary_fiduciary_doc_passes(self):
        f = fiduciary_gate(
            account_type=AccountType.k401,
            suitability_standard=SuitabilityStandard.fiduciary,
            proposed_doc_path="fiduciary",
        )
        assert not f.triggered


# =============================================================================
# R4 — PTE 2020-02 gate truth table (AC5.4)
# =============================================================================


class TestPte202002Gate:
    def test_no_rollover_never_fires(self):
        f = pte_2020_02_gate(
            account_type=AccountType.traditional_ira,
            is_rollover=False,
        )
        assert not f.triggered

    def test_rollover_into_taxable_does_not_fire(self):
        f = pte_2020_02_gate(
            account_type=AccountType.taxable_brokerage,
            is_rollover=True,
        )
        assert not f.triggered

    def test_rollover_into_retirement_fires(self):
        f = pte_2020_02_gate(
            account_type=AccountType.k401, is_rollover=True
        )
        assert f.triggered
        assert f.rule_id == RULE_ID_PTE_2020_02
        assert f.wsp_section == WSP_PTE_2020_02


# =============================================================================
# R5 — Engine composition (AC5.5, AC5.6, AC5.7)
# =============================================================================


class TestEngineComposition:
    def test_allow_taxable_reg_bi(
        self, engine: AccountTypeEngine, audit_client: InMemoryAuditClient
    ):
        d = engine.evaluate(
            _req(
                account_type=AccountType.taxable_brokerage,
                suitability=SuitabilityStandard.reg_bi,
                doc_path="reg_bi",
            )
        )
        assert d.outcome == Outcome.ALLOW
        assert d.rule_ids == ()
        assert d.wsp_sections == ()
        # Still audited (R7.1)
        assert len(audit_client.records) == 1
        assert audit_client.records[0]["gap"] == "gap5"

    def test_block_retirement_fiduciary_reg_bi(
        self, engine: AccountTypeEngine, audit_client: InMemoryAuditClient
    ):
        d = engine.evaluate(
            _req(
                account_type=AccountType.traditional_ira,
                suitability=SuitabilityStandard.fiduciary,
                doc_path="reg_bi",
            )
        )
        assert d.outcome == Outcome.BLOCK
        assert RULE_ID_FIDUCIARY_GATE in d.rule_ids
        assert WSP_FIDUCIARY_GATE in d.wsp_sections

    def test_enhanced_doc_rollover(self, engine: AccountTypeEngine):
        d = engine.evaluate(
            _req(
                account_type=AccountType.roth_ira,
                suitability=SuitabilityStandard.reg_bi,
                doc_path="reg_bi",
                is_rollover=True,
            )
        )
        assert d.outcome == Outcome.REQUIRE_ENHANCED_DOC
        assert d.rule_ids == (RULE_ID_PTE_2020_02,)
        assert d.wsp_sections == (WSP_PTE_2020_02,)

    def test_block_wins_over_pte_but_appends_attribution(
        self, engine: AccountTypeEngine
    ):
        # Fiduciary-standard rollover into retirement with reg_bi doc path:
        # BLOCK dominates, but PTE attribution is still recorded.
        d = engine.evaluate(
            _req(
                account_type=AccountType.k401,
                suitability=SuitabilityStandard.fiduciary,
                doc_path="reg_bi",
                is_rollover=True,
            )
        )
        assert d.outcome == Outcome.BLOCK
        assert RULE_ID_FIDUCIARY_GATE in d.rule_ids
        assert RULE_ID_PTE_2020_02 in d.rule_ids
        assert WSP_FIDUCIARY_GATE in d.wsp_sections
        assert WSP_PTE_2020_02 in d.wsp_sections

    def test_rationale_sanitised(self, engine: AccountTypeEngine):
        d = engine.evaluate(
            _req(
                account_type=AccountType.k401,
                suitability=SuitabilityStandard.fiduciary,
                doc_path="reg_bi",
            )
        )
        # AC5.10 — rationale charset
        assert re.match(r"^[A-Za-z0-9 _\-\.\(\)/§]+$", d.rationale)
        assert len(d.rationale) <= 200


# =============================================================================
# AC5.5 — 128-cell decision matrix
# =============================================================================


class TestDecisionMatrix:
    def test_all_128_cells_deterministic(
        self, engine: AccountTypeEngine, audit_client: InMemoryAuditClient
    ):
        # 16 account types × 2 suitability × 2 doc_path × 2 rollover = 128
        combos = list(
            itertools.product(
                list(AccountType),
                [SuitabilityStandard.fiduciary, SuitabilityStandard.reg_bi],
                ["reg_bi", "fiduciary"],
                [False, True],
            )
        )
        assert len(combos) == 128

        for at, suit, dp, roll in combos:
            audit_client.clear()
            d = engine.evaluate(
                _req(
                    account_type=at,
                    suitability=suit,
                    doc_path=dp,
                    is_rollover=roll,
                )
            )
            # Determinism check: same input → same output (already implied
            # by the pure helpers, but exercise the full path).
            d2 = engine.evaluate(
                _req(
                    account_type=at,
                    suitability=suit,
                    doc_path=dp,
                    is_rollover=roll,
                )
            )
            assert d.outcome == d2.outcome
            assert d.rule_ids == d2.rule_ids
            assert d.wsp_sections == d2.wsp_sections

            # Invariant: outcome is one of 3 values
            assert d.outcome in {
                Outcome.ALLOW,
                Outcome.BLOCK,
                Outcome.REQUIRE_ENHANCED_DOC,
            }

            # Invariant: BLOCK only when fiduciary + reg_bi + retirement
            if d.outcome == Outcome.BLOCK:
                assert at in RETIREMENT_SET
                assert suit == SuitabilityStandard.fiduciary
                assert dp == "reg_bi"

            # Invariant: REQUIRE_ENHANCED_DOC only when rollover + retirement
            # and NOT blocked.
            if d.outcome == Outcome.REQUIRE_ENHANCED_DOC:
                assert roll is True
                assert at in RETIREMENT_SET

            # Invariant: rule_ids empty iff ALLOW (R2.5)
            if d.outcome == Outcome.ALLOW:
                assert d.rule_ids == ()
                assert d.wsp_sections == ()
            else:
                assert len(d.rule_ids) >= 1
                assert len(d.wsp_sections) >= 1


# =============================================================================
# R7 — Audit emission (AC5.6, AC5.7, AC5.8)
# =============================================================================


class TestAuditEmission:
    def test_audit_payload_schema(
        self, engine: AccountTypeEngine, audit_client: InMemoryAuditClient
    ):
        engine.evaluate(
            _req(
                account_type=AccountType.taxable_brokerage,
                suitability=SuitabilityStandard.reg_bi,
            )
        )
        rec = audit_client.records[0]
        assert rec["gap"] == "gap5"
        assert rec["schema_version"] == ACCOUNT_TYPE_DECISION_SCHEMA_VERSION
        assert rec["requested_by"] == _REQUESTER
        assert rec["decision"]["outcome"] == "ALLOW"
        assert rec["decision"]["trace_id"] == _TRACE_ID

    def test_audit_emitted_on_block(
        self, engine: AccountTypeEngine, audit_client: InMemoryAuditClient
    ):
        engine.evaluate(
            _req(
                account_type=AccountType.erisa_pension,
                suitability=SuitabilityStandard.fiduciary,
                doc_path="reg_bi",
            )
        )
        rec = audit_client.records[0]
        assert rec["decision"]["outcome"] == "BLOCK"
        assert (
            RULE_ID_FIDUCIARY_GATE
            in rec["decision"]["rule_ids"]
        )

    def test_audit_write_failure_raises(self):
        class _Boom:
            def write(self, payload):
                raise RuntimeError("sink down")

        e = AccountTypeEngine(audit_client=_Boom())
        with pytest.raises(AuditWriteFailed) as excinfo:
            e.evaluate(
                _req(
                    account_type=AccountType.taxable_brokerage,
                    suitability=SuitabilityStandard.reg_bi,
                )
            )
        assert str(excinfo.value) == "audit_write_failed"
        assert excinfo.value.reason == "audit_write_failed"


# =============================================================================
# R6 — wsp_section annotations (AC5.1, AC5.2)
# =============================================================================


class TestWspAnnotations:
    def test_allowed_vocab_expected(self):
        assert "ERISA Policy §404(a)(1)(B)" in ALLOWED_WSP_SECTIONS
        assert "ERISA Policy §PTE 2020-02(b)" in ALLOWED_WSP_SECTIONS
        assert "ERISA Policy §406" in ALLOWED_WSP_SECTIONS
        assert "ERISA Policy §IRC 4975" in ALLOWED_WSP_SECTIONS

    def test_manifest_loads_clean(self):
        bundle_root = (
            Path(__file__).resolve().parents[2]
            / "opa-bundles"
            / "account-type"
        )
        manifest = load_manifest(bundle_root)
        assert manifest["bundle"] == "account-type"
        assert manifest["gap"] == 5
        assert len(manifest["rules"]) >= 4

    def test_every_rego_rule_has_wsp_section(self):
        # AC5.1
        bundle_root = (
            Path(__file__).resolve().parents[2]
            / "opa-bundles"
            / "account-type"
        )
        for rego in bundle_root.glob("*.rego"):
            text = rego.read_text(encoding="utf-8")
            assert "wsp_section:" in text, (
                f"{rego.name} missing wsp_section annotation"
            )

    def test_manifest_rejects_missing_wsp(self, tmp_path: Path):
        bundle = tmp_path / "b"
        bundle.mkdir()
        # A rego file without wsp_section annotation.
        (bundle / "bad.rego").write_text("package x\nrule_a := true\n")
        (bundle / "manifest.json").write_text(
            json.dumps(
                {
                    "bundle": "x",
                    "rules": [
                        {
                            "file": "bad.rego",
                            "wsp_section": "ERISA Policy §406",
                        }
                    ],
                }
            )
        )
        with pytest.raises(RegoManifestError):
            load_manifest(bundle)

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
        with pytest.raises(RegoManifestError) as excinfo:
            load_manifest(bundle)
        assert "not in allowed vocabulary" in str(excinfo.value)

    def test_manifest_missing_file_rejected(self, tmp_path: Path):
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "manifest.json").write_text(
            json.dumps(
                {
                    "bundle": "x",
                    "rules": [
                        {
                            "file": "does_not_exist.rego",
                            "wsp_section": "ERISA Policy §406",
                        }
                    ],
                }
            )
        )
        with pytest.raises(RegoManifestError):
            load_manifest(bundle)

    def test_manifest_malformed_json(self, tmp_path: Path):
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "manifest.json").write_text("{not valid json")
        with pytest.raises(RegoManifestError):
            load_manifest(bundle)


# =============================================================================
# AC5.9 — No LLM SDK imports
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
        src = Path(__file__).resolve().parents[2] / "src" / "compliance" / (
            "gap5_erisa_account_type"
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
# AC5.11 — Module boundary
# =============================================================================


class TestModuleBoundary:
    def test_only_m5_cross_module_import(self):
        allowed = {
            "m5_config_loader",
            "compliance",
            "pydantic",
        }
        src = Path(__file__).resolve().parents[2] / "src" / "compliance" / (
            "gap5_erisa_account_type"
        )
        for py in src.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    top = node.module.split(".")[0]
                    if top in allowed or top.startswith("_") or top == "typing":
                        continue
                    # stdlib modules are fine
                    if top in {
                        "re",
                        "json",
                        "pathlib",
                        "dataclasses",
                        "enum",
                        "typing",
                        "__future__",
                    }:
                        continue
                    assert False, (
                        f"{py} imports disallowed cross-module {node.module}"
                    )


# =============================================================================
# Request validation
# =============================================================================


class TestRequestValidation:
    def test_invalid_account_type_string(self):
        with pytest.raises(ValidationError):
            AccountTypeRequest(
                trace_id=_TRACE_ID,
                account_type="not_a_real_account",  # type: ignore[arg-type]
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="reg_bi",
                requested_by=_REQUESTER,
            )

    def test_trace_id_charset(self):
        with pytest.raises(ValidationError):
            AccountTypeRequest(
                trace_id="has spaces",
                account_type=AccountType.taxable_brokerage,
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="reg_bi",
                requested_by=_REQUESTER,
            )

    def test_doc_path_literal(self):
        with pytest.raises(ValidationError):
            AccountTypeRequest(
                trace_id=_TRACE_ID,
                account_type=AccountType.taxable_brokerage,
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="invalid_path",  # type: ignore[arg-type]
                requested_by=_REQUESTER,
            )

    def test_requested_by_charset(self):
        with pytest.raises(ValidationError):
            AccountTypeRequest(
                trace_id=_TRACE_ID,
                account_type=AccountType.taxable_brokerage,
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="reg_bi",
                requested_by="advisor with spaces",
            )

    def test_decision_rationale_charset_rejected(self):
        with pytest.raises(ValidationError):
            # `@` is outside the safe charset.
            AccountTypeDecision(
                outcome=Outcome.ALLOW,
                account_type=AccountType.taxable_brokerage,
                rule_ids=(),
                wsp_sections=(),
                rationale="client@example.com leak",
                suitability_standard=SuitabilityStandard.reg_bi,
                is_rollover=False,
                trace_id=_TRACE_ID,
            )


# =============================================================================
# Protocol compliance
# =============================================================================


class TestProtocolCompliance:
    def test_inmemory_audit_client_is_audit_client(self):
        c = InMemoryAuditClient()
        assert isinstance(c, AuditClient)

    def test_inmemory_audit_client_records(self):
        c = InMemoryAuditClient()
        c.write({"gap": "gap5", "trace_id": "t1"})
        c.write({"gap": "gap5", "trace_id": "t2"})
        assert len(c.records) == 2
        c.clear()
        assert c.records == ()
