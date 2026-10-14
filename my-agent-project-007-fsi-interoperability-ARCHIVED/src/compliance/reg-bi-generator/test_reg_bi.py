"""
Tests for Gap 1: Reg BI Document Generator.

Covers: trigger detection, context assembly, document generation,
HITL lifecycle, storage, retrieval, applicability checks.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"reg_bi_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
# Register as bare 'models' so generator.py's fallback import finds the right one
sys.modules["models"] = _models
_generator = _load_local("generator")

REG_BI_TRIGGER_INTENTS = _models.REG_BI_TRIGGER_INTENTS
RecommendationEvent = _models.RecommendationEvent
RecommendationType = _models.RecommendationType
RegBIDocument = _models.RegBIDocument
RegBIQuery = _models.RegBIQuery
RegBIStatus = _models.RegBIStatus
RegistrationType = _models.RegistrationType
SecurityRecommendation = _models.SecurityRecommendation
RegBIGenerator = _generator.RegBIGenerator
RegBIGeneratorError = _generator.RegBIGeneratorError


# ── Fixtures ─────────────────────────────────────────────────────


def _make_event(
    intent: str = "client.recommend_action",
    registration_type: str = "dual_registered",
    archetype: str = "tier3_broker_dealer",
    **kwargs,
) -> RecommendationEvent:
    return RecommendationEvent(
        trace_id="trace-001",
        intent=intent,
        advisor_id="advisor-001",
        client_id="client-001",
        firm_id="firm-001",
        registration_type=RegistrationType(registration_type),
        archetype=archetype,
        securities=[SecurityRecommendation(ticker="AAPL", action="buy")],
        recommendation_type=RecommendationType.buy,
        summary="Buy AAPL for growth",
        **kwargs,
    )


def _make_generator(**kwargs) -> RegBIGenerator:
    return RegBIGenerator(
        conflict_inventory=[
            {
                "type": "revenue_sharing",
                "description": "Revenue sharing with XYZ Fund",
                "mitigation": "Disclosed in Form CRS",
            }
        ],
        **kwargs,
    )


# ── Trigger Detection ────────────────────────────────────────────


class TestTriggerDetection:
    def test_bd_recommendation_triggers(self):
        gen = _make_generator()
        event = _make_event(registration_type="bd_only")
        assert gen.should_generate(event) is True

    def test_dual_registered_triggers(self):
        gen = _make_generator()
        event = _make_event(registration_type="dual_registered")
        assert gen.should_generate(event) is True

    def test_ria_only_does_not_trigger(self):
        """Pure RIAs have fiduciary duty, not Reg BI."""
        gen = _make_generator()
        event = _make_event(registration_type="ria_only")
        assert gen.should_generate(event) is False

    def test_institutional_archetype_does_not_trigger(self):
        gen = _make_generator()
        for arch in ("tier1_investment_bank", "tier2_asset_manager"):
            event = _make_event(archetype=arch)
            assert gen.should_generate(event) is False

    def test_all_trigger_intents(self):
        gen = _make_generator()
        for intent in REG_BI_TRIGGER_INTENTS:
            event = _make_event(intent=intent)
            assert gen.should_generate(event) is True

    def test_non_recommendation_intent_does_not_trigger(self):
        gen = _make_generator()
        event = _make_event(intent="client.read_profile")
        assert gen.should_generate(event) is False


# ── Document Generation ──────────────────────────────────────────


class TestDocumentGeneration:
    def test_generates_draft_document(self):
        gen = _make_generator()
        event = _make_event()
        doc = gen.generate_document(event)
        assert doc.status == RegBIStatus.DRAFT
        assert doc.firm_id == "firm-001"
        assert doc.client.client_id == "client-001"
        assert doc.advisor.user_id == "advisor-001"

    def test_sha256_hash_computed(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        assert doc.audit.sha256_hash != ""
        assert len(doc.audit.sha256_hash) == 64

    def test_four_obligations_populated(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        assert doc.obligations.disclosure is not None
        assert doc.obligations.care is not None
        assert doc.obligations.conflict_of_interest is not None
        assert doc.obligations.compliance is not None

    def test_conflict_inventory_from_config(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        conflicts = doc.obligations.conflict_of_interest.conflicts_identified
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type.value == "revenue_sharing"

    def test_no_conflicts_attestation_when_empty(self):
        gen = RegBIGenerator(conflict_inventory=[])
        doc = gen.generate_document(_make_event())
        assert doc.obligations.conflict_of_interest.no_conflicts_attestation is True

    def test_narrative_fields_empty_for_hitl(self):
        """Narrative fields left empty — LLM fills, HITL reviews."""
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        assert doc.obligations.care.basis_for_recommendation == ""
        assert doc.obligations.care.best_interest_rationale == ""

    def test_compliance_results_populated(self):
        gen = _make_generator()
        doc = gen.generate_document(
            _make_event(),
            compliance_results=[
                {"check_type": "restricted_list", "result": "PASS", "rule_applied": "authority/restricted_list.rego"},
                {"check_type": "concentration", "result": "WARN", "rule_applied": "authority/concentration.rego"},
            ],
        )
        checks = doc.obligations.compliance.compliance_checks_passed
        assert len(checks) == 2
        assert checks[0].result.value == "PASS"
        assert doc.obligations.compliance.restricted_list_clear is True

    def test_raises_for_ria_only(self):
        gen = _make_generator()
        event = _make_event(registration_type="ria_only")
        with pytest.raises(RegBIGeneratorError, match="not applicable"):
            gen.generate_document(event)

    def test_cost_data_populated(self):
        gen = _make_generator()
        doc = gen.generate_document(
            _make_event(),
            cost_data={"commission": 9.99, "total_cost": 9.99},
        )
        assert doc.obligations.care.cost_analysis.estimated_commission == 9.99
        assert doc.obligations.disclosure.fee_schedule_disclosed is True


# ── HITL Lifecycle ───────────────────────────────────────────────


class TestHITLLifecycle:
    def test_draft_to_pending_review(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        updated = gen.submit_for_review(doc.document_id)
        assert updated.status == RegBIStatus.PENDING_REVIEW

    def test_pending_review_to_finalized(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        gen.submit_for_review(doc.document_id)
        finalized = gen.finalize(doc.document_id, "reviewer-001", "Looks good")
        assert finalized.status == RegBIStatus.FINALIZED
        assert finalized.reviewed_by == "reviewer-001"
        assert finalized.finalized_at is not None

    def test_finalized_to_superseded(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        gen.submit_for_review(doc.document_id)
        gen.finalize(doc.document_id, "reviewer-001")
        superseded = gen.supersede(doc.document_id)
        assert superseded.status == RegBIStatus.SUPERSEDED

    def test_cannot_finalize_draft(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        with pytest.raises(RegBIGeneratorError, match="expected PENDING_REVIEW"):
            gen.finalize(doc.document_id, "reviewer-001")

    def test_cannot_submit_finalized(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        gen.submit_for_review(doc.document_id)
        gen.finalize(doc.document_id, "reviewer-001")
        with pytest.raises(RegBIGeneratorError, match="expected DRAFT"):
            gen.submit_for_review(doc.document_id)

    def test_cannot_supersede_draft(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        with pytest.raises(RegBIGeneratorError):
            gen.supersede(doc.document_id)

    def test_hash_changes_on_status_transition(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        hash_draft = doc.audit.sha256_hash
        gen.submit_for_review(doc.document_id)
        hash_pending = doc.audit.sha256_hash
        assert hash_draft != hash_pending


# ── Retrieval ────────────────────────────────────────────────────


class TestRetrieval:
    def test_query_by_client_id(self):
        gen = _make_generator()
        gen.generate_document(_make_event())
        gen.generate_document(_make_event(
            intent="execution.prepare_order",
        ))
        result = gen.query(RegBIQuery(firm_id="firm-001", client_id="client-001"))
        assert result.count == 2

    def test_query_by_status(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        gen.submit_for_review(doc.document_id)
        result = gen.query(RegBIQuery(
            firm_id="firm-001", status=RegBIStatus.PENDING_REVIEW,
        ))
        assert result.count == 1

    def test_query_by_security(self):
        gen = _make_generator()
        gen.generate_document(_make_event())
        result = gen.query(RegBIQuery(firm_id="firm-001", security_id="AAPL"))
        assert result.count == 1
        result2 = gen.query(RegBIQuery(firm_id="firm-001", security_id="MSFT"))
        assert result2.count == 0

    def test_get_document_by_id(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        retrieved = gen.get_document(doc.document_id)
        assert retrieved is not None
        assert retrieved.document_id == doc.document_id

    def test_get_nonexistent_returns_none(self):
        gen = _make_generator()
        assert gen.get_document("nonexistent") is None


# ── Storage ──────────────────────────────────────────────────────


class TestStorage:
    @pytest.mark.asyncio
    async def test_store_to_worm_dev_mode(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        worm_id = await gen.store_to_worm(doc)
        assert worm_id.startswith("s3://007-worm-audit/")
        assert doc.audit.worm_record_id == worm_id

    @pytest.mark.asyncio
    async def test_store_to_crm_dev_mode(self):
        gen = _make_generator()
        doc = gen.generate_document(_make_event())
        crm_id = await gen.store_to_crm(doc)
        assert crm_id.startswith("crm-")
        assert doc.audit.crm_record_id == crm_id
