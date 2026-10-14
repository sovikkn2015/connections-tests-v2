"""
Gap 4 — Integration tests.

Exercises the full M2 <-> Gap 4 round-trip and the Gap 4 <-> M10 audit
path with real AuditLogger + 3-tier backends. Also verifies the
archetype-gated disable via a real M5 loader path.

Maps to T4.39 / T4.40 / T4.41 in .kiro/specs/gap4-bsa-aml-monitoring.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from m2_m4_policy_engine import Decision, PolicyInput
from m5_config_loader import BsaAmlConfig
from m10_audit_logger import (
    AuditLogger,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
)

from compliance.gap4_bsa_aml_monitoring import (
    AlertType,
    AuditEmitter,
    BsaAmlEngine,
    CashTransaction,
    CashTransactionCategory,
    CtrPolicyRule,
    InMemoryWindowStore,
    SarStructuringPolicyRule,
)


_FIRM = "firm-test-int-1"
_CLIENT = UUID("00000000-0000-0000-0000-000000000101")
_ACCOUNT = UUID("00000000-0000-0000-0000-000000000102")
_BASE_TS = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def _cash(
    amount: str,
    *,
    category: CashTransactionCategory = CashTransactionCategory.cash_deposit,
    delta_seconds: int = 0,
) -> CashTransaction:
    return CashTransaction(
        txn_id=uuid4(),
        client_id=_CLIENT,
        account_id=_ACCOUNT,
        category=category,
        amount_usd=Decimal(amount),
        occurred_at=_BASE_TS + timedelta(seconds=delta_seconds),
        firm_id=_FIRM,
        source_txn_ref="int-src",
        trace_id="trace-int-1",
    )


# =============================================================================
# T4.39 — Full M2 PolicyRule round-trip (engine-style evaluation).
# =============================================================================


def test_t4_39_ctr_rule_oracle_roundtrip(fixture_aid_advisor):
    """CtrPolicyRule evaluated through an M2 PolicyInput must ESCALATE
    when the Gap 4 engine would have raised an alert."""
    store = InMemoryWindowStore()
    cfg = BsaAmlConfig(
        enabled=True, ctr_threshold=10000.0, sar_structuring_threshold=7000.0
    )
    engine = BsaAmlEngine(
        config=cfg,
        store=store,
        clock=lambda: _BASE_TS + timedelta(hours=1),
    )
    rule = CtrPolicyRule()

    txn_pass = _cash("500")
    decision_pass = rule.evaluate(
        PolicyInput(
            identity=fixture_aid_advisor,
            action="order.submit",
            target={"ticker": "XYZ"},
            context={
                "cash_transaction": txn_pass,
                "bsa_aml_engine": engine,
            },
        )
    )
    assert decision_pass is None  # abstain — no alert

    txn_ctr = _cash("11000")
    decision_ctr = rule.evaluate(
        PolicyInput(
            identity=fixture_aid_advisor,
            action="order.submit",
            target={"ticker": "XYZ"},
            context={
                "cash_transaction": txn_ctr,
                "bsa_aml_engine": engine,
            },
        )
    )
    assert decision_ctr is not None
    assert decision_ctr.decision == Decision.ESCALATE
    assert decision_ctr.wsp_section == "WSP-BSA-8.2"
    assert decision_ctr.rule_applied == "authority/bsa_aml/ctr.v1"


def test_t4_39_sar_rule_oracle_roundtrip(fixture_aid_advisor):
    """Structuring alert reaches the M2 adapter when the engine
    accumulated a mid-band pattern."""
    store = InMemoryWindowStore()
    cfg = BsaAmlConfig(
        enabled=True, ctr_threshold=10000.0, sar_structuring_threshold=7000.0
    )
    engine = BsaAmlEngine(
        config=cfg,
        store=store,
        clock=lambda: _BASE_TS + timedelta(hours=4),
    )
    # Pre-populate 2 mid-band deposits.
    for i in range(2):
        engine.evaluate_post_trade(
            _cash("8000", delta_seconds=i * 3600)
        )
    rule = SarStructuringPolicyRule()
    current = _cash("8500", delta_seconds=3 * 3600)
    decision = rule.evaluate(
        PolicyInput(
            identity=fixture_aid_advisor,
            action="payment.draft",
            target={"ticker": "X"},
            context={"cash_transaction": current, "bsa_aml_engine": engine},
        )
    )
    assert decision is not None
    assert decision.decision == Decision.ESCALATE
    assert decision.wsp_section == "WSP-BSA-8.1"


# =============================================================================
# T4.40 — End-to-end Gap 4 → M10 audit path.
# =============================================================================


def test_t4_40_audit_emission_end_to_end():
    """Trigger a CTR alert → AuditEmitter writes to 3-tier M10 stack →
    all three in-memory backends have the entry + integrity hash."""
    langfuse = InMemoryAuditBackend(tier="langfuse")
    worm = InMemoryAuditBackend(tier="worm")
    crm = InMemoryAuditBackend(tier="crm")
    audit = AuditLogger(
        langfuse=langfuse, worm=worm, crm=crm, dlq=InMemoryAuditDLQ()
    )
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    store = InMemoryWindowStore()
    cfg = BsaAmlConfig(
        enabled=True, ctr_threshold=10000.0, sar_structuring_threshold=7000.0
    )
    engine = BsaAmlEngine(
        config=cfg,
        store=store,
        clock=lambda: _BASE_TS + timedelta(hours=2),
        audit_emitter=emitter,
    )
    alerts = engine.evaluate_post_trade(_cash("15000"))
    assert len(alerts) >= 1

    # All 3 backends received the entry.
    assert len(langfuse.entries) == len(alerts)
    assert len(worm.entries) == len(alerts)
    assert len(crm.entries) == len(alerts)

    # Integrity hash attached + verifies.
    for entry in worm.entries:
        assert entry.sha256_integrity != ""
        assert audit.verify_integrity(entry) is True
        # Anti-tipping-off invariants preserved in audit trail.
        assert entry.action == "bsa_aml.alert_emitted"
        assert entry.target_type == "cash_transaction"
        assert entry.decision == "ESCALATE"
        assert entry.wsp_section in {"WSP-BSA-8.1", "WSP-BSA-8.2"}
        assert entry.retention_years >= 6


# =============================================================================
# T4.41 — Archetype-gated disable via real M5 BsaAmlConfig.
# =============================================================================


def test_t4_41_archetype_gated_disable_via_m5_loader():
    """Build a BsaAmlConfig with enabled=False (the tier4 RIA firm that
    is exempt from Phase-3 BD-only BSA/AML program requirements) and
    verify Gap 4 short-circuits end-to-end."""
    cfg_disabled = BsaAmlConfig(
        enabled=False,
        ctr_threshold=10000.0,
        sar_structuring_threshold=7000.0,
    )
    langfuse = InMemoryAuditBackend(tier="langfuse")
    worm = InMemoryAuditBackend(tier="worm")
    crm = InMemoryAuditBackend(tier="crm")
    audit = AuditLogger(
        langfuse=langfuse, worm=worm, crm=crm, dlq=InMemoryAuditDLQ()
    )
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    store = InMemoryWindowStore()
    engine = BsaAmlEngine(
        config=cfg_disabled,
        store=store,
        clock=lambda: _BASE_TS + timedelta(hours=2),
        audit_emitter=emitter,
    )
    # Run 50 txns that would otherwise trigger massive alerts.
    for i in range(50):
        out = engine.evaluate_post_trade(_cash("50000", delta_seconds=i))
        assert out == ()
    # Zero side effects:
    assert store.size() == 0
    assert langfuse.entries == []
    assert worm.entries == []
    assert crm.entries == []
