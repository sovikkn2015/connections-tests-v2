"""Task 17 -- Anti-fabrication: numeric-token provenance."""

import uuid
from datetime import datetime, timezone

from m3_schema_registry import ResearchBrief, ResearchSource

from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.gateway_client import FakeGatewayClient, LocalVendorAdapterResolver
from m8_pipeline_engine.llm_client import FakeSonnetClient
from m8_pipeline_engine.nodes import stage_21_anti_fabrication_check
from tests.fixtures.m8_fixtures import make_initial_state


def _deps():
    return {
        "audit": FakeAuditClient(),
        "llm": FakeSonnetClient(),
        "gateway": FakeGatewayClient(),
        "resolver": LocalVendorAdapterResolver({}),
        "config": None,
    }


def _brief(summary, thesis):
    return ResearchBrief(
        brief_id=uuid.uuid4(),
        analyst_id="a",
        rating="buy",
        summary=summary,
        thesis=thesis,
        catalysts=[],
        risks=[],
        sources=[ResearchSource(source_type="crm_data", description="seed 100 200")],
        pipeline_run_id="r",
        hitl_gates_passed=[],
        anti_fabrication_score=1.0,
        created_at=datetime.now(timezone.utc),
        trace_id="t",
    )


def test_anti_fab_passes_when_numbers_in_sources():
    state = make_initial_state()
    state["draft_brief"] = _brief("Trade at 100", "Target 200")
    state["data_sources"] = [
        ResearchSource(source_type="crm_data", description="seed 100 200")
    ]
    d = _deps()
    out = stage_21_anti_fabrication_check(state, **d)
    assert out["anti_fabrication_failures"] == []


def test_anti_fab_flags_missing_numbers():
    state = make_initial_state()
    state["draft_brief"] = _brief("Trade at 999", "Target 888")
    state["data_sources"] = [
        ResearchSource(source_type="crm_data", description="seed 100 200")
    ]
    d = _deps()
    out = stage_21_anti_fabrication_check(state, **d)
    tokens = {f["token"] for f in out["anti_fabrication_failures"]}
    assert "999" in tokens
    assert "888" in tokens
    assert d["audit"].entries[0]["reason_code"] == "m8_anti_fabrication_failed"
