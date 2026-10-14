"""Multi-agent orchestration layer.

Topology definitions, message schemas, and the AgentCore-facing coordinator
that routes incoming user queries to the correct persona orchestrator.
"""

from .topology import (
    AGENT_TOPOLOGY,
    AgentDefinition,
    AgentRole,
    ModelTier,
    PERSONAS,
    topology_for_persona,
)
from .messages import (
    AgentError,
    OrchestratorDispatch,
    SessionContext,
    WorkerResponse,
)

__all__ = [
    "AGENT_TOPOLOGY",
    "AgentDefinition",
    "AgentError",
    "AgentRole",
    "ModelTier",
    "OrchestratorDispatch",
    "PERSONAS",
    "SessionContext",
    "WorkerResponse",
    "topology_for_persona",
]
