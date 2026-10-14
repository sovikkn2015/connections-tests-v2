"""Module-boundary + credential tests for the M11 Python adapters.

Steering Rule 33 — no cross-module imports. Adapters may only import:
* Python stdlib
* pydantic (+ typing_extensions)
* m3_schema_registry (canonical types — Rule 12 translator staging)
* m11_python_adapters_shared (the shared infra module in the same family)
* vendor SDK (``blpapi`` / ``grpc`` — only lazily inside real-client files)

Anything else (M6 gateway, M10 audit logger, M1 identity, etc.) is forbidden.

Steering Rule 20 — zero credentials. Source files MUST NOT contain literal
secrets (bearer tokens, private keys, API-key strings, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_DIRS = (
    ROOT / "src" / "m11_python_adapters_shared",
    ROOT / "src" / "m11_blpapi_adapters",
    ROOT / "src" / "m11_grpc_adapters",
)

# Modules our adapters are forbidden to import (cross-module boundary).
FORBIDDEN_MODULES = (
    "m6_mcp_gateway",
    "m10_audit_logger",
    "m1_identity",
    "m2_m4_policy_engine",
    "m5_config_loader",
    "m7_schema_translators",
    "m8_pipeline_engine",
    "m9_intent_router",
    "m12_supervisor",
)

# Allowed imports beyond stdlib + own-family. `m3_schema_registry` is the only
# sibling project module that adapters may consume (Steering Rule 12).
ALLOWED_NON_STDLIB_PREFIXES = (
    "m3_schema_registry",
    "m11_python_adapters_shared",
    "m11_blpapi_adapters",
    "m11_grpc_adapters",
    "pydantic",
    "typing_extensions",
    "fastapi",
    "starlette",
    "uvicorn",
    "structlog",
    "grpc",  # real-client lazy import only
    "blpapi",  # real-client lazy import only
)

_IMPORT_RX = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import\s+|import\s+([\w\.]+))",
    re.MULTILINE,
)


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize(
    "adapter_dir",
    [pytest.param(d, id=d.name) for d in ADAPTER_DIRS],
)
def test_no_forbidden_module_imports(adapter_dir: Path) -> None:
    """Assert adapter source never imports from M6/M10/etc."""
    for f in _py_files(adapter_dir):
        src = f.read_text(encoding="utf-8")
        for m in _IMPORT_RX.finditer(src):
            mod = (m.group(1) or m.group(2) or "").split(".")[0]
            assert mod not in FORBIDDEN_MODULES, (
                f"{f.relative_to(ROOT)} imports forbidden module {mod!r}"
            )


@pytest.mark.parametrize(
    "adapter_dir",
    [pytest.param(d, id=d.name) for d in ADAPTER_DIRS],
)
def test_no_hardcoded_credentials(adapter_dir: Path) -> None:
    """Assert no literal credentials appear in adapter source.

    Checks for standard credential-leak patterns:
    * AWS access key IDs (``AKIA[0-9A-Z]{16}``)
    * Stripe-style live secrets (``sk_live_``)
    * PEM private keys (``-----BEGIN (RSA|EC|) PRIVATE KEY``)
    * Bearer-prefixed tokens (``Bearer <long_string>``)
    """
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk_live_[A-Za-z0-9]{10,}"),
        re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY"),
        re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{32,}"),
    ]
    for f in _py_files(adapter_dir):
        src = f.read_text(encoding="utf-8")
        for p in patterns:
            m = p.search(src)
            assert m is None, (
                f"{f.relative_to(ROOT)} contains credential-like literal "
                f"{m.group(0)!r}"
            )


def test_python_adapters_audit_events_via_stdout() -> None:
    """Adapters must emit audit events to stdout, not to M10 via import."""
    for adapter_dir in ADAPTER_DIRS:
        for f in _py_files(adapter_dir):
            src = f.read_text(encoding="utf-8")
            # No direct import of M10 audit logger module.
            assert "from m10_audit_logger" not in src
            assert "import m10_audit_logger" not in src
