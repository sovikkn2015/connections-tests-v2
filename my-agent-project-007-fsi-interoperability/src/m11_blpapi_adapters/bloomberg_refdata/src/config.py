"""Runtime configuration for the Bloomberg refdata adapter.

Every value comes from environment variables (Rule 20 — zero credentials in
config files or source). Vault paths are strings, not values.

See `.kiro/specs/m11-blpapi-adapter.md` §7 for the full env-var table.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover — env-parse hardening
        raise ValueError(f"env {name}={raw!r} is not an integer") from exc


def _env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required:
            raise ValueError(f"required env var {name} is not set")
        return default or ""
    return raw


@dataclass(frozen=True)
class BlpapiConfig:
    """Immutable config snapshot loaded from environment.

    Fields
    ------
    enabled:
        False by default. When True the adapter attempts to import `blpapi` and
        open a live session. Tests / CI / tenants without Bloomberg leave this
        False — tool calls then return :data:`ADAPTER_NOT_ENABLED_SHAPE`.
    host / port:
        BLPAPI transport target. Usually ``localhost:8194`` for a desktop
        Terminal; different for B-PIPE / SAPI deployments.
    uuid_vault_path / serial_vault_path:
        Vault paths for the numeric BPIPE UUID + terminal serial number. Only
        required when ``enabled`` is True.
    client_mode:
        ``DAPI`` (desktop API — most common) or ``SAPI`` (server API).
    session_timeout_ms:
        Session open timeout.
    circuit_threshold / circuit_cooldown_ms:
        Breaker thresholds (Rule 4 — rate limiting + fail-closed).
    rate_limit_rpm / rate_limit_burst:
        Per-pod rate ceiling (Bloomberg default 600 rpm).
    fixtures_dir:
        Directory containing record-and-replay fixtures for fake mode.
    secrets_backend:
        ``vault`` (production) or ``fake`` (tests).
    http_port:
        FastAPI MCP port.
    log_level:
        ``info`` / ``debug`` / ``warning`` / ``error``.
    """

    enabled: bool
    host: str
    port: int
    uuid_vault_path: str
    serial_vault_path: str
    client_mode: str
    session_timeout_ms: int
    circuit_threshold: int
    circuit_cooldown_ms: int
    rate_limit_rpm: int
    rate_limit_burst: int
    fixtures_dir: str
    secrets_backend: str
    http_port: int
    log_level: str


def load_config(env: dict[str, str] | None = None) -> BlpapiConfig:
    """Load :class:`BlpapiConfig` from env. Defaults to :data:`os.environ`."""
    if env is not None:
        old = os.environ.copy()
        os.environ.clear()
        os.environ.update({k: str(v) for k, v in env.items() if v is not None})
        try:
            return _load_from_os_environ()
        finally:
            os.environ.clear()
            os.environ.update(old)
    return _load_from_os_environ()


def _load_from_os_environ() -> BlpapiConfig:
    enabled = _env_bool("BLPAPI_ENABLED", False)
    uuid_path = _env_str(
        "BLPAPI_UUID_VAULT_PATH",
        default="secret/data/007/m11-blpapi/uuid" if not enabled else "",
        required=enabled,
    )
    serial_path = _env_str(
        "BLPAPI_SERIAL_VAULT_PATH",
        default="secret/data/007/m11-blpapi/serial" if not enabled else "",
        required=enabled,
    )
    mode = _env_str("BLPAPI_CLIENT_MODE", "DAPI").upper()
    if mode not in {"DAPI", "SAPI"}:
        raise ValueError(f"BLPAPI_CLIENT_MODE must be DAPI or SAPI, got {mode!r}")

    backend = _env_str("BLPAPI_SECRETS_BACKEND", "vault").lower()
    if backend not in {"vault", "fake"}:
        raise ValueError(f"BLPAPI_SECRETS_BACKEND must be vault or fake, got {backend!r}")

    return BlpapiConfig(
        enabled=enabled,
        host=_env_str("BLPAPI_HOST", "localhost"),
        port=_env_int("BLPAPI_PORT", 8194),
        uuid_vault_path=uuid_path,
        serial_vault_path=serial_path,
        client_mode=mode,
        session_timeout_ms=_env_int("BLPAPI_SESSION_TIMEOUT_MS", 30_000),
        circuit_threshold=_env_int("BLPAPI_CIRCUIT_THRESHOLD", 5),
        circuit_cooldown_ms=_env_int("BLPAPI_CIRCUIT_COOLDOWN_MS", 30_000),
        rate_limit_rpm=_env_int("BLPAPI_RATE_LIMIT_RPM", 600),
        rate_limit_burst=_env_int("BLPAPI_RATE_LIMIT_BURST", 60),
        fixtures_dir=_env_str("BLPAPI_FIXTURES_DIR", "/app/fixtures/bloomberg"),
        secrets_backend=backend,
        http_port=_env_int("HTTP_PORT", 8080),
        log_level=_env_str("LOG_LEVEL", "info").lower(),
    )
