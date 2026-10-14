"""
M6 Redis-Backed Resilience — Tests.

Tests cover:
  1. RedisRateLimiter with mock Redis (sliding window via sorted sets)
  2. RedisCircuitBreakerStateStore with mock Redis (hash-based state)
  3. Fallback to in-memory when Redis connection fails
  4. MCPProxy uses Redis when redis_client is provided
  5. MCPProxy uses in-memory when redis_client is None

All tests use mock Redis — no real Redis required.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Package registration (same pattern as test_m6_gateway.py) ────

_pkg_dir = Path(__file__).parent
_pkg_name = "m6_mcp_gateway"
if _pkg_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg_name,
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg_name] = _mod
    _spec.loader.exec_module(_mod)

for _submod_name in ("models", "resilience", "mcp_proxy"):
    _full_name = f"{_pkg_name}.{_submod_name}"
    if _full_name not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _full_name,
            _pkg_dir / f"{_submod_name}.py",
            submodule_search_locations=[str(_pkg_dir)],
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        sys.modules[_full_name] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from m6_mcp_gateway.models import CircuitState, GatewayConfig
from m6_mcp_gateway.resilience import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    InMemoryCircuitBreakerStateStore,
    RateLimiter,
    RedisCircuitBreakerStateStore,
    RedisRateLimiter,
    create_redis_client,
)
from m6_mcp_gateway.mcp_proxy import MCPProxy


# ── Mock Redis Helper ────────────────────────────────────────────


class MockRedisPipeline:
    """Mock Redis pipeline that collects commands and returns results."""

    def __init__(self, parent: "MockRedis") -> None:
        self._parent = parent
        self._commands: list[tuple[str, tuple]] = []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        self._commands.append(("zremrangebyscore", (key, min_score, max_score)))
        return self

    def zcard(self, key: str):
        self._commands.append(("zcard", (key,)))
        return self

    def zadd(self, key: str, mapping: dict):
        self._commands.append(("zadd", (key, mapping)))
        return self

    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", (key, seconds)))
        return self

    async def execute(self) -> list:
        results = []
        for cmd, args in self._commands:
            if cmd == "zremrangebyscore":
                key, min_s, max_s = args
                if key in self._parent._sorted_sets:
                    self._parent._sorted_sets[key] = {
                        m: s for m, s in self._parent._sorted_sets[key].items()
                        if s > max_s
                    }
                results.append(0)
            elif cmd == "zcard":
                key = args[0]
                results.append(len(self._parent._sorted_sets.get(key, {})))
            elif cmd == "zadd":
                key, mapping = args
                if key not in self._parent._sorted_sets:
                    self._parent._sorted_sets[key] = {}
                self._parent._sorted_sets[key].update(mapping)
                results.append(len(mapping))
            elif cmd == "expire":
                results.append(True)
        self._commands.clear()
        return results


class MockRedis:
    """In-memory mock of redis.asyncio client for testing."""

    def __init__(self, fail: bool = False) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise ConnectionError("Mock Redis connection failed")
        return True

    async def hgetall(self, key: str) -> dict:
        if self._fail:
            raise ConnectionError("Mock Redis connection failed")
        data = self._hashes.get(key, {})
        # Return bytes like real Redis
        return {k.encode(): v.encode() for k, v in data.items()}

    async def hset(self, key: str, mapping: dict = None, **kwargs) -> int:
        if self._fail:
            raise ConnectionError("Mock Redis connection failed")
        if key not in self._hashes:
            self._hashes[key] = {}
        if mapping:
            self._hashes[key].update({str(k): str(v) for k, v in mapping.items()})
        return len(mapping or {})

    async def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> list:
        if self._fail:
            raise ConnectionError("Mock Redis connection failed")
        items = self._sorted_sets.get(key, {})
        sorted_items = sorted(items.items(), key=lambda x: x[1])
        sliced = sorted_items[start:end + 1] if end >= 0 else sorted_items[start:]
        if withscores:
            return [(m.encode() if isinstance(m, str) else m, s) for m, s in sliced]
        return [m.encode() if isinstance(m, str) else m for m, _ in sliced]

    def pipeline(self) -> MockRedisPipeline:
        if self._fail:
            raise ConnectionError("Mock Redis connection failed")
        return MockRedisPipeline(self)

    async def aclose(self) -> None:
        pass


# ═══════════════════════════════════════════════════════════════════
# TEST 1: RedisRateLimiter with mock Redis
# ═══════════════════════════════════════════════════════════════════


class TestRedisRateLimiter:
    """Tests for Redis-backed sliding window rate limiter."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        """Requests within limit should be allowed."""
        redis = MockRedis()
        rl = RedisRateLimiter(redis)
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_blocks_after_limit(self):
        """Requests exceeding limit should be blocked."""
        redis = MockRedis()
        rl = RedisRateLimiter(redis)
        for _ in range(5):
            allowed, _ = await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
            assert allowed is True

        # 6th request should be blocked
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is False
        assert retry_after is not None
        assert retry_after >= 1

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        """Different users have independent rate limits in Redis."""
        redis = MockRedis()
        rl = RedisRateLimiter(redis)
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
        # user2 should still be allowed
        allowed, _ = await rl.check_rate_limit(
            "user2", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_different_tools_independent(self):
        """Different tools have independent rate limits in Redis."""
        redis = MockRedis()
        rl = RedisRateLimiter(redis)
        for _ in range(5):
            await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
        # tool2 should still be allowed
        allowed, _ = await rl.check_rate_limit(
            "user1", "tool2", max_requests=5, window_seconds=60,
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_redis_key_format(self):
        """Redis keys should follow m6:rl:{user}:{tool} format."""
        redis = MockRedis()
        rl = RedisRateLimiter(redis)
        await rl.check_rate_limit("user1", "tool1", max_requests=5, window_seconds=60)
        assert "m6:rl:user1:tool1" in redis._sorted_sets

    @pytest.mark.asyncio
    async def test_same_interface_as_in_memory(self):
        """RedisRateLimiter has same interface as RateLimiter."""
        redis = MockRedis()
        redis_rl = RedisRateLimiter(redis)
        mem_rl = RateLimiter()

        # Both should return (bool, Optional[int])
        r1 = await redis_rl.check_rate_limit("u", "t", 10, 60)
        r2 = await mem_rl.check_rate_limit("u", "t", 10, 60)
        assert type(r1) == type(r2)
        assert r1[0] is True
        assert r2[0] is True


# ═══════════════════════════════════════════════════════════════════
# TEST 2: RedisRateLimiter fallback to in-memory
# ═══════════════════════════════════════════════════════════════════


class TestRedisRateLimiterFallback:
    """Tests for fallback behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_on_redis_failure(self):
        """Should fall back to in-memory when Redis fails."""
        redis = MockRedis(fail=True)
        rl = RedisRateLimiter(redis)

        # Should not raise — falls back to in-memory
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_fallback_rate_limiting_works(self):
        """In-memory fallback should still enforce rate limits."""
        redis = MockRedis(fail=True)
        rl = RedisRateLimiter(redis)

        for _ in range(5):
            allowed, _ = await rl.check_rate_limit(
                "user1", "tool1", max_requests=5, window_seconds=60,
            )
            assert allowed is True

        # 6th request should be blocked by in-memory fallback
        allowed, retry_after = await rl.check_rate_limit(
            "user1", "tool1", max_requests=5, window_seconds=60,
        )
        assert allowed is False
        assert retry_after is not None

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(self):
        """Should log warning when falling back to in-memory."""
        redis = MockRedis(fail=True)
        rl = RedisRateLimiter(redis)

        # Patch the logger on the module where it's actually used
        import m6_mcp_gateway.resilience as res_mod
        original_logger = res_mod.logger
        mock_logger = MagicMock()
        res_mod.logger = mock_logger
        try:
            await rl.check_rate_limit("user1", "tool1", 5, 60)
            mock_logger.warning.assert_called_once()
            assert "falling back" in mock_logger.warning.call_args[0][0].lower()
        finally:
            res_mod.logger = original_logger


# ═══════════════════════════════════════════════════════════════════
# TEST 3: RedisCircuitBreakerStateStore
# ═══════════════════════════════════════════════════════════════════


class TestRedisCircuitBreakerStateStore:
    """Tests for Redis-backed circuit breaker state storage."""

    @pytest.mark.asyncio
    async def test_default_state_is_closed(self):
        """New server should default to closed state."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.closed
        assert fc == 0
        assert lft == 0.0

    @pytest.mark.asyncio
    async def test_set_and_get_state(self):
        """Should persist and retrieve circuit breaker state."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)

        await store.set_state(
            "http://test:8000",
            CircuitState.open,
            5,
            123.456,
        )
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.open
        assert fc == 5
        assert lft == 123.456

    @pytest.mark.asyncio
    async def test_half_open_state_persists(self):
        """Half-open state should be correctly stored and retrieved."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)

        await store.set_state(
            "http://test:8000",
            CircuitState.half_open,
            3,
            99.0,
        )
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.half_open

    @pytest.mark.asyncio
    async def test_redis_key_format(self):
        """Redis keys should follow m6:cb:{server_url} format."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        await store.set_state("http://test:8000", CircuitState.closed, 0, 0.0)
        assert "m6:cb:http://test:8000" in redis._hashes

    @pytest.mark.asyncio
    async def test_multiple_servers_independent(self):
        """Different servers should have independent state."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)

        await store.set_state("http://s1:8000", CircuitState.open, 5, 100.0)
        await store.set_state("http://s2:8000", CircuitState.closed, 0, 0.0)

        s1_state, s1_fc, _ = await store.get_state("http://s1:8000")
        s2_state, s2_fc, _ = await store.get_state("http://s2:8000")

        assert s1_state == CircuitState.open
        assert s1_fc == 5
        assert s2_state == CircuitState.closed
        assert s2_fc == 0

    @pytest.mark.asyncio
    async def test_fallback_on_redis_failure(self):
        """Should fall back to in-memory when Redis fails."""
        redis = MockRedis(fail=True)
        store = RedisCircuitBreakerStateStore(redis)

        # Should not raise — falls back to in-memory
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.closed
        assert fc == 0

    @pytest.mark.asyncio
    async def test_fallback_set_and_get(self):
        """Fallback in-memory store should work for set/get."""
        redis = MockRedis(fail=True)
        store = RedisCircuitBreakerStateStore(redis)

        await store.set_state("http://test:8000", CircuitState.open, 5, 100.0)
        state, fc, _ = await store.get_state("http://test:8000")
        assert state == CircuitState.open
        assert fc == 5


# ═══════════════════════════════════════════════════════════════════
# TEST 4: CircuitBreaker with Redis state store
# ═══════════════════════════════════════════════════════════════════


class TestCircuitBreakerWithRedisStore:
    """Tests for CircuitBreaker using Redis-backed state store."""

    @pytest.mark.asyncio
    async def test_opens_after_threshold_with_redis(self):
        """Circuit opens after 5 failures with Redis state store."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, state_store=store,
        )
        for _ in range(5):
            await cb.record_failure()
        assert cb.state == CircuitState.open
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_state_persisted_to_redis(self):
        """State changes should be persisted to Redis."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, state_store=store,
        )
        for _ in range(5):
            await cb.record_failure()

        # Verify state was written to Redis
        key = "m6:cb:http://test:8000"
        assert key in redis._hashes
        assert redis._hashes[key]["state"] == "open"
        assert redis._hashes[key]["failure_count"] == "5"

    @pytest.mark.asyncio
    async def test_success_resets_with_redis(self):
        """Success resets failure count in Redis store."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        cb = CircuitBreaker(
            "http://test:8000", failure_threshold=5, state_store=store,
        )
        for _ in range(4):
            await cb.record_failure()
        await cb.record_success()

        key = "m6:cb:http://test:8000"
        assert redis._hashes[key]["failure_count"] == "0"
        assert redis._hashes[key]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_registry_with_redis_store(self):
        """CircuitBreakerRegistry should pass state store to breakers."""
        redis = MockRedis()
        store = RedisCircuitBreakerStateStore(redis)
        registry = CircuitBreakerRegistry(state_store=store)

        cb = await registry.get("http://test:8000")
        assert cb._state_store is store

    @pytest.mark.asyncio
    async def test_registry_without_store_uses_in_memory(self):
        """CircuitBreakerRegistry without store uses in-memory (default)."""
        registry = CircuitBreakerRegistry()
        cb = await registry.get("http://test:8000")
        assert cb._state_store is None


# ═══════════════════════════════════════════════════════════════════
# TEST 5: MCPProxy Redis wiring
# ═══════════════════════════════════════════════════════════════════


class TestMCPProxyRedisWiring:
    """Tests for MCPProxy Redis integration."""

    def test_proxy_with_redis_uses_redis_rate_limiter(self):
        """MCPProxy with redis_client should use RedisRateLimiter."""
        redis = MockRedis()
        config = GatewayConfig()
        proxy = MCPProxy(config, redis_client=redis)
        assert type(proxy.rate_limiter).__name__ == "RedisRateLimiter"

    def test_proxy_without_redis_uses_in_memory(self):
        """MCPProxy without redis_client should use in-memory RateLimiter."""
        config = GatewayConfig()
        proxy = MCPProxy(config)
        assert type(proxy.rate_limiter).__name__ == "RateLimiter"

    def test_proxy_with_none_redis_uses_in_memory(self):
        """MCPProxy with redis_client=None should use in-memory."""
        config = GatewayConfig()
        proxy = MCPProxy(config, redis_client=None)
        assert type(proxy.rate_limiter).__name__ == "RateLimiter"

    def test_proxy_with_redis_uses_redis_cb_store(self):
        """MCPProxy with redis_client should use Redis circuit breaker store."""
        redis = MockRedis()
        config = GatewayConfig()
        proxy = MCPProxy(config, redis_client=redis)
        assert proxy.circuit_breakers._state_store is not None
        assert type(proxy.circuit_breakers._state_store).__name__ == "RedisCircuitBreakerStateStore"

    def test_proxy_without_redis_has_no_cb_store(self):
        """MCPProxy without redis_client should have no circuit breaker store."""
        config = GatewayConfig()
        proxy = MCPProxy(config)
        assert proxy.circuit_breakers._state_store is None


# ═══════════════════════════════════════════════════════════════════
# TEST 6: create_redis_client factory
# ═══════════════════════════════════════════════════════════════════


class TestCreateRedisClient:
    """Tests for the Redis client factory function."""

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_failure(self):
        """Should return None when Redis is unreachable."""
        client = await create_redis_client("redis://localhost:59999/0")
        assert client is None

    @pytest.mark.asyncio
    async def test_returns_none_logs_warning(self):
        """Should log warning when Redis connection fails."""
        import m6_mcp_gateway.resilience as res_mod
        original_logger = res_mod.logger
        mock_logger = MagicMock()
        res_mod.logger = mock_logger
        try:
            client = await create_redis_client("redis://localhost:59999/0")
            assert client is None
            mock_logger.warning.assert_called_once()
            assert "failed to connect" in mock_logger.warning.call_args[0][0].lower()
        finally:
            res_mod.logger = original_logger


# ═══════════════════════════════════════════════════════════════════
# TEST 7: InMemoryCircuitBreakerStateStore
# ═══════════════════════════════════════════════════════════════════


class TestInMemoryCircuitBreakerStateStore:
    """Tests for the in-memory circuit breaker state store."""

    @pytest.mark.asyncio
    async def test_default_state(self):
        """Default state should be closed with zero failures."""
        store = InMemoryCircuitBreakerStateStore()
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.closed
        assert fc == 0
        assert lft == 0.0

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Should store and retrieve state correctly."""
        store = InMemoryCircuitBreakerStateStore()
        await store.set_state("http://test:8000", CircuitState.open, 5, 100.0)
        state, fc, lft = await store.get_state("http://test:8000")
        assert state == CircuitState.open
        assert fc == 5
        assert lft == 100.0
