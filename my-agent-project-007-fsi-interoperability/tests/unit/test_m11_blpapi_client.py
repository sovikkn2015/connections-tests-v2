"""BloombergRefDataClient — tool handlers, error translation, audit.

Covers:
* Happy path for each of the 4 tools.
* Bloomberg error codes → canonical AdapterError translation (spec §6).
* Circuit breaker + rate limiter integration.
* Audit-on-success + audit-on-failure.
* Shutdown / disabled-mode shapes.
* Session pool single-session serialization under concurrency.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import date, datetime, timezone
from typing import Any

import pytest

from m11_blpapi_adapters.bloomberg_refdata.src.client import (
    BloombergRefDataClient,
    BloombergSessionPool,
    FakeBlpapiClient,
)
from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiResponse,
    BlpapiVendorError,
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
    CircuitBreaker,
    FakeClock,
    RateLimiter,
)


def _aapl() -> SecurityRef:
    return SecurityRef(identifier_type="TICKER", value="AAPL US Equity")


async def _build_client(
    *,
    enabled: bool = True,
    clock: FakeClock | None = None,
    breaker: CircuitBreaker | None = None,
    rate_rpm: int = 60_000,
    rate_burst: int = 100,
) -> tuple[BloombergRefDataClient, FakeBlpapiClient, io.StringIO]:
    clock = clock or FakeClock(start_ms=1_700_000_000_000)
    fake = FakeBlpapiClient()
    await fake.open()
    pool = BloombergSessionPool(fake)
    buf = io.StringIO()
    audit = AuditEmitter(logger=None, stream=buf)
    breaker = breaker or CircuitBreaker(clock, threshold=5, cooldown_ms=30_000)
    rl = RateLimiter(clock, rpm=rate_rpm, burst=rate_burst)
    client = BloombergRefDataClient(
        pool=pool,
        audit=audit,
        breaker=breaker,
        rate_limiter=rl,
        clock=clock,
        enabled=enabled,
    )
    return client, fake, buf


def _audit_events(buf: io.StringIO) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in buf.getvalue().strip().split("\n")
        if line
    ]


# ---------------------------------------------------------------------------
# Happy paths, 4 tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_data_happy_path_emits_success_audit() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_response(
        BlpapiResponse(
            data={"ReferenceDataResponse": {"securityData": [{"security": "AAPL US Equity"}]}}
        )
    )
    inp = ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST", "MKT_CAP"])
    result = await client.reference_data(inp, "firm1")
    assert "data" in result
    assert result["vendor_response_code"] == 0
    events = _audit_events(buf)
    assert len(events) == 1
    assert events[0]["tool"] == "bloomberg.reference_data"
    assert events[0]["outcome"] == "success"
    assert events[0]["security_count"] == 1
    assert events[0]["field_count"] == 2


@pytest.mark.asyncio
async def test_historical_data_happy_path() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_response(BlpapiResponse(data={"HistoricalDataResponse": {}}))
    inp = HistoricalDataInput(
        securities=[_aapl()],
        fields=["PX_LAST"],
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        adjustment_split=True,
    )
    result = await client.historical_data(inp, "firm1")
    assert "data" in result
    events = _audit_events(buf)
    assert events[0]["outcome"] == "success"
    assert events[0]["periodicity"] == "DAILY"


@pytest.mark.asyncio
async def test_intraday_tick_happy_path() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_response(BlpapiResponse(data={"IntradayTickResponse": {"tickData": []}}))
    inp = IntradayTickInput(
        security=_aapl(),
        event_types=["TRADE", "BID"],
        start_datetime=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 5, 20, 14, 30, tzinfo=timezone.utc),
    )
    result = await client.intraday_tick(inp, "firm1")
    assert "data" in result
    events = _audit_events(buf)
    assert events[0]["tool"] == "bloomberg.intraday_tick"
    assert events[0]["event_types"] == ["TRADE", "BID"]


@pytest.mark.asyncio
async def test_corporate_actions_happy_path() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_response(
        BlpapiResponse(
            data={
                "ReferenceDataResponse": {
                    "securityData": [{"security": "MSFT US Equity"}]
                }
            }
        )
    )
    inp = CorporateActionsInput(
        securities=[_aapl()],
        action_types=["DVD_CASH"],
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
    )
    result = await client.corporate_actions(inp, "firm1")
    assert "data" in result
    events = _audit_events(buf)
    assert events[0]["tool"] == "bloomberg.corporate_actions"


# ---------------------------------------------------------------------------
# Bloomberg error code mapping — spec §6
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_entitled_maps_to_canonical_code() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_error(BlpapiVendorError("NOT_ENTITLED", "not licensed"))
    inp = ReferenceDataInput(securities=[_aapl()], fields=["EARNINGS_ESTIMATE"])
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(inp, "firm1")
    assert exc.value.code == "vendor_not_entitled"
    assert exc.value.retryable is False
    events = _audit_events(buf)
    assert events[0]["outcome"] == "failure"
    assert events[0]["error_code"] == "vendor_not_entitled"


@pytest.mark.asyncio
async def test_invalid_field_maps_to_canonical_code() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("INVALID_FIELD", "no such field"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_invalid_field"


@pytest.mark.asyncio
async def test_invalid_security_maps_to_canonical_code() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("INVALID_SECURITY", "unknown sec"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_invalid_security"


@pytest.mark.asyncio
async def test_bad_timeout_maps_to_canonical_code_and_is_retryable() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("BAD_TIMEOUT", "timed out"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_timeout"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_rate_limit_exceeded_maps_to_canonical() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("RATE_LIMIT_EXCEEDED", "slow down"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_rate_limited"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_service_unavailable_maps_to_canonical() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("SERVICE_UNAVAILABLE", "down"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_unavailable"


@pytest.mark.asyncio
async def test_session_lost_maps_to_canonical() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("SESSION_LOST", "gone"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_session_lost"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_unknown_vendor_code_maps_to_generic() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_error(BlpapiVendorError("SOMETHING_WEIRD", "???"))
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_error"


# ---------------------------------------------------------------------------
# Transport / connection failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_maps_to_session_lost() -> None:
    client, fake, _ = await _build_client()

    # Close the fake so execute() raises ConnectionError.
    await fake.close()
    await fake.open()

    # Replace the execute method with one that raises ConnectionError.
    async def boom(req: Any) -> Any:
        raise ConnectionError("pipe broken")

    fake.execute = boom  # type: ignore[method-assign]
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_session_lost"


@pytest.mark.asyncio
async def test_timeout_error_maps_to_vendor_timeout() -> None:
    client, fake, _ = await _build_client()

    async def boom(req: Any) -> Any:
        raise TimeoutError("slow")

    fake.execute = boom  # type: ignore[method-assign]
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_timeout"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breaker_opens_after_consecutive_failures() -> None:
    clock = FakeClock(start_ms=1_700_000_000_000)
    breaker = CircuitBreaker(clock, threshold=3, cooldown_ms=1_000)
    client, fake, _ = await _build_client(clock=clock, breaker=breaker)
    fake.set_default_error(BlpapiVendorError("SERVICE_UNAVAILABLE", "down"))

    for _ in range(3):
        with pytest.raises(AdapterError):
            await client.reference_data(
                ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
            )
    # 4th call short-circuits with vendor_circuit_open.
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_circuit_open"


@pytest.mark.asyncio
async def test_breaker_half_open_transitions_after_cooldown() -> None:
    clock = FakeClock(start_ms=1_700_000_000_000)
    breaker = CircuitBreaker(clock, threshold=2, cooldown_ms=500)
    client, fake, _ = await _build_client(clock=clock, breaker=breaker)
    fake.set_default_error(BlpapiVendorError("SERVICE_UNAVAILABLE", "down"))

    for _ in range(2):
        with pytest.raises(AdapterError):
            await client.reference_data(
                ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
            )
    # Breaker OPEN now.
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "vendor_circuit_open"

    clock.advance_ms(500)
    fake.set_default_error(None)
    fake.set_default_response(BlpapiResponse(data={"ok": True}))
    result = await client.reference_data(
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
    )
    assert result["vendor_response_code"] == 0


# ---------------------------------------------------------------------------
# Rate limiter integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_returns_retryable_error() -> None:
    # Set the bucket so burst=1 — second call fails.
    client, fake, buf = await _build_client(rate_rpm=60, rate_burst=1)
    fake.set_default_response(BlpapiResponse(data={"ok": True}))
    await client.reference_data(
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm_z"
    )
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm_z"
        )
    assert exc.value.code == "vendor_rate_limited"
    assert exc.value.retryable is True


# ---------------------------------------------------------------------------
# Adapter-disabled mode + shutdown shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_mode_returns_not_enabled_shape() -> None:
    client, _, buf = await _build_client(enabled=False)
    result = await client.reference_data(
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
    )
    assert result == {
        "error": "bloomberg_not_enabled",
        "message": "Bloomberg adapter disabled (BLPAPI_ENABLED=false)",
    }
    events = _audit_events(buf)
    assert events[0]["error_code"] == "adapter_not_enabled"


@pytest.mark.asyncio
async def test_shutdown_is_idempotent_and_emits_adapter_shutting_down() -> None:
    client, _, buf = await _build_client()
    await client.shutdown()
    await client.shutdown()  # idempotent
    with pytest.raises(AdapterError) as exc:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )
    assert exc.value.code == "adapter_shutting_down"
    events = _audit_events(buf)
    assert events[0]["error_code"] == "adapter_shutting_down"


@pytest.mark.asyncio
async def test_healthy_flag_disabled_still_reports_healthy() -> None:
    client, _, _ = await _build_client(enabled=False)
    assert client.healthy() is True


# ---------------------------------------------------------------------------
# Session pool single-session concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_pool_serializes_concurrent_calls() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_response(BlpapiResponse(data={"ok": True}))
    # Inject a tiny latency so concurrency has a chance to overlap.
    fake.set_latency_ms(5)

    async def one_call() -> None:
        await client.reference_data(
            ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
        )

    await asyncio.gather(*[one_call() for _ in range(100)])
    # Single session → max observed concurrency in the fake is 1.
    assert fake.max_concurrent == 1
    assert len(fake.call_log) == 100


@pytest.mark.asyncio
async def test_session_pool_tracks_in_flight_counter() -> None:
    client, fake, _ = await _build_client()
    fake.set_default_response(BlpapiResponse(data={}))
    assert client._pool.in_flight == 0
    await client.reference_data(
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
    )
    assert client._pool.in_flight == 0
    assert client._pool.total_calls == 1


# ---------------------------------------------------------------------------
# Audit discipline — no credentials in audit output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_output_has_no_credential_tokens() -> None:
    client, fake, buf = await _build_client()
    fake.set_default_response(BlpapiResponse(data={"ok": True}))
    await client.reference_data(
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"]), "firm1"
    )
    output = buf.getvalue()
    # No Vault paths, no token-like strings. Real UUID / serial are never
    # passed to the audit emitter by construction.
    for needle in ("secret/data", "BLPAPI_UUID", "BLPAPI_SERIAL", "bearer", "Bearer "):
        assert needle not in output
