"""
Gap 2: Liability Provenance — ProvenanceRecorder service.

Per-stage SHA-256 hash chain creating immutable provenance for every agent output.
Integrates with M6 (MCP Gateway) and M10 (Audit Logger).

All compliance records written to WORM storage (S3 Object Lock, 6-year retention).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

try:
    from .models import (
        ERROR_DETECTION_METHOD,
        ERROR_LIABLE_PARTY,
        MODULE_WARRANTY,
        ErrorAttribution,
        ErrorCategory,
        IndemnificationRecord,
        ProvenanceChain,
        ProvenanceStage,
        WarrantyCategory,
    )
except ImportError:
    from models import (
        ERROR_DETECTION_METHOD,
        ERROR_LIABLE_PARTY,
        MODULE_WARRANTY,
        ErrorAttribution,
        ErrorCategory,
        IndemnificationRecord,
        ProvenanceChain,
        ProvenanceStage,
        WarrantyCategory,
    )


def _sha256(data: str) -> str:
    """Compute SHA-256 hex digest."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class ProvenanceRecorder:
    """
    Records per-stage SHA-256 hash chains for liability provenance.

    Every processing stage (M1→M9→M2→M6→M11→M7→M4→LLM→M10) records
    input_hash, output_hash, module version, latency, warranty category.

    Fail-closed: if recording fails, the request is denied.
    """

    def __init__(self) -> None:
        self._chains: dict[str, ProvenanceChain] = {}

    # ── Chain lifecycle ──────────────────────────────────────────

    def start_chain(self, trace_id: str) -> ProvenanceChain:
        """Create a new provenance chain for a trace."""
        if trace_id in self._chains:
            raise ValueError(f"Chain already exists for trace_id={trace_id}")
        chain = ProvenanceChain(trace_id=trace_id)
        self._chains[trace_id] = chain
        return chain

    def record_stage(
        self,
        trace_id: str,
        module: str,
        operation: str,
        input_data: str,
        output_data: str,
        version: str = "0.0.0",
        metadata: Optional[dict] = None,
        latency_ms: float = 0.0,
    ) -> ProvenanceStage:
        """
        Append a processing stage to the provenance chain.

        Computes SHA-256 hashes of input and output data.
        Warranty category auto-classified from module ID.
        """
        chain = self._get_chain(trace_id)
        if chain.finalized:
            raise ValueError(f"Chain {trace_id} is already finalized")

        input_hash = _sha256(input_data) if input_data else None
        output_hash = _sha256(output_data)
        warranty = MODULE_WARRANTY.get(module, WarrantyCategory.SHARED)

        stage = ProvenanceStage(
            stage_number=len(chain.stages) + 1,
            module=module,
            operation=operation,
            version=version,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=metadata or {},
            latency_ms=latency_ms,
            warranty_category=warranty,
        )
        chain.stages.append(stage)
        return stage

    def finalize_chain(self, trace_id: str) -> ProvenanceChain:
        """
        Finalize the provenance chain.

        Computes final_output_hash from the concatenation of all stage hashes.
        Once finalized, no more stages can be added.
        """
        chain = self._get_chain(trace_id)
        if chain.finalized:
            raise ValueError(f"Chain {trace_id} is already finalized")
        if not chain.stages:
            raise ValueError(f"Chain {trace_id} has no stages to finalize")

        # Final hash = SHA-256 of all stage output hashes concatenated
        all_hashes = "".join(s.output_hash for s in chain.stages)
        chain.final_output_hash = _sha256(all_hashes)
        chain.finalized = True
        return chain

    def get_chain(self, trace_id: str) -> ProvenanceChain:
        """Retrieve a provenance chain by trace_id."""
        return self._get_chain(trace_id)

    # ── Error classification ─────────────────────────────────────

    def classify_error(
        self,
        trace_id: str,
        stage_number: int,
        error_description: str,
        evidence: Optional[dict] = None,
    ) -> ErrorAttribution:
        """
        Classify an error to a liable party based on the stage's module.

        Uses the 6-category taxonomy from ARCH-06 §2.4.
        """
        chain = self._get_chain(trace_id)
        stage = self._get_stage(chain, stage_number)

        category = self._infer_error_category(stage.module, error_description)
        liable_party = ERROR_LIABLE_PARTY.get(category, "unknown")
        detection_method = ERROR_DETECTION_METHOD.get(category, "manual_review")

        return ErrorAttribution(
            category=category,
            liable_party=liable_party,
            detection_method=detection_method,
            evidence=evidence or {"description": error_description},
            stage_number=stage_number,
            trace_id=trace_id,
        )

    # ── Indemnification record ───────────────────────────────────

    def generate_indemnification_record(
        self,
        trace_id: str,
        hitl_gates: Optional[list[dict]] = None,
    ) -> IndemnificationRecord:
        """
        Generate E&O insurance documentation package for a trace.

        Captures warranty boundary snapshot, stage counts by category,
        and HITL gate information.
        """
        chain = self._get_chain(trace_id)

        det = sum(
            1 for s in chain.stages
            if s.warranty_category == WarrantyCategory.DETERMINISTIC
        )
        prob = sum(
            1 for s in chain.stages
            if s.warranty_category == WarrantyCategory.PROBABILISTIC
        )
        shared = sum(
            1 for s in chain.stages
            if s.warranty_category == WarrantyCategory.SHARED
        )

        snapshot = {
            s.module: s.warranty_category.value for s in chain.stages
        }

        chain_hash = chain.final_output_hash or ""

        return IndemnificationRecord(
            trace_id=trace_id,
            stages_captured=len(chain.stages),
            hitl_gates=hitl_gates or [],
            warranty_boundary_snapshot=snapshot,
            deterministic_stages=det,
            probabilistic_stages=prob,
            shared_stages=shared,
            chain_hash=chain_hash,
        )

    # ── Helpers ──────────────────────────────────────────────────

    def _get_chain(self, trace_id: str) -> ProvenanceChain:
        chain = self._chains.get(trace_id)
        if chain is None:
            raise KeyError(f"No chain found for trace_id={trace_id}")
        return chain

    @staticmethod
    def _get_stage(chain: ProvenanceChain, stage_number: int) -> ProvenanceStage:
        for stage in chain.stages:
            if stage.stage_number == stage_number:
                return stage
        raise KeyError(
            f"No stage {stage_number} in chain {chain.trace_id}"
        )

    @staticmethod
    def _infer_error_category(module: str, description: str) -> ErrorCategory:
        """Infer error category from module and description keywords."""
        desc_lower = description.lower()

        # Explicit keyword matching
        if "source data" in desc_lower or "vendor" in desc_lower:
            return ErrorCategory.SOURCE_DATA
        if "translation" in desc_lower or "schema" in desc_lower or "mapping" in desc_lower:
            return ErrorCategory.SCHEMA_TRANSLATION
        if "policy" in desc_lower or "opa" in desc_lower or "rego" in desc_lower:
            return ErrorCategory.POLICY_EVALUATION
        if "llm" in desc_lower or "synthesis" in desc_lower or "hallucin" in desc_lower:
            return ErrorCategory.LLM_SYNTHESIS
        if "approval" in desc_lower or "hitl" in desc_lower or "human" in desc_lower:
            return ErrorCategory.HUMAN_APPROVAL
        if "compliance" in desc_lower or "rule" in desc_lower or "regulation" in desc_lower:
            return ErrorCategory.COMPLIANCE_RULE

        # Fallback: infer from module identity
        if module in ("M11",):
            return ErrorCategory.SOURCE_DATA
        if module in ("M7",):
            return ErrorCategory.SCHEMA_TRANSLATION
        if module in ("M2", "M4"):
            return ErrorCategory.POLICY_EVALUATION
        if module in ("M8", "M9", "LLM"):
            return ErrorCategory.LLM_SYNTHESIS
        return ErrorCategory.SOURCE_DATA
