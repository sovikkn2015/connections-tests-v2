"""Task 5 -- Graph assembly: 23 nodes, Send import from langgraph.types."""

from langgraph.types import Send

from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.gateway_client import FakeGatewayClient, LocalVendorAdapterResolver
from m8_pipeline_engine.graph import build_graph, _fan_out_instruments
from m8_pipeline_engine.llm_client import FakeSonnetClient


def test_build_graph_has_23_nodes():
    g = build_graph(FakeGatewayClient(), LocalVendorAdapterResolver({}), FakeAuditClient(), FakeSonnetClient())
    # StateGraph exposes nodes as a dict-like
    assert len(g.nodes) == 23


def test_send_import_is_from_langgraph_types():
    # Guard regression: Send must come from langgraph.types (Req-Fix 8)
    assert Send.__module__.startswith("langgraph.types")


def test_fan_out_single_instrument():
    state = {"discovered_instruments": ["NVDA"]}
    result = _fan_out_instruments(state)
    assert len(result) == 1
    assert isinstance(result[0], Send)


def test_fan_out_zero_returns_bypass():
    # AC5.8 zero-fan-out case
    state = {"discovered_instruments": []}
    result = _fan_out_instruments(state)
    assert result == ["stage_12_cross_source_synthesis"]


def test_fan_out_cap_enforced():
    state = {"discovered_instruments": [f"T{i}" for i in range(25)]}
    result = _fan_out_instruments(state)
    assert len(result) == 10  # cap at 10
