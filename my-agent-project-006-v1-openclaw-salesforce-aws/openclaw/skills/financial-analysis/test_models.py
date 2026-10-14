#!/usr/bin/env python3
"""
Phase 4 — Financial Model Integration Tests.

Tests each model (dcf, comps, monte_carlo, portfolio_impact, stress_test,
rebalance) with realistic FSI data and validates outputs.
"""

import math
import sys

# ── Helpers ─────────────────────────────────────────────────────────

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        msg = f"  ❌ {label}"
        if detail:
            msg += f"  — {detail}"
        print(msg)


def is_finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


# ═══ 1. DCF — NVDA ═══════════════════════════════════════════════
def test_dcf():
    print("\n═══ 1. DCF — NVDA ═══")
    from dcf import run_dcf

    result = run_dcf(
        revenue_ttm=60.0,
        revenue_growth_rates=[0.40, 0.30, 0.25, 0.20, 0.15],
        operating_margin=0.35, margin_expansion=0.01,
        tax_rate=0.12, capex_pct_revenue=0.08,
        wacc=0.10, terminal_growth=0.03,
        shares_outstanding=24.5, net_debt=-18.0,
    )
    check("No error key", "error" not in result)
    fv = result.get("fair_value_per_share")
    check("fair_value finite", is_finite(fv))
    check("fair_value > 0", fv is not None and fv > 0)
    check("fair_value $1-$2000", fv is not None and 1 < fv < 2000, f"got {fv}")
    ev = result.get("enterprise_value")
    check("enterprise_value finite", is_finite(ev))
    fcfs = result.get("fcf_projections", [])
    check("5 FCF projections", len(fcfs) == 5)
    for yr in fcfs:
        check(f"  Yr{yr['year']} FCF finite", is_finite(yr["fcf"]))
        check(f"  Yr{yr['year']} revenue finite", is_finite(yr["revenue"]))
    check("sensitivity_table present", bool(result.get("sensitivity_table")))
    check("methodology present", len(result.get("methodology", "")) > 20)
    print(f"\n  Fair value: ${fv}  |  EV: ${ev:.2f}B  |  Equity: ${result.get('equity_value',0):.2f}B")


# ═══ 2. Comps — NVDA vs Peers ════════════════════════════════════
def test_comps():
    print("\n═══ 2. Comps — NVDA vs Peers ═══")
    from comps import run_comps

    target_metrics = {
        "pe": 65.0, "ev_ebitda": 55.0, "ps": 35.0, "pb": 45.0,
        "ev_revenue": 30.0, "price": 178.0, "market_cap": 4360.0,
    }
    peer_data = [
        {"ticker": "AMD",  "name": "Advanced Micro Devices", "pe": 120.0, "ev_ebitda": 45.0, "ps": 10.0, "pb": 4.5,  "ev_revenue": 9.0,  "price": 160.0, "market_cap": 260.0},
        {"ticker": "AVGO", "name": "Broadcom Inc",           "pe": 35.0,  "ev_ebitda": 22.0, "ps": 15.0, "pb": 12.0, "ev_revenue": 14.0, "price": 180.0, "market_cap": 830.0},
        {"ticker": "INTC", "name": "Intel Corporation",      "pe": None,  "ev_ebitda": 18.0, "ps": 2.5,  "pb": 1.2,  "ev_revenue": 2.0,  "price": 30.0,  "market_cap": 128.0},
    ]
    result = run_comps(target_ticker="NVDA", target_metrics=target_metrics, peer_data=peer_data)

    check("No error key", "error" not in result)
    rv = result.get("relative_valuation", {})
    check("has pe", "pe" in rv)
    check("has ev_ebitda", "ev_ebitda" in rv)
    check("has ps", "ps" in rv)
    for metric, info in rv.items():
        prem = info.get("premium_pct")
        if prem is not None:
            check(f"  {metric} premium finite", is_finite(prem))
    ip = result.get("implied_prices", {})
    check("implied_prices present", bool(ip))
    composite = ip.get("composite_implied_price")
    if composite is not None:
        check("composite finite", is_finite(composite))
        check("composite > 0", composite > 0, f"got {composite}")
    check("sector_averages present", bool(result.get("sector_averages")))
    check("narrative non-empty", len(result.get("narrative", "")) > 20)
    print(f"\n  Composite implied: ${composite}  |  Narrative: {result.get('narrative','')[:100]}...")


# ═══ 3. Monte Carlo — NVDA ═══════════════════════════════════════
def test_monte_carlo():
    print("\n═══ 3. Monte Carlo — NVDA ═══")
    from monte_carlo import run_monte_carlo

    result = run_monte_carlo(
        current_price=178.0, annual_return=0.15, annual_volatility=0.45,
        days=252, simulations=500, seed=42,
    )
    check("No error key", "error" not in result)
    for key in ["median_price", "mean_price", "p5", "p25", "p75", "p95"]:
        v = result.get(key)
        check(f"{key} finite", is_finite(v))
        check(f"{key} > 0", v is not None and v > 0)
    check("p5 < p25 < median < p75 < p95",
          result["p5"] < result["p25"] < result["median_price"] < result["p75"] < result["p95"])
    pa = result.get("probability_above_current")
    pb = result.get("probability_below_current")
    check("prob_above in [0,1]", 0 <= pa <= 1)
    check("prob_below in [0,1]", 0 <= pb <= 1)
    check("prob_above + prob_below ≈ 1", abs(pa + pb - 1.0) < 0.05, f"got {pa+pb}")
    stats = result.get("distribution_stats", {})
    check("std > 0", is_finite(stats.get("std")) and stats["std"] > 0)
    check("skew finite", is_finite(stats.get("skew")))
    check("kurtosis finite", is_finite(stats.get("kurtosis")))
    check("simulations == 500", result.get("simulations_run") == 500)
    check("seed == 42", result.get("seed") == 42)
    print(f"\n  Median: ${result['median_price']}  |  5th-95th: ${result['p5']}—${result['p95']}  |  P(up): {pa:.1%}")


# ═══ 4. Portfolio Impact — NVDA -10% ═════════════════════════════
def test_portfolio_impact():
    print("\n═══ 4. Portfolio Impact — NVDA -10% ═══")
    from portfolio_impact import calculate_portfolio_impact

    holdings = [
        {"ticker": "NVDA", "shares": 5000, "cost_basis": 120.0, "current_price": 178.0, "client_name": "Henderson", "sector": "Technology"},
        {"ticker": "AAPL", "shares": 2000, "cost_basis": 150.0, "current_price": 195.0, "client_name": "Henderson", "sector": "Technology"},
        {"ticker": "JNJ",  "shares": 1000, "cost_basis": 155.0, "current_price": 160.0, "client_name": "Henderson", "sector": "Healthcare"},
        {"ticker": "NVDA", "shares": 1000, "cost_basis": 140.0, "current_price": 178.0, "client_name": "Patel",     "sector": "Technology"},
        {"ticker": "MSFT", "shares": 1500, "cost_basis": 300.0, "current_price": 420.0, "client_name": "Patel",     "sector": "Technology"},
        {"ticker": "BRK.B","shares": 500,  "cost_basis": 350.0, "current_price": 410.0, "client_name": "Patel",     "sector": "Financials"},
        {"ticker": "NVDA", "shares": 200,  "cost_basis": 160.0, "current_price": 178.0, "client_name": "Morrison",  "sector": "Technology"},
        {"ticker": "VTI",  "shares": 3000, "cost_basis": 200.0, "current_price": 260.0, "client_name": "Morrison",  "sector": "Diversified"},
    ]
    result = calculate_portfolio_impact(holdings=holdings, price_changes={"NVDA": -0.10})

    check("No error key", "error" not in result)
    pci = result.get("per_client_impact", [])
    check("3 clients", len(pci) == 3)
    for c in pci:
        check(f"  {c['client_name']} pnl finite", is_finite(c["pnl"]))
        check(f"  {c['client_name']} pnl <= 0", c["pnl"] <= 0, f"got {c['pnl']}")
    te = result.get("total_exposure", {})
    check("total_pnl < 0", te.get("total_pnl", 0) < 0)
    check("affected_clients == 3", result.get("affected_clients_count") == 3)
    henderson = next((c for c in pci if c["client_name"] == "Henderson"), None)
    morrison = next((c for c in pci if c["client_name"] == "Morrison"), None)
    if henderson and morrison:
        check("Henderson hit harder than Morrison", abs(henderson["pnl"]) > abs(morrison["pnl"]))
    print(f"\n  Total P&L: ${te.get('total_pnl',0):,.2f}")
    for c in pci:
        print(f"  {c['client_name']}: ${c['pnl']:,.2f} ({c['pct_change']:.2f}%)")


# ═══ 5. Stress Test — tech_crash ═════════════════════════════════
def test_stress_test():
    print("\n═══ 5. Stress Test — tech_crash ═══")
    from stress_test import run_stress_test, get_scenario

    scenario = get_scenario("tech_crash")
    check("tech_crash loaded", scenario is not None)
    holdings = [
        {"ticker": "NVDA", "shares": 3000, "current_price": 178.0, "sector": "Technology",             "client_name": "Henderson"},
        {"ticker": "AAPL", "shares": 2000, "current_price": 195.0, "sector": "Technology",             "client_name": "Henderson"},
        {"ticker": "GOOGL","shares": 500,  "current_price": 175.0, "sector": "Communication Services", "client_name": "Henderson"},
        {"ticker": "JNJ",  "shares": 1000, "current_price": 160.0, "sector": "Healthcare",             "client_name": "Henderson"},
        {"ticker": "MSFT", "shares": 1500, "current_price": 420.0, "sector": "Technology",             "client_name": "Patel"},
        {"ticker": "JPM",  "shares": 800,  "current_price": 200.0, "sector": "Financials",             "client_name": "Patel"},
        {"ticker": "XOM",  "shares": 1200, "current_price": 110.0, "sector": "Energy",                 "client_name": "Morrison"},
        {"ticker": "VTI",  "shares": 2000, "current_price": 260.0, "sector": "Diversified",            "client_name": "Morrison"},
    ]
    result = run_stress_test(holdings=holdings, scenario=scenario)

    check("No error key", "error" not in result)
    pcr = result.get("per_client_results", [])
    check("3 clients", len(pcr) == 3)
    for c in pcr:
        check(f"  {c['client_name']} drawdown finite", is_finite(c["drawdown_pct"]))
        check(f"  {c['client_name']} pnl finite", is_finite(c["pnl"]))
    tpi = result.get("total_portfolio_impact", {})
    check("total_drawdown < 0", tpi.get("total_drawdown_pct", 0) < 0)
    check("total_pnl < 0", tpi.get("total_pnl", 0) < 0)
    whc = result.get("worst_hit_clients", [])
    check("worst_hit non-empty", len(whc) > 0)
    check("Henderson worst hit", whc[0]["client_name"] == "Henderson" if whc else False,
          f"got {whc[0]['client_name']}" if whc else "empty")
    check("summary non-empty", len(result.get("scenario_summary", "")) > 20)
    print(f"\n  Drawdown: {tpi.get('total_drawdown_pct',0):.2f}%  |  P&L: ${tpi.get('total_pnl',0):,.2f}")
    if whc:
        print(f"  Worst: {whc[0]['client_name']} ({whc[0]['drawdown_pct']:.2f}%)")


# ═══ 6. Rebalance — 70/30 → 60/40 ═══════════════════════════════
def test_rebalance():
    print("\n═══ 6. Rebalance — 70/30 → 60/40 ═══")
    from rebalance import calculate_rebalance

    holdings = [
        {"ticker": "VTI",  "shares": 500,  "current_price": 260.0, "sector": "Equity"},
        {"ticker": "AAPL", "shares": 200,  "current_price": 195.0, "sector": "Equity"},
        {"ticker": "MSFT", "shares": 100,  "current_price": 420.0, "sector": "Equity"},
        {"ticker": "AGG",  "shares": 400,  "current_price": 100.0, "sector": "Fixed Income"},
        {"ticker": "BND",  "shares": 300,  "current_price": 73.0,  "sector": "Fixed Income"},
    ]
    total_value = sum(h["shares"] * h["current_price"] for h in holdings)
    result = calculate_rebalance(
        holdings=holdings,
        target_allocation={"Equity": 0.60, "Fixed Income": 0.40},
        total_portfolio_value=total_value,
    )

    check("No error key", "error" not in result)
    ca = result.get("current_allocation", {})
    check("has Equity", "Equity" in ca)
    check("has Fixed Income", "Fixed Income" in ca)
    eq_pct = ca.get("Equity", 0)
    check("Equity > 60% (drifted)", eq_pct > 0.60, f"got {eq_pct:.2%}")
    drift = result.get("drift", {})
    check("Equity drift > 0", drift.get("Equity", {}).get("drift_pct", 0) > 0)
    trades = result.get("trades", [])
    check("trades generated", len(trades) > 0)
    check("has SELL", any(t["action"] == "SELL" for t in trades))
    check("has BUY", any(t["action"] == "BUY" for t in trades))
    for t in trades:
        if t.get("shares") is not None:
            check(f"  {t['action']} {t['ticker']} shares>0", t["shares"] > 0)
            check(f"  {t['action']} {t['ticker']} value finite", is_finite(t["estimated_value"]))
    pra = result.get("post_rebalance_allocation", {})
    check("post Equity ≈ 60%", abs(pra.get("Equity", 0) - 60.0) < 2.0, f"got {pra.get('Equity',0):.1f}%")
    check("post FI ≈ 40%", abs(pra.get("Fixed Income", 0) - 40.0) < 2.0, f"got {pra.get('Fixed Income',0):.1f}%")
    check("commissions >= 0", result.get("estimated_commissions", 0) >= 0)
    print(f"\n  Current: Eq {eq_pct:.1%}, FI {ca.get('Fixed Income',0):.1%}")
    print(f"  Post:    Eq {pra.get('Equity',0):.1f}%, FI {pra.get('Fixed Income',0):.1f}%")
    print(f"  Trades: {len(trades)}, Commissions: ${result.get('estimated_commissions',0):.2f}")


# ═══ Main ════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 4 — Financial Model Integration Tests")
    print("=" * 60)

    for fn in [test_dcf, test_comps, test_monte_carlo, test_portfolio_impact, test_stress_test, test_rebalance]:
        try:
            fn()
        except Exception as e:
            FAIL += 1
            print(f"\n  💥 EXCEPTION in {fn.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"TOTAL: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)
