"""
M5 Enterprise Config Loader — Unit Tests (BLOCKER 2).

Covers:
  1.  Load tier4-ria config successfully
  2.  Load tier3-bd config successfully
  3.  BD without principal_review_enabled fails validation
  4.  HF without pod_isolation fails validation
  5.  IB without chinese_wall fails validation
  6.  WORM retention below 6 years fails
  7.  Credential detection rejects raw API keys
  8.  Credential detection allows Vault refs
  9.  Missing config file raises ConfigNotFoundError
  10. Cache hit returns same object
  11. validate_config_file returns warnings for BD without Smarsh
  12. Hot reload callback fires on reload_config

No cross-module imports. Tests use M5 internals only.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
import yaml

# Ensure the module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import (
    ConfigNotFoundError,
    ConfigValidationError,
    clear_cache,
    load_config,
    register_reload_callback,
    reload_config,
    validate_config_file,
)
from models import Archetype, EnterpriseConfig, MnpiFilterLevel


# ── Paths to real config files ───────────────────────────────────

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
TIER4_RIA_PATH = CONFIG_DIR / "enterprise-config-tier4-ria.yaml"
TIER3_BD_PATH = CONFIG_DIR / "enterprise-config-tier3-bd.yaml"


# ── Helper: write temp YAML config ──────────────────────────────


def _write_yaml(tmp_path: Path, data: dict, name: str = "test.yaml") -> Path:
    """Write a dict as YAML to a temp file and return the path."""
    filepath = tmp_path / name
    filepath.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return filepath


def _base_config(**overrides) -> dict:
    """Minimal valid tier4 RIA config dict for testing."""
    cfg = {
        "firm": {"name": "Test Firm", "crd_number": "999999", "registration_type": "ria_only"},
        "archetype": "tier4_independent_ria",
        "jurisdiction": {"primary": "US", "data_residency": "US"},
        "deployment": {"topology": "cloud", "region": "us-east-1", "runtime": "managed-agents"},
        "vendors": {"crm": "salesforce_fsc", "portfolio": "orion", "custodians": ["schwab"], "market_data": "alpha_vantage"},
        "channels": {"enabled": ["slack", "web"], "primary": "slack"},
        "compliance": {
            "suitability_standard": "fiduciary",
            "worm_retention_years": 6,
            "mnpi_filtering": "tier4_advisor_level",
        },
        "specialists": {"enabled": ["client_service", "research"], "supervisor_model": "haiku", "research_model": "sonnet", "client_service_model": "haiku"},
        "memory": {"l1_ttl_hours": 8, "l2_retention_days": 7, "l3_retention_years": 2, "l4_enabled": True, "l5_enabled": True},
    }
    cfg.update(overrides)
    return cfg


# ── Fixture: clear cache before each test ────────────────────────


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Ensure each test starts with a clean cache."""
    clear_cache()
    yield
    clear_cache()


# ── Test 1: Load tier4-ria config successfully ───────────────────


def test_load_tier4_ria_config():
    """Load the real tier4-ria YAML and validate all fields."""
    config = load_config(TIER4_RIA_PATH)

    assert isinstance(config, EnterpriseConfig)
    assert config.archetype == Archetype.tier4_independent_ria
    assert config.firm.name == "Acme Wealth Management"
    assert config.firm.crd_number == "123456"
    assert config.compliance.suitability_standard.value == "fiduciary"
    assert config.compliance.worm_retention_years >= 6
    assert config.compliance.mnpi_filtering == MnpiFilterLevel.tier4_advisor_level


# ── Test 2: Load tier3-bd config successfully ────────────────────


def test_load_tier3_bd_config():
    """Load the real tier3-bd YAML and validate BD-specific fields."""
    config = load_config(TIER3_BD_PATH)

    assert isinstance(config, EnterpriseConfig)
    assert config.archetype == Archetype.tier3_broker_dealer
    assert config.firm.lei == "5493001KJTIIGC8Y1R12"
    assert config.compliance.principal_review_enabled is True
    assert config.compliance.suitability_standard.value == "reg_bi"
    assert config.compliance.reg_bi_enabled is True
    assert config.compliance.smarsh_enabled is True
    assert config.compliance.worm_retention_years >= 6


# ── Test 3: BD without principal_review_enabled fails ────────────


def test_bd_without_principal_review_fails(tmp_path: Path):
    """Tier 3 BD MUST have principal_review_enabled (FINRA 2210)."""
    cfg = _base_config(archetype="tier3_broker_dealer")
    cfg["compliance"]["suitability_standard"] = "reg_bi"
    cfg["compliance"]["principal_review_enabled"] = False

    filepath = _write_yaml(tmp_path, cfg)
    with pytest.raises(ConfigValidationError, match="principal_review_enabled"):
        load_config(filepath)


# ── Test 4: HF without pod_isolation fails ───────────────────────


def test_hf_without_pod_isolation_fails(tmp_path: Path):
    """Tier 5 HF MUST use tier5_pod_isolation MNPI filtering."""
    cfg = _base_config(archetype="tier5_hedge_fund")
    cfg["compliance"]["mnpi_filtering"] = "tier4_advisor_level"

    filepath = _write_yaml(tmp_path, cfg)
    with pytest.raises(ConfigValidationError, match="tier5_pod_isolation"):
        load_config(filepath)


# ── Test 5: IB without chinese_wall fails ────────────────────────


def test_ib_without_chinese_wall_fails(tmp_path: Path):
    """Tier 1 IB MUST use tier1_chinese_wall MNPI filtering."""
    cfg = _base_config(archetype="tier1_investment_bank")
    cfg["compliance"]["mnpi_filtering"] = "tier4_advisor_level"

    filepath = _write_yaml(tmp_path, cfg)
    with pytest.raises(ConfigValidationError, match="tier1_chinese_wall"):
        load_config(filepath)


# ── Test 6: WORM retention below 6 years fails ──────────────────


def test_worm_retention_below_6_years_fails(tmp_path: Path):
    """SEC 17a-4: WORM retention MUST be >= 6 years."""
    cfg = _base_config()
    cfg["compliance"]["worm_retention_years"] = 3

    filepath = _write_yaml(tmp_path, cfg)
    with pytest.raises(ConfigValidationError, match="(?i)worm|retention|17a-4"):
        load_config(filepath)


# ── Test 7: Credential detection rejects raw API keys ────────────


def test_credential_detection_rejects_raw_api_key(tmp_path: Path):
    """Rule 9: Raw credentials in config MUST be rejected."""
    cfg = _base_config()
    cfg["firm"]["name"] = "api_key: sk-1234567890abcdef"

    filepath = _write_yaml(tmp_path, cfg)
    with pytest.raises(ConfigValidationError, match="(?i)credential"):
        load_config(filepath)


# ── Test 8: Credential detection allows Vault refs ───────────────


def test_credential_detection_allows_vault_refs(tmp_path: Path):
    """Rule 9: Vault/Secrets Manager references are allowed."""
    cfg = _base_config()
    # Vault refs should NOT trigger credential detection
    cfg["vendors"]["compliance_archive"] = "${VAULT:smarsh/api_key}"

    filepath = _write_yaml(tmp_path, cfg)
    # Should not raise — Vault refs are safe
    config = load_config(filepath)
    assert config.vendors.compliance_archive == "${VAULT:smarsh/api_key}"


# ── Test 9: Missing config file raises ConfigNotFoundError ───────


def test_missing_config_raises_not_found():
    """Non-existent file must raise ConfigNotFoundError."""
    with pytest.raises(ConfigNotFoundError):
        load_config("/nonexistent/path/enterprise-config-phantom.yaml")


# ── Test 10: Cache hit returns same object ───────────────────────


def test_cache_hit_returns_same_object():
    """Second load of same path returns the cached instance (identity check)."""
    config1 = load_config(TIER4_RIA_PATH)
    config2 = load_config(TIER4_RIA_PATH)

    assert config1 is config2  # Same object — cache hit


# ── Test 11: validate_config_file warns for BD without Smarsh ────


def test_validate_config_file_warns_bd_without_smarsh(tmp_path: Path):
    """BD without Smarsh should produce a warning (not an error)."""
    cfg = _base_config(archetype="tier3_broker_dealer")
    cfg["compliance"]["suitability_standard"] = "reg_bi"
    cfg["compliance"]["principal_review_enabled"] = True
    cfg["compliance"]["smarsh_enabled"] = False

    filepath = _write_yaml(tmp_path, cfg)
    issues = validate_config_file(filepath)

    assert any("Smarsh" in issue for issue in issues)
    assert any("WARN" in issue for issue in issues)


# ── Test 12: Hot reload callback fires on reload_config ──────────


def test_hot_reload_callback_fires():
    """reload_config must notify registered callbacks."""
    callback_calls: list[tuple[str, EnterpriseConfig]] = []

    def on_reload(cache_key: str, config: EnterpriseConfig) -> None:
        callback_calls.append((cache_key, config))

    register_reload_callback(on_reload)

    try:
        # Initial load
        load_config(TIER4_RIA_PATH)
        assert len(callback_calls) == 0  # load_config does NOT fire callbacks

        # Reload fires callback
        reloaded = reload_config(TIER4_RIA_PATH)
        assert len(callback_calls) == 1
        assert callback_calls[0][1] is reloaded
        assert callback_calls[0][1].archetype == Archetype.tier4_independent_ria
    finally:
        # Clean up: remove our callback to avoid polluting other tests
        from loader import _reload_callbacks
        _reload_callbacks.remove(on_reload)
