"""
Salesforce CRM MCP Server — Lambda handler.
Tools: run_soql_query, get_record, search_records, describe_object, list_custom_objects.
Uses SF REST API (credentials from SF_INSTANCE_URL and SF_ACCESS_TOKEN env vars).

MNPI fields are redacted from ALL responses (FINRA requirement).
"""

import json
import os
from urllib.parse import quote_plus

from mcp_protocol import McpServer

import requests

# ---------------------------------------------------------------------------
# Constants — fail fast if credentials are missing
# ---------------------------------------------------------------------------
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL")
SF_ACCESS_TOKEN = os.environ.get("SF_ACCESS_TOKEN")
if not SF_INSTANCE_URL:
    raise RuntimeError("SF_INSTANCE_URL environment variable is required")
if not SF_ACCESS_TOKEN:
    raise RuntimeError("SF_ACCESS_TOKEN environment variable is required")

SF_API_VERSION = "v60.0"
SF_BASE = f"{SF_INSTANCE_URL}/services/data/{SF_API_VERSION}"

# ---------------------------------------------------------------------------
# MNPI fields — NEVER returned to callers (FINRA requirement)
# ---------------------------------------------------------------------------
MNPI_FIELDS = frozenset({
    "FinServ__Shares__c",
    "FinServ__MarketValue__c",
    "FinServ__Price__c",
    "Trade_Amount__c",
    "Wire_Amount__c",
    "SSN__c",
    "Tax_ID__c",
})




def _sf_headers() -> dict:
    """Authorization headers for Salesforce REST API."""
    return {
        "Authorization": f"Bearer {SF_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _redact_mnpi(data):
    """
    Recursively redact MNPI fields from records before returning.
    Works on dicts, lists of dicts, and nested structures.
    This is a FINRA requirement — MNPI fields must NEVER reach the caller.
    """
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if key in MNPI_FIELDS:
                redacted[key] = "[REDACTED-MNPI]"
            else:
                redacted[key] = _redact_mnpi(value)
        return redacted
    if isinstance(data, list):
        return [_redact_mnpi(item) for item in data]
    return data


class SalesforceApiError(Exception):
    """Raised when Salesforce REST API returns a non-2xx response."""

    def __init__(self, status_code: int, sf_errors: list[dict]):
        self.status_code = status_code
        self.sf_errors = sf_errors
        # Salesforce error responses are a list of {errorCode, message}
        first = sf_errors[0] if sf_errors else {}
        self.error_code = first.get("errorCode", "UNKNOWN")
        self.message = first.get("message", "Unknown Salesforce error")
        super().__init__(f"SF {status_code}: [{self.error_code}] {self.message}")


def _sf_request(method: str, url: str, **kwargs) -> dict:
    """Make a request to Salesforce REST API and return parsed JSON.

    Raises SalesforceApiError with structured error info on non-2xx responses
    so callers can handle specific SF error codes (NOT_FOUND, INVALID_TYPE, etc.)
    instead of getting a generic requests.HTTPError.
    """
    kwargs.setdefault("timeout", 15)
    kwargs.setdefault("headers", _sf_headers())
    resp = requests.request(method, url, **kwargs)
    if not resp.ok:
        try:
            sf_errors = resp.json()
            if isinstance(sf_errors, dict):
                sf_errors = [sf_errors]
        except Exception:
            sf_errors = [{"errorCode": f"HTTP_{resp.status_code}", "message": resp.text[:500]}]
        raise SalesforceApiError(resp.status_code, sf_errors)
    return resp.json()


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
def handle_run_soql_query(params: dict) -> dict:
    """Execute a SOQL query and return redacted records.

    Gracefully handles missing objects (e.g. FinServ__* when FSC is not installed)
    by returning an empty result set with an error field instead of raising.
    """
    query = params["query"]
    url = f"{SF_BASE}/query?q={quote_plus(query)}"
    try:
        data = _sf_request("GET", url)
    except SalesforceApiError as exc:
        # Return structured error so callers (pipeline, agent) can handle gracefully
        return {
            "totalSize": 0,
            "done": True,
            "records": [],
            "error": {
                "errorCode": exc.error_code,
                "message": exc.message,
                "statusCode": exc.status_code,
            },
        }
    records = data.get("records", [])
    return {
        "totalSize": data.get("totalSize", len(records)),
        "done": data.get("done", True),
        "records": _redact_mnpi(records),
    }



def handle_get_record(params: dict) -> dict:
    """Fetch a single record by object type and ID, with MNPI redaction."""
    object_type = params["object_type"]
    record_id = params["record_id"]
    url = f"{SF_BASE}/sobjects/{object_type}/{record_id}"
    try:
        data = _sf_request("GET", url)
    except SalesforceApiError as exc:
        return {
            "error": {
                "errorCode": exc.error_code,
                "message": exc.message,
                "statusCode": exc.status_code,
            },
        }
    return _redact_mnpi(data)


def handle_search_records(params: dict) -> dict:
    """Search records using SOSL."""
    search_term = params["search_term"]
    object_type = params.get("object_type")
    sosl = f"FIND {{{search_term}}}"
    if object_type:
        sosl += f" IN ALL FIELDS RETURNING {object_type}"
    url = f"{SF_BASE}/search?q={quote_plus(sosl)}"
    try:
        data = _sf_request("GET", url)
    except SalesforceApiError as exc:
        return {
            "searchRecords": [],
            "error": {
                "errorCode": exc.error_code,
                "message": exc.message,
                "statusCode": exc.status_code,
            },
        }
    results = data.get("searchRecords", [])
    return {"searchRecords": _redact_mnpi(results)}


def handle_describe_object(params: dict) -> dict:
    """Describe a Salesforce object — returns field names and types."""
    object_type = params["object_type"]
    url = f"{SF_BASE}/sobjects/{object_type}/describe"
    try:
        data = _sf_request("GET", url)
    except SalesforceApiError as exc:
        return {
            "objectType": object_type,
            "fieldCount": 0,
            "fields": [],
            "error": {
                "errorCode": exc.error_code,
                "message": exc.message,
                "statusCode": exc.status_code,
            },
        }
    fields = [
        {"name": f["name"], "type": f["type"], "label": f["label"]}
        for f in data.get("fields", [])
    ]
    return {
        "objectType": object_type,
        "fieldCount": len(fields),
        "fields": fields,
    }


def handle_list_custom_objects(params: dict) -> dict:
    """Return the list of FSI custom objects available in this org.

    Dynamically checks FinServ objects (managed package, requires FSC license).
    IR_* custom objects are always listed since they're deployed via metadata.
    """
    # IR_* objects are always present (deployed via sf project deploy)
    objects = [
        "IR_Research_Note__c",
        "IR_Coverage__c",
        "IR_Watchlist__c",
        "IR_Company__c",
        "IR_Audit_Log__c",
    ]
    # FinServ objects only exist if FSC is installed — probe before listing
    for fsc_obj in ("FinServ__FinancialAccount__c", "FinServ__FinancialHolding__c"):
        try:
            _sf_request("GET", f"{SF_BASE}/sobjects/{fsc_obj}/describe")
            objects.append(fsc_obj)
        except SalesforceApiError:
            pass  # FSC not installed — omit from list
    return {"customObjects": objects}



# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------
TOOLS = {
    "run_soql_query": {
        "description": "Execute a SOQL query against Salesforce. Returns records with MNPI fields redacted.",
        "properties": {
            "query": {"type": "string", "description": "SOQL query string (e.g. SELECT Id, Name FROM Account LIMIT 10)"},
        },
        "required": ["query"],
    },
    "get_record": {
        "description": "Fetch a single Salesforce record by object type and record ID. MNPI fields are redacted.",
        "properties": {
            "object_type": {"type": "string", "description": "Salesforce object API name (e.g. Account, FinServ__FinancialAccount__c)"},
            "record_id": {"type": "string", "description": "Salesforce record ID (18-char)"},
        },
        "required": ["object_type", "record_id"],
    },
    "search_records": {
        "description": "Search Salesforce records using SOSL full-text search.",
        "properties": {
            "search_term": {"type": "string", "description": "Text to search for across records"},
            "object_type": {"type": "string", "description": "Optional: limit search to a specific object type"},
        },
        "required": ["search_term"],
    },
    "describe_object": {
        "description": "Describe a Salesforce object — returns field names, types, and labels. Useful for constructing SOQL queries.",
        "properties": {
            "object_type": {"type": "string", "description": "Salesforce object API name (e.g. IR_Research_Note__c)"},
        },
        "required": ["object_type"],
    },
    "list_custom_objects": {
        "description": "List FSI custom objects available in this Salesforce org (IR_*, FinServ__*).",
        "properties": {},
        "required": [],
    },
}

HANDLERS = {
    "run_soql_query": handle_run_soql_query,
    "get_record": handle_get_record,
    "search_records": handle_search_records,
    "describe_object": handle_describe_object,
    "list_custom_objects": handle_list_custom_objects,
}

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = McpServer(
    name="salesforce-crm",
    version="1.0.0",
    description="Salesforce CRM data — SOQL queries, record access, search, object metadata. MNPI fields redacted.",
)

for tool_name, schema in TOOLS.items():
    server.register_tool(tool_name, schema, HANDLERS[tool_name])


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    return server.handle(event)
