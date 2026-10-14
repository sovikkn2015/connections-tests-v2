"""Task 17 -- Stages 14-23 coverage."""

from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.gateway_client import FakeGatewayClient, LocalVendorAdapterResolver
from m8_pipeline_engine.llm_client import FakeSonnetClient
from m8_pipeline_engine.nodes import (
    stage_14_thesis_generation,
    stage_15_catalyst_identification,
    stage_16_risk_assessment,
    stage_17_rating_determination,
    stage_18_target_price_calc,
    stage_19_brief_assembly,
    stage_20_compliance_check,
    stage_21_anti_fabrication_check,
    stage_22_crm_writeback,
    stage_23_delivery_notify,
)
from tests.fixtures.m8_fixtures import make_initial_state


class _Adapter:
    name = "x"
    def call(self, tool_name, payload): return {}


def _deps(gateway=None):
    return {
        "audit": FakeAuditClient(),
        "llm": FakeSonnetClient(),
        "gateway": gateway or FakeGatewayClient(),
        "resolver": LocalVendorAdapterResolver({
            "compliance.screen": _Adapter(),
            "salesforce.writeback_research_brief": _Adapter(),
        }),
        "config": None,
    }


def test_stage_17_emits_valid_rating():
    out = stage_17_rating_determination(make_initial_state(), **_deps())
    assert out["rating"] in {"strong_buy", "buy", "hold", "sell", "strong_sell"}


def test_stage_18_empty_instruments_returns_none():
    out = stage_18_target_price_calc(make_initial_state(), **_deps())
    assert out["target_price"] is None


def test_stage_18_averages_present_prices():
    state = make_initial_state()
    state["per_instrument_results"] = {
        "NVDA": {"dcf_target": 100.0},
        "AAPL": {"dcf_target": 200.0},
    }
    out = stage_18_target_price_calc(state, **_deps())
    assert out["target_price"] == 150.0


def test_stage_19_builds_brief():
    state = make_initial_state()
    state["thesis"] = "NVDA grows"
    state["rating"] = "buy"
    state["data_sources"] = []
    out = stage_19_brief_assembly(state, **_deps())
    assert "draft_brief" in out


def test_stage_20_no_llm_called():
    """Stage 20 NEVER calls Sonnet -- only M6 compliance.screen (A19)."""
    d = _deps()
    state = make_initial_state()
    stage_20_compliance_check(state, **d)
    # FakeSonnetClient records() list should stay empty
    assert d["llm"].recorded == []


def test_stage_20_allow_path():
    d = _deps()
    state = make_initial_state()
    out = stage_20_compliance_check(state, **d)
    assert out["compliance_decision"] == "ALLOW"


def test_stage_22_writeback_completes():
    d = _deps()
    state = make_initial_state()
    state["draft_brief"] = {"brief_id": "1"}
    out = stage_22_crm_writeback(state, **d)
    assert "final_brief" in out


def test_stage_23_terminal():
    d = _deps()
    out = stage_23_delivery_notify(make_initial_state(), **d)
    assert out["pipeline_status"] == "completed"


def test_stage_14_llm_bearing():
    out = stage_14_thesis_generation(make_initial_state(), **_deps())
    assert "thesis" in out


def test_stage_15_16_stubs_emit_audit():
    for fn in (stage_15_catalyst_identification, stage_16_risk_assessment):
        d = _deps()
        fn(make_initial_state(), **d)
        assert len(d["audit"].entries) == 1
