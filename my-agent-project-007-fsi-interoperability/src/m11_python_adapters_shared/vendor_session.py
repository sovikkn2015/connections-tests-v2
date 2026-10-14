"""Abstract base class for a long-lived vendor connection.

BLPAPI's ``blpapi.Session``, gRPC's ``grpc.aio.Channel``, and SFTP's
``paramiko.SFTPClient`` all share the same coarse lifecycle shape:

    open() → healthy() → …calls… → close()

Where opening is expensive (TLS handshake, binary handshake, auth) and calls
are cheap per-bounce. :class:`VendorSession` is the common ABC so the shared
infrastructure (health-check wiring, SIGTERM handler) can reason about any
adapter's session without caring which vendor.

Contract:

* :meth:`open` — idempotent. Safe to call when already open.
* :meth:`close` — idempotent. Safe to call when already closed.
* :meth:`healthy` — synchronous; must not perform network I/O. Checks only
  local state (e.g. blpapi.Session started + authorized; gRPC channel
  connectivity state != SHUTDOWN).
* :meth:`is_open` — read-only snapshot of the open flag.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SessionNotOpenError(Exception):
    """Operation attempted on a closed / never-opened session."""


class VendorSession(ABC):
    """Abstract long-lived vendor connection.

    Concrete subclasses override :meth:`_do_open` and :meth:`_do_close` for the
    vendor-specific work. The public :meth:`open` / :meth:`close` provide the
    idempotence guard via :attr:`_open_flag`.
    """

    def __init__(self) -> None:
        self._open_flag: bool = False

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def _do_open(self) -> None:
        """Perform the actual connection / handshake. Raise on failure."""

    @abstractmethod
    async def _do_close(self) -> None:
        """Release resources. Must not raise for already-closed sessions."""

    @abstractmethod
    def healthy(self) -> bool:
        """Synchronous health check. Must not perform network I/O."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def open(self) -> None:
        if self._open_flag:
            return
        await self._do_open()
        self._open_flag = True

    async def close(self) -> None:
        if not self._open_flag:
            return
        try:
            await self._do_close()
        finally:
            # Mark closed even if _do_close raised — further calls must short-circuit.
            self._open_flag = False

    @property
    def is_open(self) -> bool:
        return self._open_flag

    def assert_open(self) -> None:
        if not self._open_flag:
            raise SessionNotOpenError(
                f"{type(self).__name__} is not open; call open() first"
            )
