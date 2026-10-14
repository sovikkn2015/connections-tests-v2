"""M8 Pipeline Engine -- LangGraph 23-stage research pipeline with 3 HITL gates.

Public API surface (R15). 24 names in __all__ (v0.2.0 Req-Fix 4).
"""

from typing import Literal

from m8_pipeline_engine.audit_client import (
    AuditClient,
    AuditEmitError,
    FakeAuditClient,
    M10AuditClient,
)
from m8_pipeline_engine.errors import VALID_REASON_CODES
from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient,
    GatewayClient,
    GatewayRequest,
    GatewayResponse,
    M6GatewayClient,
)
from m8_pipeline_engine.graph import (
    research_pipeline,
    resume_from_gate,
    run,
)
from m8_pipeline_engine.llm_client import (
    FakeSonnetClient,
    LLMClient,
    SonnetClient,
)
from m8_pipeline_engine.models import (
    HitlApproval,
    HitlGatePayload,
    PipelineResult,
)
from m8_pipeline_engine.state import PipelineState


class PipelineConfig:  # pragma: no cover
    """Placeholder. Real sub-model arrives in M5 v0.4.0.

    Downstream code duck-types on attributes listed in the spec §Known Blockers
    row 1.
    """


SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"

STAGE_NAMES: tuple[str, ...] = (
    "stage_1_intake",
    "stage_2_crm_context",
    "stage_3_market_data",
    "stage_4_news_sentiment",
    "stage_5_sec_filings",
    "stage_6_transcript_analysis",
    "stage_7_data_quality_gate",
    "stage_8_financial_modeling",
    "stage_9_dcf_valuation",
    "stage_10_comps_analysis",
    "stage_11_monte_carlo",
    "stage_12_cross_source_synthesis",
    "stage_13_analysis_review_gate",
    "stage_14_thesis_generation",
    "stage_15_catalyst_identification",
    "stage_16_risk_assessment",
    "stage_17_rating_determination",
    "stage_18_target_price_calc",
    "stage_19_brief_assembly",
    "stage_20_compliance_check",
    "stage_21_anti_fabrication_check",
    "stage_22_crm_writeback",
    "stage_23_delivery_notify",
)
assert len(STAGE_NAMES) == 23, "STAGE_NAMES must have exactly 23 entries (R2)"

HITL_GATES: frozenset[int] = frozenset({7, 13, 21})

PIPELINE_NAMES: frozenset[str] = frozenset(
    {
        "m8.research_pipeline_1",
        "m8.research_pipeline_2",
        "m8.research_pipeline_3",
        "m8.research_single_tool",
    }
)


__all__ = [
    "research_pipeline",
    "run",
    "resume_from_gate",
    "PipelineState",
    "PipelineResult",
    "PipelineConfig",
    "STAGE_NAMES",
    "HITL_GATES",
    "PIPELINE_NAMES",
    "VALID_REASON_CODES",
    "SCHEMA_VERSION",
    "LLMClient",
    "SonnetClient",
    "FakeSonnetClient",
    "GatewayClient",
    "M6GatewayClient",
    "FakeGatewayClient",
    "GatewayRequest",
    "GatewayResponse",
    "AuditClient",
    "M10AuditClient",
    "FakeAuditClient",
    "HitlApproval",
    "HitlGatePayload",
]

assert len(__all__) == 24, (
    f"__all__ must have exactly 24 names (got {len(__all__)})"
)
