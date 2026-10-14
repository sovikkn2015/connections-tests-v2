"""Skill name -> module mapping used by orchestrators.

The `tool_allowlist` entries in topology.py use the same snake_case names as
the module keys here. Orchestrators that need to invoke a skill do so via
`get_skill(name)` rather than importing modules directly — this keeps the
allowlist enforcement in one place and makes it trivial to swap a skill for
a mock in tests.

Lazy import: the registry does NOT import every skill module at registry
construction time. That would pull heavy deps into every import of the
topology. Instead the first `get_skill(name)` call resolves the module.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Dict, List


# name -> dotted module path under `openclaw.skills`
_SKILL_MODULES: Dict[str, str] = {
    "publish_brief": "openclaw.skills.publish_brief.actions",
    "rag_retrieve": "openclaw.skills.rag_retrieve.actions",
    "financial_statement_analysis": (
        "openclaw.skills.financial_statement_analysis.actions"
    ),
    "portfolio_analytics": "openclaw.skills.portfolio_analytics.actions",
    "scenario_modeling": "openclaw.skills.scenario_modeling.actions",
    "suitability_check": "openclaw.skills.suitability_check.actions",
    "client_summary": "openclaw.skills.client_summary.actions",
    "research_awareness": "openclaw.skills.research_awareness.actions",
    "compliance_screening": "openclaw.skills.compliance_screening.actions",
    "compliance_sweep": "openclaw.skills.compliance_sweep.actions",
    "hitl": "openclaw.skills.hitl.actions",
    "dual_auth": "openclaw.skills.dual_auth.actions",
    "mulesoft_api": "openclaw.skills.mulesoft_api.actions",
    "audit_logging": "openclaw.skills.audit_logging.actions",
    "mcp_invoke": "openclaw.skills.mcp_invoke.actions",
    "rm_handoff": "openclaw.skills.rm_handoff.actions",
}


def list_skills() -> List[str]:
    """Return the sorted list of registered skill names."""
    return sorted(_SKILL_MODULES.keys())


def get_skill(name: str) -> ModuleType:
    """Return the skill module by name. Raises KeyError if unknown."""
    try:
        dotted = _SKILL_MODULES[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown skill {name!r}; registered: {list_skills()!r}"
        ) from exc
    return importlib.import_module(dotted)


def assert_registry_integrity() -> None:
    """Verify every registered skill exposes an async `run`. Called by tests."""
    for name in _SKILL_MODULES:
        mod = get_skill(name)
        assert hasattr(mod, "run"), f"skill {name!r} must expose async `run()`"
