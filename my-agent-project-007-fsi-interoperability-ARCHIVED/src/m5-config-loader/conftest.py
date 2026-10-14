"""Pytest configuration — handle M5 package imports for testing."""

import sys
import types
from pathlib import Path

# Add this directory to sys.path so `loader` and `models` are importable directly
pkg_dir = Path(__file__).resolve().parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

# Create a fake package module so __init__.py relative imports work
pkg = types.ModuleType("m5_config_loader")
pkg.__path__ = [str(pkg_dir)]
pkg.__file__ = str(pkg_dir / "__init__.py")
pkg.__package__ = "m5_config_loader"
sys.modules["m5_config_loader"] = pkg

# Now import the actual modules
from loader import *  # noqa: F401, F403, E402
from models import *  # noqa: F401, F403, E402

# Register submodules
import loader as _loader  # noqa: E402
import models as _models  # noqa: E402
sys.modules["m5_config_loader.loader"] = _loader
sys.modules["m5_config_loader.models"] = _models

# Populate the package module
for attr in dir(_loader):
    if not attr.startswith("_"):
        setattr(pkg, attr, getattr(_loader, attr))
for attr in dir(_models):
    if not attr.startswith("_"):
        setattr(pkg, attr, getattr(_models, attr))
