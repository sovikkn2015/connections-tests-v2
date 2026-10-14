# API-01: Web API Contract — Frontend ↔ Backend

> Date: April 18, 2026
> Purpose: Single source of truth for the API contract between M12 Web Console and M6 Gateway
> Frontend: src/m12-web-console/src/api/gateway.ts + sse.ts
> Backend: src/m6-mcp-gateway/web_api.py (mounted on M6 app via include_router)
> Base path: /api/v1 (both sides)
> Auth: Bearer token in Authorization header (AID JWT from Keycloak via M1)

---

## ENDPOINT MAP

| # | Method | Path | Frontend (gateway.ts) | Backend (web_api.py) | Role Required | Status |
|---|--------|------|-----------------------|---------------------|---------------|--------|
| 1 | POST | /api/v1/chat/send | sendMessage() | chat_send() | Any | WIRED |
| 2 | GET | /api/v1/chat/history/{id} | getChatHistory() | chat_history() | Any | WIRED |
| 3 | GET | /api/v1/chat/stream | sse.ts connectSSE() | chat_stream() SSE | Any | WIRED |
| 4 | GET | /api/v1/reviews/pending | getReviewQueue() | reviews_pending() | principal, admin | WIRED |
| 5 | GET | /api/v1/reviews/history | getReviewHistory() | reviews_history() | principal, admin | WIRED |
| 6 | POST | /api/v1/reviews/action | submitReviewAction() | reviews_action() | principal, admin | WIRED |
| 7 | GET | /api/v1/audit/trail | getAuditTrail() | audit_trail() | compliance_officer, admin | WIRED |
| 8 | GET | /api/v1/audit/detail/{id} | getAuditDetail() | audit_detail() | compliance_officer, admin | WIRED |
| 9 | GET | /api/v1/admin/health | getSystemHealth() | admin_health() | admin | WIRED |
| 10 | GET | /api/v1/admin/adapters | getAdapterStatus() | admin_adapters() | admin | WIRED |
| 11 | GET | /api/v1/admin/metrics | getPerformanceMetrics() | admin_metrics() | admin | WIRED |
| 12 | POST | /api/v1/orders/approve | approveOrder() | orders_approve() | Any | WIRED |
| 13 | POST | /api/v1/orders/reject | rejectOrder() | orders_reject() | Any | WIRED |

13/13 matched. 95 backend tests pass (21 web API specific).

---

## TRUST PIPELINE (Every Endpoint)

```
Request → Extract AID token → M1 verify → Role check → M2 authority → M4 MNPI filter → Action → Leakage scan → M10 audit → Response
```

Any step fails = request denied (401/403). Generic error to client. Full details to logs only (Rule 9).

---

## REQUEST/RESPONSE FORMATS

### Chat Send (POST /api/v1/chat/send)

Request: `{ "content": "string", "conversationId?": "string" }`

Response: `{ "id", "role": "agent", "specialist", "content", "timestamp", "sources", "provenanceTraceId", "detailType", "detailPayload" }`

### Chat Stream (GET /api/v1/chat/stream) — SSE

Query params: conversationId, content, token

Events: `token` (word), `detail` (specialist info), `done`, `blocked` (MNPI detected), `error`

Mid-stream leakage scan every 50 chars. Blocked = stream closes.

### Reviews Action (POST /api/v1/reviews/action)

Request: `{ "reviewId", "action": "approve|reject|edit_approve", "reason?", "editedContent?" }`

Response: `{ "ok": true, "approvalToken": "64-char-sha256" }`

### Order Approve/Reject (POST /api/v1/orders/approve|reject)

Approve: `{ "orderId" }` → `{ "ok": true, "approvalToken": "64-char-sha256" }`

Reject: `{ "orderId", "reason" }` → `{ "ok": true }`

### Audit Trail (GET /api/v1/audit/trail)

Query params: dateFrom, dateTo, client, advisor, action, decision

Response: AuditEntry[] with provenanceChain[], mnpiFilter, wormRecord

### Admin Health (GET /api/v1/admin/health)

Response: LayerHealth[] — Trust Layer, Intelligence Layer, Data Layer, each with module status + latency

---

## ERROR RESPONSES

All errors: `{ "error": "Request denied", "request_id": "uuid" }`

| Status | Meaning |
|--------|---------|
| 401 | No/invalid/expired token |
| 403 | Role insufficient, M2 DENY, MNPI leakage |
| 404 | Not found |
| 502 | Downstream unavailable |
| 503 | M10 audit failed (fail-closed) |

---

## DEV MODE

`M6_DEV_MODE=true`: M1/M2/M4 failures return mock admin claims. Endpoints return realistic mock data. Allows UI development without all 13 services running.

---

*API-01 — Project 007 FSI Interoperability Platform*
