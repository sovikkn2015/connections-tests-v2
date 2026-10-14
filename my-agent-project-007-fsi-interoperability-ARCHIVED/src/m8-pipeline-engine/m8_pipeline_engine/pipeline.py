"""
M8 Pipeline Engine — LangGraph 23-stage research pipeline.

The pipeline is defined as a LangGraph StateGraph (Rule 1).
No custom pipeline engines. LangGraph provides:
  - Durable checkpointing (DynamoDB/PostgreSQL — Rule 2)
  - Time-travel debugging (replay from any stage)
  - Human-in-the-loop as first-class primitive (Rule 3)

This module provides a lightweight graph abstraction that mirrors
LangGraph's StateGraph API pattern, enabling testing without requiring
langgraph to be installed. In production, swap to real LangGraph.

Async execution: supervisor dispatches and polls (Rule 11).
Max 3 concurrent pipelines per tenant (configurable).

Backends:
  InMemoryCheckpoint (default) for dev/test.
  DynamoDBCheckpoint for production (M8_CHECKPOINT_BACKEND=dynamodb).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable, Optional

from m8_pipeline_engine.hitl import GATE_DEFINITIONS, HITLManager
from m8_pipeline_engine.models import (
    DEFAULT_HITL_TIMEOUT_SECONDS,
    GateStatus,
    LLMProvider,
    MAX_CONCURRENT_PIPELINES_PER_TENANT,
    PIPELINE_ALERT_THRESHOLD_SECONDS,
    PIPELINE_MAX_DURATION_SECONDS,
    PipelineState,
    PipelineStatus,
    PipelineSummary,
    ResearchQuery,
)
from m8_pipeline_engine.stages import STAGE_REGISTRY

logger = logging.getLogger(__name__)

# Type alias for stage functions
StageFn = Callable[
    [PipelineState, Optional[LLMProvider], str],
    Awaitable[PipelineState],
]


# ── Checkpoint Backend (Rule 2) ─────────────────────────────────


class CheckpointBackend:
    """
    Pluggable checkpoint backend interface (Rule 2).

    In-memory for dev/test. DynamoDB for cloud. PostgreSQL for on-prem.
    Mirrors LangGraph's native checkpointing API.
    """

    async def save(self, run_id: str, state: PipelineState) -> None:
        """Persist pipeline state."""
        raise NotImplementedError

    async def load(self, run_id: str) -> PipelineState | None:
        """Load pipeline state. Returns None if not found."""
        raise NotImplementedError

    async def delete(self, run_id: str) -> None:
        """Delete checkpoint."""
        raise NotImplementedError


class InMemoryCheckpoint(CheckpointBackend):
    """In-memory checkpoint for development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, PipelineState] = {}

    async def save(self, run_id: str, state: PipelineState) -> None:
        self._store[run_id] = state.model_copy(deep=True)

    async def load(self, run_id: str) -> PipelineState | None:
        s = self._store.get(run_id)
        return s.model_copy(deep=True) if s else None

    async def delete(self, run_id: str) -> None:
        self._store.pop(run_id, None)


class DynamoDBCheckpoint(CheckpointBackend):
    """
    DynamoDB-backed checkpoint for production (Rule 2).

    Activated when M8_CHECKPOINT_BACKEND=dynamodb and M8_DYNAMODB_TABLE is set.
    Uses boto3 DynamoDB. Credentials from IAM role / env (Rule 20).

    Falls back to in-memory on connection failure.
    """

    def __init__(self, table_name: str, dynamodb_client: Any = None) -> None:
        self._table_name = table_name
        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for DynamoDB checkpoint backend. "
                    "Install with: pip install boto3"
                )
            self._client = boto3.resource("dynamodb").Table(table_name)
        self._fallback: InMemoryCheckpoint | None = None
        logger.info("DynamoDBCheckpoint initialized: table=%s", table_name)

    def _get_fallback(self) -> InMemoryCheckpoint:
        if self._fallback is None:
            self._fallback = InMemoryCheckpoint()
            logger.warning("DynamoDBCheckpoint: activated in-memory fallback")
        return self._fallback

    async def save(self, run_id: str, state: PipelineState) -> None:
        try:
            self._client.put_item(Item={
                "run_id": run_id,
                "state_json": state.model_dump_json(),
                "tenant_id": state.tenant_id,
                "status": state.status.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.error("DynamoDB checkpoint save failed: %s. Using fallback.", exc)
            await self._get_fallback().save(run_id, state)

    async def load(self, run_id: str) -> PipelineState | None:
        try:
            resp = self._client.get_item(Key={"run_id": run_id})
            item = resp.get("Item")
            if item is None:
                if self._fallback:
                    return await self._fallback.load(run_id)
                return None
            return PipelineState.model_validate_json(item["state_json"])
        except Exception as exc:
            logger.error("DynamoDB checkpoint load failed: %s. Using fallback.", exc)
            return await self._get_fallback().load(run_id)

    async def delete(self, run_id: str) -> None:
        try:
            self._client.delete_item(Key={"run_id": run_id})
        except Exception as exc:
            logger.error("DynamoDB checkpoint delete failed: %s. Using fallback.", exc)
            await self._get_fallback().delete(run_id)


def create_checkpoint_backend() -> CheckpointBackend:
    """
    Factory: select checkpoint backend based on env var.

    M8_CHECKPOINT_BACKEND: "memory" (default) or "dynamodb"
    M8_DYNAMODB_TABLE: DynamoDB table name (required for dynamodb)
    """
    backend = os.environ.get("M8_CHECKPOINT_BACKEND", "memory").lower()
    if backend == "dynamodb":
        table_name = os.environ.get("M8_DYNAMODB_TABLE")
        if not table_name:
            logger.warning(
                "M8_CHECKPOINT_BACKEND=dynamodb but M8_DYNAMODB_TABLE not set. "
                "Falling back to in-memory checkpoint."
            )
            return InMemoryCheckpoint()
        try:
            checkpoint = DynamoDBCheckpoint(table_name=table_name)
            logger.info("M8 checkpoint backend: dynamodb (table=%s)", table_name)
            return checkpoint
        except Exception as exc:
            logger.error(
                "Failed to initialize DynamoDB checkpoint: %s. "
                "Falling back to in-memory.",
                exc,
            )
            return InMemoryCheckpoint()
    logger.info("M8 checkpoint backend: memory")
    return InMemoryCheckpoint()


# ── Concurrency Limiter (Rule 11) ───────────────────────────────


class TenantConcurrencyLimiter:
    """
    Enforce max concurrent pipelines per tenant (Rule 11).

    Default: 3 concurrent. Queued beyond limit.
    """

    def __init__(
        self, max_concurrent: int = MAX_CONCURRENT_PIPELINES_PER_TENANT,
    ) -> None:
        self._max = max_concurrent
        self._active: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def acquire(self, tenant_id: str) -> bool:
        """Try to acquire a slot. Returns False if at limit."""
        async with self._lock:
            if self._active[tenant_id] >= self._max:
                return False
            self._active[tenant_id] += 1
            return True

    async def release(self, tenant_id: str) -> None:
        """Release a slot."""
        async with self._lock:
            self._active[tenant_id] = max(0, self._active[tenant_id] - 1)

    def active_count(self, tenant_id: str) -> int:
        return self._active.get(tenant_id, 0)


# ── Research Pipeline (LangGraph StateGraph pattern) ─────────────


class ResearchPipeline:
    """
    23-stage research pipeline defined as a LangGraph-compatible graph.

    Mirrors LangGraph's StateGraph API:
      - add_node(name, fn) — register a stage function
      - add_edge(from, to) — define transitions
      - compile() — build the executable graph
      - invoke(state) — run the pipeline

    In production, this class wraps real LangGraph StateGraph.
    For testing, it provides an equivalent lightweight implementation.
    """

    def __init__(
        self,
        llm: LLMProvider | None = None,
        checkpoint: CheckpointBackend | None = None,
        hitl_manager: HITLManager | None = None,
        m6_gateway_url: str = "",
        max_duration_seconds: int = PIPELINE_MAX_DURATION_SECONDS,
        alert_threshold_seconds: int = PIPELINE_ALERT_THRESHOLD_SECONDS,
    ) -> None:
        self._llm = llm
        self._checkpoint = checkpoint or InMemoryCheckpoint()
        self._hitl = hitl_manager or HITLManager()
        self._m6_url = m6_gateway_url
        self._max_duration = max_duration_seconds
        self._alert_threshold = alert_threshold_seconds
        self._concurrency = TenantConcurrencyLimiter()

        # Build the graph from STAGE_REGISTRY
        self._nodes: list[tuple[int, str, StageFn]] = []
        self._hitl_gates: dict[int, tuple[int, str]] = {}

        for stage_num, stage_name, stage_fn in STAGE_REGISTRY:
            self._nodes.append((stage_num, stage_name, stage_fn))

        # Register HITL gates by the stage they follow
        for gate_num, gate_name, after_stage in GATE_DEFINITIONS:
            self._hitl_gates[after_stage] = (gate_num, gate_name)

    @property
    def stage_count(self) -> int:
        """Total number of stages in the pipeline."""
        return len(self._nodes)

    @property
    def hitl_gate_count(self) -> int:
        """Number of HITL gates."""
        return len(self._hitl_gates)

    async def start(self, query: ResearchQuery) -> PipelineState:
        """
        Start a new pipeline execution (async — Rule 11).

        Returns initial PipelineState with run_id for polling.
        Raises RuntimeError if tenant concurrency limit exceeded.
        """
        tenant_id = query.tenant_id or "default"

        if not await self._concurrency.acquire(tenant_id):
            raise RuntimeError(
                f"Tenant {tenant_id} has reached max concurrent pipelines "
                f"({MAX_CONCURRENT_PIPELINES_PER_TENANT}). Queued."
            )

        state = PipelineState(
            tenant_id=tenant_id,
            requesting_user_id=query.requesting_user_id,
            trace_id=query.trace_id,
            query=query,
            status=PipelineStatus.running,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        await self._checkpoint.save(state.run_id, state)
        logger.info(
            "Pipeline started: run_id=%s, tenant=%s, query=%s",
            state.run_id, tenant_id, query.raw_query[:80],
        )
        return state

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Execute the full pipeline from current state.

        Pauses at HITL gates. Resumes from checkpoint on restart.
        Enforces 20-minute timeout (Rule 4).
        """
        pipeline_start = time.monotonic()

        for stage_num, stage_name, stage_fn in self._nodes:
            # Skip already-completed stages (resume from checkpoint)
            if stage_num <= state.current_stage:
                continue

            # Check pipeline timeout (Rule 4)
            elapsed = time.monotonic() - pipeline_start
            if elapsed > self._max_duration:
                state = state.model_copy(update={
                    "status": PipelineStatus.timed_out,
                    "error": f"Pipeline exceeded {self._max_duration}s timeout",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                await self._checkpoint.save(state.run_id, state)
                logger.error(
                    "Pipeline timed out: run_id=%s, elapsed=%.1fs",
                    state.run_id, elapsed,
                )
                break

            # Alert threshold (Rule 4)
            if elapsed > self._alert_threshold:
                logger.warning(
                    "Pipeline approaching timeout: run_id=%s, elapsed=%.1fs",
                    state.run_id, elapsed,
                )

            # Execute stage
            try:
                state = await stage_fn(state, self._llm, self._m6_url)
            except Exception as exc:
                state = state.model_copy(update={
                    "status": PipelineStatus.failed,
                    "error": f"Stage {stage_name} failed: {exc}",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                await self._checkpoint.save(state.run_id, state)
                logger.exception(
                    "Stage failed: run_id=%s, stage=%s",
                    state.run_id, stage_name,
                )
                break

            # Checkpoint after every stage (Rule 2)
            await self._checkpoint.save(state.run_id, state)

            # Check for HITL gate after this stage
            if stage_num in self._hitl_gates:
                gate_num, gate_name = self._hitl_gates[stage_num]
                gate = self._hitl.create_gate(
                    gate_number=gate_num,
                    gate_name=gate_name,
                    context_summary=f"Completed through stage {stage_num}",
                )
                state = state.model_copy(update={
                    "status": PipelineStatus.paused_hitl,
                    "hitl_gates": [*state.hitl_gates, gate],
                })
                await self._checkpoint.save(state.run_id, state)
                logger.info(
                    "Pipeline paused at HITL gate: run_id=%s, gate=%s",
                    state.run_id, gate_name,
                )
                break  # Pause — wait for approval

        # Calculate total duration
        total_ms = (time.monotonic() - pipeline_start) * 1000
        state = state.model_copy(update={"total_duration_ms": total_ms})
        await self._checkpoint.save(state.run_id, state)

        # Release concurrency slot if pipeline is done
        if state.status in (
            PipelineStatus.completed,
            PipelineStatus.failed,
            PipelineStatus.timed_out,
        ):
            await self._concurrency.release(state.tenant_id)

        return state

    async def approve_gate(
        self,
        run_id: str,
        gate_id: str,
        approver_id: str,
    ) -> PipelineState:
        """
        Approve a HITL gate and resume pipeline execution.

        Generates tamper-proof token: SHA-256(gate_id + approver_id + ts).
        """
        state = await self._checkpoint.load(run_id)
        if not state:
            raise ValueError(f"Pipeline run {run_id} not found")

        if state.status != PipelineStatus.paused_hitl:
            raise ValueError(
                f"Pipeline {run_id} is not paused at HITL gate "
                f"(status: {state.status.value})"
            )

        # Find and approve the gate
        updated_gates = []
        gate_found = False
        for gate in state.hitl_gates:
            if gate.gate_id == gate_id:
                gate = self._hitl.approve_gate(gate, approver_id)
                gate_found = True
            updated_gates.append(gate)

        if not gate_found:
            raise ValueError(f"Gate {gate_id} not found in pipeline {run_id}")

        state = state.model_copy(update={
            "status": PipelineStatus.running,
            "hitl_gates": updated_gates,
        })
        await self._checkpoint.save(run_id, state)

        # Resume pipeline execution
        return await self.run(state)

    async def reject_gate(
        self,
        run_id: str,
        gate_id: str,
        approver_id: str,
        reason: str = "",
    ) -> PipelineState:
        """Reject a HITL gate. Pipeline stops."""
        state = await self._checkpoint.load(run_id)
        if not state:
            raise ValueError(f"Pipeline run {run_id} not found")

        updated_gates = []
        gate_found = False
        for gate in state.hitl_gates:
            if gate.gate_id == gate_id:
                gate = self._hitl.reject_gate(gate, approver_id, reason)
                gate_found = True
            updated_gates.append(gate)

        if not gate_found:
            raise ValueError(f"Gate {gate_id} not found in pipeline {run_id}")

        state = state.model_copy(update={
            "status": PipelineStatus.failed,
            "hitl_gates": updated_gates,
            "error": f"HITL gate {gate_id} rejected: {reason}",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._checkpoint.save(run_id, state)
        await self._concurrency.release(state.tenant_id)
        return state

    async def get_status(self, run_id: str) -> PipelineState | None:
        """Get current pipeline status from checkpoint."""
        return await self._checkpoint.load(run_id)

    def to_summary(self, state: PipelineState) -> PipelineSummary | None:
        """
        Convert completed pipeline state to PipelineSummary.

        Output matches M3 ResearchBrief canonical type.
        """
        if state.status != PipelineStatus.completed:
            return None

        from m8_pipeline_engine.models import SecurityIdentifier

        security = state.securities[0] if state.securities else (
            SecurityIdentifier(ticker="UNKNOWN")
        )

        return PipelineSummary(
            brief_id=state.brief.get("brief_id", state.run_id),
            security_identifier=security,
            analyst_id=state.requesting_user_id,
            rating=state.brief.get("rating", "hold"),
            summary=state.brief.get("summary", ""),
            thesis=state.brief.get("thesis", ""),
            catalysts=state.brief.get("catalysts", []),
            risks=state.brief.get("risks", []),
            valuation=state.brief.get("valuation", {}),
            sources=state.brief.get("sources", []),
            pipeline_run_id=state.run_id,
            hitl_gates_passed=[
                g.gate_name for g in state.hitl_gates
                if g.status == GateStatus.approved
            ],
            anti_fabrication_score=state.anti_fabrication_score,
            trace_id=state.trace_id,
        )
