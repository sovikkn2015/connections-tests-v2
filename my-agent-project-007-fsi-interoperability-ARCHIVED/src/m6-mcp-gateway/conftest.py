"""
Pytest conftest for M6 MCP Gateway.

Adds the m6-mcp-gateway directory to sys.path so that relative
imports work despite the directory name containing dashes.
"""

import importlib
import sys
from pathlib import Path

# Add the m6-mcp-gateway directory as a package
_pkg_dir = Path(__file__).parent
_src_dir = _pkg_dir.parent

# Register the package under a Python-valid name
_pkg_name = "m6_mcp_gateway"
if _pkg_name not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        _pkg_name,
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_pkg_name] = mod
    spec.loader.exec_module(mod)
