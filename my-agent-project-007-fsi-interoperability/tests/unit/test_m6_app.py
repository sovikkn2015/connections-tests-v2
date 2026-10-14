"""
M6 Trust-Aware MCP Gateway -- FastAPI REST surface unit tests (v0.3.0).

Covers the four wire routes exposed by ``m6_mcp_gateway.app``:

    GET  /health
    GET  /adapters
    GET  /gateway/reasons
    POST /gateway/call

Pattern: the in-process ``TrustAwareGateway`` is swapped for a
deterministic ``_FakeGateway`` that the test wires via ``create_app``,
so every assertion is about the HTTP shim (routing, body parsing,
reason-to-status mapping, middleware redaction) rather than the trust
pipeline itself. The pipeline has its own coverage in
``test_m6_mcp_gateway.py``.

Why these tests exist:
    * M8 pods bootstrap from ``/adapters`` -- the shape must be stable.
    * ``/gateway/reasons`` is the authoritative vocab; drift here would
      silently break M8's ``_call_with_branching`` reason mapping.
    * ``/gateway/call`` is the only surface through which vendor calls
      leave the platform -- error-to-status mapping is a production
      contract, not an implementation detail.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from m6_mcp_gateway import (
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    VALID_GATEWAY_REASONS,
)
from m6_mcp_gateway.app import AdapterRegistry, create_app


# =============================================================================
# Fakes
# =============================================================================


class _FakeGateway:
    """Test double for ``TrustAwareGateway``.

    Either returns the seeded ``response`` from ``call(...)`` or raises
    the seeded ``error``. Records the request that was dispatched so
    tests can assert wire -> dataclass round-tripping.
    """

    def __init__(
        self,
        *,
        response: Optional[GatewayResponse] = None,
        error: Optional[GatewayError] = None,
        health_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        self.response = response
        self.error = error
        self.health_payload = health_payload or {"status": "ok"}
        self.seen_requests: list[GatewayRequest] = []

    def call(self, request: GatewayRequest) -> GatewayResponse:
        self.seen_requests.append(request)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        raise AssertionError("no response or error seeded on _FakeGateway")

    def health(self) -> dict[str, Any]:
        return self.health_payload


class _FakeAdapter:
    """Minimal VendorAdapter-shaped test double.

    GatewayRequest.__post_init__ only requires ``.name`` (str) and
    ``.call`` (callable) to pass validation.
    """

    def __init__(self, name: str = "fake") -> None:
        self.name = name

    def call(self, *, tool_name: str, payload: Any) -> Any:
        return {"tool": tool_name, "echo": payload}


class _FakeRegistry:
    """In-memory registry used by /adapters and /gateway/call tests."""

    def __init__(self, manifest: list[dict[str, Any]]) -> None:
        self._manifest = manifest
        self._by_tool: dict[str, _FakeAdapter] = {}
        for entry in manifest:
            adapter = _FakeAdapter(name=entry["name"])
            for tool in entry.get("tool_names", []):
                self._by_tool[tool] = adapter

    def list_adapters(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._manifest]

    def resolve(self, tool_name: str) -> Any:
        return self._by_tool.get(tool_name)


# =============================================================================
# Helpers
# =============================================================================


_HEX64 = "a" * 64


def _happy_response(trace_id: str = "trace-m6-app-0001") -> GatewayResponse:
    return GatewayResponse(
        decision="ALLOW",
        result={"ok": True, "value": 42},
        liability_report=None,
        trace_id=trace_id,
        latency_ms=7,
        provenance_head=_HEX64,
        rule_applied="wsp-3020-advisor",
        wsp_section="3020",
        reason=None,
    )


def _valid_body(
    *,
    tool_name: str = "sfdc.fetch_client",
    trace_id: str = "trace-m6-app-0001",
    token: str = "stub-token-not-real-just-test-fixture-value-xxxxxxxx",
    payload: Any = None,
) -> dict[str, Any]:
    return {
        "token": token,
        "action": "client.read",
        "tool_name": tool_name,
        "mcp_server": "salesforce",
        "payload": payload if payload is not None else {"client_id": "CLT-1"},
        "trace_id": trace_id,
        "firm_id": "CRD-1",
        "target": {"client_id": "CLT-1", "advisor_id": "sarah"},
        "context": {},
        "session_id": None,
    }


@pytest.fixture
def sample_manifest() -> list[dict[str, Any]]:
    return [
        {
            "name": "salesforce_fsc",
            "tool_names": ["sfdc.fetch_client", "sfdc.fetch_holdings"],
        },
        {"name": "orion", "tool_names": ["orion.fetch_holdings"]},
        {"name": "emoney", "tool_names": ["emoney.fetch_plan_summary"]},
        {"name": "edgar", "tool_names": ["edgar.search_filings"]},
    ]


@pytest.fixture
def registry(sample_manifest: list[dict[str, Any]]) -> _FakeRegistry:
    return _FakeRegistry(sample_manifest)


@pytest.fixture
def captured_stdout(capsys) -> Any:
    """Return pytest's capsys handle so tests can snapshot stdout."""
    return capsys


# =============================================================================
# GET /health
# =============================================================================


def test_health_returns_200_and_v030() -> None:
    gateway = _FakeGateway(
        response=_happy_response(),
        health_payload={
            "status": "ok",
            "circuit_states": {},
            "dependencies_ready": True,
        },
    )
    with TestClient(create_app(gateway=gateway)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.3.0"
    assert body["backends"]["dependencies_ready"] is True


def test_health_tolerates_missing_gateway() -> None:
    """Container can boot before gateway injection. Liveness must pass."""
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.3.0"


# =============================================================================
# GET /adapters
# =============================================================================


def test_adapters_empty_when_no_registry() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/adapters")
    assert response.status_code == 200
    assert response.json() == {"adapters": []}


def test_adapters_returns_full_manifest(
    registry: _FakeRegistry, sample_manifest: list[dict[str, Any]]
) -> None:
    with TestClient(create_app(registry=registry)) as client:
        response = client.get("/adapters")
    assert response.status_code == 200
    body = response.json()
    assert len(body["adapters"]) == 4
    names = {entry["name"] for entry in body["adapters"]}
    assert names == {"salesforce_fsc", "orion", "emoney", "edgar"}
    # tool_names round-trip intact
    sfdc = next(e for e in body["adapters"] if e["name"] == "salesforce_fsc")
    assert sfdc["tool_names"] == [
        "sfdc.fetch_client",
        "sfdc.fetch_holdings",
    ]


# =============================================================================
# GET /gateway/reasons
# =============================================================================


def test_gateway_reasons_returns_all_11_entries() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/gateway/reasons")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reasons"], list)
    assert len(body["reasons"]) == 11
    assert set(body["reasons"]) == set(VALID_GATEWAY_REASONS)


# =============================================================================
# POST /gateway/call -- happy path
# =============================================================================


def test_gateway_call_happy_path_returns_200(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(response=_happy_response())
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["result"] == {"ok": True, "value": 42}
    assert body["trace_id"] == "trace-m6-app-0001"
    assert body["latency_ms"] == 7
    assert body["provenance_head"] == _HEX64
    assert body["rule_applied"] == "wsp-3020-advisor"
    assert body["wsp_section"] == "3020"
    # Gateway saw exactly one request with the adapter resolved from tool_name
    assert len(gateway.seen_requests) == 1
    seen = gateway.seen_requests[0]
    assert seen.tool_name == "sfdc.fetch_client"
    assert seen.vendor_adapter.name == "salesforce_fsc"


# =============================================================================
# POST /gateway/call -- GatewayError -> HTTP status mapping
# =============================================================================


@pytest.mark.parametrize(
    "reason,expected_status",
    [
        ("invalid_identity", 401),
        ("authority_denied", 403),
        ("authority_escalated", 202),
        ("rate_limited", 429),
        ("circuit_open", 503),
        ("vendor_unavailable", 503),
        ("vendor_error", 502),
        ("mnpi_filter_error", 502),
        ("mnpi_leakage_scan", 502),
        ("audit_failed", 500),
        ("invalid_request", 400),
    ],
)
def test_gateway_call_error_status_mapping(
    registry: _FakeRegistry, reason: str, expected_status: int
) -> None:
    """Every reason in VALID_GATEWAY_REASONS maps to a specific status."""
    gateway = _FakeGateway(error=GatewayError(reason))
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())
    assert response.status_code == expected_status
    body = response.json()
    assert body["error"]["reason"] == reason
    # Safety: no stack traces, vendor details, or module names leak out
    assert "traceback" not in body
    assert "m6_mcp_gateway" not in response.text


def test_gateway_call_authority_denied_returns_403(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(error=GatewayError("authority_denied"))
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())
    assert response.status_code == 403
    assert response.json()["error"]["reason"] == "authority_denied"


def test_gateway_call_rate_limited_returns_429(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(error=GatewayError("rate_limited"))
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())
    assert response.status_code == 429


def test_gateway_call_vendor_unavailable_returns_503(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(error=GatewayError("vendor_unavailable"))
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())
    assert response.status_code == 503


# =============================================================================
# POST /gateway/call -- malformed inputs
# =============================================================================


def test_gateway_call_malformed_body_returns_400(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(response=_happy_response())
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post(
            "/gateway/call",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["reason"] == "invalid_request"


def test_gateway_call_missing_required_field_returns_400(
    registry: _FakeRegistry,
) -> None:
    gateway = _FakeGateway(response=_happy_response())
    bad_body = _valid_body()
    del bad_body["trace_id"]
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=bad_body)
    assert response.status_code == 400
    assert response.json()["error"]["reason"] == "invalid_request"


def test_gateway_call_unknown_tool_name_returns_400(
    registry: _FakeRegistry,
) -> None:
    """Tool not in registry -> invalid_request. Never reaches the gateway."""
    gateway = _FakeGateway(response=_happy_response())
    body = _valid_body(tool_name="no.such_tool")
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post("/gateway/call", json=body)
    assert response.status_code == 400
    assert response.json()["error"]["reason"] == "invalid_request"
    assert gateway.seen_requests == []


def test_gateway_call_without_gateway_returns_503(
    registry: _FakeRegistry,
) -> None:
    with TestClient(create_app(registry=registry)) as client:
        response = client.post("/gateway/call", json=_valid_body())
    assert response.status_code == 503
    assert response.json()["error"]["reason"] == "vendor_unavailable"


# =============================================================================
# Middleware redaction -- body content MUST NOT appear on stdout.
# =============================================================================


def test_middleware_never_logs_body_canaries(
    registry: _FakeRegistry, captured_stdout: Any
) -> None:
    """SSN / phone / bank-routing canaries in the body must stay off stdout.

    Rule 9: clients get generic errors; full detail goes to logs ONLY.
    But *logs* means the audit log (M10), not the access log. The
    FastAPI access-log middleware must NEVER read the request body --
    asserting stdout is canary-free is how we prove it.
    """
    ssn_canary = "999-88-7777"
    phone_canary = "+1-202-555-0173"
    routing_canary = "021000021"  # ABA routing-number shape
    token_canary = "secret-token-do-not-log-0123456789abcdef0123456789abcd"

    body = _valid_body(
        token=token_canary,
        payload={
            "ssn": ssn_canary,
            "phone": phone_canary,
            "routing_number": routing_canary,
            "notes": "do-not-log-this",
        },
    )

    gateway = _FakeGateway(response=_happy_response())
    with TestClient(create_app(gateway=gateway, registry=registry)) as client:
        response = client.post(
            "/gateway/call",
            json=body,
            headers={"x-trace-id": "trace-canary-test"},
        )
    assert response.status_code == 200

    captured = captured_stdout.readouterr().out
    # Positive assertion: middleware DID log metadata.
    assert "trace-canary-test" in captured
    assert "/gateway/call" in captured
    # Negative assertions: no body content.
    for canary in (
        ssn_canary,
        phone_canary,
        routing_canary,
        token_canary,
        "do-not-log-this",
    ):
        assert canary not in captured, f"middleware leaked {canary!r}"
