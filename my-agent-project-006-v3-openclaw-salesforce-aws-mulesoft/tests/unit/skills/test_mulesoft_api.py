"""Tests for mulesoft_api skill — choke point + OFAC + mock mode."""

from __future__ import annotations

import pytest

from openclaw.skills.mulesoft_api import (
    MuleSoftInput,
    MuleSoftMethod,
    MuleSoftMode,
    run,
)


_APPROVAL = {"user_id": "u_rm", "plan_hash": "h" * 32}


@pytest.mark.asyncio
async def test_submit_order_mock(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.SUBMIT_ORDER,
            args={"ticker": "NVDA", "qty": 150, "side": "sell"},
            hitl_approval=_APPROVAL,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is True
    assert out.mode is MuleSoftMode.MOCK
    assert out.vendor_reference and out.vendor_reference.startswith("ALPACA-")
    assert out.mulesoft_reference and out.mulesoft_reference.startswith("MS-TRD-")


@pytest.mark.asyncio
async def test_cancel_order_mock(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.CANCEL_ORDER,
            args={"order_id": "ALPACA-abc"},
            hitl_approval=_APPROVAL,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is True
    assert out.data["status"] == "canceled"


@pytest.mark.asyncio
async def test_modify_order_mock(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.MODIFY_ORDER,
            args={"order_id": "ALPACA-abc", "limit_price": 165.0},
            hitl_approval=_APPROVAL,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is True
    assert out.data["status"] == "replaced"


@pytest.mark.asyncio
async def test_initiate_wire_clean(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.INITIATE_WIRE,
            args={
                "amount_usd": 24_322.50,
                "beneficiary_name": "HSBC Singapore",
                "beneficiary_bank": "HSBC-SG",
            },
            hitl_approval=_APPROVAL,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is True
    assert out.ofac_screening is not None
    assert out.ofac_screening["hit"] is None


@pytest.mark.asyncio
async def test_initiate_wire_ofac_hit_blocks(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.INITIATE_WIRE,
            args={
                "amount_usd": 50_000.0,
                "beneficiary_name": "Sanctioned Shipping Ltd Cairo Office",
                "beneficiary_bank": "Blocked",
            },
            hitl_approval=_APPROVAL,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is False
    assert out.error.startswith("ofac_sdn_hit:")
    assert out.ofac_screening["hit"] is not None


def test_writes_require_approval() -> None:
    with pytest.raises(Exception):
        MuleSoftInput(
            method=MuleSoftMethod.SUBMIT_ORDER,
            args={"ticker": "NVDA"},
            hitl_approval=None,
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
        )


@pytest.mark.asyncio
async def test_webhook_no_approval_needed(mock_mcp) -> None:
    out = await run(
        MuleSoftInput(
            method=MuleSoftMethod.ORDER_STATUS_WEBHOOK,
            args={
                "order_id": "ALPACA-7f2a",
                "status": "filled",
                "filled_qty": 150,
                "filled_avg_price": 162.15,
            },
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.success is True
