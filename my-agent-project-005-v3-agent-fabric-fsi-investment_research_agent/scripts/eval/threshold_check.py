#!/usr/bin/env python3
"""
Definition-of-done gate — EVAL subagent deliverable #5.

Reads the latest V3 run summary, V2-delta report, and synthetic-test latest
summary, then checks ALL of these:

  1. Overall pass rate >= (V2 pass rate - 2%)
  2. All 4 synthetic tests pass
  3. p95 latency <= (V2 p95 + 300 ms)
  4. FINRA audit coverage == 100% of eval calls

Exits 0 if all criteria pass, non-zero with a per-criterion report otherwise.

This script is intentionally NOT run during deploy. The REVIEW subagent
invokes it as part of the production-readiness gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_LATEST = REPO_ROOT / "scripts" / "eval" / "results" / "latest.json"
DEFAULT_SYNTHETIC_LATEST = (REPO_ROOT / "scripts" / "eval" / "results"
                            / "synthetic" / "latest.json")
V2_BASELINE_MD = (
    REPO_ROOT.parent
    / "my-agent-project-005-v2-integrations-fsi-investment_research_agent"
    / "docs" / "end-to-end-test-results-30-queries.md"
)

PASS_RATE_REGRESSION_MAX_PCT = 2.0
P95_LATENCY_DELTA_MAX_MS = 300
AUDIT_COVERAGE_MIN_PCT = 100.0
SYNTHETIC_REQUIRED_TESTS = {"mnpi_redaction", "rate_limit",
                            "circuit_breaker", "finra_audit"}


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _parse_v2_pass_rate_and_p95(md_path: Path) -> tuple[float, int]:
    if not md_path.exists():
        return (0.0, 0)
    text = md_path.read_text(encoding="utf-8")
    pass_m = re.search(r"\*\*PASS\*\*.*?\*\*(\d+)\*\*", text)
    degr_m = re.search(r"\*\*DEGRADED\*\*.*?\*\*(\d+)\*\*", text)
    fail_m = re.search(r"\*\*FAIL\*\*.*?\*\*(\d+)\*\*", text)
    v2_pass = int(pass_m.group(1)) if pass_m else 0
    v2_degr = int(degr_m.group(1)) if degr_m else 0
    v2_fail = int(fail_m.group(1)) if fail_m else 0
    total = v2_pass + v2_degr + v2_fail or 30
    rate = round(100.0 * v2_pass / total, 2)
    row_re = re.compile(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*\*\*([A-Z]+)\*\*",
        re.MULTILINE,
    )
    latencies: list[int] = []
    seen_ids: set[int] = set()
    for m in row_re.finditer(text):
        qid = int(m.group(1))
        if 1 <= qid <= 30 and qid not in seen_ids:
            seen_ids.add(qid)
            latencies.append(int(m.group(3)))
    latencies.sort()
    if not latencies:
        return (rate, 0)
    idx = max(0, min(len(latencies) - 1,
                     int(round(0.95 * (len(latencies) - 1)))))
    return (rate, latencies[idx])


def check(v2_pass_rate: float, v2_p95: int,
          v3_summary: dict, synthetic: dict) -> tuple[bool, list[dict]]:
    results: list[dict] = []

    # 1. Pass rate — SKIPPED queries already excluded from v3 numerator/denom.
    v3_rate = float(v3_summary.get("pass_rate_pct", 0.0))
    min_rate = v2_pass_rate - PASS_RATE_REGRESSION_MAX_PCT
    scored_n = v3_summary.get("scored_count", v3_summary.get("total", 0))
    skipped_n = v3_summary.get("skipped_count", 0)
    pass_note = ""
    if skipped_n:
        pass_note = (f" (MCP-direct: {scored_n} scored, "
                     f"{skipped_n} SKIPPED orchestrator-only)")
    results.append({
        "criterion": "pass_rate",
        "expected": f">= {min_rate:.2f}% (V2 {v2_pass_rate:.2f}% - "
                    f"{PASS_RATE_REGRESSION_MAX_PCT}%)",
        "actual":   f"{v3_rate:.2f}%{pass_note}",
        "passed":   v3_rate >= min_rate - 1e-9,
    })

    # 2. Synthetic tests
    syn_tests = {r["name"]: r.get("passed", False)
                 for r in (synthetic.get("results") or [])}
    missing = SYNTHETIC_REQUIRED_TESTS - set(syn_tests.keys())
    failed = [n for n, p in syn_tests.items() if not p]
    results.append({
        "criterion": "synthetic_tests_all_pass",
        "expected": "all 4 of " + str(sorted(SYNTHETIC_REQUIRED_TESTS)),
        "actual":   ("pass=" + ",".join(sorted(n for n, p in syn_tests.items() if p))
                     + "; fail=" + ",".join(sorted(failed))
                     + (f"; missing={sorted(missing)}" if missing else "")),
        "passed":   (not missing) and (not failed) and len(syn_tests) >= 4,
    })

    # 3. p95 latency
    v3_p95 = int(v3_summary.get("p95_latency_ms", 0))
    max_p95 = v2_p95 + P95_LATENCY_DELTA_MAX_MS
    results.append({
        "criterion": "p95_latency",
        "expected": f"<= {max_p95} ms (V2 {v2_p95} ms + "
                    f"{P95_LATENCY_DELTA_MAX_MS} ms)",
        "actual":   f"{v3_p95} ms",
        "passed":   v3_p95 <= max_p95,
    })

    # 4. Audit coverage
    audit = float(v3_summary.get("audit_coverage_pct", 0.0))
    results.append({
        "criterion": "finra_audit_coverage",
        "expected": f"== {AUDIT_COVERAGE_MIN_PCT:.2f}%",
        "actual":   f"{audit:.2f}%",
        "passed":   audit >= AUDIT_COVERAGE_MIN_PCT - 1e-9,
    })

    all_pass = all(r["passed"] for r in results)
    return all_pass, results


def print_results(passed_overall: bool, results: list[dict],
                  v2_pass_rate: float, v2_p95: int,
                  v3_summary: dict, mode: str) -> None:
    banner = "PASS" if passed_overall else "FAIL"
    print(f"\n=== threshold_check verdict: {banner} (mode={mode}) ===\n")
    print(f"V2 baseline: pass={v2_pass_rate:.2f}% p95={v2_p95}ms")
    print(f"V3 summary:  pass={v3_summary.get('pass_rate_pct', 0)}% "
          f"p95={v3_summary.get('p95_latency_ms', 0)}ms "
          f"audit={v3_summary.get('audit_coverage_pct', 0)}%")
    print()
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['criterion']}")
        print(f"         expected: {r['expected']}")
        print(f"         actual:   {r['actual']}")
    print()


def _synth_from_dry_run() -> dict:
    return {
        "mode": "DRY_RUN_SYNTH",
        "pass_count": 4,
        "fail_count": 0,
        "total": 4,
        "results": [
            {"name": n, "passed": True, "details": {"mode": "dry-run-synth"}}
            for n in sorted(SYNTHETIC_REQUIRED_TESTS)
        ],
    }


def _v3_from_dry_run(v2_rate: float, v2_p95: int) -> dict:
    return {
        "mode": "DRY_RUN_SYNTH",
        "total": 30,
        "pass_count": 30,
        "fail_count": 0,
        "pass_rate_pct": max(100.0, v2_rate),
        "p50_latency_ms": 4500,
        "p95_latency_ms": v2_p95 + 100,
        "audit_coverage_pct": 100.0,
        "audit_gateway_stage_count": 30,
        "gateway_expected_count": 18,
        "mnpi_redactions_total": 0,
        "circuit_breaker_trips": 0,
        "error_count": 0,
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--v2", default=str(V2_BASELINE_MD))
    p.add_argument("--v3", default=str(DEFAULT_V3_LATEST))
    p.add_argument("--synthetic", default=str(DEFAULT_SYNTHETIC_LATEST))
    p.add_argument("--out", default="")
    p.add_argument("--dry-run", action="store_true",
                   help="synthesize missing artifacts so code paths run; "
                        "returns PASS for CI sanity-check")
    args = p.parse_args(argv)

    v2_rate, v2_p95 = _parse_v2_pass_rate_and_p95(Path(args.v2))
    if v2_rate == 0.0:
        print(f"ERROR: could not parse V2 baseline at {args.v2}",
              file=sys.stderr)
        return 1

    v3_latest = _load_json(Path(args.v3))
    synthetic = _load_json(Path(args.synthetic))
    mode = "LIVE"

    if args.dry_run and v3_latest is None:
        v3_summary = _v3_from_dry_run(v2_rate, v2_p95)
        mode = "DRY_RUN_SYNTH"
    elif v3_latest is None:
        print(f"ERROR: V3 latest.json not found at {args.v3}", file=sys.stderr)
        print("       run `python scripts/eval/run_eval.py` first, "
              "or pass --dry-run", file=sys.stderr)
        return 1
    else:
        v3_summary = v3_latest.get("summary", v3_latest)

    if args.dry_run and synthetic is None:
        synthetic = _synth_from_dry_run()
        mode = "DRY_RUN_SYNTH"
    elif synthetic is None:
        print(f"ERROR: synthetic latest.json not found at {args.synthetic}",
              file=sys.stderr)
        print("       run `python scripts/eval/synthetic_tests.py` first, "
              "or pass --dry-run", file=sys.stderr)
        return 1

    all_pass, results = check(v2_rate, v2_p95, v3_summary, synthetic)
    print_results(all_pass, results, v2_rate, v2_p95, v3_summary, mode)

    report: dict[str, Any] = {
        "mode": mode,
        "verdict": "PASS" if all_pass else "FAIL",
        "v2": {"pass_rate_pct": v2_rate, "p95_latency_ms": v2_p95},
        "v3_summary": v3_summary,
        "synthetic_summary": {
            "total": synthetic.get("total"),
            "pass_count": synthetic.get("pass_count"),
            "fail_count": synthetic.get("fail_count"),
        },
        "criteria": results,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2),
                                  encoding="utf-8")
        print(f"wrote {args.out}")

    return 0 if all_pass else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
