"""HTTPS wrapper posting to the sec-edgar MCP server's /tools/call endpoint.

Mirror of ``salesforce_crm_client``: thin, stdlib-only, no retries. The
BFF uses this to fulfill GET /api/source_tables/{id} and
GET /api/source_chunk/{id}, both of which resolve against pre-indexed
filing content served by the sec-edgar MCP.

Auth + config:
- ``MCP_API_URL``  — API Gateway stage root (required at call time).
- ``MCP_API_KEY``  — propagated as X-MCP-API-Key when present; dev mode
  on the MCP side accepts calls without it.

Imports are cheap and always succeed so the BFF Lambda cold-starts fast
and tests can monkeypatch ``call_tool`` without wrestling with env vars.
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
_TOOLS_CALL_PATH = "/mcp/sec-edgar/tools/call"


def call_tool(
    *,
    tool: str,
    arguments: dict,
    principal_id: str = "bff-proxy",
) -> dict:
    """POST to the sec-edgar MCP /tools/call endpoint and return its ``result`` dict.

    Raises:
        McpUpstreamError: non-200 response, network failure, or malformed body.
        McpError: the MCP server returned a structured error ``status=="error"``.
    """
    base_url = (os.environ.get("MCP_API_URL") or "").rstrip("/")
    if not base_url:
        raise McpUpstreamError(
            "MCP_API_URL env var is not set; BFF cannot reach sec-edgar MCP"
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
            f"sec-edgar MCP returned HTTP {exc.code}: {exc.reason}"
        ) from exc
    except urlerror.URLError as exc:
        raise McpUpstreamError(f"sec-edgar MCP network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise McpUpstreamError("sec-edgar MCP call timed out") from exc

    if status != 200:
        raise McpUpstreamError(f"sec-edgar MCP HTTP {status}")

    try:
        body: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise McpUpstreamError("sec-edgar MCP returned invalid JSON") from exc

    if isinstance(body, dict) and body.get("status") == "error":
        err = body.get("error") or {}
        raise McpError(err.get("message") or "sec-edgar tool error", code=err.get("code"))

    if not isinstance(body, dict) or "result" not in body:
        raise McpUpstreamError("sec-edgar MCP response missing 'result' key")

    result = body["result"]
    return result if isinstance(result, dict) else {"value": result}
