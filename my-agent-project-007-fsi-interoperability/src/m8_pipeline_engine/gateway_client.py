"""
M8 Pipeline Engine -- GatewayClient Protocol + dataclass shapes.

v0.2.0 (Required Fixes 1-3):
- GatewayRequest / GatewayResponse are @dataclass(frozen=True) (not Pydantic).
  Field-for-field compatible with src/m6_mcp_gateway/gateway.py lines 118/221.
- GatewayRequest.vendor_adapter is REQUIRED non-None.
- Failure paths RAISE GatewayError.

M8 defines GatewayError LOCALLY (duck-typed on `.reason`) to avoid an
m6_mcp_gateway import at runtime (AC12.8).

See `.kiro/specs/m8-pipeline-engine.md` R7.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, runtime_checkable


class GatewayError(Exception):
    """Duck-typed copy of M6's GatewayError (AC7.4)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class GatewayRequest:
    """Dataclass-shaped copy of M6's GatewayRequest (Req-Fix 1)."""

    token: str
    action: str
    tool_name: str
    mcp_server: str
    payload: Any
    trace_id: str
    firm_id: str
    target: Mapping[str, Any]
    context: Mapping[str, Any]
    session_id: Optional[str]
    vendor_adapter: Any  # REQUIRED non-None -- Req-Fix 2


@dataclass(frozen=True)
class GatewayResponse:
    """Dataclass-shaped copy of M6's GatewayResponse (Req-Fix 1)."""

    decision: str
    result: Any
    liability_report: Optional[Any]
    trace_id: str
    latency_ms: int
    provenance_head: str
    rule_applied: Optional[str]
    wsp_section: Optional[str]
    reason: Optional[str]


@runtime_checkable
class GatewayClient(Protocol):
    """Protocol matching M6 TrustAwareGateway.call (AC7.1)."""

    def call(self, request: GatewayRequest) -> GatewayResponse:
        """Raises GatewayError(reason) on any failure path."""
        ...


@runtime_checkable
class VendorAdapterResolver(Protocol):
    """Protocol resolving a VendorAdapter by tool_name (AC7.3)."""

    def resolve(self, tool_name: str) -> Any:
        ...


class LocalVendorAdapterResolver:
    """Production resolver wrapping a registry snapshot."""

    def __init__(self, registry_snapshot: dict[str, Any]) -> None:
        self._reg = dict(registry_snapshot)

    def resolve(self, tool_name: str) -> Any:
        try:
            return self._reg[tool_name]
        except KeyError:
            raise GatewayError("invalid_request")


class M6GatewayClient:
    """Production GatewayClient. mTLS HTTPS to M6 FastAPI.

    urllib.request only (AC13.4). Zero credentials.
    """

    def __init__(
        self,
        *,
        base_url: str,
        mtls_cert_path: str,
        vendor_adapter_registry: VendorAdapterResolver,
        timeout_ms: int = 30000,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._cert = mtls_cert_path
        self._registry = vendor_adapter_registry
        self._timeout = timeout_ms / 1000.0

    def call(self, request: GatewayRequest) -> GatewayResponse:
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(self._cert)
        body = json.dumps(
            {
                "token": request.token,
                "action": request.action,
                "tool_name": request.tool_name,
                "mcp_server": request.mcp_server,
                "payload": request.payload,
                "trace_id": request.trace_id,
                "firm_id": request.firm_id,
                "target": dict(request.target),
                "context": dict(request.context),
                "session_id": request.session_id,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/call",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self._timeout, context=ctx
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                reason = payload.get("reason", "vendor_unavailable")
            except Exception:
                reason = "vendor_unavailable"
            raise GatewayError(reason)
        except urllib.error.URLError:
            raise GatewayError("vendor_unavailable")

        if isinstance(data.get("error"), dict) and "reason" in data["error"]:
            raise GatewayError(data["error"]["reason"])

        return GatewayResponse(
            decision=data["decision"],
            result=data["result"],
            liability_report=data.get("liability_report"),
            trace_id=data["trace_id"],
            latency_ms=int(data["latency_ms"]),
            provenance_head=data["provenance_head"],
            rule_applied=data.get("rule_applied"),
            wsp_section=data.get("wsp_section"),
            reason=data.get("reason"),
        )


class FakeGatewayClient:
    """Test GatewayClient. Seeded responses keyed by tool_name."""

    def __init__(
        self, call_responses: Optional[dict[str, Any]] = None
    ) -> None:
        self.call_responses: dict[str, Any] = dict(call_responses or {})
        self.recorded_calls: list[GatewayRequest] = []

    def call(self, request: GatewayRequest) -> GatewayResponse:
        self.recorded_calls.append(request)
        if request.tool_name in self.call_responses:
            resp = self.call_responses[request.tool_name]
        else:
            resp = GatewayResponse(
                decision="ALLOW",
                result={},
                liability_report=None,
                trace_id=request.trace_id,
                latency_ms=1,
                provenance_head="0" * 64,
                rule_applied=None,
                wsp_section=None,
                reason=None,
            )
        if isinstance(resp, Exception):
            raise resp
        return resp


def _invoke_tool(
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    *,
    trace_id: str,
    firm_id: str,
    aid_token: str,
    tool_name: str,
    mcp_server: str,
    action: str,
    payload: dict,
    target: dict,
    context: dict,
) -> GatewayResponse:
    """Resolve adapter, construct request, call gateway."""
    vendor_adapter = resolver.resolve(tool_name)
    request = GatewayRequest(
        token=aid_token,
        action=action,
        tool_name=tool_name,
        mcp_server=mcp_server,
        payload=payload,
        trace_id=trace_id,
        firm_id=firm_id,
        target=target,
        context=context,
        session_id=None,
        vendor_adapter=vendor_adapter,
    )
    return gateway.call(request)


def _call_with_branching(
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    *,
    trace_id: str,
    firm_id: str,
    aid_token: str,
    tool_name: str,
    mcp_server: str,
    action: str,
    payload: dict,
    target: dict,
    context: dict,
) -> tuple[Optional[GatewayResponse], Optional[str]]:
    """Returns (response, reason_code). Exactly one is non-None."""
    try:
        response = _invoke_tool(
            gateway,
            resolver,
            trace_id=trace_id,
            firm_id=firm_id,
            aid_token=aid_token,
            tool_name=tool_name,
            mcp_server=mcp_server,
            action=action,
            payload=payload,
            target=target,
            context=context,
        )
    except GatewayError as exc:
        reason = getattr(exc, "reason", "")
        if reason == "authority_denied":
            return None, "m8_compliance_denied"
        if reason == "authority_escalated":
            return None, "__ESCALATION__"
        if reason in ("vendor_unavailable", "vendor_error", "rate_limited", "circuit_open"):
            return None, "m8_stage_failed"
        if reason in ("mnpi_leakage_scan", "mnpi_filter_error"):
            return None, "m8_mnpi_leaked_through_gateway"
        if reason == "audit_failed":
            return None, "m8_audit_write_failed"
        if reason in ("invalid_request", "invalid_identity"):
            return None, "m8_stage_failed"
        return None, "m8_stage_failed"

    if response.decision == "ALLOW":
        return response, None
    if response.decision == "ESCALATE":
        return response, "__ESCALATION__"
    return None, "m8_compliance_denied"


__all__ = [
    "GatewayClient",
    "GatewayError",
    "GatewayRequest",
    "GatewayResponse",
    "VendorAdapterResolver",
    "LocalVendorAdapterResolver",
    "M6GatewayClient",
    "FakeGatewayClient",
]
