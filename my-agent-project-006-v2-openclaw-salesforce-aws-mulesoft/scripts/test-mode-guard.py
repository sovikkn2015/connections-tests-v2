#!/usr/bin/env python3
"""Unit test for the Tier-4 #15 production-mode guard.

Asserts that the mulesoft-actions Lambda refuses to import when:
  (a) MULESOFT_MODE=production AND VENDOR_ALPACA_SECRET_NAME points at the
      paper secret /006-v2/vendors/alpaca.
  (b) MULESOFT_MODE=production AND the secret's endpoint field contains
      paper-api.alpaca.markets (even if the secret NAME ends in -LIVE).
  (c) MULESOFT_MODE=mock or sandbox booting without error.

Runs with plain `python3 scripts/test-mode-guard.py` (no pytest dep). Uses a
lightweight boto3 monkeypatch so it does not need AWS creds.

Exit code: 0 on all assertions PASS, 1 on any failure.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MULESOFT_LAMBDA_DIR = REPO_ROOT / "aws" / "mcp-servers" / "mulesoft-actions"


def _install_fake_boto3(secret_payload: dict[str, Any]) -> None:
    """Install a boto3 shim that returns secret_payload from get_secret_value."""

    class _FakeSecretsClient:
        def get_secret_value(self, SecretId: str) -> dict[str, Any]:  # noqa: N803 - boto3 signature
            return {"SecretString": json.dumps(secret_payload), "Name": SecretId}

    class _FakeBoto3(ModuleType):
        def __init__(self) -> None:
            super().__init__("boto3")

        def client(self, service_name: str, **_kwargs: Any) -> _FakeSecretsClient:
            if service_name != "secretsmanager":
                raise RuntimeError(
                    f"fake boto3 only supports secretsmanager, got {service_name}"
                )
            return _FakeSecretsClient()

    sys.modules["boto3"] = _FakeBoto3()


def _load_app_fresh() -> ModuleType:
    """Force a fresh import of app.py so the guard re-runs under the new env."""
    if str(MULESOFT_LAMBDA_DIR) not in sys.path:
        sys.path.insert(0, str(MULESOFT_LAMBDA_DIR))
    for modname in ("app", "mulesoft_client", "mcp_protocol"):
        sys.modules.pop(modname, None)
    return importlib.import_module("app")


def _assert_raises(
    label: str,
    env: dict[str, str],
    secret_payload: dict[str, Any],
    expected_substr: str,
) -> bool:
    for key in ("MULESOFT_MODE", "VENDOR_ALPACA_SECRET_NAME"):
        os.environ.pop(key, None)
    os.environ.update(env)
    _install_fake_boto3(secret_payload)
    try:
        _load_app_fresh()
    except Exception as exc:  # noqa: BLE001 - catch any guard failure
        msg = str(exc)
        if expected_substr in msg:
            print(f"  PASS  {label}")
            return True
        print(f"  FAIL  {label}  (wrong error: '{msg}')")
        return False
    print(f"  FAIL  {label}  (expected exception containing '{expected_substr}', got none)")
    return False


def _assert_boots(label: str, env: dict[str, str]) -> bool:
    for key in ("MULESOFT_MODE", "VENDOR_ALPACA_SECRET_NAME"):
        os.environ.pop(key, None)
    os.environ.update(env)
    _install_fake_boto3({"endpoint": "https://api.alpaca.markets"})
    try:
        app = _load_app_fresh()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  {label}  (unexpected exception: {exc})")
        return False
    if getattr(app, "MODE", None) not in {"mock", "sandbox"}:
        print(f"  FAIL  {label}  (MODE resolved to {app.MODE!r})")
        return False
    print(f"  PASS  {label}  (booted in {app.MODE!r} mode)")
    return True


def main() -> int:
    print("Production-mode guard tests")
    print("-" * 60)

    results: list[bool] = []

    results.append(_assert_raises(
        "production + /006-v2/vendors/alpaca (paper name) refuses boot",
        env={
            "MULESOFT_MODE": "production",
            "VENDOR_ALPACA_SECRET_NAME": "/006-v2/vendors/alpaca",
        },
        secret_payload={"endpoint": "https://api.alpaca.markets"},
        expected_substr="paper credentials must never fuel",
    ))

    results.append(_assert_raises(
        "production + alpaca-LIVE but endpoint=paper-api.alpaca.markets refuses boot",
        env={
            "MULESOFT_MODE": "production",
            "VENDOR_ALPACA_SECRET_NAME": "/006-v2/vendors/alpaca-LIVE",
        },
        secret_payload={"endpoint": "https://paper-api.alpaca.markets"},
        expected_substr="paper-api.alpaca.markets",
    ))

    results.append(_assert_boots(
        "mock mode boots with default secret path",
        env={"MULESOFT_MODE": "mock"},
    ))

    results.append(_assert_boots(
        "sandbox mode boots with paper secret",
        env={
            "MULESOFT_MODE": "sandbox",
            "VENDOR_ALPACA_SECRET_NAME": "/006-v2/vendors/alpaca",
        },
    ))

    print("-" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
