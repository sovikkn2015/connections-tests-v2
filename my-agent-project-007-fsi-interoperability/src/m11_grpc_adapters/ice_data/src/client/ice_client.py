"""Higher-level ICE Data client used by the tool handlers.

Mirrors :class:`BloombergRefDataClient` in structure — build a request dict,
acquire the stub via the channel pool, call the RPC, emit audit, translate
errors to canonical codes.

gRPC status → canonical code table (spec §6):

    UNAUTHENTICATED      → vendor_auth_failed      (not retryable)
    PERMISSION_DENIED    → vendor_not_entitled     (not retryable)
    INVALID_ARGUMENT     → vendor_bad_request      (not retryable)
    NOT_FOUND            → vendor_not_found        (not retryable)
    DEADLINE_EXCEEDED    → vendor_timeout          (retryable)
    RESOURCE_EXHAUSTED   → vendor_rate_limited     (retryable)
    UNAVAILABLE          → vendor_unavailable      (retryable)
    channel lost         → vendor_transport_error  (retryable)
    UNKNOWN / other      → vendor_error            (not retryable)
"""

from __future__ import annotations

import asyncio
from typing import Any

from m11_grpc_adapters.ice_data.src.client.channel_pool import IceChannelPool
from m11_grpc_adapters.ice_data.src.client.protocol import IceVendorError
from m11_grpc_adapters.ice_data.src.models import (
    IceReferenceDataInput,
    IceSecurityRef,
    MarketDataSnapshotInput,
    TradeTapeInput,
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


_VENDOR_STATUS_MAP: dict[str, tuple[str, bool]] = {
    "UNAUTHENTICATED": ("vendor_auth_failed", False),
    "PERMISSION_DENIED": ("vendor_not_entitled", False),
    "INVALID_ARGUMENT": ("vendor_bad_request", False),
    "NOT_FOUND": ("vendor_not_found", False),
    "DEADLINE_EXCEEDED": ("vendor_timeout", True),
    "RESOURCE_EXHAUSTED": ("vendor_rate_limited", True),
    "UNAVAILABLE": ("vendor_unavailable", True),
    "CANCELLED": ("vendor_transport_error", True),
    "ABORTED": ("vendor_transport_error", True),
    "INTERNAL": ("vendor_error", False),
    "UNKNOWN": ("vendor_error", False),
    "UNIMPLEMENTED": ("vendor_error", False),
}


class IceDataClient:
    """Tool-facing ICE Data client (one instance per adapter process)."""

    ADAPTER_NAME = "m11-grpc-adapter"
    VENDOR = "ice_data"

    def __init__(
        self,
        *,
        pool: IceChannelPool,
        tenant_id: str,
        audit: AuditEmitter,
        breaker: CircuitBreaker,
        rate_limiter: RateLimiter,
        clock: Clock,
        logger: StructuredLogger | None = None,
        enabled: bool = True,
        max_retries: int = 2,
    ) -> None:
        self._pool = pool
        self._default_tenant_id = tenant_id
        self._audit = audit
        self._breaker = breaker
        self._rate_limiter = rate_limiter
        self._clock = clock
        self._logger = logger
        self._enabled = enabled
        self._shutting_down = False
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        if not self._enabled:
            return
        await self._pool.ensure_open(self._default_tenant_id)

    async def shutdown(self) -> None:
        """Idempotent shutdown — closes every cached channel."""
        self._shutting_down = True
        await self._pool.close_all()

    def healthy(self) -> bool:
        if not self._enabled:
            return True
        return self._pool.healthy() and not self._shutting_down

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def market_data_snapshot(
        self, args: MarketDataSnapshotInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        req = {
            "securities": [_ref_to_dict(s) for s in args.securities],
            "include_depth": args.include_depth,
        }
        return await self._dispatch(
            tool="ice.market_data_snapshot",
            rpc="get_market_data_snapshot",
            firm_id=firm_id,
            started_at=started,
            request=req,
            extra_fields={
                "security_count": len(args.securities),
                "include_depth": args.include_depth,
            },
        )

    async def trade_tape(
        self, args: TradeTapeInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        req = {
            "security": _ref_to_dict(args.security),
            "start_time": args.start_time.isoformat(),
            "end_time": args.end_time.isoformat(),
            "max_ticks": args.max_ticks,
        }
        return await self._dispatch(
            tool="ice.trade_tape",
            rpc="get_trade_tape",
            firm_id=firm_id,
            started_at=started,
            request=req,
            extra_fields={"max_ticks": args.max_ticks},
        )

    async def reference_data(
        self, args: IceReferenceDataInput, firm_id: str
    ) -> dict[str, Any]:
        started = self._clock.now_ms()
        req = {
            "securities": [_ref_to_dict(s) for s in args.securities],
            "as_of_date": args.as_of_date.isoformat() if args.as_of_date else None,
        }
        return await self._dispatch(
            tool="ice.reference_data",
            rpc="get_reference_data",
            firm_id=firm_id,
            started_at=started,
            request=req,
            extra_fields={"security_count": len(args.securities)},
        )

    # ------------------------------------------------------------------
    # Dispatch with breaker + retry + audit
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        *,
        tool: str,
        rpc: str,
        firm_id: str,
        started_at: int,
        request: dict[str, Any],
        extra_fields: dict[str, Any],
    ) -> dict[str, Any]:
        # Disabled-adapter graceful degradation.
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
                "error": "ice_not_enabled",
                "message": "ICE gRPC adapter disabled (ICE_ENABLED=false)",
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

        # Rate-limit.
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

        # Breaker.
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
                "circuit breaker is open for ICE Data",
                vendor_status={"cooldown_remaining_ms": cb.cooldown_remaining_ms},
                retryable=True,
            )

        # Resolve tenant channel (one per adapter process by default; multi-tenant
        # mode uses firm_id for per-tenant channel isolation).
        tenant_id = firm_id or self._default_tenant_id
        await self._pool.ensure_open(tenant_id)

        # Retry loop — UNAVAILABLE / DEADLINE_EXCEEDED get bounded retries.
        attempts = 0
        backoff_ms = 200
        last_err: Exception | None = None
        while True:
            attempts += 1
            try:
                resp = await self._call_stub(rpc, tenant_id, request)
                self._breaker.record_success()
                self._emit(
                    tool=tool,
                    firm_id=firm_id,
                    outcome="success",
                    started_at=started_at,
                    error_code=None,
                    vendor_status="OK",
                    retryable=None,
                    extra={**extra_fields, "attempts": attempts},
                )
                return resp
            except IceVendorError as ve:
                code, retryable = _VENDOR_STATUS_MAP.get(
                    ve.grpc_status_name, ("vendor_error", False)
                )
                if retryable and attempts <= self._max_retries:
                    last_err = ve
                    await asyncio.sleep(backoff_ms / 1000.0)
                    backoff_ms *= 2
                    continue
                self._breaker.record_failure()
                self._emit(
                    tool=tool,
                    firm_id=firm_id,
                    outcome="failure",
                    started_at=started_at,
                    error_code=code,
                    vendor_status=ve.grpc_status_name,
                    retryable=retryable,
                    extra={**extra_fields, "attempts": attempts},
                )
                raise AdapterError(
                    code,
                    f"ICE gRPC error: {ve.message}",
                    vendor_status=ve.grpc_status_name,
                    retryable=retryable,
                ) from ve
            except ConnectionError as ce:
                if attempts <= self._max_retries:
                    last_err = ce
                    await asyncio.sleep(backoff_ms / 1000.0)
                    backoff_ms *= 2
                    continue
                self._breaker.record_failure()
                self._emit(
                    tool=tool,
                    firm_id=firm_id,
                    outcome="failure",
                    started_at=started_at,
                    error_code="vendor_transport_error",
                    vendor_status="UNAVAILABLE",
                    retryable=True,
                    extra={**extra_fields, "attempts": attempts},
                )
                raise AdapterError(
                    "vendor_transport_error",
                    f"ICE channel transport error: {ce}",
                    retryable=True,
                ) from ce
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
                    extra={**extra_fields, "attempts": attempts},
                )
                raise AdapterError(
                    "vendor_error",
                    f"unexpected ICE client error: {type(err).__name__}",
                ) from err

    async def _call_stub(
        self, rpc: str, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch to the underlying stub by RPC name."""
        stub = self._pool.stub
        if rpc == "get_market_data_snapshot":
            return await stub.get_market_data_snapshot(tenant_id, request)
        if rpc == "get_trade_tape":
            return await stub.get_trade_tape(tenant_id, request)
        if rpc == "get_reference_data":
            return await stub.get_reference_data(tenant_id, request)
        raise AdapterError("adapter_internal_error", f"unknown RPC {rpc!r}")

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
        try:
            ev = AuditEvent(
                event="ice.tool_audit",
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
        except Exception:  # pragma: no cover — audit must not kill a call
            if self._logger is not None:
                self._logger.warning({"event": "audit.emit_failed", "tool": tool})


def _ref_to_dict(ref: IceSecurityRef) -> dict[str, Any]:
    """Flatten a SecurityRef for the wire payload."""
    d: dict[str, Any] = {
        "identifier_type": ref.identifier_type,
        "value": ref.value,
    }
    if ref.venue is not None:
        d["venue"] = ref.venue
    return d
