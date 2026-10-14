"""
M6 MCP Gateway — Policy adapter helpers.

Thin wrappers around M1, M2, M4 calls that translate native module
exceptions into GatewayError with the correct frozen reason. Keeps
the pipeline body in gateway.py linear and easy to audit.

See `.kiro/specs/m6-mcp-gateway.md` section 2.8 and R13.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from m1_identity import AidClaims, IdentityService, InvalidAidError
from m2_m4_policy_engine import (
    AuthorityPolicy,
    MnpiPolicy,
    PolicyDecision,
    PolicyInput,
    UnsupportedTypeForFilterError,
)


def verify_identity(identity: IdentityService, token: str) -> AidClaims:
    """M1 AID verification. Raises GatewayError('invalid_identity')."""
    from m6_mcp_gateway.gateway import GatewayError

    try:
        return identity.verify(token)
    except InvalidAidError:
        raise GatewayError("invalid_identity")


def evaluate_authority(
    authority: AuthorityPolicy, policy_input: PolicyInput
) -> PolicyDecision:
    """M2 authority evaluation. Never raises — M2 always returns a
    PolicyDecision. Caller inspects `.decision` to pick ALLOW / DENY /
    ESCALATE branch.
    """
    return authority.evaluate(policy_input)


def filter_request(
    mnpi: MnpiPolicy, claims: AidClaims, payload: Any
) -> Any:
    """M4 MNPI filter on request payload.

    strict=True for BaseModel; strict=False otherwise (dict/list/None
    pass through). Non-BaseModel-non-dict payloads were rejected at
    GatewayRequest construction.
    """
    from m6_mcp_gateway.gateway import GatewayError

    strict = isinstance(payload, BaseModel)
    try:
        return mnpi.filter(claims, payload, strict=strict)
    except UnsupportedTypeForFilterError:
        raise GatewayError("mnpi_filter_error")


def filter_response(
    mnpi: MnpiPolicy, claims: AidClaims, response: Any
) -> Any:
    """M4 MNPI filter on vendor response. Same strict rule as request."""
    from m6_mcp_gateway.gateway import GatewayError

    strict = isinstance(response, BaseModel)
    try:
        return mnpi.filter(claims, response, strict=strict)
    except UnsupportedTypeForFilterError:
        raise GatewayError("mnpi_filter_error")


__all__ = [
    "verify_identity",
    "evaluate_authority",
    "filter_request",
    "filter_response",
]
