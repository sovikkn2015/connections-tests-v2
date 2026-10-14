"""Swappable seam between the adapter and the ICE gRPC stubs.

The adapter code only talks to :class:`IceStubProtocol`. Concrete
implementations:

* :class:`FakeIceStub` (default) — deterministic, used in CI / tests and
  whenever ``ICE_ENABLED`` is false.
* :class:`RealIceStub` — wraps the generated gRPC stub, only instantiated
  when ``ICE_ENABLED=true`` AND the ``grpcio`` module is importable.

The adapter surfaces three RPCs:
* ``get_market_data_snapshot(req)``
* ``get_trade_tape(req)``
* ``get_reference_data(req)``

Each takes a plain dict (JSON-serializable) and returns a dict. The real stub
converts dict → protobuf → network → protobuf → dict; the fake short-circuits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IceVendorError(Exception):
    """Raised when the stub returns a vendor-side error.

    Carries a :attr:`grpc_status_name` string (e.g. ``"UNAVAILABLE"``,
    ``"PERMISSION_DENIED"``) for the error-translation table in
    :class:`IceDataClient`. The real stub populates this from
    ``grpc.aio.AioRpcError.code().name``.
    """

    def __init__(
        self,
        grpc_status_name: str,
        message: str,
        *,
        debug_string: str | None = None,
    ) -> None:
        super().__init__(message)
        self.grpc_status_name = grpc_status_name
        self.message = message
        self.debug_string = debug_string


class IceStubProtocol(ABC):
    """Three-RPC ICE Data stub interface."""

    @abstractmethod
    async def open(self, tenant_id: str) -> None:
        """Open the per-tenant channel (or mark fake ready)."""

    @abstractmethod
    async def close(self) -> None:
        """Close all channels. Idempotent."""

    @abstractmethod
    def healthy(self) -> bool:
        """Sync health check — must not perform I/O."""

    @abstractmethod
    async def get_market_data_snapshot(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """NBBO snapshot for N securities."""

    @abstractmethod
    async def get_trade_tape(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Historical trade ticks."""

    @abstractmethod
    async def get_reference_data(
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Security master."""
