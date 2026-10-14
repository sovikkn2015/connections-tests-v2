"""
M8 Pipeline Engine — Integration Tests.

Tests cover:
  - Pipeline state flows through all 23 stages
  - HITL gate 1 pauses after data gathering (stage 6)
  - HITL gate approval with valid SHA-256 token
  - HITL gate rejection
  - HITL gate timeout
  - Token budget tracking
  - 20-minute timeout enforcement
  - Anti-fabrication check
  - Pipeline produces valid ResearchBrief-compatible output
  - FastAPI endpoint integration
  - Provenance chain integrity
  - Tenant concurrency limiting

Run: pytest test_m8_pipeline.py -v
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from m8_pipeline_engine.models import (
    DEFAULT_HITL_TIMEOUT_SECONDS,
    DEFAULT_TOKEN_BUDGETS,
    CompletionResponse,
    GateStatus,
    HITLGate,
    Message,
    PipelineState,
    PipelineStatus,
    PipelineSummary,
    ProvenanceEntry,
    ResearchQuery,
    SecurityIdentifier,
    SourceData,
    SourceType,
    StageResult,
    TokenBudget,
    PIPELINE_MAX_DURATION_SECONDS,
)
from m8_pipeline_engine.hitl import HITLManager, GATE_DEFINITIONS

from m8_pipeline_engine.pipeline import (
    CheckpointBackend,
    InMemoryCheckpoint,
    ResearchPipeline,
    TenantConcurrencyLimiter,
)
from m8_pipeline_engine.stages import STAGE_REGISTRY


# ── Fixtures ─────────────────────────────────────────────────────


def _make_query(**kwargs: Any) -> ResearchQuery:
    defaults = {
        "raw_query": "Research NVDA earnings impact",
        "ticker": "NVDA",
        "topic": "earnings",
        "requesting_user_id": "analyst-001",
        "tenant_id": "acme_wm",
    }
    defaults.update(kwargs)
    return ResearchQuery(**defaults)


@pytest.fixture
def query() -> ResearchQuery:
    return _make_query()


@pytest.fixture
def pipeline() -> ResearchPipeline:
    return ResearchPipeline()


@pytest.fixture
def hitl_manager() -> HITLManager:
    return HITLManager()


# ══════════════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════════════


class TestModels:
    """Test Pydantic v2 model validation."""

    def test_research_query_valid(self) -> None:
        q = ResearchQuery(raw_query="Research NVDA", ticker="NVDA")
        assert q.ticker == "NVDA"
        assert q.depth == "standard"

    def test_research_query_depth_validation(self) -> None:
        q = ResearchQuery(raw_query="test", depth="deep")
        assert q.depth == "deep"
        with pytest.raises(Exception):
            ResearchQuery(raw_query="test", depth="invalid")

    def test_pipeline_state_defaults(self) -> None:
        state = PipelineState()
        assert state.status == PipelineStatus.queued
        assert state.current_stage == 0
        assert state.total_tokens_used == 0
        assert len(state.hitl_gates) == 0
        assert len(state.provenance) == 0

    def test_security_identifier(self) -> None:
        sec = SecurityIdentifier(ticker="NVDA", company_name="NVIDIA")
        assert sec.ticker == "NVDA"
        assert sec.cusip is None

    def test_stage_result(self) -> None:
        r = StageResult(stage_name="parse_query", stage_number=1)
        assert r.tokens_used == 0
        assert r.duration_ms == 0.0

    def test_hitl_gate_model(self) -> None:
        gate = HITLGate(gate_name="test_gate", gate_number=1)
        assert gate.status == GateStatus.pending
        assert gate.approval_token is None

    def test_token_budget_defaults(self) -> None:
        assert "sec_filing_analysis" in DEFAULT_TOKEN_BUDGETS
        budget = DEFAULT_TOKEN_BUDGETS["sec_filing_analysis"]
        assert budget.max_tokens == 20_000

    def test_pipeline_summary_matches_canonical(self) -> None:
        summary = PipelineSummary(
            security_identifier=SecurityIdentifier(ticker="NVDA"),
            analyst_id="analyst-001",
            rating="buy",
            summary="NVDA looks strong",
        )
        assert summary.rating == "buy"
        assert summary.anti_fabrication_score == 0.0

    def test_pipeline_max_duration(self) -> None:
        assert PIPELINE_MAX_DURATION_SECONDS == 20 * 60


# ══════════════════════════════════════════════════════════════════
# HITL GATE TESTS
# ══════════════════════════════════════════════════════════════════


class TestHITLGates:
    """Test HITL gate lifecycle: create, approve, reject, timeout."""

    def test_create_gate(self, hitl_manager: HITLManager) -> None:
        gate = hitl_manager.create_gate(1, "data_gathering_review")
        assert gate.status == GateStatus.pending
        assert gate.gate_number == 1
        assert gate.gate_name == "data_gathering_review"
        assert gate.deadline is not None

    def test_approval_token_is_sha256(self, hitl_manager: HITLManager) -> None:
        token = HITLManager.generate_approval_token(
            "gate-123", "approver-456", "2026-07-15T14:30:00Z",
        )
        assert len(token) == 64  # SHA-256 hex digest
        # Verify it matches SHA-256(gate_id + approver_id + timestamp)
        expected = hashlib.sha256(
            "gate-123approver-4562026-07-15T14:30:00Z".encode("utf-8"),
        ).hexdigest()
        assert token == expected

    def test_verify_valid_token(self) -> None:
        gate_id = "gate-abc"
        approver_id = "user-xyz"
        ts = "2026-07-15T14:30:00Z"
        token = HITLManager.generate_approval_token(gate_id, approver_id, ts)
        assert HITLManager.verify_approval_token(gate_id, approver_id, ts, token)

    def test_verify_tampered_token(self) -> None:
        token = HITLManager.generate_approval_token(
            "gate-abc", "user-xyz", "2026-07-15T14:30:00Z",
        )
        assert not HITLManager.verify_approval_token(
            "gate-abc", "DIFFERENT-USER", "2026-07-15T14:30:00Z", token,
        )

    def test_approve_gate(self, hitl_manager: HITLManager) -> None:
        gate = hitl_manager.create_gate(1, "data_gathering_review")
        approved = hitl_manager.approve_gate(gate, "approver-001")
        assert approved.status == GateStatus.approved
        assert approved.approver_id == "approver-001"
        assert approved.approval_token is not None
        assert len(approved.approval_token) == 64

    def test_approve_non_pending_gate_raises(
        self, hitl_manager: HITLManager,
    ) -> None:
        gate = hitl_manager.create_gate(1, "test")
        approved = hitl_manager.approve_gate(gate, "user")
        with pytest.raises(ValueError, match="expected pending"):
            hitl_manager.approve_gate(approved, "user")

    def test_reject_gate(self, hitl_manager: HITLManager) -> None:
        gate = hitl_manager.create_gate(1, "test")
        rejected = hitl_manager.reject_gate(gate, "user", "bad data")
        assert rejected.status == GateStatus.rejected
        assert rejected.rejection_reason == "bad data"

    def test_reject_non_pending_gate_raises(
        self, hitl_manager: HITLManager,
    ) -> None:
        gate = hitl_manager.create_gate(1, "test")
        rejected = hitl_manager.reject_gate(gate, "user", "reason")
        with pytest.raises(ValueError, match="expected pending"):
            hitl_manager.reject_gate(rejected, "user", "again")

    def test_gate_timeout(self) -> None:
        manager = HITLManager(timeout_seconds=0)  # Immediate timeout
        gate = manager.create_gate(1, "test")
        # Gate should be timed out immediately
        checked = manager.check_timeout(gate)
        assert checked.status == GateStatus.timed_out

    def test_gate_not_timed_out(self, hitl_manager: HITLManager) -> None:
        gate = hitl_manager.create_gate(1, "test")
        checked = hitl_manager.check_timeout(gate)
        assert checked.status == GateStatus.pending  # 4 hours not elapsed

    def test_approve_timed_out_gate_raises(self) -> None:
        manager = HITLManager(timeout_seconds=0)
        gate = manager.create_gate(1, "test")
        with pytest.raises(ValueError, match="timed out"):
            manager.approve_gate(gate, "user")

    def test_three_gate_definitions(self) -> None:
        assert len(GATE_DEFINITIONS) == 3
        stages = [after for _, _, after in GATE_DEFINITIONS]
        assert stages == [6, 14, 22]

    def test_get_gate_for_stage(self) -> None:
        result = HITLManager.get_gate_for_stage(6)
        assert result == (1, "data_gathering_review")
        result = HITLManager.get_gate_for_stage(14)
        assert result == (2, "analysis_review")
        result = HITLManager.get_gate_for_stage(22)
        assert result == (3, "final_review")
        assert HITLManager.get_gate_for_stage(5) is None


# ══════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestPipelineExecution:
    """Test full pipeline execution with HITL gates."""

    def test_stage_registry_has_all_stages(self) -> None:
        """Pipeline must have entries covering all 23 stages."""
        assert len(STAGE_REGISTRY) >= 19  # Some stages grouped (7-10)
        stage_nums = [num for num, _, _ in STAGE_REGISTRY]
        assert 1 in stage_nums  # First stage
        assert 23 in stage_nums  # Last stage

    @pytest.mark.asyncio
    async def test_pipeline_starts_and_pauses_at_gate_1(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Pipeline should pause at HITL gate 1 after stage 6."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        assert state.status == PipelineStatus.paused_hitl
        assert state.current_stage == 6  # Paused after news scan
        assert len(state.hitl_gates) == 1
        assert state.hitl_gates[0].gate_name == "data_gathering_review"
        assert state.hitl_gates[0].status == GateStatus.pending

    @pytest.mark.asyncio
    async def test_pipeline_has_sources_at_gate_1(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """After data gathering, pipeline should have sources."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        assert len(state.sources) >= 3  # SEC, market, news
        source_types = {s.source_type for s in state.sources}
        assert SourceType.sec_filing in source_types
        assert SourceType.market_data in source_types
        assert SourceType.news in source_types

    @pytest.mark.asyncio
    async def test_approve_gate_1_continues_to_gate_2(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Approving gate 1 should continue pipeline to gate 2."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        gate_id = state.hitl_gates[0].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate_id, "reviewer-001",
        )

        assert state.status == PipelineStatus.paused_hitl
        assert state.current_stage == 14  # Paused after compliance pre-check
        assert len(state.hitl_gates) == 2
        assert state.hitl_gates[1].gate_name == "analysis_review"

    @pytest.mark.asyncio
    async def test_full_pipeline_through_all_gates(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Pipeline flows through all 23 stages with 3 HITL approvals."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        # Gate 1: data gathering review
        assert state.status == PipelineStatus.paused_hitl
        gate1_id = state.hitl_gates[0].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate1_id, "reviewer-001",
        )

        # Gate 2: analysis review
        assert state.status == PipelineStatus.paused_hitl
        gate2_id = state.hitl_gates[1].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate2_id, "reviewer-001",
        )

        # Gate 3: final review
        assert state.status == PipelineStatus.paused_hitl
        gate3_id = state.hitl_gates[2].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate3_id, "reviewer-001",
        )

        # Pipeline should be completed
        assert state.status == PipelineStatus.completed
        assert state.current_stage == 23
        assert len(state.hitl_gates) == 3
        assert all(
            g.status == GateStatus.approved for g in state.hitl_gates
        )

    @pytest.mark.asyncio
    async def test_completed_pipeline_has_brief(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Completed pipeline should produce a valid brief."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        # Approve all 3 gates
        for i in range(3):
            gate_id = state.hitl_gates[i].gate_id
            state = await pipeline.approve_gate(
                state.run_id, gate_id, "reviewer-001",
            )

        assert state.status == PipelineStatus.completed
        assert state.brief is not None
        assert "brief_id" in state.brief
        assert "security_identifier" in state.brief
        assert "trace_id" in state.brief

    @pytest.mark.asyncio
    async def test_pipeline_summary_output(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """to_summary should produce valid PipelineSummary."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        for i in range(3):
            gate_id = state.hitl_gates[i].gate_id
            state = await pipeline.approve_gate(
                state.run_id, gate_id, "reviewer-001",
            )

        summary = pipeline.to_summary(state)
        assert summary is not None
        assert isinstance(summary, PipelineSummary)
        assert summary.security_identifier.ticker == "NVDA"
        assert summary.pipeline_run_id == state.run_id
        assert len(summary.hitl_gates_passed) == 3

    @pytest.mark.asyncio
    async def test_reject_gate_stops_pipeline(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Rejecting a HITL gate should stop the pipeline."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        gate_id = state.hitl_gates[0].gate_id
        state = await pipeline.reject_gate(
            state.run_id, gate_id, "reviewer-001", "Data quality insufficient",
        )

        assert state.status == PipelineStatus.failed
        assert "rejected" in state.error.lower()
        assert state.hitl_gates[0].status == GateStatus.rejected
        assert state.hitl_gates[0].rejection_reason == "Data quality insufficient"

    @pytest.mark.asyncio
    async def test_provenance_chain_integrity(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Each stage should add a provenance entry with hash chain."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        assert len(state.provenance) >= 6  # At least stages 1-6
        # Verify chain: each entry's previous_hash matches prior entry's hash
        for i in range(1, len(state.provenance)):
            assert state.provenance[i].previous_hash == state.provenance[i - 1].hash

    @pytest.mark.asyncio
    async def test_token_tracking(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Token usage should be tracked per stage."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        assert isinstance(state.token_usage, dict)
        assert "parse_query" in state.token_usage

    @pytest.mark.asyncio
    async def test_checkpoint_persistence(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Pipeline state should be retrievable from checkpoint."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        loaded = await pipeline.get_status(state.run_id)
        assert loaded is not None
        assert loaded.run_id == state.run_id
        assert loaded.status == state.status
        assert loaded.current_stage == state.current_stage

    @pytest.mark.asyncio
    async def test_pipeline_timeout_enforcement(self) -> None:
        """Pipeline should time out after max duration."""
        pipe = ResearchPipeline(max_duration_seconds=0)  # Immediate timeout
        query = _make_query()
        state = await pipe.start(query)
        state = await pipe.run(state)

        assert state.status == PipelineStatus.timed_out
        assert "timeout" in state.error.lower()

    @pytest.mark.asyncio
    async def test_anti_fabrication_check(
        self, pipeline: ResearchPipeline, query: ResearchQuery,
    ) -> None:
        """Anti-fabrication check should produce a score."""
        state = await pipeline.start(query)
        state = await pipeline.run(state)

        # Approve gates 1 and 2 to reach anti-fabrication stage
        gate1_id = state.hitl_gates[0].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate1_id, "reviewer",
        )
        gate2_id = state.hitl_gates[1].gate_id
        state = await pipeline.approve_gate(
            state.run_id, gate2_id, "reviewer",
        )

        # At gate 3, anti-fabrication should have run
        assert state.anti_fabrication_score > 0.0
        assert state.output_guardrails_passed is True


# ══════════════════════════════════════════════════════════════════
# CONCURRENCY TESTS
# ══════════════════════════════════════════════════════════════════


class TestConcurrency:
    """Test tenant concurrency limiting (Rule 11)."""

    @pytest.mark.asyncio
    async def test_concurrency_limiter_allows_up_to_max(self) -> None:
        limiter = TenantConcurrencyLimiter(max_concurrent=3)
        assert await limiter.acquire("tenant-1")
        assert await limiter.acquire("tenant-1")
        assert await limiter.acquire("tenant-1")
        assert not await limiter.acquire("tenant-1")  # 4th blocked

    @pytest.mark.asyncio
    async def test_concurrency_limiter_release(self) -> None:
        limiter = TenantConcurrencyLimiter(max_concurrent=1)
        assert await limiter.acquire("t1")
        assert not await limiter.acquire("t1")
        await limiter.release("t1")
        assert await limiter.acquire("t1")  # Slot freed

    @pytest.mark.asyncio
    async def test_concurrency_per_tenant_isolation(self) -> None:
        limiter = TenantConcurrencyLimiter(max_concurrent=1)
        assert await limiter.acquire("tenant-a")
        assert await limiter.acquire("tenant-b")  # Different tenant


# ══════════════════════════════════════════════════════════════════
# CHECKPOINT TESTS
# ══════════════════════════════════════════════════════════════════


class TestCheckpoint:
    """Test checkpoint backend."""

    @pytest.mark.asyncio
    async def test_in_memory_save_load(self) -> None:
        cp = InMemoryCheckpoint()
        state = PipelineState(run_id="test-123")
        await cp.save("test-123", state)
        loaded = await cp.load("test-123")
        assert loaded is not None
        assert loaded.run_id == "test-123"

    @pytest.mark.asyncio
    async def test_in_memory_load_missing(self) -> None:
        cp = InMemoryCheckpoint()
        assert await cp.load("nonexistent") is None

    @pytest.mark.asyncio
    async def test_in_memory_delete(self) -> None:
        cp = InMemoryCheckpoint()
        state = PipelineState(run_id="test-456")
        await cp.save("test-456", state)
        await cp.delete("test-456")
        assert await cp.load("test-456") is None

    @pytest.mark.asyncio
    async def test_checkpoint_deep_copy(self) -> None:
        """Checkpoint should deep-copy state to prevent mutation."""
        cp = InMemoryCheckpoint()
        state = PipelineState(run_id="test-789")
        await cp.save("test-789", state)
        loaded = await cp.load("test-789")
        assert loaded is not None
        loaded_copy = loaded.model_copy(update={"current_stage": 99})
        reloaded = await cp.load("test-789")
        assert reloaded is not None
        assert reloaded.current_stage == 0  # Original unchanged


# ══════════════════════════════════════════════════════════════════
# FASTAPI ENDPOINT TESTS
# ══════════════════════════════════════════════════════════════════


class TestFastAPIEndpoints:
    """Test FastAPI endpoints for pipeline management."""

    @pytest.fixture(autouse=True)
    def setup_client(self) -> None:
        from m8_pipeline_engine.app import set_pipeline
        set_pipeline(ResearchPipeline())

    @pytest.mark.asyncio
    async def test_health_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["module"] == "m8-pipeline-engine"

    @pytest.mark.asyncio
    async def test_start_pipeline_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.post("/pipeline/run", json={
                "raw_query": "Research NVDA earnings",
                "ticker": "NVDA",
                "tenant_id": "test_tenant",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "paused_hitl"

    @pytest.mark.asyncio
    async def test_status_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.post("/pipeline/run", json={
                "raw_query": "Research AAPL",
                "ticker": "AAPL",
            })
            run_id = resp.json()["run_id"]
            resp = await client.get(f"/pipeline/status/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["current_stage"] == 6

    @pytest.mark.asyncio
    async def test_status_not_found(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.get("/pipeline/status/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_gate_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.post("/pipeline/run", json={
                "raw_query": "Research MSFT",
                "ticker": "MSFT",
            })
            run_id = resp.json()["run_id"]
            resp = await client.get(f"/pipeline/status/{run_id}")
            gate_id = resp.json()["hitl_gates"][0]["gate_id"]
            resp = await client.post(
                f"/pipeline/gate/{run_id}/{gate_id}/approve",
                json={"approver_id": "reviewer-001"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "approved" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_reject_gate_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from m8_pipeline_engine.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.post("/pipeline/run", json={
                "raw_query": "Research TSLA",
                "ticker": "TSLA",
            })
            run_id = resp.json()["run_id"]
            resp = await client.get(f"/pipeline/status/{run_id}")
            gate_id = resp.json()["hitl_gates"][0]["gate_id"]
            resp = await client.post(
                f"/pipeline/gate/{run_id}/{gate_id}/reject",
                json={"approver_id": "reviewer-001", "reason": "Bad data"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
