"""
A2A task handler for the Financial Analysis agent.

Serves ``POST /agent`` per Google A2A spec v0.1.0. Accepts JSON-RPC 2.0
requests with these methods:

    tasks/send             — synchronous execution, returns a Task
    tasks/sendSubscribe    — advertised but returns UnsupportedOperation
                              in MVP (streaming is planned, not shipped)
    tasks/get              — trivial re-serialization (we don't persist)

The handler translates an incoming A2A Message into a Strands
``Agent.invoke()`` call. When the user message mentions a specific skill
id (``run_dcf``, ``run_comps``, ``monte_carlo``, ``fair_value``) we
short-circuit to that tool directly — this makes the agent broker's
deterministic routing fast and avoids an extra LLM hop. Otherwise we
fall through to the Strands Agent's autonomous reasoning loop.

The response artifact contains the structured tool output as a ``data``
part plus a human-readable ``text`` summary.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Wire shared/ onto sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.abspath(os.path.join(_HERE, "..", "..", "shared"))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

try:
    from a2a_types import (
        build_error,
        build_result,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        INVALID_PARAMS,
        INTERNAL_ERROR,
        UNSUPPORTED_OPERATION,
    )
except ImportError:  # pragma: no cover
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    UNSUPPORTED_OPERATION = -32004

    def build_error(request_id, code, message, data=None):
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": err}

    def build_result(request_id, result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

# Import tools and (best-effort) Langfuse tracer from the existing app
try:
    from app import (
        run_dcf,
        run_comps,
        monte_carlo,
        fair_value,
        _get_agent,
        FINANCIAL_DATA,
    )
    try:
        from app import create_trace, add_span, end_trace
    except ImportError:
        def create_trace(*a, **kw): return "no-trace"
        def add_span(*a, **kw): pass
        def end_trace(*a, **kw): pass
except ImportError as exc:  # pragma: no cover
    logging.getLogger(__name__).error("Failed to import app.py: %s", exc)
    raise

logger = logging.getLogger(__name__)

# Map skill ids (as advertised in the manifest) to tool callables
SKILL_MAP = {
    "run_dcf": run_dcf,
    "run_comps": run_comps,
    "monte_carlo": monte_carlo,
    "fair_value": fair_value,
}

SUPPORTED_METHODS = {"tasks/send", "tasks/sendSubscribe", "tasks/get"}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _parse_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Parse the API Gateway event body into a JSON-RPC request dict."""
    raw = event.get("body")
    if raw is None:
        return None, _rpc_error(None, INVALID_REQUEST, "Empty request body")
    if isinstance(raw, (dict, list)):
        return raw, None
    try:
        return json.loads(raw), None
    except (TypeError, json.JSONDecodeError) as exc:
        return None, _rpc_error(None, INVALID_REQUEST, f"Malformed JSON: {exc}")


def _rpc_error(request_id, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    return _respond(200, build_error(request_id, code, message, data))


def _respond(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "X-A2A-Protocol": "a2a/v0.1.0",
        },
        "body": json.dumps(body, default=str),
    }


def _extract_text(message: Dict[str, Any]) -> str:
    """Concatenate all text parts from an A2A Message."""
    parts = message.get("parts") or []
    out: List[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        # A2A v0.1: {"type":"text","text":"..."}; some clients use "kind"
        kind = p.get("type") or p.get("kind")
        if kind == "text":
            txt = p.get("text", "")
            if txt:
                out.append(txt)
    return "\n".join(out).strip()


def _extract_data(message: Dict[str, Any]) -> Dict[str, Any]:
    """Merge all data parts from an A2A Message into a single dict."""
    parts = message.get("parts") or []
    merged: Dict[str, Any] = {}
    for p in parts:
        if not isinstance(p, dict):
            continue
        kind = p.get("type") or p.get("kind")
        if kind == "data":
            data = p.get("data") or {}
            if isinstance(data, dict):
                merged.update(data)
    return merged


def _detect_skill(text: str, data: Dict[str, Any]) -> Optional[str]:
    """Determine which skill the caller wants, if explicitly specified.

    Priority:
      1. ``skill`` field in a data part
      2. message-level metadata.skill
      3. literal skill id word-match inside text parts
    """
    if "skill" in data and isinstance(data["skill"], str):
        candidate = data["skill"].strip().lower()
        if candidate in SKILL_MAP:
            return candidate

    t = text.lower() if text else ""
    for skill_id in SKILL_MAP:
        if re.search(rf"\b{re.escape(skill_id)}\b", t):
            return skill_id
    return None


def _extract_ticker(text: str, data: Dict[str, Any]) -> Optional[str]:
    if data.get("ticker"):
        return str(data["ticker"]).upper()
    # Scan text for known tickers
    if text:
        upper = text.upper()
        for ticker in FINANCIAL_DATA:
            if re.search(rf"\b{re.escape(ticker)}\b", upper):
                return ticker
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Skill execution
# ---------------------------------------------------------------------------
def _execute_skill(skill_id: str, ticker: str, data: Dict[str, Any]) -> Any:
    """Invoke the selected Strands tool with coerced kwargs."""
    fn = SKILL_MAP[skill_id]
    kwargs: Dict[str, Any] = {"ticker": ticker}

    if skill_id == "run_dcf":
        for k in ("growth_rate", "discount_rate", "terminal_growth"):
            if k in data:
                try:
                    kwargs[k] = float(data[k])
                except (TypeError, ValueError):
                    pass
        if "wacc" in data and "discount_rate" not in kwargs:
            try:
                kwargs["discount_rate"] = float(data["wacc"])
            except (TypeError, ValueError):
                pass
    elif skill_id == "monte_carlo":
        if "simulations" in data:
            try:
                kwargs["simulations"] = int(data["simulations"])
            except (TypeError, ValueError):
                pass

    return fn(**kwargs)


def _execute_autonomous(text: str) -> Any:
    """Fall through to the Strands Agent when no skill can be derived."""
    agent = _get_agent()
    if agent is None:
        return {
            "error": "Strands agent unavailable and no explicit skill provided.",
            "hint": "Include a data part with {\"skill\": \"run_dcf\", \"ticker\": \"NVDA\"}.",
        }
    try:
        response = agent(text)
        return {"response": str(response)}
    except Exception as exc:  # pragma: no cover
        logger.exception("Autonomous Strands execution failed")
        return {"error": f"agent execution failed: {exc}"}


# ---------------------------------------------------------------------------
# Task construction
# ---------------------------------------------------------------------------
def _build_task(
    task_id: str,
    context_id: str,
    state: str,
    user_message: Dict[str, Any],
    artifact_payload: Any,
    artifact_name: str,
    summary_text: str,
    skill_id: Optional[str],
    failed_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble an A2A Task response body."""
    history = [{**user_message, "taskId": task_id, "contextId": context_id}]

    status: Dict[str, Any] = {"state": state, "timestamp": _now_iso()}
    if failed_error:
        status["message"] = {
            "role": "agent",
            "parts": [{"type": "text", "text": failed_error}],
            "messageId": str(uuid.uuid4()),
            "taskId": task_id,
            "contextId": context_id,
        }

    artifacts: List[Dict[str, Any]] = []
    if state == "completed":
        artifact: Dict[str, Any] = {
            "artifactId": str(uuid.uuid4()),
            "name": artifact_name,
            "parts": [
                {"type": "text", "text": summary_text},
                {"type": "data", "data": _jsonable(artifact_payload)},
            ],
        }
        if skill_id:
            artifact["metadata"] = {"skillId": skill_id}
        artifacts.append(artifact)

    return {
        "id": task_id,
        "contextId": context_id,
        "status": status,
        "artifacts": artifacts,
        "history": history,
        "kind": "task",
        "metadata": {"skillId": skill_id} if skill_id else {},
    }


def _jsonable(value: Any) -> Any:
    """Coerce value to something JSON-serializable."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, default=str))


def _summarize(skill_id: Optional[str], ticker: Optional[str], result: Any) -> str:
    """Generate a one-line human-readable summary for the text part."""
    if not skill_id:
        return f"Autonomous analysis result ready."
    if isinstance(result, dict) and result.get("error"):
        return f"{skill_id} on {ticker}: error — {result['error']}"
    if skill_id == "run_dcf" and isinstance(result, dict):
        fv = result.get("fair_value_per_share")
        price = result.get("current_price")
        return f"DCF on {ticker}: fair value ${fv} vs price ${price}."
    if skill_id == "run_comps" and isinstance(result, dict):
        sector = result.get("sector")
        return f"Comps on {ticker} ({sector}): {result.get('relative_valuation', {})}."
    if skill_id == "monte_carlo" and isinstance(result, dict):
        p = result.get("percentiles", {})
        return f"Monte Carlo on {ticker}: p5=${p.get('p5')} p50=${p.get('p50')} p95=${p.get('p95')}."
    if skill_id == "fair_value" and isinstance(result, dict):
        return f"Fair value report for {ticker} (DCF ${result.get('dcf_fair_value')}, MC median ${result.get('monte_carlo_median')})."
    return f"{skill_id} on {ticker}: completed."


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------
def _handle_tasks_send(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute ``tasks/send`` synchronously."""
    if not isinstance(params, dict):
        return _rpc_error(request_id, INVALID_PARAMS, "params must be an object")

    message = params.get("message")
    if not isinstance(message, dict):
        return _rpc_error(request_id, INVALID_PARAMS, "params.message is required")
    if message.get("role") != "user":
        return _rpc_error(request_id, INVALID_PARAMS, "message.role must be 'user'")

    task_id = params.get("taskId") or message.get("taskId") or str(uuid.uuid4())
    context_id = (
        params.get("contextId")
        or message.get("contextId")
        or str(uuid.uuid4())
    )

    text = _extract_text(message)
    data = _extract_data(message)
    skill_id = _detect_skill(text, data)
    ticker = _extract_ticker(text, data)

    trace_id = create_trace(
        f"a2a-{skill_id or 'autonomous'}",
        input_data={"skill": skill_id, "ticker": ticker, "text": text},
        metadata={"protocol": "a2a/v0.1.0", "method": "tasks/send", "taskId": task_id},
    )

    start = time.time()
    try:
        if skill_id:
            if not ticker:
                return _rpc_error(
                    request_id, INVALID_PARAMS,
                    f"skill '{skill_id}' requires a ticker",
                    data={"skillId": skill_id},
                )
            result = _execute_skill(skill_id, ticker, data)
            artifact_name = f"{skill_id}-{ticker}"
        else:
            result = _execute_autonomous(text or "No input provided.")
            artifact_name = "autonomous-response"

        duration_ms = int((time.time() - start) * 1000)

        add_span(
            trace_id, skill_id or "autonomous",
            input_data={"ticker": ticker, "text": text},
            output_data=result,
            duration_ms=duration_ms,
            metadata={"protocol": "a2a/v0.1.0"},
        )

        summary = _summarize(skill_id, ticker, result)
        task = _build_task(
            task_id=task_id, context_id=context_id, state="completed",
            user_message=message, artifact_payload=result,
            artifact_name=artifact_name, summary_text=summary, skill_id=skill_id,
        )
        end_trace(trace_id, output=result, metadata={"duration_ms": duration_ms, "state": "completed"})
        return _respond(200, build_result(request_id, task))

    except Exception as exc:  # pragma: no cover
        logger.exception("tasks/send execution failed")
        end_trace(trace_id, output={"error": str(exc)}, metadata={"state": "failed"})
        task = _build_task(
            task_id=task_id, context_id=context_id, state="failed",
            user_message=message, artifact_payload=None, artifact_name="error",
            summary_text=str(exc), skill_id=skill_id, failed_error=str(exc),
        )
        return _respond(200, build_result(request_id, task))


def _handle_tasks_send_subscribe(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Streaming variant — advertised but not shipped in MVP."""
    return _rpc_error(
        request_id, UNSUPPORTED_OPERATION,
        "tasks/sendSubscribe (SSE streaming) is not supported in this MVP. "
        "Use tasks/send for synchronous execution.",
    )


def _handle_tasks_get(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a minimal 'completed' shell — we do not persist task state."""
    tid = params.get("id") if isinstance(params, dict) else None
    if not tid:
        return _rpc_error(request_id, INVALID_PARAMS, "params.id is required")
    task = {
        "id": tid,
        "status": {"state": "completed", "timestamp": _now_iso()},
        "artifacts": [],
        "history": [],
        "kind": "task",
        "metadata": {"note": "Task state is not persisted in this MVP."},
    }
    return _respond(200, build_result(request_id, task))


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def handler(event, context=None):
    """Main Lambda handler for ``POST /agent`` A2A invocations."""
    method_http = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or "POST"
    ).upper()

    if method_http == "OPTIONS":
        return _respond(204, {})

    if method_http != "POST":
        return _rpc_error(None, INVALID_REQUEST, f"HTTP {method_http} not supported on /agent")

    body, err = _parse_body(event)
    if err is not None:
        return err
    if not isinstance(body, dict):
        return _rpc_error(None, INVALID_REQUEST, "JSON-RPC body must be an object")

    if body.get("jsonrpc") != "2.0":
        return _rpc_error(body.get("id"), INVALID_REQUEST, "jsonrpc must be '2.0'")

    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if method not in SUPPORTED_METHODS:
        return _rpc_error(
            rpc_id, METHOD_NOT_FOUND,
            f"Unknown A2A method '{method}'",
            data={"supported": sorted(SUPPORTED_METHODS)},
        )

    if method == "tasks/send":
        return _handle_tasks_send(rpc_id, params)
    if method == "tasks/sendSubscribe":
        return _handle_tasks_send_subscribe(rpc_id, params)
    if method == "tasks/get":
        return _handle_tasks_get(rpc_id, params)

    # Unreachable
    return _rpc_error(rpc_id, INTERNAL_ERROR, "Unhandled method branch")


lambda_handler = handler
