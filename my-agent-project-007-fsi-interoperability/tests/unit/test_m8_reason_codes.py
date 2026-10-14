"""Task 15 -- Every VALID_REASON_CODES + VALID_GATEWAY_REASONS exercised."""

import pytest

from m8_pipeline_engine.errors import VALID_REASON_CODES
from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient,
    GatewayError,
    LocalVendorAdapterResolver,
    _call_with_branching,
)


# M6's VALID_GATEWAY_REASONS (kept local; M8 must not import m6)
M6_REASONS = frozenset({
    "invalid_identity",
    "authority_denied",
    "authority_escalated",
    "mnpi_filter_error",
    "circuit_open",
    "rate_limited",
    "vendor_unavailable",
    "vendor_error",
    "mnpi_leakage_scan",
    "audit_failed",
    "invalid_request",
})


def test_all_reason_codes_are_recognized():
    assert len(VALID_REASON_CODES) == 20
    # spot-check a handful
    required = {
        "m8_stage_failed",
        "m8_llm_timeout",
        "m8_llm_5xx",
        "m8_llm_4xx",
        "m8_llm_malformed_output",
        "m8_checkpoint_write_failed",
        "m8_hitl_denied",
        "m8_hitl_timeout",
        "m8_hitl_role_mismatch",
        "m8_hitl_token_expired",
        "m8_compliance_denied",
        "m8_audit_write_failed",
        "m8_mnpi_leaked_through_gateway",
        "m8_map_reduce_too_wide",
        "m8_map_reduce_all_failed",
        "m8_token_budget_exceeded",
        "m8_wall_clock_exceeded",
        "m8_tenant_concurrency_exceeded",
        "m8_anti_fabrication_failed",
        "m8_invalid_state",
    }
    assert required == VALID_REASON_CODES


@pytest.mark.parametrize("reason", sorted(M6_REASONS))
def test_every_gateway_reason_maps_to_known_branch(reason):
    """AC7.11 -- every M6 reason string maps deterministically."""

    class _Adapter:
        name = "x"

        def call(self, tool_name, payload):
            return {}

    fake = FakeGatewayClient(call_responses={"t.op": GatewayError(reason)})
    resolver = LocalVendorAdapterResolver({"t.op": _Adapter()})
    _, rc = _call_with_branching(
        fake,
        resolver,
        trace_id="t-00000001",
        firm_id="f",
        aid_token="tok",
        tool_name="t.op",
        mcp_server="t",
        action="research.read",
        payload={},
        target={},
        context={},
    )
    # Either a known reason_code or escalation sentinel
    allowed = VALID_REASON_CODES | {"__ESCALATION__"}
    assert rc in allowed, f"reason={reason!r} rc={rc!r}"
