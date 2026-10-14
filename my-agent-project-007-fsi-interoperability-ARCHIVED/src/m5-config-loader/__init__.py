"""
M5 Enterprise Config Loader — Project 007 FSI Interoperability Platform.

Loads per-firm YAML configuration and validates with Pydantic v2.
Pure data module: calls nothing, is called by M2, M4, M6, M8, M9.

Config files live in config/ directory. Each firm gets its own YAML.
Two templates ship: tier3-bd and tier4-ria.

Usage:
    from m5_config_loader import load_config, EnterpriseConfig

    config = load_config("config/enterprise-config-tier4-ria.yaml")
"""

try:
    from .loader import (
        ConfigLoadError,
        ConfigNotFoundError,
        ConfigParseError,
        ConfigValidationError,
        clear_cache,
        get_config,
        list_available_configs,
        load_config,
        register_reload_callback,
        reload_config,
        validate_config_file,
    )
    from .models import (
        Archetype,
        Channel,
        Channels,
        Compliance,
        CrmVendor,
        CustodianVendor,
        Deployment,
        EnterpriseConfig,
        FirmIdentity,
        Jurisdiction,
        LlmModel,
        MarketDataVendor,
        Memory,
        MnpiFilterLevel,
        PlanningVendor,
        PortfolioVendor,
        PrincipalReviewMode,
        RegBiConfig,
        RegistrationType,
        Runtime,
        Specialist,
        Specialists,
        SuitabilityStandard,
        Topology,
        Vendors,
    )
except ImportError:
    # Fallback for when running outside package context (e.g. pytest with hyphenated dirs)
    from loader import (  # type: ignore[no-redef]
        ConfigLoadError,
        ConfigNotFoundError,
        ConfigParseError,
        ConfigValidationError,
        clear_cache,
        get_config,
        list_available_configs,
        load_config,
        register_reload_callback,
        reload_config,
        validate_config_file,
    )
    from models import (  # type: ignore[no-redef]
        Archetype,
        Channel,
        Channels,
        Compliance,
        CrmVendor,
        CustodianVendor,
        Deployment,
        EnterpriseConfig,
        FirmIdentity,
        Jurisdiction,
        LlmModel,
        MarketDataVendor,
        Memory,
        MnpiFilterLevel,
        PlanningVendor,
        PortfolioVendor,
        PrincipalReviewMode,
        RegBiConfig,
        RegistrationType,
        Runtime,
        Specialist,
        Specialists,
        SuitabilityStandard,
        Topology,
        Vendors,
    )

__all__ = [
    # Models
    "Archetype",
    "Channel",
    "Channels",
    "Compliance",
    "CrmVendor",
    "CustodianVendor",
    "Deployment",
    "EnterpriseConfig",
    "FirmIdentity",
    "Jurisdiction",
    "LlmModel",
    "MarketDataVendor",
    "Memory",
    "MnpiFilterLevel",
    "PlanningVendor",
    "PortfolioVendor",
    "PrincipalReviewMode",
    "RegBiConfig",
    "RegistrationType",
    "Runtime",
    "Specialist",
    "Specialists",
    "SuitabilityStandard",
    "Topology",
    "Vendors",
    # Loader
    "load_config",
    "get_config",
    "reload_config",
    "clear_cache",
    "validate_config_file",
    "list_available_configs",
    "register_reload_callback",
    # Errors
    "ConfigLoadError",
    "ConfigNotFoundError",
    "ConfigParseError",
    "ConfigValidationError",
]
