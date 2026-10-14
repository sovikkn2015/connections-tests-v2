"""Bedrock Converse tool-use dispatch loop.

This module makes the seven-gate trust spine real at runtime instead of
prompt-advisory. When a specialist has a non-empty `tool_allowlist`, the
coordinator calls `run_tool_loop()` which:

  1. Builds a `toolConfig` from the agent's allowlist using each skill's
     Pydantic `Input` model as the JSON schema.
  2. Runs `bedrock.converse()` with tools enabled.
  3. When the response's stopReason is `tool_use`, dispatches every `toolUse`
     block to `get_skill(name).run(payload)` serially and appends each
     `toolResult` to the message history.
  4. Re-invokes `bedrock.converse()` until stopReason != "tool_use" or the
     per-turn budget is exhausted.
  5. Records the full gate trace (ordered tool names and status) on the
     returned `ToolTraceEntry` list for the orchestrator to attach to
     the WorkerResponse.

Steering rule 1: all regulated writes go through this path. The
action_specialist MUST exercise compliance_screening -> hitl -> dual_auth
-> mulesoft_api -> audit_logging in that order. We do not enforce the
ORDER in code (LLM decides), but we DO enforce:

  - every tool is in the allowlist (server-side check here, not prompt)
  - denied tools are 403-errored back to the model (not silently dropped)
  - tool-use budget caps infinite loops
  - `AuditInput.gate_trace` is populated by the dispatcher so an Apex
    reviewer can see which gates actually fired

The dispatcher is scoped to `serial_by_design=True` agents in V3 because
the read-path parallel fanout still uses the direct converse() path;
adding tool-use there would change the perf profile and is not a V3 goal.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from ..skills import MCPClient, get_skill

logger = logging.getLogger(__name__)


# Per-turn budgets. A typical action-specialist turn calls 5 gates; 20 loops
# is ~4x headroom for retries. Cost cap at 50k tokens prevents runaway spend.
# For read-path research specialists, 3 loops is plenty and keeps the
# per-turn latency inside the 29s API Gateway REST window.
import os as _os
_MAX_TOOL_LOOPS = int(_os.getenv("MCP_MAX_TOOL_LOOPS", "5"))
_MAX_TOTAL_TOKENS = int(_os.getenv("MCP_MAX_TOTAL_TOKENS", "50000"))

# Map of skill-name -> (Pydantic input class, short description).
# Imported lazily inside `_load_skill_inputs` so tests that don't touch the
# write path don't pay the import cost of every skill module.
_SKILL_SPECS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_skill_specs() -> Dict[str, Dict[str, Any]]:
    """Return { skill_name: { "input_cls": ..., "description": ... } }."""
    global _SKILL_SPECS_CACHE
    if _SKILL_SPECS_CACHE is not None:
        return _SKILL_SPECS_CACHE

    # Short descriptions shown to the LLM via Bedrock toolConfig.
    # Kept deliberately terse; the agent system prompt carries the detail.
    _DESCRIPTIONS = {
        "publish_brief": "Publish a Research_Brief__c record to Salesforce.",
        "rag_retrieve": "Hybrid retrieval (BM25 + vector + rerank) over research+filings corpora.",
        "financial_statement_analysis": "Deterministic financial-statement math (growth, ratios, DCF, Z/F/M scores).",
        "portfolio_analytics": "Portfolio-level analytics: concentration, drawdown, attribution.",
        "scenario_modeling": "Monte Carlo and deterministic scenario projections.",
        "suitability_check": "Suitability evaluation vs client risk profile and time horizon.",
        "client_summary": "MNPI-filtered client summary read (CRM).",
        "research_awareness": "Surface recent published briefs relevant to a ticker or household.",
        "compliance_screening": "Deterministic ALLOW/DENY/REVIEW: restricted list, MNPI, trading window, concentration. GATE 1.",
        "hitl": "Mint an approval token OR verify an RM-supplied approval_token. GATE 2.",
        "dual_auth": "Request or resolve a dual-approval token when required (wire>$100K, trade>$500K). GATE 3.",
        "mulesoft_api": "Invoke the MuleSoft Process API (submit_order, initiate_wire, cancel_order, modify_order). GATE 4.",
        "audit_logging": "Write an IR_Audit_Log__c row. MUST be the final gate of every write path. GATE 5.",
        "mcp_invoke": "Call any tool on an MCP server (market-data, sec-edgar, news-search, salesforce-crm, mulesoft-actions). Arguments: {server, tool, arguments}. Use this to fetch live quotes, EDGAR filings, news, and KB retrieval.",
        "rm_handoff": "Capture a client inquiry and route it to the assigned RM. Writes Client_Inquiry__c (MNPI-scrubbed), optionally Research_Request__c, and an IR_Audit_Log__c row. Use ONLY for client-liaison persona escalations.",
    }

    out: Dict[str, Dict[str, Any]] = {}
    for name in _DESCRIPTIONS:
        try:
            mod = get_skill(name)
        except KeyError:
            continue
        input_cls = _find_input_class(mod)
        out[name] = {
            "input_cls": input_cls,
            "description": _DESCRIPTIONS[name],
            "module": mod,
        }
    _SKILL_SPECS_CACHE = out
    return out


def _find_input_class(mod) -> Optional[type[BaseModel]]:
    """Locate the primary `Input` Pydantic class in a skill module.

    Convention: each skill module defines exactly one class named
    `*Input` that inherits from BaseModel. `hitl` is the exception — it
    has two (ApprovalMintInput, ApprovalVerifyInput); we pick the
    verify class since that's the write-path usage.

    Important: we only consider classes DEFINED IN this module, not
    imported from other skill modules. Several skills (e.g.
    compliance_screening) import AuditInput at the top, which would
    otherwise be picked up as the primary input and silently route the
    wrong schema to Bedrock.
    """
    if mod.__name__.endswith("hitl.actions"):
        return getattr(mod, "ApprovalVerifyInput", None)
    mod_name = mod.__name__
    for attr_name in dir(mod):
        if not attr_name.endswith("Input"):
            continue
        cls = getattr(mod, attr_name)
        if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
            continue
        if getattr(cls, "__module__", "") != mod_name:
            # Imported from another module -> not the primary input for this skill.
            continue
        return cls
    return None


def build_tool_config(tool_allowlist: List[str]) -> Dict[str, Any]:
    """Build the Bedrock Converse `toolConfig` for an agent's allowed skills.

    Returns the full dict to pass as `toolConfig=...` to bedrock-runtime
    converse. Empty allowlist -> empty toolConfig (caller should detect
    and skip the tool-use path).
    """
    specs = _load_skill_specs()
    tools: List[Dict[str, Any]] = []
    for name in tool_allowlist:
        spec = specs.get(name)
        if spec is None or spec["input_cls"] is None:
            logger.debug("skipping tool %s — no input class in registry", name)
            continue
        input_cls: type[BaseModel] = spec["input_cls"]
        schema = input_cls.model_json_schema()
        # Bedrock Converse expects `inputSchema.json` — not the raw $ref JSON
        # Schema form Pydantic emits. We drop Pydantic's `$defs` because Bedrock's
        # validator handles only inlined definitions for tool schemas.
        tools.append(
            {
                "toolSpec": {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": {"json": _inline_defs(schema)},
                }
            }
        )
    if not tools:
        return {}
    return {"tools": tools, "toolChoice": {"auto": {}}}


def _inline_defs(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Pydantic v2 emits $defs + $ref; Bedrock tool schemas want inline shapes.

    Walk the schema, inline every $ref that points into $defs, then drop $defs.
    """
    defs = schema.pop("$defs", {}) or schema.pop("definitions", {}) or {}

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref = node["$ref"]
                if ref.startswith("#/$defs/") or ref.startswith("#/definitions/"):
                    key = ref.split("/")[-1]
                    if key in defs:
                        resolved = _resolve(defs[key])
                        extra = {k: v for k, v in node.items() if k != "$ref"}
                        return {**resolved, **extra}
            return {k: _resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_resolve(x) for x in node]
        return node

    return _resolve(schema)


@dataclass
class ToolTraceEntry:
    """Record of one tool-use call — what the dispatcher did."""

    tool_name: str
    input_json: str
    status: str  # "ok" | "error" | "denied"
    output_summary: str
    elapsed_ms: int
    error: Optional[str] = None


@dataclass
class ToolLoopResult:
    """Outcome of a full tool-use dispatch loop."""

    text: str
    trace: List[ToolTraceEntry] = field(default_factory=list)
    tokens_used: int = 0
    stop_reason: str = ""
    loops: int = 0


async def run_tool_loop(
    *,
    bedrock,
    model_id: str,
    system_prompt: str,
    initial_user_text: str,
    tool_allowlist: List[str],
    agent_id: str,
    mcp: Optional[MCPClient] = None,
) -> ToolLoopResult:
    """Run the Bedrock tool-use dispatch loop for one specialist turn.

    Each tool_use block is validated against the agent's allowlist (fail-closed)
    and the skill's Pydantic Input schema (validation errors are returned to
    the model as tool errors, not silently swallowed).

    The loop terminates when:
      - stopReason != "tool_use" (normal end)
      - loop count >= _MAX_TOOL_LOOPS (budget exhaustion)
      - cumulative token count >= _MAX_TOTAL_TOKENS
    """
    allowed = set(tool_allowlist)
    tool_config = build_tool_config(tool_allowlist)
    if not tool_config:
        # No tools registered -> fall back to a plain converse call.
        result = await bedrock.converse(
            model_id=model_id,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": [{"text": initial_user_text}]}],
            agent_id=agent_id,
        )
        return ToolLoopResult(
            text=_extract_text(result),
            tokens_used=_extract_tokens(result),
            stop_reason=result.get("stopReason", "end_turn") if isinstance(result, dict) else "end_turn",
            loops=1,
        )

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": [{"text": initial_user_text}]}
    ]
    trace: List[ToolTraceEntry] = []
    total_tokens = 0
    last_text = ""
    stop_reason = "end_turn"

    for loop_i in range(_MAX_TOOL_LOOPS):
        result = await bedrock.converse(
            model_id=model_id,
            system_prompt=system_prompt,
            messages=messages,
            agent_id=agent_id,
            tool_config=tool_config,
        )
        stop_reason = (
            result.get("stopReason", "end_turn") if isinstance(result, dict) else "end_turn"
        )
        total_tokens += _extract_tokens(result)
        assistant_content = _extract_assistant_content(result)
        messages.append({"role": "assistant", "content": assistant_content})
        last_text = _content_text(assistant_content)

        if stop_reason != "tool_use":
            break

        # Collect tool_use blocks, dispatch each; build a combined tool_result message.
        tool_use_blocks = [b for b in assistant_content if "toolUse" in b]
        if not tool_use_blocks:
            # Model said tool_use but emitted no block; bail.
            logger.warning("agent=%s tool_use stopReason but no toolUse blocks", agent_id)
            break

        tool_result_blocks: List[Dict[str, Any]] = []
        for block in tool_use_blocks:
            tu = block["toolUse"]
            tool_name = tu.get("name", "")
            tool_use_id = tu.get("toolUseId", "")
            tool_input = tu.get("input", {}) or {}
            entry_start = time.time()

            # Fail-closed on allowlist.
            if tool_name not in allowed:
                msg = f"tool {tool_name!r} not in allowlist for agent {agent_id!r}"
                logger.warning(msg)
                tool_result_blocks.append(
                    _error_tool_result(tool_use_id, "tool_not_allowed", msg)
                )
                trace.append(
                    ToolTraceEntry(
                        tool_name=tool_name,
                        input_json=json.dumps(tool_input)[:500],
                        status="denied",
                        output_summary=msg,
                        elapsed_ms=int((time.time() - entry_start) * 1000),
                        error="tool_not_allowed",
                    )
                )
                continue

            # Validate input against the skill's Pydantic schema.
            specs = _load_skill_specs()
            spec = specs.get(tool_name)
            if not spec or spec["input_cls"] is None:
                msg = f"no input schema registered for tool {tool_name!r}"
                logger.error(msg)
                tool_result_blocks.append(
                    _error_tool_result(tool_use_id, "internal_error", msg)
                )
                trace.append(
                    ToolTraceEntry(
                        tool_name=tool_name,
                        input_json=json.dumps(tool_input)[:500],
                        status="error",
                        output_summary=msg,
                        elapsed_ms=int((time.time() - entry_start) * 1000),
                        error=msg,
                    )
                )
                continue

            input_cls = spec["input_cls"]
            try:
                payload = input_cls.model_validate(tool_input)
            except ValidationError as exc:
                msg = f"invalid input for {tool_name}: {exc.errors()[0].get('msg', 'validation error')}"
                logger.warning("agent=%s %s", agent_id, msg)
                tool_result_blocks.append(
                    _error_tool_result(tool_use_id, "validation_error", msg)
                )
                trace.append(
                    ToolTraceEntry(
                        tool_name=tool_name,
                        input_json=json.dumps(tool_input)[:500],
                        status="error",
                        output_summary=msg,
                        elapsed_ms=int((time.time() - entry_start) * 1000),
                        error=msg,
                    )
                )
                continue

            # Dispatch.
            try:
                skill_result = await spec["module"].run(payload, mcp=mcp)
            except Exception as exc:  # noqa: BLE001 - wrap into tool_result
                msg = f"{tool_name} raised: {type(exc).__name__}: {str(exc)[:200]}"
                logger.error("agent=%s %s", agent_id, msg)
                tool_result_blocks.append(
                    _error_tool_result(tool_use_id, "tool_execution_error", msg)
                )
                trace.append(
                    ToolTraceEntry(
                        tool_name=tool_name,
                        input_json=json.dumps(tool_input)[:500],
                        status="error",
                        output_summary=msg,
                        elapsed_ms=int((time.time() - entry_start) * 1000),
                        error=msg,
                    )
                )
                continue

            # Happy path: append a tool_result with the skill's output.
            output_json = _coerce_json(skill_result)
            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": output_json}],
                        "status": "success",
                    }
                }
            )
            trace.append(
                ToolTraceEntry(
                    tool_name=tool_name,
                    input_json=json.dumps(tool_input)[:500],
                    status="ok",
                    output_summary=json.dumps(output_json)[:300],
                    elapsed_ms=int((time.time() - entry_start) * 1000),
                )
            )

        messages.append({"role": "user", "content": tool_result_blocks})

        if total_tokens >= _MAX_TOTAL_TOKENS:
            logger.warning(
                "agent=%s token budget exhausted (%d); halting tool loop", agent_id, total_tokens
            )
            break

    return ToolLoopResult(
        text=last_text,
        trace=trace,
        tokens_used=total_tokens,
        stop_reason=stop_reason,
        loops=loop_i + 1,
    )


def _extract_text(result: Dict[str, Any]) -> str:
    """Pull assistant text from a converse response."""
    try:
        content = result["output"]["message"]["content"]
    except (KeyError, TypeError):
        return ""
    return _content_text(content)


def _content_text(content: Any) -> str:
    if isinstance(content, list):
        out = []
        for c in content:
            if isinstance(c, dict) and "text" in c:
                out.append(str(c["text"]))
        return "\n".join(out)
    return ""


def _extract_assistant_content(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return list(result["output"]["message"]["content"])
    except (KeyError, TypeError):
        return []


def _extract_tokens(result: Dict[str, Any]) -> int:
    if not isinstance(result, dict):
        return 0
    usage = result.get("usage", {}) or {}
    return int(usage.get("inputTokens", 0)) + int(usage.get("outputTokens", 0))


def _error_tool_result(tool_use_id: str, code: str, message: str) -> Dict[str, Any]:
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": [{"json": {"error": code, "message": message}}],
            "status": "error",
        }
    }


def _coerce_json(obj: Any) -> Any:
    """Convert a skill result (Pydantic model / dataclass / dict / primitive) to JSON."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__") and not isinstance(obj, (dict, list, str, int, float, bool)):
        try:
            return {k: _coerce_json(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        except Exception:  # noqa: BLE001
            return str(obj)
    if isinstance(obj, dict):
        return {k: _coerce_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_json(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
