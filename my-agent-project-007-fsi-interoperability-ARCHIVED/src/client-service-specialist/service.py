"""
Client Service Specialist — Engine for meeting prep, portfolio review, client summary.

All data access via M6 gateway REST calls (no direct vendor access).
All responses MNPI-filtered (M4 runs in M6 pipeline).
No cross-module imports. No credentials in code.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from .models import (
        ClientServiceRequest,
        ClientServiceResponse,
        MeetingPrepBrief,
        RequestType,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("clientsvc_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ClientServiceRequest = _mod.ClientServiceRequest
    ClientServiceResponse = _mod.ClientServiceResponse
    MeetingPrepBrief = _mod.MeetingPrepBrief
    RequestType = _mod.RequestType

logger = logging.getLogger("client_service_specialist.service")


class ClientServiceEngine:
    """
    Client service engine — routes requests by type.

    All data fetched via M6 gateway REST calls. In dev/test mode,
    uses an injected gateway_client (or returns stub data if None).
    Production: httpx.AsyncClient pointed at M6 gateway.
    """

    def __init__(self, gateway_client: Optional[Any] = None, m6_base_url: str = "http://m6-gateway:8006") -> None:
        self._client = gateway_client  # httpx.AsyncClient for M6 (injected)
        self._m6_base_url = m6_base_url

    async def _fetch_from_gateway(self, tool_name: str, arguments: dict) -> dict:
        """
        Fetch data via M6 gateway REST call.
        Production: POST to M6 /mcp/call. Dev/test: return stub data.
        """
        if self._client is not None:
            resp = await self._client.post(
                f"{self._m6_base_url}/mcp/call",
                json={"tool_name": tool_name, "arguments": arguments},
            )
            resp.raise_for_status()
            return resp.json().get("result", {})

        # Dev/test: stub data (MNPI-filtered — no SSN, DOB, raw PII)
        stubs = {
            "get_client": {
                "canonical_id": arguments.get("client_id", "cli-001"),
                "display_name": "Jane Henderson",
                "client_type": "individual",
                "risk_tolerance": "moderate",
                "advisor_ref": "adv-001",
            },
            "get_holdings": {
                "holdings": [
                    {"symbol": "AAPL", "quantity": 100, "market_value": 18550.00},
                    {"symbol": "MSFT", "quantity": 50, "market_value": 21250.00},
                    {"symbol": "VTI", "quantity": 200, "market_value": 46000.00},
                ],
                "total_value": 85800.00,
            },
            "get_plan_summary": {
                "plan_type": "retirement",
                "target_date": "2045",
                "on_track": True,
                "funding_ratio": 0.82,
            },
        }
        return stubs.get(tool_name, {})

    async def handle_request(self, request: ClientServiceRequest) -> ClientServiceResponse:
        """Route request by type and return MNPI-filtered response."""
        handlers = {
            RequestType.meeting_prep: self._handle_meeting_prep,
            RequestType.portfolio_review: self._handle_portfolio_review,
            RequestType.client_summary: self._handle_client_summary,
            RequestType.general: self._handle_general,
        }
        handler = handlers.get(request.request_type, self._handle_general)
        return await handler(request)

    async def _handle_meeting_prep(self, request: ClientServiceRequest) -> ClientServiceResponse:
        """Handle meeting prep request — assembles brief from M6 gateway calls."""
        brief = await self.prepare_meeting(request.client_id)
        content = (
            f"Meeting Prep for {brief.client_name}:\n"
            f"Portfolio Highlights: {'; '.join(brief.portfolio_highlights)}\n"
            f"Action Items: {'; '.join(brief.action_items)}\n"
            f"Compliance Flags: {'; '.join(brief.compliance_flags) or 'None'}"
        )
        return ClientServiceResponse(
            content=content,
            sources_used=["salesforce_fsc", "orion", "emoney"],
            mnpi_filtered=True,
            channel=request.channel,
            trace_id=request.trace_id,
        )

    async def _handle_portfolio_review(self, request: ClientServiceRequest) -> ClientServiceResponse:
        """Handle portfolio review request."""
        summary = await self.review_portfolio(request.client_id)
        return ClientServiceResponse(
            content=summary,
            sources_used=["orion", "schwab"],
            mnpi_filtered=True,
            channel=request.channel,
            trace_id=request.trace_id,
        )

    async def _handle_client_summary(self, request: ClientServiceRequest) -> ClientServiceResponse:
        """Handle client summary request."""
        summary = await self.summarize_client(request.client_id)
        return ClientServiceResponse(
            content=summary,
            sources_used=["salesforce_fsc"],
            mnpi_filtered=True,
            channel=request.channel,
            trace_id=request.trace_id,
        )

    async def _handle_general(self, request: ClientServiceRequest) -> ClientServiceResponse:
        """Handle general request."""
        return ClientServiceResponse(
            content=f"General inquiry for client {request.client_id}: {request.query or 'No query provided'}",
            sources_used=[],
            mnpi_filtered=True,
            channel=request.channel,
            trace_id=request.trace_id,
        )

    async def prepare_meeting(self, client_id: str) -> MeetingPrepBrief:
        """
        Assemble meeting prep brief from M6 gateway calls.
        Fetches: Client + Holdings + PlanSummary (all MNPI-filtered by M4 in M6 pipeline).
        """
        client_data = await self._fetch_from_gateway("get_client", {"client_id": client_id})
        holdings_data = await self._fetch_from_gateway("get_holdings", {"client_id": client_id})
        plan_data = await self._fetch_from_gateway("get_plan_summary", {"client_id": client_id})

        holdings = holdings_data.get("holdings", [])
        total_value = holdings_data.get("total_value", 0)

        highlights = []
        if total_value:
            highlights.append(f"Total portfolio value: ${total_value:,.2f}")
        for h in holdings[:3]:
            highlights.append(f"{h.get('symbol', '?')}: ${h.get('market_value', 0):,.2f}")

        action_items = []
        plan_type = plan_data.get("plan_type")
        if plan_type:
            funding = plan_data.get("funding_ratio", 0)
            if funding < 0.9:
                action_items.append(f"Review {plan_type} plan — funding at {funding:.0%}")
            else:
                action_items.append(f"{plan_type.title()} plan on track ({funding:.0%} funded)")

        risk = client_data.get("risk_tolerance", "unknown")
        action_items.append(f"Confirm risk tolerance: {risk}")

        compliance_flags: list[str] = []
        if risk == "aggressive":
            compliance_flags.append("Suitability review recommended for aggressive profile")

        return MeetingPrepBrief(
            client_name=client_data.get("display_name", f"Client {client_id}"),
            upcoming_meetings=[],
            portfolio_highlights=highlights,
            action_items=action_items,
            compliance_flags=compliance_flags,
        )

    async def review_portfolio(self, client_id: str) -> str:
        """
        Portfolio summary with performance, allocation, risk metrics.
        All data via M6 gateway (MNPI-filtered).
        """
        holdings_data = await self._fetch_from_gateway("get_holdings", {"client_id": client_id})
        client_data = await self._fetch_from_gateway("get_client", {"client_id": client_id})

        holdings = holdings_data.get("holdings", [])
        total = holdings_data.get("total_value", 0)
        risk = client_data.get("risk_tolerance", "unknown")

        lines = [f"Portfolio Review for {client_data.get('display_name', client_id)}:"]
        lines.append(f"Total Value: ${total:,.2f}")
        lines.append(f"Risk Tolerance: {risk}")
        lines.append(f"Positions: {len(holdings)}")

        if holdings:
            lines.append("Top Holdings:")
            for h in holdings[:5]:
                pct = (h.get("market_value", 0) / total * 100) if total else 0
                lines.append(f"  {h.get('symbol', '?')}: ${h.get('market_value', 0):,.2f} ({pct:.1f}%)")

        return "\n".join(lines)

    async def summarize_client(self, client_id: str) -> str:
        """
        Client profile summary. All data via M6 gateway (MNPI-filtered).
        No PII (SSN, DOB) — M4 strips before reaching this specialist.
        """
        client_data = await self._fetch_from_gateway("get_client", {"client_id": client_id})

        name = client_data.get("display_name", f"Client {client_id}")
        ctype = client_data.get("client_type", "unknown")
        risk = client_data.get("risk_tolerance", "unknown")

        return (
            f"Client Summary: {name}\n"
            f"Type: {ctype}\n"
            f"Risk Tolerance: {risk}\n"
            f"Advisor: {client_data.get('advisor_ref', 'unassigned')}"
        )
