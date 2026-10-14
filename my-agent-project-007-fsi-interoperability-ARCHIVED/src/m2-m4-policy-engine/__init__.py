"""
M2/M4 Unified Authority + MNPI Policy Engine.

Deterministic compliance engine using OPA/Rego ONLY.
No LLM. No probabilistic reasoning. Ever.

M2 (Authority): Evaluates (identity, action, target, context) -> ALLOW/DENY/ESCALATE
M4 (MNPI): Per-field data filtering by archetype, role, and jurisdiction

Two OPA policy bundles in one engine:
  - authority/ (M2 rules: action authorization, delegation, escalation)
  - mnpi/ (M4 rules: per-archetype field filtering, Chinese wall, pod isolation)

Fail-closed: If OPA is unreachable, ALL requests are DENIED.

Modules communicate via REST only — no cross-module imports.
"""

try:
    from .models import (
        AuthorityDecision,
        MnpiFilterInput,
        MnpiFilterOutput,
        PolicyInput,
        PolicyOutput,
    )
except ImportError:
    # Fallback for when running outside package context (e.g. pytest with hyphenated dirs)
    pass

__all__ = [
    "PolicyInput",
    "PolicyOutput",
    "MnpiFilterInput",
    "MnpiFilterOutput",
    "AuthorityDecision",
]
