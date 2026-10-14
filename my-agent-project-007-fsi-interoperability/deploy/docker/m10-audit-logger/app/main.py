"""M10 uvicorn entrypoint (B12 fail-closed on unwired backends).

Dockerfile ENTRYPOINT calls::

    uvicorn --factory deploy.docker.m10-audit-logger.app.main:create_app

or (when PYTHONPATH includes the deploy dir) simply::

    uvicorn --factory app.main:create_app

This bootstrap:
1. Reads ``M10_ALLOW_IN_MEMORY_AUDIT`` from env (off-by-default).
2. Emits a single structured stdout line naming the posture.
3. Calls ``m10_audit_logger.app.create_app(allow_in_memory_audit=<flag>)``.

The M10 source tree itself contains NO ``os.environ`` reads -- that is
an enforced security invariant (see
``tests/unit/test_m10_audit_logger.py::TestSecurity::test_no_os_environ_in_src``).
All runtime config flows through the ``create_app`` keyword arg.

Zero credentials. This file reads only a boolean feature flag.
"""

from __future__ import annotations

import json
import os
import sys

from m10_audit_logger.app import create_app as _create_app


def _read_allow_in_memory_audit() -> bool:
    raw = os.environ.get("M10_ALLOW_IN_MEMORY_AUDIT", "false")
    return str(raw).strip().lower() == "true"


def _emit_bootstrap_line(allow: bool) -> None:
    sys.stdout.write(json.dumps({
        "phase": "bootstrap",
        "module": "m10",
        "allow_in_memory_audit": allow,
    }, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def create_app():
    """uvicorn `--factory` entrypoint."""
    allow = _read_allow_in_memory_audit()
    _emit_bootstrap_line(allow)
    return _create_app(allow_in_memory_audit=allow)
