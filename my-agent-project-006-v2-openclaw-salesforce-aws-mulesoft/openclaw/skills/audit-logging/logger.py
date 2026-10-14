"""
Audit Logger — dual-write to Salesforce IR_Audit_Log__c and Langfuse.

Implements the audit logging described in audit-logging/SKILL.md:
  - Every agent action writes to BOTH Salesforce (regulatory) and Langfuse (engineering)
  - Shared trace_id links both systems
  - Graceful failure handling — log warning, don't crash pipeline

Architecture rules:
  - No credentials in code — all via function parameters
  - No LLM imports — pure Salesforce REST API + Langfuse SDK
  - Field truncation to SF limits
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger("audit-logging")

SF_API_VERSION = "v66.0"

# MNPI fields that must be redacted from Langfuse traces
_TRACE_REDACT_FIELDS = {
    "FinServ__Shares__c", "FinServ__MarketValue__c", "FinServ__Price__c",
    "Amount", "Balance__c", "Trade_Amount__c", "Wire_Amount__c",
    "Position_Size__c", "accessToken", "access_token", "SF_ACCESS_TOKEN",
    "password", "secret", "apiKey", "api_key",
}


def _redact_for_trace(data: dict | str) -> dict | str:
    """Redact MNPI and credential fields from data before sending to Langfuse."""
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return data
    redacted = {}
    for k, v in data.items():
        if k in _TRACE_REDACT_FIELDS:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = _redact_for_trace(v)
        elif isinstance(v, list):
            redacted[k] = [_redact_for_trace(item) if isinstance(item, dict) else item for item in v]
        else:
            redacted[k] = v
    return redacted

# Salesforce field length limits
_FIELD_LIMITS: dict[str, int] = {
    "Query__c": 255,
    "Decision_Rationale__c": 255,
    "Data_Sources_Used__c": 255,
    "Action__c": 255,
    "Analyst__c": 255,
    "Pipeline_Stage__c": 255,
    "Compliance_Status__c": 50,
    "Trace_Id__c": 255,
}


def _truncate(value: str, max_len: int) -> str:
    """Truncate a string to max_len, appending '...' if truncated."""
    if not value:
        return ""
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def _now_iso() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def log_audit(
    action: str,
    stage: int,
    detail: str,
    query: str,
    analyst: str,
    sf_instance_url: str,
    sf_access_token: str,
    langfuse_trace: Any,
    compliance_status: str = "PASS",
    sources: str = "",
    mnpi_flag: bool = False,
    trace_id: str = "",
) -> dict:
    """
    Write an audit record to Salesforce IR_Audit_Log__c AND Langfuse.

    Parameters
    ----------
    action : str
        Action type (QUERY, RESEARCH_BRIEF, COMPLIANCE_CHECK, etc.)
    stage : int
        Pipeline stage number (1-23).
    detail : str
        Decision rationale / description of the action.
    query : str
        Original user query.
    analyst : str
        Analyst name from session.
    sf_instance_url : str
        Salesforce instance URL (no trailing slash).
    sf_access_token : str
        Salesforce OAuth bearer token.
    langfuse_trace : Any
        Langfuse trace object (must have .event() and .id).
    compliance_status : str
        "PASS" or "FAIL".
    sources : str
        Comma-separated list of data sources used.
    mnpi_flag : bool
        True if the action touched MNPI data.
    trace_id : str
        Override trace ID. Falls back to langfuse_trace.id or "unknown".

    Returns
    -------
    dict
        {"sf_id": "...", "langfuse_event": True, "success": True}
        or error details on failure.
    """
    result: dict[str, Any] = {"sf_id": None, "langfuse_event": False, "success": False}

    # ── Resolve trace ID ────────────────────────────────────────────
    resolved_trace_id = trace_id
    if not resolved_trace_id:
        try:
            resolved_trace_id = str(langfuse_trace.id) if hasattr(langfuse_trace, "id") else "unknown"
        except Exception:
            resolved_trace_id = "unknown"

    # ── 1. Write to Langfuse ────────────────────────────────────────
    try:
        langfuse_trace.event(
            name=f"audit-stage-{stage}",
            metadata=_redact_for_trace({
                "action": action,
                "stage": stage,
                "detail": _truncate(detail, 500),
                "compliance": compliance_status,
                "mnpi_flag": mnpi_flag,
                "sources": sources,
            }),
        )
        result["langfuse_event"] = True
    except Exception as exc:
        logger.warning("Langfuse audit event failed at stage %d: %s", stage, exc)

    # ── 2. Write to Salesforce IR_Audit_Log__c ──────────────────────
    record = {
        "Agent__c": "OpenClaw-IR",
        "Action__c": _truncate(action, _FIELD_LIMITS["Action__c"]),
        "Query__c": _truncate(query, _FIELD_LIMITS["Query__c"]),
        "Analyst__c": _truncate(analyst, _FIELD_LIMITS["Analyst__c"]),
        "Timestamp__c": _now_iso(),
        "Data_Sources_Used__c": _truncate(sources, _FIELD_LIMITS["Data_Sources_Used__c"]),
        "Pipeline_Stage__c": _truncate(f"Stage {stage}", _FIELD_LIMITS["Pipeline_Stage__c"]),
        "Decision_Rationale__c": _truncate(detail, _FIELD_LIMITS["Decision_Rationale__c"]),
        "Trace_Id__c": _truncate(resolved_trace_id, _FIELD_LIMITS["Trace_Id__c"]),
        "Compliance_Status__c": _truncate(compliance_status, _FIELD_LIMITS["Compliance_Status__c"]),
        "MNPI_Flag__c": mnpi_flag,
    }

    url = f"{sf_instance_url}/services/data/{SF_API_VERSION}/sobjects/IR_Audit_Log__c"
    try:
        resp = requests.post(
            url,
            json=record,
            headers={
                "Authorization": f"Bearer {sf_access_token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        sf_result = resp.json()
        result["sf_id"] = sf_result.get("id")
        result["success"] = True
    except requests.RequestException as exc:
        logger.warning(
            "SF audit log write failed at stage %d: %s", stage, exc,
        )
        result["sf_error"] = str(exc)
        # Langfuse write may have succeeded — partial success
        if result["langfuse_event"]:
            result["success"] = True
            result["sf_id"] = None

    return result


__all__ = ["log_audit"]
