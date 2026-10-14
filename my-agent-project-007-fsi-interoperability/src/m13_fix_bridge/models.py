"""Pydantic v2 strict models for the M13 FIX Bridge.

Every input model uses ``model_config = ConfigDict(extra="forbid",
strict=True)`` per Steering Rule 32. Enum values are raw FIX 4.4 tag
strings so we never mis-encode when building messages.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


# ---------------------------------------------------------------------------
# FIX enum aliases (raw tag-value strings)
# ---------------------------------------------------------------------------

FixSide = Literal["1", "2", "5", "6"]
FixOrdType = Literal["1", "2", "3", "4"]
FixTimeInForce = Literal["0", "1", "2", "3", "4", "6"]

# Inbound-only enums (ExecutionReport / status codes)
FixExecType = Literal["0", "1", "2", "4", "5", "8", "C"]
FixOrdStatus = Literal["0", "1", "2", "4", "5", "8", "C"]

LogonStatus = Literal[
    "DISCONNECTED",
    "LOGON_SENT",
    "ACTIVE",
    "LOGOUT_SENT",
]


# ---------------------------------------------------------------------------
# Regex patterns (compiled once at import time)
# ---------------------------------------------------------------------------

_SYMBOL_RX = re.compile(r"^[A-Z0-9][A-Z0-9.\-/]{0,31}$")
_ID_RX = re.compile(r"^[A-Za-z0-9._\-:]{1,64}$")
_VENUE_RX = re.compile(r"^[a-z0-9_\-]{1,32}$")
_ACCOUNT_RX = re.compile(r"^[A-Za-z0-9._\-]{1,32}$")


def _validate_symbol(v: str) -> str:
    if not isinstance(v, str) or not _SYMBOL_RX.fullmatch(v):
        raise ValueError("symbol must be uppercase ASCII 1-32 chars, see FIX Tag 55")
    return v


def _validate_venue(v: str) -> str:
    if not isinstance(v, str) or not _VENUE_RX.fullmatch(v):
        raise ValueError("venue must match ^[a-z0-9_-]{1,32}$")
    return v


def _validate_id(v: str, *, field_name: str) -> str:
    if not isinstance(v, str) or not _ID_RX.fullmatch(v):
        raise ValueError(f"{field_name} must match ^[A-Za-z0-9._\\-:]{{1,64}}$")
    return v


def _validate_account(v: str) -> str:
    if not isinstance(v, str) or not _ACCOUNT_RX.fullmatch(v):
        raise ValueError("account must match ^[A-Za-z0-9._-]{1,32}$")
    return v


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if isinstance(dt, str):
        # Accept ISO-8601 strings. FastAPI may hand us the Z-suffixed form.
        s = dt.replace("Z", "+00:00") if dt.endswith("Z") else dt
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be ISO-8601 datetime or datetime object"
            ) from exc
    if not isinstance(dt, datetime):
        raise ValueError(f"{field_name} must be datetime")
    if dt.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware (UTC)")
    # Convert to UTC to normalise.
    return dt.astimezone(timezone.utc)


def _validate_qty(v: Decimal) -> Decimal:
    if isinstance(v, str):
        try:
            v = Decimal(v)
        except Exception as exc:
            raise ValueError("order_qty must be a valid Decimal") from exc
    if isinstance(v, int) and not isinstance(v, bool):
        v = Decimal(v)
    if not isinstance(v, Decimal):
        raise ValueError("order_qty must be Decimal")
    if v <= 0:
        raise ValueError("order_qty must be > 0")
    # Integer digits check (max 20).
    s = format(abs(v), "f")
    if "." in s:
        int_part, dec_part = s.split(".", 1)
        if len(dec_part.rstrip("0")) > 8:
            raise ValueError("order_qty must have at most 8 decimal places")
    else:
        int_part = s
    if len(int_part) > 20:
        raise ValueError("order_qty must have at most 20 integer digits")
    return v


def _validate_price(v: Decimal | None) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            v = Decimal(v)
        except Exception as exc:
            raise ValueError("price must be a valid Decimal") from exc
    if isinstance(v, int) and not isinstance(v, bool):
        v = Decimal(v)
    if not isinstance(v, Decimal):
        raise ValueError("price must be Decimal")
    if v <= 0:
        raise ValueError("price must be > 0")
    return v


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class NewOrderSingleInput(BaseModel):
    """FIX 4.4 NewOrderSingle (MsgType D)."""

    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    cl_ord_id: str = Field(min_length=1, max_length=64)
    venue: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=32)
    side: FixSide
    ord_type: FixOrdType
    order_qty: Decimal
    price: Optional[Decimal] = None
    time_in_force: FixTimeInForce
    transact_time: datetime
    account: str = Field(min_length=1, max_length=32)

    @field_validator("cl_ord_id")
    @classmethod
    def _v_cl_ord_id(cls, v: str) -> str:
        return _validate_id(v, field_name="cl_ord_id")

    @field_validator("venue")
    @classmethod
    def _v_venue(cls, v: str) -> str:
        return _validate_venue(v)

    @field_validator("symbol")
    @classmethod
    def _v_symbol(cls, v: str) -> str:
        return _validate_symbol(v)

    @field_validator("account")
    @classmethod
    def _v_account(cls, v: str) -> str:
        return _validate_account(v)

    @field_validator("order_qty", mode="before")
    @classmethod
    def _v_qty(cls, v: Decimal) -> Decimal:
        return _validate_qty(v)

    @field_validator("price", mode="before")
    @classmethod
    def _v_price(cls, v: Decimal | None) -> Decimal | None:
        return _validate_price(v)

    @field_validator("transact_time", mode="before")
    @classmethod
    def _v_transact_time(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "transact_time")

    @model_validator(mode="after")
    def _price_matches_ord_type(self) -> Self:
        ot = self.ord_type
        if ot == "1":  # Market — forbidden
            if self.price is not None:
                raise ValueError("price must be None when ord_type=1 (Market)")
        elif ot in ("2", "4"):  # Limit or StopLimit — required
            if self.price is None:
                raise ValueError(
                    "price is required when ord_type is '2' (Limit) or '4' (StopLimit)"
                )
        # ord_type=3 (Stop) — price optional; we accept both.
        return self


class OrderCancelInput(BaseModel):
    """FIX 4.4 OrderCancelRequest (MsgType F)."""

    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    orig_cl_ord_id: str = Field(min_length=1, max_length=64)
    cl_ord_id: str = Field(min_length=1, max_length=64)
    venue: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=32)
    side: FixSide
    transact_time: datetime

    @field_validator("orig_cl_ord_id")
    @classmethod
    def _v_orig(cls, v: str) -> str:
        return _validate_id(v, field_name="orig_cl_ord_id")

    @field_validator("cl_ord_id")
    @classmethod
    def _v_cl(cls, v: str) -> str:
        return _validate_id(v, field_name="cl_ord_id")

    @field_validator("venue")
    @classmethod
    def _v_v(cls, v: str) -> str:
        return _validate_venue(v)

    @field_validator("symbol")
    @classmethod
    def _v_s(cls, v: str) -> str:
        return _validate_symbol(v)

    @field_validator("transact_time", mode="before")
    @classmethod
    def _v_tt(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "transact_time")


class OrderCancelReplaceInput(BaseModel):
    """FIX 4.4 OrderCancelReplaceRequest (MsgType G)."""

    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    orig_cl_ord_id: str = Field(min_length=1, max_length=64)
    cl_ord_id: str = Field(min_length=1, max_length=64)
    venue: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=32)
    side: FixSide
    ord_type: FixOrdType
    order_qty: Decimal
    price: Optional[Decimal] = None
    time_in_force: FixTimeInForce
    transact_time: datetime

    @field_validator("orig_cl_ord_id")
    @classmethod
    def _v_orig(cls, v: str) -> str:
        return _validate_id(v, field_name="orig_cl_ord_id")

    @field_validator("cl_ord_id")
    @classmethod
    def _v_cl(cls, v: str) -> str:
        return _validate_id(v, field_name="cl_ord_id")

    @field_validator("venue")
    @classmethod
    def _v_ve(cls, v: str) -> str:
        return _validate_venue(v)

    @field_validator("symbol")
    @classmethod
    def _v_sy(cls, v: str) -> str:
        return _validate_symbol(v)

    @field_validator("order_qty", mode="before")
    @classmethod
    def _v_q(cls, v: Decimal) -> Decimal:
        return _validate_qty(v)

    @field_validator("price", mode="before")
    @classmethod
    def _v_p(cls, v: Decimal | None) -> Decimal | None:
        return _validate_price(v)

    @field_validator("transact_time", mode="before")
    @classmethod
    def _v_tt(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "transact_time")

    @model_validator(mode="after")
    def _price_matches_ord_type(self) -> Self:
        ot = self.ord_type
        if ot == "1" and self.price is not None:
            raise ValueError("price must be None when ord_type=1 (Market)")
        if ot in ("2", "4") and self.price is None:
            raise ValueError(
                "price is required when ord_type is '2' (Limit) or '4' (StopLimit)"
            )
        return self


class OrderStatusInput(BaseModel):
    """FIX 4.4 OrderStatusRequest (MsgType H).

    Exactly one of ``cl_ord_id`` / ``order_id`` must be supplied.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    cl_ord_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    order_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    venue: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=32)
    side: FixSide

    @field_validator("cl_ord_id")
    @classmethod
    def _v_cl(cls, v: str | None) -> str | None:
        return None if v is None else _validate_id(v, field_name="cl_ord_id")

    @field_validator("order_id")
    @classmethod
    def _v_oi(cls, v: str | None) -> str | None:
        return None if v is None else _validate_id(v, field_name="order_id")

    @field_validator("venue")
    @classmethod
    def _v_v(cls, v: str) -> str:
        return _validate_venue(v)

    @field_validator("symbol")
    @classmethod
    def _v_s(cls, v: str) -> str:
        return _validate_symbol(v)

    @model_validator(mode="after")
    def _exactly_one_of(self) -> Self:
        have_cl = self.cl_ord_id is not None
        have_oi = self.order_id is not None
        if have_cl == have_oi:
            raise ValueError("exactly one of cl_ord_id / order_id must be provided")
        return self


class SessionStatusInput(BaseModel):
    """Query per-venue session state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    venue: str = Field(min_length=1, max_length=32)

    @field_validator("venue")
    @classmethod
    def _v_v(cls, v: str) -> str:
        return _validate_venue(v)


class KillSwitchInput(BaseModel):
    """Toggle the global or per-venue kill switch.

    * ``scope == "global"``: ``venue`` MUST be omitted.
    * ``scope == "venue"``:  ``venue`` MUST be supplied.

    ``reason`` is a free-text compliance note — at least 8 chars so
    trading_supervisors must provide meaningful context in audit.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    scope: Literal["global", "venue"]
    venue: Optional[str] = Field(default=None)
    state: Literal["on", "off"]
    reason: str = Field(min_length=8, max_length=500)

    @field_validator("venue")
    @classmethod
    def _v_v(cls, v: str | None) -> str | None:
        return None if v is None else _validate_venue(v)

    @model_validator(mode="after")
    def _scope_requires_venue(self) -> Self:
        if self.scope == "global" and self.venue is not None:
            raise ValueError("venue must be None when scope=global")
        if self.scope == "venue" and (self.venue is None or self.venue == ""):
            raise ValueError("venue must be supplied when scope=venue")
        return self


# ---------------------------------------------------------------------------
# Responses / outputs
# ---------------------------------------------------------------------------


class OrderResponse(BaseModel):
    """Canonical bridge-local acknowledgement of an outbound order.

    ``bridge_status`` is what the bridge itself decided. An actual
    venue-side acceptance is reflected asynchronously via drop-copy
    ExecutionReports.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    cl_ord_id: str
    venue: str
    sender_comp_id: str
    target_comp_id: str
    seq_num_out: int
    accepted_at: datetime
    bridge_status: Literal["sent", "rejected_local"]


class ExecReport(BaseModel):
    """Canonical inbound ExecutionReport (MsgType 8).

    Raw account never touches this model — we carry ``account_hash``
    (tenant-salted HMAC-SHA256 of the underlying account).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    venue: str
    cl_ord_id: str
    order_id: str
    exec_type: FixExecType
    ord_status: FixOrdStatus
    last_qty: Optional[Decimal] = None
    last_px: Optional[Decimal] = None
    cum_qty: Decimal
    avg_px: Optional[Decimal] = None
    transact_time: datetime
    account_hash: str = Field(min_length=1, max_length=64)


class SessionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    venue: str
    logon_status: LogonStatus
    seq_num_in: int
    seq_num_out: int
    last_heartbeat_ts: Optional[datetime] = None
    sender_comp_id: str
    target_comp_id: str


class KillSwitchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scope: Literal["global", "venue"]
    venue: Optional[str] = None
    state: Literal["on", "off"]
    set_at: datetime
    actor_aid: str
    reason: str


# ---------------------------------------------------------------------------
# VenueConfig (Vault YAML → pydantic)
# ---------------------------------------------------------------------------


class VenueConfig(BaseModel):
    """One FIX session's full configuration, pulled from Vault.

    * CompIDs are references to Vault paths — the bridge resolves the
      actual SenderCompID/TargetCompID strings at session-open time.
    * mTLS paths required when ``use_tls`` is true.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    venue: str = Field(min_length=1, max_length=32)
    sender_comp_id_vault_path: str = Field(min_length=1)
    target_comp_id_vault_path: str = Field(min_length=1)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    heartbeat_interval_s: int = Field(ge=5, le=120)
    reset_on_logon: bool = False
    use_tls: bool = True
    cert_path_vault_path: Optional[str] = None
    key_path_vault_path: Optional[str] = None
    ca_path_vault_path: Optional[str] = None

    @field_validator("venue")
    @classmethod
    def _v_v(cls, v: str) -> str:
        return _validate_venue(v)

    @model_validator(mode="after")
    def _mtls_paths_when_tls(self) -> Self:
        if self.use_tls:
            missing = [
                name
                for name, val in (
                    ("cert_path_vault_path", self.cert_path_vault_path),
                    ("key_path_vault_path", self.key_path_vault_path),
                    ("ca_path_vault_path", self.ca_path_vault_path),
                )
                if val is None or val == ""
            ]
            if missing:
                raise ValueError(
                    "use_tls=true requires mTLS paths: " + ", ".join(missing)
                )
        return self


__all__ = [
    "FixExecType",
    "FixOrdStatus",
    "FixOrdType",
    "FixSide",
    "FixTimeInForce",
    "LogonStatus",
    "NewOrderSingleInput",
    "OrderCancelInput",
    "OrderCancelReplaceInput",
    "OrderStatusInput",
    "SessionStatusInput",
    "KillSwitchInput",
    "OrderResponse",
    "ExecReport",
    "SessionStatusResponse",
    "KillSwitchResponse",
    "VenueConfig",
]
