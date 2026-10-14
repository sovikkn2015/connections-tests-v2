"""
M12: Agent Runtime Configuration — PLUG IN Module.

Runtime selection is a Helm values toggle, not a code change.
This schema defines the configuration structure that Helm values
populate. Application code is identical across topologies.

M12 calls: M6 (gateway), M8 (pipeline), M9 (intent router).
No cross-module Python imports — communication via REST/MCP only.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RuntimeType(str, Enum):
    """Agent runtime backend. Selected via Helm values toggle."""
    managed_agents = "managed-agents"   # Claude Managed Agents (cloud, Tier 3/4)
    strands_sdk = "strands-sdk"         # Strands SDK (hybrid/on-prem, Tier 1/2)


class ChannelConfig(BaseModel):
    """OpenClaw channel gateway configuration."""
    enabled_channels: list[str] = Field(
        default=["slack", "teams", "web"],
        description="Active channels (OpenClaw supports 12+)",
    )
    openclaw_endpoint: str = Field(
        default="",
        description="OpenClaw gateway URL (injected by Helm)",
    )


class SpecialistConfig(BaseModel):
    """Configuration for a specialist agent."""
    name: str
    enabled: bool = True
    model: str = Field(
        default="haiku",
        description="LLM model: haiku (routing/conversation) or sonnet (research)",
    )
    timeout_seconds: int = 300
    max_retries: int = 2


class RuntimeConfig(BaseModel):
    """
    M12 runtime configuration. Populated from Helm values.

    Cloud:   runtime_type=managed-agents
    Hybrid:  runtime_type=strands-sdk
    On-prem: runtime_type=strands-sdk (Phase 5, DEFERRED)
    """
    runtime_type: RuntimeType = RuntimeType.managed_agents
    channels: ChannelConfig = Field(default_factory=ChannelConfig)

    # Module endpoints (injected by Helm/service discovery)
    gateway_url: str = Field(
        default="",
        description="M6 MCP Gateway endpoint",
    )
    intent_router_url: str = Field(
        default="",
        description="M9 Intent Router endpoint",
    )
    pipeline_url: str = Field(
        default="",
        description="M8 Pipeline Engine endpoint",
    )

    # Specialist agent configs
    specialists: list[SpecialistConfig] = Field(
        default_factory=lambda: [
            SpecialistConfig(name="supervisor", model="haiku", timeout_seconds=30),
            SpecialistConfig(name="research", model="sonnet", timeout_seconds=1200),
            SpecialistConfig(name="client_service", model="haiku", timeout_seconds=180),
            SpecialistConfig(name="compliance", model="none", timeout_seconds=10),
            SpecialistConfig(name="execution", model="haiku", timeout_seconds=300),
            SpecialistConfig(name="onboarding", model="haiku", timeout_seconds=600),
        ],
    )

    # LLM provider (abstracted, swappable via config)
    llm_provider: str = Field(
        default="bedrock",
        description="LLM provider: bedrock, azure, gcp, self-hosted",
    )
