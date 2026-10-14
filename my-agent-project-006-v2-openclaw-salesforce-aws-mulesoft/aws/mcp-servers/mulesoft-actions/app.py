"""MuleSoft Actions MCP Server (Phase 6).

Exposes MuleSoft-backed enterprise actions as MCP tools via Lambda + API Gateway.

MCP protocol compliance (006 steering rule 10):
- GET /                 -> server info
- POST /tools/list      -> tool catalog with JSON Schema
- POST /tools/call      -> invoke a tool

Modes:
- mock: returns canned responses. Default until vendor sandboxes approved.
- sandbox: calls MuleSoft Anypoint sandbox environment.
- production: calls MuleSoft production environment (requires dual-approver token).

HITL is NOT enforced here. The MuleSoft skill (openclaw/skills/mulesoft-api/)
enforces HITL before any tool call reaches this server. This server assumes
the call has been approved upstream.

Audit is NOT written here. The skill writes to IR_Audit_Log__c after this
server returns. This server returns enough metadata (mulesoft_reference,
timestamps) for the skill to audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any

from mcp_protocol import (
    build_info_response,
    build_list_response,
    build_call_response,
    build_error_response,
)

try:
    from mulesoft_client import MuleSoftClient, MuleSoftClientError
except ImportError:
    # Fallback for environments where boto3 is unavailable (pure-mock local testing).
    MuleSoftClient = None  # type: ignore[assignment]
    MuleSoftClientError = Exception  # type: ignore[assignment,misc]

MODE = os.environ.get("MULESOFT_MODE", "mock").lower()
SERVER_NAME = "mulesoft-actions"
SERVER_VERSION = "0.1.0"


# --- Production-mode guard (Tier-4 #15) --------------------------------------
# The "production" mode must NEVER boot with Alpaca paper credentials.
# This guard runs at import time so the Lambda refuses to cold-start if the
# configuration is inconsistent. Rule: if MULESOFT_MODE=production, the
# operator MUST point VENDOR_ALPACA_SECRET_NAME at /006-v2/vendors/alpaca-LIVE
# (NOT /006-v2/vendors/alpaca, which is paper). The live secret's `endpoint`
# field additionally must NOT contain "paper-api.alpaca.markets".
#
# Paper vs live distinction:
#   paper-api.alpaca.markets  -> paper trading, play money
#   api.alpaca.markets        -> live trading, real money
#
# Design choice: we only hard-fail here when MODE=production. mock/sandbox
# remain unrestricted. We DO NOT create the /006-v2/vendors/alpaca-LIVE
# secret in this commit - the operator must rotate live creds in via the
# vendor UI + scripts/rotate-secrets-after-vendor-regen.sh.

_ALPACA_SECRET_ENV = "VENDOR_ALPACA_SECRET_NAME"
_ALPACA_LIVE_SECRET_NAME = "/006-v2/vendors/alpaca-LIVE"
_ALPACA_PAPER_HOST = "paper-api.alpaca.markets"


class ProductionModeConfigError(RuntimeError):
    """Raised at cold start when MULESOFT_MODE=production but config is unsafe."""


def _check_production_mode_guard() -> None:
    """Fail-fast guard: if MODE=production, refuse to boot on any paper indicator.

    Called at module import so a misconfigured Lambda surfaces as an Init error
    in CloudWatch instead of silently routing live traffic to paper. Returns
    silently for mock/sandbox modes.
    """
    if MODE != "production":
        return

    alpaca_secret = os.environ.get(_ALPACA_SECRET_ENV, "/006-v2/vendors/alpaca")
    if alpaca_secret != _ALPACA_LIVE_SECRET_NAME:
        raise ProductionModeConfigError(
            f"MULESOFT_MODE=production requires {_ALPACA_SECRET_ENV}="
            f"{_ALPACA_LIVE_SECRET_NAME}, got '{alpaca_secret}'. "
            "Refusing to boot - paper credentials must never fuel a 'production' deployment. "
            "Rotate live Alpaca credentials via scripts/rotate-secrets-after-vendor-regen.sh "
            "and set the env var to the LIVE secret path."
        )

    # Cross-check: look up the secret's endpoint field. If it points at
    # paper-api.alpaca.markets, the secret itself is mislabeled. Refuse.
    if MuleSoftClient is None:
        # No boto3 available (pure-mock local testing). Name check already passed.
        return

    try:
        import boto3  # local import so unit-test shim can monkeypatch

        client = boto3.client("secretsmanager")
        raw = client.get_secret_value(SecretId=alpaca_secret).get("SecretString", "{}")
        creds = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - if we cannot read, we cannot prove it's safe
        raise ProductionModeConfigError(
            f"MULESOFT_MODE=production but {alpaca_secret} is unreadable: {exc}. "
            "Refusing to boot."
        ) from exc

    endpoint = str(creds.get("endpoint") or creds.get("base_url") or "")
    if _ALPACA_PAPER_HOST in endpoint.lower():
        raise ProductionModeConfigError(
            f"MULESOFT_MODE=production but {alpaca_secret} endpoint='{endpoint}' "
            f"contains '{_ALPACA_PAPER_HOST}'. Refusing to boot - this is paper."
        )


_check_production_mode_guard()

# Lazy-initialized client — only created when sandbox/production mode is active.
_client: "MuleSoftClient | None" = None


def _get_client() -> "MuleSoftClient":
    global _client
    if _client is None:
        if MuleSoftClient is None:
            raise RuntimeError(
                "mulesoft_client module unavailable — install boto3 to use sandbox/production mode"
            )
        _client = MuleSoftClient()
    return _client


# --- Tool schemas (JSON Schema — 006 steering rule 12) -----------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "who_am_i",
        "description": "Return info about the authenticated Connected App. Sandbox-mode diagnostic only — read-only, no approval required.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_environments",
        "description": "List Anypoint environments in the org. Sandbox-mode diagnostic only — read-only, no approval required.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "submit_order",
        "description": "Submit a trade order to the OMS. Requires HITL approval upstream.",
        "inputSchema": {
            "type": "object",
            "required": ["ticker", "side", "quantity", "client_id", "account_id", "approval_token"],
            "properties": {
                "ticker": {"type": "string", "pattern": "^[A-Z]{1,5}$"},
                "side": {"type": "string", "enum": ["BUY", "SELL"]},
                "quantity": {"type": "integer", "minimum": 1},
                "order_type": {"type": "string", "enum": ["MARKET", "LIMIT"], "default": "MARKET"},
                "limit_price": {"type": "number"},
                "client_id": {"type": "string"},
                "account_id": {"type": "string"},
                "approval_token": {"type": "string", "description": "Signed HITL approval token from mulesoft-api skill"},
                "dual_approval_token": {"type": "string", "description": "Required when order notional > $500K"},
            },
        },
    },
    {
        "name": "get_order_status",
        "description": "Get fill status for a previously submitted order.",
        "inputSchema": {
            "type": "object",
            "required": ["order_id"],
            "properties": {"order_id": {"type": "string"}},
        },
    },
    {
        "name": "rebalance_portfolio",
        "description": "Submit a basket of rebalancing trades. Requires HITL approval upstream.",
        "inputSchema": {
            "type": "object",
            "required": ["client_id", "trades", "approval_token"],
            "properties": {
                "client_id": {"type": "string"},
                "trades": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["ticker", "side", "quantity"],
                        "properties": {
                            "ticker": {"type": "string"},
                            "side": {"type": "string", "enum": ["BUY", "SELL"]},
                            "quantity": {"type": "integer"},
                        },
                    },
                },
                "approval_token": {"type": "string"},
                "dual_approval_token": {"type": "string"},
            },
        },
    },
    {
        "name": "initiate_wire",
        "description": "Initiate a wire transfer. Dual approval required above $100K.",
        "inputSchema": {
            "type": "object",
            "required": ["client_id", "from_account", "to_account", "amount", "currency", "approval_token"],
            "properties": {
                "client_id": {"type": "string"},
                "from_account": {"type": "string"},
                "to_account": {"type": "string"},
                "amount": {"type": "number", "minimum": 0.01},
                "currency": {"type": "string", "enum": ["USD", "EUR", "GBP", "JPY"]},
                "priority": {"type": "string", "enum": ["SAME_DAY", "NEXT_DAY", "STANDARD"]},
                "approval_token": {"type": "string"},
                "dual_approval_token": {"type": "string"},
            },
        },
    },
    {
        "name": "get_settlement_status",
        "description": "Check wire settlement status.",
        "inputSchema": {
            "type": "object",
            "required": ["wire_id"],
            "properties": {"wire_id": {"type": "string"}},
        },
    },
    {
        "name": "run_kyc_screening",
        "description": "Run KYC/AML screening on a prospect or client.",
        "inputSchema": {
            "type": "object",
            "required": ["client_name", "level"],
            "properties": {
                "client_name": {"type": "string"},
                "level": {"type": "string", "enum": ["STANDARD", "ENHANCED"]},
                "checks": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["sanctions", "pep", "adverse_media"]},
                    "default": ["sanctions", "pep"],
                },
            },
        },
    },
    {
        "name": "open_account",
        "description": "Open a new account in core banking + custodian. Requires compliance HITL.",
        "inputSchema": {
            "type": "object",
            "required": ["client_id", "account_type", "jurisdiction", "approval_token"],
            "properties": {
                "client_id": {"type": "string"},
                "account_type": {
                    "type": "string",
                    "enum": ["BROKERAGE", "MANAGED", "IRA", "ROTH_IRA", "TRUST", "529"],
                },
                "jurisdiction": {"type": "string"},
                "risk_profile": {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
                "approval_token": {"type": "string"},
            },
        },
    },
    {
        "name": "close_account",
        "description": "Close an existing account. ALWAYS requires dual approval per 006 v2 steering rule 5.",
        "inputSchema": {
            "type": "object",
            "required": ["client_id", "account_id", "reason", "approval_token", "dual_approval_token"],
            "properties": {
                "client_id": {"type": "string"},
                "account_id": {"type": "string"},
                "reason": {"type": "string", "minLength": 10},
                "approval_token": {"type": "string"},
                "dual_approval_token": {"type": "string"},
            },
        },
    },
]


# --- Mock responses ----------------------------------------------------------

def _mock_submit_order(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": f"MOCK-ORDER-{uuid.uuid4().hex[:8].upper()}",
        "status": "SUBMITTED",
        "ticker": args["ticker"],
        "side": args["side"],
        "quantity": args["quantity"],
        "submitted_at": int(time.time()),
        "mulesoft_reference": f"MS-REF-{uuid.uuid4().hex[:12]}",
        "mode": "mock",
    }


def _mock_get_order_status(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": args["order_id"],
        "status": "FILLED",
        "avg_price": 135.42,
        "filled_quantity": 1000,
        "mode": "mock",
    }


def _mock_initiate_wire(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "wire_id": f"MOCK-WIRE-{uuid.uuid4().hex[:8].upper()}",
        "status": "INITIATED",
        "amount": args["amount"],
        "currency": args["currency"],
        "submitted_at": int(time.time()),
        "mulesoft_reference": f"MS-REF-{uuid.uuid4().hex[:12]}",
        "mode": "mock",
    }


def _mock_get_settlement_status(args: dict[str, Any]) -> dict[str, Any]:
    return {"wire_id": args["wire_id"], "status": "SETTLED", "settled_at": int(time.time()), "mode": "mock"}


def _mock_run_kyc(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "screening_id": f"MOCK-KYC-{uuid.uuid4().hex[:8].upper()}",
        "client_name": args["client_name"],
        "level": args["level"],
        "results": {"sanctions": "CLEAR", "pep": "CLEAR", "adverse_media": "CLEAR"},
        "screened_at": int(time.time()),
        "mode": "mock",
    }


def _mock_open_account(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_number": f"MOCK-ACCT-{uuid.uuid4().hex[:10].upper()}",
        "account_type": args["account_type"],
        "status": "OPEN",
        "opened_at": int(time.time()),
        "mulesoft_reference": f"MS-REF-{uuid.uuid4().hex[:12]}",
        "mode": "mock",
    }


def _mock_rebalance(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "basket_id": f"MOCK-BASKET-{uuid.uuid4().hex[:8].upper()}",
        "client_id": args["client_id"],
        "trade_count": len(args.get("trades", [])),
        "status": "SUBMITTED",
        "submitted_at": int(time.time()),
        "mode": "mock",
    }


def _mock_close_account(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": args["account_id"],
        "status": "CLOSED",
        "closed_at": int(time.time()),
        "mulesoft_reference": f"MS-REF-{uuid.uuid4().hex[:12]}",
        "mode": "mock",
    }


MOCK_HANDLERS = {
    "submit_order": _mock_submit_order,
    "get_order_status": _mock_get_order_status,
    "rebalance_portfolio": _mock_rebalance,
    "initiate_wire": _mock_initiate_wire,
    "get_settlement_status": _mock_get_settlement_status,
    "run_kyc_screening": _mock_run_kyc,
    "open_account": _mock_open_account,
    "close_account": _mock_close_account,
}


# --- Process API routing for action tools (sandbox/production mode) ----------
#
# Each entry specifies:
#   path: HTTP path suffix appended to the base URL (per docs/v2-mulesoft-process-api-deploy.md)
#   fields: list of raw-pass-through request fields (non-token)
#   optional: list of fields forwarded only when present in args
#   hash_fields: dict mapping raw-token arg name -> target hashed-field name on Mule side
#
# The _call_process_api helper below reads this table, builds the payload, SHA-256s the tokens,
# and POSTs to {base_url}{path}. Adding a new action = one new row here + one new Mule app.
#
# Raw approval tokens never leave the Lambda. Only SHA-256 hashes cross the wire.

ACTION_TOOL_SPECS: dict[str, dict[str, Any]] = {
    "submit_order": {
        "path": "/api/orders",
        "fields": ["ticker", "side", "quantity", "client_id", "account_id"],
        "optional": ["order_type", "limit_price"],
        "hash_fields": {"approval_token": "approval_token_hash"},
    },
    "initiate_wire": {
        "path": "/api/wires",
        "fields": ["client_id", "from_account", "to_account", "amount", "currency"],
        "optional": ["priority"],
        "hash_fields": {
            "approval_token": "approval_token_hash",
            "dual_approval_token": "dual_approval_token_hash",
        },
    },
    "rebalance_portfolio": {
        "path": "/api/rebalances",
        "fields": ["client_id", "trades"],
        "optional": [],
        "hash_fields": {
            "approval_token": "approval_token_hash",
            "dual_approval_token": "dual_approval_token_hash",
        },
    },
    "run_kyc_screening": {
        "path": "/api/kyc",
        "fields": ["client_name", "level"],
        "optional": ["checks"],
        "hash_fields": {"approval_token": "approval_token_hash"},
    },
    "open_account": {
        "path": "/api/accounts",
        "fields": ["client_id", "account_type", "jurisdiction"],
        "optional": ["risk_profile"],
        "hash_fields": {"approval_token": "approval_token_hash"},
    },
    "close_account": {
        "path": "/api/accounts/close",
        "fields": ["client_id", "account_id", "reason"],
        "optional": [],
        "hash_fields": {
            "approval_token": "approval_token_hash",
            "dual_approval_token": "dual_approval_token_hash",
        },
    },
}


def _call_process_api(
    client: "MuleSoftClient", tool_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Route a single action tool to its CloudHub-deployed Process API.

    Resolves the deployed base URL from Secrets Manager, SHA-256s raw approval
    tokens, builds the JSON payload per the action's spec, and POSTs. All six
    action tools share this path - submit_order's previous inline block became
    one row in ACTION_TOOL_SPECS.

    Error handling mirrors the original submit_order behavior:
      502  Mule returned an HTTP error (authorization, schema, etc.)
      503  process_api_base_url not configured in the secret
      504  Network / DNS / timeout reaching CloudHub
    """
    spec = ACTION_TOOL_SPECS[tool_name]

    try:
        base_url = client.get_credential("process_api_base_url")
    except MuleSoftClientError as exc:
        return build_error_response(502, "creds_unavailable", str(exc))

    if not base_url:
        return build_error_response(
            503,
            "process_api_not_configured",
            "Process API URL not configured in Secrets Manager. "
            "Add 'process_api_base_url' to /006-v2/mulesoft/credentials "
            "per docs/v2-mulesoft-process-api-deploy.md step 6.",
        )

    # Build payload: required fields + present optional fields + hashed tokens.
    payload: dict[str, Any] = {field: args.get(field) for field in spec["fields"]}
    for field in spec["optional"]:
        if field in args:
            payload[field] = args[field]
    for raw_name, hashed_name in spec["hash_fields"].items():
        raw_value = args.get(raw_name)
        if raw_value:
            payload[hashed_name] = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()

    full_url = f"{base_url.rstrip('/')}{spec['path']}"

    try:
        result = client.request_process_api("POST", full_url, json_body=payload)
    except MuleSoftClientError as exc:
        return build_error_response(502, "process_api_error", str(exc))
    except Exception as exc:  # network / DNS / timeout
        return build_error_response(
            504,
            "process_api_unreachable",
            f"Could not reach Process API at {full_url}: {exc}",
        )

    return build_call_response(result)


# --- Lambda handler ----------------------------------------------------------

def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    path = event.get("rawPath", event.get("path", "/"))
    body_raw = event.get("body") or "{}"
    try:
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    except json.JSONDecodeError:
        return build_error_response(400, "invalid_json", "Body must be valid JSON")

    if method == "GET" and (path == "/" or path.endswith("/mulesoft-actions")):
        return build_info_response(SERVER_NAME, SERVER_VERSION, mode=MODE)

    if method == "POST" and path.endswith("/tools/list"):
        return build_list_response(TOOLS)

    if method == "POST" and path.endswith("/tools/call"):
        tool_name = body.get("name")
        args = body.get("arguments", {})
        if not tool_name:
            return build_error_response(400, "missing_tool", "Request body must include 'name'")

        if MODE == "mock":
            handler = MOCK_HANDLERS.get(tool_name)
            if not handler:
                return build_error_response(404, "unknown_tool", f"Tool '{tool_name}' not registered")
            result = handler(args)
            return build_call_response(result)

        if MODE in {"sandbox", "production"}:
            try:
                client = _get_client()
            except RuntimeError as exc:
                return build_error_response(500, "client_unavailable", str(exc))

            # Diagnostic tools — available in sandbox/production for smoke-testing auth wiring.
            if tool_name == "who_am_i":
                try:
                    return build_call_response(client.who_am_i())
                except MuleSoftClientError as exc:
                    return build_error_response(502, "mulesoft_error", str(exc))
            if tool_name == "list_environments":
                try:
                    return build_call_response(client.list_environments())
                except MuleSoftClientError as exc:
                    return build_error_response(502, "mulesoft_error", str(exc))

            # Action tools — graduated from mock to CloudHub-deployed Process APIs.
            # The raw approval_token (+ dual_approval_token) is hashed here; only the hash
            # crosses the wire to Mule. Raw tokens never leave this Lambda.
            if tool_name in ACTION_TOOL_SPECS:
                return _call_process_api(client, tool_name, args)

            # Tools still unbuilt on the Mule side: get_order_status, get_settlement_status.
            # These need separate Process APIs (status lookups, not writes) that the current
            # phase did not cover.
            return build_error_response(
                501,
                "process_api_not_deployed",
                f"Tool '{tool_name}' requires a MuleSoft Process API that is not yet deployed. "
                "Currently supported in "
                f"MULESOFT_MODE={MODE}: 'who_am_i', 'list_environments', and the 6 action tools "
                "(submit_order, initiate_wire, rebalance_portfolio, run_kyc_screening, "
                "open_account, close_account). Status lookups (get_order_status, "
                "get_settlement_status) remain on the v2 Phase 6 backlog.",
            )

        return build_error_response(
            400,
            "unknown_mode",
            f"MULESOFT_MODE='{MODE}' is not recognized. Valid: mock, sandbox, production.",
        )

    return build_error_response(404, "not_found", f"{method} {path} not supported")
