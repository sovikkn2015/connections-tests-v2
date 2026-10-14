"""Task 14 -- Stages 1-6 coverage + per-stage reason-code matrix."""

import pytest

from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient,
    GatewayError,
    LocalVendorAdapterResolver,
)
from m8_pipeline_engine.llm_client import FakeSonnetClient
from m8_pipeline_engine.nodes import (
    stage_1_intake,
    stage_2_crm_context,
    stage_3_market_data,
    stage_4_news_sentiment,
    stage_5_sec_filings,
    stage_6_transcript_analysis,
)
from tests.fixtures.m8_fixtures import make_initial_state


class _Adapter:
    name = "salesforce"
    def call(self, tool_name, payload): return {}


def _deps(llm=None, gateway=None, resolver=None):
    audit = FakeAuditClient()
    return {
        "audit": audit,
        "llm": llm or FakeSonnetClient(),
        "gateway": gateway or FakeGatewayClient(),
        "resolver": resolver or LocalVendorAdapterResolver({"salesforce.fetch_client": _Adapter()}),
        "config": None,
    }


def test_stage_1_completes():
    d = _deps()
    out = stage_1_intake(make_initial_state(), **d)
    assert "intake" in out and "instruments" in out
    assert len(d["audit"].entries) == 1


def test_stage_1_llm_timeout_sets_reason():
    d = _deps(llm=FakeSonnetClient(
        responses={"stage_1_intake": LlmTimeoutError("boom")}
    ))
    stage_1_intake(make_initial_state(), **d)
    entry = d["audit"].entries[0]
    assert entry["reason_code"] == "m8_llm_timeout"


def test_stage_1_llm_4xx_sets_reason():
    d = _deps(llm=FakeSonnetClient(
        responses={"stage_1_intake": LlmProviderError(400, "bad")}
    ))
    stage_1_intake(make_initial_state(), **d)
    assert d["audit"].entries[0]["reason_code"] == "m8_llm_4xx"


def test_stage_1_llm_5xx_sets_reason():
    d = _deps(llm=FakeSonnetClient(
        responses={"stage_1_intake": LlmProviderError(503, "down")}
    ))
    stage_1_intake(make_initial_state(), **d)
    assert d["audit"].entries[0]["reason_code"] == "m8_llm_5xx"


def test_stage_2_crm_context_allow_path():
    d = _deps()
    out = stage_2_crm_context(make_initial_state(), **d)
    assert "crm_context" in out
    entry = d["audit"].entries[0]
    assert entry["gateway_decision"] == "ALLOW"


def test_stage_2_authority_denied_sets_reason():
    d = _deps(gateway=FakeGatewayClient(
        call_responses={"salesforce.fetch_client": GatewayError("authority_denied")}
    ))
    stage_2_crm_context(make_initial_state(), **d)
    assert d["audit"].entries[0]["reason_code"] == "m8_compliance_denied"


def test_stage_2_mnpi_leakage_sets_reason():
    d = _deps(gateway=FakeGatewayClient(
        call_responses={"salesforce.fetch_client": GatewayError("mnpi_leakage_scan")}
    ))
    stage_2_crm_context(make_initial_state(), **d)
    assert d["audit"].entries[0]["reason_code"] == "m8_mnpi_leaked_through_gateway"


@pytest.mark.parametrize("fn", [
    stage_3_market_data, stage_4_news_sentiment,
    stage_5_sec_filings, stage_6_transcript_analysis,
])
def test_stage_stub_emits_audit(fn):
    d = _deps()
    fn(make_initial_state(), **d)
    assert len(d["audit"].entries) == 1
