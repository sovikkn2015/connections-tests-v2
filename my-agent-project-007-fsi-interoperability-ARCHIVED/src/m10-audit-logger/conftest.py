"""Pytest configuration — add src/m10-audit-logger to sys.path as m10_audit_logger."""

import sys
from pathlib import Path

# Allow imports like `from m10_audit_logger.models import ...`
pkg_dir = Path(__file__).resolve().parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))
