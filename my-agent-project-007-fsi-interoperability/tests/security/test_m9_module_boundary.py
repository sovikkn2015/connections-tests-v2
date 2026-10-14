"""
M9 Task 2 -- Module boundary AST scan.

AC12.1-12.8: no cross-module imports from m2/m3/m4/m6/m7/m8/m10/m11/m12/m13
/compliance.*.
"""

from __future__ import annotations

import ast
import pathlib

SRC_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m9_intent_router"
)


def _walk_py_files() -> list[pathlib.Path]:
    return sorted(
        p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in str(p)
    )


def test_src_dir_exists():
    assert SRC_ROOT.is_dir()
    assert len(_walk_py_files()) > 0


FORBIDDEN_MODULE_PREFIXES = (
    "m2_",
    "m3_",
    "m4_",
    "m6_",
    "m7_",
    "m8_",
    "m10_",
    "m11_",
    "m12_",
    "m13_",
    "compliance.",
)


def test_ac12_1_no_cross_module_imports():
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in FORBIDDEN_MODULE_PREFIXES:
                    if node.module.startswith(prefix):
                        violations.append((py.name, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in FORBIDDEN_MODULE_PREFIXES:
                        if alias.name.startswith(prefix):
                            violations.append((py.name, alias.name))
    assert not violations, f"forbidden cross-module imports: {violations}"


def test_ac12_2_positive_allowlist_m1_and_m5_only():
    """Only m1_identity and m5_config_loader are allowed intra-project."""
    ALLOWED = ("m1_identity", "m5_config_loader", "m9_intent_router")
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("m") and node.module[1:2].isdigit():
                    top = node.module.split(".", 1)[0]
                    if top not in ALLOWED:
                        violations.append((py.name, node.module))
    assert not violations, f"disallowed intra-project imports: {violations}"


def test_ac12_8_never_imports_m3_schema_registry():
    """v0.2.0 Fix 1: M9 never imports M3."""
    for py in _walk_py_files():
        content = py.read_text()
        assert "m3_schema_registry" not in content, (
            f"{py.name} contains forbidden m3_schema_registry reference"
        )


def test_m9_never_imports_m6_m8():
    """R17 / R18 -- M9 never calls M6 or M8."""
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("m6_"), (
                    f"M9 imports M6 in {py.name}"
                )
                assert not node.module.startswith("m8_"), (
                    f"M9 imports M8 in {py.name}"
                )
