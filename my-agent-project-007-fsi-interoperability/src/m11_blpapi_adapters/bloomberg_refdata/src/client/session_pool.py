"""Single-session pool for the Bloomberg adapter.

BLPAPI sessions are thread-locked at the vendor level — concurrent calls on
one session interleave events in a way that breaks response demultiplexing.
The safest contract is "one in-flight request per session". We enforce that
with an :class:`asyncio.Semaphore(1)` guarding the underlying client.

Horizontal scale is achieved by running additional pods with different UUID /
serial bindings, not by multiplying sessions inside a pod.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiClientProtocol,
    BlpapiRequest,
    BlpapiResponse,
)


class BloombergSessionPool:
    """Serialize BLPAPI calls on a single underlying client.

    Parameters
    ----------
    client:
        Any :class:`BlpapiClientProtocol` implementation. The pool does not
        own the client's lifecycle beyond :meth:`close_all` — the startup
        module calls :meth:`open_all` during bootstrap and :meth:`close_all`
        on shutdown.
    """

    def __init__(self, client: BlpapiClientProtocol) -> None:
        self._client = client
        self._semaphore = asyncio.Semaphore(1)
        # Count in-flight + total calls for test visibility.
        self._in_flight = 0
        self._total_calls = 0

    async def open_all(self) -> None:
        await self._client.open()

    async def close_all(self) -> None:
        await self._client.close()

    def healthy(self) -> bool:
        return self._client.healthy()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[BlpapiClientProtocol]:
        """Context manager yielding the exclusive client handle."""
        await self._semaphore.acquire()
        self._in_flight += 1
        self._total_calls += 1
        try:
            yield self._client
        finally:
            self._in_flight -= 1
            self._semaphore.release()

    async def execute(self, req: BlpapiRequest) -> BlpapiResponse:
        """Convenience: acquire + execute in one call."""
        async with self.acquire() as client:
            return await client.execute(req)
