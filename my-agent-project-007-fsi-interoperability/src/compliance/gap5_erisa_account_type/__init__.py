"""
Gap 5 — ERISA Account-Type Gating — Public API.

Parent module: M2 (Authority Policy Engine).

Deterministic OPA/Rego-backed gate enforcing:
  1. Fiduciary vs Reg BI doc-path branching on retirement accounts
     (ERISA §404(a)(1)(B)).
  2. DOL PTE 2020-02 rollover enhanced-documentation trigger.

No LLM. Fail-closed. All decisions audited to M10 via injected
Protocol.

Usage:
    from compliance.gap5_erisa_account_type import (
        AccountType, AccountTypeEngine, AccountTypeRequest,
        InMemoryAuditClient,
    )

    engine = AccountTypeEngine(audit_client=InMemoryAuditClient())
    decision = engine.evaluate(AccountTypeRequest(...))

See `.kiro/specs/gap5-erisa-account-type.md` for the full contract.
"""

from __future__ import annotations

from compliance.gap5_erisa_account_type._types import (
    ACCOUNT_TYPE_DECISION_SCHEMA_VERSION,
    ALLOWED_WSP_SECTIONS,
    AccountType,
    AuditWriteFailed,
    Outcome,
    RegoManifestError,
)
from compliance.gap5_erisa_account_type.audit_client import (
    AuditClient,
    InMemoryAuditClient,
)
from compliance.gap5_erisa_account_type.engine import (
    AccountTypeDecision,
    AccountTypeEngine,
    AccountTypeRequest,
)
from compliance.gap5_erisa_account_type.gates import (
    RULE_ID_FIDUCIARY_GATE,
    RULE_ID_PTE_2020_02,
    WSP_FIDUCIARY_GATE,
    WSP_PTE_2020_02,
    GateFinding,
    fiduciary_gate,
    pte_2020_02_gate,
)
from compliance.gap5_erisa_account_type.rego_loader import load_manifest
from compliance.gap5_erisa_account_type.taxonomy import (
    ERISA_GOVERNED_SET,
    RETIREMENT_SET,
    TAX_DEFERRED_SET,
    is_erisa_governed,
    is_retirement,
    is_tax_deferred,
)

__all__ = [
    # Enums + constants
    "AccountType",
    "Outcome",
    "ACCOUNT_TYPE_DECISION_SCHEMA_VERSION",
    "ALLOWED_WSP_SECTIONS",
    # Taxonomy sets + helpers
    "RETIREMENT_SET",
    "ERISA_GOVERNED_SET",
    "TAX_DEFERRED_SET",
    "is_retirement",
    "is_erisa_governed",
    "is_tax_deferred",
    # Gates
    "GateFinding",
    "fiduciary_gate",
    "pte_2020_02_gate",
    "RULE_ID_FIDUCIARY_GATE",
    "RULE_ID_PTE_2020_02",
    "WSP_FIDUCIARY_GATE",
    "WSP_PTE_2020_02",
    # Engine + records
    "AccountTypeRequest",
    "AccountTypeDecision",
    "AccountTypeEngine",
    # Audit
    "AuditClient",
    "InMemoryAuditClient",
    "AuditWriteFailed",
    # Manifest loader
    "load_manifest",
    "RegoManifestError",
]
