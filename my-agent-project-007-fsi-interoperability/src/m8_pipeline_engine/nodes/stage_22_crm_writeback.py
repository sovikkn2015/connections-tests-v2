"""M8 stage 22: CRM writeback via M6 gateway.

Writes final ResearchBrief to CRM. M4 re-screens MNPI.
"""

from __future__ import annotations

from typing import Any

from m8_pipeline_engine.gateway_client import _call_with_branching
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_22_crm_writeback(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    trace_id = state.get("trace_id", "unknown")
    firm_id = state.get("firm_id", "unknown")
    aid_token = state.get("supervisor_aid_token", "")

    draft = state.get("draft_brief") or state.get("final_brief")
    if draft is None:
        audit_stage(
            state,
            audit=audit,
            stage_number=22,
            stage_name="stage_22_crm_writeback",
            input_payload=None,
            output_payload=None,
            latency_ms=elapsed_ms(start),
            reason_code="m8_invalid_state",
        )
        return {}

    # Serialize briefly -- M6 performs MNPI re-screen
    payload: dict[str, Any] = {}
    if hasattr(draft, "model_dump"):
        payload = draft.model_dump(mode="json")
    elif isinstance(draft, dict):
        payload = dict(draft)

    response, rc = _call_with_branching(
        gateway,
        resolver,
        trace_id=trace_id,
        firm_id=firm_id,
        aid_token=aid_token,
        tool_name="salesforce.writeback_research_brief",
        mcp_server="salesforce",
        action="research.writeback",
        payload=payload,
        target={"canonical_type": "ResearchBrief"},
        context={
            "pipeline_run_id": state.get("pipeline_run_id", ""),
            "stage_number": 22,
            "stage_name": "stage_22_crm_writeback",
        },
    )

    output: dict[str, Any] = {}
    if rc is None and response is not None:
        output = {"final_brief": draft}
    elif rc and rc != "__ESCALATION__":
        audit_stage(
            state,
            audit=audit,
            stage_number=22,
            stage_name="stage_22_crm_writeback",
            input_payload={"keys": sorted(payload.keys()) if payload else []},
            output_payload=None,
            latency_ms=elapsed_ms(start),
            reason_code=rc,
            tool_name="salesforce.writeback_research_brief",
        )
        return output

    audit_stage(
        state,
        audit=audit,
        stage_number=22,
        stage_name="stage_22_crm_writeback",
        input_payload={"keys": sorted(payload.keys()) if payload else []},
        output_payload={"wrote_brief": bool(output.get("final_brief"))},
        latency_ms=elapsed_ms(start),
        tool_name="salesforce.writeback_research_brief",
        gateway_decision=response.decision if response else None,
    )
    return output


__all__ = ["stage_22_crm_writeback"]
