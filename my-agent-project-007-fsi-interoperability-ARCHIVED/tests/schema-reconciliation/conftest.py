"""
Schema Reconciliation Tests — Shared Fixtures

Sets up sys.path so M7 translators are importable.
NOTE: Do NOT add m3-schema-registry to sys.path — its types.py shadows
Python's built-in types module. M7 uses importlib in _m3_imports.py instead.
"""

import os
import sys

# Add only the src/ directory so m7_schema_translators is importable as a package
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src = os.path.join(_project_root, "src")

if _src not in sys.path:
    sys.path.insert(0, _src)
