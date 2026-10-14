"""Market price monitor — V3 Narrative 3 (Risk Alert).

Runs on a 5-minute EventBridge schedule during US market hours. For each
ticker in the SSM watchlist, polls Finnhub /quote and compares current
price to the prior close. Abs % move >= PRICE_SHOCK_THRESHOLD_PCT emits a
shock event to the compliance-sweep SQS queue (idempotency enforced via a
5-minute DynamoDB bucket so the same shock isn't dispatched twice).

    EventBridge (cron */5) -> MarketPriceMonitor -> SQS(ComplianceSweepQueue)
                                       |
                                       +--> DynamoDB(PriceShockEvents) (idempotency + TTL)

Environment:
    WATCHLIST_SSM_PARAM         /006-v3/watchlist/tickers (CSV)
    FINNHUB_API_KEY_SECRET      Secrets Manager ARN for Finnhub key
    PRICE_SHOCK_THRESHOLD_PCT   default 3.0
    SHOCK_EVENTS_TABLE          DynamoDB table name (from CDK output)
    COMPLIANCE_SWEEP_QUEUE_URL  SQS queue URL (from CDK output)
    AWS_REGION                  AWS region (auto-set by Lambda)

No credentials in source. Secrets resolved at invoke time; IAM via role.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FINNHUB_BASE = "https://finnhub.io/api/v1"
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = (9, 30)   # 09:30 ET
MARKET_CLOSE = (16, 0)  # 16:00 ET
BUCKET_SECONDS = 300    # 5-minute idempotency buckets
TTL_SECONDS = 24 * 3600

_ssm = boto3.client("ssm")
_secrets = boto3.client("secretsmanager")
_ddb = boto3.resource("dynamodb")
_sqs = boto3.client("sqs")

_FINNHUB_KEY_CACHE: dict[str, tuple[float, str]] = {}


@dataclass
class ShockEvent:
    event_id: str
    ticker: str
    current_price: float
    previous_close: float
    price_change_pct: float
    threshold_pct: float
    bucket: int
    timestamp: str


def _is_market_hours(now_et: datetime) -> bool:
    """Weekdays only, 09:30-16:00 ET inclusive of open, exclusive of close."""
    if now_et.weekday() >= 5:
        return False
    hm = (now_et.hour, now_et.minute)
    return MARKET_OPEN <= hm < MARKET_CLOSE


def _get_watchlist() -> list[str]:
    param = os.environ.get("WATCHLIST_SSM_PARAM", "/006-v3/watchlist/tickers")
    resp = _ssm.get_parameter(Name=param)
    raw = (resp.get("Parameter") or {}).get("Value", "")
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _finnhub_api_key() -> str:
    """Fetch Finnhub API key from Secrets Manager, with a 10-minute warm cache."""
    arn = os.environ.get("FINNHUB_API_KEY_SECRET")
    if not arn:
        raise RuntimeError("FINNHUB_API_KEY_SECRET env var is required")
    now = time.time()
    cached = _FINNHUB_KEY_CACHE.get(arn)
    if cached and cached[0] > now:
        return cached[1]
    resp = _secrets.get_secret_value(SecretId=arn)
    raw = resp.get("SecretString") or ""
    key: str
    try:
        parsed = json.loads(raw)
        key = str(parsed.get("FINNHUB_API_KEY") or parsed.get("api_key") or raw).strip()
    except (ValueError, TypeError):
        key = raw.strip()
    if not key:
        raise RuntimeError("Finnhub API key resolved to empty value")
    _FINNHUB_KEY_CACHE[arn] = (now + 600, key)
    return key


def _fetch_quote(ticker: str, api_key: str) -> dict[str, Any]:
    """Finnhub /quote returns {c, o, h, l, pc, d, dp, t}."""
    url = f"{FINNHUB_BASE}/quote"
    r = requests.get(url, params={"symbol": ticker, "token": api_key}, timeout=10)
    if r.status_code == 429:
        raise RuntimeError("finnhub_rate_limited")
    r.raise_for_status()
    return r.json()


def _pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous * 100.0


def _bucket_for(now_utc: datetime) -> int:
    return int(now_utc.timestamp() // BUCKET_SECONDS)


def _already_dispatched(table, event_key: str) -> bool:
    resp = table.get_item(Key={"event_key": event_key})
    return "Item" in resp


def _mark_dispatched(table, event_key: str, event: ShockEvent) -> None:
    table.put_item(
        Item={
            "event_key": event_key,
            "event_id": event.event_id,
            "ticker": event.ticker,
            "price_change_pct": str(round(event.price_change_pct, 4)),
            "created_at": event.timestamp,
            "ttl": int(time.time()) + TTL_SECONDS,
        }
    )


def _enqueue_sweep(queue_url: str, event: ShockEvent) -> str:
    resp = _sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(asdict(event)),
        MessageAttributes={
            "ticker": {"DataType": "String", "StringValue": event.ticker},
            "event_type": {"DataType": "String", "StringValue": "price_shock"},
        },
    )
    return resp.get("MessageId", "")


def lambda_handler(event: dict, _context) -> dict:
    """Scan watchlist tickers and dispatch compliance sweeps for shocks."""
    now_utc = datetime.now(tz=timezone.utc)
    now_et = now_utc.astimezone(MARKET_TZ)

    if not _is_market_hours(now_et):
        logger.info("outside_market_hours et=%s weekday=%s", now_et.isoformat(), now_et.weekday())
        return {
            "status": "skipped",
            "reason": "outside_market_hours",
            "now_et": now_et.isoformat(),
            "tickers_scanned": 0,
            "shocks_detected": 0,
            "events_enqueued": 0,
        }

    threshold = float(os.environ.get("PRICE_SHOCK_THRESHOLD_PCT", "3.0"))
    table_name = os.environ["SHOCK_EVENTS_TABLE"]
    queue_url = os.environ["COMPLIANCE_SWEEP_QUEUE_URL"]
    table = _ddb.Table(table_name)

    tickers = _get_watchlist()
    api_key = _finnhub_api_key()
    bucket = _bucket_for(now_utc)

    shocks: list[dict] = []
    enqueued: list[dict] = []
    skipped_dup: list[str] = []
    failed: list[dict] = []

    for ticker in tickers:
        try:
            quote = _fetch_quote(ticker, api_key)
            current = float(quote.get("c") or 0.0)
            prev_close = float(quote.get("pc") or 0.0)
            if current <= 0 or prev_close <= 0:
                failed.append({"ticker": ticker, "reason": "invalid_quote"})
                time.sleep(1.0)
                continue

            pct = _pct_change(current, prev_close)
            if abs(pct) < threshold:
                time.sleep(1.0)
                continue

            event_key = f"{ticker}-{bucket}"
            if _already_dispatched(table, event_key):
                skipped_dup.append(event_key)
                time.sleep(1.0)
                continue

            shock = ShockEvent(
                event_id=str(uuid.uuid4()),
                ticker=ticker,
                current_price=current,
                previous_close=prev_close,
                price_change_pct=pct,
                threshold_pct=threshold,
                bucket=bucket,
                timestamp=now_utc.isoformat(),
            )
            shocks.append(asdict(shock))
            msg_id = _enqueue_sweep(queue_url, shock)
            _mark_dispatched(table, event_key, shock)
            enqueued.append({"ticker": ticker, "message_id": msg_id, "event_key": event_key})
            logger.info(
                "shock_dispatched ticker=%s pct=%.3f event_key=%s", ticker, pct, event_key
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("monitor_failed ticker=%s error=%s", ticker, exc)
            failed.append({"ticker": ticker, "reason": str(exc)[:200]})
        finally:
            # Finnhub free tier: 60 calls/min. 1s pace keeps us under the cap.
            time.sleep(1.0)

    summary = {
        "status": "ok",
        "tickers_scanned": len(tickers),
        "shocks_detected": len(shocks),
        "events_enqueued": len(enqueued),
        "duplicates_skipped": len(skipped_dup),
        "failures": len(failed),
        "bucket": bucket,
        "now_et": now_et.isoformat(),
        "shocks": shocks[:10],
        "failed": failed[:10],
    }
    logger.info("monitor_done %s", json.dumps(summary, default=str))
    return summary
