"""
M13 FIX Bridge — MCP tool definitions with real handlers.

Exposes FIX operations as MCP tools using _shared/MCPAdapterServer.
M6 gateway calls M13 via MCP (same interface as M11 adapters).

Dev mode: when FIX_BROKER_HOST is not set, returns mock execution data.
Production mode: routes through FIXSessionManager → QuickFIX engine.

No cross-module imports. No credentials in code.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent dir so _shared is importable (works both locally and in Docker)
_here = Path(__file__).resolve().parent
for _ancestor in [_here.parent, _here.parent.parent, *_here.parents]:
    if (_ancestor / "_shared").is_dir():
        sys.path.insert(0, str(_ancestor))
        break

from _shared.mcp_server import MCPAdapterServer, ToolDefinition
from _shared.errors import canonical_error, tool_result

try:
    from .session_manager import FIXSessionManager
    from .models import (
        NewOrderSingle,
        OrderCancelRequest,
        ExecutionReport,
        FIXBridgeConfig,
        FIXSessionState,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib

    _base = _pathlib.Path(__file__).parent

    _sm_spec = importlib.util.spec_from_file_location(
        "fix_sm_local", _base / "session_manager.py"
    )
    _sm_mod = importlib.util.module_from_spec(_sm_spec)
    _sm_spec.loader.exec_module(_sm_mod)
    FIXSessionManager = _sm_mod.FIXSessionManager

    _m_spec = importlib.util.spec_from_file_location(
        "fix_models_local2", _base / "models.py"
    )
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    NewOrderSingle = _m_mod.NewOrderSingle
    OrderCancelRequest = _m_mod.OrderCancelRequest
    ExecutionReport = _m_mod.ExecutionReport
    FIXBridgeConfig = _m_mod.FIXBridgeConfig
    FIXSessionState = _m_mod.FIXSessionState


# ---------------------------------------------------------------------------
# Dev mode flag — same pattern as M11 adapters
# ---------------------------------------------------------------------------
_DEV_MODE = not os.environ.get("FIX_BROKER_HOST", "")

# Module-level session manager (shared across all tool calls)
_session_mgr = FIXSessionManager()


# ---------------------------------------------------------------------------
# Mock data generators for dev mode
# ---------------------------------------------------------------------------

def _mock_execution_report(
    cl_ord_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
) -> ExecutionReport:
    """Generate a mock fill ExecutionReport for dev mode."""
    return ExecutionReport(
        exec_id=f"DEV-EXEC-{uuid.uuid4().hex[:8].upper()}",
        cl_ord_id=cl_ord_id,
        order_id=f"DEV-ORD-{uuid.uuid4().hex[:8].upper()}",
        exec_type="2",  # Fill
        ord_status="2",  # Filled
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price or 100.0,
        leaves_qty=0,
        cum_qty=quantity,
        avg_px=price or 100.0,
    )


def _mock_cancel_ack(
    orig_cl_ord_id: str,
    cl_ord_id: str,
    symbol: str,
    side: str,
) -> ExecutionReport:
    """Generate a mock cancel ack ExecutionReport for dev mode."""
    return ExecutionReport(
        exec_id=f"DEV-EXEC-{uuid.uuid4().hex[:8].upper()}",
        cl_ord_id=cl_ord_id,
        order_id=f"DEV-ORD-{uuid.uuid4().hex[:8].upper()}",
        exec_type="4",  # Canceled
        ord_status="4",  # Canceled
        symbol=symbol,
        side=side,
        quantity=1,  # Minimum valid (model requires gt=0)
        price=0,
        leaves_qty=0,
        cum_qty=0,
        avg_px=0,
    )


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_fix_submit_order(args: dict[str, Any]) -> dict[str, Any]:
    """Submit a FIX NewOrderSingle (MsgType=D).

    Validates args, creates order via session_manager, returns cl_ord_id + seq num.
    In dev mode (no broker configured), also returns a mock execution report.
    """
    session_id = args.get("session_id")
    if not session_id:
        return canonical_error("'session_id' is required.", error_code="INVALID_PARAMS")

    symbol = args.get("symbol")
    side = args.get("side")
    order_type = args.get("order_type")
    quantity = args.get("quantity")
    account = args.get("account")

    if not all([symbol, side, order_type, quantity, account]):
        return canonical_error(
            "'symbol', 'side', 'order_type', 'quantity', and 'account' are required.",
            error_code="INVALID_PARAMS",
        )

    # Validate side and order_type
    if side not in ("1", "2"):
        return canonical_error("'side' must be '1' (Buy) or '2' (Sell).", error_code="INVALID_PARAMS")
    if order_type not in ("1", "2"):
        return canonical_error("'order_type' must be '1' (Market) or '2' (Limit).", error_code="INVALID_PARAMS")

    price = args.get("price")
    if order_type == "2" and not price:
        return canonical_error("'price' is required for limit orders.", error_code="INVALID_PARAMS")

    try:
        order = NewOrderSingle(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            account=account,
            time_in_force=args.get("time_in_force", "0"),
        )
    except Exception as exc:
        return canonical_error(f"Invalid order parameters: {exc}", error_code="INVALID_PARAMS")

    try:
        cl_ord_id = _session_mgr.send_new_order(session_id, order)
    except ValueError as exc:
        return canonical_error(str(exc), error_code="SESSION_ERROR")

    session = _session_mgr.get_session(session_id)
    result: dict[str, Any] = {
        "cl_ord_id": cl_ord_id,
        "seq_num_out": session.seq_num_out,
        "session_state": session.state.value,
    }

    if _DEV_MODE:
        mock_report = _mock_execution_report(
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price or 100.0,
        )
        # Store the mock report so get_execution_reports can find it
        _session_mgr.receive_execution_report(session_id, mock_report)
        result["execution_report"] = mock_report.model_dump()
        result["_dev_mode"] = True

    return tool_result(result)


async def _handle_fix_cancel_order(args: dict[str, Any]) -> dict[str, Any]:
    """Send a FIX OrderCancelRequest (MsgType=F).

    Validates args, creates cancel via session_manager.
    In dev mode, returns a mock cancel ack.
    """
    session_id = args.get("session_id")
    if not session_id:
        return canonical_error("'session_id' is required.", error_code="INVALID_PARAMS")

    orig_cl_ord_id = args.get("orig_cl_ord_id")
    symbol = args.get("symbol")
    side = args.get("side")

    if not all([orig_cl_ord_id, symbol, side]):
        return canonical_error(
            "'orig_cl_ord_id', 'symbol', and 'side' are required.",
            error_code="INVALID_PARAMS",
        )

    if side not in ("1", "2"):
        return canonical_error("'side' must be '1' (Buy) or '2' (Sell).", error_code="INVALID_PARAMS")

    try:
        cancel = OrderCancelRequest(
            orig_cl_ord_id=orig_cl_ord_id,
            symbol=symbol,
            side=side,
        )
    except Exception as exc:
        return canonical_error(f"Invalid cancel parameters: {exc}", error_code="INVALID_PARAMS")

    try:
        cl_ord_id = _session_mgr.send_cancel(session_id, cancel)
    except ValueError as exc:
        return canonical_error(str(exc), error_code="SESSION_ERROR")

    session = _session_mgr.get_session(session_id)
    result: dict[str, Any] = {
        "cl_ord_id": cl_ord_id,
        "orig_cl_ord_id": orig_cl_ord_id,
        "seq_num_out": session.seq_num_out,
        "session_state": session.state.value,
    }

    if _DEV_MODE:
        mock_ack = _mock_cancel_ack(
            orig_cl_ord_id=orig_cl_ord_id,
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
        )
        _session_mgr.receive_execution_report(session_id, mock_ack)
        result["cancel_ack"] = mock_ack.model_dump()
        result["_dev_mode"] = True

    return tool_result(result)


async def _handle_fix_get_session_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get FIX session state, sequence numbers, and connection info."""
    session_id = args.get("session_id")
    if not session_id:
        return canonical_error("'session_id' is required.", error_code="INVALID_PARAMS")

    session = _session_mgr.get_session(session_id)
    if session is None:
        return canonical_error(
            f"Session not found: {session_id}",
            error_code="SESSION_NOT_FOUND",
            vendor_status_code=404,
        )

    result = {
        "session_id": session.session_id,
        "state": session.state.value,
        "sender_comp_id": session.sender_comp_id,
        "target_comp_id": session.target_comp_id,
        "seq_num_out": session.seq_num_out,
        "seq_num_in": session.seq_num_in,
        "connected_at": session.connected_at.isoformat() if session.connected_at else None,
        "last_heartbeat_at": (
            session.last_heartbeat_at.isoformat() if session.last_heartbeat_at else None
        ),
        "broker_name": session.broker_name,
    }

    if _DEV_MODE:
        result["_dev_mode"] = True

    return tool_result(result)


async def _handle_fix_get_execution_reports(args: dict[str, Any]) -> dict[str, Any]:
    """Get execution reports for a specific client order ID."""
    session_id = args.get("session_id")
    cl_ord_id = args.get("cl_ord_id")

    if not session_id:
        return canonical_error("'session_id' is required.", error_code="INVALID_PARAMS")
    if not cl_ord_id:
        return canonical_error("'cl_ord_id' is required.", error_code="INVALID_PARAMS")

    try:
        reports = _session_mgr.get_execution_reports(session_id, cl_ord_id)
    except ValueError as exc:
        return canonical_error(str(exc), error_code="SESSION_ERROR")

    result: dict[str, Any] = {
        "cl_ord_id": cl_ord_id,
        "reports": [r.model_dump() for r in reports],
        "count": len(reports),
    }

    if _DEV_MODE:
        result["_dev_mode"] = True

    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly via _shared factory
# ---------------------------------------------------------------------------
def create_mcp_server() -> MCPAdapterServer:
    """Build the MCP adapter server with FIX bridge tools."""

    server = MCPAdapterServer(
        name="fix-bridge",
        version="1.0.0",
        vendor="fix-4.2",
        description=(
            "M13 FIX 4.2 Bridge — Stateful TCP sessions with sequence number tracking. "
            "Separate module from M11 per ARCH-09."
        ),
    )

    server.register_tool(
        ToolDefinition(
            name="fix_submit_order",
            description=(
                "Submit a FIX NewOrderSingle (MsgType=D). "
                "Requires active FIX session. HITL enforced by M6 gateway."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "FIX session ID"},
                    "symbol": {"type": "string", "description": "Instrument symbol (Tag 55)"},
                    "side": {
                        "type": "string",
                        "enum": ["1", "2"],
                        "description": "1=Buy, 2=Sell",
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["1", "2"],
                        "description": "1=Market, 2=Limit",
                    },
                    "quantity": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Order quantity",
                    },
                    "price": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Limit price (required for limit orders)",
                    },
                    "account": {"type": "string", "description": "Account identifier"},
                    "time_in_force": {
                        "type": "string",
                        "default": "0",
                        "description": "0=Day, 1=GTC, 3=IOC",
                    },
                },
                "required": [
                    "session_id",
                    "symbol",
                    "side",
                    "order_type",
                    "quantity",
                    "account",
                ],
                "additionalProperties": False,
            },
        ),
        _handle_fix_submit_order,
    )

    server.register_tool(
        ToolDefinition(
            name="fix_cancel_order",
            description="Send a FIX OrderCancelRequest (MsgType=F) to cancel an existing order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "FIX session ID"},
                    "orig_cl_ord_id": {
                        "type": "string",
                        "description": "Original client order ID to cancel",
                    },
                    "symbol": {"type": "string", "description": "Instrument symbol"},
                    "side": {
                        "type": "string",
                        "enum": ["1", "2"],
                        "description": "1=Buy, 2=Sell",
                    },
                },
                "required": ["session_id", "orig_cl_ord_id", "symbol", "side"],
                "additionalProperties": False,
            },
        ),
        _handle_fix_cancel_order,
    )

    server.register_tool(
        ToolDefinition(
            name="fix_get_session_status",
            description="Get FIX session state, sequence numbers, and connection info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "FIX session ID"},
                },
                "required": ["session_id"],
                "additionalProperties": False,
            },
        ),
        _handle_fix_get_session_status,
    )

    server.register_tool(
        ToolDefinition(
            name="fix_get_execution_reports",
            description="Get execution reports for a specific client order ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "FIX session ID"},
                    "cl_ord_id": {
                        "type": "string",
                        "description": "Client order ID to query",
                    },
                },
                "required": ["session_id", "cl_ord_id"],
                "additionalProperties": False,
            },
        ),
        _handle_fix_get_execution_reports,
    )

    return server
