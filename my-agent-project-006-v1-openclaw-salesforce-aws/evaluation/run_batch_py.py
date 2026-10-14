#!/usr/bin/env python3
"""Batch runner for run12-targeted eval with per-query timeout (macOS has no `timeout` CLI)."""
import os
import subprocess
import sys
import time

QUERY_IDS = [4, 5, 6, 7, 10, 12, 13, 14, 17, 21, 22, 23, 25, 26, 27, 28, 29, 31, 32,
             33, 34, 37, 38, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 150]
TIMEOUT = int(os.environ.get("QUERY_TIMEOUT_S", "300"))


def run_one(qid):
    t0 = time.time()
    out_path = f"run12-targeted/q{qid}.json"
    print(f"=== Q{qid} === (timeout={TIMEOUT}s)", flush=True)
    try:
        proc = subprocess.run(
            ["python3", "run_suite.py", "--query-id", str(qid), "--output", out_path],
            timeout=TIMEOUT,
            capture_output=True,
            text=True,
        )
        tail = (proc.stdout + proc.stderr).splitlines()[-3:]
        for ln in tail:
            print(ln, flush=True)
        status = "OK" if proc.returncode == 0 else f"EXIT_{proc.returncode}"
    except subprocess.TimeoutExpired:
        status = "TIMEOUT"
        print(f"Q{qid} timed out after {TIMEOUT}s; skipping", flush=True)
    dt = time.time() - t0
    print(f"Q{qid} -> {status} ({dt:.1f}s)", flush=True)
    return status


def main():
    t0 = time.time()
    statuses = {}
    for qid in QUERY_IDS:
        statuses[qid] = run_one(qid)
        time.sleep(2)
    dt = time.time() - t0
    ok = sum(1 for v in statuses.values() if v == "OK")
    print(f"\nBATCH DONE in {dt/60:.1f} min: {ok}/{len(QUERY_IDS)} succeeded")
    for qid, st in statuses.items():
        if st != "OK":
            print(f"  Q{qid}: {st}")


if __name__ == "__main__":
    main()
