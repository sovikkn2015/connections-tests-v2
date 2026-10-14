"""Unit tests for ``m13_fix_bridge.config`` — Spec §R4.1, §7.

AC references appear inline as ``# R-x`` comments.
"""

from __future__ import annotations

import pytest

from m13_fix_bridge.config import FixConfig, load_config


def test_defaults_when_disabled() -> None:
    """When FIX_ENABLED unset, load_config returns disabled snapshot."""
    cfg = load_config(env={})
    assert isinstance(cfg, FixConfig)
    assert cfg.fix_enabled is False
    assert cfg.sessions_config_vault_path == ""
    assert cfg.seqnum_store_dir == "/var/lib/m13/seqnums"
    assert cfg.drop_copy_enabled is True
    assert cfg.kill_switch_state_path == "/var/lib/m13/kill_switch.json"
    assert cfg.aid_verify_mode == "static"
    assert cfg.secrets_backend == "vault"
    assert cfg.http_port == 8080
    assert cfg.log_level == "info"


def test_enabled_requires_session_config_path() -> None:
    """R4.1 — enabled=true without session config path fails-closed."""
    with pytest.raises(ValueError, match="FIX_SESSIONS_CONFIG_VAULT_PATH"):
        load_config(
            env={
                "FIX_ENABLED": "true",
                # session + hash salt intentionally absent
            }
        )


def test_enabled_requires_hash_salt_path() -> None:
    """R6.3 — enabled=true without hash salt path fails-closed."""
    with pytest.raises(ValueError, match="FIX_ACCOUNT_HASH_SALT_VAULT_PATH"):
        load_config(
            env={
                "FIX_ENABLED": "true",
                "FIX_SESSIONS_CONFIG_VAULT_PATH": "secret/data/007/m13/sessions",
            }
        )


def test_enabled_full_config_loads() -> None:
    """R4.1 — enabled=true with all required paths parses cleanly."""
    cfg = load_config(
        env={
            "FIX_ENABLED": "true",
            "FIX_SESSIONS_CONFIG_VAULT_PATH": "secret/data/007/m13/sessions",
            "FIX_ACCOUNT_HASH_SALT_VAULT_PATH": "secret/data/007/m13/hash_salt",
            "HTTP_PORT": "9090",
            "LOG_LEVEL": "DEBUG",
        }
    )
    assert cfg.fix_enabled is True
    assert cfg.sessions_config_vault_path == "secret/data/007/m13/sessions"
    assert cfg.account_hash_salt_vault_path == "secret/data/007/m13/hash_salt"
    assert cfg.http_port == 9090
    assert cfg.log_level == "debug"


def test_invalid_aid_verify_mode_rejected() -> None:
    """Only static/hmac/rsa accepted."""
    with pytest.raises(ValueError, match="FIX_AID_VERIFY_MODE"):
        load_config(env={"FIX_AID_VERIFY_MODE": "magic"})


def test_invalid_secrets_backend_rejected() -> None:
    """Only vault/fake accepted."""
    with pytest.raises(ValueError, match="FIX_SECRETS_BACKEND"):
        load_config(env={"FIX_SECRETS_BACKEND": "barrel"})


def test_invalid_http_port_rejected() -> None:
    """HTTP_PORT must be an integer."""
    with pytest.raises(ValueError, match="HTTP_PORT"):
        load_config(env={"HTTP_PORT": "not-a-number"})


def test_drop_copy_can_be_disabled() -> None:
    """R6 toggle — off when explicitly set."""
    cfg = load_config(
        env={
            "FIX_DROP_COPY_ENABLED": "false",
        }
    )
    assert cfg.drop_copy_enabled is False
