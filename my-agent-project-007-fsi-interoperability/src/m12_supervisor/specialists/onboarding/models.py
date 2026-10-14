"""
M12 Onboarding Specialist -- Pydantic v2 models + KYC Protocol + stub.

All models are frozen + extra="forbid". BSA §326 (Customer
Identification Program) requires 4 mandatory checks: name, DOB,
residential address, tax id.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m8_pipeline_engine.models import HitlGatePayload


# =============================================================================
# Closed reason-code vocabulary (Appendix A / Onboarding spec §2.4)
# =============================================================================

VALID_ONBOARDING_REASONS: frozenset[str] = frozenset({
    "onb_invalid_request",
    "onb_invalid_aid",
    "onb_authority_scope_denied",
    "onb_mnpi_sanitize_failed",
    "onb_cip_failed",
    "onb_kyc_vendor_unavailable",
    "onb_kyc_vendor_denied",
    "onb_sanctions_hit",
    "onb_bd_principal_review",
    "onb_audit_failed",
    "onb_bsa_alert_failed",
    "onb_unknown",
})


# =============================================================================
# CIP validators (Appendix A.1)
# =============================================================================

_US_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
_US_ITIN_RE = re.compile(r"^9\d{2}-?\d{2}-?\d{4}$")
_US_EIN_RE = re.compile(r"^\d{2}-?\d{7}$")


def _cip_validate_name(name: str) -> bool:
    s = name.strip()
    return len(s) >= 2 and not s.isdigit()


def _cip_validate_dob(dob: date, now_date: date) -> bool:
    days = (now_date - dob).days
    if days < 0:
        return False
    return days >= int(18 * 365.25)


def _cip_validate_address(addr: str) -> bool:
    s = addr.strip()
    return len(s) >= 10 and any(c.isdigit() for c in s)


def _cip_validate_tax_id(tax_id: str, country_code: str) -> bool:
    s = tax_id.strip()
    if country_code.upper() == "US":
        return bool(
            _US_SSN_RE.match(s)
            or _US_ITIN_RE.match(s)
            or _US_EIN_RE.match(s)
        )
    return len(s) >= 5


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# =============================================================================
# Models
# =============================================================================


class OnboardingRequest(BaseModel):
    """Input to `OnboardingSpecialist.start_onboarding`.

    `tax_id`, `date_of_birth`, `residential_address` are MNPI. They
    MUST NOT appear in any audit payload, LLM prompt, or BSA alert;
    only metadata (which checks passed/failed) is persisted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["retail_client", "bd_advisor"]
    client_reference: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date
    residential_address: str = Field(min_length=1, max_length=500)
    tax_id: str = Field(min_length=1, max_length=64)
    country_code: str = Field(min_length=2, max_length=3)
    firm_id: str = Field(min_length=1, max_length=100)
    aid_token: str = Field(min_length=1, max_length=8192)
    user_utterance: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("country_code")
    @classmethod
    def _uppercase_country(cls, v: str) -> str:
        return v.upper()

    def tax_id_hash(self) -> str:
        """Deterministic SHA-256 of tax_id for vendor adapter passing.

        Vendors receive the hash, not the raw SSN -- mirrors Plaid /
        Stripe identity-verification patterns.
        """
        return _sha256(self.tax_id)


class CipResult(BaseModel):
    """BSA §326 CIP outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    failed_checks: list[str] = Field(default_factory=list)

    @field_validator("failed_checks")
    @classmethod
    def _check_names_whitelisted(cls, v: list[str]) -> list[str]:
        allowed = {"name", "dob", "address", "tax_id", "sanctions"}
        bad = set(v) - allowed
        if bad:
            raise ValueError(
                f"failed_checks contains non-whitelisted names: {sorted(bad)}"
            )
        return v


class KycVendorResult(BaseModel):
    """Result from the KYC vendor adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor_name: str = Field(min_length=1, max_length=50)
    vendor_status: Literal["approved", "manual_review", "denied"]
    vendor_reference_id: str = Field(min_length=1, max_length=100)


class KycResult(BaseModel):
    """Composite KYC outcome: CIP + vendor verification + sanctions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cip: CipResult
    vendor: Optional[KycVendorResult] = None
    sanctions_hit: bool = False


class OnboardingDecision(BaseModel):
    """Public return of `start_onboarding`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal[
        "kyc_pending",
        "cip_pending",
        "cip_passed",
        "cip_failed",
        "principal_review_queued",
        "failed",
    ]
    kyc_result: Optional[KycResult] = None
    gate_payload: Optional[HitlGatePayload] = None
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    reason_code: Optional[str] = None
    latency_ms: int = Field(ge=0)
    bsa_326_alert_emitted: bool = False

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocab(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_ONBOARDING_REASONS:
            raise ValueError(
                f"reason_code {v!r} not in VALID_ONBOARDING_REASONS"
            )
        return v


# =============================================================================
# KycAdapterProtocol + stub
# =============================================================================


@runtime_checkable
class KycAdapterProtocol(Protocol):
    """KYC + sanctions adapter contract.

    Production adapters (Jumio, Onfido, Trulioo) wrap a vendor HTTP
    API. They MUST go through M6 at the call site when finally wired
    (Phase 4+); the Protocol is vendor-agnostic.

    The specialist NEVER passes a raw SSN. `tax_id_hash` is the
    SHA-256 of the client's tax_id -- vendors match against this in
    their own hashed-index.
    """

    vendor_name: str

    def verify_identity(
        self,
        *,
        name: str,
        dob: date,
        address: str,
        tax_id_hash: str,
    ) -> KycVendorResult:
        ...

    def screen_sanctions(
        self,
        *,
        name: str,
        dob: date,
        country: str,
    ) -> bool:
        ...


class StubKycAdapter:
    """Deterministic stub adapter for Phase 3 tests.

    Behaviour (deterministic / no network):
      - `verify_identity`:
        - tax_id_hash starts with "f"+"a"+"i"+"l"... (i.e., hash of a
          tax_id beginning with "FAIL") -> vendor_status="denied"
        - hash starts with "9000...":   vendor_status="manual_review"
        - else:                         vendor_status="approved"
      - `screen_sanctions`:
        - country is "KP" or "IR":      returns True
        - name starts with "SANCTIONED": returns True
        - else:                         returns False

    Real vendor adapter lands in Phase 4; Protocol contract stays stable.
    """

    vendor_name = "stub_kyc"

    def verify_identity(
        self,
        *,
        name: str,
        dob: date,
        address: str,
        tax_id_hash: str,
    ) -> KycVendorResult:
        # Denied prefix -- hash of "FAIL..." starts with a deterministic
        # value; we match on the known hash prefix of literal "FAIL".
        fail_hash_prefix = _sha256("FAIL")[:8]
        manual_prefix = _sha256("MANUAL")[:8]
        if tax_id_hash.startswith(fail_hash_prefix):
            status: Literal["approved", "manual_review", "denied"] = "denied"
        elif tax_id_hash.startswith(manual_prefix):
            status = "manual_review"
        else:
            status = "approved"
        ref = "STUB-" + tax_id_hash[:12]
        return KycVendorResult(
            vendor_name=self.vendor_name,
            vendor_status=status,
            vendor_reference_id=ref,
        )

    def screen_sanctions(
        self,
        *,
        name: str,
        dob: date,
        country: str,
    ) -> bool:
        if country.upper() in ("KP", "IR", "SY", "CU"):
            return True
        if name.strip().upper().startswith("SANCTIONED"):
            return True
        return False


__all__ = [
    "OnboardingRequest",
    "OnboardingDecision",
    "CipResult",
    "KycResult",
    "KycVendorResult",
    "KycAdapterProtocol",
    "StubKycAdapter",
    "VALID_ONBOARDING_REASONS",
    "_cip_validate_name",
    "_cip_validate_dob",
    "_cip_validate_address",
    "_cip_validate_tax_id",
]
