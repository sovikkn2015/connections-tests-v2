"""
M6 Trust-Aware MCP Gateway -- FastAPI REST surface (v0.3.0).

Exposes four routes so peer modules can bootstrap + call M6 without
reaching into its in-process library:

    GET  /health            -- liveness + backend-health probe
    GET  /adapters          -- manifest of registered vendor adapters
    GET  /gateway/reasons   -- the 11-entry VALID_GATEWAY_REASONS vocab
    POST /gateway/call      -- execute one trust-pipeline request

The in-process ``TrustAwareGateway`` (see ``gateway.py``) stays exactly
as-is; this file *wraps* it. HTTP status codes map 1-to-1 to
``GatewayError.reason`` per the spec so upstream callers can
deterministically translate wire errors back into their local reason
vocabulary (M8's ``M6GatewayClient`` does exactly that).

Why /adapters exists:
    M8 pods boot with a ``LocalVendorAdapterResolver`` seeded from a
    compile-time ``dict[str, Any]`` snapshot. Production requires M6 to
    publish a real manifest over REST so M8 pods can hydrate the
    resolver on startup. This route is the canonical source of truth.

Why /gateway/reasons exists:
    M8's ``_call_with_branching`` hard-codes every reason string. This
    route lets peer modules assert at boot that their local reason
    branches match M6's authoritative frozenset -- preventing silent
    vocab drift between deploys.

Security / Steering invariants:
    * mTLS terminates upstream in the service mesh (Steering Rule 21);
      this app does NOT authenticate callers directly.
    * CORS is NOT installed -- private subnet only.
    * The stdlib ``logging`` module is NOT imported. Access lines are
      emitted via ``sys.stdout.write(...)``; body content is NEVER
      logged, only headers + trace_id + latency + status + path.
    * Zero credentials in code, config defaults, or env-var fallbacks.
    * No cross-module imports at the FastAPI layer -- everything is
      reached via the injected ``TrustAwareGateway`` and
      ``AdapterRegistry``.

See ``../../docs/architecture/ARCH-09-complete-module-map.md`` for
where M6 sits in the call graph.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import fields as dc_fields
from typing import Any, Awaitable, Callable, Optional, Protocol, runtime_checkable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from m6_mcp_gateway.gateway import (
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    TrustAwareGateway,
    VALID_GATEWAY_REASONS,
)


# =============================================================================
# AdapterRegistry Protocol
# =============================================================================


@runtime_checkable
class AdapterRegistry(Protocol):
    """Read-side contract for publishing the vendor-adapter manifest.

    ``list_adapters()`` returns a list of dicts with keys ``name`` (a
    vendor-adapter identifier, e.g. ``"salesforce_fsc"``) and
    ``tool_names`` (list of MCP tool names the adapter exposes, e.g.
    ``["sfdc.fetch_client", "sfdc.fetch_holdings"]``). This is the
    payload served from ``GET /adapters`` so peer pods (M8) can
    hydrate their ``LocalVendorAdapterResolver`` on startup.

    ``resolve(tool_name)`` returns the ``VendorAdapter``-shaped object
    M6 should hand to ``TrustAwareGateway`` for a given tool, or
    ``None`` if the tool is unknown. Keeping resolve optional (via
    ``hasattr`` check at call sites) lets pure-manifest test doubles
    satisfy the Protocol without implementing lookup.

    Production implementations wrap the in-process ``VendorAdapter``
    registry; tests inject an inline instance.
    """

    def list_adapters(self) -> list[dict[str, Any]]:
        ...

    def resolve(self, tool_name: str) -> Any:
        ...


# =============================================================================
# HTTP status mapping (spec R2 -> R?)
# Each GatewayError.reason deterministically maps to ONE status code.
# =============================================================================

_REASON_TO_STATUS: dict[str, int] = {
    "invalid_identity": 401,
    "authority_denied": 403,
    "authority_escalated": 202,  # response body carries the escalation
    "mnpi_filter_error": 502,
    "circuit_open": 503,
    "rate_limited": 429,
    "vendor_unavailable": 503,
    "vendor_error": 502,
    "mnpi_leakage_scan": 502,
    "audit_failed": 500,
    "invalid_request": 400,
}

# Sanity: every reason in the frozen vocab must have a status mapping.
# Asserting at import time prevents silent status regressions when new
# reasons are added to VALID_GATEWAY_REASONS.
assert set(_REASON_TO_STATUS.keys()) == set(VALID_GATEWAY_REASONS), (
    "Reason-to-status map drifted from VALID_GATEWAY_REASONS: "
    f"map={sorted(_REASON_TO_STATUS.keys())} "
    f"vocab={sorted(VALID_GATEWAY_REASONS)}"
)


# =============================================================================
# Structured stdout access logger (no body, no credentials, no MNPI)
# =============================================================================


def _structured_stdout(record: dict[str, Any]) -> None:
    """Emit a single JSON line to stdout. No request/response body ever."""
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class StructuredAccessLogMiddleware(BaseHTTPMiddleware):
    """One stdout line on request entry, one on exit.

    Captures only: method, path, status_code, latency_ms, trace_id.
    The request/response body is NEVER read or logged -- keeps access
    logs free of AID tokens (credential) and payload data (which may
    carry MNPI-shaped fragments before M4 filters them).

    ``trace_id`` is lifted from the ``x-trace-id`` header (populated
    by the service-mesh gateway upstream). No trace_id is ever pulled
    from the request body.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        trace_id = request.headers.get("x-trace-id")

        _structured_stdout({
            "phase": "request_start",
            "method": request.method,
            "path": request.url.path,
            "trace_id": trace_id,
        })

        response = await call_next(request)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _structured_stdout({
            "phase": "request_end",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
            "trace_id": trace_id,
        })
        return response


# =============================================================================
# JSON serialization for GatewayResponse -- mirrors M8's wire contract.
# =============================================================================


def _serialize_response(resp: GatewayResponse) -> dict[str, Any]:
    """Flatten a GatewayResponse to a JSON-safe dict.

    ``liability_report`` is reduced to a compact summary on the wire:
    tests do not rely on the full report shape, and M8's client only
    consumes ``decision``, ``result``, ``trace_id``, ``latency_ms``,
    ``provenance_head``, ``rule_applied``, ``wsp_section``, ``reason``.
    """
    liability: Optional[dict[str, Any]] = None
    if resp.liability_report is not None:
        report = resp.liability_report
        liability = {
            "trace_id": getattr(report, "trace_id", None),
            "chain_verified": getattr(report, "chain_verified", None),
        }
    return {
        "decision": resp.decision,
        "result": resp.result,
        "liability_report": liability,
        "trace_id": resp.trace_id,
        "latency_ms": resp.latency_ms,
        "provenance_head": resp.provenance_head,
        "rule_applied": resp.rule_applied,
        "wsp_section": resp.wsp_section,
        "reason": resp.reason,
    }


# =============================================================================
# Request body -> GatewayRequest
# =============================================================================

# Fields that the HTTP client supplies verbatim. ``vendor_adapter`` is
# resolved server-side via the registry (never trusted from the wire).
_WIRE_REQUEST_FIELDS: tuple[str, ...] = tuple(
    f.name for f in dc_fields(GatewayRequest) if f.name != "vendor_adapter"
)


# =============================================================================
# App factory
# =============================================================================


def create_app(
    gateway: Optional[TrustAwareGateway] = None,
    registry: Optional[AdapterRegistry] = None,
) -> FastAPI:
    """Construct a FastAPI app wrapping the injected ``TrustAwareGateway``.

    Both arguments are optional to support the module-level ``app``
    binding used by the Dockerfile's ``uvicorn`` entrypoint: the
    container can start without a real gateway (e.g. during image
    smoke-tests), and the ``/gateway/call`` route will reject calls
    with ``503`` until a gateway is injected via
    ``app.state.gateway = ...`` at runtime.

    Tests inject both dependencies directly.
    """
    new_app = FastAPI(
        title="M6 Trust-Aware MCP Gateway",
        version="0.3.0",
        docs_url=None,       # private subnet; no OpenAPI UI exposed
        redoc_url=None,
        openapi_url=None,
    )
    # CORS intentionally NOT installed -- private subnet only.
    new_app.add_middleware(StructuredAccessLogMiddleware)
    new_app.state.gateway = gateway
    new_app.state.registry = registry

    @new_app.get("/health")
    async def health(request: Request) -> Response:
        """Liveness + (best-effort) backend-health probe."""
        gw: Optional[TrustAwareGateway] = request.app.state.gateway
        backends: dict[str, Any] = {}
        if gw is not None:
            try:
                backends = gw.health()
            except Exception:
                # Never let a gateway-health bug fail the liveness probe.
                backends = {"status": "degraded"}
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "version": "0.3.0",
                "backends": backends,
            },
        )


    @new_app.get("/adapters")
    async def adapters(request: Request) -> Response:
        """Publish the vendor-adapter manifest so peers can bootstrap.

        Empty list when no registry is wired -- keeps the route safe
        for tests that don't care about adapters.
        """
        reg: Optional[AdapterRegistry] = request.app.state.registry
        if reg is None:
            return JSONResponse(
                status_code=200, content={"adapters": []}
            )
        try:
            listed = reg.list_adapters()
        except Exception:
            # Registry bugs must not leak into a 500 at the public API.
            # Fail safe: return empty manifest so pods can retry.
            return JSONResponse(
                status_code=200, content={"adapters": []}
            )
        return JSONResponse(
            status_code=200, content={"adapters": list(listed)}
        )

    @new_app.get("/gateway/reasons")
    async def gateway_reasons() -> Response:
        """Publish M6's authoritative reason vocabulary.

        Order is stable (sorted) so peer modules can assert
        set-equality without caring about insertion order.
        """
        return JSONResponse(
            status_code=200,
            content={"reasons": sorted(VALID_GATEWAY_REASONS)},
        )


    @new_app.post("/gateway/call")
    async def gateway_call(request: Request) -> Response:
        """Execute one trust-pipeline request.

        Body keys must match ``GatewayRequest`` dataclass fields minus
        ``vendor_adapter`` (resolved server-side via the registry).

        Error status codes are driven by ``_REASON_TO_STATUS``. Client-
        facing bodies carry only the reason string -- no stack traces,
        no vendor-side error detail, no internal-module names
        (Gateway Rule 9).
        """
        gw: Optional[TrustAwareGateway] = request.app.state.gateway
        if gw is None:
            # Container started without a gateway injected. Fail-safe
            # with a generic 503 per Rule 9 -- no internal leak.
            return JSONResponse(
                status_code=503,
                content={"error": {"reason": "vendor_unavailable"}},
            )

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        missing = [k for k in _WIRE_REQUEST_FIELDS if k not in body]
        if missing:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        reg: Optional[AdapterRegistry] = request.app.state.registry
        tool_name = body.get("tool_name")
        vendor_adapter = _resolve_adapter(reg, tool_name)
        if vendor_adapter is None:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        try:
            req_obj = GatewayRequest(
                token=body["token"],
                action=body["action"],
                tool_name=body["tool_name"],
                mcp_server=body["mcp_server"],
                payload=body["payload"],
                trace_id=body["trace_id"],
                firm_id=body["firm_id"],
                target=body["target"] or {},
                context=body["context"] or {},
                session_id=body.get("session_id"),
                vendor_adapter=vendor_adapter,
            )
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        try:
            resp = gw.call(req_obj)
        except GatewayError as exc:
            status = _REASON_TO_STATUS.get(exc.reason, 500)
            return JSONResponse(
                status_code=status,
                content={"error": {"reason": exc.reason}},
            )
        except Exception:
            # Absolute safety net. Never leak internals to the wire.
            return JSONResponse(
                status_code=500,
                content={"error": {"reason": "audit_failed"}},
            )

        return JSONResponse(
            status_code=200, content=_serialize_response(resp)
        )

    return new_app


# =============================================================================
# Adapter resolution helper
# =============================================================================


def _resolve_adapter(
    registry: Optional[AdapterRegistry], tool_name: Any
) -> Any:
    """Resolve a VendorAdapter from the registry. Returns None on miss.

    Defensive: any exception in the user-supplied registry surfaces as
    ``None`` so the HTTP layer can return 400 invalid_request rather
    than propagating internal state to the wire (Rule 9).
    """
    if registry is None:
        return None
    if not isinstance(tool_name, str) or not tool_name:
        return None
    resolve = getattr(registry, "resolve", None)
    if resolve is None or not callable(resolve):
        return None
    try:
        return resolve(tool_name)
    except Exception:
        return None


# =============================================================================
# Module-level default app (imported by Dockerfile uvicorn entrypoint).
#
# The real gateway + registry are injected at runtime via app.state, or
# the container is redeployed with an updated create_app call. Shipping
# a functional-but-empty app lets the image build + health-probe pass
# before any trust-layer wiring runs.
# =============================================================================

app: FastAPI = create_app()


__all__ = [
    "AdapterRegistry",
    "create_app",
    "app",
]
