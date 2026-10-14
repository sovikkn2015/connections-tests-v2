"""
Gap 4 — M2 PolicyRule adapters.

Thin wrappers around the CTR / SAR monitors that implement the M2
PolicyRule Protocol so they can be registered alongside the M2
AuthorityPolicy rule table. The wrappers read the CashTransaction
and a BsaAmlEngine reference from the PolicyInput.context with M2's
fail-closed `_require` helper.

See .kiro/specs/gap4-bsa-aml-monitoring.md R5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from m2_m4_policy_engine import Decision, PolicyDecision, PolicyInput
from m2_m4_policy_engine.rules import _require

from compliance.gap4_bsa_aml_monitoring.models import CashTransaction


# =============================================================================
# Shared helpers
# =============================================================================


_TRADE_OR_PAYMENT_ACTIONS: frozenset[str] = frozenset(
    {
        "order.submit",
        "payment.draft",
    }
)


def _resolve_context(
    inp: PolicyInput,
    *,
    rule_applied: str,
    wsp_section: str,
) -> tuple[Optional[CashTransaction], Optional[object], Optional[PolicyDecision]]:
    """Fail-closed retrieval of `cash_transaction` + `bsa_aml_engine`
    from `inp.context`. Returns (txn, engine, deny) where exactly one
    of (txn+engine) or deny is non-None."""
    cash_val, deny = _require(
        inp.context,
        "cash_transaction",
        "context",
        rule_applied,
        wsp_section,
    )
    if deny is not None:
        return (None, None, deny)
    if not isinstance(cash_val, CashTransaction):
        return (
            None,
            None,
            PolicyDecision(
                decision=Decision.DENY,
                reason="invalid_context:cash_transaction",
                rule_applied=rule_applied,
                wsp_section=wsp_section,
                details={},
            ),
        )
    engine_val, deny = _require(
        inp.context,
        "bsa_aml_engine",
        "context",
        rule_applied,
        wsp_section,
    )
    if deny is not None:
        return (None, None, deny)
    return (cash_val, engine_val, None)


# =============================================================================
# CtrPolicyRule (spec R5.1)
# =============================================================================


@dataclass(frozen=True)
class CtrPolicyRule:
    """M2 PolicyRule adapter for CTR detection.

    ESCALATE when the engine's CtrMonitor emits any alert for the
    transaction in context. Abstains (None) when the engine is
    disabled.
    """

    name: str = "authority.bsa_aml.ctr"
    rule_applied: str = "authority/bsa_aml/ctr.v1"
    wsp_section: str = "WSP-BSA-8.2"
    archetypes: frozenset = frozenset()
    actions: frozenset[str] = _TRADE_OR_PAYMENT_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"ESCALATE"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        cash_txn, engine, deny = _resolve_context(
            inp, rule_applied=self.rule_applied, wsp_section=self.wsp_section
        )
        if deny is not None:
            return deny

        # Engine disabled / None → abstain (R6.1).
        if engine is None:
            return None
        cfg = getattr(engine, "config", None)
        if cfg is None or not getattr(cfg, "enabled", False):
            return None

        alerts = tuple(
            a
            for a in engine.peek(cash_txn)
            if str(a.rule_applied) == self.rule_applied
        )
        if not alerts:
            return None
        return PolicyDecision(
            decision=Decision.ESCALATE,
            reason="ctr_alert_triggered",
            rule_applied=self.rule_applied,
            wsp_section=self.wsp_section,
            details={
                "alert_ids": [str(a.alert_id) for a in alerts],
                "alert_type": alerts[0].alert_type.value,
            },
        )


# =============================================================================
# SarStructuringPolicyRule (spec R5.3)
# =============================================================================


@dataclass(frozen=True)
class SarStructuringPolicyRule:
    """M2 PolicyRule adapter for SAR structuring detection."""

    name: str = "authority.bsa_aml.sar_structuring"
    rule_applied: str = "authority/bsa_aml/sar_structuring.v1"
    wsp_section: str = "WSP-BSA-8.1"
    archetypes: frozenset = frozenset()
    actions: frozenset[str] = _TRADE_OR_PAYMENT_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"ESCALATE"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        cash_txn, engine, deny = _resolve_context(
            inp, rule_applied=self.rule_applied, wsp_section=self.wsp_section
        )
        if deny is not None:
            return deny

        if engine is None:
            return None
        cfg = getattr(engine, "config", None)
        if cfg is None or not getattr(cfg, "enabled", False):
            return None

        alerts = tuple(
            a
            for a in engine.peek(cash_txn)
            if str(a.rule_applied) == self.rule_applied
        )
        if not alerts:
            return None
        return PolicyDecision(
            decision=Decision.ESCALATE,
            reason="sar_structuring_alert",
            rule_applied=self.rule_applied,
            wsp_section=self.wsp_section,
            details={
                "alert_ids": [str(a.alert_id) for a in alerts],
                "alert_type": alerts[0].alert_type.value,
            },
        )
