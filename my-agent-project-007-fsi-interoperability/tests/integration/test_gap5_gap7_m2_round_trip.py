"""
Gap 5 + Gap 7 — M2 Policy Engine Round-Trip Integration Tests.

Exercises the full decision path for each gap through a fake
PolicyDecisionPoint shim that mimics M2's `evaluate()` contract.
Verifies that:
  - every decision reaches the M10-shaped audit sink,
  - payload shape matches the spec schema,
  - fail-closed paths still emit audit records.

No cross-module imports into M2 internals — the shim speaks the same
data shape that M2 does today, which is the correct integration-test
surface.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
      python3 -m pytest \\
      my-agent-project-007-fsi-interoperability/tests/integration/test_gap5_gap7_m2_round_trip.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from m5_config_loader import Jurisdiction, SuitabilityStandard

from compliance.gap5_erisa_account_type import (
    AccountType,
    AccountTypeEngine,
    AccountTypeRequest,
    InMemoryAuditClient as Gap5AuditClient,
    Outcome,
    RULE_ID_FIDUCIARY_GATE,
    RULE_ID_PTE_2020_02,
)
from compliance.gap7_cross_border import (
    EgressGate,
    EgressRequest,
    GDPRLawfulBasis,
    InMemoryAuditClient as Gap7AuditClient,
    MiFIDClientClassification,
)


# =============================================================================
# Fake M2 PolicyDecisionPoint shim
# =============================================================================


@dataclass
class PolicyDecision:
    decision: str  # ALLOW | DENY | BLOCK | REQUIRE_ENHANCED_DOC etc.
    rule_ids: tuple[str, ...]
    wsp_sections: tuple[str, ...]
    trace_id: str


class FakePolicyDecisionPoint:
    """Minimal M2-shaped shim.

    Accepts a mapping of policy name → callable that returns a
    PolicyDecision. Exposes `evaluate(policy, input)` like M2.
    """

    def __init__(
        self, policies: dict[str, Callable[[Any], PolicyDecision]]
    ):
        self._policies = policies
        self.history: list[PolicyDecision] = []

    def evaluate(self, policy: str, input_: Any) -> PolicyDecision:
        if policy not in self._policies:
            raise KeyError(f"policy '{policy}' not registered")
        d = self._policies[policy](input_)
        self.history.append(d)
        return d


# =============================================================================
# Gap 5 round-trip
# =============================================================================


class TestGap5PolicyRoundTrip:
    def test_full_path_fiduciary_block(self):
        audit = Gap5AuditClient()
        engine = AccountTypeEngine(audit_client=audit)

        def gap5_policy(req: AccountTypeRequest) -> PolicyDecision:
            d = engine.evaluate(req)
            return PolicyDecision(
                decision=d.outcome.value,
                rule_ids=d.rule_ids,
                wsp_sections=d.wsp_sections,
                trace_id=d.trace_id,
            )

        pdp = FakePolicyDecisionPoint(
            {"authority.account_type": gap5_policy}
        )
        req = AccountTypeRequest(
            trace_id="trace-int-0001",
            account_type=AccountType.k401,
            suitability_standard=SuitabilityStandard.fiduciary,
            proposed_doc_path="reg_bi",
            requested_by="advisor-int",
        )
        out = pdp.evaluate("authority.account_type", req)

        # Decision shape
        assert out.decision == "BLOCK"
        assert RULE_ID_FIDUCIARY_GATE in out.rule_ids
        # Audit sink received the decision
        assert len(audit.records) == 1
        rec = audit.records[0]
        assert rec["gap"] == "gap5"
        assert rec["decision"]["outcome"] == "BLOCK"

    def test_full_path_pte_enhanced_doc(self):
        audit = Gap5AuditClient()
        engine = AccountTypeEngine(audit_client=audit)

        def gap5_policy(req: AccountTypeRequest) -> PolicyDecision:
            d = engine.evaluate(req)
            return PolicyDecision(
                decision=d.outcome.value,
                rule_ids=d.rule_ids,
                wsp_sections=d.wsp_sections,
                trace_id=d.trace_id,
            )

        pdp = FakePolicyDecisionPoint(
            {"authority.account_type": gap5_policy}
        )
        out = pdp.evaluate(
            "authority.account_type",
            AccountTypeRequest(
                trace_id="trace-int-0002",
                account_type=AccountType.traditional_ira,
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="reg_bi",
                is_rollover=True,
                requested_by="advisor-int",
            ),
        )
        assert out.decision == Outcome.REQUIRE_ENHANCED_DOC.value
        assert RULE_ID_PTE_2020_02 in out.rule_ids


# =============================================================================
# Gap 7 round-trip
# =============================================================================


class TestGap7PolicyRoundTrip:
    def test_full_path_us_to_eu_scc(self):
        audit = Gap7AuditClient()
        gate = EgressGate(audit_client=audit)

        def gap7_policy(req: EgressRequest) -> PolicyDecision:
            d = gate.evaluate(req)
            return PolicyDecision(
                decision=d.outcome,
                rule_ids=d.rule_ids,
                wsp_sections=d.wsp_sections,
                trace_id=d.trace_id,
            )

        pdp = FakePolicyDecisionPoint(
            {"jurisdiction.egress": gap7_policy}
        )
        out = pdp.evaluate(
            "jurisdiction.egress",
            EgressRequest(
                trace_id="trace-int-7001",
                primary_jurisdiction=Jurisdiction.us,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.eu,
                requested_by="advisor-int",
            ),
        )
        assert out.decision == "ALLOW"
        assert len(audit.records) == 1
        rec = audit.records[0]
        assert rec["primary_jurisdiction"] == "us"
        assert rec["data_residency"] == "eu"

    def test_full_path_eu_to_sg_deny(self):
        audit = Gap7AuditClient()
        gate = EgressGate(audit_client=audit)

        def gap7_policy(req: EgressRequest) -> PolicyDecision:
            d = gate.evaluate(req)
            return PolicyDecision(
                decision=d.outcome,
                rule_ids=d.rule_ids,
                wsp_sections=d.wsp_sections,
                trace_id=d.trace_id,
            )

        pdp = FakePolicyDecisionPoint({"jurisdiction.egress": gap7_policy})
        out = pdp.evaluate(
            "jurisdiction.egress",
            EgressRequest(
                trace_id="trace-int-7002",
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.sg,
                target_vendor_jurisdiction=Jurisdiction.sg,
                requested_by="advisor-int",
            ),
        )
        assert out.decision == "DENY"
        assert out.rule_ids == ("gap7.matrix.baseline_deny",)
        rec = audit.records[0]
        assert rec["decision"]["outcome"] == "DENY"

    def test_full_path_eu_pii_cross_border_deny(self):
        audit = Gap7AuditClient()
        gate = EgressGate(audit_client=audit)

        out = gate.evaluate(
            EgressRequest(
                trace_id="trace-int-7003",
                primary_jurisdiction=Jurisdiction.eu,
                data_residency=Jurisdiction.eu,
                target_vendor_jurisdiction=Jurisdiction.us,
                payload_fields=("national_id", "tax_id_eu"),
                lawful_basis=GDPRLawfulBasis.contract,
                scc_on_file=True,
                requested_by="advisor-int",
            )
        )
        assert out.outcome == "DENY"
        # Cross-border MNPI rule fired
        assert "gap7.mnpi.eu_pii_egress" in out.rule_ids
        # And audit record carries the deny
        assert audit.records[0]["decision"]["outcome"] == "DENY"


# =============================================================================
# Both gaps composed — Gap 5 runs before Gap 7 egress (realistic order)
# =============================================================================


class TestGap5ThenGap7:
    def test_account_type_allow_then_egress_allow(self):
        g5_audit = Gap5AuditClient()
        g7_audit = Gap7AuditClient()
        account_engine = AccountTypeEngine(audit_client=g5_audit)
        egress = EgressGate(audit_client=g7_audit)

        # Step 1: account-type gate
        acct_decision = account_engine.evaluate(
            AccountTypeRequest(
                trace_id="trace-compose-0001",
                account_type=AccountType.taxable_brokerage,
                suitability_standard=SuitabilityStandard.reg_bi,
                proposed_doc_path="reg_bi",
                requested_by="advisor-compose",
            )
        )
        assert acct_decision.outcome == Outcome.ALLOW

        # Step 2: egress gate (US intra)
        egress_decision = egress.evaluate(
            EgressRequest(
                trace_id="trace-compose-0001",
                primary_jurisdiction=Jurisdiction.us,
                data_residency=Jurisdiction.us,
                target_vendor_jurisdiction=Jurisdiction.us,
                requested_by="advisor-compose",
            )
        )
        assert egress_decision.outcome == "ALLOW"

        # Both audit sinks captured their decisions
        assert len(g5_audit.records) == 1
        assert len(g7_audit.records) == 1
        # Same trace_id threads through both
        assert (
            g5_audit.records[0]["decision"]["trace_id"]
            == g7_audit.records[0]["decision"]["trace_id"]
            == "trace-compose-0001"
        )

    def test_account_type_block_does_not_reach_egress(self):
        # Realistic flow — if Gap 5 BLOCKs, the caller never calls Gap 7.
        g5_audit = Gap5AuditClient()
        g7_audit = Gap7AuditClient()
        account_engine = AccountTypeEngine(audit_client=g5_audit)
        egress = EgressGate(audit_client=g7_audit)

        acct_decision = account_engine.evaluate(
            AccountTypeRequest(
                trace_id="trace-compose-0002",
                account_type=AccountType.k401,
                suitability_standard=SuitabilityStandard.fiduciary,
                proposed_doc_path="reg_bi",
                requested_by="advisor-compose",
            )
        )
        assert acct_decision.outcome == Outcome.BLOCK

        # Caller does NOT invoke egress for a blocked decision.
        # Assert Gap 7's audit sink stays empty.
        assert len(g7_audit.records) == 0
        # Gap 5's audit record still captures the block
        assert g5_audit.records[0]["decision"]["outcome"] == "BLOCK"
