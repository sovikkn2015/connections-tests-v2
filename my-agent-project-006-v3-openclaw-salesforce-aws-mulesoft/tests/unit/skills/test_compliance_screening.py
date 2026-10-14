"""Tests for compliance_screening skill."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from openclaw.skills.compliance_screening import (
    ComplianceDecision,
    ComplianceInput,
    ProposedAction,
    run,
)


def _mid_day_weekday() -> datetime:
    # Wednesday 2026-03-11 11:00 EDT (15:00 UTC).
    return datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_allow_happy_path(mock_mcp) -> None:
    out = await run(
        ComplianceInput(
            ticker="NVDA",
            principal_id="u",
            proposed_action=ProposedAction.SUBMIT_ORDER,
            current_concentration_pct=5.0,
            session_id="s",
            correlation_id="c",
            as_of=_mid_day_weekday(),
        )
    )
    assert out.decision is ComplianceDecision.ALLOW
    assert out.audit_row_id is None


@pytest.mark.asyncio
async def test_deny_restricted_list(mock_mcp) -> None:
    out = await run(
        ComplianceInput(
            ticker="ACME",  # in restricted_list.json
            principal_id="u",
            proposed_action=ProposedAction.SUBMIT_ORDER,
            session_id="s",
            correlation_id="c",
            as_of=_mid_day_weekday(),
        )
    )
    assert out.decision is ComplianceDecision.DENY
    assert out.restricted_list_hit is True
    assert out.audit_row_id is not None  # steering rule 9


@pytest.mark.asyncio
async def test_review_mnpi_after_restricted_window(mock_mcp) -> None:
    # CYBRX restricted window ends 2026-03-20; on April 1 only MNPI flag left.
    out = await run(
        ComplianceInput(
            ticker="CYBRX",
            principal_id="u",
            proposed_action=ProposedAction.PUBLISH_BRIEF,
            session_id="s",
            correlation_id="c",
            as_of=datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
        )
    )
    assert out.decision is ComplianceDecision.REVIEW
    assert out.mnpi_flag is True


@pytest.mark.asyncio
async def test_deny_concentration_exceeded(mock_mcp) -> None:
    out = await run(
        ComplianceInput(
            ticker="NVDA",
            principal_id="u",
            proposed_action=ProposedAction.SUBMIT_ORDER,
            current_concentration_pct=15.0,
            session_id="s",
            correlation_id="c",
            as_of=_mid_day_weekday(),
        )
    )
    assert out.decision is ComplianceDecision.DENY
    assert out.concentration_ok is False


@pytest.mark.asyncio
async def test_deny_trading_window_closed(mock_mcp) -> None:
    saturday = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
    out = await run(
        ComplianceInput(
            ticker="NVDA",
            principal_id="u",
            proposed_action=ProposedAction.SUBMIT_ORDER,
            session_id="s",
            correlation_id="c",
            as_of=saturday,
        )
    )
    assert out.decision is ComplianceDecision.DENY
    assert out.trading_window_open is False



# ---------------------------------------------------------------------------
# Wave 2: P2.11 - zoneinfo-based DST-boundary check.
# ---------------------------------------------------------------------------

from openclaw.skills.compliance_screening.actions import _is_trading_window_open  # noqa: E402


def test_trading_window_closed_on_sunday_dst_spring_forward():
    """2026-03-08 is the US DST spring-forward Sunday. Market is closed all day.
    The old UTC-offset approximation would treat it as EDT and open (-4h from
    UTC); zoneinfo returns Sunday correctly and keeps the window shut.
    """
    sunday_after_shift = datetime(2026, 3, 8, 14, 30, tzinfo=timezone.utc)
    assert _is_trading_window_open(sunday_after_shift) is False


def test_trading_window_open_monday_after_dst_start():
    """Monday 2026-03-09 10:00 America/New_York (14:00 UTC, DST) is open."""
    monday_edt = datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc)
    assert _is_trading_window_open(monday_edt) is True


def test_trading_window_closed_on_sunday_dst_fall_back():
    """2026-11-01 is US DST fall-back Sunday. Market closed."""
    sunday_fall_back = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)
    assert _is_trading_window_open(sunday_fall_back) is False


def test_trading_window_open_tuesday_after_fall_back():
    """Tuesday 2026-11-03 15:00 UTC -> 10:00 America/New_York (EST). Open."""
    tue_est = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
    assert _is_trading_window_open(tue_est) is True
