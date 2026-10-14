"""
Performance Tests — Shared Fixtures.

Provides:
  - Realistic payload generators (client data, holdings, research briefs)
  - Timer context manager for nanosecond-precision latency measurement
  - Percentile calculator (p50, p95, p99)
  - importlib-based package registration for M6, M2/M4, M9

No external benchmarking libraries — just pytest + time.
"""

from __future__ import annotations

import importlib
import math
import random
import string
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest

# ── Project paths ────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "src"


# ── importlib package registration (hyphenated dirs) ─────────────

def _register_package(dir_name: str, pkg_name: str, submodules: list[str]) -> None:
    """Register a hyphenated source directory as an importable package."""
    pkg_dir = _SRC / dir_name
    if pkg_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg_name] = mod
        spec.loader.exec_module(mod)

    for submod in submodules:
        full = f"{pkg_name}.{submod}"
        if full not in sys.modules:
            sub_spec = importlib.util.spec_from_file_location(
                full,
                pkg_dir / f"{submod}.py",
                submodule_search_locations=[str(pkg_dir)],
            )
            sub_mod = importlib.util.module_from_spec(sub_spec)
            sys.modules[full] = sub_mod
            sub_spec.loader.exec_module(sub_mod)


# Register M6 (leakage_scan, models)
_register_package("m6-mcp-gateway", "m6_mcp_gateway", ["models", "leakage_scan"])

# Register M2/M4 (models, policy_client)
_register_package("m2-m4-policy-engine", "m2_m4_policy_engine", ["models", "policy_client"])

# Register M9 — needs models on sys.path first (M9 uses bare `from models import`)
_m9_dir = _SRC / "m9-intent-router"
if str(_m9_dir) not in sys.path:
    sys.path.insert(0, str(_m9_dir))


# ── Timer context manager (nanosecond precision) ─────────────────


@contextmanager
def perf_timer() -> Generator[dict[str, float], None, None]:
    """
    Context manager that records elapsed time in nanoseconds.

    Usage:
        with perf_timer() as t:
            do_work()
        elapsed_ns = t["elapsed_ns"]
        elapsed_ms = t["elapsed_ms"]
    """
    result: dict[str, float] = {}
    start = time.perf_counter_ns()
    yield result
    end = time.perf_counter_ns()
    result["elapsed_ns"] = end - start
    result["elapsed_ms"] = (end - start) / 1_000_000


# ── Percentile calculator ────────────────────────────────────────


def percentile(latencies: list[float], p: float) -> float:
    """
    Calculate the p-th percentile from a sorted list of latencies.

    Args:
        latencies: List of latency values (will be sorted internally).
        p: Percentile (0-100), e.g. 50, 95, 99.

    Returns:
        The p-th percentile value.
    """
    if not latencies:
        return 0.0
    sorted_vals = sorted(latencies)
    k = (p / 100.0) * (len(sorted_vals) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def print_latency_stats(name: str, latencies_ms: list[float]) -> None:
    """Print p50/p95/p99/max stats for CI capture."""
    p50 = percentile(latencies_ms, 50)
    p95 = percentile(latencies_ms, 95)
    p99 = percentile(latencies_ms, 99)
    mx = max(latencies_ms) if latencies_ms else 0.0
    print(f"\n[PERF] {name}:")
    print(f"  p50={p50:.3f}ms  p95={p95:.3f}ms  p99={p99:.3f}ms  max={mx:.3f}ms")
    print(f"  samples={len(latencies_ms)}")


# ── Realistic payload generators ─────────────────────────────────


def _random_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters, k=length))


def _random_dollar() -> str:
    return f"${random.randint(1000, 9999999):,.2f}"


@pytest.fixture
def client_data_payload() -> dict[str, Any]:
    """Realistic client data payload with 50+ fields (nested JSON)."""
    return _generate_client_payload()


@pytest.fixture
def large_payload_100kb() -> dict[str, Any]:
    """~100KB payload for large-payload stress tests."""
    return _generate_large_payload()


@pytest.fixture
def payload_with_ssn() -> dict[str, Any]:
    """Payload containing SSN patterns for detection tests."""
    payload = _generate_client_payload()
    payload["personal"]["ssn"] = "123-45-6789"
    payload["personal"]["backup_ssn"] = "987-65-4321"
    return payload


@pytest.fixture
def payload_with_dob() -> dict[str, Any]:
    """Payload containing DOB patterns for detection tests."""
    payload = _generate_client_payload()
    payload["personal"]["date_of_birth"] = "03/15/1985"
    payload["personal"]["spouse_dob"] = "1990-07-22"
    return payload


def _generate_client_payload() -> dict[str, Any]:
    """
    Generate a realistic nested client payload with 50+ fields.

    IMPORTANT: Values must NOT trigger the Layer A regex scanner.
    Use alphanumeric IDs (not pure digit sequences) to avoid false
    positives on SSN, account_number, and routing_number patterns.
    """
    holdings = []
    for i in range(15):
        holdings.append({
            "security_id": f"SEC-{i:04d}",
            "ticker": _random_string(4).upper(),
            "cusip": f"CUSIP-{_random_string(6).upper()}",
            "name": f"{_random_string(8)} Corp",
            "quantity_shares": f"{random.randint(10, 10000)} shares",
            "market_value": _random_dollar(),
            "cost_basis": _random_dollar(),
            "cost_basis_method": random.choice(["FIFO", "LIFO", "AVG", "SPEC_ID"]),
            "unrealized_gain": _random_dollar(),
            "asset_class": random.choice(["equity", "fixed_income", "alternatives"]),
            "sector": random.choice(["tech", "healthcare", "financials", "energy"]),
        })

    return {
        "client_id": f"CLT-{_random_string(5).upper()}",
        "household_id": f"HH-{_random_string(4).upper()}",
        "personal": {
            "first_name": _random_string(6),
            "last_name": _random_string(8),
            "email": f"{_random_string(5)}@example.com",
            "phone": f"five-five-five-{_random_string(4)}",
            "address": {
                "street": f"{_random_string(3)} {_random_string(8)} St",
                "city": _random_string(7),
                "state": random.choice(["NY", "CA", "TX", "FL", "IL"]),
                "zip": f"ZIP-{_random_string(5)}",
            },
            "risk_tolerance": random.choice(["conservative", "moderate", "aggressive"]),
            "investment_objective": random.choice(["growth", "income", "preservation"]),
        },
        "accounts": [
            {
                "account_id": f"ACC-{_random_string(6).upper()}",
                "account_type": random.choice(["individual", "joint", "ira", "trust"]),
                "custodian": random.choice(["schwab", "fidelity", "pershing"]),
                "total_value": _random_dollar(),
                "cash_balance": _random_dollar(),
                "margin_enabled": random.choice([True, False]),
            }
            for _ in range(3)
        ],
        "holdings": holdings,
        "performance": {
            "ytd_return": f"{random.uniform(-10, 30):.1f} percent",
            "one_year_return": f"{random.uniform(-15, 40):.1f} percent",
            "three_year_annualized": f"{random.uniform(-5, 25):.1f} percent",
            "inception_return": f"{random.uniform(0, 200):.1f} percent",
            "benchmark": "S and P five hundred",
            "alpha": f"{random.uniform(-3, 5):.1f} percent",
            "sharpe_ratio": f"ratio {random.uniform(0.2, 2.5):.2f}",
        },
        "compliance": {
            "kyc_status": "verified",
            "aml_status": "clear",
            "last_review_date": "reviewed Nov fifteen twenty-four",
            "next_review_date": "review May fifteen twenty-five",
            "restricted_securities": [],
            "concentration_limits": {"single_security": "ten percent", "single_sector": "twenty-five percent"},
        },
        "metadata": {
            "created_at": "created March twenty-twenty",
            "updated_at": "updated Jan twenty-five",
            "source_system": "salesforce_fsc",
            "canonical_version": "one-zero-zero",
        },
    }


def _generate_large_payload() -> dict[str, Any]:
    """
    Generate a ~100KB payload with many nested fields.

    Uses alphanumeric IDs and text-based values to avoid triggering
    the Layer A regex scanner (same as _generate_client_payload).
    """
    research_notes = []
    for i in range(80):
        research_notes.append({
            "note_id": f"NOTE-{_random_string(6).upper()}",
            "analyst": _random_string(12),
            "date": f"written {_random_string(8)}",
            "ticker": _random_string(4).upper(),
            "rating": random.choice(["buy_rating", "hold_rating", "sell_rating", "strong_buy_rating"]),
            "target_price": _random_dollar(),
            "summary": " ".join(_random_string(10) for _ in range(50)),
            "key_risks": [" ".join(_random_string(8) for _ in range(6)) for _ in range(5)],
            "catalysts": [" ".join(_random_string(8) for _ in range(4)) for _ in range(4)],
            "financial_data": {
                "revenue": _random_dollar(),
                "ebitda": _random_dollar(),
                "net_income": _random_dollar(),
                "eps": _random_dollar(),
                "pe_ratio": f"ratio {random.uniform(5, 50):.1f}",
                "debt_to_equity": f"ratio {random.uniform(0.1, 3.0):.2f}",
            },
        })

    base = _generate_client_payload()
    base["research_notes"] = research_notes
    base["transaction_history"] = [
        {
            "tx_id": f"TX-{_random_string(8).upper()}",
            "date": f"traded {_random_string(8)}",
            "type": random.choice(["purchase", "sale", "dividend_payment", "transfer_in"]),
            "ticker": _random_string(4).upper(),
            "quantity_desc": f"{random.randint(1, 5000)} shares traded",
            "price": _random_dollar(),
            "total": _random_dollar(),
            "settlement_note": f"settled {_random_string(10)}",
        }
        for i in range(150)
    ]
    return base
