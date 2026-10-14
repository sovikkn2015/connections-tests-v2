"""Runtime configuration for the M13 FIX Bridge.

Environment-only. Every secret is a Vault path — NEVER a literal value
(Steering Rule 20).
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


def _env_str(
    name: str,
    default: str | None = None,
    *,
    required: bool = False,
) -> str:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required:
            raise ValueError(f"required env var {name} is not set")
        return default or ""
    return raw


@dataclass(frozen=True)
class FixConfig:
    """Immutable config snapshot for the M13 FIX Bridge.

    * ``fix_enabled`` gates all live-session behaviour. When false, the
      bridge runs in graceful-disabled mode (health ok, order tools
      return ``fix_enabled_false``).
    * ``sessions_config_vault_path``: path to YAML list of VenueConfig
      entries. Required when ``fix_enabled`` is true.
    * ``seqnum_store_dir``: directory for ``<sender>.<target>.json``
      seqnum files.
    * ``drop_copy_enabled``: toggle ExecReport → audit.
    * ``kill_switch_state_path``: JSON file with global + per-venue
      kill-switch state.
    * ``account_hash_salt_vault_path``: HMAC salt for account hashing
      in drop-copy events (R6.3).
    * ``aid_verify_*``: either HMAC shared-secret mode (tests/dev) or
      RS256 public-key mode (prod). Static verifier is a separate mode
      used in tests only.
    """

    fix_enabled: bool
    sessions_config_vault_path: str
    seqnum_store_dir: str
    drop_copy_enabled: bool
    kill_switch_state_path: str
    account_hash_salt_vault_path: str
    aid_verify_mode: str  # "static" | "hmac" | "rsa"
    aid_verify_shared_secret_vault_path: str
    aid_verify_public_key_path: str
    secrets_backend: str  # "vault" | "fake"
    http_port: int
    log_level: str


def load_config(env: dict[str, str] | None = None) -> FixConfig:
    """Load config from env. If ``env`` is provided, temporarily
    replaces ``os.environ`` (tests use this for isolation)."""
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


def _load_from_os_environ() -> FixConfig:
    enabled = _env_bool("FIX_ENABLED", False)

    mode = _env_str("FIX_AID_VERIFY_MODE", "static").lower()
    if mode not in {"static", "hmac", "rsa"}:
        raise ValueError(
            f"FIX_AID_VERIFY_MODE must be one of static/hmac/rsa, got {mode!r}"
        )

    backend = _env_str("FIX_SECRETS_BACKEND", "vault").lower()
    if backend not in {"vault", "fake"}:
        raise ValueError(
            f"FIX_SECRETS_BACKEND must be vault or fake, got {backend!r}"
        )

    # When enabled, session config + hash salt paths are REQUIRED.
    sessions_path = _env_str(
        "FIX_SESSIONS_CONFIG_VAULT_PATH",
        default="",
        required=enabled,
    )
    hash_salt_path = _env_str(
        "FIX_ACCOUNT_HASH_SALT_VAULT_PATH",
        default="",
        required=enabled,
    )

    return FixConfig(
        fix_enabled=enabled,
        sessions_config_vault_path=sessions_path,
        seqnum_store_dir=_env_str("FIX_SEQNUM_STORE_DIR", "/var/lib/m13/seqnums"),
        drop_copy_enabled=_env_bool("FIX_DROP_COPY_ENABLED", True),
        kill_switch_state_path=_env_str(
            "FIX_KILL_SWITCH_STATE_PATH", "/var/lib/m13/kill_switch.json"
        ),
        account_hash_salt_vault_path=hash_salt_path,
        aid_verify_mode=mode,
        aid_verify_shared_secret_vault_path=_env_str(
            "FIX_AID_VERIFY_SHARED_SECRET_VAULT_PATH", ""
        ),
        aid_verify_public_key_path=_env_str("FIX_AID_VERIFY_PUBLIC_KEY_PATH", ""),
        secrets_backend=backend,
        http_port=_env_int("HTTP_PORT", 8080),
        log_level=_env_str("LOG_LEVEL", "info").lower(),
    )


__all__ = ["FixConfig", "load_config"]
