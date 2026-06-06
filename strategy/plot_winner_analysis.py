"""
plot_winner_analysis.py
-----------------------
Comprehensive winner model OOF diagnostics. 3x3 panel plot.

  1. Calibration curve (reliability diagram + 95% CI)
  2. QQ plot: logit(p_pred) vs normal — checks if predicted probabilities
     are well-spread and not clumped (a classification analogue to residual QQ)
  3. Predicted probability distribution split by outcome
  4. ROC curve (ensemble + individual models)
  5. Accuracy by model disagreement decile
  6. Precision-recall by predicted probability bucket
  7. Log-loss by confidence decile (ensemble std)
  8. Per-season accuracy — checks for temporal drift
  9. Model correlation heatmap (are specialists diverse?)

Run:
    conda run -n pred python -m strategy.plot_winner_analysis
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_curve, auc, brier_score_loss, log_loss

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

OOF_PATH = Path("strategy/output/nba/ensemble/winner_ensemble_oof.csv")
GAME_PARQUET = Path("output/features/game_features.parquet")
OUT_DIR = Path("strategy/output/nba/ensemble/plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EPS = 1e-6


def run():
    log.info("Loading winner OOF data...")
    oof = pd.read_csv(OOF_PATH)
    y_true = oof["y_true"].values
    y_pred = oof["y_pred_ensemble"].values.clip(EPS, 1 - EPS)
    pred_cols = [c for c in oof.columns if c.startswith("pred_")]
    model_std = oof[pred_cols].std(axis=1).values

    brier = brier_score_loss(y_true, y_pred)
    acc = (y_pred.round() == y_true).mean()
    ll = log_loss(y_true, y_pred)
    fpr_roc, tpr_roc, _ = roc_curve(y_true, y_pred)
    roc_auc = auc(fpr_roc, tpr_roc)
    log.info(f"N={len(oof)}, Acc={acc:.3f}, AUC={roc_auc:.3f}, Brier={brier:.4f}, LogLoss={ll:.4f}")

    # Load season for per-season panel
    df_meta = pd.read_parquet(GAME_PARQUET, columns=["season"])
    df_meta = df_meta.dropna()
    if len(df_meta) == len(oof):
        oof["season"] = df_meta["season"].values
    else:
        oof["season"] = None
    oof["model_std"] = model_std
    oof["correct"] = (y_pred.round() == y_true).astype(int)
    oof["y_pred"] = y_pred

    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    fig.suptitle(f"Winner Model — OOF Diagnostics  (N={len(oof):,}, AUC={roc_auc:.3f}, Acc={acc:.3f}, Brier={brier:.4f})",
                 fontsize=13, y=1.01)

    # ── 1. Calibration curve ─────────────────────────────────────────────────
    ax = axes[0, 0]
    n_bins = 15
    prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=n_bins, strategy="quantile")
    ax.plot(prob_pred, prob_true, "b-o", lw=2, markersize=5, label="Ensemble")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect")
    counts, _ = np.histogram(y_pred, bins=n_bins)
    counts = counts[counts > 0]
    se = np.sqrt(prob_true * (1 - prob_true) / np.maximum(counts, 1))
    ax.fill_between(prob_pred, (prob_true - 1.96 * se).clip(0), (prob_true + 1.96 * se).clip(0, 1),
                    alpha=0.15, color="blue", label="95% CI")
    ax.set_xlabel("Mean Predicted P(home wins)")
    ax.set_ylabel("Actual win rate")
    ax.set_title("Calibration Curve")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 2. QQ plot of logit(p_pred) ──────────────────────────────────────────
    ax = axes[0, 1]
    logit_p = np.log(y_pred / (1 - y_pred))
    (osm, osr), (slope, intercept, r) = stats.probplot(logit_p, dist="norm")
    ax.scatter(osm, osr, s=2, alpha=0.2, color="steelblue")
    ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=2, label=f"Normal fit R²={r**2:.4f}")
    tail_mask = np.abs(osm) > 2
    ax.scatter(np.array(osm)[tail_mask], np.array(osr)[tail_mask],
               s=8, alpha=0.5, color="red", zorder=5, label="Tail |z|>2")
    ax.set_xlabel("Theoretical Quantiles (Normal)")
    ax.set_ylabel("Sample Quantiles (logit predictions)")
    ax.set_title("QQ: logit(p̂) vs Normal\nChecks spread of predicted probabilities")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 3. Predicted probability distribution by outcome ─────────────────────
    ax = axes[0, 2]
    wins = y_pred[y_true == 1]
    losses = y_pred[y_true == 0]
    bins = np.linspace(0, 1, 30)
    ax.hist(losses, bins=bins, density=True, alpha=0.5, color="red", label=f"Home loses (n={len(losses):,})")
    ax.hist(wins, bins=bins, density=True, alpha=0.5, color="blue", label=f"Home wins (n={len(wins):,})")
    kde_x = np.linspace(0.05, 0.95, 200)
    ax.plot(kde_x, stats.gaussian_kde(wins)(kde_x), "b-", lw=2)
    ax.plot(kde_x, stats.gaussian_kde(losses)(kde_x), "r-", lw=2)
    ax.axvline(0.5, color="k", ls="--", alpha=0.6, label="Threshold 0.5")
    ax.set_xlabel("Predicted P(home wins)")
    ax.set_ylabel("Density")
    ax.set_title("Predicted Probability by Outcome")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── 4. ROC curve ─────────────────────────────────────────────────────────
    ax = axes[1, 0]
    ax.plot(fpr_roc, tpr_roc, "b-", lw=2.5, label=f"Ensemble AUC={roc_auc:.3f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Random")
    for col in pred_cols[:6]:
        p = oof[col].values.clip(EPS, 1 - EPS)
        fi, ti, _ = roc_curve(y_true, p)
        ai = auc(fi, ti)
        ax.plot(fi, ti, alpha=0.3, lw=1, label=f"{col.replace('pred_','')[:18]} {ai:.3f}")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(f"ROC Curve — AUC={roc_auc:.3f}")
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(True, alpha=0.3)

    # ── 5. Accuracy by confidence decile ─────────────────────────────────────
    ax = axes[1, 1]
    oof["std_decile"] = pd.qcut(oof["model_std"], 10,
                                labels=[f"D{i+1}" for i in range(10)])
    summary = oof.groupby("std_decile", observed=True).agg(
        acc=("correct", "mean"), n=("correct", "count"),
        std_mean=("model_std", "mean")).reset_index()
    se_acc = np.sqrt(summary["acc"] * (1 - summary["acc"]) / summary["n"])
    ax.bar(range(len(summary)), summary["acc"], color="steelblue", alpha=0.7)
    ax.errorbar(range(len(summary)), summary["acc"], yerr=1.96 * se_acc,
                fmt="none", color="black", capsize=3)
    ax.axhline(acc, color="r", ls="--", lw=1.5, label=f"Overall {acc:.3f}")
    ax.set_xticks(range(len(summary)))
    ax.set_xticklabels([f"D{i+1}\n{v:.3f}" for i, v in enumerate(summary["std_mean"])], fontsize=7)
    ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy by Model Disagreement")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0.5, 0.8)

    # ── 6. Precision by predicted probability bucket ──────────────────────────
    ax = axes[1, 2]
    oof["p_bucket"] = pd.cut(oof["y_pred"], bins=np.arange(0, 1.05, 0.05))
    prec_df = oof.groupby("p_bucket", observed=True).agg(
        prec=("correct", "mean"), n=("correct", "count"),
        p_mean=("y_pred", "mean")).reset_index()
    se_prec = np.sqrt(prec_df["prec"] * (1 - prec_df["prec"]) / prec_df["n"].clip(1))
    ax.bar(range(len(prec_df)), prec_df["prec"], color="green", alpha=0.6)
    ax.errorbar(range(len(prec_df)), prec_df["prec"], yerr=1.96 * se_prec,
                fmt="none", color="black", capsize=2)
    ax.plot(range(len(prec_df)), prec_df["p_mean"], "r--", lw=1.5, label="Perfect calib.")
    ax.set_xticks(range(0, len(prec_df), 4))
    ax.set_xticklabels([f"{v:.2f}" for v in prec_df["p_mean"].iloc[::4]], fontsize=8, rotation=30)
    ax.set_xlabel("Predicted probability bucket")
    ax.set_ylabel("Actual win rate")
    ax.set_title("Precision by Probability Bucket")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── 7. Log-loss by confidence decile ─────────────────────────────────────
    ax = axes[2, 0]
    oof["logloss"] = -(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))
    ll_summary = oof.groupby("std_decile", observed=True).agg(
        ll=("logloss", "mean"), n=("logloss", "count"),
        std_mean=("model_std", "mean")).reset_index()
    ax.bar(range(len(ll_summary)), ll_summary["ll"], color="orange", alpha=0.7)
    ax.axhline(ll, color="r", ls="--", lw=1.5, label=f"Overall {ll:.4f}")
    ax.set_xticks(range(len(ll_summary)))
    ax.set_xticklabels([f"D{i+1}" for i in range(len(ll_summary))], fontsize=8)
    ax.set_xlabel("Ensemble Std Decile (D1=most confident)")
    ax.set_ylabel("Log-Loss")
    ax.set_title("Log-Loss by Model Disagreement\nLow std should mean lower loss")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── 8. Per-season accuracy ────────────────────────────────────────────────
    ax = axes[2, 1]
    if oof["season"].notna().any():
        season_acc = oof.groupby("season", observed=True).agg(
            acc=("correct", "mean"), n=("correct", "count")).reset_index()
        season_acc = season_acc.sort_values("season")
        se_s = np.sqrt(season_acc["acc"] * (1 - season_acc["acc"]) / season_acc["n"])
        ax.plot(range(len(season_acc)), season_acc["acc"], "b-o", lw=2, markersize=4)
        ax.fill_between(range(len(season_acc)),
                        (season_acc["acc"] - 1.96 * se_s).clip(0),
                        (season_acc["acc"] + 1.96 * se_s).clip(0, 1),
                        alpha=0.15, color="blue")
        ax.axhline(acc, color="r", ls="--", lw=1.5, label=f"Overall {acc:.3f}")
        ax.set_xticks(range(0, len(season_acc), 3))
        ax.set_xticklabels(season_acc["season"].iloc[::3], rotation=45, fontsize=7)
        ax.set_xlabel("Season")
        ax.set_ylabel("Accuracy")
        ax.set_title("Per-Season Accuracy (temporal drift?)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "Season data unavailable", ha="center", va="center")

    # ── 9. Model correlation heatmap ──────────────────────────────────────────
    ax = axes[2, 2]
    if len(pred_cols) > 1:
        corr = oof[pred_cols].corr()
        short_names = [c.replace("pred_", "")[:16] for c in pred_cols]
        im = ax.imshow(corr.values, vmin=0.5, vmax=1.0, cmap="Blues")
        ax.set_xticks(range(len(pred_cols)))
        ax.set_yticks(range(len(pred_cols)))
        ax.set_xticklabels(short_names, rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(short_names, fontsize=7)
        for i in range(len(pred_cols)):
            for j in range(len(pred_cols)):
                ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=6)
        plt.colorbar(im, ax=ax)
        ax.set_title("Specialist Correlation (lower = more diverse)")
    else:
        ax.text(0.5, 0.5, "Single model — no correlation", ha="center", va="center")

    plt.tight_layout()
    out_path = OUT_DIR / "winner_analysis.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Saved: {out_path}")

    # ── Console summary ──────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("WINNER MODEL ANALYSIS SUMMARY")
    log.info("=" * 60)
    log.info(f"  N={len(oof):,}, Acc={acc:.3f}, AUC={roc_auc:.3f}, Brier={brier:.4f}, LogLoss={ll:.4f}")
    log.info(f"  Ensemble std range: [{model_std.min():.4f}, {model_std.max():.4f}]")
    log.info("")
    log.info(f"  {'Decile':<8} {'Acc':>6} {'LogLoss':>9} {'N':>6} {'Mean Std':>10}")
    log.info(f"  {'-'*43}")
    ll_by_decile = oof.groupby("std_decile", observed=True).agg(
        acc=("correct", "mean"), ll=("logloss", "mean"),
        n=("logloss", "count"), std_mean=("model_std", "mean"))
    for dec, row in ll_by_decile.iterrows():
        log.info(f"  {str(dec):<8} {row['acc']:>6.3f} {row['ll']:>9.4f} {int(row['n']):>6} {row['std_mean']:>10.4f}")


if __name__ == "__main__":
    run()
