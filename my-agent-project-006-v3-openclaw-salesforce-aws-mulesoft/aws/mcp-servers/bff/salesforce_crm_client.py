"""HTTPS wrapper posting to the salesforce-crm MCP server's /tools/call endpoint.

The BFF runs inside the same API Gateway stage as the MCP servers, so we
can call the stage root URL from env var MCP_API_URL (set by the SAM
template via !Sub "https://${McpApi}.execute-api.${AWS::Region}.amazonaws.com/${EnvName}").

We keep this thin. No retries (Lambda timeout governs). No caching.
Auth: inherits the caller's X-MCP-API-Key via env var MCP_API_KEY — same
value the MCP server expects. In MCP_DEV_MODE the header is optional.

This module MUST import cleanly even when MCP_API_URL is unset; the error
is raised at call time instead so unit tests and cold-start imports stay
fast and deterministic.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base.errors import McpError, McpUpstreamError  # noqa: E402

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0
_TOOLS_CALL_PATH = "/mcp/salesforce-crm/tools/call"


def call_tool(
    *,
    tool: str,
    arguments: dict,
    principal_id: str = "bff-proxy",
) -> dict:
    """POST to the salesforce-crm MCP /tools/call endpoint and return its ``result`` dict.

    Raises:
        McpUpstreamError: non-200 response, network failure, or malformed body.
        McpError: the MCP server returned a structured error ``status=="error"``.
    """
    base_url = (os.environ.get("MCP_API_URL") or "").rstrip("/")
    if not base_url:
        raise McpUpstreamError(
            "MCP_API_URL env var is not set; BFF cannot reach salesforce-crm MCP"
        )

    url = f"{base_url}{_TOOLS_CALL_PATH}"
    headers = {
        "Content-Type": "application/json",
        "X-Principal-Id": principal_id,
    }
    api_key = os.environ.get("MCP_API_KEY", "").strip()
    if api_key:
        headers["X-MCP-API-Key"] = api_key

    payload = json.dumps({"name": tool, "arguments": arguments}).encode("utf-8")
    req = urlrequest.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        raise McpUpstreamError(
            f"salesforce-crm MCP returned HTTP {exc.code}: {exc.reason}"
        ) from exc
    except urlerror.URLError as exc:
        raise McpUpstreamError(f"salesforce-crm MCP network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise McpUpstreamError("salesforce-crm MCP call timed out") from exc

    if status != 200:
        raise McpUpstreamError(f"salesforce-crm MCP HTTP {status}")

    try:
        body: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise McpUpstreamError("salesforce-crm MCP returned invalid JSON") from exc

    if isinstance(body, dict) and body.get("status") == "error":
        err = body.get("error") or {}
        raise McpError(err.get("message") or "salesforce-crm tool error", code=err.get("code"))

    if not isinstance(body, dict) or "result" not in body:
        raise McpUpstreamError("salesforce-crm MCP response missing 'result' key")

    result = body["result"]
    return result if isinstance(result, dict) else {"value": result}
