"""Task 2 AC12.1 -- M8 imports only from m3, m5, m9.models."""

import ast
import pathlib
import pytest

_FORBIDDEN_MODULE_PREFIXES = (
    "m1_",
    "m2_",
    "m4_",
    "m6_",
    "m7_",
    "m10_",
    "m11_",
    "m12_",
    "m13_",
)

_FORBIDDEN_COMPLIANCE = ("compliance.",)

_ROOT = pathlib.Path("my-agent-project-007-fsi-interoperability/src/m8_pipeline_engine")


def _iter_modules():
    for p in sorted(_ROOT.rglob("*.py")):
        yield p


@pytest.mark.parametrize("path", list(_iter_modules()), ids=lambda p: p.name)
def test_no_forbidden_cross_module_imports(path: pathlib.Path):
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    for node in ast.walk(tree):
        mod = None
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                for prefix in _FORBIDDEN_MODULE_PREFIXES:
                    assert not mod.startswith(prefix), (
                        f"{path}: forbidden import {mod!r}"
                    )
                for prefix in _FORBIDDEN_COMPLIANCE:
                    assert not mod.startswith(prefix), (
                        f"{path}: forbidden compliance import {mod!r}"
                    )
            continue
        if mod:
            for prefix in _FORBIDDEN_MODULE_PREFIXES:
                assert not mod.startswith(prefix), (
                    f"{path}: forbidden ImportFrom {mod!r}"
                )
            for prefix in _FORBIDDEN_COMPLIANCE:
                assert not mod.startswith(prefix), (
                    f"{path}: forbidden compliance ImportFrom {mod!r}"
                )
