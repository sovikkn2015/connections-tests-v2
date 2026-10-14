"""
M6 Trust-Aware MCP Gateway — FastAPI Application.

Endpoints:
  POST /mcp/call       — Main gateway endpoint (full trust pipeline)
  POST /mcp/tools/list — List tools from downstream MCP server (trust-checked)
  GET  /health         — Health check (dependencies + circuit breaker states)

Every MCP call passes through M6. No exceptions (Rule 1).
Generic error messages to clients (Rule 9). Full errors to logs only.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from .leakage_scan import check_layer_readiness
from .mcp_proxy import MCPProxy
from .models import (
    DependencyHealth,
    GatewayConfig,
    GatewayError,
    HealthResponse,
    MCPRequest,
    MCPResponse,
    PipelineStage,
    ToolsListRequest,
    ToolsListResponse,
)
from .resilience import (
    CircuitOpenError,
    RateLimitExceededError,
    create_redis_client,
)
from .trust_pipeline import TrustPipeline
from .web_api import web_api_router

logger = logging.getLogger("m6.app")

_tracer = trace.get_tracer("m6.mcp-gateway")

# ── Module-level singletons (initialized at startup) ────────────

_config: GatewayConfig = GatewayConfig()
_pipeline: TrustPipeline | None = None
_proxy: MCPProxy | None = None


def get_config() -> GatewayConfig:
    return _config


def get_pipeline() -> TrustPipeline:
    assert _pipeline is not None, "TrustPipeline not initialized"
    return _pipeline


def get_proxy() -> MCPProxy:
    assert _proxy is not None, "MCPProxy not initialized"
    return _proxy


# ── Lifespan ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown gateway resources."""
    global _config, _pipeline, _proxy
    _config = GatewayConfig()
    _pipeline = TrustPipeline(_config)

    # Attempt Redis connection; fall back to in-memory if unavailable
    redis_client = None
    if _config.redis_url:
        redis_client = await create_redis_client(_config.redis_url)

    _proxy = MCPProxy(_config, redis_client=redis_client)
    check_layer_readiness()
    logger.info("M6 MCP Gateway started")
    yield
    if _proxy:
        await _proxy.close()
    if _pipeline:
        await _pipeline.close()
    if redis_client:
        await redis_client.aclose()
    logger.info("M6 MCP Gateway stopped")


# ── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(
    title="M6 Trust-Aware MCP Gateway",
    description="Central trust hub — every MCP call passes through M6.",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount web API routes (M12 Web Console ↔ M6 bridge)
app.include_router(web_api_router)


# ── OTel Middleware — root span per request ──────────────────────


@app.middleware("http")
async def otel_root_span_middleware(request: Request, call_next):
    """Create a root span for each HTTP request with request_id and trace_id."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    trace_id = request.headers.get("x-trace-id", str(uuid4()))
    with _tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        attributes={
            "m6.request_id": request_id,
            "m6.trace_id": trace_id,
            "http.method": request.method,
            "http.url": str(request.url.path),
        },
    ):
        response = await call_next(request)
        return response


# ── POST /mcp/call — Main Gateway Endpoint ──────────────────────


@app.post("/mcp/call", response_model=MCPResponse)
async def mcp_call(request: MCPRequest) -> MCPResponse | JSONResponse:
    """
    Main gateway endpoint. Full trust pipeline:
      Pre-call:  M1 verify → M2 authority → M4 filter request
      Forward:   MCP call to downstream server
      Post-call: M7 translate → M4 filter response → leakage scan → M10 audit

    Returns MCPResponse on success, GatewayError on failure.
    Generic errors to client (Rule 9). Full errors to logs only.
    """
    start_time = time.monotonic()
    pipeline = get_pipeline()
    proxy = get_proxy()

    # ── Pre-Call Trust Pipeline ───────────────────────────────
    pre_result = await pipeline.pre_call_pipeline(
        aid_token=request.aid_token,
        tool_name=request.tool_name,
        arguments=request.arguments,
        server_url=request.server_url,
        trace_id=request.trace_id,
    )

    if not pre_result.passed:
        logger.warning(
            "Pre-call pipeline denied request %s at stage %s: %s",
            request.request_id,
            pre_result.stage_failed,
            pre_result.reason,
        )
        # Rule 9: generic error to client
        return JSONResponse(
            status_code=403,
            content=GatewayError(
                error="Request denied",
                request_id=request.request_id,
            ).model_dump(),
        )

    # ── Forward MCP Call ──────────────────────────────────────
    try:
        raw_response = await proxy.forward_mcp_call(
            server_url=request.server_url,
            tool_name=request.tool_name,
            arguments=pre_result.filtered_arguments or request.arguments,
            user_id=pre_result.verified_claims.get("display_name", "system")
            if pre_result.verified_claims
            else "system",
        )
    except RateLimitExceededError as e:
        logger.warning("Rate limit exceeded for request %s", request.request_id)
        return JSONResponse(
            status_code=429,
            content=GatewayError(
                error="Rate limit exceeded",
                request_id=request.request_id,
                retry_after=e.retry_after,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after)},
        )
    except CircuitOpenError:
        logger.warning("Circuit open for %s", request.server_url)
        return JSONResponse(
            status_code=503,
            content=GatewayError(
                error="Service unavailable",
                request_id=request.request_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(
            "MCP call failed for request %s: %s",
            request.request_id,
            str(e),
        )
        return JSONResponse(
            status_code=502,
            content=GatewayError(
                error="Service unavailable",
                request_id=request.request_id,
            ).model_dump(),
        )

    # ── Post-Call Trust Pipeline ──────────────────────────────
    passed, filtered_response, chain, failure_reason = (
        await pipeline.post_call_pipeline(
            raw_response=raw_response,
            claims=pre_result.verified_claims or {},
            tool_name=request.tool_name,
            server_url=request.server_url,
            trace_id=request.trace_id,
            provenance_chain=pre_result.provenance_chain,
            request_arguments=pre_result.filtered_arguments or request.arguments,
        )
    )

    if not passed:
        logger.warning(
            "Post-call pipeline blocked response for request %s: %s",
            request.request_id,
            failure_reason,
        )
        return JSONResponse(
            status_code=403,
            content=GatewayError(
                error="Request denied",
                request_id=request.request_id,
            ).model_dump(),
        )

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    return MCPResponse(
        request_id=request.request_id,
        trace_id=request.trace_id,
        result=filtered_response,
        filtered=True,
        provenance_chain=chain,
        latency_ms=elapsed_ms,
    )


# ── POST /mcp/tools/list — List Tools (Trust-Checked) ───────────


@app.post("/mcp/tools/list", response_model=ToolsListResponse)
async def mcp_tools_list(request: ToolsListRequest) -> ToolsListResponse | JSONResponse:
    """
    List available tools from a downstream MCP server.
    Identity verification required (M1). No anonymous tool discovery.
    """
    pipeline = get_pipeline()
    proxy = get_proxy()

    # Verify identity only (no authority check for tool listing)
    pre_result = await pipeline.pre_call_pipeline(
        aid_token=request.aid_token,
        tool_name="tools.list",
        arguments={},
        server_url=request.server_url,
        trace_id=request.trace_id,
    )

    if not pre_result.passed:
        return JSONResponse(
            status_code=403,
            content=GatewayError(
                error="Request denied",
            ).model_dump(),
        )

    try:
        tools = await proxy.list_tools(request.server_url)
    except Exception as e:
        logger.error("Failed to list tools from %s: %s", request.server_url, str(e))
        return JSONResponse(
            status_code=502,
            content=GatewayError(error="Service unavailable").model_dump(),
        )

    return ToolsListResponse(
        server_url=request.server_url,
        tools=tools,
        trace_id=request.trace_id,
    )


# ── GET /health — Health Check ───────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Gateway health check.
    Reports connectivity to M1, M2/M4, M10 and circuit breaker states.
    """
    import httpx as _httpx

    proxy = get_proxy()
    deps: list[DependencyHealth] = []
    config = get_config()

    # Check M1
    try:
        async with _httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{config.m1_base_url.rstrip('/')}/health")
            deps.append(DependencyHealth(
                name="m1-identity", healthy=r.status_code == 200,
            ))
    except Exception as e:
        deps.append(DependencyHealth(
            name="m1-identity", healthy=False, error=str(e),
        ))

    # Check M2/M4
    try:
        async with _httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{config.m2_base_url.rstrip('/')}/health")
            deps.append(DependencyHealth(
                name="m2-m4-policy", healthy=r.status_code == 200,
            ))
    except Exception as e:
        deps.append(DependencyHealth(
            name="m2-m4-policy", healthy=False, error=str(e),
        ))

    # Check M10
    try:
        async with _httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{config.m10_base_url.rstrip('/')}/health")
            deps.append(DependencyHealth(
                name="m10-audit", healthy=r.status_code == 200,
            ))
    except Exception as e:
        deps.append(DependencyHealth(
            name="m10-audit", healthy=False, error=str(e),
        ))

    all_healthy = all(d.healthy for d in deps)
    cb_states = proxy.circuit_breakers.get_all_states()

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        dependencies=deps,
        circuit_breakers=cb_states,
    )
