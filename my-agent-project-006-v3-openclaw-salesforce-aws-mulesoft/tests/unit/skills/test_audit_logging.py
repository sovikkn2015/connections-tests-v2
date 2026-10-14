"""Tests for audit_logging skill."""

from __future__ import annotations

import json

import pytest

from openclaw.skills.audit_logging import Action, AuditInput, hash_token, run


@pytest.mark.asyncio
async def test_audit_minimum_write(mock_mcp) -> None:
    out = await run(
        AuditInput(
            action=Action.RESEARCH_PUBLISHED,
            principal_id="u_sarah",
            agent_id="research_orchestrator",
            session_id="sess_1",
            correlation_id="corr_1",
            research_brief_id="a0X_brief_001",
        )
    )
    assert out.audit_row_id.startswith("AUDIT_")
    assert out.action is Action.RESEARCH_PUBLISHED


@pytest.mark.asyncio
async def test_audit_hashes_approval_token(mock_mcp) -> None:
    await run(
        AuditInput(
            action=Action.HITL_APPROVED,
            principal_id="u_rm",
            agent_id="action_specialist",
            session_id="sess",
            correlation_id="corr",
            approval_token="raw_secret_token_abc123",
        )
    )
    last_call = mock_mcp.mock_router.call_log[-1]
    record = last_call["arguments"]["record"]
    assert record["Approval_Token_Hash__c"].startswith("sha256:")
    assert "raw_secret_token_abc123" not in record["Approval_Token_Hash__c"]


def test_hash_token_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert hash_token("") == ""


@pytest.mark.asyncio
async def test_audit_scrubs_mnpi_from_payload(mock_mcp) -> None:
    out = await run(
        AuditInput(
            action=Action.ADVISORY_QUERY,
            principal_id="u",
            agent_id="a",
            session_id="s",
            correlation_id="c",
            payload={"note": "client sold 100 shares worth $1,000,000"},
        )
    )
    last_call = mock_mcp.mock_router.call_log[-1]
    scrubbed_raw = last_call["arguments"]["record"]["Payload__c"]
    # Payload__c is a JSON-serialized string so Salesforce LongTextArea can
    # accept it (see actions.py). Parse back to inspect the scrubbed content.
    scrubbed = json.loads(scrubbed_raw) if isinstance(scrubbed_raw, str) else scrubbed_raw
    assert "$1,000,000" not in scrubbed["note"]
    assert "[$REDACTED]" in scrubbed["note"]
    assert "[SHARES_REDACTED]" in scrubbed["note"]
    assert out.mnpi_redactions >= 2
