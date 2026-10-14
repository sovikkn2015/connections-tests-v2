"""
Schwab SFTP MCP Adapter — M11-SFTP (Phase 2).
Parses daily batch files from Schwab SFTP server via paramiko.
M6 gateway calls M7 translator to convert to canonical types.

Auth: SCHWAB_SFTP_HOST, SCHWAB_SFTP_USER, SCHWAB_SFTP_KEY_PATH env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: list_files, download_positions, download_transactions, parse_daily_file.

CRITICAL: This adapter is the AUTHORITATIVE SOURCE for cost basis data (per ARCH-09).
cost_basis_method must NEVER be null in output.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8016
"""

from __future__ import annotations

import csv
import io
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

# ---------------------------------------------------------------------------
# Config from env (Rule 3)
# ---------------------------------------------------------------------------
SCHWAB_SFTP_HOST = os.environ.get("SCHWAB_SFTP_HOST", "")
SCHWAB_SFTP_PORT = int(os.environ.get("SCHWAB_SFTP_PORT", "22"))
SCHWAB_SFTP_USER = os.environ.get("SCHWAB_SFTP_USER", "")
SCHWAB_SFTP_KEY_PATH = os.environ.get("SCHWAB_SFTP_KEY_PATH", "")
SCHWAB_SFTP_REMOTE_DIR = os.environ.get("SCHWAB_SFTP_REMOTE_DIR", "/outgoing/daily")
_DEV_MODE = not SCHWAB_SFTP_HOST

_rpm = int(os.environ.get("SCHWAB_SFTP_RATE_LIMIT_RPM", "60"))
_burst = int(os.environ.get("SCHWAB_SFTP_RATE_LIMIT_BURST", "5"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)


def _get_sftp_client() -> Any:
    """Create paramiko SFTP client. Import lazily to avoid errors in dev mode."""
    import paramiko  # type: ignore[import-untyped]
    key = paramiko.RSAKey.from_private_key_file(SCHWAB_SFTP_KEY_PATH)
    transport = paramiko.Transport((SCHWAB_SFTP_HOST, SCHWAB_SFTP_PORT))
    transport.connect(username=SCHWAB_SFTP_USER, pkey=key)
    return paramiko.SFTPClient.from_transport(transport)


def _parse_position_csv(content: str) -> list[dict[str, Any]]:
    """Parse Schwab daily position CSV. cost_basis_method is NEVER null."""
    reader = csv.DictReader(io.StringIO(content))
    positions: list[dict[str, Any]] = []
    for row in reader:
        cbm = row.get("cost_basis_method", "").strip()
        if not cbm:
            cbm = "UNKNOWN"  # Never null — M7 translator flags for review
        positions.append({
            "account_id": row.get("account_id", ""),
            "symbol": row.get("symbol", ""),
            "cusip": row.get("cusip", ""),
            "quantity": float(row.get("quantity", 0)),
            "market_value": float(row.get("market_value", 0)),
            "cost_basis": float(row.get("cost_basis", 0)),
            "cost_basis_method": cbm,
            "security_type": row.get("security_type", ""),
        })
    return positions


def _parse_transaction_csv(content: str) -> list[dict[str, Any]]:
    """Parse Schwab daily transaction CSV."""
    reader = csv.DictReader(io.StringIO(content))
    return [
        {
            "account_id": row.get("account_id", ""),
            "transaction_id": row.get("transaction_id", ""),
            "trade_date": row.get("trade_date", ""),
            "settle_date": row.get("settle_date", ""),
            "type": row.get("type", ""),
            "symbol": row.get("symbol", ""),
            "quantity": float(row.get("quantity", 0)),
            "price": float(row.get("price", 0)),
            "net_amount": float(row.get("net_amount", 0)),
        }
        for row in reader
    ]


# ---------------------------------------------------------------------------
# Dev-mode mock data — CRITICAL: cost_basis_method NEVER null
# ---------------------------------------------------------------------------
_MOCK_FILES = [
    {"filename": "SCHW_POS_20250115.csv", "size": 312000, "modified": "2025-01-15T06:00:00Z", "type": "positions"},
    {"filename": "SCHW_TXN_20250115.csv", "size": 156000, "modified": "2025-01-15T06:00:00Z", "type": "transactions"},
    {"filename": "SCHW_POS_20250114.csv", "size": 308000, "modified": "2025-01-14T06:00:00Z", "type": "positions"},
]

_MOCK_POSITIONS = [
    {"account_id": "SCHW-001", "symbol": "AAPL", "cusip": "037833100", "quantity": 200, "market_value": 43000.00, "cost_basis": 30000.00, "cost_basis_method": "FIFO", "security_type": "equity"},
    {"account_id": "SCHW-001", "symbol": "VTI", "cusip": "922908769", "quantity": 300, "market_value": 81000.00, "cost_basis": 72000.00, "cost_basis_method": "AVG_COST", "security_type": "etf"},
    {"account_id": "SCHW-002", "symbol": "BND", "cusip": "921937835", "quantity": 400, "market_value": 30800.00, "cost_basis": 32000.00, "cost_basis_method": "SPEC_ID", "security_type": "etf"},
    {"account_id": "SCHW-002", "symbol": "SCHD", "cusip": "808524805", "quantity": 250, "market_value": 20750.00, "cost_basis": 18000.00, "cost_basis_method": "FIFO", "security_type": "etf"},
]

_MOCK_TRANSACTIONS = [
    {"account_id": "SCHW-001", "transaction_id": "STXN-001", "trade_date": "2025-01-15", "settle_date": "2025-01-17", "type": "buy", "symbol": "AAPL", "quantity": 50, "price": 215.00, "net_amount": -10750.00},
    {"account_id": "SCHW-001", "transaction_id": "STXN-002", "trade_date": "2025-01-15", "settle_date": "2025-01-17", "type": "dividend", "symbol": "VTI", "quantity": 0, "price": 0, "net_amount": 187.50},
    {"account_id": "SCHW-002", "transaction_id": "STXN-003", "trade_date": "2025-01-15", "settle_date": "2025-01-17", "type": "dividend", "symbol": "BND", "quantity": 0, "price": 0, "net_amount": 67.50},
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_list_files(args: dict[str, Any]) -> dict[str, Any]:
    date = args.get("date")
    if _DEV_MODE:
        files = _MOCK_FILES
        if date:
            files = [f for f in files if date in f["filename"]]
        return tool_result({"files": files, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("SFTP rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        sftp = _get_sftp_client()
        try:
            entries = sftp.listdir_attr(SCHWAB_SFTP_REMOTE_DIR)
            files = []
            for entry in entries:
                if date and date not in entry.filename:
                    continue
                files.append({"filename": entry.filename, "size": entry.st_size, "modified": str(entry.st_mtime)})
            return tool_result({"files": files})
        finally:
            sftp.close()
    except Exception as exc:
        return canonical_error(f"SFTP error: {exc}", error_code="SFTP_ERROR", retryable=True)


async def _handle_download_positions(args: dict[str, Any]) -> dict[str, Any]:
    date = args.get("date")
    if not date:
        return canonical_error("'date' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"date": date, "positions": _MOCK_POSITIONS, "record_count": len(_MOCK_POSITIONS), "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("SFTP rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        sftp = _get_sftp_client()
        try:
            filename = f"SCHW_POS_{date}.csv"
            with sftp.open(f"{SCHWAB_SFTP_REMOTE_DIR}/{filename}", "r") as f:
                content = f.read().decode("utf-8")
            positions = _parse_position_csv(content)
            return tool_result({"date": date, "positions": positions, "record_count": len(positions)})
        finally:
            sftp.close()
    except FileNotFoundError:
        return canonical_error(f"Position file not found for date {date}.", error_code="FILE_NOT_FOUND", retryable=False)
    except Exception as exc:
        return canonical_error(f"SFTP error: {exc}", error_code="SFTP_ERROR", retryable=True)


async def _handle_download_transactions(args: dict[str, Any]) -> dict[str, Any]:
    date = args.get("date")
    if not date:
        return canonical_error("'date' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"date": date, "transactions": _MOCK_TRANSACTIONS, "record_count": len(_MOCK_TRANSACTIONS), "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("SFTP rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", retryable=True)
    try:
        sftp = _get_sftp_client()
        try:
            filename = f"SCHW_TXN_{date}.csv"
            with sftp.open(f"{SCHWAB_SFTP_REMOTE_DIR}/{filename}", "r") as f:
                content = f.read().decode("utf-8")
            transactions = _parse_transaction_csv(content)
            return tool_result({"date": date, "transactions": transactions, "record_count": len(transactions)})
        finally:
            sftp.close()
    except FileNotFoundError:
        return canonical_error(f"Transaction file not found for date {date}.", error_code="FILE_NOT_FOUND", retryable=False)
    except Exception as exc:
        return canonical_error(f"SFTP error: {exc}", error_code="SFTP_ERROR", retryable=True)


async def _handle_parse_daily_file(args: dict[str, Any]) -> dict[str, Any]:
    date = args.get("date")
    file_type = args.get("file_type", "positions")
    if not date:
        return canonical_error("'date' is required.", error_code="INVALID_PARAMS")
    if file_type == "positions":
        return await _handle_download_positions({"date": date})
    elif file_type == "transactions":
        return await _handle_download_transactions({"date": date})
    return canonical_error(f"Unknown file_type: {file_type}", error_code="INVALID_PARAMS")


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="schwab-sftp-adapter",
    version="1.0.0",
    vendor="schwab_sftp",
    description="Schwab SFTP daily file adapter. Authoritative cost basis source. paramiko SFTP. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="list_files", description="List available daily files on Schwab SFTP server.",
    inputSchema={"type": "object", "properties": {
        "date": {"type": "string", "description": "Filter by date in YYYYMMDD format", "pattern": "^\\d{8}$"},
    }, "required": [], "additionalProperties": False},
), _handle_list_files)

_server.register_tool(ToolDefinition(
    name="download_positions",
    description="Download and parse daily position file. CRITICAL: cost_basis_method is NEVER null.",
    inputSchema={"type": "object", "properties": {
        "date": {"type": "string", "description": "File date in YYYYMMDD format", "pattern": "^\\d{8}$"},
    }, "required": ["date"], "additionalProperties": False},
), _handle_download_positions)

_server.register_tool(ToolDefinition(
    name="download_transactions", description="Download and parse daily transaction file.",
    inputSchema={"type": "object", "properties": {
        "date": {"type": "string", "description": "File date in YYYYMMDD format", "pattern": "^\\d{8}$"},
    }, "required": ["date"], "additionalProperties": False},
), _handle_download_transactions)

_server.register_tool(ToolDefinition(
    name="parse_daily_file", description="Parse a Schwab daily file by type (positions or transactions).",
    inputSchema={"type": "object", "properties": {
        "date": {"type": "string", "description": "File date in YYYYMMDD format", "pattern": "^\\d{8}$"},
        "file_type": {"type": "string", "description": "File type to parse", "enum": ["positions", "transactions"], "default": "positions"},
    }, "required": ["date"], "additionalProperties": False},
), _handle_parse_daily_file)

app = _server.build_app()
