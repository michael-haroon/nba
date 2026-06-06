"""
plot_spread_analysis.py
-----------------------
Comprehensive spread model OOF diagnostics. 3x3 panel plot.

  1. Error distribution with Normal + t-dist fit
  2. QQ plot: residuals vs Normal (tail departure visible)
  3. QQ plot: residuals vs fitted t-distribution (should lie on diagonal)
  4. Heteroscedasticity: error std binned by predicted spread magnitude
  5. Accuracy within ±N pts by confidence decile
  6. MAE by predicted spread magnitude (is the model better at big spreads?)
  7. Tail probability: Normal vs t-dist vs historical (log scale)
  8. Exceedance ratio: how much does Normal underprice tails?
  9. Per-season MAE — temporal drift check

Run:
    conda run -n pred python -m strategy.plot_spread_analysis
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm, t as t_dist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

OOF_PATH = Path("strategy/output/nba/ensemble/spread_ensemble_oof.csv")
GAME_PARQUET = Path("output/features/game_features.parquet")
OUT_DIR = Path("strategy/output/nba/ensemble/plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run():
    log.info("Loading spread OOF data...")
    oof = pd.read_csv(OOF_PATH)
    errors = (oof["y_true"] - oof["y_pred_ensemble"]).values
    y_pred = oof["y_pred_ensemble"].values
    y_true = oof["y_true"].values
    pred_cols = [c for c in oof.columns if c.startswith("pred_")]
    model_std = oof[pred_cols].std(axis=1).values

    mae = np.abs(errors).mean()
    bias = errors.mean()
    sigma = errors.std()

    # Fit t-distribution (MLE, floc=0)
    t_params = t_dist.fit(errors, floc=0)
    t_df, t_loc, t_scale = t_params
    log.info(f"N={len(oof)}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f}")
    log.info(f"t-dist fit: df={t_df:.2f}, scale={t_scale:.2f}  (KS vs normal comparison below)")

    # KS tests
    ks_t = stats.kstest(errors, "t", args=(t_df, t_loc, t_scale))
    ks_n = stats.kstest(errors, "norm", args=(bias, sigma))
    log.info(f"KS test — t-dist: p={ks_t.pvalue:.4f} | Normal: p={ks_n.pvalue:.6f}")

    # Load season for panel 9
    df_meta = pd.read_parquet(GAME_PARQUET, columns=["season"])
    df_meta = df_meta.dropna()
    has_season = len(df_meta) == len(oof)
    if has_season:
        oof["season"] = df_meta["season"].values
    oof["abs_error"] = np.abs(errors)
    oof["error"] = errors
    oof["model_std"] = model_std

    # Historical spread for tail comparison
    df_full = pd.read_parquet(GAME_PARQUET, columns=["target_spread", "season", "season_type"])
    playoffs = df_full[df_full["season_type"] == "Playoffs"]["target_spread"].dropna().values
    all_spreads = df_full["target_spread"].dropna().values

    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    fig.suptitle(f"Spread Model — OOF Diagnostics  (N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f})",
                 fontsize=13, y=1.01)

    x_dense = np.linspace(-55, 55, 600)

    # ── 1. Error distribution with fits ─────────────────────────────────────
    ax = axes[0, 0]
    ax.hist(errors, bins=100, density=True, alpha=0.6, color="steelblue",
            edgecolor="none", label="OOF residuals")
    ax.plot(x_dense, norm.pdf(x_dense, loc=0, scale=sigma), "r-", lw=2,
            label=f"Normal (σ={sigma:.1f})")
    ax.plot(x_dense, t_dist.pdf(x_dense, df=t_df, loc=t_loc, scale=t_scale), "g--", lw=2,
            label=f"t-dist (df={t_df:.1f}, s={t_scale:.1f})")
    ax.axvline(0, color="k", ls="--", alpha=0.4)
    ax.set_xlabel("Residual (actual − predicted)")
    ax.set_ylabel("Density")
    ax.set_title(f"Error Distribution\nKS: t p={ks_t.pvalue:.3f} | Normal p={ks_n.pvalue:.5f}")
    ax.legend(fontsize=8)
    ax.set_xlim(-55, 55)
    ax.grid(True, alpha=0.3)

    # ── 2. QQ vs Normal ──────────────────────────────────────────────────────
    ax = axes[0, 1]
    (osm, osr), (slope, intercept, r) = stats.probplot(errors, dist="norm")
    ax.scatter(osm, osr, s=2, alpha=0.2, color="steelblue")
    ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=2, label=f"Normal fit R²={r**2:.4f}")
    tail_mask = np.abs(osm) > 2
    ax.scatter(np.array(osm)[tail_mask], np.array(osr)[tail_mask],
               s=8, alpha=0.5, color="red", zorder=5, label="Tail |z|>2")
    ax.set_xlabel("Theoretical Quantiles (Normal)")
    ax.set_ylabel("Sample Quantiles (residuals)")
    ax.set_title("QQ Plot vs Normal\nTail departure = fat tails = normal underprices extremes")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 3. QQ vs fitted t-distribution ───────────────────────────────────────
    ax = axes[0, 2]
    (osm_t, osr_t), (slope_t, intercept_t, r_t) = stats.probplot(
        errors, dist=t_dist, sparams=(t_df, t_loc, t_scale))
    ax.scatter(osm_t, osr_t, s=2, alpha=0.2, color="steelblue")
    ax.plot(osm_t, slope_t * np.array(osm_t) + intercept_t, "g-", lw=2,
            label=f"t-dist fit R²={r_t**2:.4f}")
    tail_mask_t = np.abs(osm_t) > 2
    ax.scatter(np.array(osm_t)[tail_mask_t], np.array(osr_t)[tail_mask_t],
               s=8, alpha=0.5, color="orange", zorder=5, label="Tail |z|>2")
    ax.set_xlabel(f"Theoretical Quantiles (t, df={t_df:.1f})")
    ax.set_ylabel("Sample Quantiles (residuals)")
    ax.set_title(f"QQ Plot vs t-distribution\nShould lie on diagonal if t is correct")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 4. Heteroscedasticity ─────────────────────────────────────────────────
    ax = axes[1, 0]
    ax.scatter(y_pred, errors, s=2, alpha=0.08, color="steelblue")
    bins = pd.cut(y_pred, bins=30)
    bin_stats = oof.assign(error=errors).groupby(bins, observed=True)["error"].agg(["mean", "std", "count"])
    bin_centers = [(b.left + b.right) / 2 for b in bin_stats.index]
    ax.plot(bin_centers, bin_stats["std"], "r-o", lw=2, markersize=4, label="Binned σ(E)")
    ax.axhline(sigma, color="k", ls="--", alpha=0.5, label=f"Overall σ={sigma:.1f}")
    ax.set_xlabel("Predicted spread (Ŷ)")
    ax.set_ylabel("Error / Error std")
    ax.set_title("Heteroscedasticity: Error vs Prediction\nFlat σ = homoscedastic")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 5. Accuracy within ±N pts by confidence decile ───────────────────────
    ax = axes[1, 1]
    oof["std_decile"] = pd.qcut(oof["model_std"], 10, labels=[f"D{i+1}" for i in range(10)])
    windows = [3, 5, 7, 10]
    colors = ["#d73027", "#fc8d59", "#4575b4", "#313695"]
    for win, col in zip(windows, colors):
        within = oof.groupby("std_decile", observed=True).apply(
            lambda g: (g["abs_error"] <= win).mean()).values
        ax.plot(range(10), within, "-o", lw=2, markersize=4, color=col, label=f"±{win} pts")
    ax.set_xticks(range(10))
    ax.set_xticklabels([f"D{i+1}" for i in range(10)], fontsize=8)
    ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
    ax.set_ylabel("Fraction within window")
    ax.set_title("Accuracy Within ±N pts by Confidence")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 6. MAE by predicted spread magnitude ─────────────────────────────────
    ax = axes[1, 2]
    oof["abs_pred"] = np.abs(y_pred)
    pred_bins = pd.cut(oof["abs_pred"], bins=[0, 2, 4, 6, 8, 10, 12, 15, 50])
    bin_mae = oof.groupby(pred_bins, observed=True).agg(
        mae=("abs_error", "mean"), n=("abs_error", "count"),
        pred_mean=("abs_pred", "mean")).reset_index()
    ax.bar(range(len(bin_mae)), bin_mae["mae"], color="steelblue", alpha=0.7)
    ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
    ax.set_xticks(range(len(bin_mae)))
    ax.set_xticklabels([str(b) for b in pred_bins.cat.categories], rotation=30, fontsize=8)
    ax.set_xlabel("|Predicted spread|")
    ax.set_ylabel("MAE")
    ax.set_title("MAE by Prediction Magnitude")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── 7. Tail probability comparison (log scale) ───────────────────────────
    ax = axes[2, 0]
    thresholds = np.arange(10, 40, 1)
    p_normal = 2 * (1 - norm.cdf(thresholds / sigma))
    p_t = 2 * (1 - t_dist.cdf(thresholds / t_scale, df=t_df))
    p_hist_all = np.array([(np.abs(all_spreads) >= t).mean() for t in thresholds])
    p_hist_po = np.array([(np.abs(playoffs) >= t).mean() for t in thresholds])
    ax.semilogy(thresholds, p_normal, "r-", lw=2, label=f"Normal (σ={sigma:.1f})")
    ax.semilogy(thresholds, p_t, "g--", lw=2, label=f"t-dist (df={t_df:.0f})")
    ax.semilogy(thresholds, p_hist_all, "b-", lw=1.5, label=f"Historical all (N={len(all_spreads):,})")
    ax.semilogy(thresholds, p_hist_po, "k--", lw=1.5, label=f"Historical playoffs (N={len(playoffs):,})")
    ax.set_xlabel("Margin Threshold (pts)")
    ax.set_ylabel("P(|margin| ≥ threshold)")
    ax.set_title("Tail Probabilities (log scale)\nGap = normal underprices extremes")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(1e-4, 0.6)

    # ── 8. Ratio: Historical / Normal (how much does Normal underprice?) ───────
    ax = axes[2, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_all = np.where(p_normal > 0, p_hist_all / p_normal, np.nan)
        ratio_po = np.where(p_normal > 0, p_hist_po / p_normal, np.nan)
        ratio_t = np.where(p_normal > 0, p_t / p_normal, np.nan)
    ax.plot(thresholds, ratio_all, "b-o", lw=2, markersize=3, label="Historical all / Normal")
    ax.plot(thresholds, ratio_po, "k--o", lw=2, markersize=3, label="Historical playoffs / Normal")
    ax.plot(thresholds, ratio_t, "g--", lw=2, label="t-dist / Normal")
    ax.axhline(1.0, color="r", ls="--", alpha=0.7, label="Correct")
    for t_val in [20, 25, 30]:
        idx = np.argmin(np.abs(thresholds - t_val))
        if not np.isnan(ratio_po[idx]):
            ax.annotate(f"{ratio_po[idx]:.1f}x", (thresholds[idx], ratio_po[idx]),
                        textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("Margin Threshold (pts)")
    ax.set_ylabel("Actual / Normal model")
    ax.set_title("Tail Underpricing Ratio\n>1 = Normal too low")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 5)

    # ── 9. Per-season MAE ─────────────────────────────────────────────────────
    ax = axes[2, 2]
    if has_season:
        s_mae = oof.groupby("season", observed=True).agg(
            mae=("abs_error", "mean"), n=("abs_error", "count")).reset_index().sort_values("season")
        se_s = s_mae["mae"] / np.sqrt(s_mae["n"])
        ax.plot(range(len(s_mae)), s_mae["mae"], "b-o", lw=2, markersize=4)
        ax.fill_between(range(len(s_mae)),
                        s_mae["mae"] - 1.96 * se_s, s_mae["mae"] + 1.96 * se_s,
                        alpha=0.15, color="blue")
        ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
        ax.set_xticks(range(0, len(s_mae), 3))
        ax.set_xticklabels(s_mae["season"].iloc[::3], rotation=45, fontsize=7)
        ax.set_xlabel("Season")
        ax.set_ylabel("MAE (pts)")
        ax.set_title("Per-Season MAE (temporal drift?)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "Season data unavailable", ha="center", va="center")

    plt.tight_layout()
    out_path = OUT_DIR / "spread_analysis.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Saved: {out_path}")

    # ── Console summary ──────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("SPREAD MODEL ANALYSIS SUMMARY")
    log.info("=" * 60)
    log.info(f"  N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f}")
    log.info(f"  t-dist: df={t_df:.2f}, scale={t_scale:.2f}")
    log.info(f"  KS: t-dist p={ks_t.pvalue:.4f} | Normal p={ks_n.pvalue:.6f}")
    log.info(f"  Accuracy: ±3={( np.abs(errors)<=3).mean():.1%}, ±5={( np.abs(errors)<=5).mean():.1%}, "
             f"±7={( np.abs(errors)<=7).mean():.1%}, ±10={( np.abs(errors)<=10).mean():.1%}")
    log.info("")
    log.info(f"  Tail underpricing (historical all / Normal):")
    for t_val in [15, 20, 25, 30, 35]:
        idx = np.argmin(np.abs(thresholds - t_val))
        log.info(f"    |spread|≥{t_val}: Normal={p_normal[idx]:.2%}, "
                 f"t-dist={p_t[idx]:.2%}, hist={p_hist_all[idx]:.2%}, "
                 f"ratio={ratio_all[idx]:.1f}x")


if __name__ == "__main__":
    run()
