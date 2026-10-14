"""
M12 Onboarding Specialist -- main class.

Haiku-driven KYC + CIP workflow orchestrator. See
`.kiro/specs/m12-onboarding-specialist.md`.

Trust chain on every call:
  1. Validate AidClaims + authority scope
  2. Deterministic CIP format checks (name/DOB/address/tax_id)
  3. Sanctions screen via KycAdapterProtocol
  4. KYC vendor verify_identity
  5. BSA §326 alert audit emit on any CIP failure (no MNPI in payload)
  6. BD advisor principal-review gate (Rule 17)
  7. Success / terminal audit emit

Fail-closed throughout. `reason_code` is the sole error surface.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional

from m1_identity import AidClaims, Role
from m5_config_loader import RegistrationType
from m8_pipeline_engine.models import HitlGatePayload

from m12_supervisor.specialists._clients import (
    AuditClient,
    HitlApprovalVerifier,
    LLMProvider,
    MnpiSanitizer,
    PolicyClient,
    canonical_sha256,
)
from m12_supervisor.specialists.onboarding.models import (
    CipResult,
    KycAdapterProtocol,
    KycResult,
    KycVendorResult,
    OnboardingDecision,
    OnboardingRequest,
    _cip_validate_address,
    _cip_validate_dob,
    _cip_validate_name,
    _cip_validate_tax_id,
)


# =============================================================================
# Constants
# =============================================================================

_AUTHORITY_SCOPE_REQUIRED: str = "onboarding.start"

_BD_REGISTRATIONS: frozenset[str] = frozenset({
    RegistrationType.bd_only.value,
    RegistrationType.dual_registered.value,
})

_PERMITTED_ROLES: frozenset[Role] = frozenset({
    Role.advisor,
    Role.compliance_officer,
})

_HAIKU_MODEL_ID: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
_MAX_PROMPT_BYTES: int = 4096
_LLM_MAX_TOKENS: int = 2000


# =============================================================================
# OnboardingSpecialist
# =============================================================================


class OnboardingSpecialist:
    """Onboarding Specialist (Rule 13: Haiku).

    Stateless between calls. Construct once with injected Protocols
    + a `KycAdapterProtocol` adapter (Phase 3: `StubKycAdapter`).
    Every call returns an `OnboardingDecision` (never raises).
    """

    def __init__(
        self,
        *,
        policy_client: PolicyClient,
        mnpi_sanitizer: MnpiSanitizer,
        audit_client: AuditClient,
        llm_provider: LLMProvider,
        kyc_adapter: KycAdapterProtocol,
        hitl_verifier: Optional[HitlApprovalVerifier] = None,
        llm_model: str = _HAIKU_MODEL_ID,
    ) -> None:
        for name, dep in (
            ("policy_client", policy_client),
            ("mnpi_sanitizer", mnpi_sanitizer),
            ("audit_client", audit_client),
            ("llm_provider", llm_provider),
            ("kyc_adapter", kyc_adapter),
        ):
            if dep is None:
                raise ValueError(
                    f"OnboardingSpecialist missing dependency: {name}"
                )
        self._policy = policy_client
        self._mnpi = mnpi_sanitizer
        self._audit = audit_client
        self._llm = llm_provider
        self._kyc = kyc_adapter
        self._hitl = hitl_verifier
        self._llm_model = llm_model

    # -------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------

    def start_onboarding(
        self,
        request: OnboardingRequest,
        aid_claims: AidClaims,
        trace_id: str,
    ) -> OnboardingDecision:
        """Drive the onboarding workflow; return an OnboardingDecision.

        Never raises. BSA §326 alert is emitted on any CIP failure.
        """
        start = time.perf_counter()

        # --- Step 1: validate inputs ------------------------------------
        if not isinstance(request, OnboardingRequest):
            return self._terminal(
                status="failed",
                reason_code="onb_invalid_request",
                trace_id=trace_id,
                tenant_id=getattr(aid_claims, "firm_id", None) or "unknown",
                latency_ms=self._elapsed_ms(start),
                emit_audit=False,
            )
        if not isinstance(aid_claims, AidClaims):
            return self._terminal(
                status="failed",
                reason_code="onb_invalid_aid",
                trace_id=trace_id,
                tenant_id="unknown",
                latency_ms=self._elapsed_ms(start),
                emit_audit=False,
            )

        tenant_id = aid_claims.firm_id

        # --- Step 2: authority scope (Rule 8) ---------------------------
        scope_reason = self._check_authority_scope(aid_claims)
        if scope_reason is not None:
            return self._terminal(
                status="failed",
                reason_code=scope_reason,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
            )

        # --- Step 3: MNPI sanitise request (Rule 7) ---------------------
        # The sanitiser is called BEFORE the LLM path and BEFORE any
        # audit payload construction. The specialist itself uses the
        # raw values for the deterministic CIP checks -- those never
        # feed the LLM.
        try:
            self._mnpi.sanitize(aid_claims, request)
        except Exception:
            return self._terminal(
                status="failed",
                reason_code="onb_mnpi_sanitize_failed",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
            )

        # --- Step 4: deterministic CIP format checks --------------------
        today = datetime.now(timezone.utc).date()
        failed: list[str] = []
        if not _cip_validate_name(request.legal_name):
            failed.append("name")
        if not _cip_validate_dob(request.date_of_birth, today):
            failed.append("dob")
        if not _cip_validate_address(request.residential_address):
            failed.append("address")
        if not _cip_validate_tax_id(request.tax_id, request.country_code):
            failed.append("tax_id")

        # --- Step 5: sanctions screen (Appendix A.4 ordering) ----------
        try:
            sanctions_hit = self._kyc.screen_sanctions(
                name=request.legal_name,
                dob=request.date_of_birth,
                country=request.country_code,
            )
        except Exception:
            sanctions_hit = True  # fail-closed
        if sanctions_hit:
            failed.append("sanctions")

        cip = CipResult(
            passed=len(failed) == 0,
            failed_checks=failed,
        )

        if not cip.passed:
            # Emit BSA §326 alert FIRST, THEN return cip_failed.
            bsa_emitted = self._emit_bsa_326_alert(
                request=request,
                aid_claims=aid_claims,
                trace_id=trace_id,
                failed_checks=failed,
            )
            kyc_result = KycResult(
                cip=cip, vendor=None, sanctions_hit=sanctions_hit
            )
            reason = (
                "onb_sanctions_hit"
                if "sanctions" in failed and len(failed) == 1
                else "onb_cip_failed"
            )
            return self._terminal(
                status="cip_failed",
                reason_code=reason,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                kyc_result=kyc_result,
                bsa_326_alert_emitted=bsa_emitted,
            )

        # --- Step 6: KYC vendor verify_identity -------------------------
        try:
            vendor_result = self._kyc.verify_identity(
                name=request.legal_name,
                dob=request.date_of_birth,
                address=request.residential_address,
                tax_id_hash=request.tax_id_hash(),
            )
        except Exception:
            return self._terminal(
                status="failed",
                reason_code="onb_kyc_vendor_unavailable",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                kyc_result=KycResult(cip=cip, sanctions_hit=False),
            )

        if vendor_result.vendor_status == "denied":
            kyc_result = KycResult(
                cip=CipResult(passed=False, failed_checks=["tax_id"]),
                vendor=vendor_result,
                sanctions_hit=False,
            )
            bsa_emitted = self._emit_bsa_326_alert(
                request=request,
                aid_claims=aid_claims,
                trace_id=trace_id,
                failed_checks=["tax_id"],
            )
            return self._terminal(
                status="cip_failed",
                reason_code="onb_kyc_vendor_denied",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                kyc_result=kyc_result,
                bsa_326_alert_emitted=bsa_emitted,
            )

        kyc_result = KycResult(
            cip=cip, vendor=vendor_result, sanctions_hit=False
        )

        # --- Step 7: BD principal-review gate (Rule 17) ----------------
        if request.kind == "bd_advisor":
            gate_payload: Optional[HitlGatePayload] = None
            if self._hitl is not None:
                try:
                    gate_payload = self._hitl.build_gate_payload(
                        gate_id=1,
                        pipeline_run_id=self._run_id(trace_id),
                        thread_id=self._thread_id(request),
                        summary={
                            "gate_kind": "onboarding_principal_review",
                            "client_reference": request.client_reference,
                            "firm_id": request.firm_id,
                            "kind": request.kind,
                        },
                    )
                except Exception:
                    gate_payload = None
            return self._terminal(
                status="principal_review_queued",
                reason_code="onb_bd_principal_review",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                kyc_result=kyc_result,
                gate_payload=gate_payload,
            )

        # --- Step 8: success --------------------------------------------
        return self._terminal(
            status="cip_passed",
            reason_code=None,
            trace_id=trace_id,
            tenant_id=tenant_id,
            latency_ms=self._elapsed_ms(start),
            aid_claims=aid_claims,
            request=request,
            kyc_result=kyc_result,
        )

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _check_authority_scope(
        self, aid_claims: AidClaims
    ) -> Optional[str]:
        if aid_claims.role not in _PERMITTED_ROLES:
            return "onb_authority_scope_denied"
        scope = set(aid_claims.authority_scope or ())
        if _AUTHORITY_SCOPE_REQUIRED not in scope and "*" not in scope:
            return "onb_authority_scope_denied"
        excludes = set(aid_claims.authority_excludes or ())
        if _AUTHORITY_SCOPE_REQUIRED in excludes:
            return "onb_authority_scope_denied"
        return None

    def _emit_bsa_326_alert(
        self,
        *,
        request: OnboardingRequest,
        aid_claims: AidClaims,
        trace_id: str,
        failed_checks: list[str],
    ) -> bool:
        """Emit a BSA §326 CIP-failure alert through the AuditClient.

        Payload whitelist (Appendix A.3): no MNPI fields. Return True
        iff the audit emit succeeded; False otherwise (the parent
        caller then sets `bsa_326_alert_emitted=False` on the decision
        and surfaces `onb_bsa_alert_failed` only if no other terminal
        reason dominates).
        """
        payload = {
            "source": "m12.onboarding_specialist",
            "event_type": "bsa_326_cip_failure",
            "module": "m12",
            "action": "onboarding.cip_check",
            "trace_id": trace_id,
            "tenant_id": aid_claims.firm_id,
            "firm_id": request.firm_id,
            "actor_id": aid_claims.sub,
            "client_reference": request.client_reference,
            "failed_checks": sorted(failed_checks),
            "decision": "deny",
            "reason": "cip_failed",
            "role": aid_claims.role.value,
            "archetype": aid_claims.archetype,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._audit.emit(payload)
            return True
        except Exception:
            return False

    @staticmethod
    def _thread_id(request: OnboardingRequest) -> str:
        """Deterministic thread_id for HITL gates.

        `client_reference` is ≤ 64 chars. The "onb-" prefix keeps the
        namespace distinct from execution's "exec-" prefix.
        """
        base = request.client_reference
        return ("onb-" + base)[:64]

    @staticmethod
    def _run_id(trace_id: str) -> str:
        return "onb-run-" + trace_id[:24].replace("/", "-")

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.perf_counter() - start) * 1000)

    # -------------------------------------------------------------------
    # Terminal + audit
    # -------------------------------------------------------------------

    def _terminal(
        self,
        *,
        status: str,
        reason_code: Optional[str],
        trace_id: str,
        tenant_id: str,
        latency_ms: int,
        aid_claims: Optional[AidClaims] = None,
        request: Optional[OnboardingRequest] = None,
        kyc_result: Optional[KycResult] = None,
        gate_payload: Optional[HitlGatePayload] = None,
        bsa_326_alert_emitted: bool = False,
        emit_audit: bool = True,
    ) -> OnboardingDecision:
        """Build an OnboardingDecision + emit terminal audit.

        Identical fail-closed semantics to ExecutionSpecialist._terminal.
        """
        decision = OnboardingDecision(
            status=status,  # type: ignore[arg-type]
            kyc_result=kyc_result,
            gate_payload=gate_payload,
            trace_id=trace_id,
            tenant_id=tenant_id,
            reason_code=reason_code,
            latency_ms=latency_ms,
            bsa_326_alert_emitted=bsa_326_alert_emitted,
        )
        if not emit_audit:
            return decision
        try:
            self._audit.emit(
                self._build_audit_entry(
                    decision=decision,
                    aid_claims=aid_claims,
                    request=request,
                    kyc_result=kyc_result,
                )
            )
        except Exception:
            if decision.status in ("cip_passed", "principal_review_queued"):
                return OnboardingDecision(
                    status="failed",
                    kyc_result=kyc_result,
                    gate_payload=None,
                    trace_id=trace_id,
                    tenant_id=tenant_id,
                    reason_code="onb_audit_failed",
                    latency_ms=latency_ms,
                    bsa_326_alert_emitted=bsa_326_alert_emitted,
                )
            return OnboardingDecision(
                status=decision.status,
                kyc_result=kyc_result,
                gate_payload=gate_payload,
                trace_id=trace_id,
                tenant_id=tenant_id,
                reason_code="onb_audit_failed",
                latency_ms=latency_ms,
                bsa_326_alert_emitted=bsa_326_alert_emitted,
            )
        return decision

    @staticmethod
    def _build_audit_entry(
        *,
        decision: OnboardingDecision,
        aid_claims: Optional[AidClaims],
        request: Optional[OnboardingRequest],
        kyc_result: Optional[KycResult],
    ) -> dict:
        """Build a dict-shaped audit entry for M10.

        MNPI hygiene: `input_hash` covers only non-MNPI fields
        (client_reference + kind + country_code + firm_id). Raw
        tax_id / DOB / address are NEVER hashed into the audit entry.
        """
        actor_id = aid_claims.sub if aid_claims else "unknown"
        firm_id = request.firm_id if request else decision.tenant_id
        input_payload = (
            {
                "client_reference": request.client_reference,
                "country_code": request.country_code,
                "firm_id": request.firm_id,
                "kind": request.kind,
            }
            if request
            else {}
        )
        output_payload = (
            {
                "cip_passed": kyc_result.cip.passed,
                "failed_checks": sorted(kyc_result.cip.failed_checks),
                "sanctions_hit": kyc_result.sanctions_hit,
                "vendor_status": (
                    kyc_result.vendor.vendor_status
                    if kyc_result.vendor is not None
                    else None
                ),
            }
            if kyc_result is not None
            else {}
        )
        decision_map = {
            "cip_passed": "allow",
            "cip_pending": "allow",
            "kyc_pending": "allow",
            "principal_review_queued": "escalate",
            "cip_failed": "deny",
            "failed": "error",
        }
        return {
            "source": "m12.onboarding_specialist",
            "event_type": "onboarding.start",
            "trace_id": decision.trace_id,
            "tenant_id": decision.tenant_id,
            "firm_id": firm_id,
            "actor_id": actor_id,
            "action": "onboarding.start",
            "module": "m12",
            "target_type": "OnboardingRequest",
            "target_id": (
                request.client_reference if request else None
            ),
            "decision": decision_map[decision.status],
            "reason": decision.reason_code,
            "input_hash": canonical_sha256(input_payload),
            "output_hash": canonical_sha256(output_payload),
            "latency_ms": decision.latency_ms,
            "archetype": aid_claims.archetype if aid_claims else None,
            "role": aid_claims.role.value if aid_claims else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bsa_326_alert_emitted": decision.bsa_326_alert_emitted,
        }


__all__ = ["OnboardingSpecialist"]
