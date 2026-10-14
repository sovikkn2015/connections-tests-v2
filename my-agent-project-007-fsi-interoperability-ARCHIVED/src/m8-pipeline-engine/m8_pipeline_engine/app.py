"""
M8 FastAPI Application — Pipeline Engine REST endpoints.

Endpoints:
  POST /pipeline/run          — start a new pipeline (async, returns run_id)
  GET  /pipeline/status/{id}  — check pipeline status
  POST /pipeline/gate/{id}/{gate}/approve — approve HITL gate
  POST /pipeline/gate/{id}/{gate}/reject  — reject HITL gate
  GET  /health                — health check

All secrets from Vault/Secrets Manager (Rule 16). No credentials in code.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from m8_pipeline_engine.models import (
    PipelineStatus,
    ResearchQuery,
)
from m8_pipeline_engine.pipeline import ResearchPipeline

logger = logging.getLogger(__name__)

app = FastAPI(
    title="M8 Pipeline Engine",
    description="23-stage LangGraph research pipeline with HITL gates",
    version="0.1.0",
)

# Pipeline instance — initialized on startup
_pipeline: ResearchPipeline | None = None


def get_pipeline() -> ResearchPipeline:
    """Get or create the pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ResearchPipeline()
    return _pipeline


def set_pipeline(pipeline: ResearchPipeline) -> None:
    """Set pipeline instance (for testing)."""
    global _pipeline
    _pipeline = pipeline


# ── Request/Response Models ──────────────────────────────────────


class RunRequest(BaseModel):
    """Request to start a pipeline run."""
    raw_query: str = Field(..., min_length=1)
    ticker: Optional[str] = None
    topic: Optional[str] = None
    depth: str = Field(default="standard")
    requesting_user_id: str = ""
    tenant_id: str = ""


class RunResponse(BaseModel):
    """Response after starting a pipeline run."""
    run_id: str
    status: str
    message: str


class GateActionRequest(BaseModel):
    """Request to approve or reject a HITL gate."""
    approver_id: str = Field(..., min_length=1)
    reason: str = ""


class StatusResponse(BaseModel):
    """Pipeline status response."""
    run_id: str
    status: str
    current_stage: int
    current_stage_name: str
    total_tokens_used: int
    total_duration_ms: float
    hitl_gates: list[dict[str, Any]]
    error: Optional[str] = None
    brief: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    module: str
    version: str


# ── Endpoints ────────────────────────────────────────────────────


@app.post("/pipeline/run", response_model=RunResponse)
async def start_pipeline(request: RunRequest) -> RunResponse:
    """Start a new research pipeline execution (async)."""
    pipeline = get_pipeline()

    query = ResearchQuery(
        raw_query=request.raw_query,
        ticker=request.ticker,
        topic=request.topic,
        depth=request.depth,
        requesting_user_id=request.requesting_user_id,
        tenant_id=request.tenant_id,
    )

    try:
        state = await pipeline.start(query)
        # Run pipeline asynchronously — first segment until HITL gate
        state = await pipeline.run(state)
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except Exception as exc:
        logger.exception("Pipeline start failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return RunResponse(
        run_id=state.run_id,
        status=state.status.value,
        message=f"Pipeline {state.status.value} at stage {state.current_stage}",
    )


@app.get("/pipeline/status/{run_id}", response_model=StatusResponse)
async def get_status(run_id: str) -> StatusResponse:
    """Check pipeline execution status."""
    pipeline = get_pipeline()
    state = await pipeline.get_status(run_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return StatusResponse(
        run_id=state.run_id,
        status=state.status.value,
        current_stage=state.current_stage,
        current_stage_name=state.current_stage_name,
        total_tokens_used=state.total_tokens_used,
        total_duration_ms=state.total_duration_ms,
        hitl_gates=[g.model_dump() for g in state.hitl_gates],
        error=state.error,
        brief=state.brief if state.status == PipelineStatus.completed else None,
    )


@app.post("/pipeline/gate/{run_id}/{gate_id}/approve")
async def approve_gate(
    run_id: str,
    gate_id: str,
    request: GateActionRequest,
) -> dict[str, Any]:
    """Approve a HITL gate and resume pipeline."""
    pipeline = get_pipeline()

    try:
        state = await pipeline.approve_gate(
            run_id, gate_id, request.approver_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "run_id": state.run_id,
        "status": state.status.value,
        "current_stage": state.current_stage,
        "message": f"Gate {gate_id} approved. Pipeline resumed.",
    }


@app.post("/pipeline/gate/{run_id}/{gate_id}/reject")
async def reject_gate(
    run_id: str,
    gate_id: str,
    request: GateActionRequest,
) -> dict[str, Any]:
    """Reject a HITL gate. Pipeline stops."""
    pipeline = get_pipeline()

    try:
        state = await pipeline.reject_gate(
            run_id, gate_id, request.approver_id, request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "run_id": state.run_id,
        "status": state.status.value,
        "message": f"Gate {gate_id} rejected. Pipeline stopped.",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        module="m8-pipeline-engine",
        version="0.1.0",
    )
