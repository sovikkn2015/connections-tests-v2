"""Task 19 -- .env.example shipped at src/m8_pipeline_engine/.env.example.

AC14.6: Required keys include AWS_REGION, M8_MODEL_ID, M8_CHECKPOINTER_*,
M8_HITL_HMAC_KEY_VAULT_PATH, M8_GATEWAY_*, M8_AUDIT_* (new v0.2.0).
"""

import pathlib


def _m8_src_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        cand = p / "src" / "m8_pipeline_engine"
        if cand.is_dir():
            return cand
    raise RuntimeError("m8_pipeline_engine not found")


def test_env_example_exists_and_has_required_keys() -> None:
    env = _m8_src_root() / ".env.example"
    assert env.exists(), "src/m8_pipeline_engine/.env.example must ship"
    text = env.read_text()

    required_keys = [
        "AWS_REGION",
        "M8_MODEL_ID",
        "M8_CHECKPOINTER_BACKEND",
        "M8_CHECKPOINTER_DSN_VAULT_PATH",
        "M8_HITL_HMAC_KEY_VAULT_PATH",
        "M8_GATEWAY_BASE_URL",
        "M8_AUDIT_BASE_URL",
        "M8_HITL_TIMEOUT_SECONDS",
        "M8_MAX_WALL_CLOCK_SECONDS",
    ]
    for key in required_keys:
        assert f"{key}=" in text, f"missing {key} in .env.example"


def test_env_example_no_credential_shaped_values() -> None:
    env = _m8_src_root() / ".env.example"
    text = env.read_text().lower()
    for forbidden in ("password=", "api_key=", "secret_key=", "bearer "):
        assert forbidden not in text, f"forbidden token: {forbidden}"
