"""Shared test fixtures. No AWS credentials required.

Seeds the env vars the coordinator expects (model ids, signing keys) with
stub values so tests can exercise the full import path without real creds.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Put the v3 project root on sys.path so `from openclaw...` resolves.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture(autouse=True)
def _seed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env seed applied to every test — never leak between suites."""
    monkeypatch.setenv("BEDROCK_SONNET_MODEL_ID", "anthropic.stub-sonnet-v1")
    monkeypatch.setenv("BEDROCK_HAIKU_MODEL_ID", "anthropic.stub-haiku-v1")
    monkeypatch.setenv("AGENTCORE_SESSION_SIGNING_KEY", "a" * 64)
    monkeypatch.setenv("AWS_REGION_BEDROCK", "us-east-1")
    monkeypatch.setenv("MULESOFT_MODE", "mock")
    # Tests run without a real Bedrock Guardrails configuration. Explicit
    # dev-mode opt-in keeps the production fail-closed behavior intact while
    # letting the test suite exercise coordinator boot.
    monkeypatch.setenv("OPENCLAW_DEV", "true")
