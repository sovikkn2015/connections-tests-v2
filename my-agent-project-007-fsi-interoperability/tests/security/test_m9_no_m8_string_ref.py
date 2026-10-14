"""
M9 Task 2 -- string-level "m8_" reference scan.

AC12.6 Fix 14: taxonomy.py is exempt (it must contain "m8.research_pipeline_1"
literal strings by design).
"""

from __future__ import annotations

import pathlib

SRC_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m9_intent_router"
)

EXEMPT_FILES = {"taxonomy.py"}


def test_no_m8_string_refs_outside_taxonomy():
    """AC12.6 Fix 14: literal "m8_" must not appear outside taxonomy.py."""
    for py in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        if py.name in EXEMPT_FILES:
            continue
        content = py.read_text()
        assert "m8_" not in content, (
            f"{py.name} contains 'm8_' reference -- forbidden"
        )
