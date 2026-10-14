"""Task 1 -- GatewayClient Protocol + dataclass shape tests."""

import dataclasses

import pytest

from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient,
    GatewayClient,
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    LocalVendorAdapterResolver,
    VendorAdapterResolver,
    _call_with_branching,
)


class _Adapter:
    name = "fake"

    def call(self, tool_name, payload):
        return {"ok": True}


def test_gateway_request_is_dataclass():
    assert dataclasses.is_dataclass(GatewayRequest)
    assert GatewayRequest.__dataclass_params__.frozen


def test_gateway_response_is_dataclass():
    assert dataclasses.is_dataclass(GatewayResponse)
    assert GatewayResponse.__dataclass_params__.frozen


def test_fake_gateway_client_satisfies_protocol():
    assert isinstance(FakeGatewayClient(), GatewayClient)


def test_local_resolver_raises_on_missing():
    r = LocalVendorAdapterResolver({})
    with pytest.raises(GatewayError) as exc:
        r.resolve("unknown.tool")
    assert exc.value.reason == "invalid_request"


def test_local_resolver_returns_registered():
    adapter = _Adapter()
    r = LocalVendorAdapterResolver({"salesforce.fetch_client": adapter})
    assert r.resolve("salesforce.fetch_client") is adapter


def test_vendor_adapter_resolver_is_protocol():
    assert isinstance(LocalVendorAdapterResolver({}), VendorAdapterResolver)


def test_call_with_branching_allow_path():
    response = GatewayResponse(
        decision="ALLOW",
        result={"ok": True},
        liability_report=None,
        trace_id="t-1",
        latency_ms=1,
        provenance_head="a" * 64,
        rule_applied=None,
        wsp_section=None,
        reason=None,
    )
    fake = FakeGatewayClient(call_responses={"t.op": response})
    resolver = LocalVendorAdapterResolver({"t.op": _Adapter()})
    resp, rc = _call_with_branching(
        fake,
        resolver,
        trace_id="t-0000001",
        firm_id="f",
        aid_token="tok",
        tool_name="t.op",
        mcp_server="t",
        action="research.read",
        payload={},
        target={},
        context={},
    )
    assert resp is response
    assert rc is None


def test_call_with_branching_authority_denied_branch():
    fake = FakeGatewayClient(
        call_responses={"t.op": GatewayError("authority_denied")}
    )
    resolver = LocalVendorAdapterResolver({"t.op": _Adapter()})
    resp, rc = _call_with_branching(
        fake,
        resolver,
        trace_id="t-0000002",
        firm_id="f",
        aid_token="tok",
        tool_name="t.op",
        mcp_server="t",
        action="compliance.screen",
        payload={},
        target={},
        context={},
    )
    assert resp is None
    assert rc == "m8_compliance_denied"


def test_call_with_branching_mnpi_branch():
    fake = FakeGatewayClient(
        call_responses={"t.op": GatewayError("mnpi_leakage_scan")}
    )
    resolver = LocalVendorAdapterResolver({"t.op": _Adapter()})
    _, rc = _call_with_branching(
        fake,
        resolver,
        trace_id="t-0000003",
        firm_id="f",
        aid_token="tok",
        tool_name="t.op",
        mcp_server="t",
        action="research.read",
        payload={},
        target={},
        context={},
    )
    assert rc == "m8_mnpi_leaked_through_gateway"
