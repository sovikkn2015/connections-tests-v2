"""HITL Decision Bridge — REST fallback for `hitl.decision` messages.

Purpose
-------
The HitlPanel frontend prefers the OpenClaw WebSocket for approver decisions.
When the WebSocket is unavailable (Lambda cold start, network blip, proxy
failure), `sendHitlDecision` falls back to POSTing this Lambda at
`/prod/hitl/decision`. Without this route, approvals fail silently.

Wire contract (rule 22: raw tokens never cross the wire — only the 16-char
SHA-256 prefix `token_hash`)::

    POST /prod/hitl/decision
    {
      "type": "hitl.decision",
      "token_hash": "<16 hex chars, matches hitl.pending event>",
      "decision": "APPROVED" | "REJECTED",
      "approver_note": "<optional, <=500 chars>"
    }

Return
------
202 on happy path (we accept and audit — see the DynamoDB TODO below for why
this is not 200). 400 on validation. 405 on wrong method.

DynamoDB TODO
-------------
This Phase 6 stub does NOT reconcile the token_hash to a pending approval
record. Pending approvals live in-memory inside the agent container that
emitted the `hitl.pending` event, and that container is not this Lambda.

For production hardening we MUST:
  1. Persist pending approvals to a DynamoDB table keyed by token_hash
     at the moment `hitl.pending` is emitted.
  2. Look them up here to recover plan_hash / action / client_id.
  3. Verify the HMAC signature of the decision against the stored signing
     key before writing TRADE_SUBMITTED / WIRE_INITIATED.
  4. Republish a `hitl.completed` event so any WebSocket-connected panel
     still gets the terminal state.

Until that lands, this Lambda writes a `HITL_DECISION_RECEIVED` audit
record (with Action__c = HITL_DECISION_RECEIVED) to `IR_Audit_Log__c` and
returns 202 Accepted. The WebSocket path remains the primary route; this
Lambda is the belt to that WebSocket's suspenders.

Security model (rule 22)
------------------------
- Never logs the raw token_hash. Only the first 8 hex chars (the same
  forensic prefix the OpenClaw gateway uses) are logged for correlation.
- Never logs the approver_note contents (may contain client PII).
- Does not attempt to verify the HMAC signing key here — that's gateway
  responsibility. We only verify payload SHAPE.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import urllib.error
import urllib.request


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


# --- Env / constants --------------------------------------------------------

CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*")
MULESOFT_ACTIONS_URL = os.environ.get("MULESOFT_ACTIONS_URL", "")
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "")
SF_ACCESS_TOKEN = os.environ.get("SF_ACCESS_TOKEN", "")
HITL_SECRET_NAME = os.environ.get("HITL_SECRET_NAME", "/006-v2/hitl/signing-key")
AUDIT_ACTION = "HITL_DECISION_RECEIVED"

_TOKEN_HASH_RE = re.compile(r"^[0-9a-f]{8,64}$")
_VALID_DECISIONS = {"APPROVED", "REJECTED"}


# --- Response helpers -------------------------------------------------------


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ALLOW_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _resp(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": _headers(), "body": json.dumps(body)}


# --- Payload validation -----------------------------------------------------


def _validate(payload: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, error_message). Rule 22: never include raw tokens in the
    error message."""
    if payload.get("type") != "hitl.decision":
        return False, "type must be 'hitl.decision'"

    token_hash = payload.get("token_hash")
    if not isinstance(token_hash, str) or not _TOKEN_HASH_RE.match(token_hash):
        return False, "token_hash must be 8-64 lowercase hex chars"

    decision = payload.get("decision")
    if decision not in _VALID_DECISIONS:
        return False, f"decision must be one of {sorted(_VALID_DECISIONS)}"

    note = payload.get("approver_note")
    if note is not None:
        if not isinstance(note, str):
            return False, "approver_note must be a string"
        if len(note) > 500:
            return False, "approver_note must be <=500 chars"

    return True, ""


# --- Audit write ------------------------------------------------------------


def _write_audit(token_hash: str, decision: str, note: str | None) -> dict[str, Any]:
    """Write a minimal HITL_DECISION_RECEIVED record to IR_Audit_Log__c.

    Uses the same Salesforce access token that the CRM MCP Lambda uses,
    sourced from SF_ACCESS_TOKEN / SF_INSTANCE_URL env vars. On any failure
    we log the cause (without PII) and return a stub dict — the approver's
    UI still succeeds so we don't black-hole the click.
    """
    if (not SF_INSTANCE_URL
            or not SF_ACCESS_TOKEN
            or SF_INSTANCE_URL.startswith("PLACEHOLDER")
            or SF_ACCESS_TOKEN.startswith("PLACEHOLDER")
            or not SF_INSTANCE_URL.lower().startswith(("http://", "https://"))):
        log.warning(
            "SF_INSTANCE_URL / SF_ACCESS_TOKEN missing or placeholder; "
            "skipping audit write (token_hash_prefix=%s decision=%s)",
            token_hash[:8],
            decision,
        )
        return {"audit_written": False, "reason": "sf_creds_missing"}

    url = f"{SF_INSTANCE_URL.rstrip('/')}/services/data/v60.0/sobjects/IR_Audit_Log__c"
    record = {
        "Action__c": AUDIT_ACTION,
        "Status__c": decision,
        "Approval_Token_Hash__c": token_hash,
        "Approver_Note__c": (note or "")[:255],
        "Logged_At__c": int(time.time()),
    }
    body = json.dumps(record).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {SF_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body_bytes = resp.read()
            payload = json.loads(body_bytes.decode("utf-8") or "{}")
            return {"audit_written": True, "audit_log_id": payload.get("id")}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        log.error(
            "audit write failed: HTTP %s (token_hash_prefix=%s) body=%s",
            exc.code,
            token_hash[:8],
            err_body[:200],
        )
        return {"audit_written": False, "reason": f"sf_http_{exc.code}"}
    except Exception as exc:  # noqa: BLE001 — we must never crash the fallback
        log.error(
            "audit write error (token_hash_prefix=%s): %s",
            token_hash[:8],
            exc,
        )
        return {"audit_written": False, "reason": "sf_unreachable"}


# --- Lambda entry point -----------------------------------------------------


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """API Gateway proxy handler for POST /prod/hitl/decision."""
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "POST")
    ).upper()

    if method == "OPTIONS":
        return _resp(200, {})

    if method != "POST":
        return _resp(405, {"error": "method_not_allowed"})

    raw_body = event.get("body") or "{}"
    try:
        payload = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError:
        return _resp(400, {"error": "invalid_json"})

    if not isinstance(payload, dict):
        return _resp(400, {"error": "body_must_be_object"})

    ok, err = _validate(payload)
    if not ok:
        return _resp(400, {"error": err})

    token_hash: str = payload["token_hash"]
    decision: str = payload["decision"]
    note = payload.get("approver_note")

    log.info(
        "HITL decision received token_hash_prefix=%s decision=%s note_len=%s",
        token_hash[:8],
        decision,
        len(note) if isinstance(note, str) else 0,
    )

    audit_result = _write_audit(token_hash, decision, note)

    return _resp(
        202,
        {
            "accepted": True,
            "decision": decision,
            "token_hash_prefix": token_hash[:8],
            "audit": audit_result,
            "note": "Phase 6 stub - pending approval reconciliation requires DynamoDB. See module docstring.",
        },
    )
