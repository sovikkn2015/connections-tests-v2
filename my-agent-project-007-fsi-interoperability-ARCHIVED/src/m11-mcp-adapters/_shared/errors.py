"""
Canonical error format for M11 MCP adapters (Rule 5).
All vendor-specific errors are translated into this format.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_error(
    message: str,
    error_code: str = "INTERNAL_ERROR",
    vendor_status_code: int | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Return error in the canonical MCP error format."""
    return {
        "isError": True,
        "content": [{"type": "text", "text": message}],
        "errorCode": error_code,
        "vendorStatusCode": vendor_status_code,
        "retryable": retryable,
    }


def tool_result(data: Any) -> dict[str, Any]:
    """Return a successful tool result in MCP format."""
    text = json.dumps(data, default=str) if not isinstance(data, str) else data
    return {
        "content": [{"type": "text", "text": text}],
    }
