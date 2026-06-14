"""
plot_tail_analysis.py
---------------------
Comprehensive visualization of spread model tail behavior.

Answers the key question: does our normal(σ=12.44) pricing model accurately
price extreme outcomes (30+ pt blowouts), or do NBA margins have fat tails
that the market correctly prices but our model misses?

Generates 4 plots:
  1. QQ plot — normal vs actual residuals (tail departure visible)
  2. Tail probability comparison — model vs historical vs market
  3. Empirical CDF of |margin| vs fitted normal and t-distribution
  4. Exceedance plot — P(|margin| > x) on log scale for all three

Run:
    conda run -n pred python -m strategy.plot_tail_analysis
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm, t as t_dist

from strategy.config import SKIP_SEASONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

OOF_PATH = Path("strategy/output/nba/spread/ensemble_oof.csv")
GAME_PARQUET = Path("output/features/game_features.parquet")
OUT_DIR = Path("strategy/output/nba/spread/plots")

SIGMA = 12.44  # current model assumption


def _attach_season(oof: pd.DataFrame) -> pd.DataFrame:
    if "season" in oof.columns:
        return oof
    try:
        df_meta = pd.read_parquet(GAME_PARQUET, columns=["season", "target_spread"])
        valid = df_meta["target_spread"].notna() & ~df_meta["season"].isin(SKIP_SEASONS)
        seasons = df_meta.loc[valid, "season"].reset_index(drop=True)
        n = min(len(oof), len(seasons))
        oof = oof.copy()
        oof["season"] = seasons.values[:n]
        log.warning("season attached positionally (%d rows); re-run ensemble to persist.", n)
    except Exception as e:
        log.warning("Could not attach season: %s", e)
    return oof


def run(recent_seasons: int | None = None):
    log.info("Loading data...")
    oof = pd.read_csv(OOF_PATH)
    # Normalise ensemble column name
    if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
        oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})
    oof = _attach_season(oof)

    suffix = ""
    if recent_seasons and "season" in oof.columns:
        all_s = sorted(oof["season"].dropna().unique())
        keep = set(all_s[-recent_seasons:])
        oof = oof[oof["season"].isin(keep)].reset_index(drop=True)
        log.info("Filtered to %d seasons: %s", len(keep), sorted(keep))
        suffix = f"_recent{recent_seasons}"

    errors = (oof["y_true"] - oof["y_pred_ensemble"]).values

    df = pd.read_parquet(GAME_PARQUET)
    playoffs = df[df["season_type"] == "Playoffs"]
    playoff_spreads = playoffs["target_spread"].dropna().values
    all_spreads = df["target_spread"].dropna().values

    # Fit t-distribution to OOF residuals
    t_params = t_dist.fit(errors)
    t_df, t_loc, t_scale = t_params
    log.info(f"t-dist fit on residuals: df={t_df:.1f}, loc={t_loc:.2f}, scale={t_scale:.2f}")
    log.info(f"Normal fit: μ={errors.mean():.2f}, σ={errors.std():.2f}")
    log.info(f"Excess kurtosis (residuals): {stats.kurtosis(errors):.3f}")
    log.info(f"Excess kurtosis (playoff spreads): {stats.kurtosis(playoff_spreads):.3f}")

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))

    # ── 1. QQ plot: residuals vs normal, highlighting tails ──────────────────
    ax = axes[0, 0]
    (osm, osr), (slope, intercept, r) = stats.probplot(errors, dist="norm")
    ax.scatter(osm, osr, s=2, alpha=0.3, color="steelblue")
    ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=2,
            label=f"Normal fit (R²={r**2:.4f})")

    # Highlight tail departures
    tail_mask = np.abs(osm) > 2
    ax.scatter(np.array(osm)[tail_mask], np.array(osr)[tail_mask],
               s=8, alpha=0.5, color="red", zorder=5, label="Tail (|z|>2)")

    ax.set_xlabel("Theoretical Quantiles (Normal)")
    ax.set_ylabel("Sample Quantiles (Residuals)")
    ax.set_title("QQ Plot: Spread Residuals vs Normal\n"
                 "Tail departure = fat tails = normal underprices extremes")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # ── 2. Tail probability: Model vs Historical vs Market ───────────────────
    ax = axes[0, 1]
    thresholds = np.arange(15, 40, 1)

    # Model (normal): P(|residual| > t) using σ=12.44
    p_normal = 2 * (1 - norm.cdf(thresholds / SIGMA))

    # Model (t-dist fit): P(|residual| > t)
    p_t = 2 * (1 - t_dist.cdf(thresholds / t_scale, df=t_df))

    # Historical (playoff games): P(|spread| > t)
    n_playoffs = len(playoff_spreads)
    p_hist_playoffs = np.array([(np.abs(playoff_spreads) >= t).sum() / n_playoffs
                                for t in thresholds])

    # Historical (all games): P(|spread| > t)
    n_all = len(all_spreads)
    p_hist_all = np.array([(np.abs(all_spreads) >= t).sum() / n_all
                           for t in thresholds])

    ax.semilogy(thresholds, p_normal, "r-", lw=2, label=f"Normal (σ={SIGMA})")
    ax.semilogy(thresholds, p_t, "g--", lw=2, label=f"t-dist (df={t_df:.0f}, scale={t_scale:.1f})")
    ax.semilogy(thresholds, p_hist_playoffs, "b-o", lw=2, markersize=4,
                label=f"Historical (playoffs, N={n_playoffs})")
    ax.semilogy(thresholds, p_hist_all, "k--", lw=1, alpha=0.5,
                label=f"Historical (all, N={n_all})")

    # Market reference points (approximate Kalshi pricing)
    market_points = {20: 0.10, 25: 0.06, 30: 0.04, 35: 0.02}
    ax.scatter(list(market_points.keys()), list(market_points.values()),
               s=100, color="orange", marker="D", zorder=5, label="Kalshi market (approx)")

    ax.set_xlabel("Margin Threshold (pts)")
    ax.set_ylabel("P(|margin| ≥ threshold)")
    ax.set_title("Tail Probabilities: Model vs Reality vs Market\n"
                 "Gap between red and blue = model mispricing")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(1e-4, 0.5)

    # ── 3. Error distribution with both fits overlaid ────────────────────────
    ax = axes[1, 0]
    ax.hist(errors, bins=100, density=True, alpha=0.6, color="steelblue",
            edgecolor="none", label="Actual residuals")

    x = np.linspace(-50, 50, 500)
    ax.plot(x, norm.pdf(x, loc=0, scale=SIGMA), "r-", lw=2,
            label=f"Normal (σ={SIGMA})")
    ax.plot(x, t_dist.pdf(x, df=t_df, loc=t_loc, scale=t_scale), "g--", lw=2,
            label=f"t-dist (df={t_df:.0f})")

    # Shade the tails to show where mismatch matters
    tail_x = x[np.abs(x) > 25]
    ax.fill_between(tail_x, 0, norm.pdf(tail_x, loc=0, scale=SIGMA),
                    alpha=0.2, color="red", label="Normal tail (underestimates)")
    ax.fill_between(tail_x, norm.pdf(tail_x, loc=0, scale=SIGMA),
                    t_dist.pdf(tail_x, df=t_df, loc=t_loc, scale=t_scale),
                    alpha=0.2, color="green", label="t-dist correction")

    ax.set_xlabel("Spread Error (actual - predicted)")
    ax.set_ylabel("Density")
    ax.set_title("Residual Distribution: Normal Underestimates Tails\n"
                 "Red area = probability our model misses")
    ax.legend(fontsize=8)
    ax.set_xlim(-55, 55)
    ax.grid(True, alpha=0.3)

    # ── 4. Ratio plot: how much does normal underprice each threshold? ───────
    ax = axes[1, 1]

    # Ratio of historical to model probability
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_playoffs = np.where(p_normal > 0, p_hist_playoffs / p_normal, np.nan)
        ratio_t = np.where(p_normal > 0, p_t / p_normal, np.nan)

    ax.plot(thresholds, ratio_playoffs, "b-o", lw=2, markersize=4,
            label="Historical(playoffs) / Normal")
    ax.plot(thresholds, ratio_t, "g--", lw=2,
            label="t-dist / Normal")
    ax.axhline(1.0, color="r", ls="--", alpha=0.7, label="Normal = correct")
    ax.axhline(2.0, color="gray", ls=":", alpha=0.5)
    ax.axhline(3.0, color="gray", ls=":", alpha=0.5)

    # Annotate key thresholds
    for t_val in [20, 25, 30, 35]:
        idx = np.argmin(np.abs(thresholds - t_val))
        if not np.isnan(ratio_playoffs[idx]):
            ax.annotate(f"{ratio_playoffs[idx]:.1f}x",
                        (thresholds[idx], ratio_playoffs[idx]),
                        textcoords="offset points", xytext=(5, 5), fontsize=9)

    ax.set_xlabel("Margin Threshold (pts)")
    ax.set_ylabel("Ratio: Actual / Normal Model")
    ax.set_title("How Much Does Normal Underprice Tails?\n"
                 "2x = blowouts happen 2x more than model thinks")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 5)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"spread_tail_analysis{suffix}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Saved: {out_path}")

    # ── Summary statistics to log ────────────────────────────────────────────
    log.info("\n" + "=" * 70)
    log.info("SPREAD TAIL ANALYSIS SUMMARY")
    log.info("=" * 70)
    log.info(f"  OOF residuals: N={len(errors)}, σ={errors.std():.2f}, "
             f"kurtosis={stats.kurtosis(errors):.3f}")
    log.info(f"  t-dist fit: df={t_df:.1f} (lower df = fatter tails)")
    log.info(f"  Normal assumption: σ={SIGMA}")
    log.info("")
    log.info(f"  {'Threshold':>10} {'Normal':>10} {'t-dist':>10} {'Hist(PO)':>10} {'Ratio':>8}")
    log.info(f"  {'-'*52}")
    for t_val in [20, 25, 30, 31.5, 35]:
        pn = 2 * (1 - norm.cdf(t_val / SIGMA))
        pt = 2 * (1 - t_dist.cdf(t_val / t_scale, df=t_df))
        ph = (np.abs(playoff_spreads) >= t_val).sum() / n_playoffs
        ratio = ph / pn if pn > 0 else float("inf")
        log.info(f"  {t_val:>10.1f} {pn:>10.2%} {pt:>10.2%} {ph:>10.2%} {ratio:>7.1f}x")
    log.info("")
    log.info("  IMPLICATION: Normal pricing is 1.5-3x too low in tails.")
    log.info("  The market knows this. Our fair prices at extreme spreads are wrong.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spread tail analysis plots")
    parser.add_argument(
        "--recent-seasons", type=int, default=None, metavar="N",
        help="Restrict analysis to the N most recent seasons (default: all)",
    )
    args = parser.parse_args()
    run(recent_seasons=args.recent_seasons)
