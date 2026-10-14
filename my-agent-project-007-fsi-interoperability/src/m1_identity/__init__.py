"""
M1 Agent Identity — Public API.

Phase 1: HMAC-SHA256 (HS256) signing, in-memory revocation, library only.
Migrates to RS256 + Keycloak in Phase 2.

Usage:
    from m1_identity import IdentityService, Role
    svc = IdentityService(audience="007-mcp-gateway")
    token = svc.issue(
        sub="sarah", firm_id="CRD-1", crd_number="CRD-1",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        registration_type=RegistrationType.ria_only,
        authority_scope=["portfolio.read"],
        authority_excludes=[],
    )
    claims = svc.verify(token)  # -> AidClaims
    svc.revoke(claims.jti)

See `.kiro/specs/m1-agent-identity.md` for the full contract.
"""

from __future__ import annotations

from m1_identity.claims import (
    AidClaims,
    InvalidAidError,
    ISSUER,
    LEI_PATTERN,
    Role,
)
from m1_identity.service import (
    DEFAULT_CLOCK_SKEW_SECONDS,
    DEFAULT_TTL_SECONDS,
    IdentityService,
    MAX_CLOCK_SKEW_SECONDS,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    SIGNING_ALGORITHM_DEFAULT,
)

__all__ = [
    # Claims
    "AidClaims",
    "Role",
    "InvalidAidError",
    "ISSUER",
    "LEI_PATTERN",
    # Service
    "IdentityService",
    "DEFAULT_TTL_SECONDS",
    "MAX_TTL_SECONDS",
    "MIN_TTL_SECONDS",
    "DEFAULT_CLOCK_SKEW_SECONDS",
    "MAX_CLOCK_SKEW_SECONDS",
    "SIGNING_ALGORITHM_DEFAULT",
]
