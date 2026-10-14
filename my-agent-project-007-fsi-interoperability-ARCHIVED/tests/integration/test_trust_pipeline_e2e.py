"""
M6 Trust Pipeline — End-to-End Integration Tests.

Tests the full trust pipeline flow through the FastAPI app:
  Pre-call:  M1 verify → M2 authority → M4 MNPI filter request
  Forward:   MCP call to downstream server
  Post-call: M7 translate → M4 post-filter → Leakage scan → M10 audit

All downstream services (M1, M2/M4, M7, M10, MCP server) are mocked
via httpx MockTransport — no real network calls.

Test cases:
  1. Happy path — allowed request flows through all stages
  2. Denied request — M2 returns DENY, request blocked
  3. MNPI filtered — response has SSN stripped by M4
  4. Leakage scan blocks — response with MNPI keyword blocked
  5. Audit log written with correct provenance chain
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

# ── Package registration for dash-named directory ────────────────
# The conftest.py in src/m6-mcp-gateway/ registers the top-level package.
# We only need to ensure submodules are loaded if not already present.

_pkg_dir = Path(__file__).resolve().parents[2] / "src" / "m6-mcp-gateway"
_pkg_name = "m6_mcp_gateway"

# Ensure the package is registered (conftest may have done this already)
if _pkg_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg_name,
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg_name] = _mod
    _spec.loader.exec_module(_mod)

# Ensure submodules are importable — use the SAME package's search path
_existing_pkg = sys.modules[_pkg_name]
if not hasattr(_existing_pkg, "__path__"):
    _existing_pkg.__path__ = [str(_pkg_dir)]

for _submod_name in (
    "models", "leakage_scan", "resilience", "trust_pipeline", "mcp_proxy", "app",
):
    _full_name = f"{_pkg_name}.{_submod_name}"
    if _full_name not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _full_name,
            _pkg_dir / f"{_submod_name}.py",
            submodule_search_locations=[str(_pkg_dir)],
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        _sub_mod.__package__ = _pkg_name
        sys.modules[_full_name] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from m6_mcp_gateway import app as app_module
from m6_mcp_gateway.app import app
from m6_mcp_gateway.models import GatewayConfig
from m6_mcp_gateway.trust_pipeline import TrustPipeline
from m6_mcp_gateway.mcp_proxy import MCPProxy


# ── Mock Data ────────────────────────────────────────────────────

VALID_AID_CLAIMS = {
    "actor_type": "human",
    "display_name": "test.advisor",
    "firm_id": "test_firm",
    "archetype": "tier4_independent_ria",
    "role": "advisor",
    "jurisdiction": "US",
    "authority_scope": ["client.read", "portfolio.read"],
    "authority_excludes": [],
    "client_scope": ["C-12345"],
    "pod_id": None,
}

_audit_log_calls: list[dict[str, Any]] = []


def _reset_audit_log():
    _audit_log_calls.clear()


# ── Mock HTTP Transport ──────────────────────────────────────────


class TrustPipelineMockTransport(httpx.AsyncBaseTransport):
    """Routes all outbound REST calls to mock handlers."""

    def __init__(
        self,
        m1_valid: bool = True,
        m2_decision: str = "ALLOW",
        mcp_response: dict | None = None,
        m4_strip_fields: list[str] | None = None,
    ) -> None:
        self.m1_valid = m1_valid
        self.m2_decision = m2_decision
        self.mcp_response = mcp_response or {
            "content": [{"type": "text", "text": "Portfolio summary for client"}],
        }
        self.m4_strip_fields = m4_strip_fields or ["ssn", "dob"]

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body = json.loads(request.content) if request.content else {}

        if "/aid/verify" in url:
            if self.m1_valid:
                return httpx.Response(200, json={
                    "valid": True, "aid_id": "aid-001", "claims": VALID_AID_CLAIMS,
                })
            return httpx.Response(200, json={"valid": False, "reason": "Token expired"})

        if "/policy/authority" in url:
            return httpx.Response(200, json={
                "decision": self.m2_decision,
                "reason": "Authorized" if self.m2_decision == "ALLOW" else "Action not in scope",
                "rule_applied": "authority/main.rego:check",
                "wsp_section": "2.0",
            })

        if "/mnpi/filter" in url or "/policy/mnpi/filter" in url:
            payload = body.get("data_payload", {})
            filtered = {k: v for k, v in payload.items() if k not in self.m4_strip_fields}
            removed = [k for k in payload if k in self.m4_strip_fields]
            return httpx.Response(200, json={"filtered_payload": filtered, "fields_removed": removed})

        if "/translate" in url:
            return httpx.Response(200, json=body.get("data", {}))

        if "/audit/write" in url:
            _audit_log_calls.append(body)
            return httpx.Response(200, json={
                "canonical_id": "audit-e2e-001",
                "sha256_integrity": "a" * 64,
                "tier_results": [],
                "worm_record_id": "s3://worm/e2e-test",
            })

        if "/tools/call" in url:
            return httpx.Response(200, json=self.mcp_response)

        return httpx.Response(404, json={"error": "not found"})


# ── Setup: initialize app singletons (lifespan not triggered by ASGITransport) ──


def _setup_app(transport: TrustPipelineMockTransport):
    """
    Manually initialize the app's singletons and inject mock transport.
    ASGITransport does not trigger FastAPI lifespan, so we do it here.
    """
    config = GatewayConfig()
    pipeline = TrustPipeline(config)
    proxy = MCPProxy(config, redis_client=None)

    mock_client = httpx.AsyncClient(transport=transport)
    pipeline._client = mock_client
    proxy._client = mock_client

    app_module._config = config
    app_module._pipeline = pipeline
    app_module._proxy = proxy


# ═══════════════════════════════════════════════════════════════════
# E2E TEST CLASS
# ═══════════════════════════════════════════════════════════════════


class TestTrustPipelineE2E:
    """End-to-end integration tests for the full M6 trust pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_full_pipeline(self):
        """Allowed request flows through all stages with audit written."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(
            m1_valid=True, m2_decision="ALLOW",
            mcp_response={"content": [{"type": "text", "text": "Client portfolio balanced"}]},
        )
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "client.read",
                "arguments": {"client_id": "C-12345"},
                "trace_id": "e2e-trace-001",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"]
        assert data["trace_id"] == "e2e-trace-001"
        assert data["result"] is not None
        assert len(data["provenance_chain"]) >= 3

        assert len(_audit_log_calls) >= 1
        audit = _audit_log_calls[0]
        assert audit["decision"] == "allow"
        assert audit["action"] == "client.read"
        for entry in audit.get("provenance_chain", []):
            assert len(entry["hash"]) == 64

    @pytest.mark.asyncio
    async def test_m2_deny_blocks_request(self):
        """M2 DENY blocks at pre-call. Client gets 403 generic error (Rule 9)."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(m1_valid=True, m2_decision="DENY")
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "order.submit",
                "arguments": {},
                "trace_id": "e2e-trace-deny",
            })

        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Request denied"
        assert "authority" not in data["error"].lower()
        assert "m2" not in data["error"].lower()

    @pytest.mark.asyncio
    async def test_mnpi_filtered_ssn_stripped(self):
        """M4 post-filter strips SSN from response. Client never sees it."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(
            m1_valid=True, m2_decision="ALLOW",
            mcp_response={"name": "Henderson", "portfolio": "balanced", "account_status": "active"},
            m4_strip_fields=["ssn", "dob"],
        )
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "client.read",
                "arguments": {"client_id": "C-12345", "ssn": "123-45-6789"},
                "trace_id": "e2e-trace-mnpi",
            })

        assert response.status_code == 200
        result_str = json.dumps(response.json().get("result", {}))
        assert "123-45-6789" not in result_str

    @pytest.mark.asyncio
    async def test_leakage_scan_blocks_mnpi_keyword(self):
        """Leakage scan blocks response with MNPI keyword. Fail-closed (Rule 12)."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(
            m1_valid=True, m2_decision="ALLOW",
            mcp_response={"content": [{"type": "text", "text": "This contains material non-public information about the merger"}]},
            m4_strip_fields=[],
        )
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "client.read",
                "arguments": {"client_id": "C-12345"},
                "trace_id": "e2e-trace-leakage",
            })

        assert response.status_code == 403
        assert response.json()["error"] == "Request denied"
        assert len(_audit_log_calls) >= 1
        assert _audit_log_calls[0]["decision"] == "deny"

    @pytest.mark.asyncio
    async def test_audit_log_provenance_chain(self):
        """Audit log contains provenance chain with SHA-256 hashes per stage."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(
            m1_valid=True, m2_decision="ALLOW",
            mcp_response={"content": [{"type": "text", "text": "Clean response data"}]},
        )
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "portfolio.read",
                "arguments": {"client_id": "C-12345"},
                "trace_id": "e2e-trace-provenance",
            })

        assert response.status_code == 200
        assert len(_audit_log_calls) >= 1
        chain = _audit_log_calls[0].get("provenance_chain", [])
        assert len(chain) >= 3
        for entry in chain:
            assert "stage" in entry
            assert "module" in entry
            assert len(entry["hash"]) == 64
            assert "timestamp" in entry
        assert chain[0]["stage"] == "identity_verification"
        assert chain[0]["module"] == "m1"
        assert chain[1]["stage"] == "authority_check"
        assert chain[1]["module"] == "m2"

    @pytest.mark.asyncio
    async def test_m1_invalid_token_blocks_request(self):
        """M1 invalid token blocks at pre-call. Client gets 403."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(m1_valid=False)
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "expired-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "client.read",
                "arguments": {},
                "trace_id": "e2e-trace-m1-fail",
            })

        assert response.status_code == 403
        assert response.json()["error"] == "Request denied"

    @pytest.mark.asyncio
    async def test_leakage_scan_blocks_ssn_in_text(self):
        """Leakage scan blocks SSN in response text even if M4 missed it."""
        _reset_audit_log()
        transport = TrustPipelineMockTransport(
            m1_valid=True, m2_decision="ALLOW",
            mcp_response={"content": [{"type": "text", "text": "Client SSN: 987-65-4321 on file"}]},
            m4_strip_fields=[],
        )
        _setup_app(transport)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp/call", json={
                "aid_token": "valid-jwt-token",
                "server_url": "http://mock-mcp:8000",
                "tool_name": "client.read",
                "arguments": {"client_id": "C-12345"},
                "trace_id": "e2e-trace-ssn-leak",
            })

        assert response.status_code == 403
        assert response.json()["error"] == "Request denied"
