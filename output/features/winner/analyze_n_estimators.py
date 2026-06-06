"""
Compares distribution richness of n_estimators=300 (SFI, CFI-MDA)
vs n_estimators=1000 (residualized MDA, PCA-MDA) across all 30 folds.

Question: Does one produce a better-behaved, more informative distribution?
Criteria: signal-to-noise (mean/std), fraction of features with std < mean,
          spread across features, distribution shape (QQ, histogram, CV).
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
from pathlib import Path

BASE = Path(__file__).parent
OUT  = BASE

# ── Load raw per-fold data ────────────────────────────────────────────────────
# 300-tree methods
sfi_raw      = pd.read_csv(BASE / "importance_sfi.csv",           index_col=0)   # summary only; no raw folds saved
sfi_summary  = sfi_raw  # mean/std/null_log_loss per feature
cfi_raw_df   = pd.read_csv(BASE / "importance_cfi_mda_raw.csv",   index_col=0)   # (30 folds × 3 clusters)

# 1000-tree methods
resid_raw    = pd.read_csv(BASE / "importance_resid_mda_raw.csv", index_col=0)   # (30 folds × n_features)
pca_raw      = pd.read_csv(BASE / "importance_pca_mda_raw.csv",   index_col=0)   # (30 folds × n_features)

# Also load summaries
resid_sum    = pd.read_csv(BASE / "importance_resid_mda.csv",     index_col=0)
pca_sum      = pd.read_csv(BASE / "importance_pca_mda.csv",       index_col=0)
cfi_sum      = pd.read_csv(BASE / "importance_cfi_mda.csv",       index_col=0)

print(f"SFI summary:       {sfi_summary.shape}  (features × [mean, std, null_log_loss])")
print(f"CFI-MDA raw:       {cfi_raw_df.shape}   (folds × clusters)")
print(f"Resid-MDA raw:     {resid_raw.shape}     (folds × features)")
print(f"PCA-MDA raw:       {pca_raw.shape}       (folds × features)")

# ── Helper: per-feature stats from raw fold matrix ────────────────────────────
def fold_stats(raw_df):
    """Returns DataFrame with mean, std, CV (std/|mean|), snr (|mean|/std) per feature."""
    m = raw_df.mean()
    s = raw_df.std()
    cv  = s / (m.abs() + 1e-15)
    snr = m.abs() / (s + 1e-15)
    return pd.DataFrame({"mean": m, "std": s, "cv": cv, "snr": snr})

resid_stats = fold_stats(resid_raw)
pca_stats   = fold_stats(pca_raw)

# SFI has no per-fold raw, only summary mean/std
sfi_stats = sfi_summary[["mean", "std"]].copy()
sfi_stats["cv"]  = sfi_stats["std"] / (sfi_stats["mean"].abs() + 1e-15)
sfi_stats["snr"] = sfi_stats["mean"].abs() / (sfi_stats["std"] + 1e-15)

# CFI only has 3 clusters — treat as aggregate check
cfi_fold_stats = fold_stats(cfi_raw_df)

# ── Summary table ─────────────────────────────────────────────────────────────
def describe_stats(stats_df, name, n_estimators):
    m = stats_df["mean"]
    s = stats_df["std"]
    snr = stats_df["snr"]
    cv  = stats_df["cv"]
    pct_std_lt_mean = (s < m.abs()).mean() * 100
    print(f"\n{'='*55}")
    print(f"  {name}  (n_estimators={n_estimators})")
    print(f"{'='*55}")
    print(f"  Features:               {len(m)}")
    print(f"  Mean of |mean|:         {m.abs().mean():.6f}")
    print(f"  Median |mean|:          {m.abs().median():.6f}")
    print(f"  Mean std:               {s.mean():.6f}")
    print(f"  Median std:             {s.median():.6f}")
    print(f"  Mean SNR (|mean|/std):  {snr.mean():.3f}")
    print(f"  Median SNR:             {snr.median():.3f}")
    print(f"  Mean CV  (std/|mean|):  {cv.mean():.3f}")
    print(f"  Median CV:              {cv.median():.3f}")
    print(f"  %% features std < |mean|: {pct_std_lt_mean:.1f}%%")
    print(f"  Features with mean > 0: {(m > 0).sum()} / {len(m)}")
    q = np.percentile(snr.dropna(), [10, 25, 50, 75, 90])
    print(f"  SNR percentiles [10,25,50,75,90]: {np.round(q, 3)}")

describe_stats(sfi_stats,   "SFI",           300)
describe_stats(resid_stats, "Residualized MDA", 1000)
describe_stats(pca_stats,   "PCA-MDA",       1000)

print(f"\n{'='*55}")
print(f"  CFI-MDA (n_estimators=300)  — 3 clusters only")
print(f"{'='*55}")
for col in cfi_raw_df.columns:
    vals = cfi_raw_df[col].dropna().values
    m, s = vals.mean(), vals.std()
    snr = abs(m) / (s + 1e-15)
    print(f"  Cluster {col}: mean={m:.5f}  std={s:.5f}  snr={snr:.2f}  "
          f"std<|mean|: {s < abs(m)}")

# ── Figure 1: SNR distributions  (300 vs 1000) ────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle("Signal-to-Noise Ratio (|mean| / std)  per feature\n"
             "SFI=300 trees · Resid-MDA=1000 trees · PCA-MDA=1000 trees",
             fontsize=12, fontweight="bold")

for ax, (label, stats_df, n_est, color) in zip(axes, [
    ("SFI (300)",          sfi_stats,   300,  "#3b82f6"),
    ("Resid-MDA (1000)",   resid_stats, 1000, "#10b981"),
    ("PCA-MDA (1000)",     pca_stats,   1000, "#f59e0b"),
]):
    snr = stats_df["snr"].dropna()
    snr_clipped = np.clip(snr, 0, np.percentile(snr, 97))
    ax.hist(snr_clipped, bins=40, color=color, edgecolor="white", alpha=0.85)
    ax.axvline(1.0, color="red", lw=1.5, linestyle="--", label="SNR=1")
    ax.axvline(snr.median(), color="black", lw=2, linestyle="-",
               label=f"median={snr.median():.2f}")
    ax.set_title(f"{label}\n"
                 f"median SNR={snr.median():.2f}  "
                 f"pct(std<|mean|)={( stats_df['std'] < stats_df['mean'].abs() ).mean()*100:.0f}%",
                 fontsize=10)
    ax.set_xlabel("SNR = |mean| / std", fontsize=9)
    ax.set_ylabel("# features", fontsize=9)
    ax.legend(fontsize=8)

fig.tight_layout()
fig.savefig(OUT / "n_est_snr_comparison.png", dpi=130, bbox_inches="tight")
print(f"\nSaved: n_est_snr_comparison.png")
plt.close(fig)

# ── Figure 2: CV distributions ────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle("Coefficient of Variation (std / |mean|) per feature\n"
             "Lower = more precise estimates  (std << mean → signal dominates)",
             fontsize=12, fontweight="bold")

for ax, (label, stats_df, color) in zip(axes, [
    ("SFI (300)",          sfi_stats,   "#3b82f6"),
    ("Resid-MDA (1000)",   resid_stats, "#10b981"),
    ("PCA-MDA (1000)",     pca_stats,   "#f59e0b"),
]):
    cv = stats_df["cv"].dropna()
    cv_clipped = np.clip(cv, 0, np.percentile(cv, 95))
    ax.hist(cv_clipped, bins=40, color=color, edgecolor="white", alpha=0.85)
    ax.axvline(1.0, color="red", lw=1.5, linestyle="--", label="CV=1")
    ax.axvline(cv.median(), color="black", lw=2, label=f"median={cv.median():.2f}")
    ax.set_title(f"{label}\nmedian CV={cv.median():.2f}", fontsize=10)
    ax.set_xlabel("CV = std / |mean|", fontsize=9)
    ax.set_ylabel("# features", fontsize=9)
    ax.legend(fontsize=8)

fig.tight_layout()
fig.savefig(OUT / "n_est_cv_comparison.png", dpi=130, bbox_inches="tight")
print(f"Saved: n_est_cv_comparison.png")
plt.close(fig)

# ── Figure 3: std vs |mean| scatter — per feature ─────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("std vs |mean| per feature — points BELOW the diagonal have std < |mean|\n"
             "Denser below-diagonal concentration → richer, lower-noise estimates",
             fontsize=11, fontweight="bold")

for ax, (label, stats_df, color, n_est) in zip(axes, [
    ("SFI (300)",          sfi_stats,   "#3b82f6", 300),
    ("Resid-MDA (1000)",   resid_stats, "#10b981", 1000),
    ("PCA-MDA (1000)",     pca_stats,   "#f59e0b", 1000),
]):
    abs_mean = stats_df["mean"].abs()
    std      = stats_df["std"]
    below = (std < abs_mean).sum()
    total = len(std.dropna())

    ax.scatter(abs_mean, std, alpha=0.35, s=12, color=color)

    lim = max(abs_mean.max(), std.max()) * 1.05
    ax.plot([0, lim], [0, lim], "k--", lw=1, label="std = |mean|")

    ax.set_xlabel("|mean importance|", fontsize=9)
    ax.set_ylabel("std of importance", fontsize=9)
    ax.set_title(f"{label}  (n_est={n_est})\n"
                 f"{below}/{total} = {below/total*100:.0f}% have std < |mean|",
                 fontsize=10)
    ax.legend(fontsize=8)

fig.tight_layout()
fig.savefig(OUT / "n_est_std_vs_mean.png", dpi=130, bbox_inches="tight")
print(f"Saved: n_est_std_vs_mean.png")
plt.close(fig)

# ── Figure 4: QQ plots of per-fold scores (top-20 features) for both methods ──
def qq_panel(raw_df, title, fname, top_n=20):
    """QQ plots of per-fold importance for the top_n features (by mean)."""
    means = raw_df.mean().sort_values(ascending=False)
    top_feats = means.head(top_n).index.tolist()

    ncols = 5
    nrows = (top_n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3.5 * nrows))
    axes_flat = np.array(axes).flatten()
    fig.suptitle(title, fontsize=11, fontweight="bold")

    for ax, feat in zip(axes_flat, top_feats):
        vals = raw_df[feat].dropna().values
        (osm, osr), (slope, intercept, r) = stats.probplot(vals, dist="norm")
        ax.plot(osm, osr, "o", markersize=4, color="#5b8db8", alpha=0.8)
        ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=1.5)
        short = feat[:28] + "…" if len(feat) > 28 else feat
        ax.set_title(f"{short}\nn={len(vals)} r²={r**2:.2f}", fontsize=7)
        ax.set_xlabel("Theoretical", fontsize=7)
        ax.set_ylabel("Sample", fontsize=7)

    for ax in axes_flat[top_n:]:
        ax.set_visible(False)

    fig.tight_layout()
    fig.savefig(fname, dpi=120, bbox_inches="tight")
    print(f"Saved: {fname.name}")
    plt.close(fig)

qq_panel(resid_raw, "QQ plots — Residualized MDA (n_est=1000) — top 20 features\n"
         "(good normality of fold scores → reliable z-scores)",
         OUT / "n_est_qq_resid_mda.png")

qq_panel(pca_raw, "QQ plots — PCA-MDA (n_est=1000) — top 20 features",
         OUT / "n_est_qq_pca_mda.png")

# ── Figure 5: Fold-score variance: how much does each fold vary? ──────────────
# For resid_mda and pca_mda raw (folds × features), compute per-fold variance
# to see if some folds are systematically noisier.
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Per-fold variance in importance scores\n"
             "Each bar = one CV fold; high variance → that fold is noisier",
             fontsize=11, fontweight="bold")

for ax, (label, raw_df, color) in zip(axes, [
    ("Resid-MDA (1000)", resid_raw, "#10b981"),
    ("PCA-MDA (1000)",   pca_raw,   "#f59e0b"),
]):
    fold_var = raw_df.var(axis=1)  # variance across features, per fold
    ax.bar(range(len(fold_var)), fold_var.values, color=color, edgecolor="white", alpha=0.85)
    ax.set_title(f"{label}\nmean per-fold variance = {fold_var.mean():.4g}", fontsize=10)
    ax.set_xlabel("Fold index", fontsize=9)
    ax.set_ylabel("Variance across features", fontsize=9)

fig.tight_layout()
fig.savefig(OUT / "n_est_fold_variance.png", dpi=130, bbox_inches="tight")
print(f"Saved: n_est_fold_variance.png")
plt.close(fig)

# ── Figure 6: Head-to-head SNR: 300 vs 1000 for matched features ─────────────
# Compare SFI (300) vs Resid-MDA (1000) SNR on the same features
common = sfi_stats.index.intersection(resid_stats.index)
sfi_snr_common   = sfi_stats.loc[common, "snr"]
resid_snr_common = resid_stats.loc[common, "snr"]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Head-to-head SNR: 300 trees (SFI) vs 1000 trees (Resid-MDA)\n"
             "Same features, matched by name", fontsize=11, fontweight="bold")

ax = axes[0]
ax.scatter(sfi_snr_common, resid_snr_common, alpha=0.35, s=14, color="#6366f1")
lim = max(sfi_snr_common.max(), resid_snr_common.max()) * 1.05
ax.plot([0, lim], [0, lim], "k--", lw=1.2, label="y = x")
ax.set_xlabel("SNR: SFI (n_est=300)", fontsize=9)
ax.set_ylabel("SNR: Resid-MDA (n_est=1000)", fontsize=9)
above = (resid_snr_common > sfi_snr_common).sum()
ax.set_title(f"Resid-MDA > SFI SNR: {above}/{len(common)} = {above/len(common)*100:.0f}%",
             fontsize=10)
ax.legend(fontsize=8)

ax = axes[1]
diff = resid_snr_common - sfi_snr_common
ax.hist(diff.clip(-10, 10), bins=40, color="#6366f1", edgecolor="white", alpha=0.85)
ax.axvline(0, color="red", lw=1.5, linestyle="--", label="no difference")
ax.axvline(diff.mean(), color="black", lw=2, label=f"mean={diff.mean():.2f}")
ax.set_title(f"SNR difference (Resid-MDA - SFI)\nmean={diff.mean():.2f}  "
             f"median={diff.median():.2f}", fontsize=10)
ax.set_xlabel("ΔSNR", fontsize=9)
ax.set_ylabel("# features", fontsize=9)
ax.legend(fontsize=8)

fig.tight_layout()
fig.savefig(OUT / "n_est_snr_head2head.png", dpi=130, bbox_inches="tight")
print(f"Saved: n_est_snr_head2head.png")
plt.close(fig)

# ── Figure 7: CFI-MDA fold distributions (3 clusters) ────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
fig.suptitle("CFI-MDA fold distributions (n_est=300) — 3 clusters\n"
             "Tells us if cluster-level signal is stable across folds",
             fontsize=11, fontweight="bold")

for ax, col in zip(axes, cfi_raw_df.columns):
    vals = cfi_raw_df[col].dropna().values
    m, s = vals.mean(), vals.std()
    snr = abs(m) / (s + 1e-15)
    se = s / np.sqrt(len(vals))
    ax.hist(vals, bins=max(5, len(vals) // 3), color="#f43f5e", edgecolor="white", alpha=0.8)
    ax.axvline(0, color="black", lw=1.5, linestyle="--", label="null=0")
    ax.axvline(m, color="navy", lw=2, label=f"mean={m:.4f}")
    label = cfi_sum.index[int(col)] if int(col) < len(cfi_sum) else f"Cluster {col}"
    short_label = str(label)[:40] + "…" if len(str(label)) > 40 else str(label)
    ax.set_title(f"{short_label}\nSNR={snr:.2f}  std<|mean|: {s < abs(m)}", fontsize=8)
    ax.set_xlabel("base − permuted score", fontsize=8)
    ax.set_ylabel("folds", fontsize=8)
    ax.legend(fontsize=7)

fig.tight_layout()
fig.savefig(OUT / "n_est_cfi_fold_dist.png", dpi=130, bbox_inches="tight")
print(f"Saved: n_est_cfi_fold_dist.png")
plt.close(fig)

print("\n=== Done. All plots written to output/features/winner/ ===")
