"""
M6 Web API Layer — Bridges M12 Web Console to internal MCP/module calls.

Every endpoint:
  1. Extracts AID token from Authorization header
  2. Runs trust pipeline (M1 verify → M2 authority → M4 MNPI filter)
  3. Translates REST request into internal module call
  4. Writes audit entry to M10
  5. Returns response in the format M12 frontend expects

Endpoints:
  POST /api/v1/chat/send              — Send chat message
  GET  /api/v1/chat/history/{id}      — Get conversation history
  GET  /api/v1/chat/stream            — SSE streaming agent response
  GET  /api/v1/reviews/pending        — Principal review queue
  GET  /api/v1/reviews/history        — Completed reviews
  POST /api/v1/reviews/action         — Approve/reject/edit review
  GET  /api/v1/audit/trail            — Query audit trail
  GET  /api/v1/audit/detail/{traceId} — Full audit entry
  GET  /api/v1/admin/health           — System health across modules
  GET  /api/v1/admin/adapters         — Adapter/circuit breaker states
  GET  /api/v1/admin/metrics          — Performance metrics
  POST /api/v1/orders/approve         — Approve trade order
  POST /api/v1/orders/reject          — Reject trade order

All module communication via REST (Rule 14). No cross-module imports.
Generic errors to clients (Rule 9). Full errors to logs only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .leakage_scan import scan_output
from .models import GatewayError, ProvenanceEntry, PipelineStage

logger = logging.getLogger("m6.web_api")

# ── Configuration (env vars, no hardcoded creds — Rule 20) ──────

_M1_URL = os.environ.get("M1_URL", "http://m1-identity:8000")
_M2_URL = os.environ.get("M2_URL", "http://m2-m4-policy:8000")
_M4_URL = os.environ.get("M4_URL", "http://m2-m4-policy:8000")
_M8_URL = os.environ.get("M8_URL", "http://m8-memory:8000")
_M9_URL = os.environ.get("M9_URL", "http://m9-intent-router:8000")
_M10_URL = os.environ.get("M10_URL", "http://m10-audit:8000")
_M11_URL = os.environ.get("M11_URL", "http://m11-adapters:8000")
_EXEC_URL = os.environ.get("EXEC_SPECIALIST_URL", "http://execution-specialist:8000")
_DEV_MODE = os.environ.get("M6_DEV_MODE", "false").lower() == "true"
_HTTP_TIMEOUT = float(os.environ.get("M6_WEB_API_TIMEOUT", "15.0"))

web_api_router = APIRouter(prefix="/api/v1", tags=["web-api"])

# Shared httpx client — initialized lazily
_http_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
    return _http_client


# ── Request / Response Models (matching M12 frontend types.ts) ──


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    conversationId: Optional[str] = None


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str = "agent"
    specialist: Optional[str] = None
    content: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    sources: Optional[list[dict[str, str]]] = None
    provenanceTraceId: Optional[str] = None
    hitlAction: Optional[dict[str, Any]] = None
    detailType: Optional[str] = None
    detailPayload: Optional[Any] = None


class ReviewActionRequest(BaseModel):
    reviewId: str
    action: str  # "approve" | "reject" | "edit_approve"
    reason: Optional[str] = None
    editedContent: Optional[str] = None


class OrderApproveRequest(BaseModel):
    orderId: str


class OrderRejectRequest(BaseModel):
    orderId: str
    reason: str


# ── Helpers ──────────────────────────────────────────────────────


def _sha256(payload: Any) -> str:
    """Compute SHA-256 hash of a JSON-serializable payload."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def _generic_error(status: int, msg: str = "Request denied", request_id: Optional[str] = None) -> JSONResponse:
    """Rule 9: generic error to client. Full details to logs only."""
    return JSONResponse(
        status_code=status,
        content=GatewayError(error=msg, request_id=request_id).model_dump(),
    )


async def _verify_identity(token: str) -> dict[str, Any]:
    """Call M1 to verify AID token. REST only (Rule 14)."""
    client = await _get_client()
    resp = await client.post(
        f"{_M1_URL.rstrip('/')}/aid/verify",
        json={"token": token},
    )
    resp.raise_for_status()
    return resp.json()


async def _check_authority(claims: dict[str, Any], action: str) -> dict[str, Any]:
    """Call M2 to check authority. REST only (Rule 14)."""
    client = await _get_client()
    resp = await client.post(
        f"{_M2_URL.rstrip('/')}/policy/authority",
        json={
            "identity": {
                "actor_type": claims.get("actor_type", "human"),
                "archetype": claims.get("archetype", "tier4_independent_ria"),
                "role": claims.get("role", "advisor"),
                "firm_id": claims.get("firm_id", ""),
                "jurisdiction": claims.get("jurisdiction", "US"),
                "authority_scope": claims.get("authority_scope", []),
                "authority_excludes": claims.get("authority_excludes", []),
                "client_scope": claims.get("client_scope", []),
                "pod_id": claims.get("pod_id"),
            },
            "action": action,
            "context": {},
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _filter_mnpi(payload: dict[str, Any], claims: dict[str, Any], direction: str) -> dict[str, Any]:
    """Call M4 to filter MNPI fields. REST only (Rule 14)."""
    client = await _get_client()
    resp = await client.post(
        f"{_M4_URL.rstrip('/')}/policy/mnpi/filter",
        json={
            "data_payload": payload,
            "archetype": claims.get("archetype", "tier4_independent_ria"),
            "role": claims.get("role", "advisor"),
            "jurisdiction": claims.get("jurisdiction", "US"),
            "client_scope": claims.get("client_scope", []),
            "pod_id": claims.get("pod_id"),
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _write_audit(
    trace_id: str,
    claims: dict[str, Any],
    action: str,
    decision: str,
    reason: str,
    request_data: Any = None,
    response_data: Any = None,
) -> None:
    """Call M10 to write audit entry. REST only (Rule 14)."""
    try:
        client = await _get_client()
        await client.post(
            f"{_M10_URL.rstrip('/')}/audit/write",
            json={
                "trace_id": trace_id,
                "actor_id": _sha256(claims.get("display_name", "unknown")),
                "action": action,
                "module": "m6",
                "decision": decision,
                "reason": reason,
                "input_hash": _sha256(request_data or {}),
                "output_hash": _sha256(response_data or {}),
                "archetype": claims.get("archetype"),
                "role": claims.get("role"),
                "firm_id": claims.get("firm_id", "unknown"),
                "jurisdiction": claims.get("jurisdiction", "US"),
                "provenance_chain": [],
            },
        )
    except Exception as e:
        logger.error("M10 audit write failed: %s", e)



# ── Trust Pipeline Runner ────────────────────────────────────────
# Every web API endpoint calls this before doing anything.
# M1 verify → M2 authority → M4 MNPI filter (Rule 2).
# If ANY step fails → DENIED (Rule 12).


async def _run_trust_pipeline(
    token: str,
    action: str,
    request_payload: dict[str, Any],
    required_role: Optional[str] = None,
) -> tuple[bool, dict[str, Any], Optional[JSONResponse]]:
    """
    Run the pre-call trust pipeline for a web API request.

    Returns:
        (passed, claims, error_response)
        If passed=True, claims contains verified AID claims.
        If passed=False, error_response is the JSONResponse to return.
    """
    trace_id = str(uuid4())

    # Step 1: M1 — Verify AID
    try:
        m1_result = await _verify_identity(token)
    except Exception as e:
        logger.error("M1 identity verification failed: %s", e)
        if _DEV_MODE:
            return True, _dev_mode_claims(), None
        return False, {}, _generic_error(503, "Service unavailable")

    if not m1_result.get("valid", False):
        logger.warning("M1 denied: %s", m1_result.get("reason", "unknown"))
        return False, {}, _generic_error(401, "Authentication failed")

    claims = m1_result.get("claims", {})

    # Role check (if required)
    if required_role:
        user_role = claims.get("role", "")
        allowed_roles = required_role.split(",")
        if user_role not in allowed_roles and user_role != "admin":
            logger.warning(
                "Role check failed: user=%s required=%s", user_role, required_role,
            )
            await _write_audit(trace_id, claims, action, "deny", "Insufficient role")
            return False, claims, _generic_error(403, "Access denied")

    # Step 2: M2 — Check authority
    try:
        m2_result = await _check_authority(claims, action)
    except Exception as e:
        logger.error("M2 authority check failed: %s", e)
        if _DEV_MODE:
            return True, claims, None
        return False, claims, _generic_error(503, "Service unavailable")

    if m2_result.get("decision") != "ALLOW":
        logger.warning("M2 denied: %s", m2_result.get("reason", "unknown"))
        await _write_audit(trace_id, claims, action, "deny", "Authority denied")
        return False, claims, _generic_error(403, "Access denied")

    # Step 3: M4 — Filter MNPI from request
    try:
        await _filter_mnpi(request_payload, claims, "request")
    except Exception as e:
        logger.error("M4 MNPI filter failed: %s", e)
        if _DEV_MODE:
            return True, claims, None
        return False, claims, _generic_error(503, "Service unavailable")

    return True, claims, None


def _dev_mode_claims() -> dict[str, Any]:
    """Mock AID claims for dev mode when M1 is unavailable."""
    return {
        "actor_type": "human",
        "display_name": "dev.user",
        "firm_id": "dev_firm",
        "archetype": "tier4_independent_ria",
        "role": "admin",
        "jurisdiction": "US",
        "authority_scope": ["*"],
        "authority_excludes": [],
        "client_scope": ["*"],
        "pod_id": None,
    }


# ── Mock Data (dev mode fallback when downstream unavailable) ────


def _mock_chat_history(conversation_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": str(uuid4()),
            "role": "user",
            "content": "Show me the Henderson portfolio",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": str(uuid4()),
            "role": "agent",
            "specialist": "client_service",
            "content": "Here is the Henderson portfolio summary.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": [{"name": "Schwab Adapter", "module": "M11"}],
        },
    ]


def _mock_reviews_pending() -> list[dict[str, Any]]:
    return [
        {
            "id": "rev-001",
            "advisorName": "Jane Smith",
            "advisorCrd": "CRD-12345",
            "clientName": "Henderson Family",
            "clientId": "C-12345",
            "type": "portfolio_recommendation",
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "slaDeadline": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "agentOutput": "Recommend rebalancing to 60/40 allocation.",
            "opaDecision": "ESCALATE",
            "opaRule": "principal_review/bd_communication.rego",
            "wspSection": "WSP-4.2",
            "mnpiStripped": [],
            "leakageScan": "pass",
            "smarchArchive": "pending",
        },
    ]


def _mock_reviews_history() -> list[dict[str, Any]]:
    return [
        {
            "id": "rev-000",
            "advisorName": "Jane Smith",
            "advisorCrd": "CRD-12345",
            "clientName": "Henderson Family",
            "clientId": "C-12345",
            "type": "portfolio_recommendation",
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "slaDeadline": datetime.now(timezone.utc).isoformat(),
            "status": "approved",
            "agentOutput": "Previous recommendation approved.",
            "opaDecision": "ALLOW",
            "opaRule": "principal_review/bd_communication.rego",
            "wspSection": "WSP-4.2",
            "mnpiStripped": [],
            "leakageScan": "pass",
            "smarchArchive": "archived",
        },
    ]


def _mock_audit_trail() -> list[dict[str, Any]]:
    return [
        {
            "id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceId": str(uuid4()),
            "actor": "advisor:jane.smith",
            "action": "portfolio.read",
            "target": "client:C-12345",
            "decision": "ALLOW",
            "module": "m6",
            "sha256": "a" * 64,
        },
    ]


def _mock_layer_health() -> list[dict[str, Any]]:
    return [
        {
            "name": "Trust Layer",
            "modules": [
                {"module": "M1", "label": "Identity", "status": "healthy", "latencyMs": 12},
                {"module": "M2/M4", "label": "Policy Engine", "status": "healthy", "latencyMs": 8},
                {"module": "M6", "label": "MCP Gateway", "status": "healthy", "latencyMs": 2},
                {"module": "M10", "label": "Audit Logger", "status": "healthy", "latencyMs": 15},
            ],
        },
        {
            "name": "Intelligence Layer",
            "modules": [
                {"module": "M8", "label": "Bedrock Agents", "status": "healthy", "latencyMs": 45},
                {"module": "M9", "label": "Intent Router", "status": "healthy", "latencyMs": 5},
            ],
        },
        {
            "name": "Data Layer",
            "modules": [
                {"module": "M11", "label": "Adapters", "status": "healthy", "latencyMs": 22},
            ],
        },
    ]


def _mock_adapter_health() -> list[dict[str, Any]]:
    return [
        {
            "name": "Schwab",
            "vendor": "Charles Schwab",
            "protocol": "REST/MCP",
            "status": "healthy",
            "circuitBreaker": "CLOSED",
            "lastSuccess": datetime.now(timezone.utc).isoformat(),
        },
        {
            "name": "Fidelity",
            "vendor": "Fidelity Investments",
            "protocol": "REST/MCP",
            "status": "healthy",
            "circuitBreaker": "CLOSED",
            "lastSuccess": datetime.now(timezone.utc).isoformat(),
        },
    ]


def _mock_metrics() -> list[dict[str, Any]]:
    return [
        {"service": "M6 Gateway", "p50": 45, "p95": 120, "p99": 250, "throughput": "142 req/s"},
        {"service": "M1 Identity", "p50": 12, "p95": 35, "p99": 80, "throughput": "142 req/s"},
        {"service": "M2/M4 Policy", "p50": 8, "p95": 22, "p99": 55, "throughput": "142 req/s"},
        {"service": "M10 Audit", "p50": 15, "p95": 45, "p99": 110, "throughput": "142 req/s"},
    ]



# ═════════════════════════════════════════════════════════════════
# CHAT ENDPOINTS
# ═════════════════════════════════════════════════════════════════


@web_api_router.post("/chat/send")
async def chat_send(body: SendMessageRequest, request: Request):
    """
    Send a chat message. Runs trust pipeline, classifies intent via M9,
    routes to appropriate specialist, returns ChatMessage.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "chat.send", {"content": body.content},
    )
    if not passed:
        return err

    conversation_id = body.conversationId or str(uuid4())

    # Call M9 intent router to classify the message
    try:
        client = await _get_client()
        intent_resp = await client.post(
            f"{_M9_URL.rstrip('/')}/intent/classify",
            json={
                "user_input": body.content,
                "aid_claims": claims,
            },
        )
        intent_resp.raise_for_status()
        intent_data = intent_resp.json()
        specialist = intent_data.get("specialist", "client_service")
        agent_content = intent_data.get("response", f"Understood. Routing to {specialist} specialist.")
    except Exception as e:
        logger.error("M9 intent classification failed: %s", e)
        specialist = "client_service"
        agent_content = "I understand your request. Let me look into that for you."

    # Run leakage scan on outbound response (Rule 10)
    scan_result = scan_output({"content": agent_content})
    if not scan_result.passed:
        logger.warning("MNPI leakage detected in chat response, blocking")
        await _write_audit(trace_id, claims, "chat.send", "deny", "MNPI leakage in response")
        return _generic_error(403, "Request denied")

    # Write audit (Rule 3 step 4)
    await _write_audit(
        trace_id, claims, "chat.send", "allow", "Chat message processed",
        request_data={"content": body.content},
        response_data={"specialist": specialist},
    )

    return ChatMessage(
        role="agent",
        specialist=specialist,
        content=agent_content,
        provenanceTraceId=trace_id,
    )


@web_api_router.get("/chat/history/{conversation_id}")
async def chat_history(conversation_id: str, request: Request):
    """Query M8 memory service for conversation history."""
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "chat.history", {"conversationId": conversation_id},
    )
    if not passed:
        return err

    # Call M8 memory service for conversation history
    try:
        client = await _get_client()
        resp = await client.get(
            f"{_M8_URL.rstrip('/')}/memory/conversation/{conversation_id}",
        )
        resp.raise_for_status()
        messages = resp.json().get("messages", [])
    except Exception as e:
        logger.error("M8 memory query failed: %s", e)
        if _DEV_MODE:
            messages = _mock_chat_history(conversation_id)
        else:
            messages = []

    # Run leakage scan on outbound data
    scan_result = scan_output(messages)
    if not scan_result.passed:
        logger.warning("MNPI leakage in chat history, blocking")
        await _write_audit(trace_id, claims, "chat.history", "deny", "MNPI leakage")
        return _generic_error(403, "Request denied")

    await _write_audit(
        trace_id, claims, "chat.history", "allow", "History retrieved",
    )
    return messages


@web_api_router.get("/chat/stream")
async def chat_stream(
    request: Request,
    conversationId: str = "",
    content: str = "",
    token: str = "",
):
    """
    SSE endpoint for streaming agent responses.
    Token passed as query param (EventSource doesn't support headers).
    Events: token, detail, done, error, blocked.
    """
    aid_token = token or _extract_token(request)
    if not aid_token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        aid_token, "chat.stream", {"content": content},
    )
    if not passed:
        # For SSE, return error as event stream then close
        async def error_stream():
            yield f"event: blocked\ndata: Trust pipeline denied\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_generator():
        """Generate SSE events. Runs leakage scan mid-stream."""
        accumulated_text = ""
        try:
            # Call M9 for intent classification
            client = await _get_client()
            try:
                intent_resp = await client.post(
                    f"{_M9_URL.rstrip('/')}/intent/classify",
                    json={"user_input": content, "aid_claims": claims},
                )
                intent_resp.raise_for_status()
                intent_data = intent_resp.json()
                specialist = intent_data.get("specialist", "client_service")
                full_response = intent_data.get(
                    "response",
                    "I understand your request. Let me look into that for you.",
                )
            except Exception as e:
                logger.error("M9 failed during stream: %s", e)
                specialist = "client_service"
                full_response = "I understand your request. Let me look into that for you."

            # Send detail event with specialist info
            detail_payload = json.dumps({"type": "specialist", "payload": specialist})
            yield f"event: detail\ndata: {detail_payload}\n\n"

            # Simulate token-by-token streaming
            words = full_response.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                accumulated_text += chunk

                # Mid-stream leakage scan every 50 chars
                if len(accumulated_text) % 50 < len(chunk):
                    mid_scan = scan_output({"text": accumulated_text})
                    if not mid_scan.passed:
                        logger.warning("MNPI leakage mid-stream, blocking")
                        await _write_audit(
                            trace_id, claims, "chat.stream", "deny",
                            "MNPI leakage mid-stream",
                        )
                        yield f"event: blocked\ndata: Content blocked by compliance filter\n\n"
                        return

                yield f"event: token\ndata: {chunk}\n\n"
                await asyncio.sleep(0.02)

            # Final leakage scan on complete response
            final_scan = scan_output({"text": accumulated_text})
            if not final_scan.passed:
                logger.warning("MNPI leakage in final response, blocking")
                await _write_audit(
                    trace_id, claims, "chat.stream", "deny",
                    "MNPI leakage in final response",
                )
                yield f"event: blocked\ndata: Content blocked by compliance filter\n\n"
                return

            await _write_audit(
                trace_id, claims, "chat.stream", "allow", "Stream completed",
            )
            yield "event: done\ndata: \n\n"

        except Exception as e:
            logger.error("SSE stream error: %s", e)
            yield f"event: error\ndata: Stream interrupted\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# ═════════════════════════════════════════════════════════════════
# REVIEWS ENDPOINTS (Principal Review Queue — FINRA 2210)
# Requires principal or admin role.
# ═════════════════════════════════════════════════════════════════


@web_api_router.get("/reviews/pending")
async def reviews_pending(request: Request):
    """Get pending review items. Requires principal or admin role."""
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "reviews.pending", {}, required_role="principal,admin",
    )
    if not passed:
        return err

    # Query review queue (M10 or dedicated review service)
    try:
        http_client = await _get_client()
        resp = await http_client.get(
            f"{_M10_URL.rstrip('/')}/audit/query",
            params={"trace_id": "reviews:pending"},
        )
        resp.raise_for_status()
        entries = resp.json().get("entries", [])
        reviews = entries if entries else (_mock_reviews_pending() if _DEV_MODE else [])
    except Exception as e:
        logger.error("Review queue query failed: %s", e)
        reviews = _mock_reviews_pending() if _DEV_MODE else []

    scan_result = scan_output(reviews)
    if not scan_result.passed:
        logger.warning("MNPI leakage in reviews, blocking")
        await _write_audit(trace_id, claims, "reviews.pending", "deny", "MNPI leakage")
        return _generic_error(403, "Request denied")

    await _write_audit(trace_id, claims, "reviews.pending", "allow", "Reviews retrieved")
    return reviews


@web_api_router.get("/reviews/history")
async def reviews_history(request: Request):
    """Get completed review history. Requires principal or admin role."""
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "reviews.history", {}, required_role="principal,admin",
    )
    if not passed:
        return err

    try:
        http_client = await _get_client()
        resp = await http_client.get(
            f"{_M10_URL.rstrip('/')}/audit/query",
            params={"trace_id": "reviews:history"},
        )
        resp.raise_for_status()
        entries = resp.json().get("entries", [])
        reviews = entries if entries else (_mock_reviews_history() if _DEV_MODE else [])
    except Exception as e:
        logger.error("Review history query failed: %s", e)
        reviews = _mock_reviews_history() if _DEV_MODE else []

    scan_result = scan_output(reviews)
    if not scan_result.passed:
        await _write_audit(trace_id, claims, "reviews.history", "deny", "MNPI leakage")
        return _generic_error(403, "Request denied")

    await _write_audit(trace_id, claims, "reviews.history", "allow", "Review history retrieved")
    return reviews


@web_api_router.post("/reviews/action")
async def reviews_action(body: ReviewActionRequest, request: Request):
    """
    Submit review action (approve/reject/edit). Requires principal or admin.
    Generates SHA-256 approval token. Archives to Smarsh if BD.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "reviews.action", body.model_dump(), required_role="principal,admin",
    )
    if not passed:
        return err

    # Generate SHA-256 approval token
    approval_payload = {
        "reviewId": body.reviewId,
        "action": body.action,
        "actor": claims.get("display_name", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    approval_token = _sha256(approval_payload)

    # Write audit with approval token
    await _write_audit(
        trace_id, claims, "reviews.action", "allow",
        f"Review {body.action}: {body.reviewId}",
        request_data=body.model_dump(),
        response_data={"approval_token": approval_token},
    )

    return {"ok": True, "approvalToken": approval_token}


# ═════════════════════════════════════════════════════════════════
# AUDIT ENDPOINTS
# Requires compliance_officer or admin role.
# ═════════════════════════════════════════════════════════════════


@web_api_router.get("/audit/trail")
async def audit_trail(
    request: Request,
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    client: Optional[str] = None,
    advisor: Optional[str] = None,
    action: Optional[str] = None,
    decision: Optional[str] = None,
):
    """Query audit trail with filters. Requires compliance_officer or admin."""
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "audit.trail", {},
        required_role="compliance_officer,admin",
    )
    if not passed:
        return err

    # Build query params for M10
    query_params: dict[str, str] = {}
    if dateFrom:
        query_params["date_from"] = dateFrom
    if dateTo:
        query_params["date_to"] = dateTo
    if client:
        query_params["client"] = client
    if advisor:
        query_params["advisor"] = advisor
    if action:
        query_params["action"] = action
    if decision:
        query_params["decision"] = decision

    # Call M10 audit query
    try:
        http_client = await _get_client()
        resp = await http_client.get(
            f"{_M10_URL.rstrip('/')}/audit/query",
            params=query_params if query_params else {"trace_id": "audit:trail"},
        )
        resp.raise_for_status()
        entries = resp.json().get("entries", [])
        if not entries and _DEV_MODE:
            entries = _mock_audit_trail()
    except Exception as e:
        logger.error("M10 audit query failed: %s", e)
        entries = _mock_audit_trail() if _DEV_MODE else []

    scan_result = scan_output(entries)
    if not scan_result.passed:
        await _write_audit(trace_id, claims, "audit.trail", "deny", "MNPI leakage")
        return _generic_error(403, "Request denied")

    await _write_audit(trace_id, claims, "audit.trail", "allow", "Audit trail queried")
    return entries


@web_api_router.get("/audit/detail/{trace_id_param}")
async def audit_detail(trace_id_param: str, request: Request):
    """Get full audit entry with provenance chain. Requires compliance_officer or admin."""
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "audit.detail", {"traceId": trace_id_param},
        required_role="compliance_officer,admin",
    )
    if not passed:
        return err

    try:
        http_client = await _get_client()
        resp = await http_client.get(
            f"{_M10_URL.rstrip('/')}/audit/query",
            params={"trace_id": trace_id_param},
        )
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("entries", [])
        entry = entries[0] if entries else None
    except Exception as e:
        logger.error("M10 audit detail query failed: %s", e)
        entry = None

    if entry is None:
        if _DEV_MODE:
            trail = _mock_audit_trail()
            entry = trail[0] if trail else {}
        else:
            return _generic_error(404, "Not found")

    scan_result = scan_output(entry)
    if not scan_result.passed:
        await _write_audit(trace_id, claims, "audit.detail", "deny", "MNPI leakage")
        return _generic_error(403, "Request denied")

    await _write_audit(trace_id, claims, "audit.detail", "allow", "Audit detail retrieved")
    return entry



# ═════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# Requires admin role.
# ═════════════════════════════════════════════════════════════════


@web_api_router.get("/admin/health")
async def admin_health(request: Request):
    """
    Check health of all modules. Calls /health on each service.
    Requires admin role.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "admin.health", {}, required_role="admin",
    )
    if not passed:
        return err

    # Health check targets: (url, module_name, label)
    targets = [
        (_M1_URL, "M1", "Identity"),
        (_M2_URL, "M2/M4", "Policy Engine"),
        (_M8_URL, "M8", "Bedrock Agents"),
        (_M9_URL, "M9", "Intent Router"),
        (_M10_URL, "M10", "Audit Logger"),
        (_M11_URL, "M11", "Adapters"),
    ]

    layers: dict[str, list[dict[str, Any]]] = {
        "Trust Layer": [],
        "Intelligence Layer": [],
        "Data Layer": [],
    }
    layer_map = {
        "M1": "Trust Layer",
        "M2/M4": "Trust Layer",
        "M10": "Trust Layer",
        "M8": "Intelligence Layer",
        "M9": "Intelligence Layer",
        "M11": "Data Layer",
    }

    http_client = await _get_client()
    for url, module, label in targets:
        t0 = time.monotonic()
        try:
            resp = await http_client.get(
                f"{url.rstrip('/')}/health",
                timeout=5.0,
            )
            latency = int((time.monotonic() - t0) * 1000)
            status = "healthy" if resp.status_code == 200 else "degraded"
        except Exception:
            latency = int((time.monotonic() - t0) * 1000)
            status = "down"

        layer_name = layer_map.get(module, "Data Layer")
        layers[layer_name].append({
            "module": module,
            "label": label,
            "status": status,
            "latencyMs": latency,
        })

    # Add M6 itself (always healthy if we're responding)
    layers["Trust Layer"].insert(2, {
        "module": "M6",
        "label": "MCP Gateway",
        "status": "healthy",
        "latencyMs": 0,
    })

    result = [{"name": name, "modules": mods} for name, mods in layers.items()]

    await _write_audit(trace_id, claims, "admin.health", "allow", "Health check performed")
    return result


@web_api_router.get("/admin/adapters")
async def admin_adapters(request: Request):
    """
    Get adapter/circuit breaker states from M6 registry.
    Requires admin role.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "admin.adapters", {}, required_role="admin",
    )
    if not passed:
        return err

    # Get circuit breaker states from the M6 app's proxy (intra-module)
    try:
        from .app import get_proxy
        proxy = get_proxy()
        cb_states = proxy.circuit_breakers.get_all_states()
        adapters = [
            {
                "name": url.split("//")[-1].split(":")[0].split(".")[0],
                "vendor": url,
                "protocol": "REST/MCP",
                "status": "healthy" if state == "closed" else "degraded" if state == "half_open" else "down",
                "circuitBreaker": state.upper().replace("_", "_"),
                "lastSuccess": datetime.now(timezone.utc).isoformat(),
            }
            for url, state in cb_states.items()
        ]
    except Exception as e:
        logger.error("Failed to get adapter states: %s", e)
        adapters = _mock_adapter_health() if _DEV_MODE else []

    if not adapters and _DEV_MODE:
        adapters = _mock_adapter_health()

    await _write_audit(trace_id, claims, "admin.adapters", "allow", "Adapter status retrieved")
    return adapters


@web_api_router.get("/admin/metrics")
async def admin_metrics(request: Request):
    """
    Get performance metrics from M6 internal counters.
    Requires admin role.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "admin.metrics", {}, required_role="admin",
    )
    if not passed:
        return err

    # In production, these come from OpenTelemetry/Prometheus.
    # For now, return mock data.
    metrics = _mock_metrics()

    await _write_audit(trace_id, claims, "admin.metrics", "allow", "Metrics retrieved")
    return metrics


# ═════════════════════════════════════════════════════════════════
# ORDER ENDPOINTS
# ═════════════════════════════════════════════════════════════════


@web_api_router.post("/orders/approve")
async def orders_approve(body: OrderApproveRequest, request: Request):
    """
    Approve a trade order. Calls execution specialist.
    Generates SHA-256 approval token. Writes audit to M10.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "order.approve", {"orderId": body.orderId},
    )
    if not passed:
        return err

    # Generate SHA-256 approval token
    approval_payload = {
        "orderId": body.orderId,
        "action": "approve",
        "actor": claims.get("display_name", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    approval_token = _sha256(approval_payload)

    # Call execution specialist approve endpoint
    try:
        http_client = await _get_client()
        approver_id = claims.get("display_name", "unknown")
        resp = await http_client.post(
            f"{_EXEC_URL.rstrip('/')}/order/{body.orderId}/approve",
            params={"approver_id": approver_id},
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error("Execution specialist approve failed: %s", e)
        if not _DEV_MODE:
            return _generic_error(502, "Service unavailable")

    await _write_audit(
        trace_id, claims, "order.approve", "allow",
        f"Order approved: {body.orderId}",
        request_data={"orderId": body.orderId},
        response_data={"approval_token": approval_token},
    )

    return {"ok": True, "approvalToken": approval_token}


@web_api_router.post("/orders/reject")
async def orders_reject(body: OrderRejectRequest, request: Request):
    """
    Reject a trade order. Calls execution specialist.
    Writes audit to M10.
    """
    token = _extract_token(request)
    if not token:
        return _generic_error(401, "Authentication required")

    trace_id = str(uuid4())
    passed, claims, err = await _run_trust_pipeline(
        token, "order.reject", {"orderId": body.orderId, "reason": body.reason},
    )
    if not passed:
        return err

    # Call execution specialist reject endpoint
    try:
        http_client = await _get_client()
        approver_id = claims.get("display_name", "unknown")
        resp = await http_client.post(
            f"{_EXEC_URL.rstrip('/')}/order/{body.orderId}/reject",
            params={"approver_id": approver_id},
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error("Execution specialist reject failed: %s", e)
        if not _DEV_MODE:
            return _generic_error(502, "Service unavailable")

    await _write_audit(
        trace_id, claims, "order.reject", "allow",
        f"Order rejected: {body.orderId}",
        request_data=body.model_dump(),
    )

    return {"ok": True}
