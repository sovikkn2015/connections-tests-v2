"""Tests for dual_auth skill — thresholds + request/resolve."""

from __future__ import annotations

import pytest

from openclaw.skills.dual_auth import (
    DualAuthDecision,
    DualAuthInput,
    DualAuthThreshold,
    run,
    threshold_required,
)


def test_thresholds_small_trade_not_required() -> None:
    assert threshold_required(action_type="submit_order", notional_usd=10_000) == []


def test_thresholds_large_trade() -> None:
    trig = threshold_required(action_type="submit_order", notional_usd=600_000)
    assert DualAuthThreshold.TRADE_OVER_500K in trig


def test_thresholds_large_wire() -> None:
    trig = threshold_required(action_type="initiate_wire", notional_usd=200_000)
    assert DualAuthThreshold.WIRE_OVER_100K in trig


def test_thresholds_account_closure_always_triggers() -> None:
    trig = threshold_required(
        action_type="close_account", notional_usd=0, is_account_closure=True
    )
    assert DualAuthThreshold.ACCOUNT_CLOSURE in trig


@pytest.mark.asyncio
async def test_not_required_below_thresholds(mock_mcp) -> None:
    out = await run(
        DualAuthInput(
            action_type="submit_order",
            notional_usd=24_000,
            plan_hash="x" * 32,
            first_approver_id="u_rm",
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.decision is DualAuthDecision.NOT_REQUIRED


@pytest.mark.asyncio
async def test_request_phase_creates_pending(mock_mcp) -> None:
    out = await run(
        DualAuthInput(
            action_type="submit_order",
            notional_usd=1_200_000,
            plan_hash="y" * 32,
            first_approver_id="u_rm",
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.decision is DualAuthDecision.PENDING
    assert out.pending_approval_id is not None


def test_second_approver_distinct_enforced() -> None:
    with pytest.raises(Exception):
        DualAuthInput(
            action_type="submit_order",
            notional_usd=1_000_000,
            plan_hash="z" * 32,
            first_approver_id="u_rm",
            second_approver_id="u_rm",  # same — rejected
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
        )


@pytest.mark.asyncio
async def test_resolve_phase_approve(mock_mcp) -> None:
    out = await run(
        DualAuthInput(
            action_type="submit_order",
            notional_usd=1_000_000,
            plan_hash="z" * 32,
            first_approver_id="u_rm",
            pending_approval_id="a0Y_pend_001",
            second_approver_id="u_senior",
            senior_permset_held=True,
            second_approver_decision="approve",
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.decision is DualAuthDecision.APPROVED


@pytest.mark.asyncio
async def test_resolve_phase_rejects_without_permset(mock_mcp) -> None:
    out = await run(
        DualAuthInput(
            action_type="submit_order",
            notional_usd=1_000_000,
            plan_hash="z" * 32,
            first_approver_id="u_rm",
            pending_approval_id="a0Y_pend_001",
            second_approver_id="u_junior",
            senior_permset_held=False,
            second_approver_decision="approve",
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.decision is DualAuthDecision.REJECTED
