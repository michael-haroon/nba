"""Per-season accuracy for all trained ensemble targets.

Loads ensemble_oof.csv for each target, attaches season (from stored column
or best-effort positional reconstruction), computes per-season MAE/accuracy,
applies exponential recency weighting, and saves a multi-panel plot.

Usage:
    python -m strategy.plot_season_accuracy                 # all targets
    python -m strategy.plot_season_accuracy --target spread # one target
    python -m strategy.plot_season_accuracy --no-weight     # unweighted only
"""

import argparse
import logging
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import log_loss

import strategy.config as _cfg
from strategy.config import SKIP_SEASONS

logger = logging.getLogger(__name__)

_TARGETS = ["winner", "spread", "h1_spread", "h2_spread", "h1_total", "h2_total", "total", "home_wins_h1"]

_TASK = {
    "winner": "clf",
    "spread": "reg",
    "h1_spread": "reg",
    "h2_spread": "reg",
    "h1_total": "reg",
    "h2_total": "reg",
    "total": "reg",
    "home_wins_h1": "clf",
}

_TARGET_COL = {
    "winner": "target_winner",
    "spread": "target_spread",
    "h1_spread": "target_h1_spread",
    "h2_spread": "target_h2_spread",
    "h1_total": "target_h1_total",
    "h2_total": "target_h2_total",
    "total": "target_total",
    "home_wins_h1": "target_home_wins_h1",
}

_LABELS = {
    "winner": "Winner (Direction Accuracy %)",
    "spread": "Spread (Direction Accuracy %)",
    "h1_spread": "H1 Spread (Direction Accuracy %)",
    "h2_spread": "H2 Spread (Direction Accuracy %)",
    "h1_total": "H1 Total (O/U Accuracy %)",
    "h2_total": "H2 Total (O/U Accuracy %)",
    "total": "Total (O/U Accuracy %)",
    "home_wins_h1": "Home Wins H1 (Accuracy %)",
}


def _oof_path(target: str) -> pathlib.Path:
    # New path uses ensemble_oof.csv; legacy path uses {target}_ensemble_oof.csv
    new_path = _cfg.OUTPUT_DIR / target / "ensemble_oof.csv"
    legacy_path = _cfg.OUTPUT_DIR / target / f"{target}_ensemble_oof.csv"
    if new_path.exists():
        return new_path
    if legacy_path.exists():
        return legacy_path
    return new_path  # will raise on load if missing


def _load_parquet_seasons(target: str) -> pd.Series:
    df = pd.read_parquet(_cfg.GAME_PARQUET)
    target_col = _TARGET_COL[target]
    valid = df[target_col].notna() & ~df["season"].isin(SKIP_SEASONS)
    return df[valid]["season"].reset_index(drop=True)


def _attach_season(oof: pd.DataFrame, target: str) -> pd.DataFrame:
    if "season" in oof.columns:
        return oof

    # Best-effort positional reconstruction
    parquet_seasons = _load_parquet_seasons(target)
    n_oof = len(oof)
    n_par = len(parquet_seasons)
    if n_oof > n_par:
        # extend by repeating the last season (accounts for the common_mask +1 row)
        extra = pd.Series([parquet_seasons.iloc[-1]] * (n_oof - n_par))
        parquet_seasons = pd.concat([parquet_seasons, extra], ignore_index=True)
    oof = oof.copy()
    oof["season"] = parquet_seasons.values[:n_oof]
    logger.warning(
        "%s: no season column in OOF — positional reconstruction used (re-run ensemble to fix)",
        target,
    )
    return oof


def _pred_col(oof: pd.DataFrame) -> str:
    for c in ("pred_ensemble", "y_pred_ensemble"):
        if c in oof.columns:
            return c
    # fallback: average all pred_* columns
    pred_cols = [c for c in oof.columns if c.startswith("pred_")]
    if pred_cols:
        return pred_cols[0]
    raise ValueError("No prediction column found in OOF CSV")


def _season_metrics(group: pd.DataFrame, task: str, target: str, ou_line: float = 0.0) -> tuple[float, float | None]:
    """Return (accuracy_pct, nMAE).

    Classification: fraction predicted correctly (yhat>0.5 vs y==1).
    Spread regression: direction accuracy (sign(ŷ) == sign(y), line=0).
    Total regression: O/U accuracy at ou_line (global OOF median of y_true).
    nMAE is only used for the secondary axis overlay; None for classification.
    """
    y = group["y_true"].values
    yhat = group["pred"].values
    mae = float(np.mean(np.abs(y - yhat)))
    std_y = float(np.std(y))
    nmae = mae / std_y if std_y > 0 else np.nan

    if task == "clf":
        return float(np.mean((yhat > 0.5) == y)) * 100, None

    if target in ("spread", "h1_spread", "h2_spread"):
        acc = float(np.mean(np.sign(yhat) == np.sign(y))) * 100
    else:
        acc = float(np.mean((yhat > ou_line) == (y > ou_line))) * 100
    return acc, nmae


def _recency_weights(seasons: list, lam: float = 0.15) -> np.ndarray:
    """Exponential recency weights: w_i = exp(lam * i) normalised."""
    idx = np.arange(len(seasons), dtype=float)
    w = np.exp(lam * idx)
    return w / w.sum()


def load_target(target: str) -> tuple[pd.DataFrame, str]:
    """Return (oof_with_season, pred_col_name). Raises if file missing."""
    path = _oof_path(target)
    oof = pd.read_csv(path)
    oof = _attach_season(oof, target)
    pred_col = _pred_col(oof)
    return oof, pred_col


def compute_season_stats(target: str, lam: float = 0.15, recent_seasons: int | None = None) -> dict:
    oof, pred_col = load_target(target)
    task = _TASK[target]
    oof = oof.rename(columns={pred_col: "pred"})

    if recent_seasons and "season" in oof.columns:
        all_s = sorted(oof["season"].dropna().unique())
        keep = set(all_s[-recent_seasons:])
        oof = oof[oof["season"].isin(keep)].reset_index(drop=True)

    # For total targets: use global OOF y_true median as the O/U line
    # This approximates a season-neutral market line without look-ahead bias
    ou_line = float(oof["y_true"].median()) if task == "reg" and target not in ("spread", "h1_spread", "h2_spread") else 0.0

    rows = (
        oof.groupby("season", sort=True)
        .apply(lambda g: pd.Series(_season_metrics(g, task, target, ou_line), index=["metric", "nmae"]), include_groups=False)
        .reset_index()
    )
    seasons = rows["season"].tolist()

    weights = _recency_weights(seasons, lam=lam)
    weighted_metric = float(np.dot(rows["metric"].values, weights))
    unweighted_metric = float(rows["metric"].mean())

    return {
        "target": target,
        "task": task,
        "per_season": rows,
        "seasons": seasons,
        "weights": weights,
        "weighted": weighted_metric,
        "unweighted": unweighted_metric,
        "n_rows": len(oof),
        "ou_line": ou_line,
    }


def plot_all(stats_list: list, lam: float, out_path: pathlib.Path) -> None:
    n = len(stats_list)
    ncols = 2
    nrows = (n + 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.5 * nrows))
    axes = axes.flatten()

    for i, stats in enumerate(stats_list):
        ax = axes[i]
        target = stats["target"]
        task = stats["task"]
        per_season = stats["per_season"]
        seasons = stats["seasons"]
        weights = stats["weights"]

        x = np.arange(len(seasons))
        values = per_season["metric"].values  # already in % for all tasks

        bars = ax.bar(x, values, alpha=0.7, width=0.7, label="Per-season Acc %")

        # Colour bars by recency weight (darker = more weight)
        norm_w = (weights - weights.min()) / (weights.max() - weights.min() + 1e-9)
        for bar, nw in zip(bars, norm_w):
            bar.set_facecolor(plt.cm.Blues(0.3 + 0.6 * nw))

        weighted_val = stats["weighted"]
        unweighted_val = stats["unweighted"]
        ax.axhline(weighted_val, color="red", lw=1.5, ls="--", label=f"Weighted: {weighted_val:.1f}%")
        ax.axhline(unweighted_val, color="gray", lw=1.0, ls=":", label=f"Unweighted: {unweighted_val:.1f}%")

        ax.set_title(_LABELS[target], fontsize=11, fontweight="bold")
        ax.set_xticks(x[::3])
        ax.set_xticklabels(seasons[::3], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Accuracy %", fontsize=9)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)

        # Overlay nMAE as a line on twin axis for regression targets
        if task == "reg" and per_season["nmae"].notna().any():
            nmae = per_season["nmae"].values
            ax2 = ax.twinx()
            ax2.plot(x, nmae, color="darkorange", lw=1.5, marker="o", markersize=2,
                     alpha=0.85, label="nMAE = MAE / σ(y)")
            ax2.set_ylabel("nMAE (normalised)", fontsize=8, color="darkorange")
            ax2.tick_params(axis="y", labelcolor="darkorange", labelsize=7)
            # Flat nMAE = model keeping pace with game variance; rising = true degradation
            ax2.axhline(np.nanmean(nmae), color="darkorange", lw=1.0, ls=":", alpha=0.6)
            lines2, labels2 = ax2.get_legend_handles_labels()
            lines1, labels1 = ax.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")
        else:
            ax.legend(fontsize=8, loc="upper right")

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(
        f"Per-Season Accuracy  |  spreads=direction, totals=O/U, orange line=nMAE/σ(y)  (λ={lam})",
        fontsize=12,
        fontweight="bold",
        y=1.01,
    )
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved: %s", out_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Per-season ensemble accuracy plots")
    parser.add_argument(
        "--target",
        choices=_TARGETS + ["all"],
        default="all",
        help="Target to plot (default: all)",
    )
    parser.add_argument(
        "--lam",
        type=float,
        default=0.15,
        help="Exponential recency decay (default 0.15). Higher = more recent seasons dominate.",
    )
    parser.add_argument(
        "--no-weight",
        action="store_true",
        help="Report unweighted accuracy only (still plots both lines)",
    )
    parser.add_argument(
        "--recent-seasons", type=int, default=None, metavar="N",
        help="Restrict analysis to the N most recent seasons (default: all)",
    )
    args = parser.parse_args()

    targets = _TARGETS if args.target == "all" else [args.target]
    lam = 0.0 if args.no_weight else args.lam

    stats_list = []
    for t in targets:
        try:
            stats = compute_season_stats(t, lam=lam, recent_seasons=args.recent_seasons)
            stats_list.append(stats)
        except FileNotFoundError:
            logger.warning("No OOF file for target '%s' — skipping", t)

    if not stats_list:
        logger.error("No targets loaded. Nothing to plot.")
        return

    # Print summary table
    print("\nPer-Season Accuracy Summary")
    print(f"{'Target':<12} {'Metric':<28} {'Unweighted':>11} {'Weighted (λ='+str(args.lam)+')':>18} {'N':>8}")
    print("-" * 80)
    for s in stats_list:
        target = s["target"]
        task = s["task"]
        if task == "clf" or target in ("spread", "h1_spread", "h2_spread"):
            metric_name = "Direction Accuracy %"
        else:
            metric_name = f"O/U Acc % (line={s['ou_line']:.1f})"
        print(f"{target:<12} {metric_name:<28} {s['unweighted']:>10.1f}% {s['weighted']:>16.1f}% {s['n_rows']:>8}")

    print()
    print("Recency weighting: w_i = exp(λ·i), normalised. Recent seasons dominate.")
    print("Colour gradient in plots: darker bars = higher recency weight.\n")

    suffix = f"_recent{args.recent_seasons}" if args.recent_seasons else ""
    if len(stats_list) == 1:
        t = stats_list[0]["target"]
        out_path = _cfg.OUTPUT_DIR / t / "plots" / f"{t}_season_accuracy{suffix}.png"
    else:
        out_path = _cfg.OUTPUT_DIR / f"season_accuracy_all{suffix}.png"

    plot_all(stats_list, args.lam, out_path)
    print(f"Plot saved: {out_path}")


if __name__ == "__main__":
    main()
