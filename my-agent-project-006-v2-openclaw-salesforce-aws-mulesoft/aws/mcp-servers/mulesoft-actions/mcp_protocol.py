"""Thin MCP response builders for Lambda integration responses.

Shape matches the shared protocol used by other 006 MCP servers (sec-edgar,
market-data, news-search, salesforce-crm). Duplicated here so the Lambda
package is self-contained (no cross-directory imports in the deployment
artifact).
"""

from __future__ import annotations

import json
from typing import Any


_HEADERS = {"Content-Type": "application/json"}


def _resp(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": _HEADERS, "body": json.dumps(body)}


def build_info_response(name: str, version: str, **extras: Any) -> dict[str, Any]:
    payload = {
        "protocolVersion": "2025-03-26",
        "serverInfo": {"name": name, "version": version},
        "capabilities": {"tools": {}},
    }
    if extras:
        payload["serverInfo"].update(extras)
    return _resp(200, payload)


def build_list_response(tools: list[dict[str, Any]]) -> dict[str, Any]:
    return _resp(200, {"tools": tools})


def build_call_response(result: dict[str, Any]) -> dict[str, Any]:
    return _resp(
        200,
        {
            "content": [
                {"type": "text", "text": json.dumps(result)},
            ],
            "isError": False,
            "structuredContent": result,
        },
    )


def build_error_response(status: int, code: str, message: str) -> dict[str, Any]:
    return _resp(
        status,
        {
            "isError": True,
            "error": {"code": code, "message": message},
        },
    )
