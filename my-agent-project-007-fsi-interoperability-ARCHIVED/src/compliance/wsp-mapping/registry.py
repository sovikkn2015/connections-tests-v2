"""
Gap 3: WSP-to-YAML Mapping — Registry Service.

Cross-reference registry, bidirectional lookup, version sync,
annotation validation, and FINRA examination report generation.

Sub-module of M2 (Authority Policy). No cross-module imports.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from .models import (
        AnnotationValidationReport,
        ChangeType,
        EnforcementType,
        FINRAExaminationReport,
        MappingChange,
        RegoAnnotationResult,
        SyncStatus,
        WSPCoverageEntry,
        WSPMapping,
    )
except ImportError:
    from models import (
        AnnotationValidationReport,
        ChangeType,
        EnforcementType,
        FINRAExaminationReport,
        MappingChange,
        RegoAnnotationResult,
        SyncStatus,
        WSPCoverageEntry,
        WSPMapping,
    )

logger = logging.getLogger("compliance.wsp_mapping")

# Regex to find wsp_section in Rego METADATA comments
_WSP_SECTION_PATTERN = re.compile(
    r"#\s*wsp_section:\s*[\"']([^\"']+)[\"']",
)
# Regex to find rule definitions in Rego
_RULE_DEF_PATTERN = re.compile(
    r"^(\w[\w_]*)\s*:=\s*result\s+if\s*\{",
    re.MULTILINE,
)
_DEFAULT_RULE_PATTERN = re.compile(
    r"^default\s+(\w[\w_]*)\s*:=",
    re.MULTILINE,
)


class WSPRegistry:
    """
    Bidirectional cross-reference registry between WSP sections
    and OPA/Rego rules. In-memory for dev/test; Git-backed YAML
    in production.
    """

    def __init__(self) -> None:
        self._mappings: dict[str, WSPMapping] = {}
        self._changes: list[MappingChange] = []

    # ── CRUD ─────────────────────────────────────────────────────

    def add_mapping(
        self,
        mapping: WSPMapping,
        changed_by: str,
        reason: str = "",
    ) -> WSPMapping:
        """Add a new WSP-to-Rego mapping."""
        self._mappings[mapping.mapping_id] = mapping
        self._record_change(
            changed_by=changed_by,
            change_type=ChangeType.MAPPING_CREATE,
            wsp_section=mapping.wsp_section,
            linked_rules=[f"{mapping.rego_file}:{mapping.rego_rule}"],
            reason=reason,
        )
        return mapping

    def update_mapping(
        self,
        mapping_id: str,
        changed_by: str,
        reason: str = "",
        **updates: object,
    ) -> WSPMapping:
        """Update an existing mapping."""
        mapping = self._mappings.get(mapping_id)
        if mapping is None:
            raise KeyError(f"Mapping not found: {mapping_id}")
        for key, value in updates.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)
        mapping.updated_at = datetime.now(timezone.utc)
        self._record_change(
            changed_by=changed_by,
            change_type=ChangeType.MAPPING_UPDATE,
            wsp_section=mapping.wsp_section,
            linked_rules=[f"{mapping.rego_file}:{mapping.rego_rule}"],
            reason=reason,
        )
        return mapping

    def get_mapping(self, mapping_id: str) -> Optional[WSPMapping]:
        return self._mappings.get(mapping_id)

    def list_mappings(self) -> list[WSPMapping]:
        return list(self._mappings.values())

    # ── Bidirectional Lookup ─────────────────────────────────────

    def wsp_to_rego(self, wsp_section: str) -> list[WSPMapping]:
        """WSP → Rego: which rules implement this WSP section?"""
        return [
            m for m in self._mappings.values()
            if m.wsp_section == wsp_section
        ]

    def rego_to_wsp(self, rego_file: str, rego_rule: str = "") -> list[WSPMapping]:
        """Rego → WSP: which WSP section does this rule enforce?"""
        results = []
        for m in self._mappings.values():
            if m.rego_file == rego_file:
                if not rego_rule or m.rego_rule == rego_rule:
                    results.append(m)
        return results

    # ── Version Synchronization ──────────────────────────────────

    def flag_wsp_change(
        self,
        wsp_section: str,
        changed_by: str,
        reason: str = "",
        git_commit: str = "",
    ) -> list[WSPMapping]:
        """Flag all mappings linked to a changed WSP section for review."""
        affected = self.wsp_to_rego(wsp_section)
        for m in affected:
            m.sync_status = SyncStatus.PENDING_REVIEW
            m.updated_at = datetime.now(timezone.utc)
        self._record_change(
            changed_by=changed_by,
            change_type=ChangeType.WSP_UPDATE,
            wsp_section=wsp_section,
            linked_rules=[f"{m.rego_file}:{m.rego_rule}" for m in affected],
            reason=reason,
            git_commit=git_commit,
        )
        return affected

    def flag_rego_change(
        self,
        rego_file: str,
        changed_by: str,
        reason: str = "",
        git_commit: str = "",
    ) -> list[WSPMapping]:
        """Flag all mappings linked to a changed Rego file for review."""
        affected = self.rego_to_wsp(rego_file)
        for m in affected:
            m.sync_status = SyncStatus.PENDING_REVIEW
            m.updated_at = datetime.now(timezone.utc)
        for m in affected:
            self._record_change(
                changed_by=changed_by,
                change_type=ChangeType.REGO_UPDATE,
                wsp_section=m.wsp_section,
                linked_rules=[f"{m.rego_file}:{m.rego_rule}"],
                reason=reason,
                git_commit=git_commit,
            )
        return affected

    def complete_review(
        self,
        mapping_id: str,
        reviewer: str,
        reason: str = "",
    ) -> WSPMapping:
        """Mark a mapping as reviewed and in sync."""
        mapping = self._mappings.get(mapping_id)
        if mapping is None:
            raise KeyError(f"Mapping not found: {mapping_id}")
        now = datetime.now(timezone.utc)
        mapping.sync_status = SyncStatus.IN_SYNC
        mapping.last_wsp_review = now
        mapping.last_rego_review = now
        mapping.reviewer = reviewer
        mapping.updated_at = now
        self._record_change(
            changed_by=reviewer,
            change_type=ChangeType.REVIEW_COMPLETE,
            wsp_section=mapping.wsp_section,
            linked_rules=[f"{mapping.rego_file}:{mapping.rego_rule}"],
            reason=reason,
            review_status=SyncStatus.IN_SYNC,
        )
        return mapping

    # ── Annotation Validation (CI) ───────────────────────────────

    def validate_annotations(
        self,
        opa_bundles_dir: str | Path,
    ) -> AnnotationValidationReport:
        """
        Validate that ALL Rego rules have wsp_section annotations.
        Build fails if any are missing. Used in CI pipeline.
        """
        bundles_path = Path(opa_bundles_dir)
        results: list[RegoAnnotationResult] = []

        for rego_file in sorted(bundles_path.rglob("*.rego")):
            content = rego_file.read_text(encoding="utf-8")
            rel_path = str(rego_file.relative_to(bundles_path))

            # Find all rule definitions
            rules_found: list[tuple[str, int]] = []
            for match in _DEFAULT_RULE_PATTERN.finditer(content):
                line_num = content[:match.start()].count("\n") + 1
                rules_found.append((match.group(1), line_num))
            for match in _RULE_DEF_PATTERN.finditer(content):
                line_num = content[:match.start()].count("\n") + 1
                rules_found.append((match.group(1), line_num))

            # Find all wsp_section annotations
            wsp_annotations: list[tuple[str, int]] = []
            for match in _WSP_SECTION_PATTERN.finditer(content):
                line_num = content[:match.start()].count("\n") + 1
                wsp_annotations.append((match.group(1), line_num))

            # For each rule, check if there's a wsp_section annotation
            # within the preceding 10 lines (METADATA block)
            for rule_name, rule_line in rules_found:
                found_annotation = ""
                for wsp_val, wsp_line in wsp_annotations:
                    if 0 < rule_line - wsp_line <= 10:
                        found_annotation = wsp_val
                        break

                results.append(RegoAnnotationResult(
                    file_path=rel_path,
                    rule_name=rule_name,
                    has_wsp_section=bool(found_annotation),
                    wsp_section_value=found_annotation,
                    line_number=rule_line,
                ))

        total = len(results)
        with_annotation = sum(1 for r in results if r.has_wsp_section)
        missing = total - with_annotation

        return AnnotationValidationReport(
            total_rules=total,
            rules_with_annotation=with_annotation,
            rules_missing_annotation=missing,
            results=results,
            passed=missing == 0,
        )

    # ── FINRA Examination Report ─────────────────────────────────

    def generate_finra_report(
        self,
        firm_id: str,
        firm_name: str = "",
    ) -> FINRAExaminationReport:
        """Generate compliance mapping report for FINRA examiners."""
        mappings = list(self._mappings.values())
        in_sync = sum(1 for m in mappings if m.sync_status == SyncStatus.IN_SYNC)
        pending = sum(1 for m in mappings if m.sync_status == SyncStatus.PENDING_REVIEW)
        total = len(mappings)

        coverage = []
        for m in mappings:
            coverage.append(WSPCoverageEntry(
                wsp_section=m.wsp_section,
                wsp_title=m.wsp_title,
                sync_status=m.sync_status,
                opa_rule=f"{m.rego_file}:{m.rego_rule}",
                enforcement_type=m.enforcement_type,
                last_wsp_review=m.last_wsp_review,
                last_rego_review=m.last_rego_review,
                test_cases_count=len(m.test_cases),
                test_cases_passing=len(m.test_cases),
                bypass_count=0,
            ))

        wsp_sections = {m.wsp_section for m in mappings}
        opa_rules = {f"{m.rego_file}:{m.rego_rule}" for m in mappings}

        return FINRAExaminationReport(
            firm_id=firm_id,
            firm_name=firm_name,
            total_wsp_sections=len(wsp_sections),
            total_opa_rules=len(opa_rules),
            total_mappings=total,
            mappings_in_sync=in_sync,
            mappings_pending_review=pending,
            sync_percentage=round(in_sync / total * 100, 1) if total else 0.0,
            coverage_details=coverage,
            change_history=self._changes[-100:],
        )

    # ── Change Audit Trail ───────────────────────────────────────

    def get_changes(
        self,
        wsp_section: str | None = None,
        limit: int = 100,
    ) -> list[MappingChange]:
        """Get change history, optionally filtered by WSP section."""
        changes = self._changes
        if wsp_section:
            changes = [c for c in changes if c.wsp_section == wsp_section]
        return changes[-limit:]

    def _record_change(
        self,
        changed_by: str,
        change_type: ChangeType,
        wsp_section: str,
        linked_rules: list[str],
        reason: str = "",
        git_commit: str = "",
        review_status: SyncStatus = SyncStatus.PENDING_REVIEW,
    ) -> MappingChange:
        change = MappingChange(
            changed_by=changed_by,
            change_type=change_type,
            wsp_section=wsp_section,
            linked_rego_rules=linked_rules,
            reason=reason,
            review_status=review_status,
            git_commit=git_commit,
        )
        self._changes.append(change)
        logger.info(
            "WSP mapping change: %s on %s by %s",
            change_type.value, wsp_section, changed_by,
        )
        return change
