"""
M5 Enterprise Config Loader -- Pydantic v2 models + YAML loader.

Loads per-firm YAML config defining: archetype, vendors, compliance regime,
jurisdiction, channels, MNPI rules, HITL timeout, specialist agents, memory tiers.

Called by M2, M4, M8, M9 (4 consumers). Calls nothing (pure data library).
Zero credentials in config. All secrets via Vault/Secrets Manager at runtime.

v0.4.0 additions (Known Blockers resolution):
  * `IntentRouterConfig` -- M9 v0.2.0 AC12.4 contract.
  * `PipelineConfig`     -- M8 v0.2.0 Known Blockers row 1 contract.

Ops Hardening Wave 3 additions:
  * `MinIOWormConfig`    -- M10 real WORM backend config (MinIO Object
    Lock in Compliance mode). Nested under ComplianceConfig.minio_worm.
"""

from __future__ import annotations

import hashlib
import re
import warnings
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# Constants
# =============================================================================

CONFIG_VERSION = "0.4.0"

VALID_CHANNELS: frozenset[str] = frozenset({
    "slack", "teams", "web", "whatsapp", "email", "sms",
})

VALID_SPECIALISTS: frozenset[str] = frozenset({
    "client_service", "research", "execution", "onboarding",
})

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"),
    re.compile(r"-----BEGIN"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[bp]-[A-Za-z0-9\-]+"),
    re.compile(r"postgresql://"),
    re.compile(r"mongodb://"),
    re.compile(r"redis://"),
    re.compile(r"mysql://"),
]

_SECRET_KEYWORDS: list[str] = [
    "password", "secret", "api_key", "apikey", "token=",
]

_OPA_BUNDLE_PREFIX_MAP: dict[str, str] = {
    "tier1_investment_bank": "opa-bundles/tier1/",
    "tier2_asset_manager": "opa-bundles/tier2/",
    "tier3_broker_dealer": "opa-bundles/tier3/",
    "tier4_independent_ria": "opa-bundles/tier4/",
    "tier5_hedge_fund": "opa-bundles/tier5/",
}

# Vault path pattern -- `secret/data/<module>/<...>` -- no literal creds.
_VAULT_PATH_RE: re.Pattern[str] = re.compile(r"^secret/data/[\w\-<>/]+$")

# Dedicated M10/MinIO Vault-path pattern (tighter than the generic one).
_M10_MINIO_VAULT_PATH_RE: re.Pattern[str] = re.compile(
    r"^secret/data/m10/minio/[\w\-/<>]+$"
)


# =============================================================================
# Exceptions
# =============================================================================

class ConfigLoadError(Exception):
    """Raised on YAML parse failure or file I/O error."""

class ConfigSecurityError(Exception):
    """Raised when credential patterns are detected in config data."""


# =============================================================================
# Enums (8 total)
# =============================================================================

class Archetype(str, Enum):
    tier1_investment_bank = "tier1_investment_bank"
    tier2_asset_manager = "tier2_asset_manager"
    tier3_broker_dealer = "tier3_broker_dealer"
    tier4_independent_ria = "tier4_independent_ria"
    tier5_hedge_fund = "tier5_hedge_fund"

class Jurisdiction(str, Enum):
    us = "us"
    eu = "eu"
    uk = "uk"
    sg = "sg"
    hk = "hk"

class RegistrationType(str, Enum):
    ria_only = "ria_only"
    bd_only = "bd_only"
    dual_registered = "dual_registered"

class Topology(str, Enum):
    cloud = "cloud"
    hybrid = "hybrid"
    onprem = "onprem"

class Runtime(str, Enum):
    managed_agents = "managed_agents"
    strands_sdk = "strands_sdk"

class SuitabilityStandard(str, Enum):
    fiduciary = "fiduciary"
    reg_bi = "reg_bi"

class PrincipalReviewMode(str, Enum):
    pre_use = "pre_use"
    post_use = "post_use"

class TimeoutAction(str, Enum):
    block = "block"
    escalate = "escalate"


# =============================================================================
# Shared validators
# =============================================================================

def _assert_vault_path_no_literal_secret(value: str) -> str:
    """Reject anything that looks like an embedded credential."""
    if not value:
        raise ValueError("vault path must be non-empty")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"Vault path must not contain credential-like substring: "
                f"pattern '{pattern.pattern}' matched"
            )
    if not _VAULT_PATH_RE.match(value):
        raise ValueError(
            f"Vault path '{value}' does not match secret/data/... shape"
        )
    return value


# =============================================================================
# Sub-Models
# =============================================================================

class FirmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1)
    lei: Optional[str] = Field(None)
    crd_number: str = Field(..., min_length=1)
    registration_type: RegistrationType

    @field_validator("lei")
    @classmethod
    def validate_lei(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[A-Z0-9]{18}[0-9]{2}$", v):
            raise ValueError(
                f"Invalid LEI format: '{v}'. "
                "Must be 18 alphanumeric + 2 check digits (ISO 17442)."
            )
        return v


class JurisdictionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: Jurisdiction
    data_residency: Jurisdiction


class DeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topology: Topology
    region: str = Field(..., min_length=1)
    runtime: Runtime


class VendorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crm: str = Field(..., min_length=1)
    portfolio: str = Field(..., min_length=1)
    planning: Optional[str] = None
    custodians: list[str] = Field(..., min_length=1)
    market_data: Optional[str] = None
    compliance_archive: Optional[str] = None


class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: list[str] = Field(..., min_length=1)
    primary: str

    @model_validator(mode="after")
    def validate_channels(self) -> ChannelConfig:
        invalid = set(self.enabled) - VALID_CHANNELS
        if invalid:
            raise ValueError(
                f"Invalid channels: {sorted(invalid)}. "
                f"Valid: {sorted(VALID_CHANNELS)}"
            )
        if self.primary not in VALID_CHANNELS:
            raise ValueError(
                f"Invalid primary channel: '{self.primary}'. "
                f"Valid: {sorted(VALID_CHANNELS)}"
            )
        if self.primary not in self.enabled:
            raise ValueError(
                f"Primary channel '{self.primary}' must be in "
                f"enabled list: {self.enabled}"
            )
        return self


class ConflictEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    mitigation: str = Field(..., min_length=1)


class PrincipalReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: PrincipalReviewMode
    sla_hours: int = Field(4, ge=1)
    timeout_action: TimeoutAction = TimeoutAction.block


class BsaAmlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    ctr_threshold: float = 10000.0
    sar_structuring_threshold: float = 8000.0


class RegBiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: str = "default"
    conflict_inventory: list[ConflictEntry] = Field(default_factory=list)
    auto_generate: bool = True
    require_advisor_review: bool = True
    narrative_model: str = "haiku"


# =============================================================================
# Ops Hardening Wave 3 -- MinIOWormConfig (M10 WORM backend)
# =============================================================================

class MinIOWormConfig(BaseModel):
    """M10 MinIO WORM backend runtime config.

    Vault paths only -- no embedded credentials. Retention floor is
    SEC 17a-4 (6 years); enforced here at parse time and again at the
    M10 backend constructor + AuditLogger write path (defence-in-depth).

    Fields:
        endpoint_url: ``http[s]://host[:port]``. MinIO server URL.
        bucket_name: DNS-valid S3 bucket name (3--63 chars, lowercase,
            dots/hyphens).
        region: MinIO region. Defaults to ``us-east-1``.
        access_key_vault_path: Vault path to the MinIO access key.
            Must match ``secret/data/m10/minio/...``.
        secret_key_vault_path: Vault path to the MinIO secret key.
            Same pattern.
        retention_years: Integer >= 6 (SEC 17a-4 floor).
        object_lock_mode: ``COMPLIANCE`` (default) or ``GOVERNANCE``.
            GOVERNANCE raises ``UserWarning`` at construction because
            privileged users can release the lock.
        secure: ``True`` when the endpoint_url uses HTTPS (enforced
            consistent with the scheme).
    """

    model_config = ConfigDict(extra="forbid")

    endpoint_url: str = Field(
        ...,
        pattern=r"^https?://[A-Za-z0-9._\-]+(:[0-9]{1,5})?(/.*)?$",
        description="MinIO endpoint URL (http[s]://host[:port]).",
    )
    bucket_name: str = Field(..., min_length=3, max_length=63)
    region: str = Field(default="us-east-1", min_length=1)
    access_key_vault_path: str = Field(...)
    secret_key_vault_path: str = Field(...)
    retention_years: int = Field(default=6, ge=6)
    object_lock_mode: Literal["COMPLIANCE", "GOVERNANCE"] = "COMPLIANCE"
    secure: bool = True

    @field_validator("bucket_name")
    @classmethod
    def _dns_valid_bucket(cls, v: str) -> str:
        # S3/MinIO DNS rules: lowercase, start/end alphanumeric,
        # dots + hyphens permitted in the middle, no consecutive
        # dots, no dot-dash / dash-dot sequences.
        if not re.match(r"^[a-z0-9]([a-z0-9.\-]*[a-z0-9])?$", v):
            raise ValueError(
                f"bucket_name {v!r} must be DNS-valid (lowercase, "
                "alphanumeric, dots/hyphens in middle only)."
            )
        if ".." in v or ".-" in v or "-." in v:
            raise ValueError(
                f"bucket_name {v!r} contains consecutive dots or "
                "dot-dash/dash-dot."
            )
        return v

    @field_validator("access_key_vault_path", "secret_key_vault_path")
    @classmethod
    def _minio_vault_path(cls, v: str) -> str:
        # Reuse the shared literal-secret scanner + the tighter M10
        # prefix pattern.
        _assert_vault_path_no_literal_secret(v)
        if not _M10_MINIO_VAULT_PATH_RE.match(v):
            raise ValueError(
                f"Vault path {v!r} must match 'secret/data/m10/minio/...'"
            )
        return v

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> MinIOWormConfig:
        if self.endpoint_url.startswith("https://") and not self.secure:
            raise ValueError(
                "secure must be True when endpoint_url uses https://."
            )
        if self.endpoint_url.startswith("http://") and self.secure:
            # Accept but warn -- developer/test on plain HTTP often
            # forgets to flip secure=False. We keep the flag as the
            # source of truth but this is a common footgun.
            warnings.warn(
                "MinIOWormConfig: endpoint_url is http:// but secure=True; "
                "MinIO SDK will attempt TLS and fail. Set secure=False "
                "for cleartext endpoints (dev/test only).",
                UserWarning,
                stacklevel=2,
            )
        if self.object_lock_mode == "GOVERNANCE":
            warnings.warn(
                "MinIOWormConfig: object_lock_mode=GOVERNANCE -- a "
                "privileged compliance officer can release the lock. "
                "COMPLIANCE is the SEC 17a-4 default.",
                UserWarning,
                stacklevel=2,
            )
        return self


class ComplianceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suitability_standard: SuitabilityStandard
    reg_bi_enabled: bool
    smarsh_enabled: bool
    principal_review_enabled: bool
    principal_review_config: Optional[PrincipalReviewConfig] = None
    bsa_aml_config: Optional[BsaAmlConfig] = None
    reg_bi_config: Optional[RegBiConfig] = None
    worm_retention_years: int = Field(..., ge=6)
    mnpi_filtering: str = Field(..., min_length=1)
    hitl_timeout_hours: int = Field(24, ge=1, le=168)
    # Ops Hardening Wave 3: real MinIO Object Lock WORM backend config
    # for M10. None by default -- InMemoryAuditBackend(tier="worm") is
    # still the dev/test default. Provisioning the bucket is operator
    # responsibility; M10 backend fails loud if Object Lock is not
    # COMPLIANCE-mode configured.
    minio_worm: Optional[MinIOWormConfig] = None

    @model_validator(mode="after")
    def validate_principal_review(self) -> ComplianceConfig:
        if self.principal_review_enabled and self.principal_review_config is None:
            raise ValueError(
                "principal_review_config required when "
                "principal_review_enabled is True"
            )
        return self


# =============================================================================
# NEW in v0.4.0: IntentRouterConfig (M9 v0.2.0 AC12.4)
# =============================================================================

class IntentRouterConfig(BaseModel):
    """M9 Intent Router runtime config. 8 fields per spec Known Blockers row 2.

    Vault paths only -- no embedded creds. Threshold ordering enforced.
    """
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(
        default="anthropic.claude-3-5-haiku-20241022-v1:0",
        min_length=1,
    )
    provider: Literal["bedrock", "azure", "gcp", "self_hosted"] = "bedrock"
    region: str = Field(default="us-east-1", min_length=1)
    confidence_high: float = Field(default=0.95, ge=0.0, le=1.0)
    confidence_med: float = Field(default=0.80, ge=0.0, le=1.0)
    timeout_ms: int = Field(default=1500, ge=1)
    fallback_enabled: bool = True
    tenant_hmac_key_vault_path: str = Field(
        default="secret/data/m9/tenants/<tenant_id>/hmac_key",
    )

    @field_validator("tenant_hmac_key_vault_path")
    @classmethod
    def _no_literal_secret(cls, v: str) -> str:
        return _assert_vault_path_no_literal_secret(v)

    @model_validator(mode="after")
    def _validate_threshold_ordering(self) -> IntentRouterConfig:
        if not (self.confidence_high > self.confidence_med > 0):
            raise ValueError(
                f"confidence_high ({self.confidence_high}) must be > "
                f"confidence_med ({self.confidence_med}) > 0"
            )
        return self


# =============================================================================
# NEW in v0.4.0: PipelineConfig (M8 v0.2.0 Known Blockers row 1)
# =============================================================================

class PipelineConfig(BaseModel):
    """M8 Pipeline Engine runtime config. 15 fields per spec.

    Vault paths only. Concurrency + wall-clock caps enforced.
    """
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(
        default="anthropic.claude-sonnet-4-5-20250929-v1:0",
        min_length=1,
    )
    model_provider: Literal[
        "bedrock", "azure", "gcp", "self_hosted"
    ] = "bedrock"
    region: str = Field(default="us-east-1", min_length=1)
    checkpointer_backend: Literal["memory", "postgres", "dynamodb"] = "postgres"
    checkpointer_dsn_vault_path: str = Field(...)
    hitl_hmac_key_vault_path: str = Field(...)
    hitl_timeout_seconds: int = Field(default=14_400, ge=1)
    max_concurrent_instruments: int = Field(default=10, ge=1, le=100)
    max_pipeline_wall_clock_seconds: int = Field(default=1_200, ge=1)
    alert_pipeline_wall_clock_seconds: int = Field(default=900, ge=1)
    gateway_base_url: str = Field(...)
    gateway_mtls_client_cert_path: str = Field(...)
    audit_base_url: str = Field(...)
    audit_mtls_client_cert_path: str = Field(...)
    token_budgets: dict[str, int] = Field(
        default_factory=lambda: {
            "stage_12_cross_source_synthesis": 15_000,
            "stage_14_instrument_analysis": 8_000,
            "stage_18_final_synthesis": 12_000,
        }
    )

    @field_validator("checkpointer_dsn_vault_path", "hitl_hmac_key_vault_path")
    @classmethod
    def _no_literal_secret(cls, v: str) -> str:
        return _assert_vault_path_no_literal_secret(v)

    @model_validator(mode="after")
    def _validate_wall_clock_ordering(self) -> PipelineConfig:
        if self.alert_pipeline_wall_clock_seconds >= self.max_pipeline_wall_clock_seconds:
            raise ValueError(
                "alert_pipeline_wall_clock_seconds must be < "
                "max_pipeline_wall_clock_seconds"
            )
        return self


# =============================================================================
# SpecialistConfig (extended for intent_router + pipeline)
# =============================================================================

class SpecialistConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: list[str]
    supervisor_model: str = "haiku"
    research_model: str = "sonnet"
    client_service_model: str = "haiku"
    execution_model: Optional[str] = None
    onboarding_model: Optional[str] = None
    # v0.4.0 additions: optional sub-configs for M9 + M8.
    intent_router: Optional[IntentRouterConfig] = None
    pipeline: Optional[PipelineConfig] = None

    @field_validator("enabled")
    @classmethod
    def validate_specialists(cls, v: list[str]) -> list[str]:
        if "compliance" in v:
            raise ValueError(
                "compliance specialist is always implicit (OPA, not LLM) "
                "-- do not include in enabled list"
            )
        invalid = set(v) - VALID_SPECIALISTS
        if invalid:
            raise ValueError(
                f"Invalid specialists: {sorted(invalid)}. "
                f"Valid: {sorted(VALID_SPECIALISTS)}"
            )
        return v


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    l1_ttl_hours: int = Field(8, ge=1)
    l2_retention_days: int = Field(7, ge=1)
    l3_retention_years: int = Field(2, ge=1)
    l4_enabled: bool = True
    l5_enabled: bool = True


# =============================================================================
# Top-Level Model
# =============================================================================

class EnterpriseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    firm: FirmConfig
    archetype: Archetype
    jurisdiction: JurisdictionConfig
    deployment: DeploymentConfig
    vendors: VendorConfig
    channels: ChannelConfig
    compliance: ComplianceConfig
    specialists: SpecialistConfig
    memory: MemoryConfig
    config_hash: str = Field("")

    @model_validator(mode="after")
    def validate_cross_fields(self) -> EnterpriseConfig:
        if self.config_version != CONFIG_VERSION:
            raise ValueError(
                f"Config version mismatch: got '{self.config_version}', "
                f"expected '{CONFIG_VERSION}'"
            )
        if (self.archetype == Archetype.tier3_broker_dealer
                and not self.compliance.principal_review_enabled):
            warnings.warn(
                "BD archetype without principal review enabled -- "
                "required for FINRA 2210 compliance",
                UserWarning, stacklevel=2)
        if (self.archetype == Archetype.tier3_broker_dealer
                and not self.compliance.smarsh_enabled):
            warnings.warn(
                "BD archetype without Smarsh archiving enabled -- "
                "required before BD deployment",
                UserWarning, stacklevel=2)
        return self

    def get_opa_bundle_prefix(self) -> str:
        """Return OPA bundle path prefix for this archetype."""
        return _OPA_BUNDLE_PREFIX_MAP[self.archetype.value]


# =============================================================================
# Security Scanner
# =============================================================================

def validate_no_secrets(data: dict | list | str, _path: str = "root") -> None:
    """Recursively scan config data for credential patterns."""
    if isinstance(data, dict):
        for key, value in data.items():
            validate_no_secrets(value, _path=f"{_path}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            validate_no_secrets(item, _path=f"{_path}[{i}]")
    elif isinstance(data, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(data):
                raise ConfigSecurityError(
                    f"Credential pattern detected at {_path}: "
                    f"matches '{pattern.pattern}'"
                )
        lower = data.lower()
        for keyword in _SECRET_KEYWORDS:
            if keyword in lower and "=" in data:
                raise ConfigSecurityError(
                    f"Credential keyword detected at {_path}: "
                    f"contains '{keyword}'"
                )


# =============================================================================
# Loader
# =============================================================================

def load_enterprise_config(path: Path) -> EnterpriseConfig:
    """Load and validate a per-firm YAML config file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_bytes = path.read_bytes()
    config_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        data = yaml.safe_load(raw_bytes.decode("utf-8"))
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Expected YAML mapping at top level in {path}, "
            f"got {type(data).__name__}"
        )

    validate_no_secrets(data)
    config = EnterpriseConfig.model_validate(data)
    config.config_hash = config_hash
    return config


def load_intent_router_config(
    enterprise_config: EnterpriseConfig,
) -> Optional[IntentRouterConfig]:
    """Return the IntentRouterConfig sub-block if present, else None."""
    return enterprise_config.specialists.intent_router


def load_pipeline_config(
    enterprise_config: EnterpriseConfig,
) -> Optional[PipelineConfig]:
    """Return the PipelineConfig sub-block if present, else None."""
    return enterprise_config.specialists.pipeline
