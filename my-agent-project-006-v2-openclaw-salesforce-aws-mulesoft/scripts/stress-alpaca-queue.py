#!/usr/bin/env python3
"""
stress-alpaca-queue.py — 30-order parallel stress test against CloudHub.

Submits 30 BUY-1 MARKET orders over ~30s across 7 tickers from parallel workers,
then verifies each canonical response has a unique ALPACA-* order_id.
Does NOT hit Alpaca directly — trusts CloudHub -> Alpaca coupling already
verified in Layer 7/8 of the round-3 test sweep.

Usage:
    CLOUDHUB_APP_URL="https://openclaw-v2-trade-process-api-q73tdv.5sc6y6-2.usa-e2.cloudhub.io" \
    MULESOFT_CLIENT_ID="<from-API-Manager>" \
    python3 scripts/stress-alpaca-queue.py

Exit codes:
    0 = 30/30 success, no duplicates
    1 = some orders failed (see report)
    2 = duplicates detected
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import random
import ssl
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib import request as urlreq
from urllib import error as urlerr


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context with a reliable CA bundle.

    Python 3.10 on macOS (from python.org) ships with no default CA file, so
    urllib HTTPS calls fail SSL verification. Try certifi first, then
    /etc/ssl/cert.pem, then the python defaults as a last resort.
    """
    cafile: Optional[str] = None
    try:
        import certifi  # type: ignore
        cafile = certifi.where()
    except ImportError:
        if os.path.exists("/etc/ssl/cert.pem"):
            cafile = "/etc/ssl/cert.pem"
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


SSL_CTX = _build_ssl_context()


TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOG", "AMZN", "META"]
TOTAL_ORDERS = 30
SPREAD_SECONDS = 30.0  # jitter window across which orders fire
REQUEST_TIMEOUT = 30.0


@dataclass
class OrderResult:
    idx: int
    ticker: str
    client_order_id: str
    http_status: int = 0
    order_id: str = ""
    mulesoft_reference: str = ""
    error: str = ""
    elapsed_ms: int = 0


def _mint_hash() -> str:
    """Fake approval_token_hash — never a real token. Just satisfies shape check."""
    raw = f"stress-{uuid.uuid4()}-{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def submit_one(idx: int, base_url: str, client_id_header: Optional[str], ticker: str) -> OrderResult:
    client_order_id = f"stress-{idx:02d}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    body = {
        "client_order_id": client_order_id,
        "ticker": ticker,
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "client_id": f"CLI-STRESS-{idx:02d}",
        "account_id": f"ACC-STRESS-{idx:02d}",
        "approval_token_hash": _mint_hash(),
    }
    payload = json.dumps(body).encode()
    url = f"{base_url.rstrip('/')}/api/orders"
    headers = {"Content-Type": "application/json"}
    if client_id_header:
        headers["client_id"] = client_id_header
    req = urlreq.Request(url, data=payload, headers=headers, method="POST")

    result = OrderResult(idx=idx, ticker=ticker, client_order_id=client_order_id)
    started = time.perf_counter()
    try:
        with urlreq.urlopen(req, timeout=REQUEST_TIMEOUT, context=SSL_CTX) as resp:
            body_bytes = resp.read()
            result.http_status = resp.getcode()
            try:
                parsed = json.loads(body_bytes.decode() or "{}")
                result.order_id = parsed.get("order_id", "")
                result.mulesoft_reference = parsed.get("mulesoft_reference", "")
            except json.JSONDecodeError:
                result.error = f"non-JSON body (first 120 chars): {body_bytes[:120]!r}"
    except urlerr.HTTPError as exc:
        result.http_status = exc.code
        try:
            body_bytes = exc.read()
            result.error = body_bytes.decode(errors="replace")[:240]
        except Exception:  # pragma: no cover - defensive
            result.error = str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return result


def main() -> int:
    base_url = os.environ.get("CLOUDHUB_APP_URL")
    client_id_header = os.environ.get("MULESOFT_CLIENT_ID")  # optional
    if not base_url:
        sys.stderr.write("ERROR: CLOUDHUB_APP_URL must be set.\n")
        return 64

    rng = random.Random(42)
    tickers_rotation = [rng.choice(TICKERS) for _ in range(TOTAL_ORDERS)]
    # Schedule: each worker sleeps a pre-computed jitter so orders span SPREAD_SECONDS
    jitters = sorted(rng.uniform(0, SPREAD_SECONDS) for _ in range(TOTAL_ORDERS))

    print(f"stress-alpaca-queue: {TOTAL_ORDERS} orders over ~{SPREAD_SECONDS:.0f}s")
    print(f"base_url = {base_url}")
    print()

    run_start = time.perf_counter()

    def scheduled_submit(pair):
        idx, ticker, jitter = pair
        time.sleep(jitter)
        return submit_one(idx, base_url, client_id_header, ticker)

    tasks = [(i, tickers_rotation[i], jitters[i]) for i in range(TOTAL_ORDERS)]

    results: list[OrderResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        for r in pool.map(scheduled_submit, tasks):
            results.append(r)

    results.sort(key=lambda r: r.idx)
    run_elapsed = time.perf_counter() - run_start

    # --- summarize
    successes = [r for r in results if r.http_status == 200 and r.order_id.startswith("ALPACA-")]
    failures = [r for r in results if r.http_status != 200]
    non_alpaca = [r for r in results if r.http_status == 200 and not r.order_id.startswith("ALPACA-")]
    order_ids = [r.order_id for r in successes]
    duplicates = {oid for oid in order_ids if order_ids.count(oid) > 1}

    print(f"Finished in {run_elapsed:.1f}s")
    print()
    print(f"{'idx':>3} {'ticker':<6} {'http':>4} {'ms':>5}  order_id")
    print("-" * 75)
    for r in results:
        marker = "OK  " if (r.http_status == 200 and r.order_id.startswith("ALPACA-")) else "FAIL"
        oid = r.order_id or (f"ERR: {r.error[:40]}" if r.error else "(no id)")
        print(f"{r.idx:>3} {r.ticker:<6} {r.http_status:>4} {r.elapsed_ms:>5}  {marker}  {oid}")
    print()
    print(f"successes   : {len(successes)}/{TOTAL_ORDERS}")
    print(f"failures    : {len(failures)}")
    print(f"non-ALPACA  : {len(non_alpaca)}")
    print(f"duplicates  : {len(duplicates)}")
    if duplicates:
        for d in duplicates:
            print(f"  duplicate id: {d}")

    # --- write report if any failure (for Item D deliverable)
    if failures or duplicates or non_alpaca or len(successes) != TOTAL_ORDERS:
        report_path = _write_failure_report(results, run_elapsed, duplicates)
        print(f"\nFailure report: {report_path}")
        return 1 if not duplicates else 2
    return 0


def _write_failure_report(results, run_elapsed, duplicates) -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = os.path.join(here, "docs")
    os.makedirs(docs, exist_ok=True)
    path = os.path.join(docs, "v2-stress-test-report.md")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# 006 v2 Stress Test Report",
        "",
        f"**Timestamp:** {now}",
        f"**Total orders:** {TOTAL_ORDERS}  **Elapsed:** {run_elapsed:.1f}s",
        "",
        "## Per-order results",
        "",
        "| idx | ticker | http | ms | order_id / error |",
        "|---:|---|---:|---:|---|",
    ]
    for r in results:
        err_or_id = r.order_id if r.order_id else f"{r.error[:80]}"
        lines.append(f"| {r.idx} | {r.ticker} | {r.http_status} | {r.elapsed_ms} | {err_or_id} |")
    if duplicates:
        lines.extend(["", "## Duplicates detected", ""])
        for d in duplicates:
            lines.append(f"- `{d}`")
    lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


if __name__ == "__main__":
    sys.exit(main())
