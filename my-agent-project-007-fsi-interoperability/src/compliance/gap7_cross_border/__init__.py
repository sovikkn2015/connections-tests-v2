"""
Gap 7 — Cross-Border Regulatory Enforcement — Public API.

Parent module: M2 (Authority Policy Engine), egress hook in M6.

Deterministic jurisdiction-aware gate covering:
  - 5×5 primary × data_residency matrix (US/EU/UK/SG/HK),
  - GDPR Art. 6(1) lawful-basis evaluator,
  - MiFID II product-governance (retail / professional / eligible CP),
  - MAS Notice 626 (SG) + HKMA/SFC (HK) marketing rules,
  - cross-border MNPI filter (runs BEFORE any LLM/vendor call).

No LLM. Fail-closed. All decisions audited to M10 via injected
Protocol.

Usage:
    from compliance.gap7_cross_border import (
        EgressGate, EgressRequest, InMemoryAuditClient,
        GDPRLawfulBasis, MiFIDClientClassification,
    )
    from m5_config_loader import Jurisdiction

    gate = EgressGate(audit_client=InMemoryAuditClient())
    decision = gate.evaluate(EgressRequest(
        trace_id="trace-000001",
        primary_jurisdiction=Jurisdiction.us,
        data_residency=Jurisdiction.us,
        target_vendor_jurisdiction=Jurisdiction.us,
        requested_by="advisor-001",
    ))

See `.kiro/specs/gap7-cross-border.md` for the full contract.
"""

from __future__ import annotations

from m5_config_loader import Jurisdiction  # re-exported for convenience

from compliance.gap7_cross_border._types import (
    ALLOWED_WSP_SECTIONS,
    EGRESS_DECISION_SCHEMA_VERSION,
    AuditWriteFailed,
    GDPRLawfulBasis,
    MiFIDClientClassification,
    RegoManifestError,
    UndefinedJurisdictionPair,
)
from compliance.gap7_cross_border.audit_client import (
    AuditClient,
    InMemoryAuditClient,
)
from compliance.gap7_cross_border.egress_gate import (
    EgressDecision,
    EgressGate,
    EgressRequest,
)
from compliance.gap7_cross_border.gdpr import GdprEvaluation
from compliance.gap7_cross_border.gdpr import evaluate as gdpr_evaluate
from compliance.gap7_cross_border.mas_hkma import (
    MAS_RESTRICTED_RETAIL_PRODUCTS,
    MarketingEvaluation,
    evaluate_hkma_sfc,
    evaluate_mas_notice_626,
)
from compliance.gap7_cross_border.matrix import (
    JURISDICTION_MATRIX,
    MatrixCell,
    matrix_lookup,
)
from compliance.gap7_cross_border.mifid2 import (
    COMPLEX_PRODUCTS,
    MifidEvaluation,
)
from compliance.gap7_cross_border.mifid2 import evaluate as mifid2_evaluate
from compliance.gap7_cross_border.mnpi_cross_border import (
    EU_PII_FIELDS,
    HK_SFC_MNPI_FIELDS,
    CrossBorderScanResult,
    scan_cross_border_mnpi,
)
from compliance.gap7_cross_border.rego_loader import load_manifest

__all__ = [
    # Re-exports
    "Jurisdiction",
    # Enums + constants
    "GDPRLawfulBasis",
    "MiFIDClientClassification",
    "ALLOWED_WSP_SECTIONS",
    "EGRESS_DECISION_SCHEMA_VERSION",
    "COMPLEX_PRODUCTS",
    "MAS_RESTRICTED_RETAIL_PRODUCTS",
    "EU_PII_FIELDS",
    "HK_SFC_MNPI_FIELDS",
    # Errors
    "UndefinedJurisdictionPair",
    "AuditWriteFailed",
    "RegoManifestError",
    # Matrix
    "MatrixCell",
    "JURISDICTION_MATRIX",
    "matrix_lookup",
    # Sub-evaluators
    "GdprEvaluation",
    "gdpr_evaluate",
    "MifidEvaluation",
    "mifid2_evaluate",
    "MarketingEvaluation",
    "evaluate_mas_notice_626",
    "evaluate_hkma_sfc",
    "CrossBorderScanResult",
    "scan_cross_border_mnpi",
    # Gate
    "EgressRequest",
    "EgressDecision",
    "EgressGate",
    # Audit
    "AuditClient",
    "InMemoryAuditClient",
    # Manifest loader
    "load_manifest",
]
