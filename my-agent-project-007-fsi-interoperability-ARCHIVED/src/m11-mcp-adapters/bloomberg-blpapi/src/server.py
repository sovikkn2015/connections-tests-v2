"""
Bloomberg BLPAPI MCP Adapter — M11-BLPAPI (Phase 4).
Wraps Bloomberg's binary B-PIPE protocol behind the MCP HTTP interface.
Uses Python blpapi SDK for session-based binary protocol — NOT REST.

Auth: BLOOMBERG_SERVER_HOST, BLOOMBERG_SERVER_PORT env vars (B-PIPE connection).
Dev mode: returns realistic mock data when B-PIPE host is not configured.
Tools: get_reference_data, get_historical_data, subscribe_realtime, get_intraday_bars.

CRITICAL: Bloomberg BLPAPI is a binary protocol with 10K+ fields and a subscription model.
The adapter translates BLPAPI responses to MCP JSON format.
M7 translator converts Bloomberg field names to M3 canonical types.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8040
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

BLOOMBERG_SERVER_HOST = os.environ.get("BLOOMBERG_SERVER_HOST", "")
BLOOMBERG_SERVER_PORT = int(os.environ.get("BLOOMBERG_SERVER_PORT", "8194"))
_DEV_MODE = not BLOOMBERG_SERVER_HOST

_rpm = int(os.environ.get("BLOOMBERG_RATE_LIMIT_RPM", "600"))
_burst = int(os.environ.get("BLOOMBERG_RATE_LIMIT_BURST", "20"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_session: Any = None


def _get_session() -> Any:
    """Create Bloomberg blpapi session. Import lazily for dev mode."""
    global _session
    if _session is not None:
        return _session
    import blpapi  # type: ignore[import-untyped]
    options = blpapi.SessionOptions()
    options.setServerHost(BLOOMBERG_SERVER_HOST)
    options.setServerPort(BLOOMBERG_SERVER_PORT)
    session = blpapi.Session(options)
    if not session.start():
        raise ConnectionError("Failed to start Bloomberg session")
    if not session.openService("//blp/refdata"):
        raise ConnectionError("Failed to open //blp/refdata service")
    _session = session
    return _session


def _blpapi_reference_request(securities: list[str], fields: list[str]) -> list[dict[str, Any]]:
    """Execute a Bloomberg ReferenceDataRequest."""
    import blpapi  # type: ignore[import-untyped]
    session = _get_session()
    service = session.getService("//blp/refdata")
    request = service.createRequest("ReferenceDataRequest")
    for sec in securities:
        request.getElement("securities").appendValue(sec)
    for fld in fields:
        request.getElement("fields").appendValue(fld)
    session.sendRequest(request)
    results: list[dict[str, Any]] = []
    while True:
        event = session.nextEvent(500)
        for msg in event:
            if msg.hasElement("securityData"):
                sec_data = msg.getElement("securityData")
                for i in range(sec_data.numValues()):
                    sec = sec_data.getValueAsElement(i)
                    row: dict[str, Any] = {"security": sec.getElementAsString("security")}
                    field_data = sec.getElement("fieldData")
                    for fld in fields:
                        if field_data.hasElement(fld):
                            row[fld] = str(field_data.getElement(fld))
                    results.append(row)
        if event.eventType() == blpapi.Event.RESPONSE:
            break
    return results


def _blpapi_historical_request(security: str, fields: list[str], start: str, end: str, periodicity: str) -> list[dict[str, Any]]:
    """Execute a Bloomberg HistoricalDataRequest."""
    import blpapi  # type: ignore[import-untyped]
    session = _get_session()
    service = session.getService("//blp/refdata")
    request = service.createRequest("HistoricalDataRequest")
    request.getElement("securities").appendValue(security)
    for fld in fields:
        request.getElement("fields").appendValue(fld)
    request.set("startDate", start)
    request.set("endDate", end)
    request.set("periodicitySelection", periodicity)
    session.sendRequest(request)
    results: list[dict[str, Any]] = []
    while True:
        event = session.nextEvent(500)
        for msg in event:
            if msg.hasElement("securityData"):
                fd = msg.getElement("securityData").getElement("fieldData")
                for i in range(fd.numValues()):
                    bar = fd.getValueAsElement(i)
                    row: dict[str, Any] = {"date": str(bar.getElement("date"))}
                    for fld in fields:
                        if bar.hasElement(fld):
                            row[fld] = str(bar.getElement(fld))
                    results.append(row)
        if event.eventType() == blpapi.Event.RESPONSE:
            break
    return results


# Dev-mode mock data
_MOCK_REF_DATA = [
    {"security": "AAPL US Equity", "PX_LAST": 215.00, "PE_RATIO": 28.5, "CUR_MKT_CAP": 3300000000000.0, "GICS_SECTOR_NAME": "Information Technology"},
    {"security": "MSFT US Equity", "PX_LAST": 425.00, "PE_RATIO": 35.2, "CUR_MKT_CAP": 3150000000000.0, "GICS_SECTOR_NAME": "Information Technology"},
]

_MOCK_HIST_DATA = [
    {"date": "2025-01-13", "PX_LAST": 212.50, "PX_VOLUME": 45000000},
    {"date": "2025-01-14", "PX_LAST": 214.00, "PX_VOLUME": 52000000},
    {"date": "2025-01-15", "PX_LAST": 215.00, "PX_VOLUME": 48000000},
]

_MOCK_REALTIME = [
    {"security": "AAPL US Equity", "LAST_PRICE": 215.25, "BID": 215.20, "ASK": 215.30, "VOLUME": 12500000},
]

_MOCK_INTRADAY = [
    {"time": "2025-01-15T09:30:00", "open": 214.50, "high": 215.10, "low": 214.30, "close": 215.00, "volume": 2500000},
    {"time": "2025-01-15T09:35:00", "open": 215.00, "high": 215.50, "low": 214.90, "close": 215.25, "volume": 1800000},
]


async def _handle_get_reference_data(args: dict[str, Any]) -> dict[str, Any]:
    securities = args.get("securities")
    fields = args.get("fields")
    if not securities or not fields:
        return canonical_error("'securities' and 'fields' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        mock = [d for d in _MOCK_REF_DATA if d["security"] in securities]
        if not mock:
            mock = [{"security": s, **{f: "N/A" for f in fields}} for s in securities]
        return tool_result({"reference_data": mock, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Bloomberg rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    try:
        data = _blpapi_reference_request(securities, fields)
        return tool_result({"reference_data": data})
    except Exception as exc:
        return canonical_error(f"BLPAPI error: {exc}", error_code="BLPAPI_ERROR", retryable=True)


async def _handle_get_historical_data(args: dict[str, Any]) -> dict[str, Any]:
    security = args.get("security")
    fields = args.get("fields")
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    if not all([security, fields, start_date, end_date]):
        return canonical_error("'security', 'fields', 'start_date', and 'end_date' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"security": security, "historical_data": _MOCK_HIST_DATA, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Bloomberg rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    try:
        data = _blpapi_historical_request(security, fields, start_date, end_date, args.get("periodicity", "DAILY"))
        return tool_result({"security": security, "historical_data": data})
    except Exception as exc:
        return canonical_error(f"BLPAPI error: {exc}", error_code="BLPAPI_ERROR", retryable=True)


async def _handle_subscribe_realtime(args: dict[str, Any]) -> dict[str, Any]:
    securities = args.get("securities")
    fields = args.get("fields")
    if not securities or not fields:
        return canonical_error("'securities' and 'fields' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        mock = [d for d in _MOCK_REALTIME if d["security"] in securities]
        if not mock:
            mock = [{"security": s, **{f: 0.0 for f in fields}} for s in securities]
        return tool_result({"snapshots": mock, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Bloomberg rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    try:
        data = _blpapi_reference_request(securities, fields)
        return tool_result({"snapshots": data})
    except Exception as exc:
        return canonical_error(f"BLPAPI error: {exc}", error_code="BLPAPI_ERROR", retryable=True)


async def _handle_get_intraday_bars(args: dict[str, Any]) -> dict[str, Any]:
    security = args.get("security")
    interval = args.get("interval")
    start_dt = args.get("start_datetime")
    end_dt = args.get("end_datetime")
    if not all([security, interval, start_dt, end_dt]):
        return canonical_error("'security', 'interval', 'start_datetime', and 'end_datetime' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"security": security, "interval": interval, "bars": _MOCK_INTRADAY, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("Bloomberg rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    try:
        import blpapi  # type: ignore[import-untyped]
        session = _get_session()
        service = session.getService("//blp/refdata")
        request = service.createRequest("IntradayBarRequest")
        request.set("security", security)
        request.set("eventType", "TRADE")
        request.set("interval", interval)
        request.set("startDateTime", start_dt)
        request.set("endDateTime", end_dt)
        session.sendRequest(request)
        bars: list[dict[str, Any]] = []
        while True:
            event = session.nextEvent(500)
            for msg in event:
                if msg.hasElement("barData"):
                    bar_data = msg.getElement("barData").getElement("barTickData")
                    for i in range(bar_data.numValues()):
                        bar = bar_data.getValueAsElement(i)
                        bars.append({
                            "time": str(bar.getElement("time")),
                            "open": float(str(bar.getElement("open"))),
                            "high": float(str(bar.getElement("high"))),
                            "low": float(str(bar.getElement("low"))),
                            "close": float(str(bar.getElement("close"))),
                            "volume": int(str(bar.getElement("volume"))),
                        })
            if event.eventType() == blpapi.Event.RESPONSE:
                break
        return tool_result({"security": security, "interval": interval, "bars": bars})
    except Exception as exc:
        return canonical_error(f"BLPAPI error: {exc}", error_code="BLPAPI_ERROR", retryable=True)


_server = MCPAdapterServer(
    name="bloomberg-blpapi-adapter", version="1.0.0", vendor="bloomberg",
    description="Bloomberg BLPAPI adapter. Binary B-PIPE protocol. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_reference_data",
    description="Bloomberg reference data request (//blp/refdata). Returns security fundamentals.",
    inputSchema={"type": "object", "properties": {
        "securities": {"type": "array", "items": {"type": "string"}, "description": "Bloomberg security identifiers", "minItems": 1, "maxItems": 100},
        "fields": {"type": "array", "items": {"type": "string"}, "description": "Bloomberg field mnemonics", "minItems": 1, "maxItems": 50},
    }, "required": ["securities", "fields"], "additionalProperties": False},
), _handle_get_reference_data)

_server.register_tool(ToolDefinition(
    name="get_historical_data",
    description="Bloomberg historical data request. Returns price history for a single security.",
    inputSchema={"type": "object", "properties": {
        "security": {"type": "string", "description": "Bloomberg security identifier"},
        "start_date": {"type": "string", "description": "Start date YYYYMMDD", "pattern": "^\\d{8}$"},
        "end_date": {"type": "string", "description": "End date YYYYMMDD", "pattern": "^\\d{8}$"},
        "fields": {"type": "array", "items": {"type": "string"}, "description": "Bloomberg field mnemonics", "minItems": 1, "maxItems": 25},
        "periodicity": {"type": "string", "description": "Data periodicity", "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "SEMI_ANNUALLY", "YEARLY"], "default": "DAILY"},
    }, "required": ["security", "start_date", "end_date", "fields"], "additionalProperties": False},
), _handle_get_historical_data)

_server.register_tool(ToolDefinition(
    name="subscribe_realtime",
    description="Bloomberg real-time snapshot (//blp/mktdata). Returns point-in-time values in MCP context.",
    inputSchema={"type": "object", "properties": {
        "securities": {"type": "array", "items": {"type": "string"}, "description": "Bloomberg security identifiers", "minItems": 1, "maxItems": 50},
        "fields": {"type": "array", "items": {"type": "string"}, "description": "Bloomberg real-time field mnemonics", "minItems": 1, "maxItems": 25},
    }, "required": ["securities", "fields"], "additionalProperties": False},
), _handle_subscribe_realtime)

_server.register_tool(ToolDefinition(
    name="get_intraday_bars",
    description="Bloomberg intraday bar request. Returns OHLCV bars at specified intervals.",
    inputSchema={"type": "object", "properties": {
        "security": {"type": "string", "description": "Bloomberg security identifier"},
        "interval": {"type": "integer", "description": "Bar interval in minutes", "enum": [1, 5, 15, 30, 60]},
        "start_datetime": {"type": "string", "description": "Start datetime ISO 8601"},
        "end_datetime": {"type": "string", "description": "End datetime ISO 8601"},
    }, "required": ["security", "interval", "start_datetime", "end_datetime"], "additionalProperties": False},
), _handle_get_intraday_bars)

app = _server.build_app()
