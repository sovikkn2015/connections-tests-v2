"""Shared fixtures for MCP server tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make aws/mcp-servers/ importable so `from _base import ...` resolves.
_ROOT = Path(__file__).resolve().parents[3]
_MCP_DIR = _ROOT / "aws" / "mcp-servers"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

# Make each server folder importable so their private helpers resolve.
for _child in ("sec-edgar", "salesforce-crm", "mulesoft-actions", "market-data", "news-search"):
    _d = _MCP_DIR / _child
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    monkeypatch.setenv("SEC_EDGAR_MODE", "mock")
    monkeypatch.setenv("NEWS_SEARCH_MODE", "mock")
    monkeypatch.setenv("SALESFORCE_CRM_MODE", "mock")
    monkeypatch.setenv("MULESOFT_MODE", "mock")
    monkeypatch.setenv("SF_AUTH_PROXY_MODE", "mock")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    # Tests intentionally run without an MCP_API_KEY set. The production code
    # is fail-closed (no key -> 401). Tests opt into dev-mode here so the
    # contract is explicit, not silent.
    monkeypatch.setenv("MCP_DEV_MODE", "true")
