"""
SS&C Eze xAPI gRPC MCP Adapter — M11-gRPC (Phase 4).
Wraps SS&C Eze xAPI gRPC protocol behind the MCP HTTP interface.
Uses Python grpcio for gRPC communication with proto-defined services.

Auth: EZE_GRPC_HOST, EZE_GRPC_PORT, EZE_CLIENT_ID, EZE_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_orders, get_positions, get_executions, submit_order.
Hedge fund OMS/EMS integration.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8041
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_here = Path(__file__).resolve().parent
for _ancestor in [_here.parent, _here.parent.parent, *_here.parents]:
    if (_ancestor / "_shared").is_dir():
        sys.path.insert(0, str(_ancestor))
        break

from _shared.mcp_server import MCPAdapterServer, ToolDefinition
from _shared.rate_limiter import TokenBucket
from _shared.errors import canonical_error, tool_result

EZE_GRPC_HOST = os.environ.get("EZE_GRPC_HOST", "")
EZE_GRPC_PORT = int(os.environ.get("EZE_GRPC_PORT", "50051"))
EZE_CLIENT_ID = os.environ.get("EZE_CLIENT_ID", "")
EZE_CLIENT_SECRET = os.environ.get("EZE_CLIENT_SECRET", "")
_DEV_MODE = not EZE_GRPC_HOST

_rpm = int(os.environ.get("EZE_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("EZE_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_channel: Any = None


def _get_channel() -> Any:
    """Create gRPC channel. Import grpc lazily for dev mode."""
    global _channel
    if _channel is not None:
        return _channel
    import grpc  # type: ignore[import-untyped]
    _channel = grpc.insecure_channel(f"{EZE_GRPC_HOST}:{EZE_GRPC_PORT}")
    return _channel


# Dev-mode mock data
_MOCK_ORDERS = [
    {"order_id": "EZE-O001", "portfolio_id": "HF-001", "security_id": "AAPL", "side": "BUY", "quantity": 500, "order_type": "LIMIT", "limit_price": 215.00, "status": "FILLED", "filled_quantity": 500, "avg_price": 214.85, "created_at": "2025-01-15T09:31:00Z"},
    {"order_id": "EZE-O002", "portfolio_id": "HF-001", "security_id": "TSLA", "side": "SHORT", "quantity": 200, "order_type": "MARKET", "limit_price": None, "status": "OPEN", "filled_quantity": 0, "avg_price": 0, "created_at": "2025-01-15T10:15:00Z"},
]

_MOCK_POSITIONS = [
    {"portfolio_id": "HF-001", "security_id": "AAPL", "quantity": 1500, "market_value": 322500.00, "avg_cost": 200.00, "unrealized_pnl": 22500.00, "realized_pnl": 5000.00},
    {"portfolio_id": "HF-001", "security_id": "MSFT", "quantity": 800, "market_value": 340000.00, "avg_cost": 400.00, "unrealized_pnl": 20000.00, "realized_pnl": 12000.00},
    {"portfolio_id": "HF-001", "security_id": "TSLA", "quantity": -300, "market_value": -75000.00, "avg_cost": 260.00, "unrealized_pnl": 3000.00, "realized_pnl": 0},
]

_MOCK_EXECUTIONS = [
    {"execution_id": "EZE-X001", "order_id": "EZE-O001", "security_id": "AAPL", "side": "BUY", "quantity": 300, "price": 214.80, "venue": "NYSE", "timestamp": "2025-01-15T09:31:05Z"},
    {"execution_id": "EZE-X002", "order_id": "EZE-O001", "security_id": "AAPL", "side": "BUY", "quantity": 200, "price": 214.92, "venue": "ARCA", "timestamp": "2025-01-15T09:31:08Z"},
]


async def _handle_get_orders(args: dict[str, Any]) -> dict[str, Any]:
    portfolio_id = args.get("portfolio_id")
    if not portfolio_id:
        return canonical_error("'portfolio_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        orders = [o for o in _MOCK_ORDERS if o["portfolio_id"] == portfolio_id]
        status_filter = args.get("status_filter", "ALL")
        if status_filter != "ALL":
            orders = [o for o in orders if o["status"] == status_filter]
        return tool_result({"orders": orders, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Eze rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        import grpc  # type: ignore[import-untyped]
        channel = _get_channel()
        # In production: use generated stubs from eze_xapi.proto
        # stub = eze_xapi_pb2_grpc.OrderServiceStub(channel)
        # response = stub.GetOrders(eze_xapi_pb2.GetOrdersRequest(portfolio_id=portfolio_id, status_filter=status_filter))
        return canonical_error("gRPC stubs not generated — run protoc on eze_xapi.proto", error_code="GRPC_STUBS_MISSING", retryable=False)
    except Exception as exc:
        return canonical_error(f"gRPC error: {exc}", error_code="GRPC_ERROR", retryable=True)


async def _handle_get_positions(args: dict[str, Any]) -> dict[str, Any]:
    portfolio_id = args.get("portfolio_id")
    if not portfolio_id:
        return canonical_error("'portfolio_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        positions = [p for p in _MOCK_POSITIONS if p["portfolio_id"] == portfolio_id]
        return tool_result({"positions": positions, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Eze rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        channel = _get_channel()
        return canonical_error("gRPC stubs not generated — run protoc on eze_xapi.proto", error_code="GRPC_STUBS_MISSING", retryable=False)
    except Exception as exc:
        return canonical_error(f"gRPC error: {exc}", error_code="GRPC_ERROR", retryable=True)


async def _handle_get_executions(args: dict[str, Any]) -> dict[str, Any]:
    order_id = args.get("order_id")
    portfolio_id = args.get("portfolio_id")
    if not order_id and not portfolio_id:
        return canonical_error("'order_id' or 'portfolio_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        execs = _MOCK_EXECUTIONS
        if order_id:
            execs = [e for e in execs if e["order_id"] == order_id]
        return tool_result({"executions": execs, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Eze rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        channel = _get_channel()
        return canonical_error("gRPC stubs not generated — run protoc on eze_xapi.proto", error_code="GRPC_STUBS_MISSING", retryable=False)
    except Exception as exc:
        return canonical_error(f"gRPC error: {exc}", error_code="GRPC_ERROR", retryable=True)


async def _handle_submit_order(args: dict[str, Any]) -> dict[str, Any]:
    portfolio_id = args.get("portfolio_id")
    security_id = args.get("security_id")
    side = args.get("side")
    quantity = args.get("quantity")
    order_type = args.get("order_type")
    if not all([portfolio_id, security_id, side, quantity, order_type]):
        return canonical_error("'portfolio_id', 'security_id', 'side', 'quantity', and 'order_type' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"order_id": "EZE-O003", "portfolio_id": portfolio_id, "security_id": security_id, "side": side, "quantity": quantity, "order_type": order_type, "status": "OPEN", "created_at": "2025-01-15T10:30:00Z", "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Eze rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        channel = _get_channel()
        return canonical_error("gRPC stubs not generated — run protoc on eze_xapi.proto", error_code="GRPC_STUBS_MISSING", retryable=False)
    except Exception as exc:
        return canonical_error(f"gRPC error: {exc}", error_code="GRPC_ERROR", retryable=True)


_server = MCPAdapterServer(
    name="eze-grpc-adapter", version="1.0.0", vendor="eze",
    description="SS&C Eze xAPI gRPC adapter. Hedge fund OMS/EMS. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_orders", description="Get orders from Eze OMS via gRPC OrderService.",
    inputSchema={"type": "object", "properties": {
        "portfolio_id": {"type": "string", "description": "Eze portfolio identifier"},
        "status_filter": {"type": "string", "description": "Order status filter", "enum": ["ALL", "OPEN", "FILLED", "PARTIALLY_FILLED", "CANCELLED", "REJECTED"], "default": "ALL"},
    }, "required": ["portfolio_id"], "additionalProperties": False},
), _handle_get_orders)

_server.register_tool(ToolDefinition(
    name="get_positions", description="Get positions from Eze EMS via gRPC PositionService.",
    inputSchema={"type": "object", "properties": {
        "portfolio_id": {"type": "string", "description": "Eze portfolio identifier"},
    }, "required": ["portfolio_id"], "additionalProperties": False},
), _handle_get_positions)

_server.register_tool(ToolDefinition(
    name="get_executions", description="Get execution fills for an order or portfolio.",
    inputSchema={"type": "object", "properties": {
        "order_id": {"type": "string", "description": "Eze order identifier"},
        "portfolio_id": {"type": "string", "description": "Eze portfolio identifier"},
    }, "required": [], "additionalProperties": False},
), _handle_get_executions)

_server.register_tool(ToolDefinition(
    name="submit_order", description="Submit order to Eze OMS via gRPC OrderService. Requires pre-trade compliance.",
    inputSchema={"type": "object", "properties": {
        "portfolio_id": {"type": "string", "description": "Eze portfolio identifier"},
        "security_id": {"type": "string", "description": "Security identifier (ticker or CUSIP)"},
        "side": {"type": "string", "description": "Order side", "enum": ["BUY", "SELL", "SHORT", "COVER"]},
        "quantity": {"type": "number", "description": "Order quantity (shares)", "exclusiveMinimum": 0},
        "order_type": {"type": "string", "description": "Order type", "enum": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]},
        "limit_price": {"type": "number", "description": "Limit price (required for LIMIT/STOP_LIMIT)", "exclusiveMinimum": 0},
        "stop_price": {"type": "number", "description": "Stop price (required for STOP/STOP_LIMIT)", "exclusiveMinimum": 0},
    }, "required": ["portfolio_id", "security_id", "side", "quantity", "order_type"], "additionalProperties": False},
), _handle_submit_order)

app = _server.build_app()
