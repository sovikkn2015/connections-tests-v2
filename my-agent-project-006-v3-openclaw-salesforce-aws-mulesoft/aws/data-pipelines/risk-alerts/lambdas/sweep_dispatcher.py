"""Compliance sweep dispatcher — V3 Narrative 3 (Risk Alert).

SQS-triggered Lambda that receives shock events from the market monitor
and invokes the OpenClaw AgentCore coordinator with the `compliance_sweep`
skill. This is the bridge from async market telemetry to the agent
runtime.

Event shape (SQS record body, JSON):
    {
      "event_id": "uuid",
      "ticker": "NVDA",
      "current_price": 123.45,
      "previous_close": 120.00,
      "price_change_pct": 2.87,
      "threshold_pct": 3.0,
      "bucket": 8759432,
      "timestamp": "2025-01-15T14:32:00+00:00"
    }

Environment:
    AGENTCORE_URL               HTTPS endpoint of the AgentCore coordinator
    AGENTCORE_TOKEN_SECRET      Secrets Manager ARN holding the system bearer token
    SWEEP_EVENTS_TABLE          DynamoDB table for idempotent sweep tracking
    AWS_REGION                  AWS region

If AGENTCORE_URL is not configured we raise loudly — the SQS message
returns to the queue (visibility timeout), and after maxReceiveCount
retries the DLQ catches it. That way operators see the misconfig fast
instead of silently dropping shocks.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TTL_SECONDS = 24 * 3600
SWEEP_TIMEOUT_S = 60.0
SYSTEM_PRINCIPAL = "system-risk-monitor"

_ddb = boto3.resource("dynamodb")
_secrets = boto3.client("secretsmanager")

_TOKEN_CACHE: dict[str, tuple[float, str]] = {}


def _agentcore_token() -> str:
    arn = os.environ.get("AGENTCORE_TOKEN_SECRET")
    if not arn:
        raise RuntimeError("AGENTCORE_TOKEN_SECRET env var is required")
    now = time.time()
    cached = _TOKEN_CACHE.get(arn)
    if cached and cached[0] > now:
        return cached[1]
    resp = _secrets.get_secret_value(SecretId=arn)
    raw = resp.get("SecretString") or ""
    token: str
    try:
        parsed = json.loads(raw)
        token = str(parsed.get("token") or parsed.get("AGENTCORE_TOKEN") or raw).strip()
    except (ValueError, TypeError):
        token = raw.strip()
    if not token:
        raise RuntimeError("AgentCore token resolved to empty value")
    _TOKEN_CACHE[arn] = (now + 600, token)
    return token


def _mark_sweep(event_id: str, ticker: str, status: str, detail: str = "") -> None:
    tbl_name = os.environ.get("SWEEP_EVENTS_TABLE")
    if not tbl_name:
        return
    tbl = _ddb.Table(tbl_name)
    tbl.put_item(
        Item={
            "event_id": event_id,
            "ticker": ticker,
            "status": status,
            "detail": detail[:500],
            "dispatched_at": int(time.time()),
            "ttl": int(time.time()) + TTL_SECONDS,
        }
    )


def _already_handled(event_id: str) -> bool:
    tbl_name = os.environ.get("SWEEP_EVENTS_TABLE")
    if not tbl_name:
        return False
    tbl = _ddb.Table(tbl_name)
    resp = tbl.get_item(Key={"event_id": event_id})
    item = resp.get("Item")
    return bool(item and item.get("status") == "dispatched")


def _invoke_agentcore(shock: dict[str, Any]) -> dict[str, Any]:
    """POST the shock event to AgentCore with the compliance_sweep skill."""
    url = os.environ.get("AGENTCORE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "AGENTCORE_URL not configured — cannot dispatch compliance sweep"
        )
    token = _agentcore_token()
    payload = {
        "skill": "compliance_sweep",
        "principal_id": SYSTEM_PRINCIPAL,
        "persona": "system",
        "session_kind": "risk_alert",
        "inputs": {
            "event_id": shock["event_id"],
            "ticker": shock["ticker"],
            "price_change_pct": shock["price_change_pct"],
            "current_price": shock["current_price"],
            "previous_close": shock["previous_close"],
            "triggered_at": shock["timestamp"],
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Event-Id": shock["event_id"],
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=SWEEP_TIMEOUT_S)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"status": "ok", "raw": resp.text[:500]}


def lambda_handler(event: dict, _context) -> dict:
    """SQS-triggered handler; raises to trigger redrive on failure."""
    records = event.get("Records") or []
    results: list[dict] = []
    failures: list[dict] = []

    for record in records:
        try:
            body = json.loads(record.get("body") or "{}")
            event_id = str(body.get("event_id") or "").strip()
            ticker = str(body.get("ticker") or "").strip().upper()
            if not event_id or not ticker:
                raise ValueError("shock event missing event_id or ticker")

            if _already_handled(event_id):
                logger.info("sweep_already_handled event_id=%s ticker=%s", event_id, ticker)
                results.append({"event_id": event_id, "ticker": ticker, "status": "duplicate"})
                continue

            logger.info("sweep_dispatch_start event_id=%s ticker=%s", event_id, ticker)
            agent_resp = _invoke_agentcore(body)
            _mark_sweep(event_id, ticker, "dispatched", json.dumps(agent_resp)[:400])
            results.append({"event_id": event_id, "ticker": ticker, "status": "dispatched"})
            logger.info("sweep_dispatch_ok event_id=%s ticker=%s", event_id, ticker)
        except Exception as exc:  # noqa: BLE001
            logger.exception("sweep_dispatch_failed record=%s", record.get("messageId"))
            # Record the failure for observability, then re-raise so SQS retries.
            try:
                body = json.loads(record.get("body") or "{}")
                _mark_sweep(
                    str(body.get("event_id") or record.get("messageId", "unknown")),
                    str(body.get("ticker") or "UNKNOWN"),
                    "failed",
                    str(exc),
                )
            except Exception:  # noqa: BLE001
                pass
            failures.append({"messageId": record.get("messageId"), "error": str(exc)[:200]})

    if failures:
        # Raise so SQS sees the batch as failed → redrive → eventually DLQ.
        raise RuntimeError(f"sweep_dispatch_batch_failed count={len(failures)} detail={failures}")

    return {"processed": len(results), "results": results}
