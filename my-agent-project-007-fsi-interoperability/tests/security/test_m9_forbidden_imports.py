"""
M9 Task 2 -- Forbidden imports AST scan.

AC13.1-13.7.
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


BANNED = frozenset({
    "logging",
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "langchain",
    "langgraph",
    "anthropic",
    "openai",
    "warnings",
    "tempfile",
    "socket",
    "subprocess",
    "aiohttp",
    "grpc",
})


def test_ac13_1_no_banned_imports():
    violations = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".", 1)[0]
                    if top in BANNED:
                        violations.append((py.name, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".", 1)[0]
                if top in BANNED:
                    violations.append((py.name, node.module))
    assert not violations, f"forbidden imports: {violations}"


def test_ac13_3_boto3_only_in_llm_and_hmac():
    """boto3 is allowed ONLY in llm_client.py and hmac_util.py."""
    for py in _walk_py_files():
        if py.name in ("llm_client.py", "hmac_util.py"):
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("boto3"), (
                        f"boto3 import in {py.name} -- forbidden outside "
                        "llm_client/hmac_util"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("boto3"), (
                    f"boto3 import in {py.name}"
                )


def test_ac13_5_print_only_in_route():
    """AC13.5 -- print( appears only in route.py (inside _emit_audit)."""
    import re as _re

    locations = []
    pat = _re.compile(r"^\s*print\(")
    for py in _walk_py_files():
        for lineno, line in enumerate(py.read_text().splitlines(), start=1):
            stripped = line.split("#", 1)[0]  # strip trailing comment
            if pat.search(stripped):
                locations.append((py.name, lineno))
    assert locations, "no print() found; expected exactly 1 in route.py"
    assert all(loc[0] == "route.py" for loc in locations), (
        f"print() allowed only in route.py: {locations}"
    )
    assert len(locations) == 1, (
        f"expected exactly 1 print() call, got {len(locations)}: {locations}"
    )
