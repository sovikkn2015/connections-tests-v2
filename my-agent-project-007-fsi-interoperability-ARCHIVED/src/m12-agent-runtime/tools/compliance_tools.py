"""
M12 Compliance Tool Wrappers — @tool functions for OPA policy checks.

All compliance decisions are deterministic OPA/Rego via M2 (Rule 5).
Compliance is NEVER done by LLM (Rule 14).
All calls go through M6 gateway (Rule 4).

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

logger = logging.getLogger("m12.tools.compliance")

_M6_URL = os.environ.get("M6_GATEWAY_URL", "http://localhost:8000")
_M2_SERVER = os.environ.get("M2_POLICY_URL", "http://m2-m4-policy:8000")
_HTTP_TIMEOUT = float(os.environ.get("M12_TOOL_TIMEOUT", "30.0"))


def _call_m6_compliance(tool_name: str, arguments: dict[str, Any]) -> str:
    """Call M2 OPA policy engine via M6 gateway. Deterministic, not LLM."""
    aid_token = current_aid_token.get()
    if not aid_token:
        aid_token = "dev-token"

    payload = {
        "aid_token": aid_token,
        "server_url": _M2_SERVER,
        "tool_name": tool_name,
        "arguments": arguments,
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(f"{_M6_URL}/mcp/call", json=payload)

        if resp.status_code == 403:
            return "DENY: Access denied"

        if resp.status_code >= 400:
            # Fail-closed on compliance check failure (Rule 8)
            return "DENY: Compliance service unavailable — fail-closed"

        data = resp.json()
        result = data.get("result", data)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result)

    except httpx.HTTPError as exc:
        logger.error("Compliance check failed: %s", exc)
        # Fail-closed (Rule 8)
        return "DENY: Compliance service unavailable — fail-closed"


@tool
def check_compliance(action: str, target: str, context: str) -> str:
    """Check if an action is compliant using OPA/Rego policy engine.
    This is a DETERMINISTIC check — not an LLM opinion.
    Returns ALLOW, DENY, or ESCALATE with reason.
    action: what you want to do (e.g. 'trade', 'view_holdings')
    target: what it applies to (e.g. client_id, ticker)
    context: additional context as JSON string"""
    return _call_m6_compliance("check_compliance", {
        "action": action,
        "target": target,
        "context": context,
    })


@tool
def check_restricted_list(ticker: str) -> str:
    """Check if a security is on the restricted trading list.
    Deterministic OPA check — not an LLM decision.
    Returns CLEAR or RESTRICTED with reason."""
    return _call_m6_compliance("check_restricted_list", {
        "ticker": ticker,
    })


@tool
def check_concentration(
    client_id: str, ticker: str, proposed_pct: float
) -> str:
    """Check if a proposed position would exceed concentration limits.
    Deterministic OPA check — not an LLM decision.
    Returns WITHIN_LIMITS or EXCEEDS_LIMIT with details."""
    return _call_m6_compliance("check_concentration", {
        "client_id": client_id,
        "ticker": ticker,
        "proposed_pct": proposed_pct,
    })
