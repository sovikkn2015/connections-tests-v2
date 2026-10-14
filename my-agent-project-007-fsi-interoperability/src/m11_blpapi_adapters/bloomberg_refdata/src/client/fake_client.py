"""Deterministic fake BLPAPI client.

Serves the record-and-replay fixtures under ``tests/fixtures/bloomberg/``
(or whatever directory ``BLPAPI_FIXTURES_DIR`` points at). Used in CI and
whenever ``BLPAPI_ENABLED=false`` — the adapter still serves all 4 tools, it
just answers from canned responses.

Fixtures are JSON files; naming convention:

    {operation}__{hash_of_sorted_payload_keys}.json

For our test suite we use explicit file names the test controls (via
``set_fixture`` / programmatic load) so tests stay self-contained and don't
depend on disk layout.

The fake also supports **error injection** — register a :class:`BlpapiVendorError`
against a fixture key and it will be raised instead of returning data. This is
how the unit tests exercise ``NOT_ENTITLED``, ``INVALID_FIELD`` etc. without a
real Terminal.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiClientProtocol,
    BlpapiRequest,
    BlpapiResponse,
    BlpapiVendorError,
)


class FakeBlpapiClient(BlpapiClientProtocol):
    """In-memory fake. No I/O, fully deterministic.

    A fixture is keyed by ``(operation, canonical_payload_key)`` where the
    canonical key is the SHA-256 of the sorted JSON rendering of the payload.
    Registering a response via :meth:`set_fixture` with an explicit key is the
    preferred test pattern; :meth:`load_fixture_file` supports disk-loaded
    captures for integration tests.
    """

    def __init__(self, fixtures_dir: str | Path | None = None) -> None:
        self._fixtures_dir = Path(fixtures_dir) if fixtures_dir else None
        self._responses: dict[tuple[str, str], BlpapiResponse] = {}
        self._errors: dict[tuple[str, str], BlpapiVendorError] = {}
        self._default_response: BlpapiResponse | None = None
        self._default_error: BlpapiVendorError | None = None
        self._open_flag = False
        # Track invocations for test assertions.
        self.call_log: list[BlpapiRequest] = []
        # Optional injected latency — async sleep before returning.
        self._latency_ms: int = 0
        # Counters for session-stress testing.
        self._concurrent: int = 0
        self._max_concurrent: int = 0
        self._concurrency_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    async def open(self) -> None:
        self._open_flag = True

    async def close(self) -> None:
        self._open_flag = False

    def healthy(self) -> bool:
        return self._open_flag

    async def execute(self, req: BlpapiRequest) -> BlpapiResponse:
        if not self._open_flag:
            raise ConnectionError("fake BLPAPI client is not open")

        self.call_log.append(req)
        async with self._concurrency_lock:
            self._concurrent += 1
            self._max_concurrent = max(self._max_concurrent, self._concurrent)
        try:
            if self._latency_ms > 0:
                await asyncio.sleep(self._latency_ms / 1000.0)

            key = _canonical_key(req)
            wildcard = (req.operation, _WILDCARD_KEY)

            # Error injections take precedence over data fixtures.
            err = (
                self._errors.get(key)
                or self._errors.get(wildcard)
                or self._default_error
            )
            if err is not None:
                raise err

            resp = (
                self._responses.get(key)
                or self._responses.get(wildcard)
                or self._default_response
            )
            if resp is None:
                # Graceful default — empty data. Tests that care assert the key
                # was registered; tests that don't care get a harmless shape.
                return BlpapiResponse(data={}, partial=False, vendor_response_code=0)
            # Return a deep copy so tests can't mutate the fixture cache.
            return BlpapiResponse(
                data=copy.deepcopy(resp.data),
                partial=resp.partial,
                vendor_response_code=resp.vendor_response_code,
            )
        finally:
            async with self._concurrency_lock:
                self._concurrent -= 1

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def set_fixture(
        self,
        operation: str,
        payload: dict[str, Any] | None,
        response: BlpapiResponse,
    ) -> None:
        key = (operation, _hash_payload(payload))
        self._responses[key] = response

    def set_error(
        self,
        operation: str,
        payload: dict[str, Any] | None,
        error: BlpapiVendorError,
    ) -> None:
        key = (operation, _hash_payload(payload))
        self._errors[key] = error

    def set_default_response(self, response: BlpapiResponse) -> None:
        self._default_response = response

    def set_default_error(self, error: BlpapiVendorError | None) -> None:
        self._default_error = error

    def set_latency_ms(self, latency_ms: int) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        self._latency_ms = latency_ms

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def reset_counters(self) -> None:
        self._max_concurrent = 0
        self.call_log.clear()

    def load_fixture_file(self, filename: str, operation: str) -> None:
        """Load a JSON fixture from ``fixtures_dir`` and register as default."""
        if self._fixtures_dir is None:
            raise RuntimeError("fixtures_dir not configured")
        path = self._fixtures_dir / filename
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        response = BlpapiResponse(
            data=data.get("data", {}),
            partial=bool(data.get("partial", False)),
            vendor_response_code=int(data.get("vendor_response_code", 0)),
        )
        # Register under the operation as a default (no payload-hash match).
        self._responses[(operation, _WILDCARD_KEY)] = response


_WILDCARD_KEY = "*"


def _hash_payload(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return _WILDCARD_KEY
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_key(req: BlpapiRequest) -> tuple[str, str]:
    """Lookup key for the fixture / error registry."""
    # Try exact payload match first; fall back to wildcard.
    exact = (req.operation, _hash_payload(req.payload))
    return exact
