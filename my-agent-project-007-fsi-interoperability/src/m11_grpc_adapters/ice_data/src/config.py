"""Runtime configuration for the ICE Data gRPC adapter.

Environment-only. See spec §7 for the full table.
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
    except ValueError as exc:
        raise ValueError(f"env {name}={raw!r} is not an integer") from exc


def _env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required:
            raise ValueError(f"required env var {name} is not set")
        return default or ""
    return raw


@dataclass(frozen=True)
class IceConfig:
    """Immutable config snapshot for the ICE Data adapter."""

    enabled: bool
    target: str
    tenant_id: str
    bearer_token_vault_path: str
    mtls_cert_vault_path: str
    mtls_key_vault_path: str
    mtls_ca_vault_path: str
    channel_pool_size: int
    channel_idle_s: int
    circuit_threshold: int
    circuit_cooldown_ms: int
    rate_limit_rpm: int
    rate_limit_burst: int
    secrets_backend: str
    fixtures_dir: str
    http_port: int
    log_level: str


def load_config(env: dict[str, str] | None = None) -> IceConfig:
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


def _load_from_os_environ() -> IceConfig:
    enabled = _env_bool("ICE_ENABLED", False)

    def _path(name: str, default: str) -> str:
        return _env_str(name, default=default if not enabled else "", required=enabled)

    backend = _env_str("ICE_SECRETS_BACKEND", "vault").lower()
    if backend not in {"vault", "fake"}:
        raise ValueError(f"ICE_SECRETS_BACKEND must be vault or fake, got {backend!r}")

    return IceConfig(
        enabled=enabled,
        target=_env_str("ICE_TARGET", "localhost:50051"),
        tenant_id=_env_str("ICE_TENANT_ID", "default-tenant"),
        bearer_token_vault_path=_path(
            "ICE_BEARER_TOKEN_VAULT_PATH", "secret/data/007/m11-grpc/bearer"
        ),
        mtls_cert_vault_path=_path(
            "ICE_MTLS_CERT_VAULT_PATH", "secret/data/007/m11-grpc/mtls/cert"
        ),
        mtls_key_vault_path=_path(
            "ICE_MTLS_KEY_VAULT_PATH", "secret/data/007/m11-grpc/mtls/key"
        ),
        mtls_ca_vault_path=_path(
            "ICE_MTLS_CA_VAULT_PATH", "secret/data/007/m11-grpc/mtls/ca"
        ),
        channel_pool_size=_env_int("ICE_CHANNEL_POOL_SIZE", 4),
        channel_idle_s=_env_int("ICE_CHANNEL_IDLE_S", 300),
        circuit_threshold=_env_int("ICE_CIRCUIT_THRESHOLD", 5),
        circuit_cooldown_ms=_env_int("ICE_CIRCUIT_COOLDOWN_MS", 30_000),
        rate_limit_rpm=_env_int("ICE_RATE_LIMIT_RPM", 1200),
        rate_limit_burst=_env_int("ICE_RATE_LIMIT_BURST", 100),
        secrets_backend=backend,
        fixtures_dir=_env_str("ICE_FIXTURES_DIR", "/app/fixtures/ice"),
        http_port=_env_int("HTTP_PORT", 8080),
        log_level=_env_str("LOG_LEVEL", "info").lower(),
    )
