"""
Tests for Gap 3: WSP-to-YAML Mapping.

Covers: mapping CRUD, bidirectional lookup, version sync,
annotation validation, FINRA report generation, change audit trail.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import pytest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"wsp_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
# Register as bare 'models' so registry.py's fallback import finds the right one
sys.modules["models"] = _models
_registry = _load_local("registry")

ChangeType = _models.ChangeType
EnforcementType = _models.EnforcementType
SyncStatus = _models.SyncStatus
WSPMapping = _models.WSPMapping
WSPRegistry = _registry.WSPRegistry


# ── Fixtures ─────────────────────────────────────────────────────


def _make_mapping(**kwargs) -> WSPMapping:
    defaults = dict(
        wsp_section="4.2",
        wsp_title="Restricted List Management",
        wsp_text="The firm maintains a restricted list...",
        opa_bundle="authority",
        rego_file="authority/restricted_list.rego",
        rego_rule="check_restricted_list",
        enforcement_type=EnforcementType.DETERMINISTIC,
        test_cases=["ADV-001", "ADV-RESTRICTED-001"],
    )
    defaults.update(kwargs)
    return WSPMapping(**defaults)


def _make_registry_with_mappings() -> WSPRegistry:
    reg = WSPRegistry()
    reg.add_mapping(
        _make_mapping(wsp_section="4.2", rego_rule="check_restricted_list"),
        changed_by="sme@firm.com",
    )
    reg.add_mapping(
        _make_mapping(
            wsp_section="5.1",
            wsp_title="Trade Execution Oversight",
            rego_file="authority/execution.rego",
            rego_rule="require_hitl_approval",
        ),
        changed_by="sme@firm.com",
    )
    return reg


# ── CRUD ─────────────────────────────────────────────────────────


class TestMappingCRUD:
    def test_add_mapping(self):
        reg = WSPRegistry()
        m = reg.add_mapping(_make_mapping(), changed_by="sme@firm.com")
        assert m.wsp_section == "4.2"
        assert len(reg.list_mappings()) == 1

    def test_get_mapping(self):
        reg = WSPRegistry()
        m = reg.add_mapping(_make_mapping(), changed_by="sme@firm.com")
        retrieved = reg.get_mapping(m.mapping_id)
        assert retrieved is not None
        assert retrieved.wsp_section == "4.2"

    def test_get_nonexistent_returns_none(self):
        reg = WSPRegistry()
        assert reg.get_mapping("nonexistent") is None

    def test_update_mapping(self):
        reg = WSPRegistry()
        m = reg.add_mapping(_make_mapping(), changed_by="sme@firm.com")
        updated = reg.update_mapping(
            m.mapping_id,
            changed_by="sme@firm.com",
            reason="Updated title",
            wsp_title="Updated Title",
        )
        assert updated.wsp_title == "Updated Title"

    def test_update_nonexistent_raises(self):
        reg = WSPRegistry()
        with pytest.raises(KeyError):
            reg.update_mapping("nonexistent", changed_by="sme@firm.com")

    def test_add_records_change(self):
        reg = WSPRegistry()
        reg.add_mapping(_make_mapping(), changed_by="sme@firm.com")
        changes = reg.get_changes()
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MAPPING_CREATE


# ── Bidirectional Lookup ─────────────────────────────────────────


class TestBidirectionalLookup:
    def test_wsp_to_rego(self):
        reg = _make_registry_with_mappings()
        results = reg.wsp_to_rego("4.2")
        assert len(results) == 1
        assert results[0].rego_rule == "check_restricted_list"

    def test_wsp_to_rego_no_match(self):
        reg = _make_registry_with_mappings()
        results = reg.wsp_to_rego("99.99")
        assert len(results) == 0

    def test_rego_to_wsp(self):
        reg = _make_registry_with_mappings()
        results = reg.rego_to_wsp("authority/restricted_list.rego")
        assert len(results) == 1
        assert results[0].wsp_section == "4.2"

    def test_rego_to_wsp_with_rule_filter(self):
        reg = _make_registry_with_mappings()
        results = reg.rego_to_wsp(
            "authority/execution.rego", "require_hitl_approval",
        )
        assert len(results) == 1
        assert results[0].wsp_section == "5.1"

    def test_rego_to_wsp_no_match(self):
        reg = _make_registry_with_mappings()
        results = reg.rego_to_wsp("nonexistent.rego")
        assert len(results) == 0


# ── Version Synchronization ──────────────────────────────────────


class TestVersionSync:
    def test_flag_wsp_change(self):
        reg = _make_registry_with_mappings()
        affected = reg.flag_wsp_change(
            "4.2", changed_by="sme@firm.com", reason="Updated SLA",
        )
        assert len(affected) == 1
        assert affected[0].sync_status == SyncStatus.PENDING_REVIEW

    def test_flag_rego_change(self):
        reg = _make_registry_with_mappings()
        affected = reg.flag_rego_change(
            "authority/restricted_list.rego",
            changed_by="eng@firm.com",
            git_commit="abc123",
        )
        assert len(affected) == 1
        assert affected[0].sync_status == SyncStatus.PENDING_REVIEW

    def test_complete_review(self):
        reg = _make_registry_with_mappings()
        reg.flag_wsp_change("4.2", changed_by="sme@firm.com")
        m = reg.wsp_to_rego("4.2")[0]
        assert m.sync_status == SyncStatus.PENDING_REVIEW
        reviewed = reg.complete_review(m.mapping_id, reviewer="sme@firm.com")
        assert reviewed.sync_status == SyncStatus.IN_SYNC
        assert reviewed.reviewer == "sme@firm.com"

    def test_complete_review_nonexistent_raises(self):
        reg = WSPRegistry()
        with pytest.raises(KeyError):
            reg.complete_review("nonexistent", reviewer="sme@firm.com")

    def test_change_audit_trail(self):
        reg = _make_registry_with_mappings()
        reg.flag_wsp_change("4.2", changed_by="sme@firm.com", reason="SLA update")
        changes = reg.get_changes(wsp_section="4.2")
        assert len(changes) >= 2
        wsp_changes = [c for c in changes if c.change_type == ChangeType.WSP_UPDATE]
        assert len(wsp_changes) == 1


# ── Annotation Validation ────────────────────────────────────────


class TestAnnotationValidation:
    def test_validates_annotated_rego(self):
        reg = WSPRegistry()
        with tempfile.TemporaryDirectory() as tmpdir:
            rego_content = '''# METADATA
# title: Test rule
# custom:
#   wsp_section: "WSP-4.2"
default check_test := {"decision": "PASS"}

# METADATA
# title: Another rule
# custom:
#   wsp_section: "WSP-5.1"
check_test := result if {
    result := {"decision": "ALLOW"}
}
'''
            Path(tmpdir, "test.rego").write_text(rego_content)
            report = reg.validate_annotations(tmpdir)
            assert report.passed is True
            assert report.rules_missing_annotation == 0
            assert report.total_rules >= 2

    def test_fails_on_missing_annotation(self):
        reg = WSPRegistry()
        with tempfile.TemporaryDirectory() as tmpdir:
            rego_content = '''# No wsp_section annotation here
default check_test := {"decision": "PASS"}

check_test := result if {
    result := {"decision": "ALLOW"}
}
'''
            Path(tmpdir, "test.rego").write_text(rego_content)
            report = reg.validate_annotations(tmpdir)
            assert report.passed is False
            assert report.rules_missing_annotation > 0

    def test_validates_real_opa_bundles(self):
        reg = WSPRegistry()
        bundles_dir = Path(__file__).parent.parent.parent.parent / "opa-bundles"
        if bundles_dir.exists():
            report = reg.validate_annotations(bundles_dir)
            assert report.total_rules > 0


# ── FINRA Report ─────────────────────────────────────────────────


class TestFINRAReport:
    def test_generates_report(self):
        reg = _make_registry_with_mappings()
        report = reg.generate_finra_report("firm-001", "Acme Wealth")
        assert report.firm_id == "firm-001"
        assert report.total_mappings == 2
        assert report.mappings_in_sync == 2
        assert report.sync_percentage == 100.0

    def test_report_reflects_pending_review(self):
        reg = _make_registry_with_mappings()
        reg.flag_wsp_change("4.2", changed_by="sme@firm.com")
        report = reg.generate_finra_report("firm-001")
        assert report.mappings_pending_review == 1
        assert report.mappings_in_sync == 1
        assert report.sync_percentage == 50.0

    def test_report_includes_coverage_details(self):
        reg = _make_registry_with_mappings()
        report = reg.generate_finra_report("firm-001")
        assert len(report.coverage_details) == 2
        sections = {c.wsp_section for c in report.coverage_details}
        assert "4.2" in sections
        assert "5.1" in sections

    def test_report_includes_change_history(self):
        reg = _make_registry_with_mappings()
        report = reg.generate_finra_report("firm-001")
        assert len(report.change_history) >= 2
