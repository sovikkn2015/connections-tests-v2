"""
Test M7 module boundary — Task 2 negative tests.

AC12.1 / AC12.2 / AC12.4 — no cross-module imports, no forbidden runtime deps,
positive M5 allow-list.
AC14.3 / AC14.4 — no logging, no warnings, no tempfile, etc.
AC10.1 / AC10.2 / AC10.3 — no uuid.uuid4, datetime.utcnow/now, time.time, random.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

SRC_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "m7_schema_translators"


def _walk_py_files() -> list[pathlib.Path]:
    return sorted(
        p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in str(p)
    )


def test_src_dir_exists():
    assert SRC_ROOT.is_dir()
    assert len(_walk_py_files()) > 0


FORBIDDEN_MODULE_PREFIXES = (
    "m1_",
    "m2_",
    "m4_",
    "m6_",
    "m8_",
    "m9_",
    "m10_",
    "m11_",
    "m12_",
    "m13_",
    "compliance.gap2",
    "compliance.gap6",
)


def test_no_cross_module_imports():
    """AC12.1 — forbidden module prefix imports."""
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in FORBIDDEN_MODULE_PREFIXES:
                    if node.module.startswith(prefix):
                        violations.append((str(py), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in FORBIDDEN_MODULE_PREFIXES:
                        if alias.name.startswith(prefix):
                            violations.append((str(py), alias.name))
    assert not violations, f"forbidden imports: {violations}"


FORBIDDEN_RUNTIME_DEPS = (
    "httpx",
    "requests",
    "boto3",
    "fastapi",
    "redis",
    "langchain",
    "langgraph",
    "openai",
    "anthropic",
    "simple_salesforce",
    "orion_sdk",
    "schwab_sdk",
    "emoney_sdk",
)


def test_no_vendor_sdks_or_http_libs():
    """AC12.2 — forbidden runtime deps."""
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for dep in FORBIDDEN_RUNTIME_DEPS:
                    if node.module == dep or node.module.startswith(dep + "."):
                        violations.append((str(py), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for dep in FORBIDDEN_RUNTIME_DEPS:
                        if (
                            alias.name == dep
                            or alias.name.startswith(dep + ".")
                        ):
                            violations.append((str(py), alias.name))
    assert not violations, f"forbidden dep imports: {violations}"


FORBIDDEN_SIDE_EFFECTS = (
    "logging",
    "warnings",
    "tempfile",
    "socket",
    "urllib",
    "subprocess",
)


def test_no_forbidden_side_effect_imports():
    """AC14.3 / AC14.4 — forbidden side-effect imports."""
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for dep in FORBIDDEN_SIDE_EFFECTS:
                    if node.module == dep or node.module.startswith(dep + "."):
                        violations.append((str(py), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for dep in FORBIDDEN_SIDE_EFFECTS:
                        if (
                            alias.name == dep
                            or alias.name.startswith(dep + ".")
                        ):
                            violations.append((str(py), alias.name))
    assert not violations, f"forbidden side-effect imports: {violations}"


_FORBIDDEN_ATTR_CALLS = frozenset(
    {
        ("uuid", "uuid4"),
        ("datetime", "utcnow"),
        ("datetime", "now"),
        ("time", "time"),
    }
)


def test_no_uuid_uuid4_or_nondeterministic_clock():
    """AC10.1 / AC10.2 / AC10.3 — no uuid4, no datetime.utcnow/now, no time.time,
    no random.*. Uses AST to avoid false positives from docstrings/comments."""
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(
                node.func, ast.Attribute
            ):
                owner = node.func.value
                attr = node.func.attr
                if isinstance(owner, ast.Name):
                    if (owner.id, attr) in _FORBIDDEN_ATTR_CALLS:
                        violations.append((str(py), f"{owner.id}.{attr}()"))
                    if owner.id == "random":
                        violations.append((str(py), f"random.{attr}()"))
    assert not violations, f"forbidden runtime calls: {violations}"


def test_m5_import_allowlist():
    """AC12.4 — positive AST-enforced allow-list on M5 imports."""
    allowed = frozenset({"Archetype", "Jurisdiction", "RegistrationType"})
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "m5_config_loader" or node.module.startswith(
                    "m5_config_loader."
                ):
                    imported = {alias.name for alias in node.names}
                    bad = imported - allowed
                    if bad:
                        violations.append((str(py), bad))
    assert not violations, f"non-allowed M5 imports: {violations}"


def test_no_credentials_literal_assignments():
    """AC14.1 — no credential-shaped literal assignments in source."""
    cred_patterns = [
        re.compile(r'api_key\s*=\s*["\'][^"\']+["\']'),
        re.compile(r'password\s*=\s*["\'][^"\']+["\']'),
        re.compile(r'secret\s*=\s*["\'][^"\']+["\']'),
        re.compile(r'bearer\s*=\s*["\'][^"\']+["\']'),
        re.compile(r'oauth\s*=\s*["\'][^"\']+["\']'),
    ]
    violations = []
    for py in _walk_py_files():
        text = py.read_text()
        for pat in cred_patterns:
            for match in pat.finditer(text):
                violations.append((str(py), match.group(0)))
    assert not violations, f"credential-shaped literals: {violations}"
