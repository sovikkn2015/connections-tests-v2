"""
M5 Enterprise Config — Pydantic v2 Models.

Project 007 FSI Interoperability Platform.

Defines the complete enterprise configuration schema for all 5 FSI archetypes.
Every module that needs firm context (M2, M4, M6, M8, M9) receives a validated
EnterpriseConfig instance — never raw YAML.

Rules enforced:
  - WORM retention >= 6 years (SEC 17a-4, Rule 4)
  - Zero credentials in config (Rule 9) — secrets via Vault/Secrets Manager refs
  - BD must have principal_review_enabled + reg_bi suitability (FINRA 2210)
  - HF must have pod_isolation MNPI filtering
  - All 5 archetypes: tier1_investment_bank .. tier5_hedge_fund
  - Hot reload support via file watcher (ARCH-04 M5 spec)
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Credential leak detection ────────────────────────────────────────

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret|credential)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key
    re.compile(r"(?i)-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY"),  # PEM private key
]

# Allowed secret reference patterns (Vault / Secrets Manager / env)
_VAULT_REF = re.compile(r"^\$\{(VAULT|ENV|SECRETS_MANAGER):.+\}$")


def _contains_credential(value: str) -> bool:
    """Return True if value looks like a raw credential (not a Vault ref)."""
    if _VAULT_REF.match(value):
        return False
    return any(p.search(value) for p in _SECRET_PATTERNS)


# ── Enums — all 5 archetypes + supporting types ─────────────────────

class Archetype(str, Enum):
    """Five FSI enterprise archetypes (ARCH-09, Part 6)."""
    tier1_investment_bank = "tier1_investment_bank"
    tier2_asset_manager = "tier2_asset_manager"
    tier3_broker_dealer = "tier3_broker_dealer"
    tier4_independent_ria = "tier4_independent_ria"
    tier5_hedge_fund = "tier5_hedge_fund"


class RegistrationType(str, Enum):
    ria_only = "ria_only"
    bd_only = "bd_only"
    dual_registered = "dual_registered"


class Topology(str, Enum):
    cloud = "cloud"
    hybrid = "hybrid"
    onprem = "onprem"


class Runtime(str, Enum):
    managed_agents = "managed-agents"
    strands_sdk = "strands-sdk"


class SuitabilityStandard(str, Enum):
    fiduciary = "fiduciary"
    reg_bi = "reg_bi"


class MnpiFilterLevel(str, Enum):
    """Per-archetype MNPI filtering level (ARCH-09 6-Layer Memory)."""
    tier1_chinese_wall = "tier1_chinese_wall"
    tier2_portfolio_level = "tier2_portfolio_level"
    tier3_advisor_level = "tier3_advisor_level"
    tier4_advisor_level = "tier4_advisor_level"
    tier5_pod_isolation = "tier5_pod_isolation"


class CrmVendor(str, Enum):
    salesforce_fsc = "salesforce_fsc"
    wealthbox = "wealthbox"
    redtail = "redtail"
    dynamics_365 = "dynamics_365"


class PortfolioVendor(str, Enum):
    orion = "orion"
    envestnet = "envestnet"
    schwab = "schwab"


class PlanningVendor(str, Enum):
    emoney = "emoney"
    moneyguidepro = "moneyguidepro"
    rightcapital = "rightcapital"


class CustodianVendor(str, Enum):
    schwab = "schwab"
    fidelity = "fidelity"
    pershing = "pershing"


class MarketDataVendor(str, Enum):
    bloomberg = "bloomberg"
    factset = "factset"
    alpha_vantage = "alpha_vantage"


class Channel(str, Enum):
    slack = "slack"
    teams = "teams"
    whatsapp = "whatsapp"
    web = "web"
    email = "email"


class LlmModel(str, Enum):
    sonnet = "sonnet"
    haiku = "haiku"


class PrincipalReviewMode(str, Enum):
    pre_use = "pre_use"
    post_use = "post_use"


class Specialist(str, Enum):
    client_service = "client_service"
    research = "research"
    execution = "execution"
    onboarding = "onboarding"
    compliance = "compliance"


# ── Sub-models ───────────────────────────────────────────────────────

class FirmIdentity(BaseModel):
    """Firm identification. LEI optional for small RIAs."""
    name: str = Field(..., min_length=1, max_length=255)
    lei: Optional[str] = Field(
        None,
        pattern=r"^[A-Z0-9]{20}$",
        description="ISO 17442 Legal Entity Identifier",
    )
    crd_number: Optional[str] = Field(
        None,
        pattern=r"^\d{1,7}$",
        description="FINRA Central Registration Depository number",
    )
    registration_type: RegistrationType = RegistrationType.ria_only

    @field_validator("name")
    @classmethod
    def name_no_credentials(cls, v: str) -> str:
        if _contains_credential(v):
            raise ValueError("Credential detected in firm name — secrets must use Vault refs")
        return v


class Jurisdiction(BaseModel):
    primary: str = Field(
        "US",
        pattern=r"^[A-Z]{2}(-[A-Z]{2,3})?$",
        description="ISO-3166 country code",
    )
    data_residency: str = Field("US", pattern=r"^[A-Z]{2}$")
    additional: list[str] = Field(
        default_factory=list,
        description="Cross-border jurisdictions (ARCH-06 Gap 7)",
    )


class Deployment(BaseModel):
    topology: Topology = Topology.cloud
    region: str = Field("us-east-1", description="AWS region or equivalent")
    runtime: Runtime = Runtime.managed_agents


class Vendors(BaseModel):
    crm: CrmVendor = CrmVendor.salesforce_fsc
    portfolio: PortfolioVendor = PortfolioVendor.orion
    planning: Optional[PlanningVendor] = PlanningVendor.emoney
    custodians: list[CustodianVendor] = Field(
        default_factory=lambda: [CustodianVendor.schwab],
    )
    market_data: MarketDataVendor = MarketDataVendor.alpha_vantage
    compliance_archive: Optional[str] = Field(
        None,
        description="smarsh or null — required for BD before deployment (IMPL-06 Blocker 1)",
    )

    @field_validator("compliance_archive")
    @classmethod
    def archive_no_credentials(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _contains_credential(v):
            raise ValueError("Credential detected in compliance_archive field")
        return v


class Channels(BaseModel):
    enabled: list[Channel] = Field(
        default_factory=lambda: [Channel.slack, Channel.web],
    )
    primary: Channel = Channel.slack


class RegBiConfig(BaseModel):
    """Reg BI documentation generator config (ARCH-06 Gap 1)."""
    template: str = "default"
    conflict_inventory: list[dict] = Field(default_factory=list)
    auto_generate: bool = True
    require_advisor_review: bool = True
    narrative_model: LlmModel = LlmModel.haiku


class Compliance(BaseModel):
    """
    Compliance configuration.

    Archetype-specific invariants enforced at the root model level:
      - BD: principal_review_enabled=True, suitability_standard=reg_bi
      - HF: mnpi_filtering=tier5_pod_isolation
      - WORM retention >= 6 years (SEC 17a-4)
    """
    suitability_standard: SuitabilityStandard = SuitabilityStandard.fiduciary
    reg_bi_enabled: bool = False
    smarsh_enabled: bool = False
    principal_review_enabled: bool = False
    principal_review_mode: PrincipalReviewMode = PrincipalReviewMode.pre_use
    principal_review_sla_hours: int = Field(4, ge=1, le=48)
    worm_retention_years: int = Field(
        6,
        ge=6,
        description="Minimum 6 years per SEC Rule 17a-4. Immutable once set.",
    )
    mnpi_filtering: MnpiFilterLevel = MnpiFilterLevel.tier4_advisor_level
    bsa_aml_enabled: bool = False
    ctr_threshold: int = Field(
        10000,
        description="Currency Transaction Report threshold (BSA/AML, ARCH-06 Gap 4)",
    )
    sar_structuring_threshold: int = Field(
        8000,
        description="SAR structuring detection threshold",
    )
    reg_bi_config: Optional[RegBiConfig] = None

    @field_validator("worm_retention_years")
    @classmethod
    def worm_retention_minimum(cls, v: int) -> int:
        """SEC 17a-4: WORM retention MUST be >= 6 years. Non-negotiable."""
        if v < 6:
            raise ValueError(
                f"WORM retention {v} years violates SEC 17a-4 minimum of 6 years"
            )
        return v


class Specialists(BaseModel):
    enabled: list[Specialist] = Field(
        default_factory=lambda: [Specialist.client_service, Specialist.research],
    )
    supervisor_model: LlmModel = LlmModel.haiku
    research_model: LlmModel = LlmModel.sonnet
    client_service_model: LlmModel = LlmModel.haiku
    execution_model: LlmModel = LlmModel.haiku
    onboarding_model: LlmModel = LlmModel.haiku


class Memory(BaseModel):
    """6-layer memory config. L6 (compliance/WORM) is always on."""
    l1_ttl_hours: int = Field(8, ge=1, le=24, description="Working memory TTL (Redis)")
    l2_retention_days: int = Field(7, ge=1, le=30, description="Short-term memory (DynamoDB)")
    l3_retention_years: int = Field(2, ge=1, le=10, description="Episodic memory")
    l4_enabled: bool = Field(True, description="Semantic memory (pgvector)")
    l5_enabled: bool = Field(True, description="Procedural memory (advisor prefs)")


# ── Root model ───────────────────────────────────────────────────────

class EnterpriseConfig(BaseModel):
    """
    Root enterprise configuration for one firm.

    Loaded from YAML, validated by Pydantic v2.
    Every module that needs firm context (M2, M4, M6, M8, M9)
    receives this object — never raw YAML.

    Cross-field invariants enforced by model_validator:
      - Tier 3 BD: principal_review_enabled, reg_bi suitability
      - Tier 5 HF: pod_isolation MNPI filtering
      - Tier 1 IB: chinese_wall MNPI filtering
    """

    firm: FirmIdentity
    archetype: Archetype
    jurisdiction: Jurisdiction = Field(default_factory=Jurisdiction)
    deployment: Deployment = Field(default_factory=Deployment)
    vendors: Vendors = Field(default_factory=Vendors)
    channels: Channels = Field(default_factory=Channels)
    compliance: Compliance = Field(default_factory=Compliance)
    specialists: Specialists = Field(default_factory=Specialists)
    memory: Memory = Field(default_factory=Memory)

    @model_validator(mode="after")
    def enforce_archetype_invariants(self) -> "EnterpriseConfig":
        """Enforce per-archetype compliance invariants."""
        arch = self.archetype
        comp = self.compliance

        # ── Tier 3 Broker-Dealer: FINRA 2210 + Reg BI ───────────
        if arch == Archetype.tier3_broker_dealer:
            if not comp.principal_review_enabled:
                raise ValueError(
                    "Tier 3 broker-dealers MUST enable principal_review_enabled "
                    "(FINRA Rule 2210). Set compliance.principal_review_enabled: true"
                )
            if comp.suitability_standard != SuitabilityStandard.reg_bi:
                raise ValueError(
                    "Tier 3 broker-dealers MUST use 'reg_bi' suitability standard "
                    "(SEC Regulation Best Interest)"
                )

        # ── Tier 5 Hedge Fund: pod isolation MNPI ────────────────
        if arch == Archetype.tier5_hedge_fund:
            if comp.mnpi_filtering != MnpiFilterLevel.tier5_pod_isolation:
                raise ValueError(
                    "Tier 5 hedge funds MUST use 'tier5_pod_isolation' MNPI filtering "
                    "to enforce information barriers between pods"
                )

        # ── Tier 1 Investment Bank: Chinese wall MNPI ────────────
        if arch == Archetype.tier1_investment_bank:
            if comp.mnpi_filtering != MnpiFilterLevel.tier1_chinese_wall:
                raise ValueError(
                    "Tier 1 investment banks MUST use 'tier1_chinese_wall' MNPI "
                    "filtering (MAR information barriers)"
                )

        # ── Tier 2 Asset Manager: portfolio-level MNPI ───────────
        if arch == Archetype.tier2_asset_manager:
            if comp.mnpi_filtering != MnpiFilterLevel.tier2_portfolio_level:
                raise ValueError(
                    "Tier 2 asset managers MUST use 'tier2_portfolio_level' MNPI "
                    "filtering (GIPS compliance)"
                )

        return self

    @model_validator(mode="after")
    def scan_for_leaked_credentials(self) -> "EnterpriseConfig":
        """
        Rule 9: Zero credentials in config.

        Deep-scan all string fields for patterns that look like raw
        API keys, tokens, passwords, or private keys. Vault/Secrets
        Manager references (${VAULT:...}) are allowed.
        """
        def _scan_obj(obj: object, path: str = "") -> None:
            if isinstance(obj, str):
                if _contains_credential(obj):
                    raise ValueError(
                        f"Credential detected at '{path}' — "
                        "secrets MUST use ${{VAULT:...}} or ${{SECRETS_MANAGER:...}} "
                        "references (Rule 9)"
                    )
            elif isinstance(obj, BaseModel):
                for field_name, field_value in obj:
                    _scan_obj(field_value, f"{path}.{field_name}" if path else field_name)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    _scan_obj(v, f"{path}.{k}")
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    _scan_obj(item, f"{path}[{i}]")

        _scan_obj(self)
        return self
