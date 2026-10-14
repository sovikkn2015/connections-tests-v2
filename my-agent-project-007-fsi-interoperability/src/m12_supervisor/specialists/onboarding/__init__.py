"""
M12 Onboarding Specialist -- public surface.

The 5th specialist in the M12 dispatch map. Haiku-driven KYC + CIP
workflow orchestrator per BSA §326 (Customer Identification Program).
See `.kiro/specs/m12-onboarding-specialist.md`.
"""

from __future__ import annotations

from m12_supervisor.specialists.onboarding.models import (
    CipResult,
    KycAdapterProtocol,
    KycResult,
    KycVendorResult,
    OnboardingDecision,
    OnboardingRequest,
    StubKycAdapter,
    VALID_ONBOARDING_REASONS,
)
from m12_supervisor.specialists.onboarding.specialist import (
    OnboardingSpecialist,
)

SPECIALIST_NAME: str = "onboarding"

__all__ = [
    "OnboardingSpecialist",
    "OnboardingRequest",
    "OnboardingDecision",
    "KycResult",
    "CipResult",
    "KycVendorResult",
    "KycAdapterProtocol",
    "StubKycAdapter",
    "VALID_ONBOARDING_REASONS",
    "SPECIALIST_NAME",
]
