"""
M8 — Pipeline Engine (Research Specialist Brain).

23-stage LangGraph research pipeline with:
  - 3 HITL gates (tamper-proof SHA-256 approval tokens)
  - DynamoDB/PostgreSQL checkpointing (pluggable)
  - Map-reduce multi-source synthesis
  - Per-stage token budgets (20 min max total)
  - Async execution (max 3 concurrent per tenant)
  - All tool calls through M6 Trust-Aware Gateway ONLY

Stack: Python 3.12+, LangGraph, Pydantic v2, FastAPI.
"""

from m8_pipeline_engine.models import (
    GateStatus,
    HITLGate,
    PipelineState,
    PipelineStatus,
    PipelineSummary,
    ResearchQuery,
    SecurityIdentifier,
    SourceData,
    StageResult,
    TokenBudget,
)
from m8_pipeline_engine.hitl import HITLManager
from m8_pipeline_engine.pipeline import ResearchPipeline

__all__ = [
    "GateStatus",
    "HITLGate",
    "HITLManager",
    "PipelineState",
    "PipelineStatus",
    "PipelineSummary",
    "ResearchPipeline",
    "ResearchQuery",
    "SecurityIdentifier",
    "SourceData",
    "StageResult",
    "TokenBudget",
]
