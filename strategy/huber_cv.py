"""
huber_cv.py
-----------
Adaptive Huber delta selection via nested inner-loop CV.

For each outer LOYO fold's training set, runs inner time-based CV over a
MAD-scaled grid of delta candidates. Selects the delta minimizing inner
validation MAE. This makes the loss function target-specific and era-adaptive.

Mathematical basis:
    - Huber loss transitions from quadratic to linear at |residual| = delta
    - Robust statistics: delta = k * MAD / 0.6745 gives k-sigma efficiency
    - Grid [0.5, 0.75, 1.0, 1.25, 1.5] * sigma_hat spans conservative to permissive
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from typing import Callable
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)

DELTA_MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5]
N_INNER_FOLDS = 3


def _mad_sigma(y: np.ndarray) -> float:
    """MAD-based robust scale estimate: MAD / 0.6745 ≈ sigma for Gaussian."""
    med = np.median(y)
    mad = np.median(np.abs(y - med))
    return mad / 0.6745 if mad > 0 else 1.0


def build_regressor_with_delta(model_name: str, delta: float):
    """
    Build a regression model with a specific Huber delta.
    Self-contained to avoid modifying models.py.
    """
    if model_name == "lgbm":
        from lightgbm import LGBMRegressor
        from strategy.config import LGBM_REG_PARAMS
        params = {**LGBM_REG_PARAMS, "alpha": delta}
        return LGBMRegressor(**params)

    elif model_name == "xgb":
        from xgboost import XGBRegressor
        from strategy.config import XGB_REG_PARAMS
        params = {**XGB_REG_PARAMS, "huber_slope": delta}
        return XGBRegressor(**params)

    elif model_name == "catboost":
        from catboost import CatBoostRegressor
        from strategy.config import CATBOOST_REG_PARAMS
        params = {**CATBOOST_REG_PARAMS, "loss_function": f"Huber:delta={delta}"}
        return CatBoostRegressor(**params)

    elif model_name == "ridge":
        from sklearn.linear_model import RidgeCV
        from strategy.config import RIDGE_ALPHAS
        return RidgeCV(alphas=RIDGE_ALPHAS)

    else:
        raise ValueError(f"Unknown regressor: {model_name}")


def select_huber_delta(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_name: str,
    n_inner_folds: int = N_INNER_FOLDS,
    multipliers: list[float] | None = None,
) -> float:
    """
    Select optimal Huber delta via inner time-based CV on the training fold.

    Args:
        X_train: Training features (single outer fold)
        y_train: Training targets
        model_name: Model identifier (lgbm, xgb, catboost, ridge)
        n_inner_folds: Number of inner CV splits (chronological)
        multipliers: Grid multipliers on sigma_hat

    Returns:
        Optimal delta value
    """
    if model_name == "ridge":
        return 1.0  # Ridge uses MSE, delta not applicable

    if multipliers is None:
        multipliers = DELTA_MULTIPLIERS

    sigma_hat = _mad_sigma(y_train.values)
    grid = [m * sigma_hat for m in multipliers]

    # Ensure grid values are reasonable (floor at 1.0 for NBA scales)
    grid = [max(1.0, d) for d in grid]

    tscv = TimeSeriesSplit(n_splits=n_inner_folds)

    best_delta = grid[2]  # default: 1.0 * sigma_hat
    best_mae = np.inf

    for delta in grid:
        fold_maes = []
        for train_idx, val_idx in tscv.split(X_train):
            X_inner_tr = X_train.iloc[train_idx]
            X_inner_val = X_train.iloc[val_idx]
            y_inner_tr = y_train.iloc[train_idx]
            y_inner_val = y_train.iloc[val_idx]

            try:
                mdl = build_regressor_with_delta(model_name, delta)

                if model_name == "lgbm":
                    import lightgbm as lgb
                    mdl.fit(
                        X_inner_tr, y_inner_tr,
                        eval_set=[(X_inner_val, y_inner_val)],
                        callbacks=[lgb.log_evaluation(period=-1)],
                    )
                else:
                    mdl.fit(X_inner_tr, y_inner_tr)

                pred = mdl.predict(X_inner_val)
                fold_maes.append(mean_absolute_error(y_inner_val, pred))
            except Exception:
                fold_maes.append(np.inf)

        avg_mae = np.mean(fold_maes)
        if avg_mae < best_mae:
            best_mae = avg_mae
            best_delta = delta

    logger.info(
        f"  Delta CV: selected δ={best_delta:.2f} "
        f"(σ̂={sigma_hat:.2f}, grid={[f'{d:.1f}' for d in grid]}), "
        f"inner MAE={best_mae:.3f}"
    )
    print(
        f"    Delta CV: δ={best_delta:.2f} "
        f"(σ̂={sigma_hat:.2f}, grid=[{', '.join(f'{d:.1f}' for d in grid)}], "
        f"inner MAE={best_mae:.3f})"
    )

    return best_delta
