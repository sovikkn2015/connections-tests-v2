"""
M6 MCP Gateway — Pydantic v2 Models.

All models for the trust-aware MCP gateway:
  - MCPRequest / MCPResponse: wire format for MCP calls
  - TrustPipelineResult: pre/post pipeline outcomes
  - ProvenanceEntry: SHA-256 hash chain per processing stage
  - LeakageScanResult: 3-layer MNPI leakage scan results
  - GatewayConfig: per-server resilience settings
  - GatewayError: safe error response (Rule 9)
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ────────────────────────────────────────────────────────


class PipelineStage(str, Enum):
    """Processing stages in the trust pipeline."""
    identity_verification = "identity_verification"
    authority_check = "authority_check"
    mnpi_filter_request = "mnpi_filter_request"
    mcp_forward = "mcp_forward"
    response_translate = "response_translate"
    mnpi_filter_response = "mnpi_filter_response"
    leakage_scan = "leakage_scan"
    audit_log = "audit_log"


class LeakageLayer(str, Enum):
    """MNPI leakage scan layers (ARCH-06 Gap 6)."""
    layer_a_regex = "layer_a_regex"
    layer_b_ner = "layer_b_ner"
    layer_c_llm = "layer_c_llm"


class CircuitState(str, Enum):
    """Circuit breaker states."""
    closed = "closed"
    open = "open"
    half_open = "half_open"


# ── Provenance Chain (ARCH-06 Gap 2, Rule 11) ───────────────────


class ProvenanceEntry(BaseModel):
    """
    Single entry in the provenance chain. Each processing stage
    adds a SHA-256 hash computed over the canonical payload at
    that stage. Chain is append-only.
    """
    stage: PipelineStage
    module: str = Field(..., description="Module that executed this stage, e.g. 'm1'")
    hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of canonical payload at this stage",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def compute_hash(payload: Any) -> str:
        """Compute SHA-256 over a JSON-serializable payload."""
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── MCP Request / Response ───────────────────────────────────────


class MCPRequest(BaseModel):
    """
    Incoming MCP call to the gateway.
    Every request carries an AID token (JWT RS256).
    """
    request_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique request identifier",
    )
    aid_token: str = Field(
        ..., min_length=1, description="JWT RS256 AID token from M1",
    )
    server_url: str = Field(
        ..., min_length=1, description="Target MCP server URL",
    )
    tool_name: str = Field(
        ..., min_length=1, description="MCP tool to invoke",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments",
    )
    trace_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Distributed trace ID for OpenTelemetry",
    )


class MCPResponse(BaseModel):
    """
    Outgoing MCP response from the gateway.
    Contains filtered result + audit metadata.
    """
    request_id: str
    trace_id: str
    result: Any = Field(None, description="Filtered MCP tool result")
    filtered: bool = Field(
        False, description="True if MNPI fields were stripped",
    )
    audit_trace_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="M10 audit entry trace ID",
    )
    provenance_chain: list[ProvenanceEntry] = Field(default_factory=list)
    latency_ms: int = Field(0, ge=0)


# ── Trust Pipeline Result ────────────────────────────────────────


class TrustPipelineResult(BaseModel):
    """
    Result of pre-call or post-call trust pipeline execution.
    If passed=False, the request/response is DENIED (fail-closed).
    """
    passed: bool
    stage_failed: Optional[PipelineStage] = Field(
        None, description="Stage that caused failure, if any",
    )
    reason: Optional[str] = Field(
        None, description="Internal reason (logs only, never to client)",
    )
    provenance_chain: list[ProvenanceEntry] = Field(default_factory=list)

    # Pre-call pipeline outputs (populated on success)
    verified_claims: Optional[dict[str, Any]] = Field(
        None, description="AID claims from M1 verification",
    )
    filtered_arguments: Optional[dict[str, Any]] = Field(
        None, description="Request arguments after M4 MNPI filter",
    )


# ── Leakage Scan (ARCH-06 Gap 6, Rule 10) ───────────────────────


class LayerResult(BaseModel):
    """Result from a single leakage scan layer."""
    layer: LeakageLayer
    passed: bool
    detections: list[str] = Field(
        default_factory=list,
        description="Detected MNPI patterns (for audit log only)",
    )
    not_implemented: bool = Field(
        False, description="True for Phase 2/3 stubs",
    )
    latency_ms: float = Field(0.0, ge=0.0)


class LeakageScanResult(BaseModel):
    """
    Combined result of the 3-layer MNPI leakage scan.
    If ANY layer detects leakage, overall passed=False → response BLOCKED.
    """
    passed: bool
    layers: list[LayerResult] = Field(default_factory=list)
    blocked_reason: Optional[str] = None


# ── Gateway Config (per-server settings) ─────────────────────────


class ServerConfig(BaseModel):
    """Per-MCP-server resilience configuration."""
    server_url: str
    timeout_seconds: float = Field(
        30.0, gt=0, description="Timeout per MCP call (Rule 6)",
    )
    max_retries: int = Field(
        3, ge=0, le=10, description="Max retry attempts (Rule 5)",
    )
    circuit_breaker_threshold: int = Field(
        5, ge=1, description="Failures before circuit opens (Rule 4)",
    )
    circuit_breaker_recovery_seconds: float = Field(
        30.0, gt=0, description="Seconds in open state before half-open (Rule 4)",
    )
    rate_limit_per_user: int = Field(
        100, ge=1, description="Max requests per user per minute (Rule 7)",
    )
    rate_limit_window_seconds: int = Field(
        60, ge=1, description="Sliding window size in seconds",
    )
    bulkhead_max_concurrent: int = Field(
        10, ge=1, description="Max concurrent requests to this server (Rule 8)",
    )
    category: str = Field(
        "default", description="Server category for bulkhead isolation",
    )


class GatewayConfig(BaseModel):
    """
    Full gateway configuration. Loaded from M5 enterprise config
    via REST call (no cross-module import).

    Env var mapping (docker-compose → field):
      M1_URL  → m1_base_url
      M2_URL  → m2_base_url
      M4_URL  → m4_base_url
      M7_URL  → m7_base_url
      M10_URL → m10_base_url
      REDIS_URL → redis_url

    Falls back to hardcoded defaults when env vars are not set,
    so existing tests (which don't set env vars) keep working.
    """
    m1_base_url: str = Field(
        "http://m1-identity:8000",
        description="M1 Identity Service base URL",
    )
    m2_base_url: str = Field(
        "http://m2-m4-policy:8000",
        description="M2/M4 Policy Engine base URL",
    )
    m4_base_url: str = Field(
        "http://m2-m4-policy:8000",
        description="M4 MNPI Filter base URL (same as M2)",
    )
    m7_base_url: str = Field(
        "http://m7-translator:8000",
        description="M7 Schema Translator base URL",
    )
    m10_base_url: str = Field(
        "http://m10-audit:8000",
        description="M10 Audit Logger base URL",
    )
    redis_url: str = Field(
        "redis://localhost:6379/0",
        description="Redis for rate limits + circuit breaker state",
    )
    default_timeout_seconds: float = Field(30.0, gt=0)
    servers: dict[str, ServerConfig] = Field(
        default_factory=dict,
        description="Per-server config overrides keyed by server_url",
    )

    @model_validator(mode="before")
    @classmethod
    def _load_env_vars(cls, values: Any) -> Any:
        """Read docker-compose env var names and map to field names.

        Only overrides fields that were NOT explicitly provided by the
        caller, so programmatic construction (e.g. tests) still works.
        """
        if not isinstance(values, dict):
            return values

        env_map = {
            "M1_URL": "m1_base_url",
            "M2_URL": "m2_base_url",
            "M4_URL": "m4_base_url",
            "M7_URL": "m7_base_url",
            "M10_URL": "m10_base_url",
            "REDIS_URL": "redis_url",
        }
        for env_key, field_name in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val and field_name not in values:
                values[field_name] = env_val
        return values

    def get_server_config(self, server_url: str) -> ServerConfig:
        """Get config for a server, falling back to defaults."""
        if server_url in self.servers:
            return self.servers[server_url]
        return ServerConfig(server_url=server_url)


# ── Gateway Error (Rule 9 — generic errors to clients) ──────────


class GatewayError(BaseModel):
    """
    Safe error response. Never leaks internal details.
    Full error info goes to logs only (Rule 9).
    """
    error: str = Field(
        "Request denied",
        description="Generic, safe error message for client",
    )
    request_id: Optional[str] = None
    retry_after: Optional[int] = Field(
        None, description="Seconds until retry (for 429 responses)",
    )


# ── Health Check ─────────────────────────────────────────────────


class DependencyHealth(BaseModel):
    """Health status of a single dependency."""
    name: str
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Gateway health check response."""
    status: str = Field(..., description="healthy | degraded | unhealthy")
    module: str = "m6-mcp-gateway"
    version: str = "0.1.0"
    dependencies: list[DependencyHealth] = Field(default_factory=list)
    circuit_breakers: dict[str, str] = Field(
        default_factory=dict,
        description="Circuit breaker states keyed by server_url",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Tools List ───────────────────────────────────────────────────


class ToolsListRequest(BaseModel):
    """Request to list tools from a downstream MCP server."""
    aid_token: str = Field(..., min_length=1)
    server_url: str = Field(..., min_length=1)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class ToolInfo(BaseModel):
    """Single tool descriptor from an MCP server."""
    name: str
    description: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = None


class ToolsListResponse(BaseModel):
    """Response containing available tools from a downstream MCP server."""
    server_url: str
    tools: list[ToolInfo] = Field(default_factory=list)
    trace_id: str
