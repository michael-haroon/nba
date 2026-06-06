"""Analyze spread ensemble error distribution and model confidence."""
import pandas as pd
import numpy as np
from pathlib import Path

OOF_PATH = Path("strategy/output/nba/ensemble/spread_ensemble_oof.csv")

oof = pd.read_csv(OOF_PATH)
errors = oof["y_true"] - oof["y_pred_ensemble"]
abs_errors = errors.abs()

print("=" * 60)
print("  SPREAD ERROR DISTRIBUTION")
print("=" * 60)
print(f"\n  N games: {len(oof)}")
print(f"  MAE: {abs_errors.mean():.2f}")
print(f"  Median AE: {abs_errors.median():.2f}")
print(f"  Std of error: {errors.std():.2f}")
print(f"  Mean error (bias): {errors.mean():+.2f}")
print(f"\n  Percentiles of ABSOLUTE error:")
for p in [10, 25, 50, 75, 90, 95, 99]:
    print(f"    {p:3d}th: {abs_errors.quantile(p/100):.1f} pts")

print(f"\n  Percentiles of SIGNED error (true - pred):")
for p in [5, 10, 25, 50, 75, 90, 95]:
    print(f"    {p:3d}th: {errors.quantile(p/100):+.1f} pts")

# Naive baseline comparison
naive_pred = oof["y_true"].mean()
naive_mae = (oof["y_true"] - naive_pred).abs().mean()
print(f"\n  Naive baseline (predict mean={naive_pred:.1f}): MAE={naive_mae:.2f}")
print(f"  Model lift over naive: {naive_mae - abs_errors.mean():.2f} pts ({(naive_mae - abs_errors.mean())/naive_mae*100:.1f}%)")

# --- MODEL CONFIDENCE via ensemble disagreement ---
print("\n" + "=" * 60)
print("  MODEL CONFIDENCE (ensemble disagreement)")
print("=" * 60)

pred_cols = [c for c in oof.columns if c.startswith("pred_")]
print(f"\n  Ensemble members with non-zero weight: {len(pred_cols)}")

oof["model_std"] = oof[pred_cols].std(axis=1)
oof["abs_error"] = abs_errors

print(f"  Model std range: [{oof['model_std'].min():.2f}, {oof['model_std'].max():.2f}]")
print(f"  Model std mean: {oof['model_std'].mean():.2f}")

# Bin by confidence (low std = high confidence)
oof["confidence_quintile"] = pd.qcut(
    oof["model_std"], 5,
    labels=["Q1 (highest conf)", "Q2", "Q3", "Q4", "Q5 (lowest conf)"]
)

print(f"\n  MAE by confidence quintile:")
print(f"  {'Quintile':<20} {'MAE':>6} {'Median AE':>10} {'N':>6} {'Std range':>15}")
print(f"  {'-'*60}")
for q in ["Q1 (highest conf)", "Q2", "Q3", "Q4", "Q5 (lowest conf)"]:
    subset = oof[oof["confidence_quintile"] == q]
    print(f"  {q:<20} {subset['abs_error'].mean():>6.2f} "
          f"{subset['abs_error'].median():>10.2f} "
          f"{len(subset):>6} "
          f"[{subset['model_std'].min():.1f}-{subset['model_std'].max():.1f}]")

# Finer bins — deciles
oof["confidence_decile"] = pd.qcut(
    oof["model_std"], 10,
    labels=[f"D{i+1}" for i in range(10)]
)
print(f"\n  MAE by confidence decile:")
print(f"  {'Decile':<8} {'MAE':>6} {'N':>6} {'Model Std':>12}")
print(f"  {'-'*40}")
for d in [f"D{i+1}" for i in range(10)]:
    subset = oof[oof["confidence_decile"] == d]
    print(f"  {d:<8} {subset['abs_error'].mean():>6.2f} "
          f"{len(subset):>6} "
          f"{subset['model_std'].mean():>8.2f}")

# --- Accuracy within spread windows ---
print("\n" + "=" * 60)
print("  ACCURACY WITHIN SPREAD WINDOWS")
print("=" * 60)
for window in [1, 2, 3, 5, 7, 10]:
    pct = (abs_errors <= window).mean() * 100
    print(f"  Within ±{window:2d} pts: {pct:5.1f}%")

# --- Confidence + window (the money signal) ---
print("\n" + "=" * 60)
print("  HIGH CONFIDENCE ACCURACY (top 20% confidence)")
print("=" * 60)
high_conf = oof[oof["confidence_quintile"] == "Q1 (highest conf)"]
high_conf_errors = (high_conf["y_true"] - high_conf["y_pred_ensemble"]).abs()
for window in [1, 2, 3, 5, 7, 10]:
    pct = (high_conf_errors <= window).mean() * 100
    pct_all = (abs_errors <= window).mean() * 100
    print(f"  Within ±{window:2d} pts: {pct:5.1f}% (vs {pct_all:.1f}% overall)")

# --- Spread magnitude vs accuracy ---
print("\n" + "=" * 60)
print("  MAE BY PREDICTED SPREAD MAGNITUDE")
print("=" * 60)
oof["pred_abs"] = oof["y_pred_ensemble"].abs()
oof["pred_bucket"] = pd.cut(oof["pred_abs"], bins=[0, 3, 6, 10, 15, 50],
                            labels=["0-3", "3-6", "6-10", "10-15", "15+"])
print(f"  {'Pred magnitude':<15} {'MAE':>6} {'N':>6} {'Correct sign%':>14}")
print(f"  {'-'*45}")
for bucket in ["0-3", "3-6", "6-10", "10-15", "15+"]:
    subset = oof[oof["pred_bucket"] == bucket]
    if len(subset) == 0:
        continue
    correct_sign = ((subset["y_pred_ensemble"] * subset["y_true"]) > 0).mean() * 100
    print(f"  {bucket:<15} {subset['abs_error'].mean():>6.2f} "
          f"{len(subset):>6} {correct_sign:>13.1f}%")
