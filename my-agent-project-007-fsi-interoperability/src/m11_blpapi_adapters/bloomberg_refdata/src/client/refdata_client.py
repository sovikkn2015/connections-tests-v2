"""Higher-level Bloomberg refdata client.

Sits between the tool handlers (``src/tools.py``) and the BLPAPI protocol
client. Responsibilities:

* Build a :class:`BlpapiRequest` from validated pydantic input.
* Acquire the session from :class:`BloombergSessionPool` (serializes calls).
* Wrap the call in the shared :class:`CircuitBreaker` + :class:`RateLimiter`.
* Emit the ``bloomberg.tool_audit`` event to stdout (success AND failure).
* Translate :class:`BlpapiVendorError` + transport errors into canonical
  :class:`AdapterError` with codes from the spec §6 mapping table.

All four tool methods return JSON-safe dicts. M7 translators canonicalize
into M3 types at a higher layer.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiClientProtocol,
    BlpapiRequest,
    BlpapiResponse,
    BlpapiVendorError,
)
from m11_blpapi_adapters.bloomberg_refdata.src.client.session_pool import (
    BloombergSessionPool,
)
from m11_blpapi_adapters.bloomberg_refdata.src.models import (
    CorporateActionsInput,
    HistoricalDataInput,
    IntradayTickInput,
    ReferenceDataInput,
    SecurityRef,
)
from m11_python_adapters_shared import (
    AdapterError,
    AuditEmitter,
    AuditEvent,
    CircuitBreaker,
    CircuitBreakerOpen,
    Clock,
    RateLimiter,
    RateLimitExceeded,
    StructuredLogger,
)


# Canonical error map — see spec §6 table.
_VENDOR_ERROR_MAP: dict[str, tuple[str, bool]] = {
    "NOT_ENTITLED": ("vendor_not_entitled", False),
    "INVALID_FIELD": ("vendor_invalid_field", False),
    "INVALID_SECURITY": ("vendor_invalid_security", False),
    "BAD_TIMEOUT": ("vendor_timeout", True),
    "TIMEOUT": ("vendor_timeout", True),
    "RATE_LIMIT_EXCEEDED": ("vendor_rate_limited", True),
    "SERVICE_UNAVAILABLE": ("vendor_unavailable", True),
    "SESSION_LOST": ("vendor_session_lost", True),
    "AUTHORIZATION_FAILURE": ("vendor_auth_failed", False),
}


class BloombergRefDataClient:
    """Tool-facing Bloomberg client.

    One instance per adapter process. Non-async methods are side-effect free
    (builders); async methods do I/O + audit emission.
    """

    ADAPTER_NAME = "m11-blpapi-adapter"
    VENDOR = "bloomberg"

    def __init__(
        self,
        *,
        pool: BloombergSessionPool,
        audit: AuditEmitter,
        breaker: CircuitBreaker,
        rate_limiter: RateLimiter,
        clock: Clock,
        logger: StructuredLogger | None = None,
        enabled: bool = True,
    ) -> None:
        self._pool = pool
        self._audit = audit
        self._breaker = breaker
        self._rate_limiter = rate_limiter
        self._clock = clock
        self._logger = logger
        self._enabled = enabled
        self._shutting_down = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        await self._pool.open_all()

    async def shutdown(self) -> None:
        """Idempotent shutdown — closes the underlying session.

        Safe to call multiple times; subsequent tool calls will return the
        ``adapter_shutting_down`` canonical code.
        """
        self._shutting_down = True
        await self._pool.close_all()

    def healthy(self) -> bool:
        if not self._enabled:
            # Adapter explicitly disabled — healthy from the orchestrator's
            # POV (Rule 16: 200 when healthy OR disabled). The server factory
            # reads this and translates to HTTP 200.
            return True
        return self._pool.healthy() and not self._shutting_down

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def reference_data(
        self, args: ReferenceDataInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        fields = {
            "security_count": len(args.securities),
            "field_count": len(args.fields),
        }
        req = BlpapiRequest(
            service="//blp/refdata",
            operation="ReferenceDataRequest",
            payload={
                "securities": [_security_to_bbg_string(s) for s in args.securities],
                "fields": list(args.fields),
            },
        )
        return await self._dispatch(
            tool="bloomberg.reference_data",
            req=req,
            firm_id=firm_id,
            started_at=started,
            extra_fields=fields,
        )

    async def historical_data(
        self, args: HistoricalDataInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        fields = {
            "security_count": len(args.securities),
            "field_count": len(args.fields),
            "periodicity": args.periodicity,
        }
        req = BlpapiRequest(
            service="//blp/refdata",
            operation="HistoricalDataRequest",
            payload={
                "securities": [_security_to_bbg_string(s) for s in args.securities],
                "fields": list(args.fields),
                "startDate": _date_to_bbg(args.start_date),
                "endDate": _date_to_bbg(args.end_date),
                "periodicitySelection": args.periodicity,
                "adjustmentNormal": args.adjustment_normal,
                "adjustmentAbnormal": args.adjustment_abnormal,
                "adjustmentSplit": args.adjustment_split,
            },
        )
        return await self._dispatch(
            tool="bloomberg.historical_data",
            req=req,
            firm_id=firm_id,
            started_at=started,
            extra_fields=fields,
        )

    async def intraday_tick(
        self, args: IntradayTickInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        fields = {
            "event_types": list(args.event_types),
        }
        req = BlpapiRequest(
            service="//blp/refdata",
            operation="IntradayTickRequest",
            payload={
                "security": _security_to_bbg_string(args.security),
                "eventTypes": list(args.event_types),
                "startDateTime": _datetime_to_bbg(args.start_datetime),
                "endDateTime": _datetime_to_bbg(args.end_datetime),
                "includeConditionCodes": args.include_condition_codes,
            },
        )
        return await self._dispatch(
            tool="bloomberg.intraday_tick",
            req=req,
            firm_id=firm_id,
            started_at=started,
            extra_fields=fields,
        )

    async def corporate_actions(
        self, args: CorporateActionsInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        fields = {
            "security_count": len(args.securities),
            "action_types": list(args.action_types),
        }
        # Corporate actions use ReferenceDataRequest with DVD_HIST_ALL override.
        req = BlpapiRequest(
            service="//blp/refdata",
            operation="ReferenceDataRequest",
            payload={
                "securities": [_security_to_bbg_string(s) for s in args.securities],
                "fields": ["DVD_HIST_ALL"],
                "overrides": {
                    "DVD_START_DT": _date_to_bbg(args.start_date),
                    "DVD_END_DT": _date_to_bbg(args.end_date),
                    "DVD_ACTION_TYPES": ",".join(args.action_types),
                },
            },
        )
        return await self._dispatch(
            tool="bloomberg.corporate_actions",
            req=req,
            firm_id=firm_id,
            started_at=started,
            extra_fields=fields,
        )

    # ------------------------------------------------------------------
    # Internal dispatch with breaker + audit
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        *,
        tool: str,
        req: BlpapiRequest,
        firm_id: str,
        started_at: int,
        extra_fields: dict[str, Any],
    ) -> dict[str, Any]:
        # Short-circuit for disabled adapter (Rule 16 graceful-degradation).
        if not self._enabled:
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="adapter_not_enabled",
                vendor_status=None,
                retryable=False,
                extra=extra_fields,
            )
            return {
                "error": "bloomberg_not_enabled",
                "message": "Bloomberg adapter disabled (BLPAPI_ENABLED=false)",
            }

        if self._shutting_down:
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="adapter_shutting_down",
                vendor_status=None,
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "adapter_shutting_down",
                "adapter is shutting down, retry via another pod",
                retryable=True,
            )

        # Rate-limit check BEFORE touching the session.
        try:
            self._rate_limiter.acquire(firm_id)
        except RateLimitExceeded as rl:
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_rate_limited",
                vendor_status={"retry_after_ms": rl.retry_after_ms},
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_rate_limited",
                f"adapter rate limit exceeded; retry after {rl.retry_after_ms}ms",
                vendor_status={"retry_after_ms": rl.retry_after_ms},
                retryable=True,
            )

        # Circuit breaker check.
        try:
            self._breaker.check()
        except CircuitBreakerOpen as cb:
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_circuit_open",
                vendor_status={"cooldown_remaining_ms": cb.cooldown_remaining_ms},
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_circuit_open",
                "circuit breaker is open for Bloomberg",
                vendor_status={"cooldown_remaining_ms": cb.cooldown_remaining_ms},
                retryable=True,
            )

        # Invoke via the session pool (serializes on single session).
        try:
            resp = await self._pool.execute(req)
        except BlpapiVendorError as vendor_err:
            self._breaker.record_failure()
            code, retryable = _VENDOR_ERROR_MAP.get(
                vendor_err.error_code, ("vendor_error", False)
            )
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code=code,
                vendor_status=vendor_err.error_code,
                retryable=retryable,
                extra=extra_fields,
            )
            raise AdapterError(
                code,
                f"Bloomberg vendor error: {vendor_err.message}",
                vendor_status=vendor_err.error_code,
                retryable=retryable,
            ) from vendor_err
        except asyncio.TimeoutError as terr:
            self._breaker.record_failure()
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_timeout",
                vendor_status="TIMEOUT",
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_timeout",
                "Bloomberg request timed out",
                retryable=True,
            ) from terr
        except TimeoutError as terr:
            self._breaker.record_failure()
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_timeout",
                vendor_status="TIMEOUT",
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_timeout",
                "Bloomberg request timed out",
                retryable=True,
            ) from terr
        except ConnectionError as conn_err:
            self._breaker.record_failure()
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_session_lost",
                vendor_status="SESSION_LOST",
                retryable=True,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_session_lost",
                f"Bloomberg session lost: {conn_err}",
                retryable=True,
            ) from conn_err
        except AdapterError:
            raise
        except Exception as err:
            self._breaker.record_failure()
            self._emit(
                tool=tool,
                firm_id=firm_id,
                outcome="failure",
                started_at=started_at,
                error_code="vendor_error",
                vendor_status=None,
                retryable=False,
                extra=extra_fields,
            )
            raise AdapterError(
                "vendor_error",
                f"unexpected Bloomberg client error: {type(err).__name__}",
            ) from err

        # Success.
        self._breaker.record_success()
        self._emit(
            tool=tool,
            firm_id=firm_id,
            outcome="success",
            started_at=started_at,
            error_code=None,
            vendor_status=resp.vendor_response_code,
            retryable=None,
            extra={**extra_fields, "partial": bool(resp.partial)},
        )
        return {
            "data": resp.data,
            "partial": resp.partial,
            "vendor_response_code": resp.vendor_response_code,
        }

    def _emit(
        self,
        *,
        tool: str,
        firm_id: str,
        outcome: str,
        started_at: int,
        error_code: str | None,
        vendor_status: Any,
        retryable: bool | None,
        extra: dict[str, Any],
    ) -> None:
        """Single point for audit emission. Never raises."""
        try:
            ev = AuditEvent(
                event="bloomberg.tool_audit",
                tool=tool,
                firm_id=firm_id,
                outcome=outcome,
                duration_ms=self._clock.now_ms() - started_at,
                adapter_name=self.ADAPTER_NAME,
                vendor=self.VENDOR,
                timestamp_ms=self._clock.now_ms(),
                error_code=error_code,
                vendor_status=vendor_status,
                retryable=retryable,
                fields=extra,
            )
            self._audit.emit(ev)
        except Exception:  # pragma: no cover — audit must never fail a call
            if self._logger is not None:
                self._logger.warning({"event": "audit.emit_failed", "tool": tool})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _security_to_bbg_string(ref: SecurityRef) -> str:
    """Return a Bloomberg-parseable security string.

    For TICKER we return the value verbatim (callers formed it as
    ``"AAPL US Equity"``). For ISIN/CUSIP we prefix with the standard
    `/isin/` or `/cusip/` convention BLPAPI expects.
    """
    if ref.identifier_type == "TICKER":
        return ref.value
    prefix = "/isin/" if ref.identifier_type == "ISIN" else "/cusip/"
    return f"{prefix}{ref.value}"


def _date_to_bbg(d: date) -> str:
    """BLPAPI expects YYYYMMDD for dates."""
    return d.strftime("%Y%m%d")


def _datetime_to_bbg(dt: datetime) -> str:
    """BLPAPI expects ISO-ish UTC datetimes; we keep full ISO for fidelity."""
    # Fall back to UTC for naive datetimes so the vendor picks up on the
    # server's timezone assumption rather than using local time.
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()
