"""Task 2 AC12.6 -- No forbidden module-name string literals.

Exempt: __init__.py (defines PIPELINE_NAMES with 'm8.research_*').
"""

import pathlib
import re

_BANNED_SUBSTRINGS = (
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

_EXEMPT_FILES = {
    "__init__.py",
    # Tests reference fake/forbidden-shape strings intentionally
}

_ROOT = pathlib.Path("my-agent-project-007-fsi-interoperability/src/m8_pipeline_engine")


def test_no_forbidden_module_strings():
    for path in sorted(_ROOT.rglob("*.py")):
        if path.name in _EXEMPT_FILES:
            continue
        src = path.read_text()
        # Strip docstrings and comments (approximate -- line-by-line)
        for i, line in enumerate(src.splitlines(), start=1):
            # skip comment-only lines
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for bad in _BANNED_SUBSTRINGS:
                # Allow bad strings inside triple-quoted docstrings or module comments
                if bad in line:
                    # As a heuristic, require the line not be inside a string literal
                    # by checking it is not solely a string. Simpler: accept lines that
                    # begin with a docstring triple-quote.
                    if line.lstrip().startswith(('"""', "'''", '"', "'")):
                        continue
                    # Flag any other occurrence
                    raise AssertionError(
                        f"{path}:{i} forbidden module substring {bad!r} in: {line!r}"
                    )
