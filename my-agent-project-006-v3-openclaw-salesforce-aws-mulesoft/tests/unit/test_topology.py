"""Topology registry — 14 unique agents, 3 personas, invariants enforced."""

from __future__ import annotations

import pytest

from openclaw.orchestration.topology import (
    AGENT_TOPOLOGY,
    AgentRole,
    MemoryScope,
    ModelTier,
    PERSONAS,
    assert_topology_integrity,
    orchestrator_for_persona,
    topology_for_persona,
)


def test_registry_size() -> None:
    assert len(AGENT_TOPOLOGY) == 14


def test_personas_have_exactly_one_orchestrator() -> None:
    for persona in PERSONAS:
        subset = topology_for_persona(persona)
        orchs = [a for a in subset.values() if a.role is AgentRole.ORCHESTRATOR]
        assert len(orchs) == 1


def test_action_specialist_is_serial() -> None:
    a = AGENT_TOPOLOGY["action_specialist"]
    assert a.serial_by_design is True
    assert a.persona == "fsi_advisor"


def test_faq_specialist_on_haiku() -> None:
    assert AGENT_TOPOLOGY["faq_specialist"].model is ModelTier.HAIKU


def test_research_orchestrator_on_sonnet() -> None:
    a = AGENT_TOPOLOGY["research_orchestrator"]
    assert a.model is ModelTier.SONNET
    assert a.role is AgentRole.ORCHESTRATOR


def test_system_prompts_are_nontrivial() -> None:
    for aid, agent in AGENT_TOPOLOGY.items():
        assert len(agent.system_prompt) >= 200, f"{aid} has a stub prompt"


def test_agent_ids_are_snake_case() -> None:
    for aid in AGENT_TOPOLOGY.keys():
        assert aid == aid.lower()
        assert "-" not in aid and " " not in aid


def test_pydantic_frozen_contract() -> None:
    a = AGENT_TOPOLOGY["market_specialist"]
    with pytest.raises(Exception):
        a.id = "hacked"  # type: ignore[misc]


def test_action_specialist_allowlist_includes_seven_gates() -> None:
    a = AGENT_TOPOLOGY["action_specialist"]
    expected = {
        "compliance_screening",
        "hitl",
        "dual_auth",
        "mulesoft_api",
        "audit_logging",
    }
    assert expected.issubset(set(a.tool_allowlist))


def test_faq_specialist_has_no_mcp_or_tools() -> None:
    """Client-facing FAQ must not reach any MCP server — bounded answers only."""
    a = AGENT_TOPOLOGY["faq_specialist"]
    assert a.mcp_allowlist == []
    assert a.tool_allowlist == []


def test_liaison_context_specialist_is_read_only() -> None:
    a = AGENT_TOPOLOGY["context_specialist"]
    assert MemoryScope.READ_ONLY in a.memory_scope


def test_topology_integrity_check_runs() -> None:
    assert_topology_integrity()


def test_orchestrator_lookup() -> None:
    for persona in PERSONAS:
        orch = orchestrator_for_persona(persona)
        assert orch.role is AgentRole.ORCHESTRATOR
        assert orch.persona == persona


def test_unknown_persona_raises() -> None:
    with pytest.raises(ValueError, match="unknown persona"):
        topology_for_persona("fsi_trader")
