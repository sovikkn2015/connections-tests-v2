"""Startup + SIGTERM wiring for M13 FIX Bridge (Spec §R4, §R4.6).

Production flow (when ``FIX_ENABLED=true``):

1. Pull session config YAML from Vault path
   ``FIX_SESSIONS_CONFIG_VAULT_PATH``.
2. Parse as ``list[VenueConfig]`` — fail-closed (refuse to start) on
   invalid config.
3. Resolve SenderCompID + TargetCompID + mTLS paths from Vault for each
   venue.
4. Open the engine.
5. Install SIGTERM handler: send Logout on every active session, fsync
   seqnums, exit.

This module is kept small + injectable so tests can wire Vault and
engine stubs without touching the real FastAPI lifecycle.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import yaml

from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.models import VenueConfig


class SecretsClientProtocol(Protocol):
    async def get_secret(self, path: str) -> str: ...


class FakeSecretsClient:
    """Dict-backed Vault client for tests."""

    def __init__(self, store: dict[str, str] | None = None) -> None:
        self._store = dict(store or {})

    def set(self, path: str, value: str) -> None:
        self._store[path] = value

    async def get_secret(self, path: str) -> str:
        if path not in self._store:
            raise KeyError(path)
        return self._store[path]


@dataclass
class StartupResult:
    configs: list[VenueConfig]
    resolved_comp_ids: dict[str, tuple[str, str]]  # venue → (sender, target)


async def load_venue_configs(
    *,
    secrets: SecretsClientProtocol,
    sessions_vault_path: str,
) -> list[VenueConfig]:
    """Pull the YAML list of VenueConfig from Vault and parse.

    Fail-closed: invalid YAML or pydantic validation → ValueError.
    """
    raw = await secrets.get_secret(sessions_vault_path)
    try:
        parsed = yaml.safe_load(raw) or []
    except yaml.YAMLError as exc:
        raise ValueError(f"session config YAML parse failed: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("session config must be a YAML list")
    return [VenueConfig.model_validate(entry) for entry in parsed]


async def resolve_comp_ids(
    *,
    secrets: SecretsClientProtocol,
    configs: Sequence[VenueConfig],
) -> dict[str, tuple[str, str]]:
    """Resolve SenderCompID + TargetCompID from Vault for each venue."""
    out: dict[str, tuple[str, str]] = {}
    for vc in configs:
        sender = (await secrets.get_secret(vc.sender_comp_id_vault_path)).strip()
        target = (await secrets.get_secret(vc.target_comp_id_vault_path)).strip()
        if not sender or not target:
            raise ValueError(f"empty CompIDs for venue {vc.venue!r}")
        out[vc.venue] = (sender, target)
    return out


async def open_sessions(
    *,
    session_manager: SessionManager,
    configs: Sequence[VenueConfig],
) -> None:
    """Open the engine with the given configs."""
    await session_manager.open(configs)


def install_sigterm_handler(
    *,
    session_manager: SessionManager,
    loop: Any | None = None,
) -> None:
    """Install a SIGTERM handler that closes sessions gracefully."""
    import asyncio

    target_loop = loop or asyncio.get_event_loop()

    def _handler() -> None:
        asyncio.ensure_future(session_manager.close(graceful=True), loop=target_loop)

    try:
        target_loop.add_signal_handler(signal.SIGTERM, _handler)
        target_loop.add_signal_handler(signal.SIGINT, _handler)
    except NotImplementedError:  # pragma: no cover — Windows / event-loop unsupported
        return


__all__ = [
    "FakeSecretsClient",
    "SecretsClientProtocol",
    "StartupResult",
    "install_sigterm_handler",
    "load_venue_configs",
    "open_sessions",
    "resolve_comp_ids",
]
