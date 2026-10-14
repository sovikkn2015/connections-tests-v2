"""
Phase 0 Integration Test: M3 (Canonical Schema) + M5 (Enterprise Config).

Verifies that M5 config archetypes/jurisdictions are consistent with M3
canonical types, and that config drives type selection for OPA rule sets.

This is the Phase 0 integration gate — must pass before Phase 1 begins.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from m5_config_loader import (
    Archetype,
    Jurisdiction,
    EnterpriseConfig,
    CONFIG_VERSION,
    load_enterprise_config,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
TIER4_CONFIG = PROJECT_ROOT / "config" / "enterprise-config-tier4-ria.yaml"
TIER3_CONFIG = PROJECT_ROOT / "config" / "enterprise-config-tier3-bd.yaml"


def _build_config_for_archetype(arch: Archetype) -> EnterpriseConfig:
    """Helper: build a minimal valid config for any archetype."""
    return EnterpriseConfig(
        config_version=CONFIG_VERSION,
        firm={"name": "Test", "crd_number": "1", "registration_type": "ria_only"},
        archetype=arch.value,
        jurisdiction={"primary": "us", "data_residency": "us"},
        deployment={"topology": "cloud", "region": "us-east-1", "runtime": "managed_agents"},
        vendors={"crm": "sf", "portfolio": "orion", "custodians": ["schwab"]},
        channels={"enabled": ["slack"], "primary": "slack"},
        compliance={
            "suitability_standard": "fiduciary", "reg_bi_enabled": False,
            "smarsh_enabled": False, "principal_review_enabled": False,
            "worm_retention_years": 6, "mnpi_filtering": "test",
        },
        specialists={"enabled": ["research"]},
        memory={},
    )


class TestPhase0Integration:
    """Phase 0 gate: M3 + M5 together."""

    def test_tier4_config_loads(self):
        cfg = load_enterprise_config(TIER4_CONFIG)
        assert cfg.archetype == Archetype.tier4_independent_ria

    def test_tier3_config_loads(self):
        cfg = load_enterprise_config(TIER3_CONFIG)
        assert cfg.archetype == Archetype.tier3_broker_dealer

    def test_archetype_values_match_m3_conventions(self):
        """M5 archetypes are snake_case strings starting with 'tier'."""
        for arch in Archetype:
            assert isinstance(arch.value, str)
            assert "_" in arch.value
            assert arch.value.startswith("tier")

    def test_jurisdiction_values_are_2_letter_codes(self):
        """M5 jurisdictions are 2-letter codes matching M3 Client.jurisdiction."""
        for j in Jurisdiction:
            assert isinstance(j.value, str)
            assert len(j.value) == 2

    def test_config_drives_opa_bundle_selection(self):
        cfg = load_enterprise_config(TIER4_CONFIG)
        assert cfg.get_opa_bundle_prefix() == "opa-bundles/tier4/"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cfg3 = load_enterprise_config(TIER3_CONFIG)
        assert cfg3.get_opa_bundle_prefix() == "opa-bundles/tier3/"

    def test_config_drives_compliance_regime(self):
        ria = load_enterprise_config(TIER4_CONFIG)
        assert ria.compliance.suitability_standard.value == "fiduciary"
        assert ria.compliance.reg_bi_enabled is False
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bd = load_enterprise_config(TIER3_CONFIG)
        assert bd.compliance.suitability_standard.value == "reg_bi"
        assert bd.compliance.reg_bi_enabled is True

    def test_config_drives_mnpi_rule_selection(self):
        ria = load_enterprise_config(TIER4_CONFIG)
        assert "tier4" in ria.compliance.mnpi_filtering
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bd = load_enterprise_config(TIER3_CONFIG)
        assert "tier3" in bd.compliance.mnpi_filtering

    def test_config_hash_deterministic(self):
        cfg1 = load_enterprise_config(TIER4_CONFIG)
        cfg2 = load_enterprise_config(TIER4_CONFIG)
        assert cfg1.config_hash == cfg2.config_hash
        assert len(cfg1.config_hash) == 64

    def test_all_5_archetypes_have_opa_prefix(self):
        for arch in Archetype:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cfg = _build_config_for_archetype(arch)
            prefix = cfg.get_opa_bundle_prefix()
            assert prefix.startswith("opa-bundles/")
