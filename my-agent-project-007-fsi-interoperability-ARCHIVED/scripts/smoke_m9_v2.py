"""Smoke test: M9 v2 router against real Bedrock.

Picks 5 sample utterances covering all specialist categories, runs each
through classify_intent_v2, and checks that the right category was chosen.

Run:
  python3 scripts/smoke_m9_v2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "m9-intent-router"))

from router_v2 import classify_intent_v2  # type: ignore


TESTS = [
    ("Prep me for my meeting with client CLT-0042 tomorrow",    "client"),
    ("Research Apple's latest 10-K and competitive position",   "research"),
    ("Buy 100 shares of AAPL for account 12345",                 "execution"),
    ("Is TSLA on the restricted trading list?",                  "compliance"),
    ("Start KYC onboarding for John Smith",                      "onboarding"),
]


def main() -> int:
    passes = 0
    failures = []
    for query, expected in TESTS:
        print(f"\n[q] {query}")
        result = classify_intent_v2(query)
        cat = result.intent.category.value
        conf = result.intent.confidence
        ms = result.processing_time_ms
        tag = "PASS" if cat == expected else "FAIL"
        print(f"  [{tag}] category={cat} (expected={expected}) "
              f"action={result.intent.action} conf={conf:.2f} "
              f"latency={ms:.0f}ms params={result.intent.parameters}")
        if cat == expected:
            passes += 1
        else:
            failures.append((query, cat, expected))

    print(f"\n{passes}/{len(TESTS)} correct")
    if failures:
        print("FAILURES:")
        for q, got, want in failures:
            print(f"  '{q[:60]}'  got={got} want={want}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
