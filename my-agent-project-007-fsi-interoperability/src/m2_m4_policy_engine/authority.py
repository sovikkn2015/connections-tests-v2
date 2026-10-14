"""
M2/M4 Policy Engine — authority.py

M2 Authority Policy. Deterministic Python rule engine evaluating
ALLOW / DENY / ESCALATE for (identity, action, target, context).

Phase 2 migration (R12): each rule transcribes to a Rego package.
``authority/advisor/restricted_list.v1`` -> Rego package
``authority.advisor.restricted_list`` rule ``v1``.

Rule inventory (list_rules() order, 11 entries):
  authority/meta/excludes_check.v1              WSP-META-0.2
  authority/advisor/restricted_list.v1          WSP-TRD-3.1
  authority/advisor/trading_window.v1           WSP-TRD-3.2
  authority/advisor/chinese_wall.v1             WSP-CWL-4.1
  authority/advisor/pod_isolation.v1            WSP-POD-5.1
  authority/advisor/read_other_advisor_clients.v1   WSP-ADV-1.2
  authority/advisor/read_own_clients.v1         WSP-ADV-1.1
  authority/advisor/concentration_limit.v1      WSP-RISK-2.1
  authority/principal/review_required.v1        WSP-FINRA-2210
  authority/meta/default_deny.v1                WSP-META-0.1
  authority/meta/unknown_action.v1              WSP-META-0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from m1_identity import AidClaims, Role
from m5_config_loader import Archetype, RegistrationType

from m2_m4_policy_engine.decisions import Decision, PolicyDecision, PolicyInput
from m2_m4_policy_engine.rules import _require


# =============================================================================
# Action catalog (R1.4)
# =============================================================================

ACTION_CATALOG: frozenset[str] = frozenset(
    {
        "client.read",
        "client.list",
        "portfolio.view",
        "security.lookup",
        "order.draft",
        "order.submit",
        "payment.draft",
        "comm.send_retail",
    }
)


# =============================================================================
# Helpers
# =============================================================================

_EMPTY_ARCHETYPES: frozenset = frozenset()
_EMPTY_ACTIONS: frozenset[str] = frozenset()

_TRADE_ACTIONS: frozenset[str] = frozenset({"order.draft", "order.submit"})
_CLIENT_READ_ACTIONS: frozenset[str] = frozenset(
    {"client.read", "client.list", "portfolio.view"}
)


# =============================================================================
# Meta rules
# =============================================================================

@dataclass(frozen=True)
class _ExcludesCheckRule:
    """authority/meta/excludes_check.v1 — denies if action is in the
    AID's ``authority_excludes`` negative-authority list.
    """

    name: str = "authority.meta.excludes_check"
    rule_applied: str = "authority/meta/excludes_check.v1"
    wsp_section: str = "WSP-META-0.2"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _EMPTY_ACTIONS
    rule_kind: str = "authority_meta"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        if inp.action in inp.identity.authority_excludes:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="excluded_by_aid",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={"action": inp.action},
            )
        return None


@dataclass(frozen=True)
class _DefaultDenyRule:
    """authority/meta/default_deny.v1 — constructed directly by the
    engine when no rule matched. Not iterated inside the rule loop.
    """

    name: str = "authority.meta.default_deny"
    rule_applied: str = "authority/meta/default_deny.v1"
    wsp_section: str = "WSP-META-0.1"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _EMPTY_ACTIONS
    rule_kind: str = "authority_meta"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        return None  # Engine constructs the default-deny decision.


@dataclass(frozen=True)
class _UnknownActionRule:
    """authority/meta/unknown_action.v1 — constructed directly by the
    engine when ``inp.action`` is not in ACTION_CATALOG.
    """

    name: str = "authority.meta.unknown_action"
    rule_applied: str = "authority/meta/unknown_action.v1"
    wsp_section: str = "WSP-META-0.0"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _EMPTY_ACTIONS
    rule_kind: str = "authority_meta"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        return None  # Engine constructs the unknown-action decision.


# =============================================================================
# Business rules
# =============================================================================

@dataclass(frozen=True)
class _RestrictedListRule:
    """authority/advisor/restricted_list.v1 — DENY trades in restricted
    tickers.
    """

    name: str = "authority.advisor.restricted_list"
    rule_applied: str = "authority/advisor/restricted_list.v1"
    wsp_section: str = "WSP-TRD-3.1"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _TRADE_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        restricted, deny = _require(
            inp.context, "restricted_list", "context",
            self.rule_applied, self.wsp_section,
        )
        if deny is not None:
            return deny
        ticker, deny = _require(
            inp.target, "ticker", "target",
            self.rule_applied, self.wsp_section,
        )
        if deny is not None:
            return deny
        if ticker in restricted:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="ticker_on_restricted_list",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={"ticker": ticker},
            )
        return None


@dataclass(frozen=True)
class _TradingWindowRule:
    """authority/advisor/trading_window.v1 — DENY trades outside
    permitted window.
    """

    name: str = "authority.advisor.trading_window"
    rule_applied: str = "authority/advisor/trading_window.v1"
    wsp_section: str = "WSP-TRD-3.2"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _TRADE_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        if (
            "trading_window_open" not in inp.context
            or inp.context["trading_window_open"] is None
        ):
            return PolicyDecision(
                decision=Decision.DENY,
                reason="missing_context:trading_window_open",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        if inp.context["trading_window_open"] is False:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="trading_window_closed",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        return None


@dataclass(frozen=True)
class _ChineseWallRule:
    """authority/advisor/chinese_wall.v1 — tier1-only. DENY if crossing
    an information barrier (IB/AM).
    """

    name: str = "authority.advisor.chinese_wall"
    rule_applied: str = "authority/advisor/chinese_wall.v1"
    wsp_section: str = "WSP-CWL-4.1"
    archetypes: frozenset = frozenset({Archetype.tier1_investment_bank})
    actions: frozenset[str] = _EMPTY_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        if (
            "crossing_wall" not in inp.context
            or inp.context["crossing_wall"] is None
        ):
            return PolicyDecision(
                decision=Decision.DENY,
                reason="missing_context:crossing_wall",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        if inp.context["crossing_wall"] is True:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="chinese_wall_crossing",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        return None


@dataclass(frozen=True)
class _PodIsolationRule:
    """authority/advisor/pod_isolation.v1 — tier5-only. DENY if
    crossing a pod boundary.
    """

    name: str = "authority.advisor.pod_isolation"
    rule_applied: str = "authority/advisor/pod_isolation.v1"
    wsp_section: str = "WSP-POD-5.1"
    archetypes: frozenset = frozenset({Archetype.tier5_hedge_fund})
    actions: frozenset[str] = _EMPTY_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        if (
            "crossing_pod" not in inp.context
            or inp.context["crossing_pod"] is None
        ):
            return PolicyDecision(
                decision=Decision.DENY,
                reason="missing_context:crossing_pod",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        if inp.context["crossing_pod"] is True:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="pod_crossing",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        return None


@dataclass(frozen=True)
class _ReadOtherAdvisorClientsRule:
    """authority/advisor/read_other_advisor_clients.v1 — DENY
    cross-advisor client reads unless role is compliance_officer.
    """

    name: str = "authority.advisor.read_other_advisor_clients"
    rule_applied: str = "authority/advisor/read_other_advisor_clients.v1"
    wsp_section: str = "WSP-ADV-1.2"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _CLIENT_READ_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"DENY"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        advisor_id, deny = _require(
            inp.target, "advisor_id", "target",
            self.rule_applied, self.wsp_section,
        )
        if deny is not None:
            return deny
        if advisor_id == inp.identity.sub:
            return None  # Own client — defer to read_own_clients.
        if inp.identity.role == Role.compliance_officer:
            return None  # Compliance — defer to read_own_clients (ALLOW).
        return PolicyDecision(
            decision=Decision.DENY,
            reason="cross_advisor_read_forbidden",
            rule_applied=self.rule_applied,
            wsp_section=self.wsp_section,
            details={"role": inp.identity.role.value},
        )


@dataclass(frozen=True)
class _ReadOwnClientsRule:
    """authority/advisor/read_own_clients.v1 — ALLOW if caller is the
    assigned advisor OR compliance_officer. Phase 1 requires role in
    {advisor, compliance_officer}; system/agent roles abstain.
    """

    name: str = "authority.advisor.read_own_clients"
    rule_applied: str = "authority/advisor/read_own_clients.v1"
    wsp_section: str = "WSP-ADV-1.1"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _CLIENT_READ_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"ALLOW"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        advisor_id, deny = _require(
            inp.target, "advisor_id", "target",
            self.rule_applied, self.wsp_section,
        )
        if deny is not None:
            return deny
        if inp.identity.role not in {Role.advisor, Role.compliance_officer}:
            return None  # system/agent roles fall through.
        if (
            advisor_id == inp.identity.sub
            or inp.identity.role == Role.compliance_officer
        ):
            return PolicyDecision(
                decision=Decision.ALLOW,
                reason="advisor_owns_client",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={"role": inp.identity.role.value},
            )
        return None


@dataclass(frozen=True)
class _ConcentrationLimitRule:
    """authority/advisor/concentration_limit.v1 — ESCALATE if
    concentration > 10% in a single security (strict >).

    Accepts only float in [0.0, 1.0]. Any other type (bool, int,
    str, None, out-of-range) is treated as missing (fail-closed DENY).
    """

    name: str = "authority.advisor.concentration_limit"
    rule_applied: str = "authority/advisor/concentration_limit.v1"
    wsp_section: str = "WSP-RISK-2.1"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = _TRADE_ACTIONS
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"ESCALATE"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        raw = inp.context.get("concentration_pct")
        # Strict float: reject None, bool (bool is subclass of int),
        # non-float, and out-of-range values.
        if (
            raw is None
            or isinstance(raw, bool)
            or not isinstance(raw, float)
            or raw < 0.0
            or raw > 1.0
        ):
            return PolicyDecision(
                decision=Decision.DENY,
                reason="missing_context:concentration_pct",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={},
            )
        if raw > 0.10:  # strict > per spec AC-R4-7-3
            return PolicyDecision(
                decision=Decision.ESCALATE,
                reason="concentration_exceeds_10pct",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={"concentration_pct": raw},
            )
        return None


@dataclass(frozen=True)
class _PrincipalReviewRule:
    """authority/principal/review_required.v1 — ESCALATE for FINRA
    2210 when a BD (or dual-registered) firm sends retail
    communication. Phase 1 uses recipient_type only; Phase 2 adds
    content type, channel, and archetype per IMPL-06 Blocker 4.
    """

    name: str = "authority.principal.review_required"
    rule_applied: str = "authority/principal/review_required.v1"
    wsp_section: str = "WSP-FINRA-2210"
    archetypes: frozenset = _EMPTY_ARCHETYPES
    actions: frozenset[str] = frozenset({"comm.send_retail"})
    rule_kind: str = "authority_gate"
    decision_kinds: frozenset[str] = frozenset({"ESCALATE"})

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]:
        reg = inp.identity.registration_type
        if reg not in {
            RegistrationType.bd_only.value,
            RegistrationType.dual_registered.value,
        }:
            return None  # RIA-only skipped.
        recipient_type, deny = _require(
            inp.context, "recipient_type", "context",
            self.rule_applied, self.wsp_section,
        )
        if deny is not None:
            return deny
        if recipient_type == "retail":
            return PolicyDecision(
                decision=Decision.ESCALATE,
                reason="retail_comm_requires_principal_review",
                rule_applied=self.rule_applied,
                wsp_section=self.wsp_section,
                details={
                    "recipient_type": recipient_type,
                    "registration_type": reg,
                },
            )
        return None


# =============================================================================
# AuthorityPolicy engine
# =============================================================================

class AuthorityPolicy:
    """M2 Authority Policy.

    Deterministic Python evaluator. Same input -> same decision every
    call. Fail-closed on any rule exception (DENY / evaluation_error).
    Rule evaluation order: R4.1.
    """

    def __init__(self) -> None:
        self._unknown_action_rule = _UnknownActionRule()
        self._default_deny_rule = _DefaultDenyRule()
        self._rules: tuple = self._build_rules()

    def _build_rules(self) -> tuple:
        """Build the tuple of rules iterated by ``evaluate``.

        Matches spec R4.1. Meta rules (unknown_action, default_deny)
        are NOT iterated — they are applied around the loop.
        """
        return (
            _ExcludesCheckRule(),
            _RestrictedListRule(),
            _TradingWindowRule(),
            _ChineseWallRule(),
            _PodIsolationRule(),
            _ReadOtherAdvisorClientsRule(),
            _ReadOwnClientsRule(),
            _ConcentrationLimitRule(),
            _PrincipalReviewRule(),
        )

    def evaluate(self, inp: PolicyInput) -> PolicyDecision:
        """Evaluate (identity, action, target, context) deterministically.

        Semantics — DENY-OVERRIDES with ALLOW-records:
          1. Unknown action -> immediate DENY / unknown_action.
          2. Iterate rules in defined order.
          3. DENY or ESCALATE is TERMINAL (returned immediately).
          4. ALLOW is recorded as ``first_allow``; loop continues so a
             later DENY/ESCALATE can override.
          5. On any exception, return DENY / "evaluation_error"
             (LITERAL string — exception message DISCARDED).
          6. If loop ends with a recorded ALLOW -> return it.
          7. Otherwise -> default-deny.
        """
        if not isinstance(inp, PolicyInput):
            raise TypeError("inp must be PolicyInput")

        if inp.action not in ACTION_CATALOG:
            return PolicyDecision(
                decision=Decision.DENY,
                reason="unknown_action",
                rule_applied=self._unknown_action_rule.rule_applied,
                wsp_section=self._unknown_action_rule.wsp_section,
                details={"action": inp.action},
            )

        first_allow: Optional[PolicyDecision] = None
        arch_value = inp.identity.archetype  # string in AidClaims
        for rule in self._rules:
            if rule.archetypes:
                allowed_values = {a.value for a in rule.archetypes}
                if arch_value not in allowed_values:
                    continue
            if rule.actions and inp.action not in rule.actions:
                continue
            try:
                decision = rule.evaluate(inp)
            except Exception:
                return PolicyDecision(
                    decision=Decision.DENY,
                    reason="evaluation_error",
                    rule_applied=rule.rule_applied,
                    wsp_section=rule.wsp_section,
                    details={},
                )
            if decision is None:
                continue
            if not isinstance(decision, PolicyDecision):
                return PolicyDecision(
                    decision=Decision.DENY,
                    reason="evaluation_error",
                    rule_applied=rule.rule_applied,
                    wsp_section=rule.wsp_section,
                    details={},
                )
            if decision.decision in (Decision.DENY, Decision.ESCALATE):
                return decision  # Terminal.
            if first_allow is None:
                first_allow = decision  # Record first ALLOW.

        if first_allow is not None:
            return first_allow
        return PolicyDecision(
            decision=Decision.DENY,
            reason="no_rule_matched",
            rule_applied=self._default_deny_rule.rule_applied,
            wsp_section=self._default_deny_rule.wsp_section,
            details={"action": inp.action},
        )

    def list_rules(self) -> list[tuple[str, str]]:
        """Return (rule_applied, wsp_section) for every rule — 11 entries.

        Order: 9 business/meta rules in evaluation order, then
        default_deny, then unknown_action. The engine does not iterate
        default_deny/unknown_action inside the loop; they are listed
        for audit completeness (R2.3, AC-R2-1).
        """
        out = [(r.rule_applied, r.wsp_section) for r in self._rules]
        out.append(
            (
                self._default_deny_rule.rule_applied,
                self._default_deny_rule.wsp_section,
            )
        )
        out.append(
            (
                self._unknown_action_rule.rule_applied,
                self._unknown_action_rule.wsp_section,
            )
        )
        return out

    def rule_table(self) -> list[dict]:
        """Return structured inventory for WSP-to-YAML mapping.

        Entries: rule_applied, wsp_section, archetypes (sorted),
        actions (sorted), rule_kind, decision_kinds (sorted). See
        R10 + AC-R10-5 golden vector.
        """
        def _archetypes(rule) -> list[str]:
            if not rule.archetypes:
                return ["ALL"]
            return sorted(a.value for a in rule.archetypes)

        def _actions(rule) -> list[str]:
            if not rule.actions:
                return ["ALL"]
            return sorted(rule.actions)

        rows: list[dict] = []
        for rule in self._rules:
            rows.append(
                {
                    "rule_applied": rule.rule_applied,
                    "wsp_section": rule.wsp_section,
                    "archetypes": _archetypes(rule),
                    "actions": _actions(rule),
                    "rule_kind": rule.rule_kind,
                    "decision_kinds": sorted(rule.decision_kinds),
                }
            )
        for meta in (self._default_deny_rule, self._unknown_action_rule):
            rows.append(
                {
                    "rule_applied": meta.rule_applied,
                    "wsp_section": meta.wsp_section,
                    "archetypes": _archetypes(meta),
                    "actions": _actions(meta),
                    "rule_kind": meta.rule_kind,
                    "decision_kinds": sorted(meta.decision_kinds),
                }
            )
        return rows
