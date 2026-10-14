"""
Tests for Gap 2: Liability Provenance.

Covers: chain creation, stage recording, SHA-256 hashing, finalization,
error classification, warranty boundary, indemnification records.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"liability_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
sys.modules["models"] = _models
_provenance = _load_local("provenance")

ProvenanceRecorder = _provenance.ProvenanceRecorder
WarrantyCategory = _models.WarrantyCategory
ErrorCategory = _models.ErrorCategory
MODULE_WARRANTY = _models.MODULE_WARRANTY


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ── Chain creation ───────────────────────────────────────────────


class TestChainCreation:
    def test_start_chain(self):
        rec = ProvenanceRecorder()
        chain = rec.start_chain("trace-001")
        assert chain.trace_id == "trace-001"
        assert chain.stages == []
        assert chain.finalized is False
        assert chain.final_output_hash is None

    def test_start_chain_duplicate_raises(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-001")
        with pytest.raises(ValueError, match="already exists"):
            rec.start_chain("trace-001")

    def test_get_chain(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-002")
        chain = rec.get_chain("trace-002")
        assert chain.trace_id == "trace-002"

    def test_get_chain_missing_raises(self):
        rec = ProvenanceRecorder()
        with pytest.raises(KeyError, match="No chain found"):
            rec.get_chain("nonexistent")


# ── Stage recording ──────────────────────────────────────────────


class TestStageRecording:
    def test_record_single_stage(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-010")
        stage = rec.record_stage(
            trace_id="trace-010",
            module="M1",
            operation="identity_verification",
            input_data="user:sarah.chen",
            output_data='{"aid_hash":"abc123"}',
            version="1.2.0",
            latency_ms=12.0,
        )
        assert stage.stage_number == 1
        assert stage.module == "M1"
        assert stage.input_hash == _sha256("user:sarah.chen")
        assert stage.output_hash == _sha256('{"aid_hash":"abc123"}')
        assert stage.warranty_category == WarrantyCategory.DETERMINISTIC

    def test_record_multiple_stages(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-011")
        s1 = rec.record_stage("trace-011", "M1", "identity", "in1", "out1")
        s2 = rec.record_stage("trace-011", "M2", "authority", "in2", "out2")
        s3 = rec.record_stage("trace-011", "LLM", "synthesis", "in3", "out3")
        assert s1.stage_number == 1
        assert s2.stage_number == 2
        assert s3.stage_number == 3
        chain = rec.get_chain("trace-011")
        assert len(chain.stages) == 3

    def test_record_stage_empty_input(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-012")
        stage = rec.record_stage("trace-012", "M1", "init", "", "out1")
        assert stage.input_hash is None
        assert stage.output_hash == _sha256("out1")

    def test_record_stage_on_finalized_raises(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-013")
        rec.record_stage("trace-013", "M1", "op", "in", "out")
        rec.finalize_chain("trace-013")
        with pytest.raises(ValueError, match="already finalized"):
            rec.record_stage("trace-013", "M2", "op2", "in2", "out2")

    def test_record_stage_missing_chain_raises(self):
        rec = ProvenanceRecorder()
        with pytest.raises(KeyError):
            rec.record_stage("missing", "M1", "op", "in", "out")


# ── SHA-256 hash computation ─────────────────────────────────────


class TestHashing:
    def test_sha256_deterministic(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-020")
        s1 = rec.record_stage("trace-020", "M1", "op", "hello", "world")
        s2 = rec.record_stage("trace-020", "M1", "op", "hello", "world")
        assert s1.input_hash == s2.input_hash
        assert s1.output_hash == s2.output_hash

    def test_sha256_different_data(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-021")
        s1 = rec.record_stage("trace-021", "M1", "op", "data_a", "out_a")
        s2 = rec.record_stage("trace-021", "M1", "op", "data_b", "out_b")
        assert s1.input_hash != s2.input_hash
        assert s1.output_hash != s2.output_hash


# ── Chain finalization ───────────────────────────────────────────


class TestFinalization:
    def test_finalize_computes_final_hash(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-030")
        rec.record_stage("trace-030", "M1", "op1", "in1", "out1")
        rec.record_stage("trace-030", "M2", "op2", "in2", "out2")
        chain = rec.finalize_chain("trace-030")
        assert chain.finalized is True
        assert chain.final_output_hash is not None
        expected = _sha256(
            _sha256("out1") + _sha256("out2")
        )
        assert chain.final_output_hash == expected

    def test_finalize_empty_chain_raises(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-031")
        with pytest.raises(ValueError, match="no stages"):
            rec.finalize_chain("trace-031")

    def test_finalize_twice_raises(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-032")
        rec.record_stage("trace-032", "M1", "op", "in", "out")
        rec.finalize_chain("trace-032")
        with pytest.raises(ValueError, match="already finalized"):
            rec.finalize_chain("trace-032")


# ── Warranty boundary ────────────────────────────────────────────


class TestWarrantyBoundary:
    @pytest.mark.parametrize("module,expected", [
        ("M1", WarrantyCategory.DETERMINISTIC),
        ("M2", WarrantyCategory.DETERMINISTIC),
        ("M3", WarrantyCategory.DETERMINISTIC),
        ("M4", WarrantyCategory.DETERMINISTIC),
        ("M5", WarrantyCategory.DETERMINISTIC),
        ("M7", WarrantyCategory.DETERMINISTIC),
        ("M10", WarrantyCategory.DETERMINISTIC),
        ("M8", WarrantyCategory.PROBABILISTIC),
        ("M9", WarrantyCategory.PROBABILISTIC),
        ("LLM", WarrantyCategory.PROBABILISTIC),
        ("M6", WarrantyCategory.SHARED),
        ("M11", WarrantyCategory.SHARED),
    ])
    def test_warranty_classification(self, module, expected):
        rec = ProvenanceRecorder()
        rec.start_chain(f"trace-wc-{module}")
        stage = rec.record_stage(f"trace-wc-{module}", module, "op", "in", "out")
        assert stage.warranty_category == expected

    def test_unknown_module_defaults_to_shared(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-wc-unknown")
        stage = rec.record_stage("trace-wc-unknown", "M99", "op", "in", "out")
        assert stage.warranty_category == WarrantyCategory.SHARED


# ── Error classification ─────────────────────────────────────────


class TestErrorClassification:
    def _setup_chain(self, rec, trace_id, module):
        rec.start_chain(trace_id)
        rec.record_stage(trace_id, module, "op", "in", "out")

    def test_source_data_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e1", "M11")
        err = rec.classify_error("trace-e1", 1, "Vendor returned stale data")
        assert err.category == ErrorCategory.SOURCE_DATA
        assert err.liable_party == "vendor"

    def test_schema_translation_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e2", "M7")
        err = rec.classify_error("trace-e2", 1, "Schema mapping failed for field X")
        assert err.category == ErrorCategory.SCHEMA_TRANSLATION
        assert err.liable_party == "platform"

    def test_policy_evaluation_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e3", "M2")
        err = rec.classify_error("trace-e3", 1, "OPA policy returned unexpected result")
        assert err.category == ErrorCategory.POLICY_EVALUATION
        assert err.liable_party == "platform"

    def test_llm_synthesis_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e4", "LLM")
        err = rec.classify_error("trace-e4", 1, "LLM hallucinated a price target")
        assert err.category == ErrorCategory.LLM_SYNTHESIS
        assert err.liable_party == "llm_provider_shared"

    def test_human_approval_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e5", "M10")
        err = rec.classify_error("trace-e5", 1, "HITL approval given incorrectly")
        assert err.category == ErrorCategory.HUMAN_APPROVAL
        assert err.liable_party == "firm_user"

    def test_compliance_rule_error(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e6", "M2")
        err = rec.classify_error("trace-e6", 1, "Compliance rule was outdated")
        assert err.category == ErrorCategory.COMPLIANCE_RULE
        assert err.liable_party == "sme_firm"

    def test_error_with_evidence(self):
        rec = ProvenanceRecorder()
        self._setup_chain(rec, "trace-e7", "M11")
        evidence = {"api_response": "500", "vendor": "orion"}
        err = rec.classify_error("trace-e7", 1, "Source data error", evidence=evidence)
        assert err.evidence == evidence
        assert err.trace_id == "trace-e7"
        assert err.stage_number == 1

    def test_error_missing_stage_raises(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-e8")
        rec.record_stage("trace-e8", "M1", "op", "in", "out")
        with pytest.raises(KeyError, match="No stage 5"):
            rec.classify_error("trace-e8", 5, "some error")


# ── Indemnification record ───────────────────────────────────────


class TestIndemnificationRecord:
    def test_generate_record(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-ind-1")
        rec.record_stage("trace-ind-1", "M1", "identity", "in1", "out1")
        rec.record_stage("trace-ind-1", "M2", "authority", "in2", "out2")
        rec.record_stage("trace-ind-1", "LLM", "synthesis", "in3", "out3")
        rec.record_stage("trace-ind-1", "M6", "gateway", "in4", "out4")
        rec.finalize_chain("trace-ind-1")

        hitl = [{"gate": "execution", "approver": "sarah.chen", "approved": True}]
        record = rec.generate_indemnification_record("trace-ind-1", hitl_gates=hitl)

        assert record.trace_id == "trace-ind-1"
        assert record.stages_captured == 4
        assert record.deterministic_stages == 2
        assert record.probabilistic_stages == 1
        assert record.shared_stages == 1
        assert record.hitl_gates == hitl
        assert record.chain_hash != ""
        assert "M1" in record.warranty_boundary_snapshot
        assert record.warranty_boundary_snapshot["M1"] == "deterministic"
        assert record.warranty_boundary_snapshot["LLM"] == "probabilistic"

    def test_generate_record_no_hitl(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-ind-2")
        rec.record_stage("trace-ind-2", "M1", "op", "in", "out")
        record = rec.generate_indemnification_record("trace-ind-2")
        assert record.hitl_gates == []
        assert record.stages_captured == 1

    def test_generate_record_unfinalized_chain(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-ind-3")
        rec.record_stage("trace-ind-3", "M1", "op", "in", "out")
        record = rec.generate_indemnification_record("trace-ind-3")
        assert record.chain_hash == ""


# ── Empty chain handling ─────────────────────────────────────────


class TestEmptyChain:
    def test_empty_chain_has_no_stages(self):
        rec = ProvenanceRecorder()
        chain = rec.start_chain("trace-empty")
        assert len(chain.stages) == 0

    def test_empty_chain_cannot_finalize(self):
        rec = ProvenanceRecorder()
        rec.start_chain("trace-empty-2")
        with pytest.raises(ValueError, match="no stages"):
            rec.finalize_chain("trace-empty-2")
