"""M8 stage node functions. One file per stage per AC2.6."""

from m8_pipeline_engine.nodes.stage_1_intake import stage_1_intake
from m8_pipeline_engine.nodes.stage_2_crm_context import stage_2_crm_context
from m8_pipeline_engine.nodes.stage_3_market_data import stage_3_market_data
from m8_pipeline_engine.nodes.stage_4_news_sentiment import stage_4_news_sentiment
from m8_pipeline_engine.nodes.stage_5_sec_filings import stage_5_sec_filings
from m8_pipeline_engine.nodes.stage_6_transcript_analysis import (
    stage_6_transcript_analysis,
)
from m8_pipeline_engine.nodes.stage_7_data_quality_gate import (
    stage_7_data_quality_gate,
)
from m8_pipeline_engine.nodes.stage_8_financial_modeling import (
    stage_8_financial_modeling,
)
from m8_pipeline_engine.nodes.stage_9_dcf_valuation import stage_9_dcf_valuation
from m8_pipeline_engine.nodes.stage_10_comps_analysis import stage_10_comps_analysis
from m8_pipeline_engine.nodes.stage_11_monte_carlo import stage_11_monte_carlo
from m8_pipeline_engine.nodes.stage_12_cross_source_synthesis import (
    stage_12_cross_source_synthesis,
)
from m8_pipeline_engine.nodes.stage_13_analysis_review_gate import (
    stage_13_analysis_review_gate,
)
from m8_pipeline_engine.nodes.stage_14_thesis_generation import (
    stage_14_thesis_generation,
)
from m8_pipeline_engine.nodes.stage_15_catalyst_identification import (
    stage_15_catalyst_identification,
)
from m8_pipeline_engine.nodes.stage_16_risk_assessment import (
    stage_16_risk_assessment,
)
from m8_pipeline_engine.nodes.stage_17_rating_determination import (
    stage_17_rating_determination,
)
from m8_pipeline_engine.nodes.stage_18_target_price_calc import (
    stage_18_target_price_calc,
)
from m8_pipeline_engine.nodes.stage_19_brief_assembly import stage_19_brief_assembly
from m8_pipeline_engine.nodes.stage_20_compliance_check import (
    stage_20_compliance_check,
)
from m8_pipeline_engine.nodes.stage_21_anti_fabrication_check import (
    stage_21_anti_fabrication_check,
)
from m8_pipeline_engine.nodes.stage_22_crm_writeback import stage_22_crm_writeback
from m8_pipeline_engine.nodes.stage_23_delivery_notify import stage_23_delivery_notify

__all__ = [
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
]
