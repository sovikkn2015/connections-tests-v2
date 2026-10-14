"""M8 stage 2: CRM context fetch via M6 gateway.

Calls salesforce.fetch_client + salesforce.fetch_household. M4 filters MNPI
before the response returns. No direct vendor call -- Steering Rule 4.
"""

from __future__ import annotations

from typing import Any

from m8_pipeline_engine.gateway_client import _call_with_branching
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_2_crm_context(
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
    routing = state.get("routing_decision")
    client_id = (
        (getattr(routing, "entities", {}) or {}).get("client_id") if routing else None
    ) or "unknown"

    reason_code = None
    crm_context: dict[str, Any] = {}
    rule_applied = wsp = None
    decision: str | None = None

    response, rc = _call_with_branching(
        gateway,
        resolver,
        trace_id=trace_id,
        firm_id=firm_id,
        aid_token=aid_token,
        tool_name="salesforce.fetch_client",
        mcp_server="salesforce",
        action="research.read",
        payload={"client_id": client_id},
        target={"canonical_type": "Client", "client_id": client_id},
        context={
            "pipeline_run_id": state.get("pipeline_run_id", ""),
            "stage_number": 2,
            "stage_name": "stage_2_crm_context",
        },
    )
    if rc and rc != "__ESCALATION__":
        reason_code = rc
    elif response is not None:
        decision = response.decision
        rule_applied = response.rule_applied
        wsp = response.wsp_section
        if isinstance(response.result, dict):
            crm_context = response.result

    output: dict[str, Any] = {"crm_context": crm_context}
    audit_stage(
        state,
        audit=audit,
        stage_number=2,
        stage_name="stage_2_crm_context",
        input_payload={"client_id_hash": len(client_id)},
        output_payload={"keys": sorted(crm_context.keys())},
        latency_ms=elapsed_ms(start),
        reason_code=reason_code,
        tool_name="salesforce.fetch_client",
        gateway_decision=decision,
        rule_applied=rule_applied,
        wsp_section=wsp,
    )
    return output


__all__ = ["stage_2_crm_context"]
