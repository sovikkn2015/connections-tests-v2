"""
Gap 4 — BSA/AML Monitoring — Public API.

Parent module: M2 (Authority Policy) + M10 (Audit Logger).

Deterministic post-trade BSA/AML monitor that implements:
- CTR threshold detection (31 CFR §1010.311: cash >= $10,000).
- SAR structuring detection (31 CFR §1023.320: 3+ mid-band deposits
  in 7 days).
- Alert emission to compliance officer ONLY (31 U.S.C. §5318(g)(2)
  anti-tipping-off).
- M10 audit emission on every alert.

All classification is deterministic Python + OPA/Rego. NO LLM calls.

Usage:
    from compliance.gap4_bsa_aml_monitoring import (
        BsaAmlEngine, CashTransaction, CashTransactionCategory,
        InMemoryWindowStore, AuditEmitter, CtrPolicyRule,
        SarStructuringPolicyRule,
    )

    engine = BsaAmlEngine(
        config=bsa_aml_config,
        store=InMemoryWindowStore(),
        clock=lambda: datetime.now(timezone.utc),
        audit_emitter=AuditEmitter(audit=audit_logger, firm_id="firm-1"),
    )
    alerts = engine.evaluate_post_trade(cash_txn)

See `.kiro/specs/gap4-bsa-aml-monitoring.md` for the full contract.
"""

from __future__ import annotations

from compliance.gap4_bsa_aml_monitoring.models import (
    ALERT_REASONS,
    CTR_THRESHOLD_USD_DEFAULT,
    SAR_STRUCTURING_LOWER_USD_DEFAULT,
    SAR_STRUCTURING_UPPER_USD_DEFAULT,
    AlertSeverity,
    AlertType,
    BsaAmlAlert,
    CashTransaction,
    CashTransactionCategory,
    NotACashTransactionError,
)
from compliance.gap4_bsa_aml_monitoring.window_store import (
    InMemoryWindowStore,
    RedisWindowStore,
    WindowStore,
)
from compliance.gap4_bsa_aml_monitoring.monitors import (
    CtrMonitor,
    SarStructuringMonitor,
)
from compliance.gap4_bsa_aml_monitoring.rules import (
    CtrPolicyRule,
    SarStructuringPolicyRule,
)
from compliance.gap4_bsa_aml_monitoring.audit_emitter import (
    AlertEmitFailed,
    AuditEmitter,
)
from compliance.gap4_bsa_aml_monitoring.config import BsaAmlEngine

__all__ = [
    # Models
    "CashTransactionCategory",
    "CashTransaction",
    "NotACashTransactionError",
    "AlertType",
    "AlertSeverity",
    "BsaAmlAlert",
    "ALERT_REASONS",
    # Thresholds (defaults — runtime uses BsaAmlConfig from M5)
    "CTR_THRESHOLD_USD_DEFAULT",
    "SAR_STRUCTURING_UPPER_USD_DEFAULT",
    "SAR_STRUCTURING_LOWER_USD_DEFAULT",
    # Window store
    "WindowStore",
    "InMemoryWindowStore",
    "RedisWindowStore",
    # Monitors
    "CtrMonitor",
    "SarStructuringMonitor",
    # M2 adapters
    "CtrPolicyRule",
    "SarStructuringPolicyRule",
    # M10 adapter
    "AuditEmitter",
    "AlertEmitFailed",
    # Orchestrator
    "BsaAmlEngine",
]
