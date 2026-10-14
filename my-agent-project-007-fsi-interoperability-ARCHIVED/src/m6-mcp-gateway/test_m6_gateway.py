"""
M6 Trust-Aware MCP Gateway — Integration Tests.

Tests cover:
  1. Full trust pipeline: request → M1 → M2 → M4 → forward → M4 → scan → M10 → response
  2. Pre-call DENY when M1 verification fails
  3. Pre-call DENY when M2 authority denies
  4. Post-call block when leakage scan detects MNPI
  5. Circuit breaker opens after 5 failures
  6. Rate limiter blocks after limit exceeded
  7. Provenance chain has correct number of stages
  8. Generic error to client, full error in logs
  9. Fail-closed when M10 audit write fails

All module dependencies (M1, M2, M4, M7, M10) are mocked via httpx
transport — no cross-module imports.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

import importlib
import sys
from pathlib import Path

# Register the dash-named directory as a valid Python package
_pkg_dir = Path(__file__).parent
_pkg_name = "m6_mcp_gateway"
if _pkg_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg_name,
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg_name] = _mod
    _spec.loader.exec_module(_mod)

# Now register submodules so relative imports within the package work
for _submod_name in ("models", "leakage_scan", "resilience", "trust_pipeline", "mcp_proxy", "app"):
    _full_name = f"{_pkg_name}.{_submod_name}"
    if _full_name not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _full_name,
            _pkg_dir / f"{_submod_name}.py",
            submodule_search_locations=[str(_pkg_dir)],
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        sys.modules[_full_name] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from m6_mcp_gateway.leakage_scan import scan_output, _scan_layer_a, _extract_text
from m6_mcp_gateway.models import (
    CircuitState,
    GatewayConfig,
    GatewayError,
    LeakageScanResult,
    MCPRequest,
    MCPResponse,
    PipelineStage,
    ProvenanceEntry,
    ServerConfig,
    TrustPipelineResult,
)
from m6_mcp_gateway.resilience import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitOpenError,
    RateLimiter,
    RateLimitExceededError,
    TransientError,
    NonTransientError,
)
from m6_mcp_gateway.trust_pipeline import TrustPipeline, _hash_payload


# ── Fixtures ─────────────────────────────────────────────────────

MOCK_AID_CLAIMS = {
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


def _mock_m1_success() -> dict:
    return {"valid": True, "aid_id": "aid-001", "claims": MOCK_AID_CLAIMS}


def _mock_m1_failure() -> dict:
    return {"valid": False, "reason": "Token expired"}


def _mock_m2_allow() -> dict:
    return {
        "decision": "ALLOW",
        "reason": "Authorized",
        "rule_applied": "authority/main.rego:check",
        "wsp_section": "WSP-3.1",
    }


def _mock_m2_deny() -> dict:
    return {
        "decision": "DENY",
        "reason": "Action not in authority_scope",
        "rule_applied": "authority/main.rego:check",
        "wsp_section": "WSP-3.1",
    }


def _mock_m4_filter(payload: dict) -> dict:
    """Simulate M4 MNPI filter — strips ssn and dob fields."""
    filtered = {k: v for k, v in payload.items() if k not in ("ssn", "dob")}
    return {
        "filtered_payload": filtered,
        "fields_removed": [k for k in payload if k in ("ssn", "dob")],
    }


def _mock_m7_translate(data: Any) -> dict:
    return data if isinstance(data, dict) else {"result": data}


def _mock_m10_audit() -> dict:
    return {
        "canonical_id": "audit-001",
        "sha256_integrity": "a" * 64,
        "tier_results": [],
        "worm_record_id": "s3://worm/test",
    }


def _mock_mcp_response() -> dict:
    return {"content": [{"type": "text", "text": "Client portfolio summary"}]}


def _mock_mcp_response_with_mnpi() -> dict:
    return {
        "content": [{"type": "text", "text": "SSN: 123-45-6789, DOB: 01/15/1980"}],
    }


# ── Helper: mock httpx transport ─────────────────────────────────


class MockTransport(httpx.AsyncBaseTransport):
    """Mock transport that routes requests to handler functions."""

    def __init__(self, handlers: dict[str, Any]) -> None:
        self._handlers = handlers

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for pattern, handler in self._handlers.items():
            if pattern in url:
                if callable(handler):
                    body = json.loads(request.content) if request.content else {}
                    result = handler(body) if handler.__code__.co_argcount > 0 else handler()
                else:
                    result = handler
                return httpx.Response(200, json=result)
        return httpx.Response(404, json={"error": "not found"})


class MockTransportWithFailure(httpx.AsyncBaseTransport):
    """Mock transport that returns errors for specific patterns."""

    def __init__(self, fail_pattern: str, status_code: int = 500) -> None:
        self._fail_pattern = fail_pattern
        self._status_code = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if self._fail_pattern in url:
            return httpx.Response(self._status_code, json={"error": "fail"})
        # Default success for other endpoints
        if "/aid/verify" in url:
            return httpx.Response(200, json=_mock_m1_success())
        if "/policy/authority" in url:
            return httpx.Response(200, json=_mock_m2_allow())
        if "/mnpi/filter" in url:
            body = json.loads(request.content) if request.content else {}
            payload = body.get("data_payload", {})
            return httpx.Response(200, json=_mock_m4_filter(payload))
        if "/translate" in url:
            body = json.loads(request.content) if request.content else {}
            return httpx.Response(200, json=body.get("data", {}))
        if "/audit/write" in url:
            return httpx.Response(200, json=_mock_m10_audit())
        return httpx.Response(200, json={})


# ═══════════════════════════════════════════════════════════════════
# TEST 1: Leakage Scan — Layer A regex detection
# ═══════════════════════════════════════════════════════════════════


class TestLeakageScan:
    """Tests for MNPI leakage scan (Rule 10)."""

    def test_clean_data_passes(self):
        """Clean data with no MNPI patterns should pass."""
        result = scan_output({"name": "Henderson", "portfolio": "balanced"})
        assert result.passed is True
        assert len(result.layers) == 3
        assert result.layers[0].layer.value == "layer_a_regex"
        assert result.layers[0].passed is True

    def test_ssn_detected(self):
        """SSN pattern should be detected and blocked."""
        result = scan_output({"text": "Client SSN is 123-45-6789"})
        assert result.passed is False
        assert result.layers[0].passed is False
        assert any("ssn" in d for d in result.layers[0].detections)

    def test_dob_detected(self):
        """Date of birth pattern should be detected."""
        result = scan_output({"text": "DOB: 01/15/1980"})
        assert result.passed is False

    def test_dob_iso_detected(self):
        """ISO date of birth pattern should be detected."""
        result = scan_output({"text": "Born 1985-03-22"})
        assert result.passed is False

    def test_account_number_detected(self):
        """Long digit sequences (account numbers) should be detected."""
        result = scan_output({"text": "Account 12345678901234"})
        assert result.passed is False

    def test_mnpi_keyword_detected(self):
        """MNPI keywords should be detected."""
        result = scan_output({"text": "This is material non-public information"})
        assert result.passed is False

    def test_insider_trading_keyword(self):
        """Insider trading keyword should be detected."""
        result = scan_output({"text": "Possible insider trading activity"})
        assert result.passed is False

    def test_layer_b_stub_passes(self):
        """Layer B (NER) stub should return pass with not_implemented."""
        result = scan_output({"text": "clean data"})
        layer_b = result.layers[1]
        assert layer_b.passed is True
        assert layer_b.not_implemented is True

    def test_layer_c_stub_passes(self):
        """Layer C (LLM) stub should return pass with not_implemented."""
        result = scan_output({"text": "clean data"})
        layer_c = result.layers[2]
        assert layer_c.passed is True
        assert layer_c.not_implemented is True

    def test_nested_data_extraction(self):
        """Should extract text from nested dicts and lists."""
        data = {
            "level1": {
                "level2": [
                    {"text": "SSN: 123-45-6789"},
                    "more data",
                ],
            },
        }
        result = scan_output(data)
        assert result.passed is False

    def test_layer_a_latency_under_10ms(self):
        """Layer A regex should complete in under 10ms."""
        text = "Some normal text " * 1000  # ~18KB of text
        result = _scan_layer_a(text)
        assert result.latency_ms < 10.0


# ═══════════════════════════════════════════════════════════════════
# TEST 2: Circuit Breaker
# ═══════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """Tests for circuit breaker (Rule 4)."""

    @pytest.mark.asyncio
    async def test_starts_closed(self):
        cb = CircuitBreaker("http://test:8000", failure_threshold=5)
        assert cb.state == CircuitState.closed
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        """Circuit opens after 5 consecutive failures."""
        cb = CircuitBreaker("http://test:8000", failure_threshold=5)
        for _ in range(5):
            await cb.record_failure()
        assert cb.state == CircuitState.open
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_stays_closed_below_threshold(self):
        """Circuit stays closed with fewer than threshold failures."""
        cb = CircuitBreaker("http://test:8000", failure_threshold=5)
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == CircuitState.closed
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_success_resets_count(self):
        """Success resets failure count."""
        cb = CircuitBreaker("http://test:8000", failure_threshold=5)
        for _ in range(4):
            await cb.record_failure()
        await cb.record_success()
        # Should need 5 more failures to open
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == CircuitState.closed

    @pytest.mark.asyncio
    async def test_half_open_after_recovery(self):
        """Circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, recovery_timeout=0.01,
        )
        for _ in range(5):
            await cb.record_failure()
        assert cb.state == CircuitState.open
        await asyncio.sleep(0.02)
        assert await cb.can_execute() is True
        assert cb.state == CircuitState.half_open

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        """Success in half-open state closes the circuit."""
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, recovery_timeout=0.01,
        )
        for _ in range(5):
            await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.can_execute()  # transition to half-open
        await cb.record_success()
        assert cb.state == CircuitState.closed

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        """Failure in half-open state re-opens the circuit."""
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, recovery_timeout=0.01,
        )
        for _ in range(5):
            await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.can_execute()  # transition to half-open
        await cb.record_failure()
        assert cb.state == CircuitState.open

    @pytest.mark.asyncio
    async def test_registry_creates_per_server(self):
        """Registry creates separate circuit breakers per server."""
        registry = CircuitBreakerRegistry()
        cb1 = await registry.get("http://server1:8000")
        cb2 = await registry.get("http://server2:8000")
        assert cb1 is not cb2
        # Same server returns same instance
        cb1_again = await registry.get("http://server1:8000")
        assert cb1 is cb1_again


# ═══════════════════════════════════════════════════════════════════
# TEST 3: Rate Limiter
# ═══════════════════════════════════════════════════════════════════


class TestRateLimiter:
    """Tests for rate limiter (Rule 7)."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        rl = RateLimiter()
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_blocks_after_limit(self):
        """Blocks requests after rate limit exceeded."""
        rl = RateLimiter()
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is False
        assert retry_after is not None
        assert retry_after >= 1

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        """Different users have independent rate limits."""
        rl = RateLimiter()
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
        # user2 should still be allowed
        allowed, _ = await rl.check_rate_limit(
            "user2", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_different_tools_independent(self):
        """Different tools have independent rate limits."""
        rl = RateLimiter()
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
        # tool2 should still be allowed
        allowed, _ = await rl.check_rate_limit(
            "user1", "tool2", max_requests=5, window_seconds=60,
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_window_slides(self):
        """Requests expire after window slides."""
        rl = RateLimiter()
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=0.01,
            )
        await asyncio.sleep(0.02)
        allowed, _ = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=0.01,
        )
        assert allowed is True


# ═══════════════════════════════════════════════════════════════════
# TEST 4: Provenance Chain
# ═══════════════════════════════════════════════════════════════════


class TestProvenanceChain:
    """Tests for provenance chain (Rule 11)."""

    def test_hash_deterministic(self):
        """Same payload produces same hash."""
        h1 = _hash_payload({"a": 1, "b": 2})
        h2 = _hash_payload({"b": 2, "a": 1})  # different order
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_different_payloads(self):
        """Different payloads produce different hashes."""
        h1 = _hash_payload({"a": 1})
        h2 = _hash_payload({"a": 2})
        assert h1 != h2

    def test_provenance_entry_creation(self):
        """ProvenanceEntry computes valid SHA-256 hash."""
        h = ProvenanceEntry.compute_hash({"test": "data"})
        assert len(h) == 64
        assert re.match(r"^[a-f0-9]{64}$", h)

    def test_provenance_entry_model(self):
        """ProvenanceEntry validates correctly."""
        entry = ProvenanceEntry(
            stage=PipelineStage.identity_verification,
            module="m1",
            hash="a" * 64,
        )
        assert entry.stage == PipelineStage.identity_verification
        assert entry.module == "m1"


# ═══════════════════════════════════════════════════════════════════
# TEST 5: Trust Pipeline (unit tests with mocked HTTP)
# ═══════════════════════════════════════════════════════════════════


class TestTrustPipeline:
    """Tests for pre-call and post-call trust pipeline."""

    @pytest.mark.asyncio
    async def test_pre_call_success(self):
        """Full pre-call pipeline succeeds with valid M1/M2/M4 responses."""
        config = GatewayConfig(
            m1_base_url="http://mock-m1:8000",
            m2_base_url="http://mock-m2:8000",
            m4_base_url="http://mock-m4:8000",
        )
        pipeline = TrustPipeline(config)
        transport = MockTransport({
            "/aid/verify": _mock_m1_success,
            "/policy/authority": _mock_m2_allow,
            "/mnpi/filter": lambda body: _mock_m4_filter(body.get("data_payload", {})),
        })
        pipeline._client = httpx.AsyncClient(transport=transport)

        result = await pipeline.pre_call_pipeline(
            aid_token="valid-jwt-token",
            tool_name="client.read",
            arguments={"client_id": "C-12345"},
            server_url="http://mcp-server:8000",
            trace_id="trace-001",
        )

        assert result.passed is True
        assert result.verified_claims is not None
        assert result.filtered_arguments is not None
        assert len(result.provenance_chain) == 3  # M1 + M2 + M4
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_pre_call_m1_deny(self):
        """Pre-call pipeline fails when M1 denies (invalid token)."""
        config = GatewayConfig(m1_base_url="http://mock-m1:8000")
        pipeline = TrustPipeline(config)
        transport = MockTransport({
            "/aid/verify": _mock_m1_failure,
        })
        pipeline._client = httpx.AsyncClient(transport=transport)

        result = await pipeline.pre_call_pipeline(
            aid_token="expired-token",
            tool_name="client.read",
            arguments={},
            server_url="http://mcp-server:8000",
            trace_id="trace-002",
        )

        assert result.passed is False
        assert result.stage_failed == PipelineStage.identity_verification
        assert "expired" in (result.reason or "").lower() or "failed" in (result.reason or "").lower()
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_pre_call_m2_deny(self):
        """Pre-call pipeline fails when M2 denies (unauthorized action)."""
        config = GatewayConfig(
            m1_base_url="http://mock-m1:8000",
            m2_base_url="http://mock-m2:8000",
        )
        pipeline = TrustPipeline(config)
        transport = MockTransport({
            "/aid/verify": _mock_m1_success,
            "/policy/authority": _mock_m2_deny,
        })
        pipeline._client = httpx.AsyncClient(transport=transport)

        result = await pipeline.pre_call_pipeline(
            aid_token="valid-jwt-token",
            tool_name="order.submit",
            arguments={},
            server_url="http://mcp-server:8000",
            trace_id="trace-003",
        )

        assert result.passed is False
        assert result.stage_failed == PipelineStage.authority_check
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_pre_call_provenance_chain_stages(self):
        """Pre-call pipeline produces 3 provenance entries on success."""
        config = GatewayConfig(
            m1_base_url="http://mock-m1:8000",
            m2_base_url="http://mock-m2:8000",
            m4_base_url="http://mock-m4:8000",
        )
        pipeline = TrustPipeline(config)
        transport = MockTransport({
            "/aid/verify": _mock_m1_success,
            "/policy/authority": _mock_m2_allow,
            "/mnpi/filter": lambda body: _mock_m4_filter(body.get("data_payload", {})),
        })
        pipeline._client = httpx.AsyncClient(transport=transport)

        result = await pipeline.pre_call_pipeline(
            aid_token="valid-jwt-token",
            tool_name="client.read",
            arguments={"client_id": "C-12345"},
            server_url="http://mcp-server:8000",
            trace_id="trace-004",
        )

        assert result.passed is True
        chain = result.provenance_chain
        assert len(chain) == 3
        assert chain[0].stage == PipelineStage.identity_verification
        assert chain[0].module == "m1"
        assert chain[1].stage == PipelineStage.authority_check
        assert chain[1].module == "m2"
        assert chain[2].stage == PipelineStage.mnpi_filter_request
        assert chain[2].module == "m4"
        # All hashes are valid SHA-256
        for entry in chain:
            assert re.match(r"^[a-f0-9]{64}$", entry.hash)
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_post_call_leakage_blocks(self):
        """Post-call pipeline blocks response when leakage scan detects MNPI."""
        config = GatewayConfig(
            m4_base_url="http://mock-m4:8000",
            m7_base_url="http://mock-m7:8000",
            m10_base_url="http://mock-m10:8000",
        )
        pipeline = TrustPipeline(config)
        transport = MockTransport({
            "/mnpi/filter": lambda body: {
                "filtered_payload": body.get("data_payload", {}),
                "fields_removed": [],
            },
            "/translate": lambda body: body.get("data", {}),
            "/audit/write": _mock_m10_audit,
        })
        pipeline._client = httpx.AsyncClient(transport=transport)

        # Response contains SSN — should be blocked by leakage scan
        passed, response, chain, reason = await pipeline.post_call_pipeline(
            raw_response=_mock_mcp_response_with_mnpi(),
            claims=MOCK_AID_CLAIMS,
            tool_name="client.read",
            server_url="http://mcp-server:8000",
            trace_id="trace-005",
            provenance_chain=[],
            request_arguments={"client_id": "C-12345"},
        )

        assert passed is False
        assert response is None
        assert "leakage" in (reason or "").lower() or "mnpi" in (reason or "").lower()
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_post_call_audit_failure_blocks(self):
        """Post-call pipeline blocks response when M10 audit write fails."""
        config = GatewayConfig(
            m4_base_url="http://mock-m4:8000",
            m7_base_url="http://mock-m7:8000",
            m10_base_url="http://mock-m10:8000",
        )
        pipeline = TrustPipeline(config)
        transport = MockTransportWithFailure("/audit/write", status_code=500)
        pipeline._client = httpx.AsyncClient(transport=transport)

        passed, response, chain, reason = await pipeline.post_call_pipeline(
            raw_response=_mock_mcp_response(),
            claims=MOCK_AID_CLAIMS,
            tool_name="client.read",
            server_url="http://mcp-server:8000",
            trace_id="trace-006",
            provenance_chain=[],
            request_arguments={"client_id": "C-12345"},
        )

        assert passed is False
        assert response is None
        assert "audit" in (reason or "").lower()
        await pipeline.close()


# ═══════════════════════════════════════════════════════════════════
# TEST 6: Models Validation
# ═══════════════════════════════════════════════════════════════════


class TestModels:
    """Tests for Pydantic model validation."""

    def test_mcp_request_requires_aid_token(self):
        """MCPRequest requires non-empty aid_token."""
        with pytest.raises(Exception):
            MCPRequest(aid_token="", server_url="http://test", tool_name="test")

    def test_mcp_request_valid(self):
        req = MCPRequest(
            aid_token="jwt-token",
            server_url="http://mcp:8000",
            tool_name="client.read",
            arguments={"id": "123"},
        )
        assert req.tool_name == "client.read"
        assert req.request_id  # auto-generated
        assert req.trace_id  # auto-generated

    def test_gateway_error_generic(self):
        """GatewayError provides generic message (Rule 9)."""
        err = GatewayError()
        assert err.error == "Request denied"
        # Should NOT contain internal details
        assert "stack" not in err.error.lower()
        assert "module" not in err.error.lower()

    def test_server_config_defaults(self):
        """ServerConfig has correct defaults per rules."""
        sc = ServerConfig(server_url="http://test:8000")
        assert sc.timeout_seconds == 30.0  # Rule 6
        assert sc.max_retries == 3  # Rule 5
        assert sc.circuit_breaker_threshold == 5  # Rule 4
        assert sc.circuit_breaker_recovery_seconds == 30.0  # Rule 4

    def test_gateway_config_get_server_config(self):
        """GatewayConfig returns per-server config or defaults."""
        custom = ServerConfig(server_url="http://custom:8000", timeout_seconds=10.0)
        config = GatewayConfig(servers={"http://custom:8000": custom})
        assert config.get_server_config("http://custom:8000").timeout_seconds == 10.0
        assert config.get_server_config("http://other:8000").timeout_seconds == 30.0

    def test_trust_pipeline_result_fail(self):
        """TrustPipelineResult correctly represents failure."""
        result = TrustPipelineResult(
            passed=False,
            stage_failed=PipelineStage.authority_check,
            reason="Not authorized",
        )
        assert result.passed is False
        assert result.stage_failed == PipelineStage.authority_check


# ═══════════════════════════════════════════════════════════════════
# TEST 7: Error Handling — Generic Errors to Client (Rule 9)
# ═══════════════════════════════════════════════════════════════════


class TestGenericErrors:
    """Verify clients receive generic errors, never internal details."""

    def test_gateway_error_no_internal_details(self):
        err = GatewayError(error="Service unavailable", request_id="req-001")
        dumped = err.model_dump()
        # Must not contain module names, stack traces, or vendor details
        json_str = json.dumps(dumped)
        assert "traceback" not in json_str.lower()
        assert "opa" not in json_str.lower()

    def test_rate_limit_error_has_retry_after(self):
        err = GatewayError(
            error="Rate limit exceeded",
            request_id="req-002",
            retry_after=30,
        )
        assert err.retry_after == 30


# ═══════════════════════════════════════════════════════════════════
# TEST 8: M7 Translation Failure Is Fail-Closed (BLOCKER 4)
# ═══════════════════════════════════════════════════════════════════


class TestM7FailClosed:
    """Verify M7 translation failure blocks response (Rule 12)."""

    @pytest.mark.asyncio
    async def test_post_call_m7_failure_returns_denied(self):
        """When M7 translation raises, post_call_pipeline returns passed=False."""
        config = GatewayConfig(
            m4_base_url="http://mock-m4:8000",
            m7_base_url="http://mock-m7:8000",
            m10_base_url="http://mock-m10:8000",
        )
        pipeline = TrustPipeline(config)
        # M7 /translate returns 500 → raises on raise_for_status()
        transport = MockTransportWithFailure("/translate", status_code=500)
        pipeline._client = httpx.AsyncClient(transport=transport)

        passed, response, chain, reason = await pipeline.post_call_pipeline(
            raw_response=_mock_mcp_response(),
            claims=MOCK_AID_CLAIMS,
            tool_name="client.read",
            server_url="http://mcp-server:8000",
            trace_id="trace-m7-fail",
            provenance_chain=[],
            request_arguments={"client_id": "C-12345"},
        )

        assert passed is False, "M7 failure must be fail-closed (Rule 12)"
        assert response is None
        assert reason is not None
        assert "translation failed" in reason.lower()
        await pipeline.close()

    @pytest.mark.asyncio
    async def test_post_call_m7_connection_error_returns_denied(self):
        """When M7 is unreachable, post_call_pipeline returns passed=False."""
        config = GatewayConfig(
            m4_base_url="http://mock-m4:8000",
            m7_base_url="http://unreachable-m7:8000",
            m10_base_url="http://mock-m10:8000",
        )
        pipeline = TrustPipeline(config)

        # Use a transport that raises ConnectionError for /translate
        class M7ConnectionErrorTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                url = str(request.url)
                if "/translate" in url:
                    raise httpx.ConnectError("M7 unreachable")
                if "/mnpi/filter" in url:
                    body = json.loads(request.content) if request.content else {}
                    payload = body.get("data_payload", {})
                    return httpx.Response(200, json=_mock_m4_filter(payload))
                if "/audit/write" in url:
                    return httpx.Response(200, json=_mock_m10_audit())
                return httpx.Response(200, json={})

        pipeline._client = httpx.AsyncClient(transport=M7ConnectionErrorTransport())

        passed, response, chain, reason = await pipeline.post_call_pipeline(
            raw_response=_mock_mcp_response(),
            claims=MOCK_AID_CLAIMS,
            tool_name="client.read",
            server_url="http://mcp-server:8000",
            trace_id="trace-m7-conn-fail",
            provenance_chain=[],
            request_arguments={"client_id": "C-12345"},
        )

        assert passed is False, "M7 connection failure must be fail-closed (Rule 12)"
        assert response is None
        assert reason is not None
        assert "translation failed" in reason.lower()
        await pipeline.close()
