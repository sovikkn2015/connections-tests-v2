"""
M9 Task 17 -- .env.example shipped + no credential-shaped names.

AC14.4, Recommended Fix 7.
"""

from __future__ import annotations

import pathlib

ENV_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m9_intent_router"
    / ".env.example"
)


def test_env_example_exists():
    assert ENV_PATH.exists(), "AC14.4 -- .env.example must ship with M9"


def test_env_example_has_required_keys():
    content = ENV_PATH.read_text()
    for key in (
        "AWS_REGION",
        "M9_PROVIDER",
        "M9_MODEL_ID",
        "M9_TIMEOUT_MS",
        "M9_TENANT_HMAC_KEY_VAULT_PATH",
    ):
        assert key in content, f".env.example missing {key}"


def test_env_example_has_no_credential_shaped_keys():
    for line in ENV_PATH.read_text().splitlines():
        if line.strip().startswith("#") or "=" not in line:
            continue
        key, _, _ = line.partition("=")
        key_l = key.lower().strip()
        assert "password" not in key_l
        assert "api_key" not in key_l
        assert "apikey" not in key_l
