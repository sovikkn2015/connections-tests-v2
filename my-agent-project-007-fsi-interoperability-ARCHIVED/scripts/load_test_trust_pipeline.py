"""
Load test the 007 trust pipeline against the live harness from
scripts/live_e2e_bedrock.py.

Usage:
  # 1. Start the stack (use env vars to persist ports)
  FSI_HARNESS_HOLD=1 python3 scripts/live_e2e_bedrock.py &
  # wait for "all 5 services up"
  # 2. Export the ports it printed, or just run:
  python3 scripts/load_test_trust_pipeline.py --url http://127.0.0.1:PORT \\
      --token $(cat /tmp/aid_token) --duration 60 --concurrency 50

This script is intentionally dependency-free (httpx + asyncio only).
Reports p50/p95/p99 + throughput + error rate.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LoadResult:
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    errors: int = 0
    total: int = 0


async def _one_call(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    server_url: str,
    tool_name: str,
    args: dict[str, Any],
    result: LoadResult,
) -> None:
    payload = {
        "aid_token": token,
        "server_url": server_url,
        "tool_name": tool_name,
        "arguments": args,
    }
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result.latencies_ms.append(elapsed_ms)
        result.status_counts[r.status_code] = result.status_counts.get(r.status_code, 0) + 1
        result.total += 1
    except Exception:
        result.errors += 1
        result.total += 1


async def _worker(
    client: httpx.AsyncClient, url: str, token: str, server_url: str,
    deadline: float, result: LoadResult,
) -> None:
    rotation = [
        ("get_client_profile", {"client_id": "CLT-0042"}),
        ("get_holdings",       {"client_id": "CLT-0042"}),
        ("get_financial_plan", {"client_id": "CLT-0042"}),
    ]
    i = 0
    while time.perf_counter() < deadline:
        tool, args = rotation[i % len(rotation)]
        await _one_call(client, url, token, server_url, tool, args, result)
        i += 1


async def run(
    url: str, token: str, server_url: str,
    duration: float, concurrency: int,
) -> LoadResult:
    limits = httpx.Limits(
        max_connections=concurrency * 2,
        max_keepalive_connections=concurrency * 2,
    )
    result = LoadResult()
    deadline = time.perf_counter() + duration
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        tasks = [
            asyncio.create_task(_worker(client, url, token, server_url, deadline, result))
            for _ in range(concurrency)
        ]
        await asyncio.gather(*tasks)
    return result


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs_sorted = sorted(xs)
    k = min(len(xs_sorted) - 1, int(round((p / 100.0) * (len(xs_sorted) - 1))))
    return xs_sorted[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="M6 /mcp/call endpoint")
    ap.add_argument("--token", required=True, help="AID token (valid, with wide scope)")
    ap.add_argument("--server-url", required=True,
                    help="downstream MCP adapter URL")
    ap.add_argument("--duration", type=float, default=30.0, help="seconds")
    ap.add_argument("--concurrency", type=int, default=20,
                    help="concurrent workers")
    args = ap.parse_args()

    print(f"[load] url={args.url}")
    print(f"[load] duration={args.duration}s concurrency={args.concurrency}")

    t0 = time.perf_counter()
    result = asyncio.run(run(
        args.url, args.token, args.server_url,
        args.duration, args.concurrency,
    ))
    elapsed = time.perf_counter() - t0

    rps = result.total / elapsed if elapsed > 0 else 0
    success = sum(v for k, v in result.status_counts.items() if 200 <= k < 300)
    success_rate = (success / result.total * 100) if result.total else 0

    print("-" * 72)
    print(f"total requests      : {result.total:>8d}")
    print(f"elapsed             : {elapsed:>8.2f}s")
    print(f"throughput          : {rps:>8.1f} req/s")
    print(f"success rate        : {success_rate:>7.1f}%")
    print(f"errors (network)    : {result.errors:>8d}")
    print(f"status codes        : {dict(sorted(result.status_counts.items()))}")
    print("latency (ms):")
    lat = result.latencies_ms
    if lat:
        print(f"  p50 = {_pct(lat, 50):8.1f}")
        print(f"  p90 = {_pct(lat, 90):8.1f}")
        print(f"  p95 = {_pct(lat, 95):8.1f}")
        print(f"  p99 = {_pct(lat, 99):8.1f}")
        print(f"  max = {max(lat):8.1f}")
        print(f"  avg = {statistics.mean(lat):8.1f}")
    print("-" * 72)

    # Non-zero exit if success rate < 95%
    return 0 if success_rate >= 95.0 else 2


if __name__ == "__main__":
    sys.exit(main())
