"""
One-shot load test: spawns the trust pipeline (M1 + M2/M4 + adapter + M6 + M10
against real AWS), mints an AID token, runs load_test_trust_pipeline.py's
logic for N seconds with K concurrency, then tears down.

Use this to get real p50/p95/p99 numbers. No mocks for M6 trust pipeline;
M10 writes to real S3 WORM; M1 uses local RSA; M2/M4 uses local Rego evaluator.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import boto3
import httpx

# Reuse the E2E harness machinery
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from live_e2e_bedrock import (  # type: ignore
    FAKE_ADAPTER_SRC,
    UvicornProcess,
    _free_port,
)
from load_test_trust_pipeline import run as run_load  # type: ignore


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("live_load")


async def _worker_with_token(
    client: httpx.AsyncClient, url: str, token: str, server_url: str,
    deadline: float, result,
) -> None:
    rotation = [
        ("get_client_profile", {"client_id": "CLT-0042"}),
        ("get_holdings",       {"client_id": "CLT-0042"}),
        ("get_financial_plan", {"client_id": "CLT-0042"}),
    ]
    i = 0
    while time.perf_counter() < deadline:
        tool, args = rotation[i % len(rotation)]
        payload = {
            "aid_token": token,
            "server_url": server_url,
            "tool_name": tool,
            "arguments": args,
        }
        t0 = time.perf_counter()
        try:
            r = await client.post(url, json=payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            result.latencies_ms.append(elapsed_ms)
            result.status_counts[r.status_code] = \
                result.status_counts.get(r.status_code, 0) + 1
            result.total += 1
        except Exception:
            result.errors += 1
            result.total += 1
        i += 1


async def _run_multi_token(
    url: str, server_url: str, tokens: list[str], duration: float,
):
    """Each worker has its own AID (avoids per-actor rate limiter)."""
    from load_test_trust_pipeline import LoadResult  # local import
    result = LoadResult()
    limits = httpx.Limits(
        max_connections=len(tokens) * 2,
        max_keepalive_connections=len(tokens) * 2,
    )
    deadline = time.perf_counter() + duration
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        tasks = [
            asyncio.create_task(
                _worker_with_token(client, url, tok, server_url, deadline, result)
            )
            for tok in tokens
        ]
        await asyncio.gather(*tasks)
    return result


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
    return s[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--concurrency", type=int, default=20)
    args = ap.parse_args()

    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    os.environ.setdefault("AWS_REGION", aws_region)
    sts = boto3.client("sts", region_name=aws_region)
    ident = sts.get_caller_identity()
    log.info("aws account=%s arn=%s", ident["Account"], ident["Arn"])

    # ports
    m1_port = _free_port()
    m2_port = _free_port()
    m10_port = _free_port()
    adapter_port = _free_port()
    m6_port = _free_port()

    common_env = {"AWS_REGION": aws_region, "PYTHONUNBUFFERED": "1"}
    m1_env = dict(common_env)
    m2_env = {**common_env, "USE_LOCAL_EVALUATOR": "true"}
    m10_env = {
        **common_env,
        "M10_S3_BUCKET": f"fsi007-audit-worm-{aws_region}",
        "M10_S3_REGION": aws_region,
        "M10_DLQ_BACKEND": "sqs",
        "M10_DLQ_QUEUE_URL": (
            f"https://sqs.{aws_region}.amazonaws.com/{ident['Account']}/fsi007-audit-dlq"
        ),
    }
    m6_env = {
        **common_env,
        "M1_URL": f"http://127.0.0.1:{m1_port}",
        "M2_URL": f"http://127.0.0.1:{m2_port}",
        "M4_URL": f"http://127.0.0.1:{m2_port}",
        "M7_URL": f"http://127.0.0.1:{adapter_port}",
        "M10_URL": f"http://127.0.0.1:{m10_port}",
    }

    # write shims
    tmp = REPO_ROOT / "scripts" / "_live_e2e_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "fake_adapter.py").write_text(FAKE_ADAPTER_SRC)

    def _pkg_shim(alias, module_dir, submodule):
        return (
            'import importlib.util, sys, os\n'
            f'_dir = {str(module_dir)!r}\n'
            'sys.path.insert(0, _dir)\n'
            '_init = os.path.join(_dir, "__init__.py")\n'
            f'spec = importlib.util.spec_from_file_location({alias!r}, _init,\n'
            '    submodule_search_locations=[_dir])\n'
            'pkg = importlib.util.module_from_spec(spec)\n'
            f'sys.modules[{alias!r}] = pkg\n'
            'spec.loader.exec_module(pkg)\n'
            'from importlib import import_module\n'
            f'app = import_module("{alias}.{submodule}").app\n'
        )

    (tmp / "m1_shim.py").write_text(_pkg_shim("m1_pkg", SRC / "m1-identity", "entrypoint"))
    (tmp / "m2_shim.py").write_text(_pkg_shim("m2_pkg", SRC / "m2-m4-policy-engine", "app"))
    (tmp / "m10_shim.py").write_text(_pkg_shim("m10_pkg", SRC / "m10-audit-logger", "app"))
    (tmp / "m6_shim.py").write_text(_pkg_shim("m6_pkg", SRC / "m6-mcp-gateway", "app"))

    procs = [
        UvicornProcess("M1",      tmp, "m1_shim:app",       m1_port,  m1_env),
        UvicornProcess("M2/M4",   tmp, "m2_shim:app",       m2_port,  m2_env),
        UvicornProcess("M10",     tmp, "m10_shim:app",      m10_port, m10_env),
        UvicornProcess("adapter", tmp, "fake_adapter:app",  adapter_port, common_env),
        UvicornProcess("M6",      tmp, "m6_shim:app",       m6_port,  m6_env),
    ]

    try:
        for p in procs:
            p.start()
        log.info("all 5 services up")

        # Mint one AID per worker so no single actor trips the 100/min
        # per-user rate limit. This mirrors production where many advisors
        # share the same trust gateway.
        tokens: list[str] = []
        for i in range(args.concurrency):
            r = httpx.post(f"http://127.0.0.1:{m1_port}/aid/issue", timeout=10, json={
                "actor_type": "human",
                "display_name": f"Load Tester {i}",
                "firm_id": "acme_wm",
                "archetype": "tier3_broker_dealer",
                "role": "advisor",
                "jurisdiction": "US",
                "authority_scope": [
                    "get_client_profile", "get_holdings", "get_financial_plan",
                ],
                "client_scope": ["CLT-0042"],
                "ttl_hours": 1,
            })
            r.raise_for_status()
            tokens.append(r.json()["token"])
        log.info("minted %d AID tokens (one per worker)", len(tokens))

        # warm-up with token 0
        warm = httpx.post(f"http://127.0.0.1:{m6_port}/mcp/call", timeout=10, json={
            "aid_token": tokens[0],
            "server_url": f"http://127.0.0.1:{adapter_port}",
            "tool_name": "get_client_profile",
            "arguments": {"client_id": "CLT-0042"},
        })
        assert warm.status_code == 200, warm.text
        log.info("warmup ok (status=%d, %dms)", warm.status_code,
                 int(warm.elapsed.total_seconds() * 1000))

        # ── run load, one token per worker ──────────────────────
        print()
        print(f"[load] starting: duration={args.duration}s  "
              f"concurrency={args.concurrency}  tokens={len(tokens)}")

        result = asyncio.run(_run_multi_token(
            url=f"http://127.0.0.1:{m6_port}/mcp/call",
            server_url=f"http://127.0.0.1:{adapter_port}",
            tokens=tokens,
            duration=args.duration,
        ))

        elapsed = args.duration
        rps = result.total / elapsed if elapsed else 0
        success = sum(v for k, v in result.status_counts.items() if 200 <= k < 300)
        success_rate = success / result.total * 100 if result.total else 0

        print()
        print("-" * 72)
        print(f"007 trust pipeline: M6 -> M1 -> M2 -> M4 -> M7 -> adapter -> M4 -> M10")
        print(f"concurrency={args.concurrency}  duration={args.duration}s")
        print("-" * 72)
        print(f"total requests      : {result.total}")
        print(f"throughput          : {rps:.1f} req/s")
        print(f"success rate        : {success_rate:.2f}%")
        print(f"errors (network)    : {result.errors}")
        print(f"status codes        : {dict(sorted(result.status_counts.items()))}")
        print("latency (ms):")
        lat = result.latencies_ms
        if lat:
            import statistics
            print(f"  p50 = {_pct(lat, 50):8.2f}")
            print(f"  p90 = {_pct(lat, 90):8.2f}")
            print(f"  p95 = {_pct(lat, 95):8.2f}")
            print(f"  p99 = {_pct(lat, 99):8.2f}")
            print(f"  max = {max(lat):8.2f}")
            print(f"  avg = {statistics.mean(lat):8.2f}")
        print("-" * 72)
        return 0 if success_rate >= 95.0 else 2

    finally:
        for p in procs:
            try:
                p.stop()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
