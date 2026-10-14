"""
Monte Carlo price simulation using Geometric Brownian Motion.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import numpy as np
from scipy import stats as _scipy_stats


def run_monte_carlo(
    current_price: float,
    annual_return: float,
    annual_volatility: float,
    days: int = 252,
    simulations: int = 500,
    seed: int | None = None,
) -> dict:
    """
    Simulate future stock price paths via Geometric Brownian Motion.

    Parameters
    ----------
    current_price : float
        Current stock price.
    annual_return : float
        Expected annualised return (e.g. 0.15 for 15 %).
    annual_volatility : float
        Historical annualised volatility (e.g. 0.45 for 45 %).
    days : int
        Number of trading days to simulate (default 252 ≈ 1 year).
    simulations : int
        Number of independent price paths (default 500).
    seed : int | None
        Random seed for reproducibility (default None — non-deterministic).

    Returns
    -------
    dict
        median_price, mean_price, p5, p25, p75, p95,
        distribution_stats, probability_above_current,
        probability_below_current, seed.
    """
    # ── Input validation ────────────────────────────────────────────
    if current_price <= 0:
        return _error("current_price must be positive")
    if annual_volatility < 0:
        return _error("annual_volatility cannot be negative")
    if days <= 0:
        return _error("days must be positive")
    if simulations <= 0:
        return _error("simulations must be positive")

    # Cap simulations to avoid sandbox memory issues
    simulations = min(simulations, 10_000)
    days = min(days, 2520)  # max ~10 years

    # ── GBM parameters ──────────────────────────────────────────────
    dt = 1.0 / 252.0  # one trading day
    drift = (annual_return - 0.5 * annual_volatility ** 2) * dt
    diffusion = annual_volatility * np.sqrt(dt)

    # ── Simulate paths ──────────────────────────────────────────────
    rng = np.random.default_rng(seed=seed)
    shocks = rng.normal(loc=drift, scale=diffusion, size=(simulations, days))
    log_paths = np.cumsum(shocks, axis=1)
    terminal_log_returns = log_paths[:, -1]
    terminal_prices = current_price * np.exp(terminal_log_returns)

    # ── Distribution statistics ─────────────────────────────────────
    p5 = float(np.percentile(terminal_prices, 5))
    p25 = float(np.percentile(terminal_prices, 25))
    median_price = float(np.median(terminal_prices))
    p75 = float(np.percentile(terminal_prices, 75))
    p95 = float(np.percentile(terminal_prices, 95))
    mean_price = float(np.mean(terminal_prices))
    std_price = float(np.std(terminal_prices))

    # Skewness and kurtosis via scipy (excess kurtosis by default)
    if std_price > 0:
        skew = float(_scipy_stats.skew(terminal_prices))
        kurtosis = float(_scipy_stats.kurtosis(terminal_prices))
    else:
        skew = 0.0
        kurtosis = 0.0

    prob_above = float(np.mean(terminal_prices > current_price))
    prob_below = float(np.mean(terminal_prices < current_price))

    return {
        "median_price": round(median_price, 2),
        "mean_price": round(mean_price, 2),
        "p5": round(p5, 2),
        "p25": round(p25, 2),
        "p75": round(p75, 2),
        "p95": round(p95, 2),
        "distribution_stats": {
            "std": round(std_price, 2),
            "skew": round(skew, 4),
            "kurtosis": round(kurtosis, 4),
        },
        "probability_above_current": round(prob_above, 4),
        "probability_below_current": round(prob_below, 4),
        "simulations_run": simulations,
        "days_simulated": days,
        "current_price": current_price,
        "seed": seed,
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    """Return a standardised error envelope."""
    return {"error": True, "message": msg}
