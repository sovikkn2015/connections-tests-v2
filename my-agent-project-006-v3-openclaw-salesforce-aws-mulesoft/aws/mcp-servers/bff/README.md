# BFF Lambda — V3 Backend For Frontend

Small REST Lambda serving the four endpoints the React frontend expects.

## Routes

| Method | Path | Handler | Backing MCP |
|---|---|---|---|
| GET  | `/api/inquiries?type=alert&status=open` | `handle_inquiries` | salesforce-crm `read_object` on `Client_Inquiry__c` |
| GET  | `/api/source_tables/{id}` | `handle_source_table` | sec-edgar `get_source_table` |
| GET  | `/api/source_chunk/{id}` | `handle_source_chunk` | sec-edgar `get_source_chunk` |
| POST | `/api/session/warm` | `handle_session_warm` | logs-only; actual warm happens in AgentCore on WS open |

## Why this exists

The three frontend persona screens talk to AgentCore over WebSocket for streaming turns. But a handful of non-turn reads (citation drill-down, chart source-table lookup, alert list, intent prefetch) are plain HTTP GETs. The BFF keeps those off the WS channel so a long streaming turn doesn't block an inquiries refresh.

## Auth

Bearer token in `Authorization` header — the same token AgentCore minted at session open. The BFF does not re-verify signature in V3 demo (it trusts API Gateway's TLS + upstream token presence). Production hardening would validate HMAC via `AGENTCORE_SESSION_SIGNING_KEY`.

`MCP_DEV_MODE=true` lets the test fixture run without a real token — identical dev-escape to the other MCP Lambdas.

## Trust invariants preserved

- Inquiries read goes through salesforce-crm MCP → MNPI scrub + SOQL safety + persona gate still fire.
- Source lookups are read-only on public filing data; no write surface.
- Session warm is advisory; has no side effects in V3.

## Deploy

SAM template wires this Lambda under the shared `McpApi` with the four route `Events`. No separate CloudFormation needed.
