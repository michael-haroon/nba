"""
plot_diagnostics.py
-------------------
Generalized OOF diagnostic plots for any trained target.

For regression targets (spread, total, h1_spread, h2_spread, h1_total, h2_total):
  Panel 1: Error distribution — histogram + top-3 MLE-fitted distributions (ranked by KS stat)
  Panel 2: QQ vs best-fit signed distribution (KS rank 1 from norm/t/cauchy/laplace/logistic/uniform)
  Panel 3: QQ vs best-fit |error| distribution (KS rank 1 from lognorm/gamma/weibull/expon)
  Panel 4: Heteroscedasticity — residual std vs predicted value
  Panel 5: MAE by model-disagreement decile (does high ensemble std = high error?)
  Panel 6: MAE by prediction magnitude bucket
  Panel 7: Tail exceedance — Normal vs t-dist vs empirical OOF (log scale)
  Panel 8: Tail underpricing ratio — empirical / Normal
  Panel 9: Per-season MAE — temporal drift check
  Panel 10: Interval coverage calibration — empirical vs nominal coverage at each confidence level
  Panel 11: Coverage error — empirical − nominal (signed)
  Panel 12: Sharpness — distribution of predicted interval half-widths (how decisive is the model?)

For classification targets (winner, home_wins_h1, ...):
  Panel 1: Calibration curve (reliability diagram + 95% CI bands)
  Panel 2: QQ of logit(p_pred) vs best-fit signed distribution (KS rank 1)
  Panel 3: Predicted probability distribution split by outcome
  Panel 4: ROC curve (ensemble + individual models)
  Panel 5: Log-loss by confidence decile (ensemble std)
  Panel 6: Accuracy within prob buckets
  Panel 7: Brier score by confidence decile
  Panel 8: Per-season accuracy — temporal drift
  Panel 9: Specialist correlation heatmap
  Panel 10: ECE bar chart — mean predicted vs observed per probability bin (gap = calibration error)
  Panel 11: Brier decomposition — reliability + resolution + uncertainty
  Panel 12: Sharpness histogram — predicted probability distribution (how decisive is the model?)

Usage:
    conda run -n pred python -m strategy.plot_diagnostics --target spread
    conda run -n pred python -m strategy.plot_diagnostics --target total
    conda run -n pred python -m strategy.plot_diagnostics --target h1_spread
    conda run -n pred python -m strategy.plot_diagnostics --all
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

GAME_PARQUET = Path("output/features/game_features.parquet")
OUTPUT_ROOT = Path("strategy/output/nba")

TRAINED_TARGETS = ["winner", "spread", "h1_spread", "h2_spread", "total", "h1_total", "h2_total", "home_wins_h1"]

# Human-readable labels and axis ranges per target
_TARGET_CFG = {
    "winner":      {"label": "Game Winner",     "task": "clf",  "unit": "prob"},
    "spread":      {"label": "Game Spread",     "task": "reg",  "unit": "pts", "xlim": 55, "tail_lo": 10, "tail_hi": 40},
    "h1_spread":   {"label": "H1 Spread",       "task": "reg",  "unit": "pts", "xlim": 45, "tail_lo": 5,  "tail_hi": 30},
    "h2_spread":   {"label": "H2 Spread",       "task": "reg",  "unit": "pts", "xlim": 45, "tail_lo": 5,  "tail_hi": 30},
    "total":       {"label": "Game Total",      "task": "reg",  "unit": "pts", "xlim": 80, "tail_lo": 5,  "tail_hi": 40},
    "h1_total":    {"label": "H1 Total",        "task": "reg",  "unit": "pts", "xlim": 50, "tail_lo": 5,  "tail_hi": 30},
    "h2_total":    {"label": "H2 Total",        "task": "reg",  "unit": "pts", "xlim": 50, "tail_lo": 5,  "tail_hi": 30},
    "home_wins_h1": {"label": "Home Wins H1",   "task": "clf",  "unit": "prob"},
}

# Candidate distribution pools for goodness-of-fit ranking
_SIGNED_POOL = [
    ("norm",     stats.norm),
    ("t",        stats.t),
    ("cauchy",   stats.cauchy),
    ("laplace",  stats.laplace),
    ("logistic", stats.logistic),
    ("uniform",  stats.uniform),
]

_POS_POOL = [
    ("lognorm",  stats.lognorm),
    ("gamma",    stats.gamma),
    ("weibull",  stats.weibull_min),
    ("expon",    stats.expon),
]

_DIST_COLORS = ["#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2"]


def _rank_distributions(data: np.ndarray, pool: list) -> pd.DataFrame:
    """Rank distributions in pool by KS goodness-of-fit on data.

    KS p-values are optimistic when params are estimated from the same data (Lilliefors effect).
    Rank by ks_stat (lower = better fit), not p-value.

    Also computes a KDE baseline KS stat so callers can see whether any parametric
    distribution actually beats the empirical density.  The KDE row has params=None
    and is kept in the returned DataFrame for reference but is excluded from winner
    selection (since it's non-parametric and can't be used for interval arithmetic).

    Tie-breaking: when two entries share the same ks_stat to 6 decimal places, t
    beats norm (heavier tails = safer default).
    """
    from scipy.stats import gaussian_kde

    # KDE baseline: fit a KDE, evaluate on a fine grid, build empirical CDF, run KS
    kde = gaussian_kde(data, bw_method="scott")
    x_grid = np.linspace(data.min(), data.max(), 2000)
    kde_cdf_vals = np.array([kde.integrate_box_1d(-np.inf, xi) for xi in x_grid])
    kde_cdf = lambda x: np.interp(x, x_grid, kde_cdf_vals, left=0.0, right=1.0)
    kde_ks, _ = stats.kstest(data, kde_cdf)

    rows = []
    for name, dist in pool:
        try:
            params = dist.fit(data)
            ks_stat, ks_pval = stats.kstest(data, dist.cdf, args=params)
            rows.append({"dist": name, "params": params, "ks_stat": ks_stat, "ks_pval": ks_pval})
        except Exception as exc:
            log.debug(f"  {name}: fit failed — {exc}")
    if not rows:
        df = pd.DataFrame(columns=["dist", "params", "ks_stat", "ks_pval"])
        df.attrs["kde_ks"] = kde_ks
        return df

    df = pd.DataFrame(rows)
    # Tie-break: t before norm when ks_stats are equal to 6 decimal places
    df["_ks_r"] = df["ks_stat"].round(6)
    df["_torder"] = df["dist"].map(lambda d: 0 if d == "t" else (1 if d == "norm" else 2))
    df = df.sort_values(["_ks_r", "_torder"]).drop(columns=["_ks_r", "_torder"]).reset_index(drop=True)
    df.attrs["kde_ks"] = kde_ks
    return df


def _load_oof(target: str) -> pd.DataFrame:
    path = OUTPUT_ROOT / target / "ensemble_oof.csv"
    if not path.exists():
        raise FileNotFoundError(f"No OOF at {path}")
    oof = pd.read_csv(path)
    # Normalise ensemble column name (old scripts used y_pred_ensemble, new uses pred_ensemble)
    if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
        oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})
    return oof


def _attach_season(oof: pd.DataFrame) -> pd.DataFrame:
    """Best-effort season join via positional alignment."""
    try:
        df_meta = pd.read_parquet(GAME_PARQUET, columns=["season", "game_date"])
        df_meta = df_meta.dropna(subset=["season"])
        if len(df_meta) == len(oof):
            oof = oof.copy()
            oof["season"] = df_meta["season"].values
        else:
            log.warning(f"Season alignment skipped: parquet rows={len(df_meta)}, OOF rows={len(oof)}")
    except Exception as e:
        log.warning(f"Could not load season metadata: {e}")
    return oof


# ── Regression diagnostics ────────────────────────────────────────────────────

def _plot_regression(target: str, oof: pd.DataFrame, out_dir: Path) -> None:
    cfg = _TARGET_CFG[target]
    label = cfg["label"]
    xlim  = cfg["xlim"]
    tail_lo, tail_hi = cfg["tail_lo"], cfg["tail_hi"]
    target_col = f"target_{target}"

    errors = (oof["y_true"] - oof["y_pred_ensemble"]).values
    y_pred = oof["y_pred_ensemble"].values
    pred_cols = [c for c in oof.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    model_std = oof[pred_cols].std(axis=1).values if len(pred_cols) > 1 else np.zeros(len(oof))

    mae   = np.abs(errors).mean()
    bias  = errors.mean()
    sigma = errors.std()

    # Rank signed distributions (for panels 1 & 2)
    signed_rank = _rank_distributions(errors, _SIGNED_POOL)
    signed_kde_ks = signed_rank.attrs.get("kde_ks", float("nan"))
    # Rank positive-support distributions on |errors| (for panel 3)
    pos_rank = _rank_distributions(np.abs(errors), _POS_POOL)
    pos_kde_ks = pos_rank.attrs.get("kde_ks", float("nan"))

    # Keep t-dist fit for tail panels 7 & 8 (unchanged analysis)
    t_df, t_loc, t_scale = t_dist.fit(errors, floc=0)

    log.info(f"[{target}] N={len(oof):,}, MAE={mae:.3f}, σ={sigma:.3f}, bias={bias:+.3f}")
    log.info(f"[{target}] Signed dist ranking (KS stat):\n{signed_rank[['dist','ks_stat','ks_pval']].to_string(index=False)}")
    log.info(f"[{target}] |error| dist ranking (KS stat):\n{pos_rank[['dist','ks_stat','ks_pval']].to_string(index=False)}")

    oof = oof.copy()
    oof["error"]     = errors
    oof["abs_error"] = np.abs(errors)
    oof["model_std"] = model_std

    x_dense    = np.linspace(-xlim, xlim, 600)
    thresholds = np.arange(tail_lo, tail_hi + 1, 1, dtype=float)
    p_norm   = 2 * (1 - norm.cdf(thresholds / sigma))
    p_t_fit  = 2 * (1 - t_dist.cdf(thresholds / t_scale, df=t_df))
    p_hist   = np.array([(np.abs(errors) >= t).mean() for t in thresholds])

    fig, axes = plt.subplots(4, 3, figsize=(18, 20))
    fig.suptitle(
        f"{label} — OOF Diagnostics  "
        f"(N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f})",
        fontsize=13, y=1.01,
    )

    # 1. Error distribution — top-3 fits by KS rank
    ax = axes[0, 0]
    ax.hist(errors, bins=100, density=True, alpha=0.6, color="steelblue",
            edgecolor="none", label="OOF residuals")
    dist_lookup = dict(_SIGNED_POOL)
    for i, row in signed_rank.head(3).iterrows():
        d = dist_lookup[row["dist"]]
        color = _DIST_COLORS[i % len(_DIST_COLORS)]
        label_str = f"{row['dist']} (KS={row['ks_stat']:.3f}, p={row['ks_pval']:.3f})"
        ax.plot(x_dense, d.pdf(x_dense, *row["params"]), color=color, lw=2,
                linestyle=["-", "--", ":"][i % 3], label=label_str)
    ax.axvline(0, color="k", ls="--", alpha=0.4)
    ax.set_xlabel(f"Residual (actual − predicted, {cfg['unit']})")
    ax.set_ylabel("Density")
    best1 = signed_rank.iloc[0]["dist"] if len(signed_rank) else "?"
    ax.set_title(f"Error Distribution\nTop fit: {best1} | ranked by KS stat (lower = better)")
    ax.legend(fontsize=7)
    ax.set_xlim(-xlim, xlim)
    ax.grid(True, alpha=0.3)

    # 2. QQ vs best-fit signed distribution
    ax = axes[0, 1]
    if len(signed_rank) > 0:
        best_signed = signed_rank.iloc[0]
        best_signed_dist = dist_lookup[best_signed["dist"]]
        best_signed_params = best_signed["params"]
        (osm, osr), (slope, intercept, r) = stats.probplot(
            errors, dist=best_signed_dist, sparams=best_signed_params)
        ax.scatter(osm, osr, s=2, alpha=0.2, color="steelblue")
        ax.plot(osm, slope * np.array(osm) + intercept, color=_DIST_COLORS[0], lw=2,
                label=f"{best_signed['dist']} fit R²={r**2:.4f}")
        tail_mask = np.abs(osm) > 2
        ax.scatter(np.array(osm)[tail_mask], np.array(osr)[tail_mask],
                   s=8, alpha=0.5, color="red", zorder=5, label="Tail |z|>2")
        ax.set_xlabel(f"Theoretical Quantiles ({best_signed['dist']})")
        ratio_signed = best_signed["ks_stat"] / signed_kde_ks if signed_kde_ks > 0 else float("nan")
        ax.set_title(
            f"QQ vs {best_signed['dist']} (KS rank 1)\n"
            f"KS={best_signed['ks_stat']:.3f}  KDE={signed_kde_ks:.3f}  ratio={ratio_signed:.1f}x"
        )
    else:
        ax.text(0.5, 0.5, "No distributions fitted", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("QQ (best signed dist)")
    ax.set_ylabel("Sample Quantiles")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 3. QQ vs best-fit |error| distribution (positive support)
    ax = axes[0, 2]
    abs_errors = np.abs(errors)
    pos_lookup = dict(_POS_POOL)
    if len(pos_rank) > 0:
        best_pos = pos_rank.iloc[0]
        best_pos_dist = pos_lookup[best_pos["dist"]]
        best_pos_params = best_pos["params"]
        (osm_p, osr_p), (slope_p, intercept_p, r_p) = stats.probplot(
            abs_errors, dist=best_pos_dist, sparams=best_pos_params)
        ax.scatter(osm_p, osr_p, s=2, alpha=0.2, color="steelblue")
        ax.plot(osm_p, slope_p * np.array(osm_p) + intercept_p, color=_DIST_COLORS[1], lw=2,
                label=f"{best_pos['dist']} fit R²={r_p**2:.4f}")
        tail_p = np.abs(osm_p) > 2
        ax.scatter(np.array(osm_p)[tail_p], np.array(osr_p)[tail_p],
                   s=8, alpha=0.5, color="orange", zorder=5, label="Tail |z|>2")
        ax.set_xlabel(f"Theoretical Quantiles (|error|, {best_pos['dist']})")
        ratio_pos = best_pos["ks_stat"] / pos_kde_ks if pos_kde_ks > 0 else float("nan")
        ax.set_title(
            f"QQ vs |error| {best_pos['dist']} (KS rank 1)\n"
            f"KS={best_pos['ks_stat']:.3f}  KDE={pos_kde_ks:.3f}  ratio={ratio_pos:.1f}x"
        )
    else:
        ax.text(0.5, 0.5, "No distributions fitted", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("QQ (best |error| dist)")
    ax.set_ylabel("Sample Quantiles (|error|)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4. Heteroscedasticity
    ax = axes[1, 0]
    ax.scatter(y_pred, errors, s=2, alpha=0.08, color="steelblue")
    bins = pd.cut(y_pred, bins=30)
    bin_stats = oof.groupby(bins, observed=True)["error"].agg(["mean", "std", "count"])
    bin_centers = [(b.left + b.right) / 2 for b in bin_stats.index]
    ax.plot(bin_centers, bin_stats["std"], "r-o", lw=2, markersize=4, label="Binned σ(E)")
    ax.axhline(sigma, color="k", ls="--", alpha=0.5, label=f"Overall σ={sigma:.1f}")
    ax.set_xlabel(f"Predicted ({cfg['unit']})")
    ax.set_ylabel("Residual / Residual std")
    ax.set_title("Heteroscedasticity\nFlat binned σ = homoscedastic")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 5. MAE by model-disagreement decile
    ax = axes[1, 1]
    if model_std.std() > 0:
        oof["std_decile"] = pd.qcut(oof["model_std"], 10, labels=[f"D{i+1}" for i in range(10)],
                                    duplicates="drop")
        mae_dec = oof.groupby("std_decile", observed=True).agg(
            mae=("abs_error", "mean"),
            n=("abs_error", "count"),
            std_mean=("model_std", "mean"),
        ).reset_index()
        se_mae = mae_dec["mae"] / np.sqrt(mae_dec["n"])
        ax.bar(range(len(mae_dec)), mae_dec["mae"], color="steelblue", alpha=0.7)
        ax.errorbar(range(len(mae_dec)), mae_dec["mae"], yerr=1.96 * se_mae,
                    fmt="none", color="black", capsize=3)
        ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
        ax.set_xticks(range(len(mae_dec)))
        # Show decile label, mean std, and sample count so anomalies (e.g. D10 n=30) are visible
        ax.set_xticklabels(
            [f"D{i+1}\nstd={v:.2f}\nn={n}" for i, (v, n) in
             enumerate(zip(mae_dec["std_mean"], mae_dec["n"]))],
            fontsize=6,
        )
        ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
        ax.set_ylabel(f"MAE ({cfg['unit']})")
        ax.set_title("MAE by Model Disagreement\nRising = ensemble std is informative")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(0.5, 0.5, "Single model — no disagreement metric", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("MAE by Model Disagreement")

    # 6. MAE by prediction magnitude — equal-width line chart
    # Equal-width bins avoid the single-sample spike artifact from pd.cut with few extreme predictions.
    ax = axes[1, 2]
    n_pts = 40
    pred_lo, pred_hi = np.percentile(y_pred, 1), np.percentile(y_pred, 99)
    bin_edges = np.linspace(pred_lo, pred_hi, n_pts + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    bin_idx = np.digitize(y_pred, bin_edges, right=True).clip(1, n_pts) - 1
    mae_line, n_line = [], []
    for b in range(n_pts):
        mask = bin_idx == b
        if mask.sum() > 0:
            mae_line.append(np.abs(errors[mask]).mean())
            n_line.append(mask.sum())
        else:
            mae_line.append(np.nan)
            n_line.append(0)
    mae_arr = np.array(mae_line)
    n_arr   = np.array(n_line)
    reliable = n_arr >= 30  # bins with fewer than 30 samples are flagged

    ax2b = ax.twinx()
    ax2b.bar(bin_centers, n_arr, width=(pred_hi - pred_lo) / n_pts * 0.9,
             color="lightgray", alpha=0.5, label="N per bin")
    ax2b.set_ylabel("N per bin", fontsize=8, color="gray")
    ax2b.tick_params(axis="y", labelcolor="gray", labelsize=7)

    ax.plot(bin_centers[reliable], mae_arr[reliable], "b-o", lw=2, markersize=4,
            label=f"MAE (n≥30)")
    if (~reliable & (n_arr > 0)).any():
        ax.plot(bin_centers[~reliable & (n_arr > 0)], mae_arr[~reliable & (n_arr > 0)],
                "ro", markersize=5, label="MAE (n<30, unreliable)")
    ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
    ax.set_xlabel(f"Predicted {label} ({cfg['unit']})")
    ax.set_ylabel(f"MAE ({cfg['unit']})")
    ax.set_title("MAE by Prediction Magnitude\nOpen red = n<30 (unreliable)")
    lines1, labels1 = ax.get_legend_handles_labels()
    ax.legend(lines1, labels1, fontsize=7, loc="upper left")
    ax.grid(True, alpha=0.3, axis="y")

    # 7. Tail exceedance (log scale)
    ax = axes[2, 0]
    ax.semilogy(thresholds, p_norm,  "r-",  lw=2, label=f"Normal (σ={sigma:.1f})")
    ax.semilogy(thresholds, p_t_fit, "g--", lw=2, label=f"t-dist (df={t_df:.0f})")
    ax.semilogy(thresholds, p_hist,  "b-",  lw=1.5, label="Empirical OOF")
    ax.set_xlabel(f"|Residual| Threshold ({cfg['unit']})")
    ax.set_ylabel("P(|residual| ≥ threshold)")
    ax.set_title("Tail Exceedance (log scale)\nGap between Normal & empirical = underpricing")
    ax.legend(fontsize=8)
    ax.set_ylim(1e-4, 1)
    ax.grid(True, alpha=0.3)

    # 8. Tail underpricing ratio
    ax = axes[2, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_emp = np.where(p_norm > 0, p_hist / p_norm, np.nan)
        ratio_t   = np.where(p_norm > 0, p_t_fit / p_norm, np.nan)
    ax.plot(thresholds, ratio_emp, "b-o", lw=2, markersize=3, label="Empirical / Normal")
    ax.plot(thresholds, ratio_t,   "g--", lw=2,              label="t-dist / Normal")
    ax.axhline(1.0, color="r", ls="--", alpha=0.7, label="Correct pricing")
    # Annotate a few reference points
    for t_val in thresholds[::max(1, len(thresholds) // 5)][1:4]:
        idx = np.argmin(np.abs(thresholds - t_val))
        if not np.isnan(ratio_emp[idx]):
            ax.annotate(f"{ratio_emp[idx]:.1f}x", (thresholds[idx], ratio_emp[idx]),
                        textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel(f"|Residual| Threshold ({cfg['unit']})")
    ax.set_ylabel("Actual / Normal")
    ax.set_title("Tail Underpricing Ratio\n>1 = Normal underestimates tail probability")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 5)
    ax.grid(True, alpha=0.3)

    # 9. Per-season MAE
    ax = axes[2, 2]
    if "season" in oof.columns and oof["season"].notna().any():
        s_mae = (
            oof.groupby("season", observed=True)
               .agg(mae=("abs_error", "mean"), n=("abs_error", "count"))
               .reset_index()
               .sort_values("season")
        )
        se_s = s_mae["mae"] / np.sqrt(s_mae["n"])
        ax.plot(range(len(s_mae)), s_mae["mae"], "b-o", lw=2, markersize=4)
        ax.fill_between(range(len(s_mae)),
                        s_mae["mae"] - 1.96 * se_s,
                        s_mae["mae"] + 1.96 * se_s,
                        alpha=0.15, color="blue")
        ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
        ax.set_xticks(range(0, len(s_mae), max(1, len(s_mae) // 8)))
        ax.set_xticklabels(s_mae["season"].iloc[::max(1, len(s_mae) // 8)],
                           rotation=45, fontsize=7)
        ax.set_xlabel("Season")
        ax.set_ylabel(f"MAE ({cfg['unit']})")
        ax.set_title("Per-Season MAE\nDrift = model is becoming stale")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "Season data not available", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("Per-Season MAE")

    # 10–12. Interval coverage calibration using best-fit signed distribution
    # Nominal coverage α → predict interval [q_{(1-α)/2}, q_{(1+α)/2}] of the fitted dist,
    # then measure empirical coverage. Perfect calibration = diagonal.
    nominal_levels = np.linspace(0.05, 0.99, 50)
    if len(signed_rank) > 0:
        best_s = signed_rank.iloc[0]
        best_s_dist = dict(_SIGNED_POOL)[best_s["dist"]]
        best_s_params = best_s["params"]
        empirical_coverage = np.array([
            (
                (errors >= best_s_dist.ppf((1 - alpha) / 2, *best_s_params)) &
                (errors <= best_s_dist.ppf((1 + alpha) / 2, *best_s_params))
            ).mean()
            for alpha in nominal_levels
        ])
        # Interval half-widths (sharpness)
        half_widths = np.array([
            best_s_dist.ppf((1 + alpha) / 2, *best_s_params) -
            best_s_dist.ppf((1 - alpha) / 2, *best_s_params)
        for alpha in nominal_levels]) / 2
        coverage_error = empirical_coverage - nominal_levels
        mce = np.abs(coverage_error).mean()
        log.info(f"[{target}] MCE (mean |coverage error|) = {mce:.4f}")
    else:
        empirical_coverage = coverage_error = half_widths = None

    ax = axes[3, 0]
    if empirical_coverage is not None:
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
        ax.plot(nominal_levels, empirical_coverage, "b-", lw=2, label=f"Empirical ({best_s['dist']} base)")
        ax.fill_between(nominal_levels, nominal_levels, empirical_coverage,
                        where=empirical_coverage > nominal_levels,
                        alpha=0.15, color="red", label="Overconfident (too narrow)")
        ax.fill_between(nominal_levels, nominal_levels, empirical_coverage,
                        where=empirical_coverage < nominal_levels,
                        alpha=0.15, color="green", label="Underconfident (too wide)")
        ax.set_xlabel("Nominal coverage (1−α)")
        ax.set_ylabel("Empirical coverage")
        ax.set_title(f"Interval Coverage Calibration\nMCE={mce:.4f} (0 = perfect)")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    else:
        ax.text(0.5, 0.5, "No distribution fit available", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("Interval Coverage Calibration")

    ax = axes[3, 1]
    if coverage_error is not None:
        ax.plot(nominal_levels, coverage_error, "b-", lw=2)
        ax.axhline(0, color="k", ls="--", lw=1, alpha=0.6, label="Zero error")
        ax.fill_between(nominal_levels, 0, coverage_error,
                        where=coverage_error > 0, alpha=0.2, color="red",
                        label="+: empirical > nominal (underconfident)")
        ax.fill_between(nominal_levels, 0, coverage_error,
                        where=coverage_error < 0, alpha=0.2, color="green",
                        label="−: empirical < nominal (overconfident)")
        ax.set_xlabel("Nominal coverage (1−α)")
        ax.set_ylabel("Empirical − Nominal")
        ax.set_title("Coverage Error\n+= too wide, −= too narrow")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No distribution fit available", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("Coverage Error")

    ax = axes[3, 2]
    if half_widths is not None:
        ax.plot(nominal_levels, half_widths, "b-", lw=2)
        ax.set_xlabel("Nominal coverage (1−α)")
        ax.set_ylabel(f"Interval half-width ({cfg['unit']})")
        ax.set_title("Sharpness: Predicted Interval Half-Width\nNarrower = more decisive model")
        ax.grid(True, alpha=0.3)
        # Annotate a few reference coverage levels
        for alpha_ref in [0.50, 0.80, 0.95]:
            idx = np.argmin(np.abs(nominal_levels - alpha_ref))
            hw = half_widths[idx]
            ax.annotate(f"{alpha_ref:.0%}: ±{hw:.1f}", (nominal_levels[idx], hw),
                        textcoords="offset points", xytext=(4, 4), fontsize=8)
    else:
        ax.text(0.5, 0.5, "No distribution fit available", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("Sharpness")

    plt.tight_layout()
    out_path = out_dir / f"{target}_diagnostics.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"[{target}] Saved: {out_path}")

    # Summary to log
    log.info(f"[{target}] t-dist: df={t_df:.2f}, scale={t_scale:.3f}")
    within = {n: (np.abs(errors) <= n).mean() for n in [3, 5, 7, 10, 15]}
    log.info(f"[{target}] Within: " + "  ".join(f"±{n}={v:.1%}" for n, v in within.items()))


# ── Classification diagnostics ────────────────────────────────────────────────

def _plot_classification(target: str, oof: pd.DataFrame, out_dir: Path) -> None:
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import roc_curve, auc, brier_score_loss, log_loss

    cfg   = _TARGET_CFG[target]
    label = cfg["label"]
    EPS   = 1e-6

    y_true = oof["y_true"].values
    y_pred = oof["y_pred_ensemble"].values.clip(EPS, 1 - EPS)
    pred_cols = [c for c in oof.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    model_std = oof[pred_cols].std(axis=1).values if len(pred_cols) > 1 else np.zeros(len(oof))

    brier = brier_score_loss(y_true, y_pred)
    acc   = (y_pred.round() == y_true).mean()
    ll    = log_loss(y_true, y_pred)
    fpr_roc, tpr_roc, _ = roc_curve(y_true, y_pred)
    roc_auc = auc(fpr_roc, tpr_roc)
    log.info(f"[{target}] N={len(oof):,}, Acc={acc:.3f}, AUC={roc_auc:.3f}, "
             f"Brier={brier:.4f}, LogLoss={ll:.4f}")

    oof = oof.copy()
    oof["abs_error"] = np.abs(y_true - y_pred)
    oof["model_std"] = model_std

    fig, axes = plt.subplots(4, 3, figsize=(18, 20))
    fig.suptitle(
        f"{label} — OOF Diagnostics  "
        f"(N={len(oof):,}, Acc={acc:.3f}, AUC={roc_auc:.3f}, "
        f"Brier={brier:.4f}, LogLoss={ll:.4f})",
        fontsize=13, y=1.01,
    )

    # 1. Calibration curve
    ax = axes[0, 0]
    fraction_pos, mean_pred = calibration_curve(y_true, y_pred, n_bins=15, strategy="quantile")
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
    ax.plot(mean_pred, fraction_pos, "b-o", lw=2, markersize=5, label="Ensemble")
    # 95% CI via Wilson score interval
    n_cal = len(y_true) / 15
    ci = 1.96 * np.sqrt(fraction_pos * (1 - fraction_pos) / n_cal)
    ax.fill_between(mean_pred, fraction_pos - ci, fraction_pos + ci,
                    alpha=0.15, color="blue", label="95% CI")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed win rate")
    ax.set_title("Calibration Curve\nShould lie on diagonal")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 2. QQ of logit(p̂) vs best-fit signed distribution
    ax = axes[0, 1]
    logit_p = np.log(y_pred / (1 - y_pred))
    logit_rank = _rank_distributions(logit_p, _SIGNED_POOL)
    logit_kde_ks = logit_rank.attrs.get("kde_ks", float("nan"))
    log.info(f"[{target}] logit(p̂) dist ranking (KDE baseline KS={logit_kde_ks:.4f}):\n{logit_rank[['dist','ks_stat','ks_pval']].to_string(index=False)}")
    dist_lookup_clf = dict(_SIGNED_POOL)
    if len(logit_rank) > 0:
        best_logit = logit_rank.iloc[0]
        best_logit_dist = dist_lookup_clf[best_logit["dist"]]
        best_logit_params = best_logit["params"]
        (osm, osr), (slope, intercept, r) = stats.probplot(
            logit_p, dist=best_logit_dist, sparams=best_logit_params)
        ax.scatter(osm, osr, s=2, alpha=0.2, color="steelblue")
        ax.plot(osm, slope * np.array(osm) + intercept, color=_DIST_COLORS[0], lw=2,
                label=f"{best_logit['dist']} fit R²={r**2:.4f}")
        # Also overlay rank-2 if available
        if len(logit_rank) > 1:
            r2 = logit_rank.iloc[1]
            d2 = dist_lookup_clf[r2["dist"]]
            (osm2, osr2), (s2, i2, r2v) = stats.probplot(
                logit_p, dist=d2, sparams=r2["params"])
            ax.plot(osm2, s2 * np.array(osm2) + i2, color=_DIST_COLORS[1], lw=1.5, ls="--",
                    label=f"{r2['dist']} fit R²={r2v**2:.4f}")
        ax.set_xlabel(f"Theoretical Quantiles ({best_logit['dist']})")
        ratio_logit = best_logit["ks_stat"] / logit_kde_ks if logit_kde_ks > 0 else float("nan")
        ax.set_title(
            f"QQ of logit(p̂) vs {best_logit['dist']} (KS rank 1)\n"
            f"KS={best_logit['ks_stat']:.3f}  KDE={logit_kde_ks:.3f}  ratio={ratio_logit:.1f}x"
        )
    else:
        ax.text(0.5, 0.5, "No distributions fitted", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("QQ of logit(p̂)")
    ax.set_ylabel("Sample Quantiles logit(p̂)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 3. Predicted probability distribution by outcome
    ax = axes[0, 2]
    ax.hist(y_pred[y_true == 1], bins=40, density=True, alpha=0.5,
            color="steelblue", label="Actual wins (y=1)")
    ax.hist(y_pred[y_true == 0], bins=40, density=True, alpha=0.5,
            color="tomato", label="Actual losses (y=0)")
    ax.axvline(0.5, color="k", ls="--", alpha=0.6)
    ax.set_xlabel("Predicted win probability")
    ax.set_ylabel("Density")
    ax.set_title("Predicted Probability by Outcome\nWider separation = better discrimination")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4. ROC curve (ensemble + sample of individual models)
    ax = axes[1, 0]
    ax.plot(fpr_roc, tpr_roc, "b-", lw=2.5, label=f"Ensemble (AUC={roc_auc:.3f})")
    for col in pred_cols[:5]:
        p_ind = oof[col].values.clip(EPS, 1 - EPS)
        fpr_i, tpr_i, _ = roc_curve(y_true, p_ind)
        auc_i = auc(fpr_i, tpr_i)
        ax.plot(fpr_i, tpr_i, lw=0.8, alpha=0.5, label=f"{col.replace('pred_','')[:20]} ({auc_i:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5)
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_title("ROC Curve")
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(True, alpha=0.3)

    # 5. Log-loss by ensemble-std decile
    ax = axes[1, 1]
    if model_std.std() > 0:
        oof["std_decile"] = pd.qcut(oof["model_std"], 10,
                                    labels=[f"D{i+1}" for i in range(10)],
                                    duplicates="drop")
        ll_dec = oof.groupby("std_decile", observed=True).apply(
            lambda g: pd.Series({
                "logloss": log_loss(g["y_true"], g["y_pred_ensemble"].clip(EPS, 1 - EPS)),
                "n": len(g),
            })
        ).reset_index()
        ax.bar(range(len(ll_dec)), ll_dec["logloss"], color="steelblue", alpha=0.7)
        ax.axhline(ll, color="r", ls="--", lw=1.5, label=f"Overall LL={ll:.4f}")
        ax.set_xticks(range(len(ll_dec)))
        ax.set_xticklabels(
            [f"D{i+1}\nn={int(n)}" for i, n in enumerate(ll_dec["n"])], fontsize=7
        )
        ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
        ax.set_ylabel("Log-loss")
        ax.set_title("Log-Loss by Confidence\nD1 should have lowest log-loss")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(0.5, 0.5, "Single model — no disagreement metric", ha="center", va="center",
                transform=ax.transAxes)

    # 6. Accuracy within probability buckets
    ax = axes[1, 2]
    p_bins = pd.cut(y_pred, bins=np.arange(0, 1.05, 0.05))
    oof["p_bin"] = p_bins
    oof["y_pred_ens"] = y_pred
    oof["y_true_col"] = y_true
    acc_bucket = oof.groupby("p_bin", observed=True).agg(
        acc=("y_true_col", "mean"),
        n=("y_true_col", "count"),
        p_mean=("y_pred_ens", "mean"),
    ).reset_index()
    se_acc = np.sqrt(acc_bucket["acc"] * (1 - acc_bucket["acc"]) / acc_bucket["n"])
    ax.scatter(acc_bucket["p_mean"], acc_bucket["acc"], s=acc_bucket["n"] / 5 + 5,
               alpha=0.7, color="steelblue", label="Observed win rate")
    ax.errorbar(acc_bucket["p_mean"], acc_bucket["acc"], yerr=1.96 * se_acc,
                fmt="none", color="steelblue", alpha=0.4, capsize=2)
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed win rate")
    ax.set_title("Win Rate by Prob Bucket\n(size ∝ N in bucket)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 7. Brier score by ensemble-std decile
    ax = axes[2, 0]
    if model_std.std() > 0 and "std_decile" in oof.columns:
        brier_dec = oof.groupby("std_decile", observed=True).apply(
            lambda g: pd.Series({
                "brier": brier_score_loss(g["y_true"], g["y_pred_ensemble"].clip(EPS, 1 - EPS)),
                "n": len(g),
            })
        ).reset_index()
        ax.bar(range(len(brier_dec)), brier_dec["brier"], color="steelblue", alpha=0.7)
        ax.axhline(brier, color="r", ls="--", lw=1.5, label=f"Overall Brier={brier:.4f}")
        ax.set_xticks(range(len(brier_dec)))
        ax.set_xticklabels(
            [f"D{i+1}\nn={int(n)}" for i, n in enumerate(brier_dec["n"])], fontsize=7
        )
        ax.set_xlabel("Ensemble Std Decile")
        ax.set_ylabel("Brier Score")
        ax.set_title("Brier Score by Confidence")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(0.5, 0.5, "Single model — no disagreement metric", ha="center", va="center",
                transform=ax.transAxes)

    # 8. Per-season accuracy
    ax = axes[2, 1]
    if "season" in oof.columns and oof["season"].notna().any():
        s_acc = oof.groupby("season", observed=True).apply(
            lambda g: pd.Series({
                "acc": (g["y_pred_ensemble"].clip(EPS, 1 - EPS).round() == g["y_true"]).mean(),
                "n": len(g),
            })
        ).reset_index().sort_values("season")
        se_s = np.sqrt(s_acc["acc"] * (1 - s_acc["acc"]) / s_acc["n"])
        ax.plot(range(len(s_acc)), s_acc["acc"], "b-o", lw=2, markersize=4)
        ax.fill_between(range(len(s_acc)),
                        s_acc["acc"] - 1.96 * se_s,
                        s_acc["acc"] + 1.96 * se_s,
                        alpha=0.15, color="blue")
        ax.axhline(acc, color="r", ls="--", lw=1.5, label=f"Overall Acc={acc:.3f}")
        ax.axhline(0.5, color="k", ls=":", alpha=0.4, label="Baseline 50%")
        ax.set_xticks(range(0, len(s_acc), max(1, len(s_acc) // 8)))
        ax.set_xticklabels(s_acc["season"].iloc[::max(1, len(s_acc) // 8)],
                           rotation=45, fontsize=7)
        ax.set_xlabel("Season")
        ax.set_ylabel("Accuracy")
        ax.set_title("Per-Season Accuracy")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "Season data not available", ha="center", va="center",
                transform=ax.transAxes)

    # 9. Specialist correlation heatmap
    ax = axes[2, 2]
    if len(pred_cols) > 1:
        corr = oof[pred_cols].corr()
        short_names = [c.replace("pred_", "")[:15] for c in pred_cols]
        im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
        ax.set_xticks(range(len(pred_cols)))
        ax.set_yticks(range(len(pred_cols)))
        ax.set_xticklabels(short_names, rotation=60, ha="right", fontsize=6)
        ax.set_yticklabels(short_names, fontsize=6)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Specialist Correlation\nLow correlation = good diversity")
    else:
        ax.text(0.5, 0.5, "Single model", ha="center", va="center", transform=ax.transAxes)

    # 10. ECE bar chart
    # ECE = Σ (|B_m| / N) * |acc(B_m) − conf(B_m)|  where B_m are equal-width bins
    ax = axes[3, 0]
    n_ece_bins = 15
    ece_bin_edges = np.linspace(0, 1, n_ece_bins + 1)
    ece_acc, ece_conf, ece_counts = [], [], []
    for lo, hi in zip(ece_bin_edges[:-1], ece_bin_edges[1:]):
        mask = (y_pred >= lo) & (y_pred < hi)
        if mask.sum() > 0:
            ece_acc.append(y_true[mask].mean())
            ece_conf.append(y_pred[mask].mean())
            ece_counts.append(mask.sum())
        else:
            ece_acc.append(np.nan)
            ece_conf.append(np.nan)
            ece_counts.append(0)
    ece_acc = np.array(ece_acc)
    ece_conf = np.array(ece_conf)
    ece_counts = np.array(ece_counts)
    valid = ece_counts > 0
    ece_val = (ece_counts[valid] / ece_counts[valid].sum() * np.abs(ece_acc[valid] - ece_conf[valid])).sum()
    log.info(f"[{target}] ECE = {ece_val:.4f}")
    bar_colors = ["tomato" if a > c else "steelblue"
                  for a, c in zip(ece_acc[valid], ece_conf[valid])]
    ax.bar(ece_conf[valid], ece_acc[valid] - ece_conf[valid],
           width=1 / n_ece_bins * 0.8, color=bar_colors, alpha=0.7, align="center")
    ax.axhline(0, color="k", ls="--", lw=1, alpha=0.6)
    ax.set_xlabel("Mean predicted probability (bin)")
    ax.set_ylabel("Observed − Predicted (gap)")
    ax.set_title(f"ECE = {ece_val:.4f}\nRed=overconfident, Blue=underconfident")
    ax.grid(True, alpha=0.3, axis="y")

    # 11. Brier decomposition: Brier = Reliability − Resolution + Uncertainty
    # Murphy (1973) decomposition via equal-width bins
    ax = axes[3, 1]
    base_rate = y_true.mean()
    uncertainty = base_rate * (1 - base_rate)
    reliability_terms = ece_counts[valid] / len(y_true) * (ece_conf[valid] - ece_acc[valid]) ** 2
    resolution_terms  = ece_counts[valid] / len(y_true) * (ece_acc[valid] - base_rate) ** 2
    reliability = reliability_terms.sum()
    resolution  = resolution_terms.sum()
    brier_decomp = reliability - resolution + uncertainty
    log.info(f"[{target}] Brier decomp: REL={reliability:.4f}, RES={resolution:.4f}, UNC={uncertainty:.4f}, "
             f"sum={brier_decomp:.4f} (direct={brier:.4f})")
    components = ["Reliability\n(↓ better)", "Resolution\n(↑ better)", "Uncertainty\n(irreducible)"]
    values     = [reliability, resolution, uncertainty]
    bar_c      = ["tomato", "steelblue", "gray"]
    bars = ax.bar(components, values, color=bar_c, alpha=0.8)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0005,
                f"{val:.4f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Component value")
    ax.set_title(f"Brier Decomposition\nBrier = REL − RES + UNC = {brier_decomp:.4f}")
    ax.grid(True, alpha=0.3, axis="y")

    # 12. Sharpness histogram
    ax = axes[3, 2]
    ax.hist(y_pred, bins=50, color="steelblue", alpha=0.7, edgecolor="none")
    ax.axvline(0.5, color="k", ls="--", alpha=0.6, label="0.5")
    frac_decisive = ((y_pred < 0.4) | (y_pred > 0.6)).mean()
    ax.set_xlabel("Predicted win probability")
    ax.set_ylabel("Count")
    ax.set_title(f"Sharpness (Predicted Prob Distribution)\n"
                 f"{frac_decisive:.1%} of predictions outside [0.4, 0.6]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out_path = out_dir / f"{target}_diagnostics.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"[{target}] Saved: {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_target(target: str) -> None:
    cfg = _TARGET_CFG.get(target)
    if cfg is None:
        raise ValueError(f"Unknown target '{target}'. Known: {list(_TARGET_CFG)}")

    oof = _load_oof(target)
    oof = _attach_season(oof)

    out_dir = OUTPUT_ROOT / target / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    if cfg["task"] == "clf":
        _plot_classification(target, oof, out_dir)
    else:
        _plot_regression(target, oof, out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="OOF diagnostic plots for any trained target")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", choices=list(_TARGET_CFG), help="Single target to plot")
    group.add_argument("--all", action="store_true", help="Plot all trained targets")
    args = parser.parse_args()

    targets = TRAINED_TARGETS if args.all else [args.target]
    for t in targets:
        try:
            run_target(t)
        except FileNotFoundError as e:
            log.warning(f"[{t}] Skipped: {e}")


if __name__ == "__main__":
    main()
