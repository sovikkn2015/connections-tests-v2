"""Tests for hitl skill — HMAC tokens, replay, tamper, expiry, plan-bind."""

from __future__ import annotations

import pytest

from openclaw.skills.hitl import (
    ApprovalMintInput,
    ApprovalVerifyInput,
    HITLError,
    compute_plan_hash,
    mint,
    verify,
)
from openclaw.skills.hitl._tokens import TokenStore, replace_default_store


@pytest.fixture(autouse=True)
def _fresh_store() -> TokenStore:
    store = TokenStore()
    replace_default_store(store)
    return store


@pytest.mark.asyncio
async def test_mint_and_verify_roundtrip(mock_mcp) -> None:
    plan = {"ticker": "NVDA", "qty": 100, "side": "sell"}
    mint_out = await mint(
        ApprovalMintInput(
            action_plan=plan,
            user_id="u_rm",
            ttl_seconds=300,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert mint_out.plan_hash == compute_plan_hash(plan)
    verify_out = await verify(
        ApprovalVerifyInput(
            token=mint_out.token,
            action_plan=plan,
            expected_user_id="u_rm",
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    assert verify_out.approved is True
    assert verify_out.user_id == "u_rm"
    assert verify_out.token_fingerprint


@pytest.mark.asyncio
async def test_verify_rejects_tampered_token(mock_mcp) -> None:
    plan = {"ticker": "NVDA", "qty": 100}
    mint_out = await mint(
        ApprovalMintInput(
            action_plan=plan,
            user_id="u",
            principal_id="u",
            agent_id="action_specialist",
            session_id="s",
            correlation_id="c",
        )
    )
    tampered = mint_out.token[:-4] + "ffff"
    with pytest.raises(HITLError) as ex:
        await verify(
            ApprovalVerifyInput(
                token=tampered,
                action_plan=plan,
                principal_id="u",
                agent_id="action_specialist",
                session_id="s",
                correlation_id="c",
            )
        )
    assert ex.value.kind == "tamper"


@pytest.mark.asyncio
async def test_verify_rejects_plan_mismatch(mock_mcp) -> None:
    plan = {"ticker": "NVDA", "qty": 100}
    mint_out = await mint(
        ApprovalMintInput(
            action_plan=plan,
            user_id="u",
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
        )
    )
    with pytest.raises(HITLError) as ex:
        await verify(
            ApprovalVerifyInput(
                token=mint_out.token,
                action_plan={"ticker": "AMD", "qty": 999},
                principal_id="u",
                agent_id="a",
                session_id="s",
                correlation_id="c",
            )
        )
    assert ex.value.kind == "plan_mismatch"


@pytest.mark.asyncio
async def test_verify_rejects_replay(mock_mcp) -> None:
    plan = {"ticker": "NVDA"}
    mint_out = await mint(
        ApprovalMintInput(
            action_plan=plan,
            user_id="u",
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
        )
    )
    common = dict(
        token=mint_out.token,
        action_plan=plan,
        principal_id="u",
        agent_id="a",
        session_id="s",
        correlation_id="c",
    )
    await verify(ApprovalVerifyInput(**common))
    with pytest.raises(HITLError) as ex:
        await verify(ApprovalVerifyInput(**common))
    assert ex.value.kind == "replay"


@pytest.mark.asyncio
async def test_verify_rejects_expired(mock_mcp, monkeypatch) -> None:
    plan = {"ticker": "NVDA"}
    mint_out = await mint(
        ApprovalMintInput(
            action_plan=plan,
            user_id="u",
            ttl_seconds=30,
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
        )
    )
    import openclaw.skills.hitl._tokens as toks

    future = mint_out.expires_at.timestamp() + 60
    monkeypatch.setattr(toks._time, "time", lambda: future)
    with pytest.raises(HITLError) as ex:
        await verify(
            ApprovalVerifyInput(
                token=mint_out.token,
                action_plan=plan,
                principal_id="u",
                agent_id="a",
                session_id="s",
                correlation_id="c",
            )
        )
    assert ex.value.kind == "expired"
