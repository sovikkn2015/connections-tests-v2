"""Tests for `m11_python_adapters_shared` infrastructure.

Covers the building blocks used by both BLPAPI and gRPC adapters:
* Clock (fake vs system)
* CircuitBreaker state machine
* RateLimiter token bucket
* AuditEmitter JSON-line contract
* AdapterError vocabulary
* FakeVaultClient
"""

from __future__ import annotations

import io
import json

import pytest

from m11_python_adapters_shared import (
    ADAPTER_ERROR_CODES,
    AdapterError,
    AuditEmitter,
    AuditEvent,
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    FakeClock,
    FakeVaultClient,
    HealthStatus,
    RateLimiter,
    RateLimitExceeded,
    ServerInfo,
    SystemClock,
    ToolDefinition,
    VaultNotFound,
    VendorSession,
    build_app,
    is_retryable_code,
)


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


def test_system_clock_returns_positive_ms() -> None:
    c = SystemClock()
    assert c.now_ms() > 0


def test_fake_clock_advances_deterministically() -> None:
    c = FakeClock(start_ms=1_000)
    assert c.now_ms() == 1_000
    c.advance_ms(500)
    assert c.now_ms() == 1_500
    c.set_ms(2_000)
    assert c.now_ms() == 2_000
    with pytest.raises(ValueError):
        c.advance_ms(-1)
    with pytest.raises(ValueError):
        c.set_ms(500)  # cannot go backwards


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


def test_breaker_starts_closed() -> None:
    cb = CircuitBreaker(FakeClock(), threshold=3, cooldown_ms=1000)
    assert cb.state == CircuitState.CLOSED


def test_breaker_opens_after_threshold_failures() -> None:
    cb = CircuitBreaker(FakeClock(), threshold=3, cooldown_ms=1000)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_breaker_check_raises_when_open() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(clock, threshold=2, cooldown_ms=1000)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitBreakerOpen) as exc:
        cb.check()
    assert exc.value.cooldown_remaining_ms == 1000


def test_breaker_half_open_after_cooldown() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(clock, threshold=1, cooldown_ms=100)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    clock.advance_ms(100)
    cb.check()  # transitions OPEN -> HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN


def test_breaker_half_open_success_closes() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(clock, threshold=1, cooldown_ms=10)
    cb.record_failure()
    clock.advance_ms(10)
    cb.check()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_breaker_half_open_failure_reopens() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(clock, threshold=1, cooldown_ms=10)
    cb.record_failure()
    clock.advance_ms(10)
    cb.check()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_breaker_validates_inputs() -> None:
    with pytest.raises(ValueError):
        CircuitBreaker(FakeClock(), threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(FakeClock(), cooldown_ms=-1)


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_allows_burst() -> None:
    rl = RateLimiter(FakeClock(), rpm=60, burst=5)
    for _ in range(5):
        rl.acquire("firm1")
    with pytest.raises(RateLimitExceeded) as exc:
        rl.acquire("firm1")
    assert exc.value.retry_after_ms > 0


def test_rate_limiter_refills() -> None:
    clock = FakeClock()
    rl = RateLimiter(clock, rpm=6000, burst=3)  # 100 tokens/sec -> 1 token per 10ms
    for _ in range(3):
        rl.acquire("firm1")
    with pytest.raises(RateLimitExceeded):
        rl.acquire("firm1")
    clock.advance_ms(10)
    rl.acquire("firm1")


def test_rate_limiter_per_firm_isolation() -> None:
    rl = RateLimiter(FakeClock(), rpm=60, burst=1)
    rl.acquire("firm_a")
    # firm_b still has its own bucket
    rl.acquire("firm_b")
    with pytest.raises(RateLimitExceeded):
        rl.acquire("firm_a")


def test_rate_limiter_snapshot() -> None:
    rl = RateLimiter(FakeClock(), rpm=60, burst=10)
    assert rl.snapshot_tokens("firm_x") == 10.0
    rl.acquire("firm_x")
    assert rl.snapshot_tokens("firm_x") == 9.0


def test_rate_limiter_validates_inputs() -> None:
    with pytest.raises(ValueError):
        RateLimiter(FakeClock(), rpm=0, burst=1)
    with pytest.raises(ValueError):
        RateLimiter(FakeClock(), rpm=1, burst=0)


# ---------------------------------------------------------------------------
# AuditEmitter
# ---------------------------------------------------------------------------


def test_audit_emitter_writes_json_line() -> None:
    buf = io.StringIO()
    ae = AuditEmitter(logger=None, stream=buf)
    ev = AuditEvent(
        event="test.tool_audit",
        tool="test.hello",
        firm_id="firm1",
        outcome="success",
        duration_ms=42,
        adapter_name="test-adapter",
        vendor="test-vendor",
        timestamp_ms=1_700_000_000_000,
    )
    ae.emit(ev)
    lines = buf.getvalue().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event"] == "test.tool_audit"
    assert parsed["outcome"] == "success"
    assert parsed["duration_ms"] == 42


def test_audit_emitter_includes_error_code_on_failure() -> None:
    buf = io.StringIO()
    ae = AuditEmitter(logger=None, stream=buf)
    ev = AuditEvent(
        event="test.tool_audit",
        tool="test.hello",
        firm_id="firm1",
        outcome="failure",
        duration_ms=10,
        adapter_name="a",
        vendor="v",
        timestamp_ms=1,
        error_code="vendor_error",
        vendor_status=500,
        retryable=False,
        fields={"extra": 1},
    )
    ae.emit(ev)
    parsed = json.loads(buf.getvalue().strip())
    assert parsed["error_code"] == "vendor_error"
    assert parsed["vendor_status"] == 500
    assert parsed["retryable"] is False
    assert parsed["extra"] == 1


def test_audit_emitter_multiple_events_each_on_own_line() -> None:
    buf = io.StringIO()
    ae = AuditEmitter(logger=None, stream=buf)
    for i in range(3):
        ae.emit(
            AuditEvent(
                event="e",
                tool="t",
                firm_id="f",
                outcome="success",
                duration_ms=i,
                adapter_name="a",
                vendor="v",
                timestamp_ms=i,
            )
        )
    lines = buf.getvalue().strip().split("\n")
    assert len(lines) == 3
    for i, line in enumerate(lines):
        assert json.loads(line)["duration_ms"] == i


# ---------------------------------------------------------------------------
# AdapterError
# ---------------------------------------------------------------------------


def test_adapter_error_accepts_known_code() -> None:
    err = AdapterError("vendor_rate_limited", "too many")
    assert err.code == "vendor_rate_limited"
    assert err.retryable is True
    assert err.message == "too many"


def test_adapter_error_rejects_unknown_code() -> None:
    with pytest.raises(ValueError):
        AdapterError("not_a_real_code", "x")


def test_is_retryable_code_table() -> None:
    assert is_retryable_code("vendor_timeout") is True
    assert is_retryable_code("vendor_unavailable") is True
    assert is_retryable_code("vendor_not_entitled") is False
    assert is_retryable_code("invalid_arguments") is False


def test_error_codes_vocabulary_is_frozen() -> None:
    with pytest.raises((TypeError, AttributeError)):
        ADAPTER_ERROR_CODES.add("new_code")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FakeVaultClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_vault_client_set_and_get() -> None:
    v = FakeVaultClient()
    v.set_secret("secret/data/007/foo", "bar")
    assert await v.get_secret("secret/data/007/foo") == "bar"


@pytest.mark.asyncio
async def test_fake_vault_client_raises_on_missing() -> None:
    v = FakeVaultClient()
    with pytest.raises(VaultNotFound):
        await v.get_secret("secret/data/missing")


def test_fake_vault_client_validates_inputs() -> None:
    v = FakeVaultClient()
    with pytest.raises(ValueError):
        v.set_secret("", "x")
    with pytest.raises(TypeError):
        v.set_secret("p", 123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# VendorSession
# ---------------------------------------------------------------------------


class _StubSession(VendorSession):
    def __init__(self) -> None:
        super().__init__()
        self.opens = 0
        self.closes = 0

    async def _do_open(self) -> None:
        self.opens += 1

    async def _do_close(self) -> None:
        self.closes += 1

    def healthy(self) -> bool:
        return self.is_open


@pytest.mark.asyncio
async def test_vendor_session_idempotent_open_close() -> None:
    s = _StubSession()
    await s.open()
    await s.open()
    assert s.opens == 1
    await s.close()
    await s.close()
    assert s.closes == 1


# ---------------------------------------------------------------------------
# MCP server helpers
# ---------------------------------------------------------------------------


def test_build_app_returns_fastapi_instance() -> None:
    from fastapi import FastAPI

    info = ServerInfo(name="t", version="0.1.0", vendor="tv", capabilities={})

    async def healthy() -> HealthStatus:
        return HealthStatus(ok=True, checks={"x": "ok"})

    app = build_app(info, {}, healthy)
    assert isinstance(app, FastAPI)
