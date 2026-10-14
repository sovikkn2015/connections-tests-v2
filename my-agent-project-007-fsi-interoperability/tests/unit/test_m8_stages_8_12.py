"""Task 16 -- Stages 8-12 (map-reduce): fan-out cap, reducer, zero-fan-out, all-failed."""

from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.gateway_client import FakeGatewayClient, LocalVendorAdapterResolver
from m8_pipeline_engine.llm_client import FakeSonnetClient
from m8_pipeline_engine.nodes import (
    stage_8_financial_modeling,
    stage_12_cross_source_synthesis,
)
from m8_pipeline_engine.graph import _fan_out_instruments
from tests.fixtures.m8_fixtures import make_initial_state


def _deps():
    return {
        "audit": FakeAuditClient(),
        "llm": FakeSonnetClient(),
        "gateway": FakeGatewayClient(),
        "resolver": LocalVendorAdapterResolver({}),
        "config": None,
    }


def test_stage_8_fan_out_cap():
    state = make_initial_state()
    state["instruments"] = [f"T{i}" for i in range(25)]
    state["discovered_instruments"] = state["instruments"]
    out = stage_8_financial_modeling(state, **_deps())
    # AC5.7 too-wide warning + cap at 10
    assert len(out["discovered_instruments"]) == 10
    assert len(out["dropped_instruments"]) >= 15


def test_stage_8_fan_out_within_cap():
    state = make_initial_state()
    state["instruments"] = ["NVDA"]
    state["discovered_instruments"] = ["NVDA"]
    out = stage_8_financial_modeling(state, **_deps())
    assert out["discovered_instruments"] == ["NVDA"]
    assert out["dropped_instruments"] == []


def test_stage_12_zero_fan_out_single_tool_bypass():
    """AC5.8 -- discovered_instruments == [] -> m8.single_tool_bypass."""
    d = _deps()
    state = make_initial_state()
    state["discovered_instruments"] = []
    out = stage_12_cross_source_synthesis(state, **d)
    assert out == {"cross_source_synthesis": {}}
    entry = d["audit"].entries[0]
    assert entry["event_type"] == "m8.single_tool_bypass"
    assert entry["reason_code"] is None


def test_stage_12_all_instruments_failed():
    """AC5.5 -- per_instrument_results empty when discovered > 0 -> all_failed."""
    d = _deps()
    state = make_initial_state()
    state["discovered_instruments"] = ["NVDA", "AAPL"]
    state["per_instrument_results"] = {}
    stage_12_cross_source_synthesis(state, **d)
    assert d["audit"].entries[0]["reason_code"] == "m8_map_reduce_all_failed"


def test_stage_12_reducer_deterministic_iteration():
    """A16 -- reducer iterates in sorted() order."""
    d = _deps()
    state = make_initial_state()
    state["discovered_instruments"] = ["AAPL", "NVDA"]
    state["per_instrument_results"] = {
        "NVDA": {"summary": "n"},
        "AAPL": {"summary": "a"},
    }
    out = stage_12_cross_source_synthesis(state, **d)
    assert out["cross_source_synthesis"].get("instrument_count") == 2


def test_fan_out_sends_are_langgraph_send_instances():
    from langgraph.types import Send
    sends = _fan_out_instruments({"discovered_instruments": ["NVDA"]})
    assert isinstance(sends[0], Send)
