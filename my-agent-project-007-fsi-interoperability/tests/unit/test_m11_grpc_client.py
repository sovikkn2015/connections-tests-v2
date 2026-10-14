"""IceDataClient unit tests — happy path, error translation, retry, audit."""

from __future__ import annotations

import asyncio
import io
import json
from datetime import date, datetime, timezone
from typing import Any

import pytest

from m11_grpc_adapters.ice_data.src.client import (
    FakeIceStub,
    IceChannelPool,
    IceDataClient,
)
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
    CircuitBreaker,
    FakeClock,
    RateLimiter,
)


def _spy() -> IceSecurityRef:
    return IceSecurityRef(identifier_type="SYMBOL", value="SPY", venue="ARCA")


async def _build(
    *,
    enabled: bool = True,
    tenant_id: str = "tenantA",
    clock: FakeClock | None = None,
    breaker: CircuitBreaker | None = None,
    rate_rpm: int = 600_000,
    rate_burst: int = 500,
    max_retries: int = 2,
) -> tuple[IceDataClient, FakeIceStub, io.StringIO]:
    clock = clock or FakeClock(start_ms=1_700_000_000_000)
    stub = FakeIceStub()
    pool = IceChannelPool(stub)
    buf = io.StringIO()
    audit = AuditEmitter(logger=None, stream=buf)
    breaker = breaker or CircuitBreaker(clock, threshold=5, cooldown_ms=30_000)
    rl = RateLimiter(clock, rpm=rate_rpm, burst=rate_burst)
    client = IceDataClient(
        pool=pool,
        tenant_id=tenant_id,
        audit=audit,
        breaker=breaker,
        rate_limiter=rl,
        clock=clock,
        enabled=enabled,
        max_retries=max_retries,
    )
    await client.open()
    return client, stub, buf


def _events(buf: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(l) for l in buf.getvalue().strip().split("\n") if l]


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_market_data_snapshot_happy() -> None:
    client, stub, buf = await _build()
    stub.set_response("get_market_data_snapshot", None, {"quotes": [{"symbol": "SPY"}]})
    inp = MarketDataSnapshotInput(securities=[_spy()])
    result = await client.market_data_snapshot(inp, "tenantA")
    assert result["quotes"][0]["symbol"] == "SPY"
    ev = _events(buf)[0]
    assert ev["tool"] == "ice.market_data_snapshot"
    assert ev["outcome"] == "success"


@pytest.mark.asyncio
async def test_trade_tape_happy() -> None:
    client, stub, buf = await _build()
    stub.set_response("get_trade_tape", None, {"ticks": [{"price": 450.1}]})
    inp = TradeTapeInput(
        security=_spy(),
        start_time=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 20, 20, 0, tzinfo=timezone.utc),
    )
    result = await client.trade_tape(inp, "tenantA")
    assert result["ticks"][0]["price"] == 450.1


@pytest.mark.asyncio
async def test_reference_data_happy() -> None:
    client, stub, buf = await _build()
    stub.set_response("get_reference_data", None, {"securities": [{"asset_class": "ETF"}]})
    inp = IceReferenceDataInput(securities=[_spy()], as_of_date=date(2026, 5, 20))
    result = await client.reference_data(inp, "tenantA")
    assert result["securities"][0]["asset_class"] == "ETF"


# ---------------------------------------------------------------------------
# gRPC status translation — spec §6
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "grpc_status,expected_code,retryable",
    [
        ("UNAUTHENTICATED", "vendor_auth_failed", False),
        ("PERMISSION_DENIED", "vendor_not_entitled", False),
        ("INVALID_ARGUMENT", "vendor_bad_request", False),
        ("NOT_FOUND", "vendor_not_found", False),
        ("DEADLINE_EXCEEDED", "vendor_timeout", True),
        ("RESOURCE_EXHAUSTED", "vendor_rate_limited", True),
        ("UNAVAILABLE", "vendor_unavailable", True),
        ("CANCELLED", "vendor_transport_error", True),
        ("INTERNAL", "vendor_error", False),
    ],
)
@pytest.mark.asyncio
async def test_grpc_status_maps_to_canonical(
    grpc_status: str, expected_code: str, retryable: bool
) -> None:
    client, stub, _ = await _build(max_retries=0)
    stub.set_error(
        "get_market_data_snapshot",
        None,
        IceVendorError(grpc_status, "synth err"),
    )
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == expected_code
    assert exc.value.retryable is retryable


# ---------------------------------------------------------------------------
# Retry on retryable gRPC statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_unavailable_then_success() -> None:
    client, stub, buf = await _build()
    # Set up: first two calls fail UNAVAILABLE, third succeeds.
    call_counter = {"n": 0}
    orig = stub.get_market_data_snapshot

    async def flaky(tenant_id: str, req: dict[str, Any]) -> dict[str, Any]:
        call_counter["n"] += 1
        if call_counter["n"] < 3:
            raise IceVendorError("UNAVAILABLE", "try again")
        return await orig(tenant_id, req)

    stub.get_market_data_snapshot = flaky  # type: ignore[assignment]
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})

    result = await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
    )
    assert "quotes" in result
    # 3 attempts (2 retries + final success)
    ev = _events(buf)[-1]
    assert ev["outcome"] == "success"
    assert ev["attempts"] == 3


@pytest.mark.asyncio
async def test_retry_exhausted_raises() -> None:
    client, stub, buf = await _build(max_retries=2)
    stub.set_error(
        "get_market_data_snapshot",
        None,
        IceVendorError("UNAVAILABLE", "never comes back"),
    )
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == "vendor_unavailable"
    ev = _events(buf)[-1]
    assert ev["attempts"] == 3  # 1 initial + 2 retries


# ---------------------------------------------------------------------------
# Connection / transport errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_wrapped_as_transport() -> None:
    client, stub, _ = await _build(max_retries=0)

    async def boom(tenant_id: str, req: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("broken pipe")

    stub.get_market_data_snapshot = boom  # type: ignore[assignment]
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == "vendor_transport_error"


# ---------------------------------------------------------------------------
# Circuit breaker + rate limiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breaker_opens_after_failures() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(clock, threshold=3, cooldown_ms=1000)
    client, stub, _ = await _build(clock=clock, breaker=breaker, max_retries=0)
    stub.set_error(
        "get_market_data_snapshot", None, IceVendorError("PERMISSION_DENIED", "no")
    )
    for _ in range(3):
        with pytest.raises(AdapterError):
            await client.market_data_snapshot(
                MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
            )
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == "vendor_circuit_open"


@pytest.mark.asyncio
async def test_rate_limiter_short_circuits() -> None:
    client, stub, _ = await _build(rate_rpm=60, rate_burst=1)
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
    )
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == "vendor_rate_limited"


# ---------------------------------------------------------------------------
# Per-tenant channel isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_tenant_channel_creation() -> None:
    client, stub, _ = await _build(tenant_id="tenantA")
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})

    # Call for tenantA (default bootstrap opens it already).
    await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
    )
    # Call for tenantB — triggers a new channel open on the stub.
    await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantB"
    )
    assert "tenantA" in stub.open_tenants
    assert "tenantB" in stub.open_tenants
    assert stub.open_count == 2


@pytest.mark.asyncio
async def test_channel_reuse_across_calls() -> None:
    client, stub, _ = await _build(tenant_id="tenantA")
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    for _ in range(50):
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    # Only 1 channel open across 50 calls.
    assert stub.open_count == 1


# ---------------------------------------------------------------------------
# Shutdown + disabled modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_mode_returns_not_enabled_shape() -> None:
    client, _, buf = await _build(enabled=False)
    result = await client.reference_data(
        IceReferenceDataInput(securities=[_spy()]), "tenantA"
    )
    assert result == {
        "error": "ice_not_enabled",
        "message": "ICE gRPC adapter disabled (ICE_ENABLED=false)",
    }
    ev = _events(buf)[0]
    assert ev["error_code"] == "adapter_not_enabled"


@pytest.mark.asyncio
async def test_shutdown_closes_all_channels_and_blocks_calls() -> None:
    client, stub, buf = await _build()
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
    )
    await client.shutdown()
    await client.shutdown()  # idempotent
    assert stub.close_count == 1
    with pytest.raises(AdapterError) as exc:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )
    assert exc.value.code == "adapter_shutting_down"


@pytest.mark.asyncio
async def test_audit_output_has_no_credential_tokens() -> None:
    client, stub, buf = await _build()
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    await client.market_data_snapshot(
        MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
    )
    out = buf.getvalue()
    for needle in ("secret/data", "Bearer ", "ICE_BEARER", "BEGIN CERTIFICATE", "BEGIN PRIVATE"):
        assert needle not in out


# ---------------------------------------------------------------------------
# Concurrent call safety — no channel leaks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_single_tenant_uses_one_channel() -> None:
    client, stub, _ = await _build(tenant_id="tenantA", rate_rpm=600_000, rate_burst=500)
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    stub.set_latency_ms(1)

    async def one() -> None:
        await client.market_data_snapshot(
            MarketDataSnapshotInput(securities=[_spy()]), "tenantA"
        )

    await asyncio.gather(*[one() for _ in range(50)])
    assert stub.open_count == 1
