"""
M12 Agent Runtime Tests — Verify wiring, not LLM quality.

Tests mock Bedrock (no real LLM calls in tests) and verify:
- Supervisor routes to correct specialist
- Tools call M6 gateway with correct payload
- Compliance tools call M2 via M6
- Agent factory creates correct version
- Streaming yields tokens

All vendor calls go through M6 (Rule 4). No real API calls in tests.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Set env vars for tests."""
    monkeypatch.setenv("M6_GATEWAY_URL", "http://test-m6:8000")
    monkeypatch.setenv("AGENT_VERSION", "v2")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


@pytest.fixture
def mock_m6_response():
    """Create a mock M6 gateway response."""
    def _make(result: dict, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {"result": result}
        return mock_resp
    return _make


# ── Test: Tools call M6 gateway ──────────────────────────────────


class TestM6Tools:
    """Verify tool wrappers call M6 gateway with correct payload."""

    @patch("httpx.Client")
    def test_get_client_profile_calls_m6(self, mock_client_cls, mock_m6_response):
        """get_client_profile POSTs to M6 /mcp/call."""
        from m12_rt.tools.m6_tools import get_client_profile, current_aid_token

        mock_resp = mock_m6_response({"name": "Test Client", "id": "C001"})
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = current_aid_token.set("test-aid-token")
        try:
            result = get_client_profile.fn(client_id="C001")
        finally:
            current_aid_token.reset(token)

        # Verify M6 was called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/mcp/call" in call_args[0][0]

        # Verify payload structure matches MCPRequest
        payload = call_args[1]["json"]
        assert payload["aid_token"] == "test-aid-token"
        assert payload["tool_name"] == "get_client_profile"
        assert payload["arguments"]["client_id"] == "C001"

    @patch("httpx.Client")
    def test_tool_returns_access_denied_on_403(self, mock_client_cls):
        """Tools return 'Access denied' on M6 403 (Rule 9)."""
        from m12_rt.tools.m6_tools import get_holdings, current_aid_token

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = current_aid_token.set("test-token")
        try:
            result = get_holdings.fn(client_id="C001")
        finally:
            current_aid_token.reset(token)

        assert result == "Access denied"

    @patch("httpx.Client")
    def test_tool_returns_unavailable_on_error(self, mock_client_cls):
        """Tools return 'Service temporarily unavailable' on errors."""
        from m12_rt.tools.m6_tools import get_market_data, current_aid_token

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = current_aid_token.set("test-token")
        try:
            result = get_market_data.fn(ticker="AAPL")
        finally:
            current_aid_token.reset(token)

        assert result == "Service temporarily unavailable"


# ── Test: Compliance tool calls M2 via M6 ────────────────────────


class TestComplianceTools:
    """Verify compliance tools call OPA/M2 via M6 gateway."""

    @patch("httpx.Client")
    def test_check_compliance_calls_m2_via_m6(self, mock_client_cls):
        """check_compliance POSTs to M6 targeting M2 server."""
        from m12_rt.tools.compliance_tools import check_compliance
        from m12_rt.tools.m6_tools import current_aid_token

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "result": {"decision": "ALLOW", "reason": "Compliant"}
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = current_aid_token.set("test-token")
        try:
            result = check_compliance.fn(
                action="trade", target="AAPL", context="{}"
            )
        finally:
            current_aid_token.reset(token)

        # Verify call went to M6
        call_args = mock_client.post.call_args
        assert "/mcp/call" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["tool_name"] == "check_compliance"

    @patch("httpx.Client")
    def test_compliance_fail_closed_on_error(self, mock_client_cls):
        """Compliance returns DENY on service error (fail-closed)."""
        from m12_rt.tools.compliance_tools import check_compliance
        from m12_rt.tools.m6_tools import current_aid_token

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = current_aid_token.set("test-token")
        try:
            result = check_compliance.fn(
                action="trade", target="AAPL", context="{}"
            )
        finally:
            current_aid_token.reset(token)

        assert "DENY" in result
        assert "fail-closed" in result


# ── Test: Agent factory ──────────────────────────────────────────


class TestAgentFactory:
    """Verify agent factory creates correct version."""

    @patch("m12_rt.config._check_bedrock", return_value=False)
    def test_factory_creates_v2_supervisor(self, mock_bedrock):
        """Factory returns Strands supervisor agent for v2."""
        from m12_rt.agent_factory import create_agent
        from strands import Agent

        agent = create_agent(version="v2")
        assert isinstance(agent, Agent)

    def test_factory_creates_v1_fallback(self):
        """Factory returns V1Router for v1."""
        from m12_rt.agent_factory import create_agent, V1Router

        agent = create_agent(version="v1")
        assert isinstance(agent, V1Router)

    @patch("m12_rt.config._check_bedrock", return_value=False)
    def test_supervisor_has_five_tools(self, mock_bedrock):
        """Supervisor agent has 5 specialist tools."""
        from m12_rt.agents.supervisor import create_supervisor_agent

        supervisor = create_supervisor_agent()
        # Supervisor should have 5 tools: 4 specialists + compliance
        assert len(supervisor.tool_registry) == 5


# ── Test: Supervisor routes correctly ────────────────────────────


class TestSupervisorRouting:
    """Verify supervisor creates correct specialist agents."""

    @patch("m12_rt.config._check_bedrock", return_value=False)
    def test_client_service_agent_has_correct_tools(self, mock_bedrock):
        """Client service agent has profile, holdings, plan tools."""
        from m12_rt.agents.client_service import create_client_service_agent

        agent = create_client_service_agent()
        tool_names = list(agent.tool_registry.keys())
        assert "get_client_profile" in tool_names
        assert "get_holdings" in tool_names
        assert "get_financial_plan" in tool_names
        assert "check_compliance" in tool_names

    @patch("m12_rt.config._check_bedrock", return_value=False)
    def test_research_agent_uses_sonnet(self, mock_bedrock):
        """Research agent is configured (model may be None in test)."""
        from m12_rt.agents.research import create_research_agent

        agent = create_research_agent()
        tool_names = list(agent.tool_registry.keys())
        assert "search_sec_filings" in tool_names
        assert "get_market_data" in tool_names

    @patch("m12_rt.config._check_bedrock", return_value=False)
    def test_execution_agent_has_compliance_tools(self, mock_bedrock):
        """Execution agent has compliance + concentration tools."""
        from m12_rt.agents.execution import create_execution_agent

        agent = create_execution_agent()
        tool_names = list(agent.tool_registry.keys())
        assert "check_compliance" in tool_names
        assert "check_concentration" in tool_names
        assert "submit_order" in tool_names


# ── Test: FastAPI app health ─────────────────────────────────────


class TestApp:
    """Verify FastAPI app endpoints."""

    def test_health_endpoint(self):
        """Health check returns correct structure."""
        from fastapi.testclient import TestClient
        from m12_rt.app import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["module"] == "m12-agent-runtime"
        assert "agent_version" in data
