"""
visualize.py — Generate all research plots.

Run:
    conda run -n pred python -m backtest.flb.visualize
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.flb.config import STRATEGIES, OUTPUT_DIR, TIME_BINS, PRICE_BINS
from backtest.flb.data import (
    load_trades, fetch_tipoff_times, add_hours_to_tipoff,
    build_edge_grid, first_entry_per_market, assign_time_bin, assign_price_bin,
)
from backtest.flb.paper_pnl import compute_pnl, compute_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


# ── 1. Edge Heatmap ──────────────────────────────────────────────────────────

def plot_heatmap(grid: pd.DataFrame):
    """Heatmap: time_bin × price_bin → edge in cents."""
    time_order = [t[0] for t in TIME_BINS]
    price_order = [p[0] for p in PRICE_BINS]

    pivot = grid.pivot_table(
        index="time_bin", columns="price_bin", values="edge_cents", aggfunc="mean"
    )
    # Reindex to ensure correct order
    pivot = pivot.reindex(index=time_order, columns=price_order)

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1f",
        cmap="RdBu_r",
        center=0,
        vmin=-15,
        vmax=15,
        ax=ax,
        cbar_kws={"label": "Edge (cents per contract)"},
        linewidths=0.5,
    )
    ax.set_title("Kalshi NBA Game Winner: Bias by Time to Tipoff x Implied Probability\n"
                 "(+) = underdog underpriced / (-) = favorite overpriced", fontsize=11)
    ax.set_xlabel("Implied Probability Bin")
    ax.set_ylabel("Time to Tipoff")
    plt.tight_layout()

    path = OUTPUT_DIR / "bias_heatmap.png"
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"Saved: {path}")


# ── 2. Calibration Curves ────────────────────────────────────────────────────

def plot_calibration_curves(df: pd.DataFrame):
    """Actual vs implied probability, one panel per time window."""
    valid = df[(df["hours_to_tipoff"].notna()) & (df["hours_to_tipoff"] > 0)].copy()
    valid["time_bin"] = valid["hours_to_tipoff"].apply(assign_time_bin)
    valid = valid.dropna(subset=["time_bin"])

    time_windows = [">48h", "24-48h", "6-24h", "1-3h", "30m-1h"]
    fig, axes = plt.subplots(1, len(time_windows), figsize=(20, 4), sharey=True)

    for ax, t_label in zip(axes, time_windows):
        subset = valid[valid["time_bin"] == t_label]
        if subset.empty:
            ax.set_title(t_label)
            continue

        bins = pd.cut(subset["yes_price"], bins=10)
        grouped = subset.groupby(bins, observed=True).agg(
            implied=("yes_price", "mean"),
            actual=("actual_win", "mean"),
            n=("actual_win", "count"),
        ).reset_index()
        grouped = grouped[grouped["n"] >= 100]

        ax.plot([0, 1], [0, 1], "k--", alpha=0.3, linewidth=1)
        ax.scatter(grouped["implied"], grouped["actual"],
                   s=np.clip(grouped["n"] / 500, 10, 100), alpha=0.7, color="steelblue")
        ax.plot(grouped["implied"], grouped["actual"], "b-", alpha=0.7)

        # Error bars
        se = np.sqrt(grouped["actual"] * (1 - grouped["actual"]) / grouped["n"])
        ax.fill_between(grouped["implied"],
                        grouped["actual"] - 1.96 * se,
                        grouped["actual"] + 1.96 * se,
                        alpha=0.15, color="steelblue")

        ax.set_title(t_label, fontsize=11)
        ax.set_xlabel("Implied Prob")
        if ax == axes[0]:
            ax.set_ylabel("Actual Win Rate")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")

    plt.suptitle("Calibration Curves by Time to Tipoff (shaded = 95% CI)", fontsize=12, y=1.02)
    plt.tight_layout()
    path = OUTPUT_DIR / "calibration_curves.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Saved: {path}")


# ── 3. Equity Curves ─────────────────────────────────────────────────────────

def plot_equity_curves(df: pd.DataFrame):
    """Cumulative P&L per strategy."""
    fig, ax = plt.subplots(figsize=(12, 6))
    has_data = False

    for strategy in STRATEGIES:
        entries = first_entry_per_market(df, strategy)
        if entries.empty:
            continue

        pnl_df = compute_pnl(entries, strategy)
        pnl_df = pnl_df.sort_values("trade_time")
        cum_pnl = pnl_df["pnl"].cumsum()
        metrics = compute_metrics(pnl_df["pnl"])

        label = f"{strategy.name} (Sharpe={metrics['sharpe']:.2f}, N={metrics['n_markets']})"
        ax.plot(range(len(cum_pnl)), cum_pnl.values, linewidth=1.5, label=label)
        has_data = True

    if has_data:
        ax.axhline(0, color="gray", linestyle="--", alpha=0.5)
        ax.set_xlabel("Trade # (chronological)")
        ax.set_ylabel("Cumulative P&L ($)")
        ax.set_title("Paper P&L Equity Curves by Strategy")
        ax.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    path = OUTPUT_DIR / "equity_curves.png"
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"Saved: {path}")


# ── 4. Edge Distributions ────────────────────────────────────────────────────

def plot_edge_distributions(df: pd.DataFrame):
    """Box plots of per-market PnL by time window for the best strategy."""
    strategy = STRATEGIES[0]  # fade_heavy_fav_early
    entries = first_entry_per_market(df, strategy)
    if entries.empty:
        return

    pnl_df = compute_pnl(entries, strategy)
    pnl_df["time_bin"] = pnl_df["hours_to_tipoff"].apply(assign_time_bin)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Box plot by time bin
    time_order = [t[0] for t in TIME_BINS if t[0] in pnl_df["time_bin"].values]
    if time_order:
        sns.boxplot(data=pnl_df, x="time_bin", y="pnl", order=time_order, ax=ax1)
        ax1.axhline(0, color="red", linestyle="--", alpha=0.5)
        ax1.set_title(f"P&L Distribution: {strategy.name}")
        ax1.set_xlabel("Time to Tipoff")
        ax1.set_ylabel("P&L per contract ($)")
        ax1.tick_params(axis="x", rotation=30)

    # Histogram of all P&L
    ax2.hist(pnl_df["pnl"], bins=30, edgecolor="black", alpha=0.7, color="steelblue")
    ax2.axvline(0, color="red", linestyle="--", alpha=0.7)
    ax2.axvline(pnl_df["pnl"].mean(), color="green", linestyle="-", linewidth=2,
                label=f"Mean = {pnl_df['pnl'].mean()*100:.1f}¢")
    ax2.set_title(f"P&L Histogram: {strategy.name}")
    ax2.set_xlabel("P&L per contract ($)")
    ax2.set_ylabel("Count")
    ax2.legend()

    plt.tight_layout()
    path = OUTPUT_DIR / "edge_distributions.png"
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"Saved: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=" * 70)
    log.info("GENERATING VISUALIZATIONS")
    log.info("=" * 70)

    df = load_trades()
    tipoff_map = fetch_tipoff_times()
    df = add_hours_to_tipoff(df, tipoff_map)

    log.info("\n[1] Edge heatmap...")
    grid = build_edge_grid(df)
    plot_heatmap(grid)

    log.info("\n[2] Calibration curves...")
    plot_calibration_curves(df)

    log.info("\n[3] Equity curves...")
    plot_equity_curves(df)

    log.info("\n[4] Edge distributions...")
    plot_edge_distributions(df)

    log.info(f"\nAll plots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    run()
