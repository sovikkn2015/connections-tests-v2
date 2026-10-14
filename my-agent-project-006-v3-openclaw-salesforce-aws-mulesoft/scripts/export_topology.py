#!/usr/bin/env python3
"""Export the dynamic topology graph to a frontend-friendly JSON artifact.

Source of truth is openclaw.orchestration.topology.AGENT_TOPOLOGY (which hard-
asserts 14 unique agent ids: 3 orchestrators + 11 specialists). The exported
graph adds infrastructure kinds — 1 coordinator root, 13 skills derived from
tool_allowlist, 5 MCP servers, 7 gate nodes (serial action spine), 3 trust
nodes — for a total of 43 nodes and 53 edges.

Output is deterministic: nodes + edges sorted, stable `generated_at` only if
the semantic content changed (we preserve the previous timestamp when the
graph shape is identical to make the script idempotent across runs).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from openclaw.orchestration.topology import (  # noqa: E402
    AGENT_TOPOLOGY,
    AgentRole,
    ModelTier,
)

OUTPUT_PATH = REPO_ROOT / "frontend" / "src" / "data" / "topology.json"

# Stable MCP server catalog — every MCP referenced by any agent's mcp_allowlist
# plus the two write-path servers that only action_specialist uses.
MCP_NODES: List[Dict[str, Any]] = [
    {"id": "salesforce-crm", "label": "Salesforce CRM MCP", "detail": "CRM household + audit"},
    {"id": "market-data", "label": "Market Data MCP", "detail": "Finnhub quotes & technicals"},
    {"id": "sec-edgar", "label": "SEC EDGAR MCP", "detail": "10-K / 10-Q / 8-K retrieval"},
    {"id": "news-search", "label": "News Search MCP", "detail": "Tavily 30-day headlines"},
    {"id": "mulesoft-actions", "label": "MuleSoft Actions MCP", "detail": "Write-path API gateway"},
]

# Trust-layer nodes — rendered as kind="trust" so the UI can pin them in a
# separate row. These are not in AGENT_TOPOLOGY because they're middleware,
# but they show up in the traversal map whenever they fire.
TRUST_NODES: List[Dict[str, Any]] = [
    {"id": "idp_session", "label": "IdP Session", "detail": "Auth / session token verify"},
    {"id": "mnpi_filter", "label": "MNPI Filter", "detail": "Server-side redaction"},
    {"id": "gate_enforcer", "label": "Seven-Gate Enforcer", "detail": "Action-path gate sequencer"},
]

# Skill name -> human label + persona bucket (for kind="skill" layer).
# Derived from agent.tool_allowlist across the registry.
SKILL_LABELS: Dict[str, str] = {
    "rag_retrieve": "rag_retrieve",
    "financial_statement_analysis": "financial_statement_analysis",
    "research_awareness": "research_awareness",
    "publish_brief": "publish_brief",
    "compliance_screening": "compliance_screening",
    "portfolio_analytics": "portfolio_analytics",
    "scenario_modeling": "scenario_modeling",
    "suitability_check": "suitability_check",
    "client_summary": "client_summary",
    "hitl": "hitl",
    "dual_auth": "dual_auth",
    "mulesoft_api": "mulesoft_api",
    "audit_logging": "audit_logging",
}

# Tools that are orchestration primitives, not skill nodes worth rendering.
# Dispatch / synthesize are edges in the graph (orchestrator->specialist), not
# leaves. rm_handoff is a CRM write, same idea.
_ORCHESTRATION_TOOLS = {
    "dispatch_specialist",
    "synthesize_brief",
    "synthesize_response",
    "rm_handoff",
}


def _persona_for_skill(skill: str) -> str:
    """Infer a persona bucket for a skill node.

    Walk every agent; the first persona whose tool_allowlist includes this
    skill wins. Skills shared across personas (rag_retrieve, research_awareness,
    compliance_screening) get "shared".
    """
    owners: set[str] = set()
    for agent in AGENT_TOPOLOGY.values():
        if skill in agent.tool_allowlist:
            owners.add(agent.persona)
    if len(owners) == 1:
        return next(iter(owners))
    return "shared"


def _model_literal(model: ModelTier) -> str:
    return "sonnet" if model is ModelTier.SONNET else "haiku"


def _build() -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()

    def add_edge(src: str, dst: str, kind: str) -> None:
        key = (src, dst, kind)
        if key in seen:
            return
        seen.add(key)
        edges.append({"from": src, "to": dst, "kind": kind})

    # 1. Coordinator root (layer 0).
    nodes.append(
        {
            "id": "coordinator",
            "kind": "coordinator",
            "label": "Coordinator",
            "persona": "shared",
            "model": None,
            "detail": "Persona router + audit anchor",
            "layer": 0,
        }
    )

    # 2. Orchestrators (layer 1) and specialists (layer 2).
    for agent in AGENT_TOPOLOGY.values():
        is_orch = agent.role is AgentRole.ORCHESTRATOR
        layer = 1 if is_orch else 2
        kind = "orchestrator" if is_orch else "specialist"
        nodes.append(
            {
                "id": agent.id,
                "kind": kind,
                "label": agent.id,
                "persona": agent.persona,
                "model": _model_literal(agent.model),
                "detail": agent.description,
                "layer": layer,
            }
        )
        if is_orch:
            add_edge("coordinator", agent.id, "routes")

    # 3. Orchestrator -> specialist edges (dispatches).
    for agent in AGENT_TOPOLOGY.values():
        if agent.role is AgentRole.ORCHESTRATOR:
            continue
        # find the orchestrator for this persona
        for cand in AGENT_TOPOLOGY.values():
            if cand.role is AgentRole.ORCHESTRATOR and cand.persona == agent.persona:
                add_edge(cand.id, agent.id, "dispatches")
                break

    # 4. Skill nodes (layer 3) — derived from each agent's tool_allowlist.
    declared_skills: set[str] = set()
    for agent in AGENT_TOPOLOGY.values():
        for tool in agent.tool_allowlist:
            if tool in _ORCHESTRATION_TOOLS:
                continue
            declared_skills.add(tool)

    for skill in sorted(declared_skills):
        nodes.append(
            {
                "id": f"skill:{skill}",
                "kind": "skill",
                "label": SKILL_LABELS.get(skill, skill),
                "persona": _persona_for_skill(skill),
                "model": None,
                "detail": "Skill",
                "layer": 3,
            }
        )

    # 5. Agent -> skill edges ("calls").
    for agent in AGENT_TOPOLOGY.values():
        for tool in agent.tool_allowlist:
            if tool in _ORCHESTRATION_TOOLS:
                continue
            add_edge(agent.id, f"skill:{tool}", "calls")

    # 6. MCP nodes (layer 4) — stable list; add any declared but missing for safety.
    declared_mcps: set[str] = set()
    for agent in AGENT_TOPOLOGY.values():
        declared_mcps.update(agent.mcp_allowlist)
    for extra in declared_mcps:
        if not any(n["id"] == extra for n in MCP_NODES):
            MCP_NODES.append({"id": extra, "label": extra, "detail": "MCP server"})

    for mcp in MCP_NODES:
        nodes.append(
            {
                "id": mcp["id"],
                "kind": "mcp",
                "label": mcp["label"],
                "persona": "shared",
                "model": None,
                "detail": mcp["detail"],
                "layer": 4,
            }
        )

    # 7. Agent -> MCP edges ("tools").
    for agent in AGENT_TOPOLOGY.values():
        for mcp_id in agent.mcp_allowlist:
            add_edge(agent.id, mcp_id, "tools")

    # 8. Trust-layer nodes (separate kind, own layer row — we place at layer 1
    # so the UI can hang them alongside the orchestrators conceptually).
    for trust in TRUST_NODES:
        nodes.append(
            {
                "id": trust["id"],
                "kind": "trust",
                "label": trust["label"],
                "persona": "shared",
                "model": None,
                "detail": trust["detail"],
                "layer": 1,
            }
        )

    # 9. Seven-gate serial spine — explicit nodes so the map renders the
    # gate-by-gate sequence. One node per gate in documented order, layer 5.
    # Edges model the SERIAL flow: action_specialist -> g1 -> g2 -> ... -> g7.
    # This is the demo-critical proof of `serial_by_design`.
    _GATE_SEQUENCE: List[Tuple[str, str, str]] = [
        ("gate:guardrails", "① Guardrails", "Input-side Bedrock Guardrails"),
        ("gate:mnpi_filter", "② MNPI Filter", "Block MNPI leak before compliance"),
        ("gate:compliance", "③ Compliance", "ALLOW/DENY/REVIEW — DENY is hard stop"),
        ("gate:hitl", "④ HITL", "HMAC-SHA256, 5m TTL, plan_hash bound, single-use"),
        ("gate:dual_auth", "⑤ Dual Auth", "> $100K wire / > $500K trade"),
        ("gate:mulesoft", "⑥ MuleSoft", "ONLY write path — Anypoint Exchange"),
        ("gate:audit", "⑦ Audit", "Fires on every outcome — even BLOCKED"),
    ]
    for gate_id, label, detail in _GATE_SEQUENCE:
        nodes.append(
            {
                "id": gate_id,
                "kind": "gate",
                "label": label,
                "persona": "fsi_advisor",
                "model": None,
                "detail": detail,
                "layer": 5,
            }
        )
    # action_specialist enters gate 1; each gate flows serially to the next.
    add_edge("action_specialist", _GATE_SEQUENCE[0][0], "sequences")
    for prev_gate, next_gate in zip(_GATE_SEQUENCE, _GATE_SEQUENCE[1:]):
        add_edge(prev_gate[0], next_gate[0], "sequences")

    nodes.sort(key=lambda n: (n["layer"], n["kind"], n["id"]))
    edges.sort(key=lambda e: (e["kind"], e["from"], e["to"]))

    return {"nodes": nodes, "edges": edges}


def _same_shape(prev: Dict[str, Any], new: Dict[str, Any]) -> bool:
    """Semantic equality ignoring `generated_at`."""
    return prev.get("nodes") == new.get("nodes") and prev.get("edges") == new.get("edges")


def main() -> int:
    graph = _build()

    previous: Dict[str, Any] | None = None
    if OUTPUT_PATH.exists():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None

    if previous and _same_shape(previous, graph):
        # Idempotent rerun — keep the prior timestamp so two runs are byte-equal.
        generated_at = previous.get("generated_at") or datetime.now(timezone.utc).isoformat()
    else:
        generated_at = datetime.now(timezone.utc).isoformat()

    payload: Dict[str, Any] = {
        "version": "1",
        "generated_at": generated_at,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(
        f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}: "
        f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
