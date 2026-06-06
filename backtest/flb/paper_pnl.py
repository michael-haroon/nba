"""
paper_pnl.py — Backtest each strategy on historical data.

Run:
    conda run -n pred python -m backtest.flb.paper_pnl
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.flb.config import STRATEGIES, OUTPUT_DIR, Strategy
from backtest.flb.data import load_trades, fetch_tipoff_times, add_hours_to_tipoff, first_entry_per_market

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def compute_pnl(entries: pd.DataFrame, strategy: Strategy) -> pd.DataFrame:
    """
    Compute per-market P&L for a strategy.

    Buy NO (fade): cost = 1 - yes_price, win if actual_win == 0
    Buy YES (back): cost = yes_price, win if actual_win == 1
    """
    entries = entries.copy()

    if strategy.side == "no":
        entries["cost"] = 1 - entries["yes_price"]
        entries["won"] = (entries["actual_win"] == 0).astype(int)
        entries["pnl"] = np.where(
            entries["actual_win"] == 0,
            entries["yes_price"],       # payoff when team loses
            -(1 - entries["yes_price"]) # loss when team wins
        )
    else:
        entries["cost"] = entries["yes_price"]
        entries["won"] = (entries["actual_win"] == 1).astype(int)
        entries["pnl"] = np.where(
            entries["actual_win"] == 1,
            1 - entries["yes_price"],   # payoff when team wins
            -entries["yes_price"]       # loss when team loses
        )

    entries["strategy"] = strategy.name
    return entries


def compute_metrics(pnl_series: pd.Series) -> dict:
    """Aggregate metrics from a P&L series (per-market, in dollars 0-1 scale)."""
    n = len(pnl_series)
    if n == 0:
        return {}

    wins = (pnl_series > 0).sum()
    cum_pnl = pnl_series.cumsum()
    peak = cum_pnl.cummax()
    drawdown = peak - cum_pnl
    max_dd = drawdown.max()

    avg = pnl_series.mean()
    std = pnl_series.std()
    sharpe = (avg / std) * np.sqrt(n) if std > 0 else 0.0

    return {
        "n_markets": n,
        "win_rate": wins / n,
        "avg_pnl_cents": avg * 100,
        "total_pnl_dollars": pnl_series.sum(),
        "sharpe": sharpe,
        "max_drawdown_dollars": max_dd,
    }


def run():
    log.info("=" * 70)
    log.info("PAPER P&L BACKTEST")
    log.info("=" * 70)

    # Load data
    df = load_trades()
    tipoff_map = fetch_tipoff_times()
    df = add_hours_to_tipoff(df, tipoff_map)

    # Run each strategy
    all_pnl = []
    summary_rows = []

    for strategy in STRATEGIES:
        log.info(f"\n--- {strategy.name} ---")
        log.info(f"  Time: {strategy.time_range}h | Price: {strategy.price_range} | Side: {strategy.side}")

        entries = first_entry_per_market(df, strategy)
        if entries.empty:
            log.info("  No qualifying trades")
            continue

        pnl_df = compute_pnl(entries, strategy)
        metrics = compute_metrics(pnl_df["pnl"])

        log.info(f"  N={metrics['n_markets']} | Win={metrics['win_rate']:.0%} | "
                 f"Avg={metrics['avg_pnl_cents']:+.1f}¢ | "
                 f"Total=${metrics['total_pnl_dollars']:+.2f} | "
                 f"Sharpe={metrics['sharpe']:.2f}")

        all_pnl.append(pnl_df)
        summary_rows.append({"strategy": strategy.name, **metrics})

    # Save results
    if all_pnl:
        combined = pd.concat(all_pnl, ignore_index=True)
        combined.to_csv(OUTPUT_DIR / "paper_pnl_detail.csv", index=False)

    if summary_rows:
        summary = pd.DataFrame(summary_rows)
        summary.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False)

        log.info("\n" + "=" * 70)
        log.info("STRATEGY COMPARISON")
        log.info("=" * 70)
        log.info(f"{'Strategy':<25} {'N':>5} {'Win%':>6} {'Avg¢':>7} {'Total$':>9} {'Sharpe':>7} {'MaxDD$':>8}")
        log.info("─" * 70)
        for _, row in summary.iterrows():
            log.info(
                f"{row['strategy']:<25} {int(row['n_markets']):>5} "
                f"{row['win_rate']:>5.0%} {row['avg_pnl_cents']:>+6.1f} "
                f"{row['total_pnl_dollars']:>+8.2f} {row['sharpe']:>7.2f} "
                f"{row['max_drawdown_dollars']:>8.3f}"
            )

    log.info("\nDone.")


if __name__ == "__main__":
    run()
