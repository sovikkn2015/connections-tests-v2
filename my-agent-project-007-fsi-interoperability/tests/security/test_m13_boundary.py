"""Module-boundary + credential-shape tests for M13 FIX Bridge.

Steering Rule 33 — ``m13_fix_bridge`` MUST NOT import from any other
project module (M1/M2/M4/M5/M6/M7/M8/M9/M10/M11/M12). Explicitly
includes the ``m11_python_adapters_shared`` package — M13 is a
separate adapter family (Rule 11 / D9 in the M13 spec) and copies its
own infra rather than importing from the M11 family.

Steering Rule 20 — no literal credentials in source.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
M13_DIR = ROOT / "src" / "m13_fix_bridge"


# Modules that the boundary forbids.
FORBIDDEN_MODULES = (
    "m1_identity",
    "m2_m4_policy_engine",
    "m5_config_loader",
    "m6_mcp_gateway",
    "m7_schema_translators",
    "m8_pipeline_engine",
    "m9_intent_router",
    "m10_audit_logger",
    "m11_rest_adapters",
    "m11_blpapi_adapters",
    "m11_grpc_adapters",
    "m11_python_adapters_shared",
    "m12_supervisor",
    "compliance",
)

_IMPORT_RX = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import\s+|import\s+([\w\.]+))",
    re.MULTILINE,
)


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_m13_source_exists() -> None:
    assert M13_DIR.is_dir(), f"M13 source dir missing: {M13_DIR}"
    # Guard against accidental empty package.
    assert list(_py_files(M13_DIR)), "no .py files under m13_fix_bridge/"


def test_no_forbidden_module_imports() -> None:
    """Spec §R11 — AST scan for forbidden imports."""
    violations: list[str] = []
    for f in _py_files(M13_DIR):
        src = f.read_text(encoding="utf-8")
        for m in _IMPORT_RX.finditer(src):
            mod = (m.group(1) or m.group(2) or "").split(".")[0]
            if mod in FORBIDDEN_MODULES:
                violations.append(
                    f"{f.relative_to(ROOT)} imports forbidden module {mod!r}"
                )
    assert not violations, "\n".join(violations)


def test_no_hardcoded_credentials() -> None:
    """Spec §R9.1 — no literal credentials in M13 source.

    The boundary-scan fixtures in ``tests/security/test_m11_*`` use the
    same set of patterns (AKIA.../sk_live_/PEM/Bearer+token). M13
    source must NOT contain any of these — all credentials must be
    Vault paths, which are plain strings and won't match these regexes.
    """
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk_live_[A-Za-z0-9]{10,}"),
        re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY"),
        re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{32,}"),
        re.compile(r"password\s*=\s*[\"'][A-Za-z0-9!@#$%^&*]{8,}[\"']"),
    ]
    violations: list[str] = []
    for f in _py_files(M13_DIR):
        src = f.read_text(encoding="utf-8")
        for p in patterns:
            m = p.search(src)
            if m:
                violations.append(
                    f"{f.relative_to(ROOT)} contains credential-like literal "
                    f"{m.group(0)!r}"
                )
    assert not violations, "\n".join(violations)


def test_no_direct_m10_import() -> None:
    """Rule 33 — drop-copy MUST go via stdout, NOT via M10 import."""
    for f in _py_files(M13_DIR):
        src = f.read_text(encoding="utf-8")
        assert "from m10_audit_logger" not in src, f"{f} imports M10"
        assert "import m10_audit_logger" not in src, f"{f} imports M10"
