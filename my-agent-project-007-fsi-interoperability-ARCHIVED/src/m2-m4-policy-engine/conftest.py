"""
Pytest conftest for M2/M4 policy engine.

Registers the hyphenated directory as an importable Python package
before pytest tries to collect tests.
"""

import importlib.util
import sys
from pathlib import Path

_module_dir = Path(__file__).parent

# Register the package under an underscore name
_pkg = "m2_m4_policy_engine"

if _pkg not in sys.modules:
    # Register the package itself
    spec = importlib.util.spec_from_file_location(
        _pkg,
        _module_dir / "__init__.py",
        submodule_search_locations=[str(_module_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_pkg] = mod

    # Register submodules BEFORE executing __init__ (which uses relative imports)
    for sub_name in ("models", "policy_client", "app"):
        sub_full = f"{_pkg}.{sub_name}"
        sub_spec = importlib.util.spec_from_file_location(
            sub_full,
            _module_dir / f"{sub_name}.py",
        )
        sub_mod = importlib.util.module_from_spec(sub_spec)
        sub_mod.__package__ = _pkg
        sys.modules[sub_full] = sub_mod
        sub_spec.loader.exec_module(sub_mod)

    # Now execute __init__ (relative imports will resolve via sys.modules)
    spec.loader.exec_module(mod)
