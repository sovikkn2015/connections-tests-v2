"""
M1 Agent Identity — AidClaims model, Role enum, InvalidAidError.

Defines the verified payload structure for an Agent Identity Document (AID).
All claims validated at both issue-time (type-checked inputs) and verify-time
(enum-membership + format + issuer lock).

Source docs: `.kiro/specs/m1-agent-identity.md` §2.3, §2.9.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Importing enums from M5 is the ONLY permitted cross-module dependency.
# See `.kiro/specs/m1-agent-identity.md` §2.6 and steering rule 9.
from m5_config_loader import Archetype, RegistrationType


# =============================================================================
# Constants
# =============================================================================

#: Fixed issuer string — reject any token that does not match.
ISSUER: str = "007-fsi-platform"

#: Legal Entity Identifier regex (ISO 17442).
#
# Source of truth: m5_config_loader.FirmConfig.validate_lei
# Duplicated here to avoid importing a private validator. A runtime drift test
# asserts this pattern string equals the M5 pattern string.
LEI_PATTERN: str = r"^[A-Z0-9]{18}[0-9]{2}$"


# =============================================================================
# Role enum
# =============================================================================

class Role(str, Enum):
    """Operational role of an AID holder."""

    advisor = "advisor"
    compliance_officer = "compliance_officer"
    system = "system"
    agent = "agent"


# =============================================================================
# Exception
# =============================================================================

class InvalidAidError(Exception):
    """
    Fail-closed AID verification error.

    Constructed ONLY with a reason string from the frozen vocabulary
    (see `.kiro/specs/m1-agent-identity.md` §2.9). Decoded payload contents
    MUST NOT be passed to this exception — `str(self) == self.reason`.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# =============================================================================
# AidClaims model
# =============================================================================

# Pre-computed enum value sets — referenced by validators.
_ARCHETYPE_VALUES: frozenset[str] = frozenset(a.value for a in Archetype)
_REGISTRATION_TYPE_VALUES: frozenset[str] = frozenset(
    r.value for r in RegistrationType
)


class AidClaims(BaseModel):
    """
    Verified AID payload. RFC 7519 + FSI extensions.

    Validators:
      - `iss` must equal `ISSUER`
      - `lei` must match `LEI_PATTERN` if non-null (None is accepted)
      - `archetype` must be one of `Archetype` enum values
      - `registration_type` must be one of `RegistrationType` enum values
    """

    model_config = ConfigDict(extra="forbid")

    # RFC 7519 registered claims
    iss: str
    sub: str = Field(..., min_length=1)
    aud: str = Field(..., min_length=1)
    exp: int
    iat: int
    nbf: int
    jti: str = Field(..., min_length=1)

    # FSI extension claims
    firm_id: str = Field(..., min_length=1)
    # `lei` has no default: the key MUST be present in the wire payload
    # (R1.3 — always present, possibly with value null). Missing the `lei`
    # key entirely raises Pydantic `ValidationError` → `invalid_claims`.
    lei: Optional[str]
    crd_number: str = Field(..., min_length=1)
    archetype: str  # enum-validated below
    role: Role
    authority_scope: list[str] = Field(default_factory=list)
    authority_excludes: list[str] = Field(default_factory=list)
    registration_type: str  # enum-validated below

    @field_validator("iss")
    @classmethod
    def _lock_issuer(cls, v: str) -> str:
        if v != ISSUER:
            raise ValueError(f"iss must be '{ISSUER}'")
        return v

    @field_validator("lei")
    @classmethod
    def _validate_lei(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(LEI_PATTERN, v):
            raise ValueError(f"Invalid LEI format (must match {LEI_PATTERN})")
        return v

    @field_validator("archetype")
    @classmethod
    def _validate_archetype(cls, v: str) -> str:
        if v not in _ARCHETYPE_VALUES:
            raise ValueError(
                f"archetype must be one of {sorted(_ARCHETYPE_VALUES)}"
            )
        return v

    @field_validator("registration_type")
    @classmethod
    def _validate_registration_type(cls, v: str) -> str:
        if v not in _REGISTRATION_TYPE_VALUES:
            raise ValueError(
                f"registration_type must be one of "
                f"{sorted(_REGISTRATION_TYPE_VALUES)}"
            )
        return v
