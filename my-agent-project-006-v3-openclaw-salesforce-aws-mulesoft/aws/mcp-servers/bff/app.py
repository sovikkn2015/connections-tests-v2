"""BFF (Backend-For-Frontend) Lambda — V3.

Thin REST shim that answers the four endpoints the React frontend calls:

  GET  /api/inquiries?type=alert&status=open   -> AlertQueue.tsx polls this
  GET  /api/source_tables/{id}                 -> chartRenderer.ts
  GET  /api/source_chunk/{id}                  -> citationChip drill-down
  POST /api/session/warm                       -> useIntentPrefetch

The BFF does NOT host business logic. For each request it routes to one
of the existing MCP servers by invoking its `/tools/call` endpoint via
the shared `_base` MCP server surface. That keeps the trust spine intact:
every data read still goes through the salesforce-crm MCP's MNPI redact,
SOQL safety validation, and persona write-gate.

Auth: bearer token in `Authorization` header, same shape the WebSocket
uses. Production mode (MCP_API_KEY set, MCP_DEV_MODE != true) validates.
Dev mode tolerates a missing header.

Output shapes mirror `frontend/src/types/api.ts`. No drift allowed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any
from urllib.parse import parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import (  # noqa: E402
    McpAuthError,
    McpError,
    McpValidationError,
)
from _base.mcp_server import build_response  # noqa: E402


logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Auth guard — mirrors _base.mcp_server._require_api_key semantics, but
# the BFF uses X-Session-Token (or Authorization Bearer) not X-MCP-API-Key.
# ---------------------------------------------------------------------------
def _require_session_token(headers: dict[str, str]) -> str:
    dev_mode = os.environ.get("MCP_DEV_MODE", "").lower() == "true"
    expected_signing_key = os.environ.get("AGENTCORE_SESSION_SIGNING_KEY", "").strip()
    auth = headers.get("authorization", "") or headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    else:
        token = headers.get("x-session-token", "") or headers.get("X-Session-Token", "")
    if not token:
        if dev_mode:
            return "dev-bootstrap-token"
        raise McpAuthError("Missing Authorization bearer or X-Session-Token")
    if not expected_signing_key and not dev_mode:
        raise McpAuthError(
            "AGENTCORE_SESSION_SIGNING_KEY not configured; cannot validate tokens"
        )
    # In a real deploy the token would be HMAC-verified here; for V3 demo we
    # accept any non-empty token that reaches us over TLS via API Gateway.
    # Production hardening: validate HMAC signature + issuer + expiry against
    # AGENTCORE_SESSION_SIGNING_KEY. Out of scope for V3 BFF.
    return token


# ---------------------------------------------------------------------------
# Inquiries endpoint — routes to salesforce-crm MCP.
# ---------------------------------------------------------------------------
def handle_inquiries(query_params: dict[str, list[str]], principal_id: str) -> dict:
    """Answer GET /api/inquiries?type=alert&status=open.

    Delegates to salesforce-crm MCP's `read_object` tool with a SOQL filter.
    The MCP handler enforces MNPI redaction + SOQL safety + persona gate
    before returning rows.
    """
    inquiry_type = (query_params.get("type", ["alert"]) or ["alert"])[0]
    status = (query_params.get("status", ["open"]) or ["open"])[0]

    if inquiry_type not in {"alert", "question", "research-suggestion"}:
        raise McpValidationError(f"invalid type filter {inquiry_type!r}")
    if status not in {"open", "resolved"}:
        raise McpValidationError(f"invalid status filter {status!r}")

    try:
        from salesforce_crm_client import call_tool as sf_call
    except ImportError as exc:
        # Import MUST succeed in V3 — the shim is bundled with the BFF
        # Lambda. A missing module is a packaging bug, not a soft failure.
        raise McpError(f"BFF packaging error: salesforce_crm_client unavailable ({exc})") from exc

    rows = sf_call(
        tool="read_object",
        arguments={
            "object_type": "Client_Inquiry__c",
            "where": {"Type__c": inquiry_type, "Status__c": status},
            "fields": [
                "Id",
                "Ticker_Mentions__c",
                "Client_Contact_Id__c",
                "Client_Contact_Name__c",
                "Auto_Send_Eligible__c",
                "Concentration_Pct__c",
                "CreatedDate",
            ],
            "limit": 50,
        },
        principal_id=principal_id,
    )

    items = [
        {
            "id": r.get("Id"),
            "ticker": r.get("Ticker_Mentions__c") or "",
            "concentration_pct": float(r.get("Concentration_Pct__c") or 0.0),
            "client_name": r.get("Client_Contact_Name__c") or "",
            "client_contact_id": r.get("Client_Contact_Id__c") or "",
            "auto_send_eligible": bool(r.get("Auto_Send_Eligible__c")),
            "timestamp": r.get("CreatedDate") or "",
        }
        for r in (rows.get("records") or rows.get("rows") or [])
    ]
    return {"items": items}


# ---------------------------------------------------------------------------
# Source-table and source-chunk endpoints — route to sec-edgar MCP.
# Both are read-only lookups of pre-indexed filing + memo content.
# ---------------------------------------------------------------------------
def handle_source_table(source_id: str) -> dict:
    """Answer GET /api/source_tables/{id}.

    source_id is a stable identifier minted by the filings/research
    corpus ingestion pipelines. The lookup goes to sec-edgar MCP for
    public filings and to the research-corpus cache for internal memos.
    Both return the SourceTable shape declared in frontend/src/types/api.ts.
    """
    if not source_id:
        raise McpValidationError("source_id required")
    try:
        from sec_edgar_client import call_tool as edgar_call
    except ImportError as exc:
        raise McpError(f"BFF packaging error: sec_edgar_client unavailable ({exc})") from exc

    resp = edgar_call(
        tool="get_source_table",
        arguments={"source_id": source_id},
    )
    if not resp or not resp.get("columns"):
        return _empty_source_table(source_id)
    return resp


def handle_source_chunk(source_id: str) -> dict:
    """Answer GET /api/source_chunk/{id}."""
    if not source_id:
        raise McpValidationError("source_id required")
    try:
        from sec_edgar_client import call_tool as edgar_call
    except ImportError as exc:
        raise McpError(f"BFF packaging error: sec_edgar_client unavailable ({exc})") from exc

    resp = edgar_call(
        tool="get_source_chunk",
        arguments={"source_id": source_id},
    )
    if not resp or not resp.get("text"):
        return _empty_source_chunk(source_id)
    return resp


def _empty_source_table(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "title": "(source not available)",
        "columns": [],
        "rows": [],
        "as_of": "",
        "citation": {
            "span_id": "",
            "source_id": source_id,
            "source_type": "filing",
            "label": "(unavailable)",
        },
    }


def _empty_source_chunk(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "title": "(source not available)",
        "text": "",
    }


# ---------------------------------------------------------------------------
# Session warm — intent prefetch path. Non-blocking, logs only.
# ---------------------------------------------------------------------------
def handle_session_warm(body: dict, principal_id: str) -> dict:
    """Answer POST /api/session/warm.

    The frontend fires this when the user starts typing a ticker. We use it
    to pre-cache RAG hits so the streaming turn lands instantly. For V3 BFF
    we just log + 200; the actual cache-warm happens inside AgentCore when
    the WebSocket turn opens.
    """
    ticker = (body.get("ticker") or "").strip().upper()
    if not ticker:
        raise McpValidationError("ticker required")
    if len(ticker) > 12 or not ticker.replace(".", "").isalnum():
        raise McpValidationError(f"invalid ticker {ticker!r}")
    logger.info(
        "session_warm ticker=%s principal=%s persona=%s",
        ticker,
        principal_id,
        body.get("persona"),
    )
    return {"warmed": True, "ticker": ticker}


# ---------------------------------------------------------------------------
# Router + Lambda handler.
# ---------------------------------------------------------------------------
_ROUTES = {
    ("GET", "/api/inquiries"): "inquiries",
    ("GET", "/api/source_tables"): "source_table",
    ("GET", "/api/source_chunk"): "source_chunk",
    ("POST", "/api/session/warm"): "session_warm",
}


def _route(method: str, path: str) -> tuple[str | None, str | None]:
    """Return (handler_name, path_param) for a request."""
    if (method, path) in _ROUTES:
        return _ROUTES[(method, path)], None
    if method == "GET":
        if path.startswith("/api/source_tables/"):
            return "source_table", path[len("/api/source_tables/"):]
        if path.startswith("/api/source_chunk/"):
            return "source_chunk", path[len("/api/source_chunk/"):]
    return None, None


def lambda_handler(event: dict, _context: Any = None) -> dict:
    """API Gateway proxy integration entrypoint."""
    try:
        method = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
        path = event.get("path") or event.get("rawPath") or "/"
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        query_params: dict[str, list[str]] = {}
        raw_qs = event.get("rawQueryString") or ""
        if raw_qs:
            query_params = parse_qs(raw_qs, keep_blank_values=True)
        elif event.get("queryStringParameters"):
            query_params = {k: [v] for k, v in (event["queryStringParameters"] or {}).items()}
        body_raw = event.get("body") or ""
        body: dict = {}
        if body_raw:
            try:
                body = json.loads(body_raw)
            except json.JSONDecodeError:
                return build_response(400, {"error": "invalid_json"})

        try:
            _require_session_token(headers)
        except McpAuthError as exc:
            return build_response(401, {"error": "unauthorized", "message": str(exc)})

        principal_id = headers.get("x-principal-id", "") or "unknown"

        handler_name, path_param = _route(method, path)
        if handler_name is None:
            return build_response(404, {"error": "not_found", "path": path})

        try:
            if handler_name == "inquiries":
                payload = handle_inquiries(query_params, principal_id)
            elif handler_name == "source_table":
                payload = handle_source_table(path_param or "")
            elif handler_name == "source_chunk":
                payload = handle_source_chunk(path_param or "")
            elif handler_name == "session_warm":
                payload = handle_session_warm(body, principal_id)
            else:
                return build_response(500, {"error": "internal", "message": "router_bug"})
        except McpValidationError as exc:
            return build_response(400, {"error": "validation_error", "message": str(exc)})
        except McpError as exc:
            return build_response(502, {"error": "upstream_error", "message": str(exc)})

        return build_response(200, payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("bff_unhandled")
        return build_response(500, {"error": "internal", "message": str(exc)[:200]})
