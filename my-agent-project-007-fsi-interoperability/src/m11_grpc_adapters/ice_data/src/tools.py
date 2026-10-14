"""MCP tool registry for ICE Data gRPC."""

from __future__ import annotations

from typing import Mapping

from m11_grpc_adapters.ice_data.src.client.ice_client import IceDataClient
from m11_grpc_adapters.ice_data.src.models import (
    IceReferenceDataInput,
    MarketDataSnapshotInput,
    TradeTapeInput,
)
from m11_python_adapters_shared import ToolDefinition


TOOL_NAMES = (
    "ice.market_data_snapshot",
    "ice.trade_tape",
    "ice.reference_data",
)


def build_tools(client: IceDataClient) -> Mapping[str, ToolDefinition]:
    """Build the frozen tool registry bound to the given client instance."""
    tools: dict[str, ToolDefinition] = {}

    async def _snapshot(args, firm_id):
        return await client.market_data_snapshot(args, firm_id)  # type: ignore[arg-type]

    async def _tape(args, firm_id):
        return await client.trade_tape(args, firm_id)  # type: ignore[arg-type]

    async def _ref(args, firm_id):
        return await client.reference_data(args, firm_id)  # type: ignore[arg-type]

    tools["ice.market_data_snapshot"] = ToolDefinition(
        name="ice.market_data_snapshot",
        description=(
            "Current NBBO snapshot for up to 100 securities identified by "
            "SYMBOL / ISIN / CUSIP / ICE_OPAQUE_ID. Optional Level-2 depth "
            "(requires entitlement)."
        ),
        input_model=MarketDataSnapshotInput,
        handler=_snapshot,
    )
    tools["ice.trade_tape"] = ToolDefinition(
        name="ice.trade_tape",
        description=(
            "Historical trade ticks for a single security within a ≤ 30-day "
            "window. Max 100,000 ticks per call."
        ),
        input_model=TradeTapeInput,
        handler=_tape,
    )
    tools["ice.reference_data"] = ToolDefinition(
        name="ice.reference_data",
        description=(
            "Security master for up to 500 securities — symbol, asset class, "
            "tick size, lot size, trading hours. Optional as_of_date for "
            "point-in-time lookup."
        ),
        input_model=IceReferenceDataInput,
        handler=_ref,
    )
    return tools
