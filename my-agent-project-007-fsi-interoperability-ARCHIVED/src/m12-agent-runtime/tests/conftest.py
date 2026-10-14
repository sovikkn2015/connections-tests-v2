"""
M12 test configuration.

Makes the m12-agent-runtime package importable as 'm12_rt' for tests.
Uses sys.modules aliasing so relative imports within the package work.
"""

import importlib
import sys
from pathlib import Path

# Add parent of m12-agent-runtime to path
_pkg_dir = Path(__file__).resolve().parent.parent
_parent_dir = _pkg_dir.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))
if str(_pkg_dir) not in sys.path:
    sys.path.insert(0, str(_pkg_dir))

# Register the package directory as 'm12_rt' in sys.modules
# so 'from m12_rt.tools.m6_tools import ...' works in tests
import types

_pkg = types.ModuleType("m12_rt")
_pkg.__path__ = [str(_pkg_dir)]
_pkg.__package__ = "m12_rt"
sys.modules["m12_rt"] = _pkg

# Register sub-packages
for sub in ["tools", "agents", "tests"]:
    sub_path = _pkg_dir / sub
    if sub_path.is_dir():
        mod = types.ModuleType(f"m12_rt.{sub}")
        mod.__path__ = [str(sub_path)]
        mod.__package__ = f"m12_rt.{sub}"
        sys.modules[f"m12_rt.{sub}"] = mod
