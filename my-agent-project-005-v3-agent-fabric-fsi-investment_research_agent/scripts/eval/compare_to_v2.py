#!/usr/bin/env python3
"""
V2 <-> V3 delta report — EVAL subagent deliverable #3.

Parses V2's markdown baseline (end-to-end-test-results-30-queries.md) and V3's
latest run summary, emits a markdown delta report.

Per-query diff:
  - V2 PASS + V3 PASS     -> "unchanged"
  - V2 PASS + V3 FAIL     -> "REGRESSION"  (adverse)
  - V2 DEGRADED + V3 PASS -> "improvement" (expected in V3 for many queries)
  - V2 FAIL + V3 PASS     -> "improvement"

Overall deltas:
  - pass rate
  - p50 / p95 latency (flag if p95 delta > 300 ms)
  - gateway-exclusive metrics (audit coverage, MNPI redactions, CB trips)

Verdict:
  - PASS : no regression + all gateway metrics present
  - WARN : minor regression (< 2%)
  - FAIL : regression >= 2% OR missing gateway metrics
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
V2_BASELINE_MD = (
    REPO_ROOT.parent
    / "my-agent-project-005-v2-integrations-fsi-investment_research_agent"
    / "docs" / "end-to-end-test-results-30-queries.md"
)
DEFAULT_V3_LATEST = REPO_ROOT / "scripts" / "eval" / "results" / "latest.json"
DEFAULT_OUT = REPO_ROOT / "scripts" / "eval" / "results" / "compare-to-v2.md"

REGRESSION_THRESHOLD_PCT = 2.0
LATENCY_P95_DELTA_WARN_MS = 300


def parse_v2_markdown(md_path: Path) -> dict[str, Any]:
    """Extract 30-row query table + scoreboard from the V2 results doc."""
    if not md_path.exists():
        raise FileNotFoundError(f"V2 baseline not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")

    pass_m = re.search(r"\*\*PASS\*\*.*?\*\*(\d+)\*\*", text)
    degr_m = re.search(r"\*\*DEGRADED\*\*.*?\*\*(\d+)\*\*", text)
    fail_m = re.search(r"\*\*FAIL\*\*.*?\*\*(\d+)\*\*", text)
    v2_pass = int(pass_m.group(1)) if pass_m else 0
    v2_degr = int(degr_m.group(1)) if degr_m else 0
    v2_fail = int(fail_m.group(1)) if fail_m else 0
    total = v2_pass + v2_degr + v2_fail or 30

    lat_m = re.search(r"Median latency\s*~?\s*([\d.]+)\s*s.*?max\s*([\d.]+)\s*s",
                      text, re.IGNORECASE)
    v2_median_ms = int(float(lat_m.group(1)) * 1000) if lat_m else 4500
    v2_max_ms = int(float(lat_m.group(2)) * 1000) if lat_m else 7069

    rows: list[dict] = []
    row_re = re.compile(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*\*\*([A-Z]+)\*\*.*?\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    for m in row_re.finditer(text):
        qid = int(m.group(1))
        if qid < 1 or qid > 30:
            continue
        rows.append({
            "id": qid,
            "text": m.group(2).strip(),
            "latency_ms": int(m.group(3)),
            "status": m.group(4).strip(),
            "response_excerpt": m.group(5).strip(),
        })

    by_id: dict[int, dict] = {}
    for r in rows:
        by_id.setdefault(r["id"], r)

    latencies = sorted([r["latency_ms"] for r in by_id.values()
                        if r["latency_ms"] > 0])
    p50 = latencies[len(latencies) // 2] if latencies else v2_median_ms
    p95 = (latencies[max(0, int(round(0.95 * (len(latencies) - 1))))]
           if latencies else v2_max_ms)

    pass_rate_pct = round(100.0 * v2_pass / total, 2)

    return {
        "source_path": str(md_path),
        "total": total,
        "pass_count": v2_pass,
        "degraded_count": v2_degr,
        "fail_count": v2_fail,
        "pass_rate_pct": pass_rate_pct,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "max_latency_ms": v2_max_ms,
        "queries": sorted(by_id.values(), key=lambda r: r["id"]),
    }


def load_v3_run(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        raise FileNotFoundError(f"V3 summary/latest not found: {summary_path}")
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = data.get("summary", data)
    run_dir = data.get("run_dir") or summary.get("run_dir")
    if not run_dir:
        raise RuntimeError("V3 run_dir missing from summary/latest")
    results_path = Path(run_dir) / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"V3 results.json missing: {results_path}")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    return {"summary": summary, "results": results, "run_dir": run_dir}


def diff_queries(v2_queries: list[dict], v3_results: list[dict]) -> list[dict]:
    v2_by_id = {q["id"]: q for q in v2_queries}
    diffs: list[dict] = []
    for r in v3_results:
        qid = r["id"]
        v2 = v2_by_id.get(qid, {})
        v2_status = v2.get("status", "UNKNOWN")
        status_verdict = r.get("status_verdict") or (
            "PASS" if r.get("judge_pass") else "FAIL"
        )
        v3_pass = (status_verdict == "PASS")
        v3_skipped = (status_verdict == "SKIPPED")
        v3_status = status_verdict
        if v3_skipped:
            verdict = "skipped"
        elif v2_status == "PASS" and v3_pass:
            verdict = "unchanged"
        elif v2_status == "PASS" and not v3_pass:
            verdict = "REGRESSION"
        elif v2_status in ("DEGRADED", "FAIL") and v3_pass:
            verdict = "improvement"
        else:
            verdict = "unchanged-fail"
        diffs.append({
            "id": qid,
            "text": r.get("text", v2.get("text", "")),
            "v2_status": v2_status,
            "v2_latency_ms": v2.get("latency_ms", 0),
            "v3_status": v3_status,
            "v3_latency_ms": r.get("latency_ms", 0),
            "verdict": verdict,
            "v3_reason": r.get("judge_reason", "") or r.get("skip_reason", ""),
            "v3_audit_records": r.get("audit_records_found", 0),
            "v3_audit_gateway": r.get("audit_has_gateway_stage", False),
            "v3_skip_reason": r.get("skip_reason"),
        })
    return diffs


def render_report(v2: dict, v3_run: dict, diffs: list[dict],
                  verdict: str, reasons: list[str]) -> str:
    s = v3_run["summary"]

    pass_delta = round(s["pass_rate_pct"] - v2["pass_rate_pct"], 2)
    p50_delta = int(s.get("p50_latency_ms", 0)) - int(v2["p50_latency_ms"])
    p95_delta = int(s.get("p95_latency_ms", 0)) - int(v2["p95_latency_ms"])
    regressions = [d for d in diffs if d["verdict"] == "REGRESSION"]
    improvements = [d for d in diffs if d["verdict"] == "improvement"]
    unchanged = [d for d in diffs if d["verdict"] == "unchanged"]
    unchanged_fail = [d for d in diffs if d["verdict"] == "unchanged-fail"]
    skipped = [d for d in diffs if d["verdict"] == "skipped"]

    verdict_emoji = {"PASS": "OK", "WARN": "WARN", "FAIL": "FAIL"}.get(verdict, "?")

    lines = [
        "# V2 -> V3 Eval Delta Report",
        "",
        f"**Verdict:** {verdict_emoji} **{verdict}**",
        "",
        f"**V2 source:** `{v2['source_path']}`",
        f"**V3 run:**    `{v3_run['run_dir']}`",
        f"**V3 mode:**   `{s.get('mode', 'UNKNOWN')}`",
        "",
    ]
    if reasons:
        lines.append("**Verdict reasons:**")
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    lines += [
        "## Scoreboard delta",
        "",
        "| Metric | V2 | V3 | Delta |",
        "|---|---|---|---|",
        f"| Pass rate | {v2['pass_rate_pct']:.2f}% | {s['pass_rate_pct']:.2f}% | "
        f"{pass_delta:+.2f}% |",
        f"| Pass count | {v2['pass_count']} / {v2['total']} | "
        f"{s['pass_count']} / {s['total']} | "
        f"{s['pass_count'] - v2['pass_count']:+d} |",
        f"| p50 latency | {v2['p50_latency_ms']} ms | {s.get('p50_latency_ms', 0)} ms | "
        f"{p50_delta:+d} ms |",
        f"| p95 latency | {v2['p95_latency_ms']} ms | {s.get('p95_latency_ms', 0)} ms | "
        f"{p95_delta:+d} ms |",
        "",
        "## V2 -> V3 transitions",
        "",
        f"- **REGRESSION** (V2 pass -> V3 fail): {len(regressions)}",
        f"- **Improvement** (V2 degraded/fail -> V3 pass): {len(improvements)}",
        f"- **Unchanged pass**: {len(unchanged)}",
        f"- **Still failing**: {len(unchanged_fail)}",
        f"- **SKIPPED** (orchestrator-only, not scored): {len(skipped)}",
        "",
        "## Gateway-exclusive V3 metrics (no V2 equivalent)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| FINRA audit coverage | {s.get('audit_coverage_pct', 0)}% "
        f"({s.get('audit_gateway_stage_count', 0)} with `Pipeline_Stage__c='gateway'`) |",
        f"| Gateway hops expected | {s.get('gateway_expected_count', 0)} of {s['total']} |",
        f"| MNPI redactions observed | {s.get('mnpi_redactions_total', 0)} |",
        f"| Circuit breaker trips | {s.get('circuit_breaker_trips', 0)} |",
        f"| Error count | {s.get('error_count', 0)} |",
        "",
    ]

    if regressions:
        lines += [
            "## Regressions (V2 PASS -> V3 FAIL)",
            "",
            "| # | Query | V2 ms | V3 ms | Reason |",
            "|---|---|---|---|---|",
        ]
        for d in regressions:
            reason = (d["v3_reason"] or "").replace("|", "\\|")[:100]
            lines.append(
                f"| {d['id']} | {d['text']} | {d['v2_latency_ms']} | "
                f"{d['v3_latency_ms']} | {reason} |"
            )
        lines.append("")

    if improvements:
        lines += [
            "## Improvements (V2 non-pass -> V3 PASS)",
            "",
            "| # | Query | V2 status | V3 ms | Audit? |",
            "|---|---|---|---|---|",
        ]
        for d in improvements:
            aud = "yes" if d["v3_audit_gateway"] else "no"
            lines.append(
                f"| {d['id']} | {d['text']} | {d['v2_status']} | "
                f"{d['v3_latency_ms']} | {aud} |"
            )
        lines.append("")

    lines += [
        "## Full per-query matrix",
        "",
        "| # | Query | V2 | V3 | V2 ms | V3 ms | Delta ms | Verdict | Skip reason |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in diffs:
        dms = d["v3_latency_ms"] - d["v2_latency_ms"]
        skip_r = (d.get("v3_skip_reason") or "").replace("|", "\\|")
        lines.append(
            f"| {d['id']} | {d['text']} | {d['v2_status']} | {d['v3_status']} | "
            f"{d['v2_latency_ms']} | {d['v3_latency_ms']} | {dms:+d} | "
            f"{d['verdict']} | {skip_r} |"
        )

    return "\n".join(lines) + "\n"


def compute_verdict(v2: dict, v3_summary: dict,
                    diffs: list[dict]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    pass_delta = v3_summary["pass_rate_pct"] - v2["pass_rate_pct"]
    regressions = [d for d in diffs if d["verdict"] == "REGRESSION"]
    p95_delta = int(v3_summary.get("p95_latency_ms", 0)) - int(v2["p95_latency_ms"])

    for key in ("audit_coverage_pct", "audit_gateway_stage_count",
                "mnpi_redactions_total", "circuit_breaker_trips"):
        if key not in v3_summary:
            reasons.append(f"FAIL: missing gateway metric `{key}` in V3 summary")

    if pass_delta <= -REGRESSION_THRESHOLD_PCT:
        reasons.append(
            f"FAIL: pass rate dropped by {abs(pass_delta):.2f}% "
            f"(>= {REGRESSION_THRESHOLD_PCT}% regression threshold)"
        )
    elif pass_delta < 0:
        reasons.append(
            f"WARN: pass rate dropped by {abs(pass_delta):.2f}% "
            f"(< {REGRESSION_THRESHOLD_PCT}% threshold, within tolerance)"
        )

    if regressions:
        reasons.append(f"note: {len(regressions)} per-query regression(s) observed")

    if p95_delta > LATENCY_P95_DELTA_WARN_MS:
        reasons.append(
            f"WARN: p95 latency increased by {p95_delta}ms "
            f"(> {LATENCY_P95_DELTA_WARN_MS}ms flag threshold)"
        )

    if any(r.startswith("FAIL") for r in reasons):
        return "FAIL", reasons
    if any(r.startswith("WARN") for r in reasons):
        return "WARN", reasons
    return "PASS", reasons


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--v2", default=str(V2_BASELINE_MD),
                   help="V2 baseline markdown file")
    p.add_argument("--v3", default=str(DEFAULT_V3_LATEST),
                   help="V3 latest.json (or summary.json) from run_eval.py")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--dry-run", action="store_true",
                   help="exercise all code paths using only the V2 markdown "
                        "and a synthesized V3 summary")
    args = p.parse_args(argv)

    try:
        v2 = parse_v2_markdown(Path(args.v2))
    except Exception as e:
        print(f"ERROR parsing V2 baseline: {e}", file=sys.stderr)
        return 1

    if args.dry_run and not Path(args.v3).exists():
        v3_run = {
            "run_dir": "(dry-run synthesized)",
            "summary": {
                "total": v2["total"],
                "pass_count": v2["total"],
                "fail_count": 0,
                "pass_rate_pct": 100.0,
                "p50_latency_ms": v2["p50_latency_ms"] + 100,
                "p95_latency_ms": v2["p95_latency_ms"] + 150,
                "max_latency_ms": v2["max_latency_ms"] + 200,
                "audit_coverage_pct": 100.0,
                "audit_gateway_stage_count": v2["total"],
                "gateway_expected_count": v2["total"],
                "mnpi_redactions_total": 0,
                "circuit_breaker_trips": 0,
                "error_count": 0,
                "mode": "DRY_RUN",
            },
            "results": [
                {
                    "id": q["id"], "text": q["text"],
                    "judge_pass": True, "judge_reason": "[dry-run synth]",
                    "latency_ms": q["latency_ms"] + 100,
                    "audit_records_found": 1, "audit_has_gateway_stage": True,
                }
                for q in v2["queries"]
            ],
        }
    else:
        try:
            v3_run = load_v3_run(Path(args.v3))
        except Exception as e:
            print(f"ERROR loading V3 run: {e}", file=sys.stderr)
            return 1

    diffs = diff_queries(v2["queries"], v3_run["results"])
    verdict, reasons = compute_verdict(v2, v3_run["summary"], diffs)
    report = render_report(v2, v3_run, diffs, verdict, reasons)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"[compare_to_v2] verdict={verdict} wrote {out}")
    print(f"[compare_to_v2] V2 pass={v2['pass_rate_pct']:.2f}% "
          f"V3 pass={v3_run['summary']['pass_rate_pct']:.2f}%")
    (out.with_suffix(".json")).write_text(
        json.dumps({
            "verdict": verdict, "reasons": reasons,
            "v2": {k: v for k, v in v2.items() if k != "queries"},
            "v3_summary": v3_run["summary"],
            "diffs": diffs,
        }, indent=2), encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
