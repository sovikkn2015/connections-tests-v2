"""
Gap 5 — AccountTypeEngine + request/decision models.

Composes fiduciary + PTE 2020-02 gates into a single deterministic
outcome and emits to the injected M10 AuditClient on every call.

Fail-closed, no LLM, no fallback (steering rules 5, 8, 14).

See .kiro/specs/gap5-erisa-account-type.md R2, R5, R7, R8.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m5_config_loader import SuitabilityStandard

from compliance.gap5_erisa_account_type._types import (
    ACCOUNT_TYPE_DECISION_SCHEMA_VERSION,
    AccountType,
    AuditWriteFailed,
    Outcome,
)
from compliance.gap5_erisa_account_type.audit_client import AuditClient
from compliance.gap5_erisa_account_type.gates import (
    fiduciary_gate,
    pte_2020_02_gate,
)

# =============================================================================
# Rationale sanitiser — R2.4
# =============================================================================

# Allowed characters in the machine-facing rationale.
_RATIONALE_RE: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9 _\-\.\(\)/§]+$"
)


# =============================================================================
# Request
# =============================================================================


class AccountTypeRequest(BaseModel):
    """See .kiro/specs/gap5-erisa-account-type.md §2.1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str = Field(
        min_length=8, max_length=64, pattern=r"^[A-Za-z0-9\-]+$"
    )
    account_type: AccountType
    suitability_standard: SuitabilityStandard
    proposed_doc_path: Literal["reg_bi", "fiduciary"]
    is_rollover: bool = False
    requested_by: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$"
    )


# =============================================================================
# Decision
# =============================================================================


class AccountTypeDecision(BaseModel):
    """R2.1 frozen decision record. Serialised into the audit payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: Outcome
    account_type: AccountType
    rule_ids: tuple[str, ...]
    wsp_sections: tuple[str, ...]
    rationale: str = Field(max_length=200)
    suitability_standard: SuitabilityStandard
    is_rollover: bool
    trace_id: str

    @field_validator("rationale")
    @classmethod
    def _rationale_charset(cls, v: str) -> str:
        if not _RATIONALE_RE.match(v):
            raise ValueError(
                "rationale must match the safe charset "
                "[A-Za-z0-9 _\\-\\.\\(\\)/§]"
            )
        return v


# =============================================================================
# Engine
# =============================================================================


class AccountTypeEngine:
    """Stateless composer. One instance per service; audit is injected."""

    def __init__(self, audit_client: AuditClient) -> None:
        self._audit = audit_client

    def evaluate(
        self, request: AccountTypeRequest
    ) -> AccountTypeDecision:
        fid = fiduciary_gate(
            account_type=request.account_type,
            suitability_standard=request.suitability_standard,
            proposed_doc_path=request.proposed_doc_path,
        )
        pte = pte_2020_02_gate(
            account_type=request.account_type,
            is_rollover=request.is_rollover,
        )

        rule_ids: list[str] = []
        wsp_sections: list[str] = []

        # Precedence — R5.2
        # 1. Fiduciary gate fires → BLOCK; PTE attribution still added.
        # 2. Only PTE fires → REQUIRE_ENHANCED_DOC.
        # 3. Neither fires → ALLOW.
        if fid.triggered:
            outcome = Outcome.BLOCK
            rule_ids.append(fid.rule_id)
            wsp_sections.append(fid.wsp_section)
            if pte.triggered:
                rule_ids.append(pte.rule_id)
                wsp_sections.append(pte.wsp_section)
            rationale = (
                f"BLOCK reg_bi path for {request.account_type.value} "
                f"under fiduciary standard"
            )
        elif pte.triggered:
            outcome = Outcome.REQUIRE_ENHANCED_DOC
            rule_ids.append(pte.rule_id)
            wsp_sections.append(pte.wsp_section)
            rationale = (
                f"PTE 2020-02 rollover into {request.account_type.value} "
                f"requires enhanced doc"
            )
        else:
            outcome = Outcome.ALLOW
            rationale = f"ALLOW {request.account_type.value}"

        decision = AccountTypeDecision(
            outcome=outcome,
            account_type=request.account_type,
            rule_ids=tuple(rule_ids),
            wsp_sections=tuple(wsp_sections),
            rationale=rationale,
            suitability_standard=request.suitability_standard,
            is_rollover=request.is_rollover,
            trace_id=request.trace_id,
        )

        self._emit_audit(decision, request)
        return decision

    # ------------------------------------------------------------------
    # Audit emission — fail-closed (R7.2)
    # ------------------------------------------------------------------

    def _emit_audit(
        self,
        decision: AccountTypeDecision,
        request: AccountTypeRequest,
    ) -> None:
        payload: dict = {
            "gap": "gap5",
            "schema_version": ACCOUNT_TYPE_DECISION_SCHEMA_VERSION,
            "requested_by": request.requested_by,
            "decision": decision.model_dump(mode="json"),
        }
        try:
            self._audit.write(payload)
        except Exception as exc:  # noqa: BLE001 — translate any failure
            raise AuditWriteFailed("audit_write_failed") from exc
