"""
M12 Supervisor -- Specialists subpackage.

Houses the 2 Phase-3 downstream specialists that M12 Supervisor
fan-outs to: Execution and Onboarding. Both specialists consume the
same Protocol client shapes defined in `_clients.py` so their trust
pipelines are identical at the integration boundary.

Boundary rule: anything under `m12_supervisor.specialists.*` imports
ONLY from:
  - Python stdlib, pydantic
  - m1_identity (AidClaims, Role)
  - m5_config_loader (enums)
  - m8_pipeline_engine.models + m8_pipeline_engine.hitl
    (HitlApproval / HitlGatePayload shapes + HMAC helpers)
  - m12_supervisor.specialists.* (siblings)

Upstream trust modules (M2/M3/M4/M6/M10/M11/M13, compliance.*) are
reached ONLY via the duck-typed Protocols in `_clients.py` -- no
direct import. See `.kiro/specs/m12-execution-specialist.md` §2.7 and
`.kiro/specs/m12-onboarding-specialist.md` §2.6 for the full rule.

Enforced by `tests/security/test_m12_specialists_module_boundary.py`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Optional

from m12_supervisor.specialists._clients import (
    AuditClient,
    FakeAuditClient,
    FakeGatewayClient,
    FakeHitlVerifier,
    FakeLLMProvider,
    FakeMnpiSanitizer,
    FakePolicyClient,
    GatewayClient,
    GatewayResultShape,
    HitlApprovalVerifier,
    LLMProvider,
    MnpiSanitizer,
    PolicyClient,
    PolicyResultShape,
    canonical_sha256,
)
from m12_supervisor.specialists.execution import (
    ExecutionDecision,
    ExecutionRequest,
    ExecutionSpecialist,
    OrderTicket,
    VALID_EXECUTION_REASONS,
    build_idempotency_key,
)
from m12_supervisor.specialists.execution import (
    SPECIALIST_NAME as _EXECUTION_NAME,
)
from m12_supervisor.specialists.onboarding import (
    CipResult,
    KycAdapterProtocol,
    KycResult,
    KycVendorResult,
    OnboardingDecision,
    OnboardingRequest,
    OnboardingSpecialist,
    StubKycAdapter,
    VALID_ONBOARDING_REASONS,
)
from m12_supervisor.specialists.onboarding import (
    SPECIALIST_NAME as _ONBOARDING_NAME,
)

#: Registry of specialist NAME -> class. Immutable. M12 Supervisor's
#: `get_specialist(name)` helper reads this; the caller is responsible
#: for instantiating with injected Protocol clients. Additional
#: specialists (client_service, research, compliance) land in future
#: commits -- their absence here does not mean they don't exist, just
#: that they are wired directly via M12 `dispatch()` today.
SPECIALIST_DISPATCH: Mapping[str, type] = MappingProxyType({
    _EXECUTION_NAME: ExecutionSpecialist,
    _ONBOARDING_NAME: OnboardingSpecialist,
})


def get_specialist(name: str) -> Optional[type]:
    """Return specialist CLASS by name, or None if unknown.

    Caller constructs the specialist with its injected Protocol
    clients. Example:

        cls = get_specialist("execution")
        assert cls is not None
        spec = cls(policy_client=..., mnpi_sanitizer=..., ...)
        decision = spec.prepare_order(request, aid_claims, trace_id)
    """
    return SPECIALIST_DISPATCH.get(name)


__all__ = [
    # Dispatch
    "SPECIALIST_DISPATCH",
    "get_specialist",
    # Protocols
    "PolicyClient",
    "MnpiSanitizer",
    "GatewayClient",
    "AuditClient",
    "LLMProvider",
    "HitlApprovalVerifier",
    "PolicyResultShape",
    "GatewayResultShape",
    # Fakes
    "FakePolicyClient",
    "FakeMnpiSanitizer",
    "FakeGatewayClient",
    "FakeAuditClient",
    "FakeLLMProvider",
    "FakeHitlVerifier",
    # Helpers
    "canonical_sha256",
    "build_idempotency_key",
    # Execution
    "ExecutionSpecialist",
    "ExecutionRequest",
    "ExecutionDecision",
    "OrderTicket",
    "VALID_EXECUTION_REASONS",
    # Onboarding
    "OnboardingSpecialist",
    "OnboardingRequest",
    "OnboardingDecision",
    "KycResult",
    "CipResult",
    "KycVendorResult",
    "KycAdapterProtocol",
    "StubKycAdapter",
    "VALID_ONBOARDING_REASONS",
]
