"""Langfuse prompt store wrapper — roadmap item #4.

Why this module exists
----------------------
Today the specialist system prompts live as Python string constants in
`orchestration/topology.py`. Every edit forces a container rebuild + push
to ECR + AgentCore version bump, which slows prompt iteration to hours
per change. Langfuse ships a "prompt management" feature where prompts
are stored + versioned in Langfuse cloud and fetched at runtime by the
backend — edits become seconds, with full revision history, labels, and
A/B split support.

Contract — do not break
-----------------------
    get_prompt(name: str, default: str) -> str

* If `LANGFUSE_USE_PROMPT_STORE` != "1" in the environment, returns
  `default` immediately. This is the **off** path — keeps the existing
  hardcoded prompts in-flight without any runtime dependency on
  Langfuse. Default for everyone today.

* If the switch is on but the Langfuse SDK is not installed, returns
  `default`. Logs a warning once.

* If the switch is on but the prompt `name` is not in the store, returns
  `default`. Logs a warning once per name.

* If the switch is on and the prompt is in the store, returns the stored
  compiled prompt text (with Langfuse variable substitution applied,
  currently none are used — callers still pass {ticker} style tokens to
  their own f-strings afterwards).

Any exception from the Langfuse SDK falls back to `default`. Prompts are
cached per-name for `_CACHE_TTL_SEC` to bound Langfuse latency on every
turn. Call `invalidate_cache()` when testing or after a scheduled
rollout.

Intentional omissions
---------------------
* We do not import from `orchestration/topology.py` — that's builder
  territory and an import cycle would break any module load. The
  orchestrator imports THIS module, not the other way around.
* We do not mutate prompts. Scrubbing happens in `coordinator.py` on
  outbound spans, not on inbound templates.
* We do not wire prompt IDs onto Langfuse traces (call
  `langfuse_client.prompt=prompt_obj` in the caller when they wire up
  — this keeps the scaffold agnostic of tracer-library version).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_SWITCH_ENV = "LANGFUSE_USE_PROMPT_STORE"
_CACHE_TTL_SEC = 60  # 1 minute — keeps prompt latency predictable, still fast iteration

# name -> (fetched_at_epoch, prompt_text)
_CACHE: Dict[str, tuple[float, str]] = {}
# names we've already warned about (to avoid log spam)
_WARNED_MISSING: set[str] = set()
_WARNED_GLOBAL: Dict[str, bool] = {"sdk": False, "client": False}

# Module-level client slot — built lazily on first use, reused afterwards.
_CLIENT: Optional[Any] = None


def _store_enabled() -> bool:
    """Gate — did the operator opt into prompt-store mode?"""
    return (os.getenv(_SWITCH_ENV, "") or "").strip() == "1"


def _build_client_once() -> Optional[Any]:
    """Build the Langfuse client on first call. Returns None on any failure
    and caches the None so we don't re-try import / init every turn."""
    global _CLIENT  # noqa: PLW0603 - module-level memoization is intentional
    if _CLIENT is not None:
        return _CLIENT

    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")
    if not (pub and sec and host):
        # Operator flipped the switch but didn't set the creds — treat as
        # disabled. Warn once so the misconfiguration is visible.
        if not _WARNED_GLOBAL["client"]:
            logger.warning(
                "langfuse_prompts: LANGFUSE_USE_PROMPT_STORE=1 but "
                "LANGFUSE_{PUBLIC,SECRET}_KEY / LANGFUSE_HOST missing — "
                "falling back to defaults"
            )
            _WARNED_GLOBAL["client"] = True
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        if not _WARNED_GLOBAL["sdk"]:
            logger.warning(
                "langfuse_prompts: langfuse package not installed — "
                "falling back to defaults"
            )
            _WARNED_GLOBAL["sdk"] = True
        return None

    try:
        _CLIENT = Langfuse(public_key=pub, secret_key=sec, host=host)
    except Exception as exc:  # noqa: BLE001 - any init failure -> disable
        logger.warning("langfuse_prompts: Langfuse init failed (%s)", exc)
        _CLIENT = None
        return None

    return _CLIENT


def _fetch_prompt_text(client: Any, name: str) -> Optional[str]:
    """Pull the prompt text from the Langfuse client. Returns None if the
    name doesn't exist, the SDK errors, or the returned object doesn't
    expose a `.prompt` / `.compile()` method.

    Handles two SDK shapes:
      * langfuse >=2.0 `client.get_prompt(name)` returns an object with
        `.prompt` (string) and optional `.compile(**vars)`.
      * langfuse <2.0 exposed `client.prompt_get(...)` with the raw text
        in `['prompt']`. We don't see that version in the repo, but the
        fallback keeps us forward + backward compatible.
    """
    getter: Optional[Callable[[str], Any]] = None
    for attr in ("get_prompt", "prompt_get"):
        if hasattr(client, attr):
            getter = getattr(client, attr)
            break
    if getter is None:
        return None

    try:
        obj = getter(name)
    except Exception as exc:  # noqa: BLE001 - a missing name is an exception in some SDKs
        logger.debug("langfuse_prompts: get_prompt(%s) raised %s", name, exc)
        return None

    if obj is None:
        return None

    # Modern SDK — object with `.prompt`
    text = getattr(obj, "prompt", None)
    if isinstance(text, str) and text.strip():
        return text

    # Legacy SDK — dict-like with 'prompt' key
    if isinstance(obj, dict) and isinstance(obj.get("prompt"), str):
        return obj["prompt"]

    return None


def get_prompt(name: str, default: str) -> str:
    """Return the prompt text registered at `name` in Langfuse, or
    `default` if the prompt store is disabled / unreachable / has no
    entry for that name.

    Args:
        name: Dot-notation prompt identifier, e.g.
              "research.filings_specialist" or "advisor.action_specialist".
              Must match the label used in Langfuse.
        default: The hardcoded prompt to return when the store is off or
              the name is missing. This MUST be the current in-code
              prompt so behaviour is unchanged when the store is off.

    Returns:
        The prompt string. Never raises.
    """
    if not _store_enabled():
        return default

    # Cache hit?
    cached = _CACHE.get(name)
    now = time.time()
    if cached is not None:
        fetched_at, text = cached
        if now - fetched_at < _CACHE_TTL_SEC:
            return text

    client = _build_client_once()
    if client is None:
        return default

    fetched = _fetch_prompt_text(client, name)
    if fetched is None:
        if name not in _WARNED_MISSING:
            logger.info(
                "langfuse_prompts: no entry for %s — using default", name
            )
            _WARNED_MISSING.add(name)
        return default

    _CACHE[name] = (now, fetched)
    return fetched


def invalidate_cache(name: Optional[str] = None) -> None:
    """Clear the prompt cache. Useful in tests and after a deliberate
    rollout when the operator wants the next turn to refetch.

    Args:
        name: If given, only that entry is cleared. If None, the whole
              cache is flushed.
    """
    if name is None:
        _CACHE.clear()
        _WARNED_MISSING.clear()
        return
    _CACHE.pop(name, None)
    _WARNED_MISSING.discard(name)
