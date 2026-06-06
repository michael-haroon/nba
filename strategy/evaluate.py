"""
evaluate.py
-----------
Model comparison table and spread exceedance probability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# Overfit threshold: if val - train gap exceeds this, flag it
OVERFIT_THRESHOLD = 0.05


def print_model_comparison(results: dict[str, dict], task: str) -> str:
    """
    Print a table of train_loss vs val_loss per model.
    Flags models where val_loss - train_loss > OVERFIT_THRESHOLD.

    Returns name of best model by val_loss.
    """
    if task == "classification":
        print(f"\n{'Model':<12} {'Train LogLoss':>14} {'Val LogLoss':>12} {'Val AUC':>8} {'Val Brier':>10} {'Val Acc':>8} {'Overfit?':>9}")
        print("-" * 77)
    else:
        print(f"\n{'Model':<12} {'Train Huber':>12} {'Val Huber':>10} {'Val MAE':>8} {'Val RMSE':>9} {'Overfit?':>9}")
        print("-" * 64)

    best_name = None
    best_val = np.inf

    for name, res in results.items():
        cv = res["cv_df"]
        if cv.empty:
            continue
        train_l = cv["train_loss"].mean()
        val_l   = cv["val_loss"].mean()
        overfit = (val_l - train_l) > OVERFIT_THRESHOLD

        if task == "classification":
            auc   = cv["val_auc"].mean()
            brier = cv["val_brier"].mean()
            acc   = cv["val_acc"].mean()
            flag  = " ***" if overfit else ""
            print(f"{name:<12} {train_l:>14.4f} {val_l:>12.4f} {auc:>8.4f} {brier:>10.4f} {acc:>8.4f}{flag}")
        else:
            mae  = cv["val_mae"].mean()
            rmse = cv["val_rmse"].mean()
            flag = " ***" if overfit else ""
            print(f"{name:<12} {train_l:>12.4f} {val_l:>10.4f} {mae:>8.4f} {rmse:>9.4f}{flag}")

        if val_l < best_val:
            best_val = val_l
            best_name = name

    print(f"\nBest by val loss: {best_name}")
    if task == "classification":
        print("Primary metric: log-loss (lower = better)")
    else:
        print("Primary metric: Huber loss (lower = better)")

    return best_name


def fit_spread_residuals(oof_preds: pd.DataFrame) -> stats.t:
    """
    Fit a Student-t to OOF residuals (y_true - y_pred).
    Returns a frozen scipy.stats.t distribution.
    """
    resid = oof_preds["y_true"].values - oof_preds["y_pred"].values
    df_t, loc, scale = stats.t.fit(resid)
    return stats.t(df=df_t, loc=loc, scale=scale)


def spread_exceedance(predicted_spread: float, threshold: float,
                      residual_dist: stats.t) -> float:
    """
    P(actual spread > threshold) given model's predicted spread.

    The residual distribution is centered on 0 (model bias absorbed).
    We shift it by predicted_spread and ask what fraction exceeds threshold.
    """
    # P(pred + resid > threshold) = P(resid > threshold - pred)
    return float(1.0 - residual_dist.cdf(threshold - predicted_spread))


def save_results(results: dict[str, dict], output_dir, target: str,
                 spread_residual_dist=None) -> None:
    """Save per-model CV DataFrames, OOF predictions, and trained model files."""
    import joblib
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_cv = []
    all_oof = []
    for name, res in results.items():
        cv = res["cv_df"].copy()
        cv.insert(0, "model", name)
        all_cv.append(cv)

        oof = res["oof_preds"].copy()
        oof.insert(0, "model", name)
        all_oof.append(oof)

        # Save the final model (fit on all non-skipped data) for inference
        model_path = out / f"{target}_{name}.joblib"
        joblib.dump(res["model"], model_path)
        print(f"  Saved model -> {model_path}")

    pd.concat(all_cv).to_csv(out / f"nba_{target}_cv.csv", index=False)
    pd.concat(all_oof).to_csv(out / f"nba_{target}_oof.csv", index=False)
    print(f"  Saved CV results -> {out}/nba_{target}_cv.csv")

    if spread_residual_dist is not None:
        dist_params = {
            "df": float(spread_residual_dist.kwds["df"]),
            "loc": float(spread_residual_dist.kwds["loc"]),
            "scale": float(spread_residual_dist.kwds["scale"]),
        }
        import json
        dist_file = out / f"{target}_residual_dist.json"
        with open(dist_file, "w") as f:
            json.dump(dist_params, f, indent=2)
        print(f"  Saved residual dist -> {dist_file}")


def load_model(output_dir, target: str, model_name: str):
    """Load a saved model for inference."""
    import joblib
    from pathlib import Path
    return joblib.load(Path(output_dir) / f"{target}_{model_name}.joblib")


def load_residual_dist(output_dir, target: str = "spread"):
    """Load the saved residual distribution for exceedance queries."""
    import json
    from pathlib import Path
    from scipy import stats
    with open(Path(output_dir) / f"{target}_residual_dist.json") as f:
        p = json.load(f)
    return stats.t(df=p["df"], loc=p["loc"], scale=p["scale"])
