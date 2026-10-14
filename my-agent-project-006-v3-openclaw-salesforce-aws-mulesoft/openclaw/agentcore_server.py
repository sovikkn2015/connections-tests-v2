"""V3 AgentCore HTTP server.

AgentCore calls this container on port 8080 with:

  GET  /ping         -> health
  POST /invocations  -> body has {prompt, sessionKey, persona, principal_id,
                                  correlation_id, turn_number}
                        runs PersonaCoordinator.run_turn() with the real
                        Bedrock + MCP + KB backends and returns the final
                        synthesis text + gate trace.

Contract and framing chosen to match the V2 adapter.js so the frontend's
existing WebSocket transport layer (openclawApi.ts) can reach V3 without
changes. The WebSocket layer on top of AgentCore streams messages out;
this server answers one synchronous turn per invocation — the turn's
full gate trace ships in the response so the frontend's recently-wired
post-hoc replay animates the tracker.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .orchestration.coordinator import PersonaCoordinator
from .orchestration.messages import SessionContext


# One coordinator per process; safe because it's stateless across turns
# (each turn carries its own SessionContext).
_coordinator: PersonaCoordinator | None = None


def _get_coordinator() -> PersonaCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = PersonaCoordinator()
    return _coordinator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the coordinator so first turn doesn't pay cold-start Bedrock init.
    _get_coordinator()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
async def ping() -> PlainTextResponse:
    return PlainTextResponse("pong", status_code=200)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "runtime": "openclaw-v3"})


@app.post("/invocations")
async def invocations(request: Request) -> JSONResponse:
    """AgentCore invoke contract.

    AgentCore wraps input in a JSON body. We accept either the flat
    shape used by the V2 adapter (``{prompt, persona, principal_id, ...}``)
    or a nested ``{input: {...}}`` shape. Persona defaults to research.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"bad JSON: {exc}") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    payload = body.get("input") if isinstance(body.get("input"), dict) else body

    prompt = payload.get("prompt") or payload.get("message") or ""
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=400, detail="'prompt' must be a non-empty string")

    persona = str(payload.get("persona") or "fsi_research").strip()
    principal_id = str(
        payload.get("principal_id") or payload.get("principalId") or "dev-principal"
    ).strip()
    session_id = str(
        payload.get("session_id") or payload.get("sessionKey") or f"ac-{int(time.time()*1000)}"
    ).strip()
    correlation_id = str(
        payload.get("correlation_id") or payload.get("correlationId") or session_id
    ).strip()
    turn_number = int(payload.get("turn_number") or payload.get("turnNumber") or 1)

    ctx = SessionContext(
        principal_id=principal_id,
        persona=persona,
        session_id=session_id,
        correlation_id=correlation_id,
        turn_number=turn_number,
    )

    coord = _get_coordinator()
    started = time.time()
    try:
        result = await coord.run_turn(prompt, ctx)
    except Exception as exc:  # noqa: BLE001
        # Surface as 500 with error body so AgentCore returns it to the
        # caller rather than swallowing.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
                "duration_ms": int((time.time() - started) * 1000),
                "correlation_id": correlation_id,
            },
        )

    duration_ms = int((time.time() - started) * 1000)

    # ------------------------------------------------------------------
    # Gate-trace normalisation — the frontend SevenGateTracker + v2 map
    # expect CANONICAL gate names in the seven-gate vocabulary:
    #   guardrails, mnpi_filter, compliance, hitl, dual_auth, mulesoft, audit
    # Specialists emit skill-name events (compliance_screening, mulesoft_api,
    # audit_logging, ...) which we translate here via a well-known map.
    # Unknown tool names are dropped from the canonical trace (they would
    # render as dim cells on the UI). The *text* body still contains the
    # full skill-level detail; this normalisation is purely for UI state.
    # ------------------------------------------------------------------
    SKILL_TO_GATE = {
        "compliance_screening": "compliance",
        "compliance_screen": "compliance",
        "compliance_check": "compliance",
        "mnpi_filter": "mnpi_filter",
        "mnpi_scrub": "mnpi_filter",
        "guardrails_input": "guardrails",
        "guardrails_output": "guardrails",
        "guardrails": "guardrails",
        "hitl": "hitl",
        "hitl_mint": "hitl",
        "hitl_verify": "hitl",
        "dual_auth": "dual_auth",
        "mulesoft_api": "mulesoft",
        "mulesoft_submit": "mulesoft",
        "audit_logging": "audit",
        "audit_log": "audit",
    }

    # ------------------------------------------------------------------
    # Harvest from each worker's `result` dict. Specialists return either a
    # list under `gate_trace` (tool-use sequence) or a structured response
    # with `action_plan` + `gate_trace` (action_specialist). We prefer the
    # structured form because it carries the canonical 7-gate trace.
    # ------------------------------------------------------------------
    gate_trace: list[Dict[str, Any]] = []
    action_plan: Dict[str, Any] | None = None
    queue_updates: list[Dict[str, Any]] = []
    responses = result.get("responses", []) or []
    for r in responses:
        try:
            inner = getattr(r, "result", {}) or {}
            # Action specialist — lift the plan + trace up
            if inner.get("action_plan"):
                action_plan = inner["action_plan"]
            # Queue updates (liaison handoff, research demand signal, etc.)
            qu = inner.get("queue_updates") or []
            if isinstance(qu, list):
                queue_updates.extend(qu)
            # Canonical trace (action_specialist emits 7-gate names directly)
            gt = inner.get("gate_trace", [])
            for g in gt:
                raw_name = g.get("gate") or g.get("tool", "")
                mapped = SKILL_TO_GATE.get(raw_name, raw_name)
                # Only keep canonical 7 names; unknown tool names drop out of
                # the UI-visible trace but remain in the text body.
                CANONICAL = {
                    "guardrails", "mnpi_filter", "compliance",
                    "hitl", "dual_auth", "mulesoft", "audit",
                }
                if mapped not in CANONICAL:
                    continue
                status_raw = g.get("status", "ok")
                status = (
                    "passed" if status_raw in ("ok", "passed")
                    else "failed" if status_raw in ("error", "failed", "denied")
                    else "in_progress" if status_raw == "in_progress"
                    else "passed"
                )
                gate_trace.append(
                    {
                        "gate": mapped,
                        "status": status,
                        "detail": g.get("error") or g.get("detail"),
                    }
                )
        except Exception:  # noqa: BLE001
            continue

    # If the read-path specialists answered without producing a 7-gate trace,
    # synthesize one event per completed specialist so the TraversalMap still
    # animates. These are NOT canonical gate names — they sit in a dedicated
    # `specialist_trace` field the frontend uses to pulse map nodes.
    specialist_trace: list[Dict[str, Any]] = []
    if responses:
        for r in responses:
            try:
                agent_id = getattr(r, "agent_id", None) or "specialist"
                errors = getattr(r, "errors", []) or []
                cost = int(getattr(r, "cost_tokens", 0))
                status = "failed" if errors else "passed"
                specialist_trace.append(
                    {
                        "agent_id": agent_id,
                        "status": status,
                        "detail": (errors[0].get("message") if errors else f"tokens={cost}"),
                    }
                )
            except Exception:  # noqa: BLE001
                continue

    # Result envelope — stable for the frontend useStreamingTurn
    # turn_complete case. Added fields: action_plan, queue_updates,
    # specialist_trace. Removed field: none — backward compatible.
    envelope: Dict[str, Any] = {
        "status": "ok",
        "text": result.get("text", ""),
        "cost_tokens": int(result.get("cost_tokens", 0)),
        "cost_usd": 0.0,
        "duration_ms": duration_ms,
        "had_errors": bool(result.get("had_errors", False)),
        "gate_trace": gate_trace,
        "specialist_trace": specialist_trace,
        "correlation_id": correlation_id,
        "session_id": session_id,
        "persona": persona,
    }
    if action_plan is not None:
        envelope["action_plan"] = action_plan
    if queue_updates:
        envelope["queue_updates"] = queue_updates
    return JSONResponse(envelope)


def main() -> None:
    import uvicorn  # noqa: PLC0415

    port = int(os.environ.get("AGENTCORE_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
