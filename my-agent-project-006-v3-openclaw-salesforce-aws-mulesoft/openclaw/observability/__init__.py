"""Observability module — Langfuse prompt store scaffold (roadmap item #4).

Exports a single public API used by orchestrator / specialist code that
wants to pull prompts from the Langfuse prompt store at runtime while
keeping the current hardcoded prompts as the authoritative default:

    from openclaw.observability import get_prompt
    system = get_prompt("research.filings_specialist", default=FILINGS_SPECIALIST_PROMPT)

Failure is always soft: if the Langfuse SDK is missing, env vars are
unset, or the prompt store has no entry for the requested name, the
caller receives the `default` unchanged. No turn ever fails because
the prompt store is unreachable.
"""

from .langfuse_prompts import get_prompt, invalidate_cache

__all__ = ["get_prompt", "invalidate_cache"]
