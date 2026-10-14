"""Tests for the shared MCP client + skill registry."""

from __future__ import annotations

import os

import pytest

from openclaw.skills import assert_registry_integrity, get_skill, list_skills
from openclaw.skills._mcp_client import MCPClient, MCPError


def test_registry_has_all_14_skills() -> None:
    skills = list_skills()
    assert len(skills) == 16
    required = {
        "publish_brief", "rag_retrieve", "financial_statement_analysis",
        "portfolio_analytics", "scenario_modeling", "suitability_check",
        "client_summary", "research_awareness", "compliance_screening",
        "compliance_sweep", "hitl", "dual_auth", "mulesoft_api", "audit_logging",
    }
    assert required.issubset(set(skills))


def test_registry_integrity_passes() -> None:
    assert_registry_integrity()


def test_get_skill_returns_module_with_run() -> None:
    mod = get_skill("publish_brief")
    assert hasattr(mod, "run")


def test_get_skill_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_skill("nonexistent_skill")


@pytest.mark.asyncio
async def test_mcp_client_mock_missing_handler_raises() -> None:
    client = MCPClient(mock=True)
    with pytest.raises(MCPError) as ex:
        await client.call("salesforce-crm", "nonexistent_tool", {})
    assert ex.value.retryable is False


@pytest.mark.asyncio
async def test_mcp_client_mock_registered_handler() -> None:
    client = MCPClient(mock=True)

    async def handler(args):
        return {"echo": args}

    client.mock_router.register("x", "t", handler)
    result = await client.call("x", "t", {"k": "v"})
    assert result == {"echo": {"k": "v"}}


def test_real_transport_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        MCPClient(mock=False)


@pytest.mark.asyncio
async def test_mcp_list_tools_mock() -> None:
    client = MCPClient(mock=True)

    async def h(args):
        return {}

    client.mock_router.register("srv", "tool_a", h)
    client.mock_router.register("srv", "tool_b", h)
    tools = await client.list_tools("srv")
    names = {t["name"] for t in tools}
    assert names == {"tool_a", "tool_b"}
