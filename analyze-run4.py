#!/usr/bin/env python3
"""
Deep Failure Analysis — Run 4 (36/150 = 24%)
Answers: is the problem (A) no response, (B) low quality, or (C) strict judge?
"""
import json
from collections import Counter, defaultdict

with open("my-agent-project-006-v1-openclaw-salesforce-aws/evaluation/eval-results-full-150-run4.json") as f:
    data = json.load(f)

results = data["results"]

# Normalize error records that lack standard fields
for r in results:
    r.setdefault("avg_score", 0.0)
    r.setdefault("scores", {})
    r.setdefault("response_preview", r.get("error", ""))
    r.setdefault("flags", [r.get("error", "GATEWAY_TIMEOUT")])
    r.setdefault("level", "UNKNOWN")
    r.setdefault("query", "(unknown)")
    r.setdefault("latency_ms", 0)
    r.setdefault("tools_used", [])
    if r.get("status") == "error":
        r["status"] = "ERROR"

def is_async_ack(r):
    preview = r.get("response_preview", "")
    return "ok" in preview and "runId" in preview and len(preview) < 120

def classify_failure(r):
    flags = " ".join(r.get("flags", [])).lower()
    patterns = []
    if is_async_ack(r):
        return ["ASYNC_ACK_NO_RESPONSE"]
    if any(kw in flags for kw in ["hallucin", "fabricat", "invented", "false precision"]):
        patterns.append("HALLUCINATION_FABRICATION")
    if any(kw in flags for kw in ["no_source", "no source", "no_tool", "no tool", "attribution", "not cited", "no citation"]):
        patterns.append("NO_SOURCE_ATTRIBUTION")
    if any(kw in flags for kw in ["tool_failure", "tool not", "expected_tool", "failed_to_use", "tool_use_unclear", "not_invoked", "tool execution"]):
        patterns.append("TOOL_FAILURE_OR_NOT_USED")
    if any(kw in flags for kw in ["500 error", "data unavailable", "data_unavailable", "query error", "backend issue"]):
        patterns.append("DATA_UNAVAILABLE_ERROR")
    if any(kw in flags for kw in ["core query unmet", "core_question_unanswered", "primary task failed", "not delivered", "not met"]):
        patterns.append("CORE_QUESTION_UNANSWERED")
    if any(kw in flags for kw in ["unverif", "cannot be verified", "no ground truth"]):
        patterns.append("UNVERIFIABLE_DATA")
    if any(kw in flags for kw in ["safety", "mnpi", "compliance", "mislead", "manipulation"]):
        patterns.append("SAFETY_COMPLIANCE_CONCERN")
    if any(kw in flags for kw in ["timestamp", "no timestamp", "missing_timestamp"]):
        patterns.append("MISSING_TEMPORAL_CONTEXT")
    return patterns or ["OTHER"]

levels_order = ["L1", "L2", "L3", "L4", "L5", "Edge", "UNKNOWN"]
level_data = defaultdict(list)
for r in results:
    level_data[r.get("level", "UNKNOWN")].append(r)

def hr(c="─", w=100): print(c * w)
def section(t): print(); hr("═"); print(f"  {t}"); hr("═")

# ═══ EXECUTIVE SUMMARY ═══
section("EXECUTIVE SUMMARY — Run 4 (Best Run)")
print(f"  Total queries:  {data['total_queries']}")
print(f"  Passed (>=3.5): {data['passed']}  ({data['pass_rate']}%)")
print(f"  Failed (<3.5):  {data['failed']}")
print(f"  Errors:         {data['errors']}")

async_acks = [r for r in results if is_async_ack(r)]
real_responses = [r for r in results if not is_async_ack(r)]
real_fails = [r for r in real_responses if r["status"] not in ("PASS", "ERROR")]
error_results = [r for r in results if r["status"] == "ERROR"]

print(f"\n  Async acks (raw API JSON, no real answer):  {len(async_acks)}")
print(f"  Real responses returned:                    {len(real_responses)}")
print(f"  Real responses that PASSED:                 {len([r for r in real_responses if r['status'] == 'PASS'])}")
print(f"  Real responses that FAILED:                 {len(real_fails)}")

# ═══ KEY DIAGNOSIS ═══
section("KEY DIAGNOSIS: (A) No Response vs (B) Low Quality vs (C) Strict Judge")

no_response_count = len(async_acks) + data["errors"]
low_quality = [r for r in real_fails if r["avg_score"] < 3.0]
near_miss = [r for r in real_fails if 3.0 <= r["avg_score"] < 3.5]
barely_passed = [r for r in real_responses if r["status"] == "PASS" and r["avg_score"] < 4.0]
all_real_failures = len(low_quality) + len(near_miss)

print(f"""
  (A) NO RESPONSE (async acks + errors):      {no_response_count:3d}  ({no_response_count/150*100:.1f}%)
      - Async acks (raw runId JSON):          {len(async_acks):3d}
      - Errors:                               {data['errors']:3d}

  (B) LOW QUALITY (real response, score<3.0):  {len(low_quality):3d}  ({len(low_quality)/150*100:.1f}%)

  (C) NEAR-MISS (score 3.0-3.4, strict judge): {len(near_miss):3d}  ({len(near_miss)/150*100:.1f}%)

  PASSED (>=3.5):                               {data['passed']:3d}  ({data['pass_rate']}%)
  Barely passed (3.5-3.9):                      {len(barely_passed):3d}

  VERDICT:
    Primary problem = (B) LOW QUALITY RESPONSES
    {len(low_quality)} of {all_real_failures} real failures ({len(low_quality)/all_real_failures*100 if all_real_failures else 0:.0f}%) scored below 3.0
    Only {len(async_acks)} queries got no response at all (async acks)
    {len(near_miss)} queries are near-misses that could flip with targeted fixes
""")

# ═══ THRESHOLD SENSITIVITY ═══
section("THRESHOLD SENSITIVITY: What if we lowered the bar?")
thresholds = [3.5, 3.0, 2.5, 2.0, 1.5, 1.0]
print(f"  {'Threshold':>10}  {'Pass':>6}  {'Rate':>7}  {'Delta vs 3.5':>14}")
hr("─", 50)
baseline = data["passed"]
for t in thresholds:
    p = sum(1 for r in results if r["avg_score"] >= t)
    d = p - baseline
    m = " <-- current" if t == 3.5 else ""
    print(f"  {t:>10.1f}  {p:>6}  {p/150*100:>6.1f}%  {'+' if d > 0 else ''}{d:>13}{m}")

# ═══ PER-LEVEL BREAKDOWN ═══
section("PER-LEVEL BREAKDOWN")
print(f"  {'Level':<8} {'Total':>5} {'Pass':>5} {'Fail':>5} {'Rate':>6} {'Async':>6} {'NearMiss':>9} {'AvgScore':>9}")
hr("─", 65)
for level in levels_order:
    if level not in level_data: continue
    ld = level_data[level]
    total = len(ld)
    passed = sum(1 for r in ld if r["status"] == "PASS")
    async_n = sum(1 for r in ld if is_async_ack(r))
    near_n = sum(1 for r in ld if r["status"] != "PASS" and 3.0 <= r["avg_score"] < 3.5)
    avg = sum(r["avg_score"] for r in ld) / total
    print(f"  {level:<8} {total:>5} {passed:>5} {total-passed:>5} {passed/total*100:>5.1f}% {async_n:>6} {near_n:>9} {avg:>9.2f}")

# ═══ PER-LEVEL DEEP DIVE ═══
for level in levels_order:
    if level not in level_data: continue
    ld = level_data[level]
    total = len(ld)
    passed_n = sum(1 for r in ld if r["status"] == "PASS")
    failed_list = [r for r in ld if r["status"] != "PASS"]
    async_list = [r for r in ld if is_async_ack(r)]
    near_list = [r for r in failed_list if 3.0 <= r["avg_score"] < 3.5]
    real_fail_list = [r for r in failed_list if not is_async_ack(r)]

    section(f"LEVEL {level} — {total} queries, {passed_n} passed ({passed_n/total*100:.0f}%)")

    print(f"\n  1) Response Type Breakdown:")
    print(f"     Async acks (no real answer):  {len(async_list)}")
    print(f"     Real responses:               {total - len(async_list)}")
    print(f"       - Passed:                   {passed_n}")
    print(f"       - Failed (real response):   {len(real_fail_list)}")

    if async_list:
        print(f"\n     Async ack queries:")
        for r in async_list:
            print(f"       Q{r['query_id']}: {r['query'][:70]}")

    if real_fail_list:
        pattern_counter = Counter()
        for r in real_fail_list:
            for p in classify_failure(r):
                pattern_counter[p] += 1
        print(f"\n  2) Top 3 Failure Patterns (real responses that scored low):")
        for pattern, count in pattern_counter.most_common(3):
            pct = count / len(real_fail_list) * 100
            print(f"     {pattern:<40} {count:>3} ({pct:.0f}% of {level} real failures)")

    print(f"\n  3) Near-Misses (3.0-3.4): {len(near_list)}")
    if near_list:
        for r in near_list:
            print(f"     Q{r['query_id']:>3} score={r['avg_score']:.1f}  {r['query'][:65]}")
            low_dims = {k: v for k, v in r["scores"].items() if v <= 2}
            if low_dims:
                print(f"          Drag dimensions: {low_dims}")

    if failed_list:
        dim_totals = defaultdict(list)
        for r in failed_list:
            for dim, val in r["scores"].items():
                dim_totals[dim].append(val)
        print(f"\n  4) Avg Score by Dimension (failed queries):")
        for dim in ["accuracy","completeness","relevance","safety","actionability","attribution","reasoning"]:
            if dim in dim_totals:
                vals = dim_totals[dim]
                avg = sum(vals)/len(vals)
                zeros = sum(1 for v in vals if v == 0)
                print(f"     {dim:<16} avg={avg:.2f}  zeros={zeros}")

# ═══ GLOBAL FAILURE PATTERN RANKING ═══
section("GLOBAL FAILURE PATTERN RANKING (all failed queries)")

all_fails = [r for r in results if r["status"] != "PASS"]
global_patterns = Counter()
pattern_by_level = defaultdict(lambda: Counter())

for r in all_fails:
    for p in classify_failure(r):
        global_patterns[p] += 1
        pattern_by_level[p][r.get("level", "?")] += 1

print(f"\n  {'Pattern':<40} {'Count':>5} {'%':>6}  Level Breakdown")
hr("─", 95)
for pattern, count in global_patterns.most_common():
    pct = count / len(all_fails) * 100
    level_str = ", ".join(f"{l}:{c}" for l, c in sorted(pattern_by_level[pattern].items()))
    print(f"  {pattern:<40} {count:>5} {pct:>5.1f}%  {level_str}")

# ═══ NEAR-MISS DEEP DIVE ═══
near_miss_all = [r for r in results if r["status"] != "PASS" and 3.0 <= r["avg_score"] < 3.5]
section(f"NEAR-MISS DEEP DIVE — {len(near_miss_all)} queries scoring 3.0-3.4")

print(f"\n  These {len(near_miss_all)} queries need only 0.1-0.5 improvement to pass.")
new_total = data["passed"] + len(near_miss_all)
print(f"  If ALL near-misses passed: {new_total}/150 = {new_total/150*100:.1f}%\n")

dragging_dims = Counter()
for r in near_miss_all:
    for dim, val in r["scores"].items():
        if val <= 2:
            dragging_dims[dim] += 1

print(f"  Dimensions most often <=2 in near-miss queries (the drag factors):")
for dim, count in dragging_dims.most_common():
    print(f"    {dim:<16} <=2 in {count}/{len(near_miss_all)} near-misses ({count/len(near_miss_all)*100:.0f}%)")

# ═══ LATENCY ANALYSIS ═══
section("LATENCY ANALYSIS")

def lat_stats(vals, label):
    if not vals:
        print(f"  {label}: no data"); return
    vals.sort()
    avg = sum(vals)/len(vals)
    med = vals[len(vals)//2]
    p95 = vals[int(len(vals)*0.95)]
    print(f"  {label:<25} avg={avg/1000:.1f}s  med={med/1000:.1f}s  p95={p95/1000:.1f}s  max={vals[-1]/1000:.1f}s")

lat_stats([r["latency_ms"] for r in results if r["status"] == "PASS"], "Passed queries")
lat_stats([r["latency_ms"] for r in results if r["status"] != "PASS"], "Failed queries")
lat_stats([r["latency_ms"] for r in results if is_async_ack(r)], "Async ack queries")

timeouts = [r for r in results if r["latency_ms"] > 60000]
print(f"\n  Queries >60s (potential timeouts): {len(timeouts)}")
for r in timeouts:
    print(f"    Q{r['query_id']} L={r['level']} {r['latency_ms']/1000:.1f}s score={r['avg_score']} {r['query'][:50]}")

# ═══ TOOLS_USED ANALYSIS ═══
section("TOOLS_USED ANALYSIS")

te_pass = sum(1 for r in results if r["status"]=="PASS" and not r.get("tools_used"))
te_fail = sum(1 for r in results if r["status"]!="PASS" and not r.get("tools_used"))
tu_pass = sum(1 for r in results if r["status"]=="PASS" and r.get("tools_used"))
tu_fail = sum(1 for r in results if r["status"]!="PASS" and r.get("tools_used"))

print(f"  {'':20} {'tools=[]':>12} {'tools!=[]':>12}")
print(f"  {'PASS':<20} {te_pass:>12} {tu_pass:>12}")
print(f"  {'FAIL':<20} {te_fail:>12} {tu_fail:>12}")

all_tools_used = Counter()
for r in results:
    for t in r.get("tools_used", []):
        all_tools_used[t] += 1
if all_tools_used:
    print(f"\n  Tool usage frequency:")
    for tool, count in all_tools_used.most_common(10):
        print(f"    {tool}: {count}")
else:
    print(f"\n  WARNING: ALL queries have tools_used=[] — tool tracking may be broken!")

# ═══ SCORE DIMENSION HEATMAP ═══
section("SCORE DIMENSION AVERAGES BY LEVEL (all queries)")

dims = ["accuracy","completeness","relevance","safety","actionability","attribution","reasoning"]
print(f"  {'Level':<8}", end="")
for d in dims:
    print(f" {d[:7]:>8}", end="")
print(f" {'AVG':>7}")
hr("─", 80)

for level in levels_order:
    if level not in level_data: continue
    ld = level_data[level]
    print(f"  {level:<8}", end="")
    row = []
    for d in dims:
        vals = [r["scores"].get(d, 0) for r in ld]
        avg = sum(vals)/len(vals) if vals else 0
        row.append(avg)
        flag = "!" if avg < 2.0 else " " if avg < 3.0 else ""
        print(f" {avg:>7.2f}{flag}", end="")
    print(f" {sum(row)/len(row):>7.2f}")

print(f"\n  ! = critically low (<2.0)")

# ═══ ACTIONABLE RECOMMENDATIONS ═══
section("ACTIONABLE RECOMMENDATIONS — Ranked by Impact")

nm = len(near_miss_all)
aa = len(async_acks)
lq_count = len(low_quality)

print(f"""
  FIX #1: Fix async ack problem ({aa} queries)
    Return raw {{"ok":true,"runId":"..."}} instead of answers.
    Root cause: Gateway returning job ack, not waiting for completion.
    Fix: poll/stream for completion in eval harness, or use sync invocation.
    Impact: +{aa} queries get real responses -> potential +{aa//2} passes (est 50%)

  FIX #2: Fix attribution scores (biggest drag on near-misses)
    Attribution is the #1 drag dimension across near-misses.
    Add source citations: "Source: Market Data MCP", "Source: SOQL on IR_Coverage__c"
    Impact: Could flip many of the {nm} near-misses

  FIX #3: Fix hallucination/fabrication ({global_patterns.get('HALLUCINATION_FABRICATION', 0)} failures)
    Agent invents numbers when tools fail or aren't called.
    Guardrail: "If MCP tool returns no data, say so. Never invent prices/dates/names."
    Impact: Fixes accuracy scores across L1-L3

  FIX #4: Fix tool invocation ({global_patterns.get('TOOL_FAILURE_OR_NOT_USED', 0)} failures)
    Agent often doesn't call MCP tools or tools return errors.
    Ensure MCP servers healthy + agent instructions force tool use for data queries.
    Impact: Root cause behind hallucination + attribution issues

  FIX #5: Fix FinServ__FinancialAccount__c 500 errors
    Multiple L1-L2 queries fail because this SF object throws 500s.
    Check FLS permissions, object deployment, API access.
    Impact: Unblocks client portfolio/AUM/risk queries

  COMBINED REALISTIC IMPACT ESTIMATE:
    Fix #1 (async):          +{aa//2} passes (50% of {aa} async acks)
    Fix #2 (attribution):    +{nm//2} passes (50% of {nm} near-misses)
    Fix #3+4 (halluc+tools): +{int(lq_count*0.3)} passes (30% of {lq_count} low-quality)
    Optimistic new total:    ~{data['passed'] + aa//2 + nm//2 + int(lq_count*0.3)}/150 = {(data['passed'] + aa//2 + nm//2 + int(lq_count*0.3))/150*100:.0f}%
    (up from {data['pass_rate']}%)
""")

print("Done.")
