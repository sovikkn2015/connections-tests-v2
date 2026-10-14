"""
Gap 2 — Liability Provenance — Public API.

Parent modules: M6 (MCP Gateway) + M10 (Audit Logger).

This sub-module adds three pieces on top of M10's
ProvenanceChainBuilder:

1. WarrantyBoundary  - per-module warranty classification.
2. ErrorAttribution  - 6-category error taxonomy.
3. LiabilityReport   - deterministic regulator-ready artifact.

Phase 1: deterministic Python only. NO LLM calls.
Phase 2: add reason_codes + Reg BI (Gap 1) integration.

Usage:
    from compliance.gap2_liability_provenance import (
        WarrantyBoundary, ErrorCategory, ErrorAttribution,
        LiabilityReport,
    )

    boundary = WarrantyBoundary()
    cls_m1 = boundary.classify("m1")       # warranted

    err = ErrorAttribution.attribute_from_chain(
        chain=builder.chain(),
        failing_stage_name="m8.synthesize",
        category=ErrorCategory.llm_synthesis_error,
        reason="Sonnet returned contradictory numbers",
        occurred_at=utc_now,
    )

    report = LiabilityReport.build(
        trace_id="trace-...",
        chain=builder.chain(),
        chain_verified=builder.verify(),
        generated_at=utc_now,
        error=err,
    )
    audit_payload = report.to_canonical_json()

See `.kiro/specs/gap2-liability-provenance.md` for the full contract.
"""

from __future__ import annotations

from compliance.gap2_liability_provenance.warranty import (
    WarrantyBoundary,
    WarrantyCategory,
    WarrantyClassification,
    WarrantyReason,
)
from compliance.gap2_liability_provenance.attribution import (
    ErrorAttribution,
    ErrorCategory,
    LiabilityReport,
    LiabilitySummary,
    REPORT_SCHEMA_VERSION,
    StageClassification,
)

__all__ = [
    # Warranty
    "WarrantyCategory",
    "WarrantyReason",
    "WarrantyClassification",
    "WarrantyBoundary",
    # Attribution
    "ErrorCategory",
    "ErrorAttribution",
    # Report
    "StageClassification",
    "LiabilitySummary",
    "LiabilityReport",
    "REPORT_SCHEMA_VERSION",
]
