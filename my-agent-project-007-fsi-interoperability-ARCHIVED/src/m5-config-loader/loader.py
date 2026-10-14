"""
M5 Enterprise Config Loader.

Project 007 FSI Interoperability Platform.

Loads YAML from disk, validates with Pydantic v2, caches per firm_id.
Pure data module — no network calls, no vendor access, no LLM.

Features:
  - YAML loading with yaml.safe_load only (no arbitrary code execution)
  - Pydantic v2 validation with archetype-specific invariants
  - In-memory cache with reload capability
  - Hot reload support via file watcher (ARCH-04 M5 spec)
  - CI/CD validation helper for pre-commit / pipeline checks
  - Typed error hierarchy for precise error handling

Usage:
    from m5_config_loader.loader import load_config, reload_config

    config = load_config("config/enterprise-config-tier4-ria.yaml")
    print(config.archetype)                    # Archetype.tier4_independent_ria
    print(config.compliance.worm_retention_years)  # 6
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional, Union

import yaml

try:
    from .models import EnterpriseConfig
except ImportError:
    from models import EnterpriseConfig

logger = logging.getLogger("m5.config-loader")


# ── Error types ──────────────────────────────────────────────────────

class ConfigLoadError(Exception):
    """Base error for config loading failures."""


class ConfigNotFoundError(ConfigLoadError):
    """Config file does not exist on disk."""


class ConfigValidationError(ConfigLoadError):
    """Config YAML fails Pydantic v2 validation."""


class ConfigParseError(ConfigLoadError):
    """Config file is not valid YAML."""


# ── Thread-safe in-memory cache ──────────────────────────────────────

_cache_lock = threading.Lock()
_config_cache: dict[str, EnterpriseConfig] = {}
_reload_callbacks: list[Callable[[str, EnterpriseConfig], None]] = []


def load_config(path: Union[str, Path]) -> EnterpriseConfig:
    """
    Load and validate an enterprise config YAML file.

    Returns cached instance on subsequent calls for the same path.
    Thread-safe.

    Args:
        path: Path to the YAML config file (relative or absolute).

    Returns:
        Validated EnterpriseConfig instance.

    Raises:
        ConfigNotFoundError: File does not exist.
        ConfigParseError: YAML syntax error.
        ConfigValidationError: Pydantic validation failure.
    """
    filepath = Path(path).resolve()
    cache_key = str(filepath)

    with _cache_lock:
        if cache_key in _config_cache:
            logger.debug("Config cache hit: %s", filepath.name)
            return _config_cache[cache_key]

    # Parse outside lock (IO-bound)
    config = _load_and_validate(filepath)

    with _cache_lock:
        _config_cache[cache_key] = config

    logger.info(
        "Loaded config: %s (archetype=%s, firm=%s)",
        filepath.name,
        config.archetype.value,
        config.firm.name,
    )
    return config


def get_config(path: Union[str, Path]) -> EnterpriseConfig:
    """Alias for load_config (cache-first)."""
    return load_config(path)


def reload_config(path: Union[str, Path]) -> EnterpriseConfig:
    """
    Force-reload a config file, bypassing cache.

    Supports hot reload: notifies registered callbacks after reload.
    """
    filepath = Path(path).resolve()
    cache_key = str(filepath)

    config = _load_and_validate(filepath)

    with _cache_lock:
        _config_cache[cache_key] = config

    logger.info("Reloaded config: %s (archetype=%s)", filepath.name, config.archetype.value)

    # Notify hot-reload subscribers
    for cb in _reload_callbacks:
        try:
            cb(cache_key, config)
        except Exception:
            logger.exception("Reload callback failed for %s", cache_key)

    return config


def clear_cache() -> None:
    """Clear all cached configs. Useful for testing."""
    with _cache_lock:
        _config_cache.clear()
    logger.debug("Config cache cleared")


def register_reload_callback(
    callback: Callable[[str, EnterpriseConfig], None],
) -> None:
    """
    Register a callback for hot-reload notifications (ARCH-04 M5 spec).

    Callback receives (cache_key, new_config) after every reload_config call.
    """
    _reload_callbacks.append(callback)


# ── CI/CD validation helper ──────────────────────────────────────────

def validate_config_file(path: Union[str, Path]) -> list[str]:
    """
    Validate a config file and return a list of issues (empty = valid).

    Useful for CI/CD pre-commit checks and GitHub Actions pipelines.
    Returns errors as strings; does not raise.
    """
    issues: list[str] = []

    try:
        config = _load_and_validate(Path(path).resolve())
    except ConfigNotFoundError:
        return [f"ERROR: File not found: {path}"]
    except ConfigParseError as e:
        return [f"ERROR: {e}"]
    except ConfigValidationError as e:
        return [f"ERROR: {e}"]
    except ConfigLoadError as e:
        return [f"ERROR: {e}"]

    # ── Semantic warnings beyond Pydantic validation ─────────────
    if (
        config.archetype.value.startswith("tier3")
        and not config.compliance.smarsh_enabled
    ):
        issues.append(
            "WARN: Tier 3 BD without Smarsh enabled. "
            "Required before BD deployment (IMPL-06 Blocker 1)."
        )

    if (
        config.compliance.bsa_aml_enabled
        and config.compliance.ctr_threshold != 10000
    ):
        issues.append(
            f"WARN: CTR threshold is ${config.compliance.ctr_threshold:,}, "
            "federal requirement is $10,000."
        )

    if config.deployment.topology.value == "onprem":
        issues.append(
            "WARN: On-prem topology is Phase 5 (DEFERRED). "
            "Do not deploy until funded."
        )

    # UK jurisdiction may require 7+ year retention (FCA SYSC 9)
    all_jurisdictions = [config.jurisdiction.primary] + config.jurisdiction.additional
    if config.compliance.worm_retention_years < 7 and "UK" in all_jurisdictions:
        issues.append(
            f"WARN: UK jurisdiction may require 7+ year retention (FCA SYSC 9). "
            f"Currently set to {config.compliance.worm_retention_years}."
        )

    # EU GDPR / MiFID II data residency check
    if "EU" in all_jurisdictions and config.jurisdiction.data_residency != "EU":
        issues.append(
            "WARN: EU jurisdiction with non-EU data residency. "
            "Check GDPR Article 44+ data transfer requirements."
        )

    return issues


def list_available_configs(config_dir: str = "config") -> list[Path]:
    """List all enterprise-config YAML files in the config directory."""
    config_path = Path(config_dir)
    if not config_path.is_dir():
        return []
    return sorted(config_path.glob("enterprise-config-*.yaml"))


# ── Internal helpers ─────────────────────────────────────────────────

def _load_and_validate(filepath: Path) -> EnterpriseConfig:
    """Load YAML from disk and validate with Pydantic v2."""
    if not filepath.exists():
        raise ConfigNotFoundError(f"Config file not found: {filepath}")

    if filepath.suffix not in (".yaml", ".yml"):
        raise ConfigLoadError(f"Config file must be .yaml or .yml: {filepath}")

    # SECURITY: yaml.safe_load only — no arbitrary code execution
    try:
        raw = filepath.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ConfigParseError(f"YAML parse error in {filepath.name}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigParseError(
            f"Config must be a YAML mapping, got {type(data).__name__}"
        )

    try:
        return EnterpriseConfig.model_validate(data)
    except Exception as e:
        raise ConfigValidationError(
            f"Validation failed for {filepath.name}: {e}"
        ) from e
