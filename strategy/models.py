"""
models.py
---------
Model factory for winner (classification) and spread (regression).
All tree models use n_jobs=-1 / nthread=-1 to saturate available CPUs.
CatBoost auto-detects GPU if CUDA is available.

XGBoost and CatBoost are optional — install with:
    pip install xgboost catboost
Models that are not installed are silently skipped by available_*() helpers.
"""

from __future__ import annotations

import importlib
import importlib.util

from strategy.config import (
    LGBM_CLF_PARAMS, LGBM_REG_PARAMS,
    XGB_CLF_PARAMS, XGB_REG_PARAMS,
    LOGREG_PARAMS, RIDGE_ALPHAS,
    CATBOOST_CLF_PARAMS, CATBOOST_REG_PARAMS,
    LGBM_MULTI_PARAMS, XGB_MULTI_PARAMS,
    CATBOOST_MULTI_PARAMS, LOGREG_MULTI_PARAMS,
)

_ALL_CLASSIFIERS = ["lgbm", "xgb", "logreg", "catboost"]
_ALL_REGRESSORS  = ["lgbm", "xgb", "ridge",  "catboost"]
_ALL_MULTICLASS  = ["lgbm", "xgb", "logreg", "catboost"]

_OPTIONAL_PKG = {"xgb": "xgboost", "catboost": "catboost"}


def _available(name: str) -> bool:
    pkg = _OPTIONAL_PKG.get(name)
    if pkg is None:
        return True  # lgbm, logreg, ridge are always present
    return importlib.util.find_spec(pkg) is not None


def available_classifiers() -> list[str]:
    names = [n for n in _ALL_CLASSIFIERS if _available(n)]
    skipped = [n for n in _ALL_CLASSIFIERS if not _available(n)]
    if skipped:
        print(f"  [models] Skipping unavailable classifiers: {skipped} "
              f"(install xgboost / catboost to enable)")
    return names


def available_regressors() -> list[str]:
    names = [n for n in _ALL_REGRESSORS if _available(n)]
    skipped = [n for n in _ALL_REGRESSORS if not _available(n)]
    if skipped:
        print(f"  [models] Skipping unavailable regressors: {skipped} "
              f"(install xgboost / catboost to enable)")
    return names


def _catboost_task_type() -> str:
    try:
        import torch
        return "GPU" if torch.cuda.is_available() else "CPU"
    except ImportError:
        return "CPU"


def build_classifier(name: str):
    """Return an unfitted sklearn-compatible classifier."""
    if name == "lgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(**LGBM_CLF_PARAMS)

    elif name == "xgb":
        from xgboost import XGBClassifier
        return XGBClassifier(**XGB_CLF_PARAMS)

    elif name == "logreg":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**LOGREG_PARAMS)

    elif name == "catboost":
        from catboost import CatBoostClassifier
        params = {**CATBOOST_CLF_PARAMS, "task_type": _catboost_task_type()}
        if params["task_type"] == "CPU":
            params["thread_count"] = -1
        return CatBoostClassifier(**params)

    else:
        raise ValueError(f"Unknown classifier: {name}")


def build_regressor(name: str):
    """Return an unfitted sklearn-compatible regressor."""
    if name == "lgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(**LGBM_REG_PARAMS)

    elif name == "xgb":
        from xgboost import XGBRegressor
        return XGBRegressor(**XGB_REG_PARAMS)

    elif name == "ridge":
        from sklearn.linear_model import RidgeCV
        return RidgeCV(alphas=RIDGE_ALPHAS)

    elif name == "catboost":
        from catboost import CatBoostRegressor
        params = {**CATBOOST_REG_PARAMS, "task_type": _catboost_task_type()}
        if params["task_type"] == "CPU":
            params["thread_count"] = -1
        return CatBoostRegressor(**params)

    else:
        raise ValueError(f"Unknown regressor: {name}")


def available_multiclass() -> list[str]:
    names = [n for n in _ALL_MULTICLASS if _available(n)]
    skipped = [n for n in _ALL_MULTICLASS if not _available(n)]
    if skipped:
        print(f"  [models] Skipping unavailable multiclass: {skipped} "
              f"(install xgboost / catboost to enable)")
    return names


def build_multiclass(name: str):
    """Return an unfitted sklearn-compatible multiclass classifier."""
    if name == "lgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(**LGBM_MULTI_PARAMS)

    elif name == "xgb":
        from xgboost import XGBClassifier
        return XGBClassifier(**XGB_MULTI_PARAMS)

    elif name == "logreg":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**LOGREG_MULTI_PARAMS)

    elif name == "catboost":
        from catboost import CatBoostClassifier
        params = {**CATBOOST_MULTI_PARAMS, "task_type": _catboost_task_type()}
        if params["task_type"] == "CPU":
            params["thread_count"] = -1
        return CatBoostClassifier(**params)

    else:
        raise ValueError(f"Unknown multiclass model: {name}")


def needs_imputation(name: str) -> bool:
    """True for models that cannot handle NaN inputs natively."""
    return name in {"logreg", "ridge"}
