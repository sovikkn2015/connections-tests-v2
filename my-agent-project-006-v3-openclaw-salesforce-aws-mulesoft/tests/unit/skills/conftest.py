"""Shared fixtures for skills tests. Seeds HITL_SIGNING_KEY, registers
default mock MCP handlers, resets the shared mock client between tests."""

from __future__ import annotations

import pytest

from openclaw.skills._mcp_client import (
    MCPClient,
    get_shared_mock_client,
    reset_shared_mock_client,
)


@pytest.fixture(autouse=True)
def _seed_skills_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """HITL signing + MuleSoft mock + OFAC path defaults."""
    monkeypatch.setenv("HITL_SIGNING_KEY", "b" * 64)
    monkeypatch.setenv("MULESOFT_MODE", "mock")


@pytest.fixture
def mock_mcp() -> MCPClient:
    """Fresh mock MCP client per test.

    Handlers for common `salesforce-crm` tools are registered with benign
    defaults so every skill's audit_logging hop succeeds without explicit
    registration. Individual tests can override by re-registering.
    """
    reset_shared_mock_client()
    client = get_shared_mock_client()

    async def _audit_write(args):
        return {"Id": f"AUDIT_{len(client.mock_router.call_log):05d}"}

    async def _brief_write(args):
        return {"Id": "a0X_test_brief_001"}

    async def _pending_write(args):
        return {"Id": "a0Y_test_pending_001"}

    async def _pending_update(args):
        return {"ok": True}

    async def _read_household_summary(args):
        return {
            "household_name": "Patel Household",
            "primary_contact_id": "003_patel_001",
            "positions": [
                {"ticker": "NVDA", "pct_of_portfolio": 6.2, "asset_class": "equity"},
                {"ticker": "AMD",  "pct_of_portfolio": 3.1, "asset_class": "equity"},
                {"ticker": "CASH", "pct_of_portfolio": 20.0, "asset_class": "cash"},
            ],
            "recent_changes_pct": [{"ticker": "NVDA", "change_pct_30d": -2.1}],
            "next_events": [],
            "open_items": ["Schedule quarterly review"],
            "last_contact_at": "2026-03-01T10:00:00+00:00",
            "family_events": [],
        }

    async def _read_household_positions(args):
        return {
            "positions": [
                {"ticker": "NVDA", "pct_of_portfolio": 6.2, "sector": "semis",
                 "beta": 1.6, "ret_30d_pct": -2.1, "ret_ytd_pct": 12.3, "ret_1y_pct": 55.0},
                {"ticker": "MSFT", "pct_of_portfolio": 5.0, "sector": "software",
                 "beta": 1.1, "ret_30d_pct": 0.8, "ret_ytd_pct": 6.2, "ret_1y_pct": 22.0},
                {"ticker": "XOM",  "pct_of_portfolio": 4.0, "sector": "energy",
                 "beta": 0.9, "ret_30d_pct": 1.2, "ret_ytd_pct": 3.1, "ret_1y_pct": 8.0},
            ]
        }

    async def _read_briefs_with_exposure(args):
        return {
            "briefs": [
                {
                    "brief_id": "a0X_brief_NVDA_001",
                    "ticker": "NVDA",
                    "thesis": (
                        "NVDA pre-earnings thesis: strong fundamentals offset "
                        "by supply-chain risk."
                    ),
                    "sentiment_score": 0.15,
                    "compliance_status": "ALLOW",
                    "published_at": "2026-03-10T07:08:00+00:00",
                    "author_agent_id": "research_orchestrator",
                    "affected_clients": [
                        {
                            "contact_id": "003_patel_001",
                            "household_id": "H001",
                            "pct_exposure": 6.2,
                            "last_contact_at": "2026-03-01T10:00:00+00:00",
                        }
                    ],
                    "citations": ["chunk_nvda_001", "chunk_nvda_002"],
                }
            ]
        }

    client.mock_router.register("salesforce-crm", "write_audit_log", _audit_write)
    client.mock_router.register("salesforce-crm", "write_research_brief", _brief_write)
    client.mock_router.register(
        "salesforce-crm", "write_pending_approval", _pending_write
    )
    client.mock_router.register(
        "salesforce-crm", "update_pending_approval", _pending_update
    )
    client.mock_router.register(
        "salesforce-crm", "read_household_summary", _read_household_summary
    )
    client.mock_router.register(
        "salesforce-crm", "read_household_positions", _read_household_positions
    )
    client.mock_router.register(
        "salesforce-crm",
        "read_research_briefs_with_exposure",
        _read_briefs_with_exposure,
    )
    yield client
    reset_shared_mock_client()
