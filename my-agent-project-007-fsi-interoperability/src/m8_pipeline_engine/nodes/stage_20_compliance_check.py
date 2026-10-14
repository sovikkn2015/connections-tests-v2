"""M8 stage 20: Compliance screening via M6 -- OPA/Rego, NO LLM.

Steering Rule 5 + Rule 14. Branches on GatewayError.reason.
"""

from __future__ import annotations

from typing import Any

from m8_pipeline_engine.gateway_client import _call_with_branching
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_20_compliance_check(
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

    draft = state.get("draft_brief")
    ticker = ""
    if draft is not None:
        sid = getattr(draft, "security_identifier", None)
        if sid is not None:
            ticker = getattr(sid, "ticker", "") or ""

    routing = state.get("routing_decision")
    client_id = ""
    if routing is not None:
        entities = getattr(routing, "entities", {}) or {}
        client_id = entities.get("client_id", "") or ""

    response, rc = _call_with_branching(
        gateway,
        resolver,
        trace_id=trace_id,
        firm_id=firm_id,
        aid_token=aid_token,
        tool_name="compliance.screen",
        mcp_server="compliance",
        action="compliance.screen",
        payload={"ticker": ticker, "client_id": client_id},
        target={"canonical_type": "ResearchBrief", "ticker": ticker, "client_id": client_id},
        context={
            "pipeline_run_id": state.get("pipeline_run_id", ""),
            "stage_number": 20,
            "stage_name": "stage_20_compliance_check",
        },
    )

    output: dict[str, Any] = {}
    if rc == "m8_compliance_denied":
        output = {
            "compliance_decision": "DENY",
            "compliance_escalation": False,
        }
        audit_stage(
            state,
            audit=audit,
            stage_number=20,
            stage_name="stage_20_compliance_check",
            input_payload={"ticker": ticker},
            output_payload=output,
            latency_ms=elapsed_ms(start),
            reason_code="m8_compliance_denied",
            tool_name="compliance.screen",
            gateway_decision="DENY",
        )
        return output
    if rc == "__ESCALATION__":
        output = {
            "compliance_decision": "ESCALATE",
            "compliance_escalation": True,
            "compliance_rule_applied": (response.rule_applied if response else None),
            "compliance_wsp_section": (response.wsp_section if response else None),
        }
        audit_stage(
            state,
            audit=audit,
            stage_number=20,
            stage_name="stage_20_compliance_check",
            input_payload={"ticker": ticker},
            output_payload=output,
            latency_ms=elapsed_ms(start),
            tool_name="compliance.screen",
            gateway_decision="ESCALATE",
            rule_applied=output["compliance_rule_applied"],
            wsp_section=output["compliance_wsp_section"],
        )
        return output
    if rc:  # other failure reason
        output = {
            "compliance_decision": "DENY",
            "compliance_escalation": False,
        }
        audit_stage(
            state,
            audit=audit,
            stage_number=20,
            stage_name="stage_20_compliance_check",
            input_payload={"ticker": ticker},
            output_payload=output,
            latency_ms=elapsed_ms(start),
            reason_code=rc,
            tool_name="compliance.screen",
        )
        return output

    # ALLOW path
    output = {
        "compliance_decision": "ALLOW",
        "compliance_escalation": False,
        "compliance_rule_applied": (response.rule_applied if response else None),
        "compliance_wsp_section": (response.wsp_section if response else None),
    }
    audit_stage(
        state,
        audit=audit,
        stage_number=20,
        stage_name="stage_20_compliance_check",
        input_payload={"ticker": ticker},
        output_payload=output,
        latency_ms=elapsed_ms(start),
        tool_name="compliance.screen",
        gateway_decision="ALLOW",
        rule_applied=output["compliance_rule_applied"],
        wsp_section=output["compliance_wsp_section"],
    )
    return output


__all__ = ["stage_20_compliance_check"]
