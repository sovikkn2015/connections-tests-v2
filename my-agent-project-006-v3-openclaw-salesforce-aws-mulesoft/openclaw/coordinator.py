"""Top-level ``python -m openclaw.coordinator`` entrypoint for Dockerfile CMD.

Thin shim over openclaw.orchestration.coordinator.main() so the image command
is stable across refactors of the internal module layout. In production,
AgentCore attaches its WebSocket server in front of the PersonaCoordinator.
"""

from __future__ import annotations


def main() -> None:
    """Delegate to the orchestration module's entrypoint."""
    from .orchestration.coordinator import main as _main

    _main()


if __name__ == "__main__":  # pragma: no cover
    main()
