"""V3 salesforce-crm MCP server.

Tools:
- query_soql(soql)
- get_object(sobject, record_id)
- create_object(sobject, fields)
- update_object(sobject, record_id, fields)
- query_data_cloud_dlm(query)

Per-user auth: every call goes through the SF Auth Proxy Lambda to
obtain a short-lived session token for the principal_id carried in the
X-Principal-Id header. Salesforce sharing rules then enforce authz.

MNPI redaction is applied to every outbound record — shares_held and
market_value never reach the LLM as raw numbers.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import (  # noqa: E402
    McpAuthError,
    McpError,
    McpServer,
    McpUpstreamError,
    McpValidationError,
    ToolSpec,
)
from _mnpi_redact import redact_record, redact_records  # noqa: E402
from _soql_safe import (  # noqa: E402
    SoqlSafeError,
    ensure_read_only,
    validate_identifier,
)

MOCK_MODE = os.environ.get("SALESFORCE_CRM_MODE", "live").lower() == "mock"
SF_AUTH_PROXY_URL = os.environ.get("SF_AUTH_PROXY_URL", "")
SF_API_VERSION = os.environ.get("SF_API_VERSION", "v60.0")

_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}
_TOKEN_TTL_S = 60 * 60


def _require_principal(ctx: dict) -> str:
    pid = ctx.get("principal_id", "")
    if not pid:
        raise McpAuthError("Missing X-Principal-Id header")
    return pid


def _persona(ctx: dict) -> str:
    return ctx.get("persona", "")


def _obo_token(principal_id: str) -> dict:
    now = time.time()
    cached = _TOKEN_CACHE.get(principal_id)
    if cached and cached[0] > now:
        return cached[1]

    if MOCK_MODE or not SF_AUTH_PROXY_URL:
        payload = {
            "access_token": f"MOCK-TOKEN-{principal_id[:12]}",
            "instance_url": "https://mock.my.salesforce.com",
            "expires_in": _TOKEN_TTL_S,
        }
        _TOKEN_CACHE[principal_id] = (now + _TOKEN_TTL_S, payload)
        return payload

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                SF_AUTH_PROXY_URL,
                json={"principal_id": principal_id, "grant_type": "obo"},
                headers={"X-Internal-Auth": os.environ.get("SF_AUTH_PROXY_KEY", "")},
            )
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"SF auth proxy unreachable: {exc}") from exc

    if not resp.is_success:
        raise McpAuthError(f"SF OBO failed: {resp.status_code} {resp.text[:120]}")
    body = resp.json()
    _TOKEN_CACHE[principal_id] = (now + float(body.get("expires_in", _TOKEN_TTL_S)) - 60, body)
    return body


def _sf_call(method: str, path: str, principal_id: str, json_body: dict | None = None) -> dict:
    token = _obo_token(principal_id)
    url = f"{token['instance_url']}/services/data/{SF_API_VERSION}{path}"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                    "Content-Type": "application/json",
                },
                json=json_body,
            )
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"SF REST unreachable: {exc}") from exc

    if resp.status_code == 401:
        _TOKEN_CACHE.pop(principal_id, None)
        raise McpAuthError("SF session expired")
    if not resp.is_success:
        raise McpUpstreamError(f"SF {method} {path} failed: {resp.status_code} {resp.text[:200]}")
    if resp.content:
        return resp.json()
    return {}


def _mock_records(sobject: str) -> list[dict]:
    if sobject == "Research_Brief__c":
        return [
            {
                "Id": "a0B000000000001AAC",
                "Ticker__c": "NVDA",
                "Thesis__c": "Data-center demand sustains growth through FY27.",
                "Sentiment_Score__c": 0.55,
                "Compliance_Status__c": "CLEAR",
                "Mnpi_Cleared__c": True,
                "Rm_Consumable__c": True,
                "Published_At__c": "2026-04-15T11:08:00Z",
                "Author_Agent_Id__c": "research-orchestrator",
            }
        ]
    if sobject == "Client_Inquiry__c":
        return [
            {
                "Id": "a0C000000000001AAC",
                "Client_Contact_Id__c": "003000000000001AAC",
                "Inquiry_Text__c": "Should I be worried about NVDA?",
                "Channel__c": "WhatsApp",
                "Type__c": "question",
                "Ticker_Mentions__c": "NVDA",
                "Resolved_By_Rm__c": False,
            }
        ]
    if sobject == "Position":
        return [
            {
                "Id": "p00000000000001AAC",
                "Account": {"Name": "Patel Household"},
                "Security": "NVDA",
                "Shares_Held__c": 150,
                "Market_Value__c": 24322.50,
                "Portfolio_Pct": 6.2,
            }
        ]
    return []


def _mock_dlm(_query: str) -> list[dict]:
    return [
        {
            "Client_Contact_Id": "003000000000001AAC",
            "Client_Name": "Patel Household",
            "Ticker": "NVDA",
            "Portfolio_Pct": 6.2,
            "Last_Contact_Days": 9,
            "Latest_Brief_Id": "a0B000000000001AAC",
            "Latest_Brief_Title": "NVDA — Pre-Earnings Research",
        },
        {
            "Client_Contact_Id": "003000000000002AAC",
            "Client_Name": "Chen Household",
            "Ticker": "NVDA",
            "Portfolio_Pct": 7.8,
            "Last_Contact_Days": 12,
            "Latest_Brief_Id": "a0B000000000001AAC",
            "Latest_Brief_Title": "NVDA — Pre-Earnings Research",
        },
    ]


def handle_query_soql(args: dict, ctx: dict) -> dict:
    principal_id = _require_principal(ctx)
    soql = args.get("soql")
    try:
        safe = ensure_read_only(soql) if isinstance(soql, str) else None
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc
    if not safe:
        raise McpValidationError("'soql' required")

    if MOCK_MODE:
        upper = safe.upper()
        for name in ("Research_Brief__c", "Client_Inquiry__c", "Position", "IR_Audit_Log__c"):
            if name.upper() in upper:
                return {"records": redact_records(_mock_records(name)), "totalSize": 1, "dataSource": "mock"}
        return {"records": [], "totalSize": 0, "dataSource": "mock"}

    params = httpx.QueryParams({"q": safe})
    result = _sf_call("GET", f"/query/?{params}", principal_id)
    records = result.get("records", [])
    return {
        "records": redact_records(records),
        "totalSize": result.get("totalSize", len(records)),
        "done": result.get("done", True),
        "dataSource": "salesforce",
    }


def handle_get_object(args: dict, ctx: dict) -> dict:
    principal_id = _require_principal(ctx)
    sobject = args.get("sobject")
    record_id = args.get("record_id")
    if not isinstance(sobject, str) or not isinstance(record_id, str):
        raise McpValidationError("'sobject' and 'record_id' required as strings")
    try:
        validate_identifier(sobject)
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc
    if not record_id.strip():
        raise McpValidationError("'record_id' required")

    if MOCK_MODE:
        records = _mock_records(sobject)
        rec = records[0] if records else {"Id": record_id, "sobject": sobject}
        return redact_record(rec)

    result = _sf_call("GET", f"/sobjects/{sobject}/{record_id}", principal_id)
    return redact_record(result)


def _validate_field_dict(fields: Any) -> dict[str, Any]:
    if not isinstance(fields, dict) or not fields:
        raise McpValidationError("'fields' must be a non-empty object")
    clean: dict[str, Any] = {}
    for k, v in fields.items():
        try:
            validate_identifier(k)
        except SoqlSafeError as exc:
            raise McpValidationError(f"Bad field name {k!r}: {exc}") from exc
        if v is None or isinstance(v, (bool, int, float, str)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = ";".join(str(x) for x in v)
        else:
            raise McpValidationError(f"Unsupported value type for {k}: {type(v).__name__}")
    return clean


def handle_create_object(args: dict, ctx: dict) -> dict:
    principal_id = _require_principal(ctx)
    persona = _persona(ctx)
    sobject = args.get("sobject")
    if not isinstance(sobject, str):
        raise McpValidationError("'sobject' required")
    try:
        validate_identifier(sobject)
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc

    if persona == "fsi_client_liaison":
        raise McpError("client-liaison persona is read-only", code=-32003, details={"persona": persona})

    fields = _validate_field_dict(args.get("fields"))

    if MOCK_MODE:
        return {"id": f"{sobject[:3]}000000000MOCKAAC", "success": True, "dataSource": "mock"}

    result = _sf_call("POST", f"/sobjects/{sobject}/", principal_id, json_body=fields)
    return {"id": result.get("id"), "success": bool(result.get("success", True)), "dataSource": "salesforce"}


def handle_update_object(args: dict, ctx: dict) -> dict:
    principal_id = _require_principal(ctx)
    persona = _persona(ctx)
    if persona == "fsi_client_liaison":
        raise McpError("client-liaison persona is read-only", code=-32003)

    sobject = args.get("sobject")
    record_id = args.get("record_id")
    if not isinstance(sobject, str) or not isinstance(record_id, str):
        raise McpValidationError("'sobject' and 'record_id' required")
    try:
        validate_identifier(sobject)
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc
    fields = _validate_field_dict(args.get("fields"))

    if MOCK_MODE:
        return {"id": record_id, "success": True, "dataSource": "mock"}

    _sf_call("PATCH", f"/sobjects/{sobject}/{record_id}", principal_id, json_body=fields)
    return {"id": record_id, "success": True, "dataSource": "salesforce"}


def handle_query_data_cloud_dlm(args: dict, ctx: dict) -> dict:
    principal_id = _require_principal(ctx)
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise McpValidationError("'query' required")

    if MOCK_MODE:
        return {"records": redact_records(_mock_dlm(query)), "dataSource": "mock"}

    result = _sf_call("POST", "/ssot/queryv2", principal_id, json_body={"sql": query})
    return {
        "records": redact_records(result.get("data", [])),
        "dataSource": "salesforce-data-cloud",
    }


server = McpServer(
    name="salesforce-crm",
    version="3.0.0",
    description="Salesforce + Data Cloud MCP with per-principal OAuth OBO and MNPI redaction.",
)

server.register(
    ToolSpec(
        name="query_soql",
        description="Read-only SOQL SELECT. Validated against write-keyword injection.",
        input_schema={
            "type": "object",
            "properties": {"soql": {"type": "string"}},
            "required": ["soql"],
        },
    ),
    handle_query_soql,
)
server.register(
    ToolSpec(
        name="get_object",
        description="Fetch a single record by Id.",
        input_schema={
            "type": "object",
            "properties": {
                "sobject": {"type": "string"},
                "record_id": {"type": "string"},
            },
            "required": ["sobject", "record_id"],
        },
    ),
    handle_get_object,
)
server.register(
    ToolSpec(
        name="create_object",
        description="Create a record (blocked for client-liaison persona).",
        input_schema={
            "type": "object",
            "properties": {
                "sobject": {"type": "string"},
                "fields": {"type": "object"},
            },
            "required": ["sobject", "fields"],
        },
    ),
    handle_create_object,
)
server.register(
    ToolSpec(
        name="update_object",
        description="Update a record (blocked for client-liaison persona).",
        input_schema={
            "type": "object",
            "properties": {
                "sobject": {"type": "string"},
                "record_id": {"type": "string"},
                "fields": {"type": "object"},
            },
            "required": ["sobject", "record_id", "fields"],
        },
    ),
    handle_update_object,
)
server.register(
    ToolSpec(
        name="query_data_cloud_dlm",
        description="Data Cloud DLM query — used for Research_Brief ↔ Position ↔ Client joins.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    handle_query_data_cloud_dlm,
)


#END_PHASE1


# ---------------------------------------------------------------------------
# High-level domain handlers (V3 wave 2 - close R2): thin wrappers around
# generic create/update/query so the skill layer can use domain-named call
# sites and the server enforces the persona gate + input validation for each.
#
# Persona gate: writes refuse fsi_client_liaison (read-only).
# Validation: tickers must match ^[A-Z]{1,12}(\.[A-Z]{1,4})?$; ids non-empty.
# ---------------------------------------------------------------------------

import re  # noqa: E402 - kept local to the high-level-handlers block
import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


_TICKER_RE = re.compile(r"^[A-Z]{1,12}(\.[A-Z]{1,4})?$")


def _require_writer_persona(ctx: dict) -> None:
    """Block fsi_client_liaison (read-only) from every write-path tool."""
    persona = _persona(ctx)
    if persona == "fsi_client_liaison":
        raise McpError(
            "client-liaison persona is read-only",
            code=-32003,
            details={"persona": persona},
        )


def _require_nonempty_str(args: dict, key: str) -> str:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        raise McpValidationError(f"'{key}' required (non-empty string)")
    return val.strip()


def _optional_str(args: dict, key: str):
    val = args.get(key)
    if val is None or val == "":
        return None
    if not isinstance(val, str):
        raise McpValidationError(f"'{key}' must be a string if provided")
    return val


def _require_ticker(args: dict, key: str = "ticker") -> str:
    raw = _require_nonempty_str(args, key)
    upper = raw.upper()
    if not _TICKER_RE.fullmatch(upper):
        raise McpValidationError(f"'{key}' must match ^[A-Z.]+$ (got {raw!r})")
    return upper


def handle_write_audit_log(args: dict, ctx: dict) -> dict:
    """Write one IR_Audit_Log__c row. Auto-populates Timestamp__c."""
    principal_id = _require_principal(ctx)
    _require_writer_persona(ctx)
    record = args.get("record")
    if isinstance(record, dict) and record:
        fields = dict(record)
    else:
        fields = {
            k: args[k]
            for k in (
                "action", "principal_id", "research_brief_id",
                "client_contact_id", "gate_trace", "approved_by",
                "dual_approver", "mulesoft_reference", "payload",
            )
            if k in args and args[k] is not None
        }
        if not fields:
            raise McpValidationError(
                "'record' dict or flat audit fields required"
            )
    fields.setdefault("Timestamp__c", datetime.now(timezone.utc).isoformat())
    if MOCK_MODE:
        return {
            "Id": f"AUDIT{uuid.uuid4().hex[:14].upper()}",
            "success": True,
            "dataSource": "mock",
        }
    result = _sf_call(
        "POST", "/sobjects/IR_Audit_Log__c/", principal_id, json_body=fields
    )
    return {
        "Id": result.get("id"),
        "success": bool(result.get("success", True)),
        "dataSource": "salesforce",
    }


def handle_write_research_brief(args: dict, ctx: dict) -> dict:
    """Write one Research_Brief__c row. Auto-populates Published_At__c."""
    principal_id = _require_principal(ctx)
    _require_writer_persona(ctx)
    record = args.get("record")
    if isinstance(record, dict) and record:
        fields = dict(record)
    else:
        ticker = _require_ticker(args)
        fields = {
            "Ticker__c": ticker,
            "Thesis__c": _require_nonempty_str(args, "thesis"),
            "Sentiment_Score__c": args.get("sentiment_score"),
            "Risk_Factors__c": args.get("risk_factors"),
            "Compliance_Status__c": args.get("compliance_status"),
            "MNPI_Cleared__c": bool(args.get("mnpi_cleared", False)),
            "RM_Consumable__c": bool(args.get("rm_consumable", False)),
            "Client_Demand__c": bool(args.get("client_demand", False)),
            "Source_Chunk_Ids__c": args.get("source_chunk_ids"),
            "Author_Agent_Id__c": _require_nonempty_str(args, "author_agent_id"),
        }
    fields.setdefault("Published_At__c", datetime.now(timezone.utc).isoformat())
    if MOCK_MODE:
        return {
            "Id": f"a0X{uuid.uuid4().hex[:15].upper()}",
            "success": True,
            "dataSource": "mock",
        }
    result = _sf_call(
        "POST", "/sobjects/Research_Brief__c/", principal_id, json_body=fields
    )
    return {
        "Id": result.get("id"),
        "success": bool(result.get("success", True)),
        "dataSource": "salesforce",
    }


def handle_write_pending_approval(args: dict, ctx: dict) -> dict:
    """Write one IR_Pending_Approval__c row (dual-auth request phase)."""
    principal_id = _require_principal(ctx)
    _require_writer_persona(ctx)
    record = args.get("record")
    if isinstance(record, dict) and record:
        fields = dict(record)
    else:
        fields = {
            "Plan_Hash__c": _require_nonempty_str(args, "plan_hash"),
            "Requested_By__c": _require_nonempty_str(args, "requested_by"),
            "Status__c": _require_nonempty_str(args, "status"),
            "Expires_At__c": _require_nonempty_str(args, "expires_at"),
        }
        senior = _optional_str(args, "senior_approver_id")
        if senior is not None:
            fields["Senior_Approver_Id__c"] = senior
    fields.setdefault("Requested_At__c", datetime.now(timezone.utc).isoformat())
    if MOCK_MODE:
        return {
            "Id": f"a0Y{uuid.uuid4().hex[:15].upper()}",
            "success": True,
            "dataSource": "mock",
        }
    result = _sf_call(
        "POST", "/sobjects/IR_Pending_Approval__c/", principal_id, json_body=fields
    )
    return {
        "Id": result.get("id"),
        "success": bool(result.get("success", True)),
        "dataSource": "salesforce",
    }


def handle_update_pending_approval(args: dict, ctx: dict) -> dict:
    """Update an IR_Pending_Approval__c row (dual-auth resolve phase)."""
    principal_id = _require_principal(ctx)
    _require_writer_persona(ctx)
    record_id = _optional_str(args, "id") or _optional_str(args, "record_id")
    if not record_id:
        raise McpValidationError("'id' (or 'record_id') required")
    incoming = args.get("fields")
    if isinstance(incoming, dict) and incoming:
        fields = dict(incoming)
    else:
        fields = {}
        status = _optional_str(args, "status")
        if status is not None:
            fields["Status__c"] = status
        senior = _optional_str(args, "senior_approver_id")
        if senior is not None:
            fields["Senior_Approver_Id__c"] = senior
        approved_at = _optional_str(args, "approved_at")
        if approved_at is not None:
            fields["Approved_At__c"] = approved_at
        if not fields:
            raise McpValidationError(
                "'fields' dict or one of status/senior_approver_id/"
                "approved_at required"
            )
    if MOCK_MODE:
        return {"id": record_id, "ok": True, "success": True, "dataSource": "mock"}
    _sf_call(
        "PATCH",
        f"/sobjects/IR_Pending_Approval__c/{record_id}",
        principal_id,
        json_body=fields,
    )
    return {
        "id": record_id,
        "ok": True,
        "success": True,
        "dataSource": "salesforce",
    }


# ---- Reads (read_household_summary / positions / briefs_with_exposure) ----

def _mock_household_summary(household_id: str) -> dict:
    return {
        "household_id": household_id,
        "household_name": "Patel Household",
        "primary_contact_id": "003000000000001AAC",
        "positions": [
            {"ticker": "NVDA", "pct_of_portfolio": 6.2,  "asset_class": "equity"},
            {"ticker": "AMD",  "pct_of_portfolio": 3.1,  "asset_class": "equity"},
            {"ticker": "CASH", "pct_of_portfolio": 20.0, "asset_class": "cash"},
        ],
        "recent_changes_pct": [{"ticker": "NVDA", "change_pct_30d": -2.1}],
        "next_events": [],
        "open_items": ["Schedule quarterly review"],
        "last_contact_at": "2026-03-01T10:00:00+00:00",
        "family_events": [],
    }


def _mock_household_positions(household_id: str) -> dict:
    return {
        "household_id": household_id,
        "positions": [
            {"ticker": "NVDA", "pct_of_portfolio": 6.2, "sector": "semis",
             "beta": 1.6, "ret_30d_pct": -2.1, "ret_ytd_pct": 12.3, "ret_1y_pct": 55.0},
            {"ticker": "MSFT", "pct_of_portfolio": 5.0, "sector": "software",
             "beta": 1.1, "ret_30d_pct": 0.8, "ret_ytd_pct": 6.2, "ret_1y_pct": 22.0},
            {"ticker": "XOM",  "pct_of_portfolio": 4.0, "sector": "energy",
             "beta": 0.9, "ret_30d_pct": 1.2, "ret_ytd_pct": 3.1, "ret_1y_pct": 8.0},
        ],
    }


def _mock_briefs_with_exposure(principal_id: str, ticker_filter) -> dict:
    briefs = [
        {
            "brief_id": "a0X_brief_NVDA_001",
            "ticker": "NVDA",
            "thesis": (
                "NVDA pre-earnings thesis: strong fundamentals offset "
                "by supply-chain risk."
            ),
            "sentiment_score": 0.15,
            "compliance_status": "ALLOW",
            "published_at": "2026-03-10T07:08:00+00:00",
            "author_agent_id": "research_orchestrator",
            "affected_clients": [
                {
                    "contact_id": "003_patel_001",
                    "household_id": "H001",
                    "pct_exposure": 6.2,
                    "last_contact_at": "2026-03-01T10:00:00+00:00",
                }
            ],
            "citations": ["chunk_nvda_001", "chunk_nvda_002"],
        }
    ]
    if ticker_filter:
        upper = ticker_filter.upper()
        briefs = [b for b in briefs if b["ticker"].upper() == upper]
    return {"briefs": briefs, "principal_id": principal_id}


def handle_read_household_summary(args: dict, ctx: dict) -> dict:
    """Read one household summary. MNPI-redacted on egress."""
    principal_id = _require_principal(ctx)
    household_id = _require_nonempty_str(args, "household_id")
    if MOCK_MODE:
        return _mock_household_summary(household_id)
    try:
        validate_identifier(household_id)
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc
    soql = (
        "SELECT Id, Name, "
        "(SELECT Id, Security__c, Portfolio_Pct__c, Asset_Class__c "
        "FROM Positions__r) "
        f"FROM Account WHERE Id = '{household_id}' LIMIT 1"
    )
    safe = ensure_read_only(soql)
    params = httpx.QueryParams({"q": safe})
    result = _sf_call("GET", f"/query/?{params}", principal_id)
    records = result.get("records", [])
    if not records:
        return {
            "household_id": household_id,
            "household_name": "",
            "positions": [],
            "dataSource": "salesforce",
        }
    acct = redact_record(records[0])
    positions = []
    for row in (acct.get("Positions__r", {}) or {}).get("records", []) or []:
        positions.append(
            {
                "ticker": row.get("Security__c"),
                "pct_of_portfolio": row.get("Portfolio_Pct__c"),
                "asset_class": row.get("Asset_Class__c", "equity"),
            }
        )
    return {
        "household_id": household_id,
        "household_name": acct.get("Name", ""),
        "positions": positions,
        "dataSource": "salesforce",
    }


def handle_read_household_positions(args: dict, ctx: dict) -> dict:
    """Read positions for a household. Percentages only (MNPI redacted)."""
    principal_id = _require_principal(ctx)
    household_id = _require_nonempty_str(args, "household_id")
    if MOCK_MODE:
        return _mock_household_positions(household_id)
    try:
        validate_identifier(household_id)
    except SoqlSafeError as exc:
        raise McpValidationError(str(exc)) from exc
    soql = (
        "SELECT Id, Security__c, Portfolio_Pct__c, Sector__c, Beta__c, "
        "Ret_30d_Pct__c, Ret_YTD_Pct__c, Ret_1y_Pct__c "
        f"FROM Position__c WHERE AccountId = '{household_id}'"
    )
    safe = ensure_read_only(soql)
    params = httpx.QueryParams({"q": safe})
    result = _sf_call("GET", f"/query/?{params}", principal_id)
    records = redact_records(result.get("records", []))
    positions = [
        {
            "ticker": r.get("Security__c"),
            "pct_of_portfolio": r.get("Portfolio_Pct__c"),
            "sector": r.get("Sector__c", "unknown"),
            "beta": r.get("Beta__c", 1.0),
            "ret_30d_pct": r.get("Ret_30d_Pct__c", 0.0),
            "ret_ytd_pct": r.get("Ret_YTD_Pct__c", 0.0),
            "ret_1y_pct": r.get("Ret_1y_Pct__c", 0.0),
        }
        for r in records
    ]
    return {
        "household_id": household_id,
        "positions": positions,
        "dataSource": "salesforce",
    }


def handle_read_research_briefs_with_exposure(args: dict, ctx: dict) -> dict:
    """DLM join: Research_Brief stream joined to Position stream + Contact.
    Returns briefs where the principal's book has exposure above the filter.
    """
    principal_id = _require_principal(ctx)
    skill_principal = _optional_str(args, "principal_id") or principal_id
    ticker_filter = _optional_str(args, "ticker_filter")
    min_pct = args.get("min_exposure_pct", 0.0)
    if not isinstance(min_pct, (int, float)) or min_pct < 0 or min_pct > 100:
        raise McpValidationError("'min_exposure_pct' must be a number in [0, 100]")
    if MOCK_MODE:
        return _mock_briefs_with_exposure(skill_principal, ticker_filter)

    where_parts = [f"p.pct_exposure >= {float(min_pct)}"]
    if ticker_filter:
        ticker_norm = ticker_filter.upper()
        if not _TICKER_RE.fullmatch(ticker_norm):
            raise McpValidationError("'ticker_filter' must match [A-Z.]+")
        where_parts.append(f"b.ticker = '{ticker_norm}'")
    sql = (
        "SELECT b.brief_id, b.ticker, b.thesis, b.sentiment_score, "
        "b.compliance_status, b.published_at, b.author_agent_id, "
        "p.contact_id, p.household_id, p.pct_exposure, p.last_contact_at "
        "FROM Research_Brief__dlm b "
        "JOIN Position__dlm p ON p.ticker = b.ticker "
        "WHERE " + " AND ".join(where_parts)
    )
    result = _sf_call(
        "POST", "/ssot/queryv2", principal_id, json_body={"sql": sql}
    )
    rows = redact_records(result.get("data", []))

    by_brief: dict = {}
    for row in rows:
        bid = row.get("brief_id")
        if not bid:
            continue
        brief = by_brief.setdefault(
            bid,
            {
                "brief_id": bid,
                "ticker": row.get("ticker"),
                "thesis": row.get("thesis", ""),
                "sentiment_score": row.get("sentiment_score", 0.0),
                "compliance_status": row.get("compliance_status", "ALLOW"),
                "published_at": row.get("published_at"),
                "author_agent_id": row.get("author_agent_id", ""),
                "affected_clients": [],
                "citations": [],
            },
        )
        if row.get("contact_id"):
            brief["affected_clients"].append(
                {
                    "contact_id": row.get("contact_id"),
                    "household_id": row.get("household_id"),
                    "pct_exposure": row.get("pct_exposure", 0.0),
                    "last_contact_at": row.get("last_contact_at"),
                }
            )
    return {"briefs": list(by_brief.values())}


# ---- Domain tool registrations (V3 wave 2) ------------------------------

server.register(
    ToolSpec(
        name="write_audit_log",
        description=(
            "Write one IR_Audit_Log__c row. Thin wrapper over create_object."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "record": {
                    "type": "object",
                    "description": "Full audit row payload (skill-shape).",
                },
                "principal_id": {"type": "string"},
                "action": {"type": "string"},
                "research_brief_id": {"type": "string"},
                "client_contact_id": {"type": "string"},
                "gate_trace": {"type": "array"},
                "approved_by": {"type": "string"},
                "dual_approver": {"type": "string"},
                "mulesoft_reference": {"type": "string"},
                "payload": {"type": "object"},
            },
        },
    ),
    handle_write_audit_log,
)

server.register(
    ToolSpec(
        name="write_research_brief",
        description=(
            "Write one Research_Brief__c row. Auto-populates Published_At__c."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "record": {"type": "object"},
                "ticker": {"type": "string"},
                "thesis": {"type": "string"},
                "sentiment_score": {"type": "number"},
                "risk_factors": {"type": "array"},
                "compliance_status": {"type": "string"},
                "mnpi_cleared": {"type": "boolean"},
                "rm_consumable": {"type": "boolean"},
                "client_demand": {"type": "boolean"},
                "source_chunk_ids": {"type": "array"},
                "author_agent_id": {"type": "string"},
            },
        },
    ),
    handle_write_research_brief,
)

server.register(
    ToolSpec(
        name="write_pending_approval",
        description=(
            "Write one IR_Pending_Approval__c row (dual-auth request phase)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "record": {"type": "object"},
                "plan_hash": {"type": "string"},
                "requested_by": {"type": "string"},
                "senior_approver_id": {"type": "string"},
                "status": {"type": "string"},
                "expires_at": {"type": "string"},
            },
        },
    ),
    handle_write_pending_approval,
)

server.register(
    ToolSpec(
        name="update_pending_approval",
        description=(
            "Update an IR_Pending_Approval__c row (dual-auth resolve phase)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "record_id": {"type": "string"},
                "fields": {"type": "object"},
                "status": {"type": "string"},
                "senior_approver_id": {"type": "string"},
                "approved_at": {"type": "string"},
            },
        },
    ),
    handle_update_pending_approval,
)

server.register(
    ToolSpec(
        name="read_household_summary",
        description=(
            "Household summary for meeting prep. MNPI-redacted on egress."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "household_id": {"type": "string"},
                "principal_id": {"type": "string"},
                "mnpi_filtered": {"type": "boolean"},
            },
            "required": ["household_id"],
        },
    ),
    handle_read_household_summary,
)

server.register(
    ToolSpec(
        name="read_household_positions",
        description=(
            "Positions for a household. Percentage-only (MNPI redacted)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "household_id": {"type": "string"},
                "principal_id": {"type": "string"},
                "mnpi_filtered": {"type": "boolean"},
            },
            "required": ["household_id"],
        },
    ),
    handle_read_household_positions,
)

server.register(
    ToolSpec(
        name="read_research_briefs_with_exposure",
        description=(
            "DLM join of research briefs with the principal's exposed book."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "principal_id": {"type": "string"},
                "ticker_filter": {"type": "string"},
                "min_exposure_pct": {"type": "number"},
                "published_since": {"type": "string"},
            },
        },
    ),
    handle_read_research_briefs_with_exposure,
)


def lambda_handler(event, context):
    return server.handle(event, context)
