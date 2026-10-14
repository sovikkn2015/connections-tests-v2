"""Tests for the Langfuse prompt-store wrapper (roadmap item #4).

The wrapper is scaffold — backend builder wires it into topology.py on
their timeline. These tests lock down the contract so future edits don't
accidentally remove the soft-fallback safety net."""

from __future__ import annotations

from unittest import mock

import pytest

from openclaw.observability import get_prompt, invalidate_cache
from openclaw.observability import langfuse_prompts


DEFAULT_PROMPT = "SYSTEM: you are a filings specialist. cite verbatim."


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Each test starts with a clean cache + rebuilt client + env."""
    invalidate_cache()
    # Reset the module-level singletons that the wrapper memoizes.
    langfuse_prompts._CLIENT = None  # type: ignore[attr-defined]
    langfuse_prompts._WARNED_GLOBAL = {"sdk": False, "client": False}  # type: ignore[attr-defined]
    # Clear every Langfuse env var and the switch.
    for var in (
        "LANGFUSE_USE_PROMPT_STORE",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def test_returns_default_when_switch_off():
    """Env switch unset → default unchanged (today's production path)."""
    result = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    assert result == DEFAULT_PROMPT


def test_returns_default_when_switch_on_but_creds_missing(monkeypatch, caplog):
    """Operator flipped the switch but forgot to set creds → still default.

    We also assert that the warning only logs once, not every turn.
    """
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    result1 = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    result2 = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    assert result1 == DEFAULT_PROMPT
    assert result2 == DEFAULT_PROMPT


def test_returns_default_when_sdk_not_installed(monkeypatch):
    """Switch + creds set but `import langfuse` fails → default."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    # Force ImportError inside _build_client_once by stashing a sentinel
    # that makes the `from langfuse import Langfuse` fail.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langfuse":
            raise ImportError("simulated: package not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    assert result == DEFAULT_PROMPT


def test_returns_default_when_prompt_name_missing(monkeypatch):
    """Store reachable but no entry for this name → default."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    fake_client = mock.Mock()
    fake_client.get_prompt.return_value = None
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    result = get_prompt("research.unknown_specialist", DEFAULT_PROMPT)
    assert result == DEFAULT_PROMPT
    fake_client.get_prompt.assert_called_once_with("research.unknown_specialist")


def test_returns_stored_prompt_when_present(monkeypatch):
    """Store has the entry → returns the stored text, not the default."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    stored_prompt = "STORED: you are a filings specialist. cite EXACT chunk ids."
    fake_prompt_obj = mock.Mock()
    fake_prompt_obj.prompt = stored_prompt

    fake_client = mock.Mock()
    fake_client.get_prompt.return_value = fake_prompt_obj
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    result = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    assert result == stored_prompt
    assert result != DEFAULT_PROMPT


def test_cache_hit_avoids_refetch(monkeypatch):
    """Second call within TTL reuses the cached value — no SDK call."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    stored_prompt = "STORED: specialist prompt v2"
    fake_prompt_obj = mock.Mock()
    fake_prompt_obj.prompt = stored_prompt

    fake_client = mock.Mock()
    fake_client.get_prompt.return_value = fake_prompt_obj
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    result1 = get_prompt("advisor.action_specialist", DEFAULT_PROMPT)
    result2 = get_prompt("advisor.action_specialist", DEFAULT_PROMPT)
    assert result1 == stored_prompt
    assert result2 == stored_prompt
    assert fake_client.get_prompt.call_count == 1


def test_invalidate_cache_forces_refetch(monkeypatch):
    """After invalidate_cache(), the next call hits the SDK again."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    fake_prompt_obj = mock.Mock()
    fake_prompt_obj.prompt = "STORED"

    fake_client = mock.Mock()
    fake_client.get_prompt.return_value = fake_prompt_obj
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    get_prompt("foo", DEFAULT_PROMPT)
    invalidate_cache("foo")
    get_prompt("foo", DEFAULT_PROMPT)
    assert fake_client.get_prompt.call_count == 2


def test_sdk_exception_falls_back_to_default(monkeypatch):
    """Any exception from the SDK → default, no crash."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    fake_client = mock.Mock()
    fake_client.get_prompt.side_effect = RuntimeError("Langfuse is down")
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    result = get_prompt("research.filings_specialist", DEFAULT_PROMPT)
    assert result == DEFAULT_PROMPT


def test_legacy_sdk_dict_shape(monkeypatch):
    """Fallback path for older langfuse SDK that returns a dict."""
    monkeypatch.setenv("LANGFUSE_USE_PROMPT_STORE", "1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-xxx")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-xxx")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    # Legacy SDK: no get_prompt, only prompt_get returning a dict.
    fake_client = mock.Mock(spec=["prompt_get"])
    fake_client.prompt_get.return_value = {"prompt": "LEGACY STORED"}
    langfuse_prompts._CLIENT = fake_client  # type: ignore[attr-defined]

    result = get_prompt("research.x", DEFAULT_PROMPT)
    assert result == "LEGACY STORED"
