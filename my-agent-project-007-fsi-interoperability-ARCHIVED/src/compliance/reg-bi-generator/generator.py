"""
Gap 1: Reg BI Document Generator — Core Service.

Trigger detection, context assembly, document generation,
storage (WORM + CRM), retrieval, and HITL review workflow.

Deterministic fields: client profile, costs, conflicts — NO LLM.
Narrative fields: LLM-generated from reasoning trace — HITL required.
Applicability: BD and dual-registered only. Pure RIA → skip.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from .models import (
        AdvisorInfo,
        AlternativeConsidered,
        AuditRecord,
        CareObligation,
        ClientInfo,
        ComplianceCheckEntry,
        ComplianceCheckResult,
        ComplianceObligation,
        ConflictEntry,
        ConflictOfInterestObligation,
        ConflictType,
        CostAnalysis,
        DisclosureObligation,
        Obligations,
        REG_BI_TRIGGER_INTENTS,
        RecommendationEvent,
        RecommendationInfo,
        RecommendationType,
        RegBIDocument,
        RegBIQuery,
        RegBIQueryResponse,
        RegBIStatus,
        RegistrationType,
        SecurityRecommendation,
        SourceTrace,
    )
except ImportError:
    from models import (
        AdvisorInfo,
        AlternativeConsidered,
        AuditRecord,
        CareObligation,
        ClientInfo,
        ComplianceCheckEntry,
        ComplianceCheckResult,
        ComplianceObligation,
        ConflictEntry,
        ConflictOfInterestObligation,
        ConflictType,
        CostAnalysis,
        DisclosureObligation,
        Obligations,
        REG_BI_TRIGGER_INTENTS,
        RecommendationEvent,
        RecommendationInfo,
        RecommendationType,
        RegBIDocument,
        RegBIQuery,
        RegBIQueryResponse,
        RegBIStatus,
        RegistrationType,
        SecurityRecommendation,
        SourceTrace,
    )

logger = logging.getLogger("compliance.reg_bi")


class RegBIGeneratorError(Exception):
    """Raised when Reg BI document generation fails."""


class RegBIGenerator:
    """
    Generates structured Reg BI documentation for every recommendation.

    Sub-module of M10 (Audit Logger). Does NOT import from other modules.
    Communicates with M10 WORM/CRM writers via injected callables.
    """

    def __init__(
        self,
        worm_writer: Any = None,
        crm_writer: Any = None,
        conflict_inventory: list[dict[str, str]] | None = None,
    ) -> None:
        self._worm = worm_writer
        self._crm = crm_writer
        self._conflict_inventory = conflict_inventory or []
        # In-memory store for dev/test
        self._store: dict[str, RegBIDocument] = {}

    # ── Trigger Detection ────────────────────────────────────────

    def should_generate(self, event: RecommendationEvent) -> bool:
        """
        Determine if Reg BI document generation is required.

        Returns False for:
        - Pure RIAs (fiduciary duty, not Reg BI)
        - Institutional archetypes (tier1, tier2)
        - Non-recommendation intents
        """
        # Pure RIAs have fiduciary duty, not Reg BI
        if event.registration_type == RegistrationType.ria_only:
            return False
        # Institutional archetypes not subject to Reg BI
        if event.archetype in ("tier1_investment_bank", "tier2_asset_manager"):
            return False
        # Check intent
        if event.intent in REG_BI_TRIGGER_INTENTS:
            return True
        return False

    # ── Document Generation ──────────────────────────────────────

    def generate_document(
        self,
        event: RecommendationEvent,
        client_profile: dict[str, Any] | None = None,
        cost_data: dict[str, Any] | None = None,
        compliance_results: list[dict[str, Any]] | None = None,
    ) -> RegBIDocument:
        """
        Generate a Reg BI document from a recommendation event.

        Deterministic fields populated from structured data.
        Narrative fields left empty for LLM generation + HITL review.
        """
        if not self.should_generate(event):
            raise RegBIGeneratorError(
                f"Reg BI not applicable: registration={event.registration_type.value}, "
                f"archetype={event.archetype}"
            )

        profile = client_profile or {}
        costs = cost_data or {}

        # Build client info from canonical profile
        client = ClientInfo(
            client_id=event.client_id,
            name=profile.get("name", ""),
            risk_tolerance=profile.get("risk_tolerance", "moderate"),
            investment_objectives=profile.get("investment_objectives", []),
            time_horizon=profile.get("time_horizon", "medium_term"),
            annual_income_range=profile.get("annual_income_range", ""),
            net_worth_range=profile.get("net_worth_range", ""),
            liquid_net_worth_range=profile.get("liquid_net_worth_range", ""),
            account_type=profile.get("account_type", ""),
        )

        # Build cost analysis from structured data
        cost_analysis = CostAnalysis(
            estimated_commission=costs.get("commission"),
            estimated_fees=costs.get("fees"),
            expense_ratio=costs.get("expense_ratio"),
            total_estimated_cost=costs.get("total_cost", 0.0),
            cost_comparison_to_alternatives=costs.get("comparison", ""),
        )

        # Build compliance checks from OPA results
        checks = []
        for cr in (compliance_results or []):
            checks.append(ComplianceCheckEntry(
                check_type=cr.get("check_type", "unknown"),
                result=ComplianceCheckResult(cr.get("result", "PASS")),
                rule_applied=cr.get("rule_applied", ""),
                details=cr.get("details", ""),
            ))

        # Build conflict inventory from enterprise config
        conflicts = [
            ConflictEntry(
                conflict_type=ConflictType(c.get("type", "other")),
                description=c.get("description", ""),
                mitigation=c.get("mitigation", ""),
            )
            for c in self._conflict_inventory
        ]

        doc = RegBIDocument(
            firm_id=event.firm_id,
            advisor=AdvisorInfo(
                user_id=event.advisor_id,
                aid_hash=_sha256(event.advisor_id),
            ),
            client=client,
            recommendation=RecommendationInfo(
                type=event.recommendation_type,
                securities=event.securities,
                summary=event.summary,
            ),
            obligations=Obligations(
                disclosure=DisclosureObligation(
                    form_crs_delivered=profile.get("form_crs_delivered", False),
                    fee_schedule_disclosed=bool(costs),
                ),
                care=CareObligation(
                    # Narrative fields left empty — LLM fills, HITL reviews
                    basis_for_recommendation="",
                    best_interest_rationale="",
                    alternatives_considered=[],
                    risk_factors=[],
                    cost_analysis=cost_analysis,
                ),
                conflict_of_interest=ConflictOfInterestObligation(
                    conflicts_identified=conflicts,
                    no_conflicts_attestation=len(conflicts) == 0,
                ),
                compliance=ComplianceObligation(
                    compliance_checks_passed=checks,
                    restricted_list_clear=all(
                        c.result != ComplianceCheckResult.FAIL for c in checks
                    ),
                ),
            ),
            source_trace=SourceTrace(
                trace_id=event.trace_id,
                specialist="reg_bi_generator",
                langfuse_trace_url=event.reasoning_trace_url,
            ),
            status=RegBIStatus.DRAFT,
        )

        self._store[doc.document_id] = doc
        logger.info(
            "Generated Reg BI doc %s for client %s (status=DRAFT)",
            doc.document_id, event.client_id,
        )
        return doc

    # ── HITL Review Workflow ─────────────────────────────────────

    def submit_for_review(self, document_id: str) -> RegBIDocument:
        """Transition document from DRAFT to PENDING_REVIEW."""
        doc = self._get_doc(document_id)
        if doc.status != RegBIStatus.DRAFT:
            raise RegBIGeneratorError(
                f"Cannot submit: document {document_id} is {doc.status.value}, expected DRAFT"
            )
        doc.status = RegBIStatus.PENDING_REVIEW
        doc.audit.sha256_hash = doc._compute_hash()
        return doc

    def finalize(
        self,
        document_id: str,
        reviewer_id: str,
        notes: str = "",
    ) -> RegBIDocument:
        """
        Finalize document after HITL review.
        Transitions PENDING_REVIEW → FINALIZED.
        """
        doc = self._get_doc(document_id)
        if doc.status != RegBIStatus.PENDING_REVIEW:
            raise RegBIGeneratorError(
                f"Cannot finalize: document {document_id} is {doc.status.value}, "
                f"expected PENDING_REVIEW"
            )
        doc.status = RegBIStatus.FINALIZED
        doc.finalized_at = datetime.now(timezone.utc)
        doc.reviewed_by = reviewer_id
        doc.review_timestamp = doc.finalized_at
        doc.review_notes = notes
        doc.audit.sha256_hash = doc._compute_hash()
        logger.info("Finalized Reg BI doc %s by %s", document_id, reviewer_id)
        return doc

    def supersede(self, document_id: str, reason: str = "") -> RegBIDocument:
        """Mark a finalized document as superseded."""
        doc = self._get_doc(document_id)
        if doc.status != RegBIStatus.FINALIZED:
            raise RegBIGeneratorError(
                f"Cannot supersede: document {document_id} is {doc.status.value}"
            )
        doc.status = RegBIStatus.SUPERSEDED
        doc.audit.sha256_hash = doc._compute_hash()
        return doc

    # ── Storage ──────────────────────────────────────────────────

    async def store_to_worm(self, doc: RegBIDocument) -> str:
        """Write document to WORM storage. Returns WORM record ID."""
        key = (
            f"{doc.firm_id}/reg-bi/{doc.created_at.year}/"
            f"{doc.created_at.month:02d}/{doc.document_id}.json"
        )
        if self._worm is not None:
            result = await self._worm.write_document(key, doc.model_dump_json())
            doc.audit.worm_record_id = result
        else:
            doc.audit.worm_record_id = f"s3://007-worm-audit/{key}"
        return doc.audit.worm_record_id

    async def store_to_crm(self, doc: RegBIDocument) -> Optional[str]:
        """Write document reference to CRM. Returns CRM record ID."""
        if self._crm is not None:
            crm_id = await self._crm.write_document(doc.model_dump(mode="json"))
            doc.audit.crm_record_id = crm_id
            return crm_id
        doc.audit.crm_record_id = f"crm-{doc.document_id[:8]}"
        return doc.audit.crm_record_id

    # ── Retrieval ────────────────────────────────────────────────

    def query(self, q: RegBIQuery) -> RegBIQueryResponse:
        """
        Query Reg BI documents by client_id, advisor_id, date range,
        security_id. For FINRA examiner requests.
        """
        results = []
        for doc in self._store.values():
            if doc.firm_id != q.firm_id:
                continue
            if q.client_id and doc.client.client_id != q.client_id:
                continue
            if q.advisor_id and doc.advisor.user_id != q.advisor_id:
                continue
            if q.status and doc.status != q.status:
                continue
            if q.date_from and doc.created_at < q.date_from:
                continue
            if q.date_to and doc.created_at > q.date_to:
                continue
            if q.security_id:
                tickers = {s.ticker for s in doc.recommendation.securities}
                if q.security_id not in tickers:
                    continue
            results.append(doc)

        return RegBIQueryResponse(documents=results, count=len(results))

    def get_document(self, document_id: str) -> Optional[RegBIDocument]:
        """Get a single document by ID."""
        return self._store.get(document_id)

    # ── Helpers ──────────────────────────────────────────────────

    def _get_doc(self, document_id: str) -> RegBIDocument:
        doc = self._store.get(document_id)
        if doc is None:
            raise RegBIGeneratorError(f"Document not found: {document_id}")
        return doc


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
