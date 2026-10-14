---
name: Financial Analysis
slug: financial-analysis
version: 1.0.0
trigger-keywords:
  - dcf
  - fair value
  - valuation
  - comps
  - monte carlo
  - stress test
  - portfolio impact
  - rebalance
applicable-stages: [10, 11, 12, 13, 14]
---

# Financial Analysis Skill

Financial modeling toolkit for equity research and wealth advisory workflows.
Provides DCF valuation, comparable company analysis, Monte Carlo simulation,
portfolio impact analysis, stress testing, and rebalancing calculations.

> **Sandbox constraint:** All modules run inside OpenClaw's Python sandbox.
> Only `math`, `random`, `json`, `csv`, `numpy`, `pandas`, and `scipy` may be
> imported. No external API calls — every function receives its data as
> parameters (already fetched by upstream MCP servers).

---

## Modules

### 1. `dcf.py` — Discounted Cash Flow

**Function:** `run_dcf(...) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `revenue_ttm` | `float` | Trailing 12-month revenue (billions) |
| `revenue_growth_rates` | `list[float]` | Projected growth rates for next 5 years |
| `operating_margin` | `float` | Current operating margin (e.g. 0.35) |
| `margin_expansion` | `float` | Annual margin improvement (e.g. 0.01) |
| `tax_rate` | `float` | Effective tax rate (e.g. 0.21) |
| `capex_pct_revenue` | `float` | CapEx as % of revenue (e.g. 0.08) |
| `wacc` | `float` | Weighted average cost of capital (e.g. 0.10) |
| `terminal_growth` | `float` | Terminal growth rate (e.g. 0.03) |
| `shares_outstanding` | `float` | Shares outstanding (billions) |
| `net_debt` | `float` | Net debt (billions; debt minus cash) |

**Returns:**

| Key | Type | Description |
|---|---|---|
| `fair_value_per_share` | `float` | Implied share price |
| `enterprise_value` | `float` | Total enterprise value (billions) |
| `equity_value` | `float` | Equity value (billions) |
| `fcf_projections` | `list[dict]` | Year-by-year FCF breakdown |
| `sensitivity_table` | `dict` | WACC vs terminal-growth matrix |
| `methodology` | `str` | Notes on assumptions used |

---

### 2. `comps.py` — Comparable Company Analysis

**Function:** `run_comps(target_ticker, target_metrics, peer_data) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `target_ticker` | `str` | Ticker of the target company |
| `target_metrics` | `dict` | `{pe, ev_ebitda, ps, price, market_cap, ...}` |
| `peer_data` | `list[dict]` | List of peer dicts with same metric keys |

**Returns:**

| Key | Type | Description |
|---|---|---|
| `relative_valuation` | `dict` | Premium/discount vs peers per metric |
| `peer_ranking` | `list[dict]` | Peers ranked by each metric |
| `implied_prices` | `dict` | Implied prices from peer median multiples |
| `sector_averages` | `dict` | Mean and median of each metric |
| `narrative` | `str` | Human-readable summary |

---

### 3. `monte_carlo.py` — Monte Carlo Price Simulation

**Function:** `run_monte_carlo(current_price, annual_return, annual_volatility, days, simulations) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `current_price` | `float` | Current stock price |
| `annual_return` | `float` | Expected annual return (e.g. 0.15) |
| `annual_volatility` | `float` | Historical volatility (e.g. 0.45) |
| `days` | `int` | Trading days to simulate (default 252) |
| `simulations` | `int` | Number of paths (default 500) |

**Returns:**

| Key | Type | Description |
|---|---|---|
| `median_price` | `float` | Median terminal price |
| `mean_price` | `float` | Mean terminal price |
| `p5` | `float` | 5th percentile |
| `p25` | `float` | 25th percentile |
| `p75` | `float` | 75th percentile |
| `p95` | `float` | 95th percentile |
| `distribution_stats` | `dict` | std, skew, kurtosis |
| `probability_above_current` | `float` | P(terminal > current) |
| `probability_below_current` | `float` | P(terminal < current) |

---

### 4. `portfolio_impact.py` — Portfolio Impact Calculator

**Function:** `calculate_portfolio_impact(holdings, price_changes, concentration_limit, sector_limit) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `holdings` | `list[dict]` | `[{ticker, shares, cost_basis, current_price, client_name, sector}, ...]` |
| `price_changes` | `dict` | `{ticker: pct_change}` |
| `concentration_limit` | `float` | Single-stock limit (default 0.10) |
| `sector_limit` | `float` | Sector limit (default 0.25) |

**Returns:**

| Key | Type | Description |
|---|---|---|
| `per_client_impact` | `list[dict]` | Per-client P&L and % change |
| `concentration_violations` | `list[dict]` | Clients exceeding limits |
| `sector_exposure` | `dict` | Sector-level exposure summary |
| `total_exposure` | `dict` | Aggregate portfolio stats |
| `affected_clients_count` | `int` | Number of affected clients |

---

### 5. `stress_test.py` — Scenario Stress Testing

**Function:** `run_stress_test(holdings, scenario) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `holdings` | `list[dict]` | `[{ticker, shares, current_price, sector, client_name}, ...]` |
| `scenario` | `dict` | `{name, sector_shocks: {sector: pct}, market_shock}` |

Pre-built scenarios: `tech_crash`, `rate_hike`, `oil_spike`, `recession`, `black_swan`.

**Returns:**

| Key | Type | Description |
|---|---|---|
| `per_client_results` | `list[dict]` | Per-client current vs stressed value |
| `worst_hit_clients` | `list[dict]` | Top 5 worst drawdowns |
| `total_portfolio_impact` | `dict` | Aggregate drawdown stats |
| `scenario_summary` | `str` | Human-readable summary |

---

### 6. `rebalance.py` — Portfolio Rebalancing Calculator

**Function:** `calculate_rebalance(holdings, target_allocation, total_portfolio_value) -> dict`

| Parameter | Type | Description |
|---|---|---|
| `holdings` | `list[dict]` | `[{ticker, shares, current_price, sector}, ...]` |
| `target_allocation` | `dict` | `{sector: target_pct}` |
| `total_portfolio_value` | `float` | Total portfolio value |

**Returns:**

| Key | Type | Description |
|---|---|---|
| `current_allocation` | `dict` | Current sector weights |
| `drift` | `dict` | Difference from target per sector |
| `trades` | `list[dict]` | Suggested trades (ticker, action, shares, value) |
| `post_rebalance_allocation` | `dict` | Projected weights after trades |
| `estimated_commissions` | `float` | Estimated trading cost |
