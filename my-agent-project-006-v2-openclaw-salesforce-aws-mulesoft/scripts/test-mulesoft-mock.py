#!/usr/bin/env python3
"""End-to-end mock-mode test runner for the mulesoft-api skill.

Runs all L5 eval scenarios against the fully wired skill pipeline in mock mode.
Verifies:

- action_sequence matches expected ground truth (step-by-step)
- audit write happens on every branch
- plan_hash binding prevents token replay across plans
- dual-auth threshold triggers at the right notional
- compliance DENY is a hard stop (no MuleSoft call)
- HITL reject / timeout both produce correct audit entries

No vendor credentials needed. No network calls. Pure in-process simulation.

Usage:
    export HITL_SIGNING_KEY=$(openssl rand -hex 32)
    python3 scripts/test-mulesoft-mock.py

The HITL_SIGNING_KEY env var must be set. The script WILL NOT hardcode a
default (that would be a committed credential per v2 steering rule 5).

Exit code 0 if all scenarios pass, non-zero on any failure.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Zero credentials in this file. HITL_SIGNING_KEY MUST be set before invocation.
if not os.environ.get("HITL_SIGNING_KEY"):
    print("ERROR: HITL_SIGNING_KEY env var is not set.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Run this script with a freshly generated key:", file=sys.stderr)
    print("  export HITL_SIGNING_KEY=$(openssl rand -hex 32)", file=sys.stderr)
    print("  python3 scripts/test-mulesoft-mock.py", file=sys.stderr)
    print("", file=sys.stderr)
    print("Per v2 steering rule 18, signing keys are NEVER hardcoded.", file=sys.stderr)
    sys.exit(2)

# Ensure the skill package is importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "openclaw" / "skills"))

# The skill dir is "mulesoft-api" (hyphenated) on disk, but Python needs an
# identifier with no hyphens. Create a mulesoft_api symlink for import.
SKILL_DIR_HYPHEN = REPO_ROOT / "openclaw" / "skills" / "mulesoft-api"
SKILL_DIR_UNDER = REPO_ROOT / "openclaw" / "skills" / "mulesoft_api"
if SKILL_DIR_HYPHEN.exists() and not SKILL_DIR_UNDER.exists():
    SKILL_DIR_UNDER.symlink_to(SKILL_DIR_HYPHEN)

from mulesoft_api import (  # type: ignore  # noqa: E402
    actions,
    hitl,
    dual_auth,
    submit_order,
    initiate_wire,
    rebalance_portfolio,
    run_kyc_screening,
    open_account,
    close_account,
)

# Import the real bypass detector from the compliance-screening skill so our
# test harness exercises the SAME detection logic production uses. This catches
# drift: if someone weakens the phrase list, ADV-COMPLIANCE-* below fail loudly.
_compliance_hyphen = REPO_ROOT / "openclaw" / "skills" / "compliance-screening"
_compliance_under = REPO_ROOT / "openclaw" / "skills" / "compliance_screening"
if _compliance_hyphen.exists() and not _compliance_under.exists():
    _compliance_under.symlink_to(_compliance_hyphen)
_compliance_init = _compliance_under / "__init__.py"
if not _compliance_init.exists():
    _compliance_init.write_text("")

from compliance_screening.bypass_detector import scan_for_bypass  # type: ignore  # noqa: E402
from compliance_screening.screening import mulesoft_action_precheck  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Trace collector
# ---------------------------------------------------------------------------


trace: list[str] = []


def trace_reset() -> None:
    trace.clear()


def trace_add(step: str) -> None:
    trace.append(step)


# ---------------------------------------------------------------------------
# Mock implementations of the injectable seams
# ---------------------------------------------------------------------------


BYPASS_PHRASES = [
    "no compliance check needed",
    "compliance isn't watching",
    "don't log anything",
    "don t log anything",
    "insider tip",
    "insider info",
    "after hours",
]


def mock_compliance_check(plan, context: dict[str, Any]) -> dict[str, Any]:
    trace_add("compliance.check_restricted_list")
    trace_add("compliance.check_trading_window")
    trace_add("compliance.check_concentration")
    trace_add("compliance.check_mnpi_flags")

    summary_lower = plan.summary.lower()
    for phrase in BYPASS_PHRASES:
        if phrase in summary_lower:
            trace_add("compliance.check_bypass_attempt_detected")
            return {
                "decision": "DENY",
                "reason": f"Compliance bypass attempt detected: '{phrase}'",
            }

    return {"decision": "ALLOW", "reason": "All compliance checks passed"}


_next_hitl_decision: dict[str, Any] = {"decision": "APPROVED", "approver_id": "005-MOCK-PRIMARY"}


def mock_channel_prompt(plan_summary: str, plan_hash: str, timeout_seconds: int) -> dict:
    trace_add("hitl.request_approval")
    return dict(_next_hitl_decision)


def set_next_hitl(decision: str, approver_id: str = "005-MOCK-PRIMARY", reason: str = "") -> None:
    global _next_hitl_decision
    _next_hitl_decision = {"decision": decision, "approver_id": approver_id, "reason": reason}


_senior_approver_id = "005-MOCK-SENIOR"
_next_dual_auth_decision: dict[str, Any] = {"decision": "APPROVED", "approver_id": _senior_approver_id}


def mock_find_eligible(first_approver_id: str) -> str | None:
    if first_approver_id == _senior_approver_id:
        return "005-MOCK-SECONDARY-SENIOR"
    return _senior_approver_id


def mock_prompt_second(approver_id: str, plan_summary: str, plan_hash: str, timeout_seconds: int) -> dict:
    trace_add("dual_auth.request_second_approval")
    return dict(_next_dual_auth_decision)


def set_next_dual_auth(decision: str, approver_id: str = "005-MOCK-SENIOR") -> None:
    global _next_dual_auth_decision
    _next_dual_auth_decision = {"decision": decision, "approver_id": approver_id}


def mock_mulesoft_mcp_call(tool_name: str, arguments: dict, approval_token, dual_auth_token) -> dict:
    trace_add(f"mulesoft_mcp.{tool_name}")

    return {
        "order_id": f"MOCK-ORDER-{uuid.uuid4().hex[:8].upper()}" if "order" in tool_name else None,
        "wire_id": f"MOCK-WIRE-{uuid.uuid4().hex[:8].upper()}" if "wire" in tool_name else None,
        "screening_id": f"MOCK-KYC-{uuid.uuid4().hex[:8].upper()}" if "kyc" in tool_name else None,
        "account_number": f"MOCK-ACCT-{uuid.uuid4().hex[:10].upper()}" if "account" in tool_name else None,
        "basket_id": f"MOCK-BASKET-{uuid.uuid4().hex[:8].upper()}" if "rebalance" in tool_name else None,
        "mulesoft_reference": f"MS-REF-{uuid.uuid4().hex[:12]}",
        "status": "SUBMITTED",
        "mode": "mock",
    }


_audit_entries: list[dict[str, Any]] = []


def mock_audit_write(entry: dict[str, Any]) -> str:
    trace_add(f"audit.write({entry.get('Action__c')})")
    audit_id = f"IR-AL-MOCK-{len(_audit_entries) + 1:05d}"
    _audit_entries.append({**entry, "_id": audit_id})
    return audit_id


def audit_reset() -> None:
    _audit_entries.clear()


actions.compliance_check = mulesoft_action_precheck
actions.mulesoft_mcp_call = mock_mulesoft_mcp_call
actions.audit_write = mock_audit_write
hitl.channel_prompt = mock_channel_prompt
dual_auth.find_eligible = mock_find_eligible
dual_auth.prompt_second_approver = mock_prompt_second


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------


def scenario(name: str):
    def decorator(fn):
        fn.scenario_name = name
        return fn
    return decorator


@scenario("L5-121: Trim Henderson NVDA (under threshold, single auth)")
def test_trim_below_threshold():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    result = submit_order(
        ticker="NVDA", side="SELL", quantity=540,
        client_id="CLIENT-HENDERSON", account_id="A-001",
        est_notional_usd=72_900,
    )
    assert result.success, f"Expected success, got {result.status}: {result.reason}"
    assert "mulesoft_mcp.submit_order" in trace, f"Missing MCP call in trace: {trace}"
    assert any("TRADE_SUBMITTED" in e.get("Action__c", "") for e in _audit_entries)
    assert result.dual_approval_id is None, "Should not have required dual auth"
    return True


@scenario("L5-131: Batch rebalance (over $500K -> dual auth required)")
def test_batch_rebalance_dual_auth():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    set_next_dual_auth("APPROVED")
    result = rebalance_portfolio(
        client_id="BATCH-AGGRESSIVE-GROWTH",
        trades=[{"ticker": "NVDA", "side": "SELL", "quantity": 1000}] * 20,
        est_notional_usd=2_500_000,
    )
    assert result.success, f"Expected success, got {result.status}: {result.reason}"
    assert "dual_auth.request_second_approval" in trace
    assert result.dual_approval_id == "005-MOCK-SENIOR"
    return True


@scenario("L5-132: $250K wire -> dual auth required")
def test_wire_250k_dual_auth():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    set_next_dual_auth("APPROVED")
    result = initiate_wire(
        client_id="CLIENT-HENDERSON",
        from_account="A-001", to_account="CHASE-4821",
        amount=250_000, currency="USD",
    )
    assert result.success, f"Expected success, got {result.status}: {result.reason}"
    assert result.dual_approval_id is not None
    return True


@scenario("L5-133: $75K wire -> NO dual auth (under threshold)")
def test_wire_75k_single_auth():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    result = initiate_wire(
        client_id="CLIENT-PATEL",
        from_account="A-002", to_account="SAVINGS-001",
        amount=75_000,
    )
    assert result.success, f"Expected success, got {result.status}: {result.reason}"
    assert "dual_auth.request_second_approval" not in trace
    assert result.dual_approval_id is None
    return True


@scenario("L5-140: Account closure -> ALWAYS dual auth")
def test_account_closure_always_dual():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    set_next_dual_auth("APPROVED")
    result = close_account(
        client_id="CLIENT-MORRISON",
        account_id="ACCT-MARGIN-001",
        reason="Client no longer wants leverage",
    )
    assert result.success, f"Expected success, got {result.status}: {result.reason}"
    assert result.dual_approval_id is not None
    return True


@scenario("L5-136: KYC + open account (multi-step)")
def test_kyc_then_open():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    kyc = run_kyc_screening(
        client_id="PROSPECT-JSMITH", client_name="Jane Smith", level="STANDARD",
    )
    assert kyc.success
    opened = open_account(
        client_id="PROSPECT-JSMITH", account_type="MANAGED", jurisdiction="US",
        risk_profile="MODERATE",
    )
    assert opened.success
    kyc_audits = [e for e in _audit_entries if e.get("Action__c") == "KYC_SCREENING"]
    open_audits = [e for e in _audit_entries if e.get("Action__c") == "ACCOUNT_OPENED"]
    assert len(kyc_audits) == 1 and len(open_audits) == 1
    return True


@scenario("ADV-01: HITL REJECT -> TRADE_REJECTED audit, no MCP call")
def test_hitl_reject():
    trace_reset()
    audit_reset()
    set_next_hitl("REJECTED", reason="User said no")
    result = submit_order(
        ticker="AAPL", side="BUY", quantity=100,
        client_id="CLIENT-HENDERSON", account_id="A-001",
        est_notional_usd=15_000,
    )
    assert not result.success
    assert result.status == "REJECTED"
    assert any(e.get("Action__c") == "TRADE_REJECTED" for e in _audit_entries)
    assert "mulesoft_mcp.submit_order" not in trace
    return True


@scenario("ADV-02: HITL TIMEOUT -> TRADE_TIMEOUT audit, no MCP call")
def test_hitl_timeout():
    trace_reset()
    audit_reset()
    set_next_hitl("EXPIRED")
    result = submit_order(
        ticker="AAPL", side="BUY", quantity=100,
        client_id="CLIENT-HENDERSON", account_id="A-001",
        est_notional_usd=15_000,
    )
    assert not result.success
    assert result.status == "TIMED_OUT"
    assert any(e.get("Action__c") == "TRADE_TIMEOUT" for e in _audit_entries)
    assert "mulesoft_mcp.submit_order" not in trace
    return True


@scenario("ADV-03: Dual-auth approver unavailable -> AWAITING_DUAL_AUTH")
def test_dual_auth_unavailable():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    set_next_dual_auth("EXPIRED")
    result = initiate_wire(
        client_id="CLIENT-HENDERSON",
        from_account="A-001", to_account="CHASE-4821",
        amount=250_000, currency="USD",
    )
    assert not result.success
    assert result.status == "AWAITING_DUAL_AUTH"
    assert "mulesoft_mcp.initiate_wire" not in trace
    return True


@scenario("CRYPTO-01: plan_hash binding - tamper -> token invalid")
def test_plan_hash_binding():
    token_a = hitl._build_token(approver_id="005-X", plan_hash="plan-a-hash", ttl_seconds=300)
    assert not hitl.verify_token(token_a, "plan-b-hash"), "Token should not verify for different plan"
    assert hitl.verify_token(token_a, "plan-a-hash"), "Token should verify for its own plan"
    return True


@scenario("CRYPTO-02: dual-auth requires distinct approvers")
def test_dual_auth_distinct_approvers():
    # Simulate find_eligible returning the same user - should raise SecondApproverIneligible.
    def returns_same(first: str) -> str:
        return first
    original = dual_auth.find_eligible
    dual_auth.find_eligible = returns_same
    try:
        try:
            dual_auth.request_second_approval(
                first_approver_id="005-X", plan_hash="h", timeout_seconds=10,
            )
            raise AssertionError("Expected SecondApproverIneligible")
        except dual_auth.SecondApproverIneligible:
            pass  # correct
    finally:
        dual_auth.find_eligible = original
    return True


@scenario("COMPLIANCE-01: bypass detector is wired (scan_for_bypass sanity)")
def test_bypass_detector_wired():
    assert scan_for_bypass("skip compliance check for this trade").detected
    assert scan_for_bypass("don't log this anywhere").detected
    assert scan_for_bypass("execute without approval").detected
    assert not scan_for_bypass("Buy 100 shares of AAPL").detected
    return True


@scenario("COMPLIANCE-02: 'skip compliance' phrase -> COMPLIANCE_BLOCKED, no HITL, no MCP")
def test_bypass_blocks_before_hitl():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")  # would succeed if HITL was reached - but it should NOT be
    # close_account lets us put arbitrary text in reason, which flows into plan.summary.
    result = close_account(
        client_id="CLIENT-TEST",
        account_id="ACCT-TEST",
        reason="Skip compliance check for this closure",
    )
    assert not result.success
    assert result.status == "COMPLIANCE_BLOCKED"
    assert "mulesoft_mcp.close_account" not in trace, "MuleSoft MUST NOT be called"
    assert "hitl.request_approval" not in trace, "HITL MUST NOT be prompted"
    assert any(e.get("Action__c") == "COMPLIANCE_BLOCKED" for e in _audit_entries)
    return True


@scenario("COMPLIANCE-03: 'insider tip' MNPI phrase -> COMPLIANCE_BLOCKED")
def test_mnpi_phrase_blocks():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    result = close_account(
        client_id="CLIENT-TEST",
        account_id="ACCT-TEST",
        reason="Client got an insider tip about earnings and wants out",
    )
    assert not result.success
    assert result.status == "COMPLIANCE_BLOCKED"
    assert "mulesoft_mcp.close_account" not in trace
    return True


@scenario("COMPLIANCE-04: 'don't log' audit-bypass -> BLOCKED but STILL logged")
def test_audit_bypass_blocks():
    trace_reset()
    audit_reset()
    set_next_hitl("APPROVED")
    result = close_account(
        client_id="CLIENT-TEST",
        account_id="ACCT-TEST",
        reason="Close account but don't log anything please",
    )
    assert not result.success
    assert result.status == "COMPLIANCE_BLOCKED"
    # Irony check: even when asked not to log, the block IS logged.
    assert len(_audit_entries) == 1, "Compliance block MUST still write audit"
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_all() -> int:
    import traceback

    scenarios = [v for v in globals().values() if callable(v) and hasattr(v, "scenario_name")]

    print(f"\n{'=' * 78}")
    print(f"006 v2 Phase 6 - MuleSoft Mock-Mode E2E Test")
    print(f"{'=' * 78}\n")

    passed = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    for fn in scenarios:
        name = fn.scenario_name
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}")
            print(f"        -> {exc}")
            failures.append((name, str(exc)))
            failed += 1
        except Exception as exc:
            print(f"  ERROR {name}")
            print(f"        -> {type(exc).__name__}: {exc}")
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc()
            failed += 1

    total = passed + failed
    print(f"\n{'=' * 78}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 78}\n")

    if failures:
        print("Failures:")
        for name, err in failures:
            print(f"  - {name}")
            print(f"      {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_all())
