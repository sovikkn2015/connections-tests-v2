"""Deterministic fake for the ICE Data gRPC stub.

Used in CI / tests / whenever ``ICE_ENABLED=false``. Responses are registered
programmatically via :meth:`set_response` / :meth:`set_error`; there is also
an optional disk-fixture helper for integration tests.

Key features:
* Per-tenant channel tracking — :class:`IceDataClient` asks the fake to
  ``open(tenant_id)`` before every call; the fake records which tenants it
  has "channels" for so tests can assert channel reuse and isolation.
* Error injection per RPC + per tenant for the UNAVAILABLE / PERMISSION_DENIED
  / DEADLINE_EXCEEDED flows.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from m11_grpc_adapters.ice_data.src.client.protocol import (
    IceStubProtocol,
    IceVendorError,
)


class FakeIceStub(IceStubProtocol):
    """In-memory fake. No I/O. Thread-/async-safe for the test concurrency we run."""

    def __init__(self) -> None:
        # Per-RPC default responses (applied when no tenant-specific override).
        self._defaults: dict[str, dict[str, Any]] = {
            "get_market_data_snapshot": {"quotes": []},
            "get_trade_tape": {"ticks": []},
            "get_reference_data": {"securities": []},
        }
        # Per-(rpc, tenant_id) response overrides.
        self._tenant_responses: dict[tuple[str, str], dict[str, Any]] = {}
        # Per-(rpc, tenant_id) error overrides + a default error.
        self._errors: dict[tuple[str, str], IceVendorError] = {}
        self._default_error: IceVendorError | None = None

        # Tenants we've "opened" a channel for; used by test assertions.
        self._open_tenants: set[str] = set()
        self._closed: bool = False
        self._open_count: int = 0
        self._close_count: int = 0

        self.call_log: list[tuple[str, str, dict[str, Any]]] = []
        self._latency_ms: int = 0

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    async def open(self, tenant_id: str) -> None:
        if self._closed:
            raise ConnectionError("fake ICE stub is closed")
        if tenant_id in self._open_tenants:
            # Channel already cached; no-op.
            return
        self._open_tenants.add(tenant_id)
        self._open_count += 1

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_count += 1
        self._open_tenants.clear()

    def healthy(self) -> bool:
        return not self._closed and len(self._open_tenants) > 0

    async def get_market_data_snapshot(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dispatch("get_market_data_snapshot", tenant_id, request)

    async def get_trade_tape(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dispatch("get_trade_tape", tenant_id, request)

    async def get_reference_data(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dispatch("get_reference_data", tenant_id, request)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _dispatch(
        self, rpc: str, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        if self._closed:
            raise ConnectionError("channel closed")
        if tenant_id not in self._open_tenants:
            raise ConnectionError(
                f"no channel for tenant {tenant_id!r}; call open() first"
            )
        self.call_log.append((rpc, tenant_id, dict(request)))
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)

        err = self._errors.get((rpc, tenant_id)) or self._default_error
        if err is not None:
            raise err

        resp = self._tenant_responses.get((rpc, tenant_id)) or self._defaults.get(rpc, {})
        return copy.deepcopy(resp)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def set_response(
        self, rpc: str, tenant_id: str | None, response: dict[str, Any]
    ) -> None:
        if tenant_id is None:
            self._defaults[rpc] = response
        else:
            self._tenant_responses[(rpc, tenant_id)] = response

    def set_error(
        self, rpc: str, tenant_id: str | None, error: IceVendorError | None
    ) -> None:
        if tenant_id is None:
            self._default_error = error
        else:
            if error is None:
                self._errors.pop((rpc, tenant_id), None)
            else:
                self._errors[(rpc, tenant_id)] = error

    def set_latency_ms(self, latency_ms: int) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        self._latency_ms = latency_ms

    @property
    def open_count(self) -> int:
        return self._open_count

    @property
    def close_count(self) -> int:
        return self._close_count

    @property
    def open_tenants(self) -> set[str]:
        return set(self._open_tenants)
