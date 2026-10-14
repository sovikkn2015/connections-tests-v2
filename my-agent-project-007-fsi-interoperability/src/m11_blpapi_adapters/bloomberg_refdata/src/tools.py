"""MCP tool registry for Bloomberg refdata.

Exports the four canonical tools as :class:`ToolDefinition` instances so the
shared FastAPI MCP server (in `m11_python_adapters_shared.mcp_server`) can
render ``/tools/list`` and dispatch ``/tools/call`` without knowing Bloomberg
specifics.
"""

from __future__ import annotations

from typing import Mapping

from m11_blpapi_adapters.bloomberg_refdata.src.client.refdata_client import (
    BloombergRefDataClient,
)
from m11_blpapi_adapters.bloomberg_refdata.src.models import (
    CorporateActionsInput,
    HistoricalDataInput,
    IntradayTickInput,
    ReferenceDataInput,
)
from m11_python_adapters_shared import ToolDefinition


TOOL_NAMES = (
    "bloomberg.reference_data",
    "bloomberg.historical_data",
    "bloomberg.intraday_tick",
    "bloomberg.corporate_actions",
)


def build_tools(client: BloombergRefDataClient) -> Mapping[str, ToolDefinition]:
    """Build the frozen tool registry bound to the given client instance."""
    tools: dict[str, ToolDefinition] = {}

    async def _reference_data(args, firm_id):
        return await client.reference_data(args, firm_id)  # type: ignore[arg-type]

    async def _historical_data(args, firm_id):
        return await client.historical_data(args, firm_id)  # type: ignore[arg-type]

    async def _intraday_tick(args, firm_id):
        return await client.intraday_tick(args, firm_id)  # type: ignore[arg-type]

    async def _corporate_actions(args, firm_id):
        return await client.corporate_actions(args, firm_id)  # type: ignore[arg-type]

    tools["bloomberg.reference_data"] = ToolDefinition(
        name="bloomberg.reference_data",
        description=(
            "Request static Bloomberg reference fields (price, market cap, sector, "
            "industry, description, etc.) for up to 200 securities identified by "
            "ISIN / CUSIP / TICKER. Returns raw vendor field map; M7 translator "
            "canonicalizes to M3 SecurityProfile + Quote."
        ),
        input_model=ReferenceDataInput,
        handler=_reference_data,
    )
    tools["bloomberg.historical_data"] = ToolDefinition(
        name="bloomberg.historical_data",
        description=(
            "Time-series request with daily/weekly/monthly/quarterly/yearly "
            "periodicity. Supports split / dividend / normal adjustment flags. "
            "Window capped at 10 years."
        ),
        input_model=HistoricalDataInput,
        handler=_historical_data,
    )
    tools["bloomberg.intraday_tick"] = ToolDefinition(
        name="bloomberg.intraday_tick",
        description=(
            "Tick-level data for a single security within a time window (≤ 140 "
            "days per Bloomberg archive). Supports TRADE / BID / ASK / BEST_BID "
            "/ BEST_ASK event types."
        ),
        input_model=IntradayTickInput,
        handler=_intraday_tick,
    )
    tools["bloomberg.corporate_actions"] = ToolDefinition(
        name="bloomberg.corporate_actions",
        description=(
            "Dividend, stock-dividend, split, and rights-issue history for up "
            "to 50 securities within a date range. Uses ReferenceDataRequest "
            "with DVD_HIST_ALL override."
        ),
        input_model=CorporateActionsInput,
        handler=_corporate_actions,
    )
    return tools
