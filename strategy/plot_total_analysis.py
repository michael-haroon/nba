"""
plot_total_analysis.py
----------------------
Generate LOYO OOF residuals for the total model, then produce a comprehensive
3x3 diagnostic plot.

LOYO OOF is computed by refitting each specialist on all seasons except the
held-out season, then predicting. This avoids in-sample bias from the pkl
models which were trained on all data. Results are cached to
  strategy/output/nba/total/ensemble_oof.csv
so subsequent runs skip the ~6min refit.

Panels:
  1. Error distribution with Normal + t-dist fit
  2. QQ vs Normal (tail departure)
  3. QQ vs fitted t-distribution (should lie on diagonal)
  4. Heteroscedasticity: error std vs predicted total
  5. MAE by confidence decile (ensemble model disagreement)
  6. MAE by predicted total bucket
  7. Tail probability: Normal vs t-dist vs historical
  8. Exceedance ratio: how much does Normal underprice tails?
  9. Per-season MAE — temporal drift

Run:
    conda run -n pred python -m strategy.plot_total_analysis
"""
from __future__ import annotations

import logging
import pickle
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

PKL_PATH  = Path("strategy/output/nba/total/ensemble.pkl")
OOF_CACHE = Path("strategy/output/nba/total/ensemble_oof.csv")
GAME_PARQUET = Path("output/features/game_features.parquet")
OUT_DIR   = Path("strategy/output/nba/ensemble/plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SKIP_SEASONS = {"2019-20"}
MIN_TRAIN_SEASONS = 3


def _make_oof(bundle: dict, df: pd.DataFrame) -> pd.DataFrame:
    """LOYO OOF: for each season, refit specialists on all other seasons, predict."""
    features_all = sorted(set(f for s in bundle["specialists"] for f in s["features"]))
    feat_avail = [f for f in features_all if f in df.columns]
    needed = feat_avail + ["target_total", "season"]
    sub = df[needed].dropna(subset=["target_total", "season"]).copy()

    seasons_ordered = sorted(s for s in sub["season"].unique() if s not in SKIP_SEASONS)
    log.info(f"LOYO over {len(seasons_ordered)} seasons, {len(sub):,} rows")

    oof_rows = []
    for i, test_season in enumerate(seasons_ordered):
        train_seasons = [s for s in seasons_ordered[:i] if s not in SKIP_SEASONS]
        if len(train_seasons) < MIN_TRAIN_SEASONS:
            log.info(f"  Skip {test_season} (only {len(train_seasons)} train seasons)")
            continue

        train = sub[sub["season"].isin(train_seasons)]
        test  = sub[sub["season"] == test_season]
        if len(test) == 0:
            continue

        y_tr  = train["target_total"].values
        y_te  = test["target_total"].values
        preds_per_spec = []
        weights = []

        for spec in bundle["specialists"]:
            feat = [f for f in spec["features"] if f in feat_avail]
            if not feat:
                continue

            X_tr = train[feat].copy()
            X_te = test[feat].copy()

            if spec.get("impute_median"):
                med = {k: v for k, v in spec["impute_median"].items() if k in feat}
                X_tr = X_tr.fillna(pd.Series(med))
                X_te = X_te.fillna(pd.Series(med))
            if spec.get("needs_scaling") and spec.get("scale_mean"):
                mu  = pd.Series({k: v for k, v in spec["scale_mean"].items() if k in feat})
                std = pd.Series({k: v for k, v in spec["scale_std"].items() if k in feat})
                std = std.replace(0, 1)
                X_tr = (X_tr - mu) / std
                X_te = (X_te - mu) / std

            # Refit the same model class with same hyperparams
            model_clone = type(spec["model"])(**spec["model"].get_params())
            try:
                model_clone.fit(X_tr, y_tr)
                p = model_clone.predict(X_te)
            except Exception as e:
                log.warning(f"  {spec['model_name']} fold {test_season}: {e}")
                continue

            preds_per_spec.append(p)
            weights.append(float(spec["weight"]))

        if not preds_per_spec:
            continue

        w = np.array(weights)
        w = w / w.sum()
        ensemble_pred = np.dot(w, np.array(preds_per_spec))

        for j, idx in enumerate(test.index):
            row = {"y_true": y_te[j], "y_pred_ensemble": ensemble_pred[j], "season": test_season}
            for k, p in enumerate(preds_per_spec):
                row[f"pred_spec{k}"] = p[j]
            oof_rows.append(row)

        log.info(f"  {test_season}: MAE={np.abs(y_te - ensemble_pred).mean():.2f}  n={len(y_te)}")

    return pd.DataFrame(oof_rows)


def run():
    log.info("Loading total ensemble pkl...")
    with open(PKL_PATH, "rb") as f:
        bundle = pickle.load(f)

    if OOF_CACHE.exists():
        log.info(f"Loading cached OOF from {OOF_CACHE}")
        oof = pd.read_csv(OOF_CACHE)
    else:
        log.info("No OOF cache found — running LOYO CV (this takes ~6 min)...")
        df = pd.read_parquet(GAME_PARQUET)
        oof = _make_oof(bundle, df)
        oof.to_csv(OOF_CACHE, index=False)
        log.info(f"OOF cached to {OOF_CACHE}")

    errors = (oof["y_true"] - oof["y_pred_ensemble"]).values
    y_pred = oof["y_pred_ensemble"].values
    y_true = oof["y_true"].values
    pred_cols = [c for c in oof.columns if c.startswith("pred_spec")]
    model_std = oof[pred_cols].std(axis=1).values if len(pred_cols) > 1 else np.zeros(len(oof))

    mae    = np.abs(errors).mean()
    bias   = errors.mean()
    sigma  = errors.std()

    # Fit t-distribution
    t_params = t_dist.fit(errors, floc=0)
    t_df, t_loc, t_scale = t_params

    ks_t = stats.kstest(errors, "t", args=(t_df, t_loc, t_scale))
    ks_n = stats.kstest(errors, "norm", args=(bias, sigma))

    log.info(f"N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f}")
    log.info(f"t-dist: df={t_df:.2f}, scale={t_scale:.2f}")
    log.info(f"KS: t-dist p={ks_t.pvalue:.4f} | Normal p={ks_n.pvalue:.6f}")

    # Load historical totals for tail comparison
    df_full = pd.read_parquet(GAME_PARQUET, columns=["target_total", "season", "season_type"])
    all_totals = df_full["target_total"].dropna().values
    playoff_totals = df_full[df_full["season_type"] == "Playoffs"]["target_total"].dropna().values

    oof["abs_error"] = np.abs(errors)
    oof["error"] = errors
    oof["model_std"] = model_std

    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    fig.suptitle(
        f"Total Model — LOYO OOF Diagnostics  (N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f})",
        fontsize=13, y=1.01)

    x_dense = np.linspace(-80, 80, 600)

    # ── 1. Error distribution ────────────────────────────────────────────────
    ax = axes[0, 0]
    ax.hist(errors, bins=100, density=True, alpha=0.6, color="steelblue", edgecolor="none",
            label="LOYO residuals")
    ax.plot(x_dense, norm.pdf(x_dense, 0, sigma), "r-", lw=2, label=f"Normal (σ={sigma:.1f})")
    ax.plot(x_dense, t_dist.pdf(x_dense, t_df, t_loc, t_scale), "g--", lw=2,
            label=f"t-dist (df={t_df:.1f}, s={t_scale:.1f})")
    ax.axvline(0, color="k", ls="--", alpha=0.4)
    ax.set_xlabel("Residual (actual − predicted)")
    ax.set_ylabel("Density")
    ax.set_title(f"Error Distribution\nKS: t p={ks_t.pvalue:.3f} | Normal p={ks_n.pvalue:.5f}")
    ax.legend(fontsize=8)
    ax.set_xlim(-80, 80)
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
    ax.set_title("QQ Plot vs Normal\nTail departure indicates fat tails")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 3. QQ vs fitted t-distribution ───────────────────────────────────────
    ax = axes[0, 2]
    (osm_t, osr_t), (slope_t, intercept_t, r_t) = stats.probplot(
        errors, dist=t_dist, sparams=(t_df, t_loc, t_scale))
    ax.scatter(osm_t, osr_t, s=2, alpha=0.2, color="steelblue")
    ax.plot(osm_t, slope_t * np.array(osm_t) + intercept_t, "g-", lw=2,
            label=f"t-dist fit R²={r_t**2:.4f}")
    tail_t = np.abs(osm_t) > 2
    ax.scatter(np.array(osm_t)[tail_t], np.array(osr_t)[tail_t],
               s=8, alpha=0.5, color="orange", zorder=5, label="Tail |z|>2")
    ax.set_xlabel(f"Theoretical Quantiles (t, df={t_df:.1f})")
    ax.set_ylabel("Sample Quantiles (residuals)")
    ax.set_title("QQ Plot vs t-distribution\nShould lie on diagonal")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 4. Heteroscedasticity ─────────────────────────────────────────────────
    ax = axes[1, 0]
    ax.scatter(y_pred, errors, s=2, alpha=0.08, color="steelblue")
    bins = pd.cut(y_pred, bins=30)
    bin_stats = oof.groupby(bins, observed=True)["error"].agg(["mean", "std", "count"])
    bin_centers = [(b.left + b.right) / 2 for b in bin_stats.index]
    ax.plot(bin_centers, bin_stats["std"], "r-o", lw=2, markersize=4, label="Binned σ(E)")
    ax.axhline(sigma, color="k", ls="--", alpha=0.5, label=f"Overall σ={sigma:.1f}")
    ax.set_xlabel("Predicted total (Ŷ)")
    ax.set_ylabel("Error / Error std")
    ax.set_title("Heteroscedasticity: Error vs Prediction\nFlat = homoscedastic")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 5. MAE by confidence decile ──────────────────────────────────────────
    ax = axes[1, 1]
    if model_std.std() > 0:
        oof["std_decile"] = pd.qcut(oof["model_std"], 10, labels=[f"D{i+1}" for i in range(10)])
        mae_dec = oof.groupby("std_decile", observed=True).agg(
            mae=("abs_error", "mean"), n=("abs_error", "count"),
            std_mean=("model_std", "mean")).reset_index()
        se_mae = mae_dec["mae"] / np.sqrt(mae_dec["n"])
        ax.bar(range(len(mae_dec)), mae_dec["mae"], color="steelblue", alpha=0.7)
        ax.errorbar(range(len(mae_dec)), mae_dec["mae"], yerr=1.96 * se_mae,
                    fmt="none", color="black", capsize=3)
        ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
        ax.set_xticks(range(len(mae_dec)))
        ax.set_xticklabels([f"D{i+1}\n{v:.2f}" for i, v in enumerate(mae_dec["std_mean"])], fontsize=7)
        ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
        ax.set_ylabel("MAE (pts)")
        ax.set_title("MAE by Model Disagreement")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(0.5, 0.5, "Single specialist — no disagreement metric", ha="center", va="center")

    # ── 6. MAE by predicted total bucket ─────────────────────────────────────
    ax = axes[1, 2]
    oof["pred_bucket"] = pd.cut(y_pred, bins=np.arange(160, 260, 10))
    mae_bucket = oof.groupby("pred_bucket", observed=True).agg(
        mae=("abs_error", "mean"), n=("abs_error", "count"),
        pred_mean=("y_pred_ensemble", "mean")).reset_index()
    ax.bar(range(len(mae_bucket)), mae_bucket["mae"], color="steelblue", alpha=0.7)
    ax.axhline(mae, color="r", ls="--", lw=1.5, label=f"Overall MAE={mae:.2f}")
    ax.set_xticks(range(0, len(mae_bucket), 2))
    ax.set_xticklabels([f"{v:.0f}" for v in mae_bucket["pred_mean"].iloc[::2]], fontsize=8, rotation=30)
    ax.set_xlabel("Predicted total (pts)")
    ax.set_ylabel("MAE (pts)")
    ax.set_title("MAE by Predicted Total\nHigh/low totals harder to predict?")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── 7. Tail probability (log scale) ─────────────────────────────────────
    ax = axes[2, 0]
    # For totals, tail = games far from the mean (very high or very low scoring)
    total_mean = np.mean(all_totals)
    dev_pred = np.abs(y_pred - total_mean)   # how far prediction is from league avg
    dev_err  = np.abs(errors)
    thresholds = np.arange(5, 40, 1)
    p_norm  = 2 * (1 - norm.cdf(thresholds / sigma))
    p_t_res = 2 * (1 - t_dist.cdf(thresholds / t_scale, df=t_df))
    p_hist  = np.array([(dev_err >= t).mean() for t in thresholds])
    ax.semilogy(thresholds, p_norm, "r-", lw=2, label=f"Normal (σ={sigma:.1f})")
    ax.semilogy(thresholds, p_t_res, "g--", lw=2, label=f"t-dist (df={t_df:.0f})")
    ax.semilogy(thresholds, p_hist, "b-", lw=1.5, label="Empirical OOF")
    ax.set_xlabel("|Residual| Threshold (pts)")
    ax.set_ylabel("P(|residual| ≥ threshold)")
    ax.set_title("Tail Probabilities of Total Residuals")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(1e-4, 1)

    # ── 8. Exceedance ratio: hist / Normal ────────────────────────────────────
    ax = axes[2, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_emp = np.where(p_norm > 0, p_hist / p_norm, np.nan)
        ratio_t   = np.where(p_norm > 0, p_t_res / p_norm, np.nan)
    ax.plot(thresholds, ratio_emp, "b-o", lw=2, markersize=3, label="Empirical OOF / Normal")
    ax.plot(thresholds, ratio_t, "g--", lw=2, label="t-dist / Normal")
    ax.axhline(1.0, color="r", ls="--", alpha=0.7, label="Correct")
    for t_val in [15, 20, 25]:
        idx = np.argmin(np.abs(thresholds - t_val))
        if not np.isnan(ratio_emp[idx]):
            ax.annotate(f"{ratio_emp[idx]:.1f}x", (thresholds[idx], ratio_emp[idx]),
                        textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("|Residual| Threshold (pts)")
    ax.set_ylabel("Actual / Normal model")
    ax.set_title("Tail Underpricing Ratio\n>1 = Normal underestimates extremes")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 5)

    # ── 9. Per-season MAE ─────────────────────────────────────────────────────
    ax = axes[2, 2]
    if "season" in oof.columns and oof["season"].notna().any():
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
        ax.text(0.5, 0.5, "No season metadata in OOF", ha="center", va="center")

    plt.tight_layout()
    out_path = OUT_DIR / "total_analysis.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Saved: {out_path}")

    # ── Console summary ──────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("TOTAL MODEL ANALYSIS SUMMARY")
    log.info("=" * 60)
    log.info(f"  N={len(oof):,}, MAE={mae:.2f}, σ={sigma:.2f}, bias={bias:+.2f}")
    log.info(f"  t-dist: df={t_df:.2f}, scale={t_scale:.2f}")
    log.info(f"  KS: t-dist p={ks_t.pvalue:.4f} | Normal p={ks_n.pvalue:.6f}")
    log.info(f"  Accuracy: ±5={( np.abs(errors)<=5).mean():.1%}, "
             f"±10={( np.abs(errors)<=10).mean():.1%}, "
             f"±15={( np.abs(errors)<=15).mean():.1%}")
    log.info("")
    log.info(f"  Tail exceedance (OOF empirical vs Normal):")
    for t_val in [10, 15, 20, 25, 30]:
        idx = np.argmin(np.abs(thresholds - t_val))
        log.info(f"    |residual|≥{t_val}: Normal={p_norm[idx]:.2%}, "
                 f"t-dist={p_t_res[idx]:.2%}, empirical={p_hist[idx]:.2%}, "
                 f"ratio={ratio_emp[idx]:.1f}x")


if __name__ == "__main__":
    run()
