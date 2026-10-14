"""
MCP client helper for Strands agents.

V3 constraint: ALL outbound calls from Strands agents to MCP servers
MUST traverse MuleSoft Flex Gateway so the gateway can enforce
MNPI/rate-limit/audit/circuit-breaker policies.

Reads Flex Gateway base URL from env var `FLEX_GATEWAY_URL` (set via
SAM parameter `FlexGatewayUrl`). If unset, we fall back to direct
API Gateway calls and log a warning — this is a safety net so agents
still function during bootstrap, but `CONFIGURE_AFTER_DEPLOY` values
must be replaced before the trust layer can attest the stack.

Public API:
    callMcpTool(server, tool_name, arguments, api_key=None, timeout=10)
        -> dict   (parsed MCP /tools/call response)

Server slugs expected by the Flex Gateway routing table:
    "sec-edgar", "market-data", "news-search"
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

FLEX_GATEWAY_URL = os.environ.get("FLEX_GATEWAY_URL", "").rstrip("/")
DIRECT_API_URL = os.environ.get("MCP_DIRECT_API_URL", "").rstrip("/")  # fallback only
MCP_API_KEY_DEFAULT = os.environ.get("MCP_API_KEY", "")


def _gateway_ready() -> bool:
    """True when the Flex Gateway URL is configured to a real value."""
    return bool(FLEX_GATEWAY_URL) and FLEX_GATEWAY_URL.upper() != "CONFIGURE_AFTER_DEPLOY"


def _base_url() -> str:
    """Resolve the base URL for MCP calls.

    Prefers Flex Gateway; falls back to direct API Gateway only when
    the gateway is unconfigured (CONFIGURE_AFTER_DEPLOY or empty).
    """
    if _gateway_ready():
        return FLEX_GATEWAY_URL
    if DIRECT_API_URL:
        logger.warning(
            "FLEX_GATEWAY_URL is not configured — falling back to direct "
            "MCP_DIRECT_API_URL. This bypasses MNPI/rate-limit/audit policies "
            "and MUST be fixed before promotion."
        )
        return DIRECT_API_URL
    raise RuntimeError(
        "No MCP endpoint available. Set FLEX_GATEWAY_URL (preferred) or "
        "MCP_DIRECT_API_URL env var."
    )


def callMcpTool(
    server: str,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Call an MCP tool via Flex Gateway.

    Args:
        server: MCP server slug (``sec-edgar``, ``market-data``, ``news-search``).
        tool_name: Tool name as advertised by the MCP server's ``tools/list``.
        arguments: Arguments dict passed to the tool.
        api_key: Optional API key override. Defaults to ``MCP_API_KEY`` env var.
        timeout: HTTP timeout in seconds.

    Returns:
        Parsed JSON response body. On MCP ``content`` envelopes, the
        inner JSON payload is extracted automatically.

    Raises:
        RuntimeError: if no endpoint is configured.
        requests.HTTPError: if the HTTP call fails.
    """
    base = _base_url()
    key = api_key if api_key is not None else MCP_API_KEY_DEFAULT
    url = f"{base}/{server}/tools/call"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "X-A2A-Origin": "strands-agent",
    }
    payload = {"name": tool_name, "arguments": arguments or {}}

    logger.debug("MCP call via %s: %s/%s", base, server, tool_name)
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()

    try:
        body = resp.json()
    except ValueError:
        logger.error("MCP response is not JSON: %s", resp.text[:500])
        return {}

    return _unwrap_mcp(body)


def listMcpTools(
    server: str,
    api_key: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """List tools exposed by an MCP server via Flex Gateway."""
    base = _base_url()
    key = api_key if api_key is not None else MCP_API_KEY_DEFAULT
    url = f"{base}/{server}/tools/list"
    headers = {"Content-Type": "application/json", "x-api-key": key}
    resp = requests.post(url, json={}, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _unwrap_mcp(body: Dict[str, Any]) -> Dict[str, Any]:
    """Extract JSON payload from MCP ``content[].text`` envelope if present.

    MCP tools/call returns::

        {"content": [{"type": "text", "text": "<json>"}]}

    We strip ``[TOOL_OUTPUT_START]`` / ``[TOOL_OUTPUT_END]`` markers and
    ``[Source: ...]`` / ``IMPORTANT:`` annotation lines so callers can
    work with a plain dict.
    """
    if not isinstance(body, dict):
        return {"raw": body}

    if "content" in body:
        for item in body.get("content", []):
            if item.get("type") == "text":
                text = item.get("text", "")
                text = text.replace("[TOOL_OUTPUT_START]", "").replace("[TOOL_OUTPUT_END]", "")
                lines = [
                    ln for ln in text.strip().split("\n")
                    if not ln.startswith("[Source:") and not ln.startswith("IMPORTANT:")
                ]
                try:
                    return json.loads("\n".join(lines))
                except json.JSONDecodeError:
                    return {"text": text.strip()}
    return body


__all__ = ["callMcpTool", "listMcpTools", "FLEX_GATEWAY_URL"]
