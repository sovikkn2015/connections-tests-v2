"""
M12 Agent Factory — Creates agents with correct config per archetype.

Reads RuntimeConfig to determine version:
  v1 = M9 regex intent router (fast path, <1ms)
  v2 = Strands supervisor agent (LLM reasoning, ~500ms)

Both versions coexist per ARCH-10 Decision 1.
Runtime selection is a Helm values toggle, not a code change.

No cross-module imports (Rule 9). M9 called via REST if v1.
No credentials in code (Rule 20).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Protocol

from .config import AGENT_VERSION

logger = logging.getLogger("m12.agent_factory")


class AgentProtocol(Protocol):
    """Protocol for agent interface — both v1 and v2 implement."""

    def __call__(self, message: str) -> Any: ...


class V1Router:
    """
    v1 fallback: calls M9 regex intent router via REST.
    No cross-module import — HTTP call to M9 service.
    """

    def __init__(self) -> None:
        import httpx
        self._m9_url = os.environ.get(
            "M9_INTENT_ROUTER_URL", "http://m9-intent-router:8000"
        )
        self._timeout = 10.0

    def __call__(self, message: str) -> str:
        import httpx
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._m9_url}/classify",
                    json={"user_input": message},
                )
                if resp.status_code == 200:
                    return str(resp.json())
                return f"M9 router error: {resp.status_code}"
        except Exception as exc:
            logger.error("V1 router failed: %s", exc)
            return "Intent router temporarily unavailable"


def create_agent(version: Optional[str] = None) -> Any:
    """
    Create an agent based on version config.

    Args:
        version: "v1" for M9 regex router, "v2" for Strands supervisor.
                 Defaults to AGENT_VERSION env var.

    Returns:
        v1: V1Router (calls M9 via REST)
        v2: Strands supervisor Agent
    """
    ver = version or AGENT_VERSION

    if ver == "v1":
        logger.info("Creating v1 agent (M9 regex intent router)")
        return V1Router()

    # v2: Strands supervisor agent
    logger.info("Creating v2 agent (Strands supervisor)")
    from .agents.supervisor import create_supervisor_agent
    return create_supervisor_agent()
