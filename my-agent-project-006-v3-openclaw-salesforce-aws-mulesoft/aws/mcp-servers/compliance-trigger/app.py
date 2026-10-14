"""Scheduled compliance sweep trigger — EventBridge → Lambda → MCP gateway.

Runs every 15 minutes during market hours (Mon-Fri 9:30-16:00 ET).
Queries IR_Position__c for concentrated positions, then fires the
compliance_sweep skill via the MCP gateway for each affected ticker.

This replaces the manual `scripts/simulate-price-shock.sh` with a real
automated trigger for Narrative 3 (Risk Alert).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MCP_API_URL = os.environ.get("MCP_API_URL", "")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
THRESHOLD_PCT = float(os.environ.get("CONCENTRATION_THRESHOLD_PCT", "5.0"))
TICKERS = os.environ.get("WATCH_TICKERS", "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA").split(",")


def _mcp_call(server: str, tool: str, arguments: dict) -> dict:
    """POST to the MCP gateway."""
    url = f"{MCP_API_URL}/mcp/{server}/tools/call"
    body = json.dumps({"name": tool, "arguments": arguments}).encode()
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "X-MCP-API-Key": MCP_API_KEY,
            "X-Principal-Id": "compliance-trigger",
            "X-Agent-Id": "compliance_sweep_scheduler",
            "X-Persona": "system",
            "Content-Type": "application/json",
        },
        data=body,
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("mcp_call_failed server=%s tool=%s err=%s", server, tool, exc)
        return {"error": str(exc)}


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """EventBridge scheduled trigger entry point."""
    logger.info("compliance_sweep_trigger fired at %s", time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    if not MCP_API_URL or not MCP_API_KEY:
        logger.warning("MCP_API_URL or MCP_API_KEY not set — skipping")
        return {"status": "skipped", "reason": "missing config"}

    alerts_written = 0
    for ticker in TICKERS:
        ticker = ticker.strip()
        if not ticker:
            continue

        # Query positions via salesforce-crm MCP
        positions = _mcp_call("salesforce-crm", "query_positions", {
            "ticker": ticker,
            "min_concentration_pct": THRESHOLD_PCT,
        })

        records = positions.get("result", {}).get("records", [])
        if not records:
            continue

        logger.info("ticker=%s concentrated_positions=%d", ticker, len(records))

        # For each concentrated position, write a Client_Inquiry__c alert
        for rec in records:
            client_id = rec.get("Client_Contact__c", "")
            pct = rec.get("Position_Size_Pct__c", 0)
            if not client_id:
                continue

            result = _mcp_call("salesforce-crm", "write_client_inquiry", {
                "record": {
                    "Client_Contact_Id__c": client_id,
                    "Type__c": "alert",
                    "Inquiry_Text__c": f"Automated compliance sweep: {ticker} concentration at {pct}% exceeds {THRESHOLD_PCT}% threshold.",
                    "Channel__c": "System",
                    "Ticker_Mentions__c": ticker,
                    "Auto_Send_Eligible__c": False,
                }
            })

            if result.get("result", {}).get("success"):
                alerts_written += 1
                logger.info("alert_written ticker=%s client=%s", ticker, client_id)

    logger.info("compliance_sweep_complete alerts_written=%d", alerts_written)
    return {"status": "ok", "alerts_written": alerts_written}
