"""Plot spread error distribution and heteroscedasticity check."""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats

OOF_PATH = Path("strategy/output/nba/ensemble/spread_ensemble_oof.csv")
OUT_DIR = Path("strategy/output/nba/ensemble/plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

oof = pd.read_csv(OOF_PATH)
errors = oof["y_true"] - oof["y_pred_ensemble"]
y_pred = oof["y_pred_ensemble"]

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# --- 1. Error distribution with Gaussian overlay ---
ax = axes[0, 0]
ax.hist(errors, bins=80, density=True, alpha=0.7, color="steelblue", edgecolor="none")
x = np.linspace(errors.min(), errors.max(), 200)
gaussian = stats.norm.pdf(x, loc=errors.mean(), scale=errors.std())
ax.plot(x, gaussian, "r-", lw=2, label=f"N({errors.mean():.1f}, {errors.std():.1f}²)")
ax.axvline(0, color="k", ls="--", alpha=0.5)
ax.set_xlabel("Error (True - Predicted)", fontsize=11)
ax.set_ylabel("Density", fontsize=11)
ax.set_title("Error Distribution", fontsize=13)
ax.legend(fontsize=10)

# --- 2. QQ plot ---
ax = axes[0, 1]
(osm, osr), (slope, intercept, r) = stats.probplot(errors, dist="norm")
ax.scatter(osm, osr, s=2, alpha=0.3, color="steelblue")
ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=2, label=f"R²={r**2:.4f}")
ax.set_xlabel("Theoretical Quantiles", fontsize=11)
ax.set_ylabel("Sample Quantiles", fontsize=11)
ax.set_title("QQ Plot (Normality Check)", fontsize=13)
ax.legend(fontsize=10)

# --- 3. Heteroscedasticity: error vs predicted spread ---
ax = axes[1, 0]
ax.scatter(y_pred, errors, s=3, alpha=0.1, color="steelblue")
# Rolling std in bins
bins = pd.cut(y_pred, bins=30)
bin_stats = oof.assign(error=errors).groupby(bins, observed=True)["error"].agg(["mean", "std", "count"])
bin_centers = [(b.left + b.right) / 2 for b in bin_stats.index]
ax.plot(bin_centers, bin_stats["std"], "r-o", lw=2, markersize=5, label="Binned σ(E)")
ax.axhline(errors.std(), color="k", ls="--", alpha=0.5, label=f"Overall σ={errors.std():.1f}")
ax.set_xlabel("Predicted Spread (Ŷ)", fontsize=11)
ax.set_ylabel("Error (Y - Ŷ)", fontsize=11)
ax.set_title("Heteroscedasticity Check: Error vs Prediction", fontsize=13)
ax.legend(fontsize=10)

# --- 4. Binned absolute error and std vs |prediction| ---
ax = axes[1, 1]
oof["abs_pred"] = y_pred.abs()
oof["abs_error"] = errors.abs()
pred_bins = pd.qcut(oof["abs_pred"], 10, duplicates="drop")
bin_summary = oof.groupby(pred_bins, observed=True).agg(
    mae=("abs_error", "mean"),
    error_std=("abs_error", "std"),
    n=("abs_error", "count"),
    pred_mean=("abs_pred", "mean")
).reset_index(drop=True)

ax.plot(bin_summary["pred_mean"], bin_summary["mae"], "b-o", lw=2, markersize=6, label="MAE")
ax.fill_between(bin_summary["pred_mean"],
                bin_summary["mae"] - bin_summary["error_std"] / np.sqrt(bin_summary["n"]) * 1.96,
                bin_summary["mae"] + bin_summary["error_std"] / np.sqrt(bin_summary["n"]) * 1.96,
                alpha=0.2, color="blue")
ax.axhline(errors.abs().mean(), color="k", ls="--", alpha=0.5, label=f"Overall MAE={errors.abs().mean():.1f}")
ax.set_xlabel("|Predicted Spread|", fontsize=11)
ax.set_ylabel("MAE", fontsize=11)
ax.set_title("MAE vs Prediction Magnitude (σ_E constant?)", fontsize=13)
ax.legend(fontsize=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "spread_error_analysis.png", dpi=150, bbox_inches="tight")
print(f"Saved: {OUT_DIR / 'spread_error_analysis.png'}")

# Print numerical heteroscedasticity test
print(f"\nBreusch-Pagan style check (binned σ):")
print(f"  {'|Ŷ| bin':>10} {'σ(E)':>8} {'MAE':>8} {'N':>6}")
print(f"  {'-'*36}")
pred_bins2 = pd.cut(y_pred.abs(), bins=[0, 2, 4, 6, 8, 10, 12, 15, 50])
for name, grp in oof.assign(error=errors).groupby(pred_bins2, observed=True):
    print(f"  {str(name):>10} {grp['error'].std():>8.2f} {grp['error'].abs().mean():>8.2f} {len(grp):>6}")
