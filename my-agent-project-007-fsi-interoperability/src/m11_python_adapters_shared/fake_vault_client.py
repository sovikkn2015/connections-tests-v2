"""In-memory Vault client for tests.

Real production uses a HashiCorp Vault client bound via an ExternalSecret to
a ClusterSecretStore (see `deploy/helm/.../externalsecret.yaml`). Tests inject
a :class:`FakeVaultClient` to satisfy the :class:`SecretsClientProtocol`
without standing up a real Vault.

`get_secret(path)` returns the string value registered at `path` or raises
:class:`VaultNotFound`. Paths must match the spec's Vault convention
(`secret/data/007/...`) — the fake client does no path validation, it's an
opaque key-value store.
"""

from __future__ import annotations

from typing import Dict, Protocol


class VaultNotFound(Exception):
    """Raised when a requested Vault path has no registered value."""


class SecretsClientProtocol(Protocol):
    """Shape implemented by the real and fake Vault clients."""

    async def get_secret(self, path: str) -> str: ...


class FakeVaultClient(SecretsClientProtocol):
    """Simple dict-backed vault for tests.

    Thread-safe enough for pytest-asyncio — mutation happens via
    :meth:`set_secret` during test setup and reads happen during the test body.
    """

    def __init__(self, initial: Dict[str, str] | None = None) -> None:
        self._store: Dict[str, str] = dict(initial) if initial else {}

    def set_secret(self, path: str, value: str) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError("path must be a non-empty string")
        if not isinstance(value, str):
            raise TypeError("value must be a string")
        self._store[path] = value

    async def get_secret(self, path: str) -> str:
        if path not in self._store:
            raise VaultNotFound(f"no secret at vault path: {path!r}")
        return self._store[path]

    def paths(self) -> list[str]:
        """Test helper — enumerate registered paths."""
        return sorted(self._store.keys())
