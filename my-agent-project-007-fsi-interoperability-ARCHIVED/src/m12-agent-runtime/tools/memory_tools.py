"""
M12 Memory Tool Wrappers — @tool functions for memory retrieval.

Memory tiers: L2/L3 (recent interactions), L4 (semantic), L5 (procedural).
All memory access goes through M6 gateway (Rule 4).
MNPI filtered by M4 before data reaches the LLM (Rule 7).

No cross-module imports (Rule 9) — HTTP to M6 only.
No credentials in code (Rule 20).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from strands import tool

from .m6_tools import current_aid_token

logger = logging.getLogger("m12.tools.memory")

_M6_URL = os.environ.get("M6_GATEWAY_URL", "http://localhost:8000")
_MEMORY_SERVER = os.environ.get(
    "M8_MEMORY_URL", "http://m8-memory:8000"
)
_HTTP_TIMEOUT = float(os.environ.get("M12_TOOL_TIMEOUT", "30.0"))


def _call_m6_memory(tool_name: str, arguments: dict[str, Any]) -> str:
    """Call memory service via M6 gateway. MNPI filtered by M4."""
    aid_token = current_aid_token.get()
    if not aid_token:
        aid_token = "dev-token"

    payload = {
        "aid_token": aid_token,
        "server_url": _MEMORY_SERVER,
        "tool_name": tool_name,
        "arguments": arguments,
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(f"{_M6_URL}/mcp/call", json=payload)

        if resp.status_code == 403:
            return "Access denied"
        if resp.status_code >= 400:
            return "Memory service temporarily unavailable"

        data = resp.json()
        result = data.get("result", data)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result)

    except httpx.HTTPError as exc:
        logger.error("Memory call failed: %s", exc)
        return "Memory service temporarily unavailable"


@tool
def get_recent_interactions(client_id: str) -> str:
    """Get recent interaction history for a client (L2/L3 memory).
    Returns recent meetings, calls, emails, and notes.
    Use to understand recent context before client conversations.
    Data is MNPI-filtered by the trust layer."""
    return _call_m6_memory("get_recent_interactions", {
        "client_id": client_id,
    })


@tool
def get_client_preferences(client_id: str) -> str:
    """Get client preferences and procedures (L5 procedural memory).
    Returns communication preferences, investment preferences,
    reporting preferences, and special instructions.
    Data is MNPI-filtered by the trust layer."""
    return _call_m6_memory("get_client_preferences", {
        "client_id": client_id,
    })


@tool
def get_client_facts(client_id: str) -> str:
    """Get stored facts about a client (L4 semantic memory).
    Returns key facts, life events, family info, and goals.
    Use to personalize client interactions.
    Data is MNPI-filtered by the trust layer."""
    return _call_m6_memory("get_client_facts", {
        "client_id": client_id,
    })
