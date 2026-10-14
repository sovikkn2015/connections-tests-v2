"""
M12 Execution Specialist -- Pydantic v2 models + helpers.

All models are frozen + extra="forbid" per the fail-loud contract
used across M8/M9/M12.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m8_pipeline_engine.models import HitlApproval, HitlGatePayload


# =============================================================================
# Closed reason-code vocabulary (Appendix A / Execution spec §2.4)
# =============================================================================

VALID_EXECUTION_REASONS: frozenset[str] = frozenset({
    "exec_invalid_request",
    "exec_invalid_aid",
    "exec_authority_scope_denied",
    "exec_mnpi_sanitize_failed",
    "exec_llm_failed",
    "exec_policy_denied",
    "exec_policy_escalated",
    "exec_hitl_required",
    "exec_hitl_token_invalid",
    "exec_hitl_token_expired",
    "exec_principal_review_required",
    "exec_gateway_unavailable",
    "exec_gateway_denied",
    "exec_audit_failed",
    "exec_unknown",
})


# =============================================================================
# OrderTicket
# =============================================================================

# Acceptable instrument-symbol shapes: bare ticker, CUSIP, ISIN, option
# symbols with spaces are excluded for Phase 3 (equities + ETFs only).
_INSTRUMENT_RE = r"^[A-Z0-9\.\-/]{1,32}$"


class OrderTicket(BaseModel):
    """Draft order ticket.

    Produced by Haiku after MNPI sanitisation, or supplied verbatim by
    the channel in the `ExecutionRequest.proposed_ticket` field.

    Field-level notes:
      - `quantity`: Decimal for lossless comparison (tests can pin a
        golden hash).
      - `limit_price` required when `order_type in {"limit", "stop_limit"}`.
      - `time_in_force` default "day" matches US equity markets.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str = Field(min_length=1, max_length=64)
    account_id: str = Field(min_length=1, max_length=64)
    # Pattern is enforced AFTER uppercase normalization via the
    # mode="before" validator below -- don't duplicate via Field
    # pattern=... (that would run before normalization and reject
    # lower-case input).
    instrument_symbol: str = Field(min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=Decimal("0"))
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("instrument_symbol", mode="before")
    @classmethod
    def _uppercase_symbol(cls, v: Any) -> Any:
        """Uppercase + pattern check in one validator.

        Runs BEFORE Pydantic's string-pattern constraint so that
        ``"nvda"`` normalises to ``"NVDA"`` without the constraint
        rejecting the raw lower-case input.
        """
        import re as _re
        if not isinstance(v, str):
            return v
        v_upper = v.upper()
        if not _re.match(_INSTRUMENT_RE, v_upper):
            raise ValueError(
                f"instrument_symbol {v!r} does not match pattern "
                f"{_INSTRUMENT_RE!r}"
            )
        return v_upper

    def to_canonical_payload(self) -> dict:
        """Return a JSON-safe dict for the MCP order-submit payload.

        Decimal is rendered via str() -- lossless and deterministic.
        """
        return {
            "client_id": self.client_id,
            "account_id": self.account_id,
            "instrument_symbol": self.instrument_symbol,
            "side": self.side,
            "quantity": str(self.quantity),
            "order_type": self.order_type,
            "limit_price": (
                str(self.limit_price) if self.limit_price is not None else None
            ),
            "time_in_force": self.time_in_force,
            "notes": self.notes,
        }


# =============================================================================
# ExecutionRequest
# =============================================================================


class ExecutionRequest(BaseModel):
    """Input to `ExecutionSpecialist.prepare_order`.

    The specialist never mutates this object. `user_utterance` is
    bounded to prevent prompt-injection from unbounded inputs.
    `restricted_list` and `trading_window_open` are supplied by the
    channel (sourced from M2 context earlier in the request).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_utterance: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=1, max_length=64)
    account_id: str = Field(min_length=1, max_length=64)
    proposed_ticket: Optional[OrderTicket] = None
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    firm_id: str = Field(min_length=1, max_length=100)
    aid_token: str = Field(min_length=1, max_length=8192)
    hitl_approval: Optional[HitlApproval] = None
    restricted_list: list[str] = Field(default_factory=list)
    trading_window_open: bool = True
    principal_review_threshold_usd: Optional[Decimal] = Field(
        default=None, ge=Decimal("0")
    )
    # thread_id binds HITL approval + gate payload to a consistent
    # identifier. Default is derived from idempotency_key prefix so
    # the same request produces the same thread_id deterministically.
    thread_id: Optional[str] = None


# =============================================================================
# ExecutionDecision
# =============================================================================


class ExecutionDecision(BaseModel):
    """Public return of `prepare_order`.

    Exactly one of (gate_payload, mcp_order_id) is expected per
    terminal status:
      - drafted / compliance_denied / failed -> both None
      - hitl_required                         -> gate_payload set
      - submitted                             -> mcp_order_id set
      - rejected                              -> gate_payload set if HITL
                                                 rejected, else None
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal[
        "drafted",
        "compliance_denied",
        "hitl_required",
        "submitted",
        "rejected",
        "failed",
    ]
    order_ticket: Optional[OrderTicket] = None
    gate_payload: Optional[HitlGatePayload] = None
    mcp_order_id: Optional[str] = None
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    reason_code: Optional[str] = None
    latency_ms: int = Field(ge=0)
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocab(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_EXECUTION_REASONS:
            raise ValueError(
                f"reason_code {v!r} not in VALID_EXECUTION_REASONS"
            )
        return v


# =============================================================================
# Helpers
# =============================================================================


def build_idempotency_key(
    *,
    client_id: str,
    account_id: str,
    instrument_symbol: str,
    side: str,
    quantity: Decimal,
    timestamp_bucket_minute: int,
) -> str:
    """Build the canonical SHA-256 idempotency key (Appendix A.1).

    Canonical JSON: sorted keys, compact separators. Decimal is rendered
    via `str()` for lossless determinism. Side is lower-cased.
    Instrument symbol upper-cased.

    Example:
        >>> key = build_idempotency_key(
        ...     client_id="CLT-1",
        ...     account_id="ACC-1",
        ...     instrument_symbol="nvda",
        ...     side="BUY",
        ...     quantity=Decimal("500"),
        ...     timestamp_bucket_minute=29_100_000,
        ... )
        >>> len(key)
        64
    """
    payload = {
        "account_id": account_id,
        "client_id": client_id,
        "instrument_symbol": instrument_symbol.upper(),
        "quantity": str(quantity),
        "side": side.lower(),
        "timestamp_bucket_minute": int(timestamp_bucket_minute),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = [
    "OrderTicket",
    "ExecutionRequest",
    "ExecutionDecision",
    "VALID_EXECUTION_REASONS",
    "build_idempotency_key",
]
