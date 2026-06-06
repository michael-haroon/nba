"""
train.py
--------
Leave-One-Year-Out CV for winner (classification) and spread (regression).
Logs both train loss and val loss per fold so overfit is visible.
"""

from __future__ import annotations

import warnings
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    log_loss, roc_auc_score, brier_score_loss, accuracy_score,
    mean_absolute_error, root_mean_squared_error,
)

from strategy.config import SKIP_SEASONS, LOYO_MIN_TRAIN_SEASONS, HUBER_DELTA
from strategy.data import impute_with_train_median
from strategy.models import needs_imputation

# Print LGBM boosting progress every N rounds (set to 0 to silence)
LGBM_LOG_PERIOD = 100


def _huber_loss(y_true: np.ndarray, y_pred: np.ndarray, delta: float = HUBER_DELTA) -> float:
    r = np.abs(y_true - y_pred)
    loss = np.where(r <= delta, 0.5 * r**2, delta * (r - 0.5 * delta))
    return float(loss.mean())


def _fit_lgbm(mdl, X_tr, y_tr, X_val, y_val) -> None:
    import lightgbm as lgb
    import sys
    n_rounds = mdl.n_estimators

    class _ProgressCallback:
        def __call__(self, env):
            i = env.iteration + 1
            train_l = env.evaluation_result_list[0][2]
            val_l   = env.evaluation_result_list[1][2]
            pct = i / n_rounds
            bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
            print(f"\r    [{bar}] {i}/{n_rounds}  train={train_l:.4f}  val={val_l:.4f}",
                  end="", flush=True)
            if i == n_rounds:
                print()  # newline when done

    mdl.fit(
        X_tr, y_tr,
        eval_set=[(X_tr, y_tr), (X_val, y_val)],
        eval_names=["train", "val"],
        callbacks=[lgb.log_evaluation(period=-1), _ProgressCallback()],
    )


def _fit_plain(mdl, X_tr, y_tr) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mdl.fit(X_tr, y_tr)


def train_and_evaluate(
    X: pd.DataFrame,
    y: pd.Series,
    seasons: pd.Series,
    model_name: str,
    build_fn: Callable,
    task: str,          # "classification" or "regression"
) -> dict:
    """
    LOYO cross-validation.

    Returns:
        model       — final model fit on all data
        cv_df       — DataFrame with train_loss, val_loss (and other metrics) per season
        oof_preds   — out-of-fold predictions aligned to original index
        model_name  — echoed back
        task        — echoed back
    """
    all_seasons = sorted(seasons.unique())
    cv_rows = []
    oof_rows = []
    is_lgbm = model_name == "lgbm"

    for season in all_seasons:
        if season in SKIP_SEASONS:
            continue

        train_mask = (seasons != season) & (~seasons.isin(SKIP_SEASONS))
        val_mask = seasons == season

        if train_mask.sum() < LOYO_MIN_TRAIN_SEASONS * 50:
            continue
        if val_mask.sum() == 0:
            continue

        X_tr, X_val = X[train_mask].copy(), X[val_mask].copy()
        y_tr, y_val = y[train_mask].copy(), y[val_mask].copy()

        if needs_imputation(model_name):
            X_tr, X_val = impute_with_train_median(X_tr, X_val)

        print(f"  {season} | n_train={train_mask.sum()} n_val={val_mask.sum()}")

        if task == "regression" and model_name != "ridge":
            from strategy.huber_cv import select_huber_delta, build_regressor_with_delta
            delta = select_huber_delta(X_tr, y_tr, model_name)
            mdl = build_regressor_with_delta(model_name, delta)
        else:
            mdl = build_fn(model_name)
        if is_lgbm:
            _fit_lgbm(mdl, X_tr, y_tr, X_val, y_val)
        else:
            _fit_plain(mdl, X_tr, y_tr)

        if task == "multiclass":
            train_proba = mdl.predict_proba(X_tr)
            val_proba   = mdl.predict_proba(X_val)

            train_loss = log_loss(y_tr, train_proba, labels=mdl.classes_)
            val_loss   = log_loss(y_val, val_proba, labels=mdl.classes_)
            val_pred   = mdl.classes_[val_proba.argmax(axis=1)]
            val_acc    = accuracy_score(y_val, val_pred)

            print(f"  => train_logloss={train_loss:.4f}  val_logloss={val_loss:.4f}  "
                  f"val_acc={val_acc:.4f}")

            cv_rows.append({
                "season": season,
                "train_loss": train_loss, "val_loss": val_loss,
                "val_acc": val_acc,
                "n_train": int(train_mask.sum()), "n_val": int(val_mask.sum()),
            })

            for idx, probs in zip(X.index[val_mask], val_proba):
                oof_rows.append({"index": idx, "season": season,
                                 "y_true": str(y.loc[idx]),
                                 "y_pred": ",".join(f"{p:.4f}" for p in probs)})

        elif task == "classification":
            train_proba = mdl.predict_proba(X_tr)[:, 1]
            val_proba   = mdl.predict_proba(X_val)[:, 1]

            train_loss = log_loss(y_tr, train_proba)
            val_loss   = log_loss(y_val, val_proba)
            val_auc    = roc_auc_score(y_val, val_proba) if y_val.nunique() > 1 else np.nan
            val_brier  = brier_score_loss(y_val, val_proba)
            val_acc    = accuracy_score(y_val, (val_proba >= 0.5).astype(int))

            print(f"  => train_logloss={train_loss:.4f}  val_logloss={val_loss:.4f}  "
                  f"val_auc={val_auc:.4f}  val_acc={val_acc:.4f}")

            cv_rows.append({
                "season": season,
                "train_loss": train_loss, "val_loss": val_loss,
                "val_auc": val_auc, "val_brier": val_brier, "val_acc": val_acc,
                "n_train": int(train_mask.sum()), "n_val": int(val_mask.sum()),
            })

            for idx, prob in zip(X.index[val_mask], val_proba):
                oof_rows.append({"index": idx, "season": season,
                                 "y_true": int(y.loc[idx]), "y_pred": float(prob)})

        else:  # regression
            train_pred = mdl.predict(X_tr)
            val_pred   = mdl.predict(X_val)

            _delta = delta if (task == "regression" and model_name != "ridge") else HUBER_DELTA
            train_loss = _huber_loss(y_tr.values, train_pred, delta=_delta)
            val_loss   = _huber_loss(y_val.values, val_pred, delta=_delta)
            val_mae    = mean_absolute_error(y_val, val_pred)
            val_rmse   = root_mean_squared_error(y_val, val_pred)

            print(f"  => train_huber={train_loss:.4f}  val_huber={val_loss:.4f}  "
                  f"val_mae={val_mae:.4f}  val_rmse={val_rmse:.4f}")

            cv_rows.append({
                "season": season,
                "train_loss": train_loss, "val_loss": val_loss,
                "val_mae": val_mae, "val_rmse": val_rmse,
                "n_train": int(train_mask.sum()), "n_val": int(val_mask.sum()),
            })

            for idx, pred in zip(X.index[val_mask], val_pred):
                oof_rows.append({"index": idx, "season": season,
                                 "y_true": float(y.loc[idx]), "y_pred": float(pred)})

    # Final model on all non-skipped data
    full_mask = ~seasons.isin(SKIP_SEASONS)
    X_full, y_full = X[full_mask].copy(), y[full_mask].copy()
    if needs_imputation(model_name):
        medians = X_full.median()
        X_full = X_full.fillna(medians)

    print(f"\n  -- Final model fit on all {full_mask.sum()} games --")
    if task == "regression" and model_name != "ridge":
        from strategy.huber_cv import select_huber_delta, build_regressor_with_delta
        final_delta = select_huber_delta(X_full, y_full, model_name)
        final_model = build_regressor_with_delta(model_name, final_delta)
    else:
        final_model = build_fn(model_name)
    if is_lgbm:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
        final_model.fit(X_full, y_full)
    else:
        _fit_plain(final_model, X_full, y_full)

    return {
        "model": final_model,
        "cv_df": pd.DataFrame(cv_rows),
        "oof_preds": pd.DataFrame(oof_rows),
        "model_name": model_name,
        "task": task,
    }
