"""
M6 Trust-Aware MCP Gateway — Public API.

Phase 1: library with injectable VendorAdapter. Every MCP call in the
007 platform flows through this gateway, executing the trust pipeline:

    M1 identity -> M2 authority -> M4 request MNPI filter -> vendor call
    -> M4 response MNPI filter -> Gap 6 leakage scan -> M10 audit

Fail-closed at every stage. A LiabilityReport is built for every
request (ALLOW and DENY). An AuditEntry is written to M10 before any
response is returned to the caller.

Usage (Phase 1):

    from m6_mcp_gateway import (
        TrustAwareGateway, GatewayRequest, StubVendorAdapter,
        CircuitBreaker, RateLimiter,
    )
    gateway = TrustAwareGateway(
        identity=identity_service,
        authority=authority_policy,
        mnpi=mnpi_policy,
        audit=audit_logger,
        leakage_scanner=scanner,
        circuit_breaker=CircuitBreaker(),
        rate_limiter=RateLimiter(capacity=60, refill_per_second=1.0),
    )
    response = gateway.call(GatewayRequest(...))

Phase 2 replaces StubVendorAdapter with M11 adapters and moves
CircuitBreaker + RateLimiter state to Redis. The public surface is
stable across the transition.

See `.kiro/specs/m6-mcp-gateway.md` for the full contract.
"""

from __future__ import annotations

from m6_mcp_gateway.adapters import (
    StubVendorAdapter,
    VALID_VENDOR_KINDS,
    VendorAdapter,
    VendorAdapterError,
)
from m6_mcp_gateway.gateway import (
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    TrustAwareGateway,
    VALID_GATEWAY_REASONS,
)
from m6_mcp_gateway.resilience import CircuitBreaker, RateLimiter

__all__ = [
    # Orchestrator
    "TrustAwareGateway",
    "GatewayRequest",
    "GatewayResponse",
    "GatewayError",
    "VALID_GATEWAY_REASONS",
    # Adapters
    "VendorAdapter",
    "VendorAdapterError",
    "VALID_VENDOR_KINDS",
    "StubVendorAdapter",
    # Resilience
    "CircuitBreaker",
    "RateLimiter",
]
