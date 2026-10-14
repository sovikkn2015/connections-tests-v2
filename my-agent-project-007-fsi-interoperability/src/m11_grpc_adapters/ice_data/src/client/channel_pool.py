"""Thin pool wrapper around the ICE stub.

The stub itself keeps a per-tenant channel cache (see
:class:`RealIceStub`). This pool exists to give tests + the refdata client a
uniform handle for lifecycle management without reaching into the stub
internals.
"""

from __future__ import annotations

from m11_grpc_adapters.ice_data.src.client.protocol import IceStubProtocol


class IceChannelPool:
    """Single-stub wrapper. Keeps the bootstrap + shutdown path one-liner."""

    def __init__(self, stub: IceStubProtocol) -> None:
        self._stub = stub

    @property
    def stub(self) -> IceStubProtocol:
        return self._stub

    async def ensure_open(self, tenant_id: str) -> None:
        await self._stub.open(tenant_id)

    async def close_all(self) -> None:
        await self._stub.close()

    def healthy(self) -> bool:
        return self._stub.healthy()
