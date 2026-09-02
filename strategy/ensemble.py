"""
ensemble.py
-----------
Generate 100+ diverse candidate models, train via LOYO CV, measure orthogonality,
and select/weight an optimal diverse ensemble.

Diversity sources:
  1. Model families: boosted trees (LGBM, XGB, CatBoost), linear (LogReg, Ridge),
     random forests, extra trees, KNN, naive bayes, MLP, LDA/QDA, AdaBoost, SVM
  2. Feature subsets: massey-only, rolling-means, rolling-stds, raw-diffs, full 544,
     PCA projections, random subspace sampling
  3. Hyperparameter regimes: shallow/deep trees, aggressive/light regularization,
     different learning rates, different ensemble sizes
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import os
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ─── Threading config for high-core machines ────────────────────────────────
# We parallelize at TWO levels:
#   1. Outer: multiple models train concurrently (N_PARALLEL_MODELS)
#   2. Inner: each tree model uses _MAX_JOBS threads
# Total thread budget ≈ N_PARALLEL_MODELS × _MAX_JOBS ≤ cpu_count
_N_CPUS = os.cpu_count() or 8
_MAX_JOBS = min(_N_CPUS, 8)           # threads per model (lower to leave room for parallelism)
_N_PARALLEL_MODELS = max(1, _N_CPUS // _MAX_JOBS)  # e.g. 96/8 = 12 models in parallel

os.environ.setdefault("OPENBLAS_NUM_THREADS", str(_MAX_JOBS))
os.environ.setdefault("OMP_NUM_THREADS", str(_MAX_JOBS))
os.environ.setdefault("MKL_NUM_THREADS", str(_MAX_JOBS))

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, accuracy_score

import strategy.config as _cfg
from strategy.config import SKIP_SEASONS, LOYO_MIN_TRAIN_SEASONS

logger = logging.getLogger(__name__)

# ─── Feature subset definitions ─────────────────────────────────────────────
# Features come ONLY from the feature importance pipeline's filtered output.
# The ensemble's job is specification search (model architecture + weighting),
# not variable search.  No feature that failed MDI/CFI-MDA/SFI enters here.


def _load_survivors(target: str) -> list[str]:
    """Load the filtered feature list produced by the feature importance pipeline."""
    from strategy.config import WINNER_FEATURES, SPREAD_FEATURES, load_feature_list
    path = WINNER_FEATURES if target == "winner" else SPREAD_FEATURES
    if not path.exists():
        raise FileNotFoundError(
            f"Filtered feature list not found at {path}. "
            f"Run the feature importance pipeline first: "
            f"python -m feature_pipeline.analysis.run --target target_{target}"
        )
    features = load_feature_list(path)
    if len(features) < 2:
        raise ValueError(
            f"Feature list at {path} has {len(features)} features. "
            f"The importance pipeline may have a filtering issue."
        )
    return features


def build_feature_subsets(survivors: list[str]) -> dict[str, list[str]]:
    """
    Build named feature subsets for ensemble diversity from pipeline survivors ONLY.

    Diversity comes from semantic groupings within the survivors — not from
    re-running variable search on the full library.
    """
    subsets = {}

    # Categorize survivors by semantic type
    massey = [c for c in survivors if "massey" in c]
    ratings = [c for c in survivors if any(x in c for x in
               ["bpi", "elo", "sag_", "predictor", "golden_mean", "colley",
                "pure_elo", "offtalent", "deftalent", "playoffbpi"])
               and c not in massey]
    roll5 = [c for c in survivors if "roll5_" in c]
    roll10 = [c for c in survivors if "roll10_" in c]
    roll20 = [c for c in survivors if "roll20_" in c]
    rolling_means = [c for c in survivors if any(f"roll{w}_" in c for w in [5, 10, 20])
                     and "_std" not in c]
    rolling_stds = [c for c in survivors if any(f"roll{w}_" in c for w in [5, 10, 20])
                    and "_std" in c]
    momentum = [c for c in survivors if any(x in c for x in
                ["win_streak", "win_pct", "win_entropy", "margin_last", "cusum"])]
    efficiency = [c for c in survivors if any(x in c for x in
                  ["netrtg", "offrtg", "defrtg", "efgpct", "tspct", "pie"])]
    context = [c for c in survivors if any(x in c for x in
               ["rest", "back_to_back", "travel", "timezone", "crowd",
                "venue", "days_span", "games_per_week"])]

    # Individual subsets (only include if >= 2 features)
    for name, feats in [
        ("massey", massey),
        ("ratings", ratings),
        ("roll5", roll5),
        ("roll10", roll10),
        ("roll20", roll20),
        ("rolling_means", rolling_means),
        ("rolling_stds", rolling_stds),
        ("momentum", momentum),
        ("efficiency", efficiency),
        ("context", context),
    ]:
        if len(feats) >= 2:
            subsets[name] = feats

    # Composite subsets
    massey_momentum = massey + momentum
    if len(massey_momentum) >= 2:
        subsets["massey+momentum"] = massey_momentum

    massey_ratings = massey + ratings
    if len(massey_ratings) >= 2:
        subsets["massey+ratings"] = massey_ratings

    short_window = roll5 + momentum
    if len(short_window) >= 2:
        subsets["short_window"] = short_window

    long_window = roll20
    if len(long_window) >= 2:
        subsets["long_window"] = long_window

    # Full survivor set (always included — this is the "all proven features" model)
    subsets["all_survivors"] = survivors

    return subsets


# ─── Model configurations ───────────────────────────────────────────────────

@dataclass
class ModelSpec:
    """A single model configuration to train."""
    name: str
    family: str
    feature_subset: str
    build_fn: Callable
    needs_imputation: bool = False
    needs_scaling: bool = False
    needs_pca: bool = False

    def uid(self) -> str:
        return f"{self.name}__{self.feature_subset}"


def _build_model_specs(task: str = "classification") -> list[ModelSpec]:
    """Generate all model spec combinations."""
    specs = []

    if task == "classification":
        specs.extend(_classification_specs())
    else:
        specs.extend(_regression_specs())

    return specs


def _classification_specs() -> list[ModelSpec]:
    specs = []

    # --- LGBM variants ---
    lgbm_configs = [
        ("lgbm_shallow", {"n_estimators": 300, "max_depth": 3, "num_leaves": 7, "learning_rate": 0.05}),
        ("lgbm_default", {"n_estimators": 600, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.03}),
        ("lgbm_deep", {"n_estimators": 800, "max_depth": 6, "num_leaves": 31, "learning_rate": 0.02}),
        ("lgbm_aggressive", {"n_estimators": 400, "max_depth": 5, "num_leaves": 20, "learning_rate": 0.08,
                             "reg_alpha": 0.0, "reg_lambda": 0.0}),
        ("lgbm_regularized", {"n_estimators": 600, "max_depth": 4, "num_leaves": 12, "learning_rate": 0.03,
                              "reg_alpha": 2.0, "reg_lambda": 5.0, "min_child_samples": 50}),
        ("lgbm_dart", {"n_estimators": 400, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.05,
                       "boosting_type": "dart", "drop_rate": 0.1}),
        ("lgbm_goss", {"n_estimators": 600, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.03,
                       "boosting_type": "goss"}),
        ("lgbm_lowsample", {"n_estimators": 600, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.03,
                            "subsample": 0.5, "colsample_bytree": 0.5}),
    ]
    for name, params in lgbm_configs:
        base = {"objective": "binary", "metric": "binary_logloss", "random_state": 42,
                "verbosity": -1, "n_jobs": _MAX_JOBS, "subsample": 0.8, "colsample_bytree": 0.8,
                "min_child_samples": 20, "reg_alpha": 0.5, "reg_lambda": 2.0}
        base.update(params)
        def _make_lgbm(p=base):
            from lightgbm import LGBMClassifier
            return LGBMClassifier(**p)
        specs.append(ModelSpec(name=name, family="lgbm", feature_subset="",
                              build_fn=_make_lgbm))

    # --- XGB variants ---
    xgb_configs = [
        ("xgb_shallow", {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.05}),
        ("xgb_default", {"n_estimators": 600, "max_depth": 4, "learning_rate": 0.03}),
        ("xgb_deep", {"n_estimators": 800, "max_depth": 6, "learning_rate": 0.02}),
        ("xgb_regularized", {"n_estimators": 600, "max_depth": 4, "learning_rate": 0.03,
                             "reg_alpha": 2.0, "reg_lambda": 5.0, "min_child_weight": 50}),
    ]
    for name, params in xgb_configs:
        base = {"objective": "binary:logistic", "eval_metric": "logloss", "random_state": 42,
                "verbosity": 0, "nthread": _MAX_JOBS, "subsample": 0.8, "colsample_bytree": 0.8,
                "min_child_weight": 20, "reg_alpha": 0.5, "reg_lambda": 2.0}
        base.update(params)
        def _make_xgb(p=base):
            from xgboost import XGBClassifier
            return XGBClassifier(**p)
        specs.append(ModelSpec(name=name, family="xgb", feature_subset="",
                              build_fn=_make_xgb))

    # --- CatBoost variants ---
    cb_configs = [
        ("catboost_shallow", {"depth": 3, "iterations": 400, "learning_rate": 0.05}),
        ("catboost_default", {"depth": 4, "iterations": 600, "learning_rate": 0.03}),
        ("catboost_deep", {"depth": 6, "iterations": 800, "learning_rate": 0.02}),
    ]
    for name, params in cb_configs:
        base = {"loss_function": "Logloss", "eval_metric": "Logloss",
                "random_seed": 42, "verbose": 0, "thread_count": _MAX_JOBS}
        base.update(params)
        def _make_cb(p=base):
            from catboost import CatBoostClassifier
            return CatBoostClassifier(**p)
        specs.append(ModelSpec(name=name, family="catboost", feature_subset="",
                              build_fn=_make_cb))

    # --- Random Forest variants ---
    rf_configs = [
        ("rf_shallow", {"n_estimators": 500, "max_depth": 6, "min_samples_leaf": 20}),
        ("rf_medium", {"n_estimators": 1000, "max_depth": 10, "min_samples_leaf": 10}),
        ("rf_deep", {"n_estimators": 500, "max_depth": 20, "min_samples_leaf": 5}),
        ("rf_stumps", {"n_estimators": 2000, "max_depth": 3, "min_samples_leaf": 50}),
    ]
    for name, params in rf_configs:
        base = {"random_state": 42, "n_jobs": _MAX_JOBS, "max_features": "sqrt"}
        base.update(params)
        def _make_rf(p=base):
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(**p)
        specs.append(ModelSpec(name=name, family="rf", feature_subset="",
                              build_fn=_make_rf))

    # --- Extra Trees ---
    et_configs = [
        ("et_medium", {"n_estimators": 1000, "max_depth": 10, "min_samples_leaf": 10}),
        ("et_deep", {"n_estimators": 500, "max_depth": 20, "min_samples_leaf": 5}),
    ]
    for name, params in et_configs:
        base = {"random_state": 42, "n_jobs": _MAX_JOBS, "max_features": "sqrt"}
        base.update(params)
        def _make_et(p=base):
            from sklearn.ensemble import ExtraTreesClassifier
            return ExtraTreesClassifier(**p)
        specs.append(ModelSpec(name=name, family="extra_trees", feature_subset="",
                              build_fn=_make_et))

    # --- HistGradientBoosting (sklearn native, handles NaN) ---
    hgb_configs = [
        ("hgb_shallow", {"max_iter": 300, "max_depth": 3, "learning_rate": 0.05, "min_samples_leaf": 50}),
        ("hgb_default", {"max_iter": 600, "max_depth": 5, "learning_rate": 0.03, "min_samples_leaf": 20}),
        ("hgb_deep", {"max_iter": 800, "max_depth": 8, "learning_rate": 0.02, "min_samples_leaf": 10}),
    ]
    for name, params in hgb_configs:
        base = {"random_state": 42, "l2_regularization": 1.0}
        base.update(params)
        def _make_hgb(p=base):
            from sklearn.ensemble import HistGradientBoostingClassifier
            return HistGradientBoostingClassifier(**p)
        specs.append(ModelSpec(name=name, family="hgb", feature_subset="",
                              build_fn=_make_hgb))

    # --- AdaBoost ---
    ada_configs = [
        ("ada_50", {"n_estimators": 50, "learning_rate": 1.0}),
        ("ada_200", {"n_estimators": 200, "learning_rate": 0.5}),
    ]
    for name, params in ada_configs:
        base = {"random_state": 42}
        base.update(params)
        def _make_ada(p=base):
            from sklearn.ensemble import AdaBoostClassifier
            return AdaBoostClassifier(**p)
        specs.append(ModelSpec(name=name, family="adaboost", feature_subset="",
                              build_fn=_make_ada, needs_imputation=True))

    # --- LogReg variants ---
    logreg_configs = [
        ("logreg_l2_01", {"C": 0.1, "penalty": "l2"}),
        ("logreg_l2_1", {"C": 1.0, "penalty": "l2"}),
        ("logreg_l2_10", {"C": 10.0, "penalty": "l2"}),
        ("logreg_l1_01", {"C": 0.1, "penalty": "l1", "solver": "saga"}),
        ("logreg_l1_1", {"C": 1.0, "penalty": "l1", "solver": "saga"}),
        ("logreg_elasticnet", {"C": 0.5, "penalty": "elasticnet", "solver": "saga", "l1_ratio": 0.5}),
    ]
    for name, params in logreg_configs:
        base = {"max_iter": 2000, "random_state": 42, "solver": "lbfgs"}
        base.update(params)
        def _make_lr(p=base):
            from sklearn.linear_model import LogisticRegression
            return LogisticRegression(**p)
        specs.append(ModelSpec(name=name, family="logreg", feature_subset="",
                              build_fn=_make_lr, needs_imputation=True, needs_scaling=True))

    # --- SGD (linear SVM / log loss) ---
    sgd_configs = [
        ("sgd_log", {"loss": "log_loss", "alpha": 1e-4}),
        ("sgd_hinge", {"loss": "modified_huber", "alpha": 1e-4}),
    ]
    for name, params in sgd_configs:
        base = {"max_iter": 2000, "random_state": 42, "n_jobs": _MAX_JOBS}
        base.update(params)
        def _make_sgd(p=base):
            from sklearn.linear_model import SGDClassifier
            return SGDClassifier(**p)
        specs.append(ModelSpec(name=name, family="sgd", feature_subset="",
                              build_fn=_make_sgd, needs_imputation=True, needs_scaling=True))

    # --- KNN ---
    knn_configs = [
        ("knn_5", {"n_neighbors": 5}),
        ("knn_20", {"n_neighbors": 20}),
        ("knn_50", {"n_neighbors": 50}),
        ("knn_100", {"n_neighbors": 100}),
    ]
    for name, params in knn_configs:
        base = {"n_jobs": _MAX_JOBS, "weights": "distance"}
        base.update(params)
        def _make_knn(p=base):
            from sklearn.neighbors import KNeighborsClassifier
            return KNeighborsClassifier(**p)
        specs.append(ModelSpec(name=name, family="knn", feature_subset="",
                              build_fn=_make_knn, needs_imputation=True, needs_scaling=True))

    # --- Naive Bayes ---
    def _make_gnb():
        from sklearn.naive_bayes import GaussianNB
        return GaussianNB()
    specs.append(ModelSpec(name="gnb", family="naive_bayes", feature_subset="",
                          build_fn=_make_gnb, needs_imputation=True))

    # --- LDA / QDA ---
    def _make_lda():
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
        return LinearDiscriminantAnalysis()
    specs.append(ModelSpec(name="lda", family="lda", feature_subset="",
                          build_fn=_make_lda, needs_imputation=True))

    lda_shrink_configs = [
        ("lda_shrink_auto", {"shrinkage": "auto", "solver": "lsqr"}),
    ]
    for name, params in lda_shrink_configs:
        def _make_lda_s(p=params):
            from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
            return LinearDiscriminantAnalysis(**p)
        specs.append(ModelSpec(name=name, family="lda", feature_subset="",
                              build_fn=_make_lda_s, needs_imputation=True))

    # --- MLP ---
    mlp_configs = [
        ("mlp_small", {"hidden_layer_sizes": (64,), "alpha": 0.01}),
        ("mlp_medium", {"hidden_layer_sizes": (128, 64), "alpha": 0.001}),
        ("mlp_large", {"hidden_layer_sizes": (256, 128, 64), "alpha": 0.001}),
        ("mlp_wide", {"hidden_layer_sizes": (512,), "alpha": 0.01}),
    ]
    for name, params in mlp_configs:
        base = {"max_iter": 500, "random_state": 42, "early_stopping": True,
                "validation_fraction": 0.15, "n_iter_no_change": 20, "learning_rate_init": 0.001}
        base.update(params)
        def _make_mlp(p=base):
            from sklearn.neural_network import MLPClassifier
            return MLPClassifier(**p)
        specs.append(ModelSpec(name=name, family="mlp", feature_subset="",
                              build_fn=_make_mlp, needs_imputation=True, needs_scaling=True))

    # --- Bagging (meta-ensemble with subsampling) ---
    def _make_bag_lr():
        from sklearn.ensemble import BaggingClassifier
        from sklearn.linear_model import LogisticRegression
        return BaggingClassifier(
            estimator=LogisticRegression(C=1.0, max_iter=1000, random_state=42),
            n_estimators=50, max_samples=0.8, max_features=0.7,
            random_state=42, n_jobs=-1
        )
    specs.append(ModelSpec(name="bag_logreg", family="bagging", feature_subset="",
                          build_fn=_make_bag_lr, needs_imputation=True, needs_scaling=True))

    return specs


def _regression_specs() -> list[ModelSpec]:
    specs = []

    # --- LGBM variants ---
    lgbm_configs = [
        ("lgbm_shallow", {"n_estimators": 300, "max_depth": 3, "num_leaves": 7, "learning_rate": 0.05}),
        ("lgbm_default", {"n_estimators": 600, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.03}),
        ("lgbm_deep", {"n_estimators": 800, "max_depth": 6, "num_leaves": 31, "learning_rate": 0.02}),
        ("lgbm_regularized", {"n_estimators": 600, "max_depth": 4, "num_leaves": 12, "learning_rate": 0.03,
                              "reg_alpha": 2.0, "reg_lambda": 5.0, "min_child_samples": 50}),
        ("lgbm_dart", {"n_estimators": 400, "max_depth": 4, "num_leaves": 15, "learning_rate": 0.05,
                       "boosting_type": "dart", "drop_rate": 0.1}),
    ]
    for name, params in lgbm_configs:
        base = {"objective": "huber", "alpha": 10.0, "metric": "huber",
                "random_state": 42, "verbosity": -1, "n_jobs": _MAX_JOBS,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "min_child_samples": 20, "reg_alpha": 0.5, "reg_lambda": 2.0}
        base.update(params)
        def _make_lgbm(p=base):
            from lightgbm import LGBMRegressor
            return LGBMRegressor(**p)
        specs.append(ModelSpec(name=name, family="lgbm", feature_subset="",
                              build_fn=_make_lgbm))

    # --- XGB variants ---
    xgb_configs = [
        ("xgb_shallow", {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.05}),
        ("xgb_default", {"n_estimators": 600, "max_depth": 4, "learning_rate": 0.03}),
        ("xgb_deep", {"n_estimators": 800, "max_depth": 6, "learning_rate": 0.02}),
    ]
    for name, params in xgb_configs:
        base = {"objective": "reg:pseudohubererror", "eval_metric": "mae",
                "random_state": 42, "verbosity": 0, "nthread": _MAX_JOBS,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "min_child_weight": 20, "reg_alpha": 0.5, "reg_lambda": 2.0}
        base.update(params)
        def _make_xgb(p=base):
            from xgboost import XGBRegressor
            return XGBRegressor(**p)
        specs.append(ModelSpec(name=name, family="xgb", feature_subset="",
                              build_fn=_make_xgb))

    # --- CatBoost ---
    cb_configs = [
        ("catboost_default", {"depth": 4, "iterations": 600, "learning_rate": 0.03}),
        ("catboost_deep", {"depth": 6, "iterations": 800, "learning_rate": 0.02}),
    ]
    for name, params in cb_configs:
        base = {"loss_function": "Huber:delta=10.0", "eval_metric": "MAE",
                "random_seed": 42, "verbose": 0, "thread_count": _MAX_JOBS}
        base.update(params)
        def _make_cb(p=base):
            from catboost import CatBoostRegressor
            return CatBoostRegressor(**p)
        specs.append(ModelSpec(name=name, family="catboost", feature_subset="",
                              build_fn=_make_cb))

    # --- Random Forest ---
    rf_configs = [
        ("rf_medium", {"n_estimators": 1000, "max_depth": 10, "min_samples_leaf": 10}),
        ("rf_deep", {"n_estimators": 500, "max_depth": 20, "min_samples_leaf": 5}),
    ]
    for name, params in rf_configs:
        base = {"random_state": 42, "n_jobs": _MAX_JOBS, "max_features": "sqrt"}
        base.update(params)
        def _make_rf(p=base):
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(**p)
        specs.append(ModelSpec(name=name, family="rf", feature_subset="",
                              build_fn=_make_rf))

    # --- Extra Trees ---
    def _make_et():
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor(n_estimators=1000, max_depth=12,
                                   min_samples_leaf=10, random_state=42, n_jobs=-1)
    specs.append(ModelSpec(name="et_medium", family="extra_trees", feature_subset="",
                          build_fn=_make_et))

    # --- HistGradientBoosting ---
    hgb_configs = [
        ("hgb_default", {"max_iter": 600, "max_depth": 5, "learning_rate": 0.03}),
        ("hgb_deep", {"max_iter": 800, "max_depth": 8, "learning_rate": 0.02}),
    ]
    for name, params in hgb_configs:
        base = {"random_state": 42, "l2_regularization": 1.0, "min_samples_leaf": 20,
                "loss": "absolute_error"}
        base.update(params)
        def _make_hgb(p=base):
            from sklearn.ensemble import HistGradientBoostingRegressor
            return HistGradientBoostingRegressor(**p)
        specs.append(ModelSpec(name=name, family="hgb", feature_subset="",
                              build_fn=_make_hgb))

    # --- Ridge ---
    ridge_configs = [
        ("ridge_01", {"alpha": 0.1}),
        ("ridge_1", {"alpha": 1.0}),
        ("ridge_10", {"alpha": 10.0}),
        ("ridge_100", {"alpha": 100.0}),
    ]
    for name, params in ridge_configs:
        def _make_ridge(p=params):
            from sklearn.linear_model import Ridge
            return Ridge(**p)
        specs.append(ModelSpec(name=name, family="ridge", feature_subset="",
                              build_fn=_make_ridge, needs_imputation=True, needs_scaling=True))

    # --- Lasso ---
    lasso_configs = [
        ("lasso_01", {"alpha": 0.1}),
        ("lasso_1", {"alpha": 1.0}),
    ]
    for name, params in lasso_configs:
        base = {"max_iter": 2000, "random_state": 42}
        base.update(params)
        def _make_lasso(p=base):
            from sklearn.linear_model import Lasso
            return Lasso(**p)
        specs.append(ModelSpec(name=name, family="lasso", feature_subset="",
                              build_fn=_make_lasso, needs_imputation=True, needs_scaling=True))

    # --- ElasticNet ---
    def _make_enet():
        from sklearn.linear_model import ElasticNet
        return ElasticNet(alpha=0.5, l1_ratio=0.5, max_iter=2000, random_state=42)
    specs.append(ModelSpec(name="elasticnet", family="elasticnet", feature_subset="",
                          build_fn=_make_enet, needs_imputation=True, needs_scaling=True))

    # --- KNN ---
    knn_configs = [
        ("knn_10", {"n_neighbors": 10}),
        ("knn_50", {"n_neighbors": 50}),
    ]
    for name, params in knn_configs:
        base = {"n_jobs": _MAX_JOBS, "weights": "distance"}
        base.update(params)
        def _make_knn(p=base):
            from sklearn.neighbors import KNeighborsRegressor
            return KNeighborsRegressor(**p)
        specs.append(ModelSpec(name=name, family="knn", feature_subset="",
                              build_fn=_make_knn, needs_imputation=True, needs_scaling=True))

    # --- MLP ---
    mlp_configs = [
        ("mlp_small", {"hidden_layer_sizes": (64,), "alpha": 0.01}),
        ("mlp_medium", {"hidden_layer_sizes": (128, 64), "alpha": 0.001}),
    ]
    for name, params in mlp_configs:
        base = {"max_iter": 500, "random_state": 42, "early_stopping": True,
                "validation_fraction": 0.15, "n_iter_no_change": 20, "learning_rate_init": 0.001}
        base.update(params)
        def _make_mlp(p=base):
            from sklearn.neural_network import MLPRegressor
            return MLPRegressor(**p)
        specs.append(ModelSpec(name=name, family="mlp", feature_subset="",
                              build_fn=_make_mlp, needs_imputation=True, needs_scaling=True))

    return specs


# ─── Training engine ─────────────────────────────────────────────────────────

@dataclass
class OOFResult:
    """Out-of-fold predictions for one model+feature combination."""
    uid: str
    model_name: str
    feature_subset: str
    family: str
    n_features: int
    oof_preds: np.ndarray  # aligned to full dataset index
    oof_mask: np.ndarray   # boolean: which indices have predictions
    metric: float          # primary metric (val log_loss for clf, val MAE for reg)
    train_metric: float = np.inf  # same metric computed on training folds
    train_time: float = 0.0
    failed: bool = False
    error_msg: str = ""

    @property
    def overfit_gap(self) -> float:
        """val_metric - train_metric. Large positive = overfitting."""
        if self.train_metric == np.inf:
            return np.nan
        return self.metric - self.train_metric


def _get_signal_components(X_shape: tuple) -> int | float:
    """
    Determine n_components for PCA from Marcenko-Pastur denoising.

    The denoising report tells us exactly how many eigenvalues exceed the MP
    noise bound (λ+). These are the signal components. If the report isn't
    found, fall back to 0.95 variance retention.
    """
    from strategy.config import FEATURES_ROOT
    import json

    # Try each target's denoising report (winner is the reference)
    for target in ["winner", "spread"]:
        report_path = FEATURES_ROOT / target / "denoising_report.json"
        if report_path.exists():
            with open(report_path) as f:
                report = json.load(f)
            n_signal = report.get("n_signal_eigenvalues")
            if n_signal and n_signal < X_shape[1]:
                return int(n_signal)

    # Fallback: retain 95% variance
    return 0.95


def _impute_and_scale(X_tr, X_val, scale: bool, apply_pca: bool = False):
    """
    Impute NaN with train median, optionally standardize + PCA whiten.

    When apply_pca=True, the rigorous sequence is:
      1. Drop columns that are entirely NaN in training fold (era-specific features)
      2. Impute remaining NaN with train median
      3. StandardScaler (fit on train, transform both)
      4. PCA(whiten=True) → W = Z V Λ^{-1/2}, guaranteeing W^T W = I

    This handles features that don't exist in early seasons (e.g., BPI started ~2007)
    by dropping them from folds where they have no training data.
    """
    # Drop columns entirely NaN in training data (era-specific features)
    all_nan_cols = X_tr.columns[X_tr.isna().all()]
    if len(all_nan_cols) > 0:
        X_tr = X_tr.drop(columns=all_nan_cols)
        X_val = X_val.drop(columns=all_nan_cols)

    # Also drop columns with zero variance in training (constant after imputation)
    medians = X_tr.median()
    X_tr_filled = X_tr.fillna(medians)
    X_val_filled = X_val.fillna(medians)
    zero_var_cols = X_tr_filled.columns[X_tr_filled.std() == 0]
    if len(zero_var_cols) > 0:
        X_tr_filled = X_tr_filled.drop(columns=zero_var_cols)
        X_val_filled = X_val_filled.drop(columns=zero_var_cols)

    if apply_pca:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        # Standardize BEFORE PCA (PCA is scale-variant)
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr_filled.values)
        X_val_scaled = scaler.transform(X_val_filled.values)
        # Use Marcenko-Pastur signal eigenvalue count if available, else 0.95 variance
        n_components = _get_signal_components(X_tr_scaled.shape)
        pca = PCA(n_components=n_components, whiten=True, random_state=42)
        X_tr_pca = pca.fit_transform(X_tr_scaled)
        X_val_pca = pca.transform(X_val_scaled)
        pc_cols = [f"PC_{i}" for i in range(X_tr_pca.shape[1])]
        X_tr = pd.DataFrame(X_tr_pca, index=X_tr.index, columns=pc_cols)
        X_val = pd.DataFrame(X_val_pca, index=X_val.index, columns=pc_cols)
    elif scale:
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr_filled.values)
        X_val_scaled = scaler.transform(X_val_filled.values)
        X_tr = pd.DataFrame(X_tr_scaled, index=X_tr.index, columns=X_tr_filled.columns)
        X_val = pd.DataFrame(X_val_scaled, index=X_val.index, columns=X_val_filled.columns)
    else:
        X_tr = X_tr_filled
        X_val = X_val_filled

    return X_tr, X_val


def _downsample_curve(values: list[float], n_points: int = 20) -> list[float]:
    """Downsample a loss curve to n_points evenly spaced values."""
    if len(values) <= n_points:
        return values
    idx = np.linspace(0, len(values) - 1, n_points, dtype=int)
    return [values[i] for i in idx]


def _write_curve_log(curves_dir: Path, uid: str, target: str, fold_curves: list[dict]) -> None:
    """Write per-fold learning curves to a JSON file. Silent on failure."""
    try:
        curves_dir.mkdir(parents=True, exist_ok=True)
        path = curves_dir / f"{target}__{uid}.json"
        with open(path, "w") as f:
            json.dump({"uid": uid, "target": target, "folds": fold_curves}, f)
    except Exception:
        pass


def _fit_with_curve(mdl, family: str, X_tr, y_tr, X_val, y_val, task: str) -> list[float]:
    """
    Fit a model and return a downsampled per-round val loss curve.
    Returns [] for models without iterative training (RF, KNN, etc.).
    """
    curve = []

    if family == "lgbm":
        import lightgbm as lgb

        fold_train = []
        fold_val = []

        class _Recorder:
            def __call__(self, env):
                results = env.evaluation_result_list
                if len(results) >= 2:
                    fold_train.append(results[0][2])
                    fold_val.append(results[1][2])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(
                X_tr, y_tr,
                eval_set=[(X_tr, y_tr), (X_val, y_val)],
                eval_names=["train", "val"],
                callbacks=[lgb.log_evaluation(period=-1), _Recorder()],
            )
        # Return interleaved [round, train, val] triples downsampled
        if fold_val:
            idx = np.linspace(0, len(fold_val) - 1, min(20, len(fold_val)), dtype=int)
            curve = [{"round": int(i), "train": fold_train[i], "val": fold_val[i]}
                     for i in idx]

    elif family == "xgb":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_val, y_val)], verbose=False)
        curve = []  # evals_result tracking omitted; final scalar captured separately

    elif family == "mlp":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(X_tr, y_tr)
        if hasattr(mdl, "loss_curve_"):
            lc = _downsample_curve(mdl.loss_curve_)
            vc = _downsample_curve(mdl.validation_scores_ if hasattr(mdl, "validation_scores_")
                                   else [])
            n = len(lc)
            curve = [{"round": i, "train": lc[i],
                      "val": (1 - vc[i]) if i < len(vc) else None}
                     for i in range(n)]

    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(X_tr, y_tr)

    return curve


def train_single_model(
    spec: ModelSpec,
    X: pd.DataFrame,
    y: pd.Series,
    seasons: pd.Series,
    task: str,
    curves_dir: Path | None = None,
) -> OOFResult:
    """Train one model with LOYO CV. Writes per-fold learning curves to curves_dir if set."""
    t0 = time.time()
    all_seasons = sorted(seasons.unique())
    n = len(X)
    oof_preds = np.full(n, np.nan)
    oof_mask = np.zeros(n, dtype=bool)
    train_losses = []
    fold_curves = []

    try:
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

            if spec.needs_imputation or spec.needs_scaling or spec.needs_pca:
                X_tr, X_val = _impute_and_scale(X_tr, X_val, spec.needs_scaling, spec.needs_pca)

            mdl = spec.build_fn()
            curve = _fit_with_curve(mdl, spec.family, X_tr, y_tr, X_val, y_val, task)
            if curve:
                fold_curves.append({"season": season, "curve": curve})

            if task == "classification":
                if hasattr(mdl, "predict_proba"):
                    val_p = mdl.predict_proba(X_val)[:, 1]
                    train_p = mdl.predict_proba(X_tr)[:, 1]
                else:
                    val_p = 1 / (1 + np.exp(-mdl.decision_function(X_val)))
                    train_p = 1 / (1 + np.exp(-mdl.decision_function(X_tr)))
                train_p = np.clip(train_p, 1e-7, 1 - 1e-7)
                train_losses.append(log_loss(y_tr, train_p))
            else:
                val_p = mdl.predict(X_val)
                train_p = mdl.predict(X_tr)
                train_losses.append(float(np.mean(np.abs(y_tr.values - train_p))))

            val_idx = np.where(val_mask)[0]
            oof_preds[val_idx] = val_p
            oof_mask[val_idx] = True

    except Exception as e:
        return OOFResult(
            uid=spec.uid(), model_name=spec.name, feature_subset=spec.feature_subset,
            family=spec.family, n_features=X.shape[1],
            oof_preds=oof_preds, oof_mask=oof_mask,
            metric=np.inf, train_time=time.time() - t0,
            failed=True, error_msg=str(e)
        )

    valid = oof_mask & ~np.isnan(oof_preds)
    if valid.sum() < 100:
        return OOFResult(
            uid=spec.uid(), model_name=spec.name, feature_subset=spec.feature_subset,
            family=spec.family, n_features=X.shape[1],
            oof_preds=oof_preds, oof_mask=oof_mask,
            metric=np.inf, train_time=time.time() - t0,
            failed=True, error_msg="Too few valid OOF predictions"
        )

    y_valid = y.values[valid]
    p_valid = oof_preds[valid]
    train_metric = float(np.mean(train_losses)) if train_losses else np.inf

    if task == "classification":
        p_valid = np.clip(p_valid, 1e-7, 1 - 1e-7)
        metric = log_loss(y_valid, p_valid)
    else:
        metric = float(np.mean(np.abs(y_valid - p_valid)))

    # Write curve log as a side effect — does not affect the returned result
    if curves_dir is not None and fold_curves:
        _write_curve_log(curves_dir, spec.uid(), spec.feature_subset, fold_curves)

    return OOFResult(
        uid=spec.uid(), model_name=spec.name, feature_subset=spec.feature_subset,
        family=spec.family, n_features=X.shape[1],
        oof_preds=oof_preds, oof_mask=oof_mask,
        metric=metric, train_metric=train_metric, train_time=time.time() - t0,
    )


# ─── Orthogonality analysis ─────────────────────────────────────────────────

def compute_correlation_matrix(results: list[OOFResult]) -> pd.DataFrame:
    """Compute pairwise Pearson correlation of OOF predictions."""
    # Use only indices where ALL models have predictions
    common_mask = np.ones(len(results[0].oof_preds), dtype=bool)
    for r in results:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)

    preds_matrix = np.column_stack([r.oof_preds[common_mask] for r in results])
    names = [r.uid for r in results]
    corr = np.corrcoef(preds_matrix.T)
    return pd.DataFrame(corr, index=names, columns=names)


def select_diverse_ensemble(
    results: list[OOFResult],
    max_models: int = 30,
    min_correlation_threshold: float = 0.98,
    max_metric_ratio: float = 1.15,
) -> list[OOFResult]:
    """
    Greedy forward selection: pick models that add diversity.

    1. Start with best model by metric
    2. Add model that has lowest max-correlation with current ensemble AND
       metric within max_metric_ratio of best
    3. Repeat until max_models or no model below min_correlation_threshold
    """
    if not results:
        return []

    # Sort by metric (lower is better)
    ranked = sorted(results, key=lambda r: r.metric)
    best_metric = ranked[0].metric
    cutoff = best_metric * max_metric_ratio

    # Filter to acceptable metric range
    candidates = [r for r in ranked if r.metric <= cutoff]
    if not candidates:
        candidates = ranked[:max_models]

    # Build common mask
    common_mask = np.ones(len(candidates[0].oof_preds), dtype=bool)
    for r in candidates:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)

    selected = [candidates[0]]
    remaining = candidates[1:]

    while len(selected) < max_models and remaining:
        best_score = -np.inf
        best_idx = -1

        sel_preds = np.column_stack([r.oof_preds[common_mask] for r in selected])

        for i, cand in enumerate(remaining):
            cand_pred = cand.oof_preds[common_mask]
            # Max correlation with any selected model
            corrs = np.array([np.corrcoef(cand_pred, sel_preds[:, j])[0, 1]
                              for j in range(sel_preds.shape[1])])
            max_corr = corrs.max()

            if max_corr >= min_correlation_threshold:
                continue

            # Score: lower correlation is better, penalize bad metric slightly
            diversity_score = (1 - max_corr) - 0.1 * (cand.metric - best_metric) / best_metric
            if diversity_score > best_score:
                best_score = diversity_score
                best_idx = i

        if best_idx < 0:
            break

        selected.append(remaining[best_idx])
        remaining.pop(best_idx)

    return selected


# ─── Ensemble weight optimization ───────────────────────────────────────────

def optimize_weights(
    results: list[OOFResult],
    y: pd.Series,
    task: str,
    method: str = "minimize_loss",
) -> np.ndarray:
    """
    Find optimal ensemble weights via constrained optimization.
    Weights sum to 1, all non-negative.
    """
    from scipy.optimize import minimize

    common_mask = np.ones(len(y), dtype=bool)
    for r in results:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)

    preds_matrix = np.column_stack([r.oof_preds[common_mask] for r in results])
    y_valid = y.values[common_mask]
    n_models = len(results)

    if task == "classification":
        def objective(w):
            blend = preds_matrix @ w
            blend = np.clip(blend, 1e-7, 1 - 1e-7)
            return log_loss(y_valid, blend)
    else:
        def objective(w):
            blend = preds_matrix @ w
            return float(np.mean(np.abs(y_valid - blend)))

    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}
    bounds = [(0, 1)] * n_models
    w0 = np.ones(n_models) / n_models

    result = minimize(objective, w0, method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-10})

    if result.success:
        return result.x
    else:
        return w0


# ─── Model persistence ──────────────────────────────────────────────────────

def _pickle_ensemble(
    ensemble: list[OOFResult],
    weights: np.ndarray,
    df: pd.DataFrame,
    feature_subsets: dict[str, list[str]],
    y: pd.Series,
    task: str,
    pkl_path: Path,
    verbose: bool = True,
) -> None:
    """
    Retrain each selected ensemble model on the FULL dataset and pickle.
    These are the models used for live prediction — not LOYO CV folds.
    """
    import pickle

    if verbose:
        print(f"\n  Retraining {len(ensemble)} selected models on full data for pickling...")

    trained = []
    for i, (r, w) in enumerate(zip(ensemble, weights)):
        feats = feature_subsets[r.feature_subset]
        X_full = df[feats].copy()
        y_full = y.copy()

        if r.needs_imputation if hasattr(r, "needs_imputation") else False:
            X_full = X_full.fillna(X_full.median())

        # Rebuild the spec to get needs_imputation / needs_scaling flags
        all_specs = {s.name: s for s in _build_model_specs(task)}
        spec = all_specs.get(r.model_name)

        if spec is not None and (spec.needs_imputation or spec.needs_scaling):
            medians = X_full.median()
            X_full = X_full.fillna(medians)
            if spec.needs_scaling:
                means = X_full.mean()
                stds = X_full.std().replace(0, 1)
                X_full = (X_full - means) / stds
                trained.append({
                    "uid": r.uid, "weight": float(w), "feature_subset": r.feature_subset,
                    "features": feats, "model": spec.build_fn().fit(X_full, y_full),
                    "needs_scaling": True, "scale_mean": means.to_dict(),
                    "scale_std": stds.to_dict(), "impute_median": medians.to_dict(),
                })
                if verbose:
                    print(f"    [{i+1}/{len(ensemble)}] {r.uid}")
                continue

        mdl = spec.build_fn() if spec else None
        if mdl is None:
            if verbose:
                print(f"    [{i+1}/{len(ensemble)}] {r.uid} — SKIPPED (spec not found)")
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(X_full, y_full)

        trained.append({
            "uid": r.uid, "weight": float(w), "feature_subset": r.feature_subset,
            "features": feats, "model": mdl,
            "needs_scaling": False, "scale_mean": None,
            "scale_std": None, "impute_median": None,
        })
        if verbose:
            print(f"    [{i+1}/{len(ensemble)}] {r.uid}")

    with open(pkl_path, "wb") as f:
        pickle.dump({"task": task, "models": trained}, f)
    if verbose:
        print(f"  Pickled {len(trained)} models -> {pkl_path}")


def retrain_from_config(
    target: str = "winner",
    verbose: bool = True,
) -> Path:
    """
    Reads the saved ensemble config JSON and retrains only the selected
    models on full data. Much faster than a full candidate search — use
    this locally after an EC2 run to get deployable models.

    Returns the path to the saved pkl file.
    """
    import pickle

    task = "classification" if target == "winner" else "regression"
    out_dir = _cfg.OUTPUT_DIR / "ensemble"
    config_path = out_dir / f"{target}_ensemble_config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"No config found at {config_path}. Run the full ensemble first.")

    with open(config_path) as f:
        config = json.load(f)

    survivors = _load_survivors(target)
    from strategy.config import WINNER_PARQUET, SPREAD_PARQUET
    parquet_path = WINNER_PARQUET if target == "winner" else SPREAD_PARQUET
    df_raw = pd.read_parquet(parquet_path)
    target_col = "target_winner" if target == "winner" else "target_spread"
    valid = df_raw[target_col].notna()
    df_raw = df_raw[valid].reset_index(drop=True)

    feature_subsets = build_feature_subsets(survivors)
    y_series = df_raw[target_col].astype(int if task == "classification" else float)

    selected_uids = {m["uid"] for m in config["models"]}
    weights_map = {m["uid"]: m["weight"] for m in config["models"]}

    if verbose:
        print(f"\n  Retraining {len(selected_uids)} models from config (full data)...")
        print(f"  Dataset: {len(df_raw)} games, {len(survivors)} survivors")

    all_specs = {s.name: s for s in _build_model_specs(task)}
    trained = []

    for uid in selected_uids:
        model_name, subset_name = uid.split("__", 1)
        spec = all_specs.get(model_name)
        w = weights_map[uid]

        if spec is None:
            if verbose:
                print(f"  SKIP {uid}: spec not found")
            continue
        if subset_name not in feature_subsets:
            if verbose:
                print(f"  SKIP {uid}: subset '{subset_name}' not in feature_subsets")
            continue

        feats = feature_subsets[subset_name]
        X_full = df_raw[feats].copy()

        impute_median = None
        scale_mean = None
        scale_std = None

        if spec.needs_imputation or spec.needs_scaling:
            impute_median = X_full.median()
            X_full = X_full.fillna(impute_median)
            if spec.needs_scaling:
                scale_mean = X_full.mean()
                scale_std = X_full.std().replace(0, 1)
                X_full = (X_full - scale_mean) / scale_std

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl = spec.build_fn()
            mdl.fit(X_full, y_series)

        trained.append({
            "uid": uid, "weight": w, "feature_subset": subset_name,
            "features": feats, "model": mdl,
            "needs_scaling": spec.needs_scaling,
            "scale_mean": scale_mean.to_dict() if scale_mean is not None else None,
            "scale_std": scale_std.to_dict() if scale_std is not None else None,
            "impute_median": impute_median.to_dict() if impute_median is not None else None,
        })
        if verbose:
            print(f"  Trained {uid}")

    pkl_path = out_dir / f"{target}_ensemble_models.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump({"task": task, "models": trained}, f)

    if verbose:
        print(f"\n  Done. {len(trained)} models -> {pkl_path}")

    return pkl_path


def predict_from_pkl(pkl_path: Path, X: pd.DataFrame) -> np.ndarray:
    """
    Load a pickled ensemble and predict on new data.
    X must contain all required feature columns.
    Returns probability array (classification) or prediction array (regression).
    """
    import pickle

    with open(pkl_path, "rb") as f:
        bundle = pickle.load(f)

    task = bundle["task"]
    preds = []
    weights = []

    for m in bundle["models"]:
        feats = m["features"]
        missing = [f for f in feats if f not in X.columns]
        if missing:
            raise ValueError(f"Model {m['uid']} needs features not in X: {missing}")

        X_sub = X[feats].copy()

        if m["impute_median"]:
            medians = pd.Series(m["impute_median"])
            X_sub = X_sub.fillna(medians)
        if m["needs_scaling"]:
            means = pd.Series(m["scale_mean"])
            stds = pd.Series(m["scale_std"])
            X_sub = (X_sub - means) / stds

        mdl = m["model"]
        if task == "classification":
            p = mdl.predict_proba(X_sub)[:, 1]
        else:
            p = mdl.predict(X_sub)

        preds.append(p)
        weights.append(m["weight"])

    weights = np.array(weights)
    weights /= weights.sum()
    blend = np.column_stack(preds) @ weights

    if task == "classification":
        blend = np.clip(blend, 1e-7, 1 - 1e-7)

    return blend


# ─── Main orchestrator ───────────────────────────────────────────────────────

def run_ensemble(
    target: str = "winner",
    max_candidates: int | None = None,
    verbose: bool = True,
) -> dict:
    """
    Full ensemble pipeline:
    1. Load data
    2. Generate model×feature_subset candidates
    3. Train all with LOYO CV
    4. Analyze orthogonality
    5. Select diverse subset
    6. Optimize weights
    7. Report

    Returns dict with all results for downstream use.
    """
    task = "classification" if target == "winner" else "regression"
    target_col = "target_winner" if target == "winner" else "target_spread"

    # Load survivors from the feature importance pipeline's filtered output
    survivors = _load_survivors(target)

    from strategy.config import WINNER_PARQUET, SPREAD_PARQUET
    parquet_path = WINNER_PARQUET if target == "winner" else SPREAD_PARQUET
    df_raw = pd.read_parquet(parquet_path)
    valid = df_raw[target_col].notna()
    df_raw = df_raw[valid].reset_index(drop=True)

    # Verify all survivor features exist in the data
    missing = [f for f in survivors if f not in df_raw.columns]
    if missing:
        raise ValueError(f"{len(missing)} survivor features not in parquet: {missing[:5]}")

    # Build semantic subsets from survivors only
    feature_subsets = build_feature_subsets(survivors)

    if verbose:
        print(f"\n{'='*70}")
        print(f"  ENSEMBLE PIPELINE — target: {target} ({task})")
        print(f"  Dataset: {len(df_raw)} games")
        print(f"  Survivor features (from importance pipeline): {len(survivors)}")
        print(f"  Feature subsets: {len(feature_subsets)}")
        for name, feats in sorted(feature_subsets.items()):
            print(f"    {name}: {len(feats)} features")
        print(f"{'='*70}\n")

    # Generate all model×feature combinations
    model_specs = _build_model_specs(task)
    candidates = []

    for spec in model_specs:
        for subset_name, subset_feats in feature_subsets.items():
            s = ModelSpec(
                name=spec.name,
                family=spec.family,
                feature_subset=subset_name,
                build_fn=spec.build_fn,
                needs_imputation=spec.needs_imputation,
                needs_scaling=spec.needs_scaling,
            )
            candidates.append(s)

    if max_candidates and len(candidates) > max_candidates:
        # Deterministic subset: prioritize model diversity
        import random
        random.seed(42)
        random.shuffle(candidates)
        candidates = candidates[:max_candidates]

    if verbose:
        print(f"  Total candidate models: {len(candidates)}")
        families = {}
        for c in candidates:
            families.setdefault(c.family, 0)
            families[c.family] += 1
        for f, count in sorted(families.items()):
            print(f"    {f}: {count}")
        print()

    # Output dirs (needed before workers start writing curve logs)
    out_dir = _cfg.OUTPUT_DIR / "ensemble"
    out_dir.mkdir(parents=True, exist_ok=True)
    curves_dir = out_dir / "curves"
    curves_dir.mkdir(parents=True, exist_ok=True)

    # Train all candidates (parallelized across models)
    y_series = df_raw[target_col].copy()
    if target == "winner":
        y_series = y_series.astype(int)
    else:
        y_series = y_series.astype(float)
    seasons_series = df_raw["season"].copy()

    if verbose:
        print(f"  Parallelism: {_N_PARALLEL_MODELS} models × {_MAX_JOBS} threads/model "
              f"= {_N_PARALLEL_MODELS * _MAX_JOBS} threads (of {_N_CPUS} available)")
        print(f"  Learning curves -> {curves_dir}/\n")

    from joblib import Parallel, delayed

    def _train_one(idx):
        spec = candidates[idx]
        feats = feature_subsets[spec.feature_subset]
        X_sub = df_raw[feats].copy()
        result = train_single_model(spec, X_sub, y_series, seasons_series, task,
                                    curves_dir=curves_dir)
        return idx, result

    all_results_map: dict[int, OOFResult] = {}
    n_total = len(candidates)
    done = 0

    for idx, result in Parallel(
        n_jobs=_N_PARALLEL_MODELS,
        backend="loky",
        return_as="generator_unordered",
    )(delayed(_train_one)(i) for i in range(n_total)):
        all_results_map[idx] = result
        done += 1
        if verbose:
            spec = candidates[idx]
            n_feats = len(feature_subsets[spec.feature_subset])
            if result.failed:
                print(f"  [{done}/{n_total}] {spec.uid()} "
                      f"({n_feats} feats)... FAILED: {result.error_msg[:60]}", flush=True)
            else:
                gap = result.overfit_gap
                flag = " ⚠️" if gap / max(result.train_metric, 1e-7) > 0.05 else ""
                print(f"  [{done}/{n_total}] {spec.uid()} "
                      f"({n_feats} feats)... train={result.train_metric:.4f} "
                      f"val={result.metric:.4f} gap={gap:+.4f}{flag} "
                      f"[{result.train_time:.1f}s]", flush=True)

    # Restore original order
    all_results = [all_results_map[i] for i in range(n_total)]

    # Filter successful
    good_results = [r for r in all_results if not r.failed]
    if verbose:
        print(f"\n  Successful: {len(good_results)}/{len(all_results)}")

    if len(good_results) < 2:
        print("  ERROR: fewer than 2 models succeeded. Cannot ensemble.")
        return {"all_results": all_results, "good_results": good_results}

    # Sort by metric
    good_results.sort(key=lambda r: r.metric)
    if verbose:
        metric_name = 'log_loss' if task == 'classification' else 'MAE'
        print(f"\n  Top 10 models by {metric_name} (train | val | gap):")
        for r in good_results[:10]:
            gap = r.overfit_gap
            flag = " ⚠️ OVERFIT" if gap / max(r.train_metric, 1e-7) > 0.05 else ""
            print(f"    {r.uid:<45} train={r.train_metric:.4f} val={r.metric:.4f} "
                  f"gap={gap:+.4f}{flag}")

    # Correlation analysis
    corr_matrix = compute_correlation_matrix(good_results[:50])

    # Select diverse ensemble
    ensemble = select_diverse_ensemble(good_results)
    if verbose:
        print(f"\n  Selected ensemble ({len(ensemble)} models):")
        for r in ensemble:
            print(f"    {r.uid:<50} metric={r.metric:.4f}")

    # Optimize weights
    weights = optimize_weights(ensemble, y_series, task)

    # Compute ensemble metric
    common_mask = np.ones(len(y_series), dtype=bool)
    for r in ensemble:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)

    ensemble_preds = np.column_stack([r.oof_preds[common_mask] for r in ensemble]) @ weights
    y_valid = y_series.values[common_mask]

    if task == "classification":
        ensemble_preds = np.clip(ensemble_preds, 1e-7, 1 - 1e-7)
        ensemble_metric = log_loss(y_valid, ensemble_preds)
        ensemble_auc = roc_auc_score(y_valid, ensemble_preds)
        ensemble_brier = brier_score_loss(y_valid, ensemble_preds)
        ensemble_acc = accuracy_score(y_valid, (ensemble_preds >= 0.5).astype(int))
    else:
        ensemble_metric = float(np.mean(np.abs(y_valid - ensemble_preds)))

    if verbose:
        print(f"\n  {'='*60}")
        print(f"  ENSEMBLE RESULT")
        print(f"  {'='*60}")
        if task == "classification":
            print(f"  Log Loss:  {ensemble_metric:.4f}  (best single: {good_results[0].metric:.4f})")
            print(f"  AUC:       {ensemble_auc:.4f}")
            print(f"  Brier:     {ensemble_brier:.4f}")
            print(f"  Accuracy:  {ensemble_acc:.4f}")
        else:
            print(f"  MAE:       {ensemble_metric:.4f}  (best single: {good_results[0].metric:.4f})")

        print(f"\n  Weights (non-zero):")
        for r, w in sorted(zip(ensemble, weights), key=lambda x: -x[1]):
            if w > 0.001:
                print(f"    {w:.3f}  {r.uid}")

    # Pairwise correlations within ensemble
    if verbose and len(ensemble) > 1:
        ens_corr = compute_correlation_matrix(ensemble)
        mask = np.triu(np.ones_like(ens_corr, dtype=bool), k=1)
        upper_corrs = ens_corr.values[mask]
        print(f"\n  Ensemble pairwise correlations:")
        print(f"    Mean: {upper_corrs.mean():.3f}")
        print(f"    Max:  {upper_corrs.max():.3f}")
        print(f"    Min:  {upper_corrs.min():.3f}")

    # Save results
    # Save ensemble config
    config = {
        "target": target,
        "task": task,
        "n_candidates": len(candidates),
        "n_successful": len(good_results),
        "n_ensemble": len(ensemble),
        "ensemble_metric": float(ensemble_metric),
        "best_single_metric": float(good_results[0].metric),
        "models": [
            {"uid": r.uid, "weight": float(w), "metric": float(r.metric),
             "family": r.family, "feature_subset": r.feature_subset,
             "n_features": r.n_features}
            for r, w in zip(ensemble, weights) if w > 0.001
        ],
    }
    if task == "classification":
        config["ensemble_auc"] = float(ensemble_auc)
        config["ensemble_brier"] = float(ensemble_brier)
        config["ensemble_acc"] = float(ensemble_acc)

    with open(out_dir / f"{target}_ensemble_config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Save full leaderboard
    leaderboard = pd.DataFrame([
        {"uid": r.uid, "model_name": r.model_name, "family": r.family,
         "feature_subset": r.feature_subset, "n_features": r.n_features,
         "train_metric": r.train_metric, "val_metric": r.metric,
         "overfit_gap": r.overfit_gap, "train_time": r.train_time}
        for r in good_results
    ])
    leaderboard.to_csv(out_dir / f"{target}_leaderboard.csv", index=False)

    # Save correlation matrix (top 50)
    corr_matrix.to_csv(out_dir / f"{target}_correlation_matrix.csv")

    # Save OOF predictions for the ensemble
    oof_df = pd.DataFrame({"y_true": y_valid, "y_pred_ensemble": ensemble_preds})
    for r, w in zip(ensemble, weights):
        if w > 0.001:
            oof_df[f"pred_{r.uid}"] = r.oof_preds[common_mask]
    oof_df["season"] = seasons_series.values[common_mask]
    oof_df["game_date"] = df_raw["game_date"].values[common_mask]
    oof_df.to_csv(out_dir / f"{target}_ensemble_oof.csv", index=False)

    # Retrain selected ensemble models on full data and pickle
    pkl_path = out_dir / f"{target}_ensemble_models.pkl"
    _pickle_ensemble(ensemble, weights, df_raw, feature_subsets, y_series,
                     task, pkl_path, verbose)

    if verbose:
        print(f"\n  Saved to: {out_dir}/")
        print(f"    {target}_ensemble_config.json")
        print(f"    {target}_leaderboard.csv")
        print(f"    {target}_correlation_matrix.csv")
        print(f"    {target}_ensemble_oof.csv")
        print(f"    {target}_ensemble_models.pkl")

    return {
        "all_results": all_results,
        "good_results": good_results,
        "ensemble": ensemble,
        "weights": weights,
        "ensemble_metric": ensemble_metric,
        "config": config,
        "correlation_matrix": corr_matrix,
    }


# ─── Specialist-routed ensemble (feature-aware) ──────────────────────────────

def _get_specialist_feature_group(family: str) -> str:
    """Map model family to feature group based on SPECIALIST_ROUTING config."""
    from strategy.config import SPECIALIST_ROUTING
    for pool_name, pool_cfg in SPECIALIST_ROUTING.items():
        if family in pool_cfg["models"]:
            return pool_cfg["feature_group"]
    return "trees"


def build_specialist_candidates(task: str = "classification") -> list[ModelSpec]:
    """
    Build candidate specs with feature_subset pre-assigned based on model family.
    Each model is routed to the feature group that matches its signal-exploitation capacity.

    Linear models get ACCEPTED features only (proven standalone via SFI).
    Tree models get ACCEPTED + COMPLEMENTARY (interaction features).
    No PCA needed — the accepted features are already low-dimensional and validated.
    """
    all_specs = _build_model_specs(task)
    routed = []
    for spec in all_specs:
        group = _get_specialist_feature_group(spec.family)
        routed_spec = ModelSpec(
            name=spec.name,
            family=spec.family,
            feature_subset=group,
            build_fn=spec.build_fn,
            needs_imputation=spec.needs_imputation,
            needs_scaling=spec.needs_scaling,
            needs_pca=False,
        )
        routed.append(routed_spec)
    return routed


def run_stacking(
    results: list[OOFResult],
    y: pd.Series,
    seasons: pd.Series,
    task: str,
) -> tuple[object, float]:
    """
    Train a LogReg meta-learner on specialist OOF predictions using inner LOYO.
    Returns (meta_model, loyo_metric).
    """
    from sklearn.linear_model import LogisticRegression, Ridge

    common_mask = np.ones(len(y), dtype=bool)
    for r in results:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)

    preds_matrix = np.column_stack([r.oof_preds[common_mask] for r in results])
    y_valid = y.values[common_mask]
    seasons_valid = seasons.values[common_mask]

    unique_seasons = sorted(set(seasons_valid) - SKIP_SEASONS)
    meta_oof = np.full(len(y_valid), np.nan)

    for test_season in unique_seasons:
        train_mask = seasons_valid != test_season
        test_mask = seasons_valid == test_season

        if train_mask.sum() < 100:
            continue

        X_meta_train = preds_matrix[train_mask]
        X_meta_test = preds_matrix[test_mask]
        y_meta_train = y_valid[train_mask]

        if task == "classification":
            meta = LogisticRegression(C=1.0, penalty="l2", max_iter=1000, random_state=42)
            meta.fit(X_meta_train, y_meta_train)
            meta_oof[test_mask] = meta.predict_proba(X_meta_test)[:, 1]
        else:
            meta = Ridge(alpha=1.0)
            meta.fit(X_meta_train, y_meta_train)
            meta_oof[test_mask] = meta.predict(X_meta_test)

    valid_meta = ~np.isnan(meta_oof)
    if valid_meta.sum() < 100:
        return None, float("inf")

    if task == "classification":
        meta_oof_valid = np.clip(meta_oof[valid_meta], 1e-7, 1 - 1e-7)
        metric = log_loss(y_valid[valid_meta], meta_oof_valid)
    else:
        metric = float(np.mean(np.abs(y_valid[valid_meta] - meta_oof[valid_meta])))

    # Fit final meta-model on all data for deployment
    if task == "classification":
        final_meta = LogisticRegression(C=1.0, penalty="l2", max_iter=1000, random_state=42)
    else:
        final_meta = Ridge(alpha=1.0)
    final_meta.fit(preds_matrix, y_valid)

    return final_meta, metric


def run_specialist_ensemble(
    target: str,
    verbose: bool = True,
) -> dict:
    """
    Feature-routed ensemble pipeline:
    1. Load per-group feature lists (must exist from feature_routing.py)
    2. Build specialists routed to appropriate feature groups
    3. Train all with LOYO CV
    4. Select diverse subset
    5. Compare flat weights vs stacking — auto-select winner
    6. Retrain final models, pickle

    Returns dict with all results.
    """
    import pickle
    from strategy.config import FEATURES_ROOT, STACKING_MIN_IMPROVEMENT
    from strategy.data import TARGET_MAP

    target_col, task = TARGET_MAP[target]

    # Verify per-group feature lists exist
    filtered_dir = FEATURES_ROOT / target / "filtered"
    groups_available = {}
    for group in ["trees", "linear", "diversity", "full"]:
        path = filtered_dir / f"feature_list_{group}.txt"
        if path.exists():
            from strategy.config import load_feature_list
            groups_available[group] = load_feature_list(path)

    if not groups_available:
        raise FileNotFoundError(
            f"No per-group feature lists for target '{target}'. "
            f"Run: from strategy.feature_routing import run_routing; run_routing('{target}')"
        )

    # Load data
    from strategy.config import GAME_PARQUET
    df_raw = pd.read_parquet(GAME_PARQUET)
    valid = df_raw[target_col].notna()
    df_raw = df_raw[valid].reset_index(drop=True)

    y_series = df_raw[target_col].copy()
    if task == "classification":
        y_series = y_series.astype(int)
    elif task == "multiclass":
        y_series = y_series.astype(str)
    else:
        y_series = y_series.astype(float)
    seasons_series = df_raw["season"].copy()

    # Verify features exist in parquet
    for group, feats in groups_available.items():
        missing = [f for f in feats if f not in df_raw.columns]
        if missing:
            logger.warning("Group '%s': %d features missing from parquet, removing", group, len(missing))
            groups_available[group] = [f for f in feats if f in df_raw.columns]

    # Build specialist candidates
    candidates = build_specialist_candidates(task)
    # Filter to only those whose feature_subset has available features
    candidates = [c for c in candidates if c.feature_subset in groups_available]

    if verbose:
        print(f"\n{'='*70}")
        print(f"  SPECIALIST ENSEMBLE — target: {target} ({task})")
        print(f"  Dataset: {len(df_raw)} games")
        print(f"  Feature groups:")
        for g, feats in groups_available.items():
            print(f"    {g}: {len(feats)} features")
        print(f"  Total specialist candidates: {len(candidates)}")
        print(f"  Parallelism: {_N_PARALLEL_MODELS} models × {_MAX_JOBS} threads")
        print(f"{'='*70}\n")

    # Output setup
    out_dir = _cfg.OUTPUT_DIR / target
    out_dir.mkdir(parents=True, exist_ok=True)
    curves_dir = out_dir / "curves"
    curves_dir.mkdir(parents=True, exist_ok=True)

    # Train all specialists
    from joblib import Parallel, delayed

    def _train_one(idx):
        spec = candidates[idx]
        feats = groups_available[spec.feature_subset]
        X_sub = df_raw[feats].copy()
        result = train_single_model(spec, X_sub, y_series, seasons_series, task,
                                    curves_dir=curves_dir)
        return idx, result

    all_results_map = {}
    n_total = len(candidates)
    done = 0

    for idx, result in Parallel(
        n_jobs=_N_PARALLEL_MODELS,
        backend="loky",
        return_as="generator_unordered",
    )(delayed(_train_one)(i) for i in range(n_total)):
        all_results_map[idx] = result
        done += 1
        if verbose:
            spec = candidates[idx]
            if result.failed:
                print(f"  [{done}/{n_total}] {spec.uid()} FAILED: {result.error_msg[:60]}", flush=True)
            else:
                gap = result.overfit_gap
                flag = " ⚠️" if abs(gap) / max(abs(result.train_metric), 1e-7) > 0.05 else ""
                print(f"  [{done}/{n_total}] {spec.uid()} "
                      f"train={result.train_metric:.4f} val={result.metric:.4f} "
                      f"gap={gap:+.4f}{flag} [{result.train_time:.1f}s]", flush=True)

    all_results = [all_results_map[i] for i in range(n_total)]
    good_results = [r for r in all_results if not r.failed]
    good_results.sort(key=lambda r: r.metric)

    if verbose:
        print(f"\n  Successful: {len(good_results)}/{len(all_results)}")
        metric_name = "log_loss" if task == "classification" else "MAE"
        print(f"\n  Top 10 specialists by {metric_name}:")
        for r in good_results[:10]:
            print(f"    {r.uid:<50} val={r.metric:.4f}")

    if len(good_results) < 2:
        logger.error("Fewer than 2 specialists succeeded. Cannot ensemble.")
        return {"all_results": all_results, "good_results": good_results}

    # Diversity selection
    ensemble = select_diverse_ensemble(good_results)
    if verbose:
        print(f"\n  Diverse ensemble: {len(ensemble)} specialists selected")

    # --- Compare flat weights vs stacking ---
    weights_flat = optimize_weights(ensemble, y_series, task)

    # Flat metric
    common_mask = np.ones(len(y_series), dtype=bool)
    for r in ensemble:
        common_mask &= r.oof_mask & ~np.isnan(r.oof_preds)
    preds_flat = np.column_stack([r.oof_preds[common_mask] for r in ensemble]) @ weights_flat
    y_valid = y_series.values[common_mask]

    if task == "classification":
        preds_flat = np.clip(preds_flat, 1e-7, 1 - 1e-7)
        flat_metric = log_loss(y_valid, preds_flat)
    else:
        flat_metric = float(np.mean(np.abs(y_valid - preds_flat)))

    # Stacking
    meta_model, stacking_metric = run_stacking(ensemble, y_series, seasons_series, task)

    # Choose winner
    improvement = flat_metric - stacking_metric
    use_stacking = (meta_model is not None) and (improvement > STACKING_MIN_IMPROVEMENT)
    combination_method = "stacking" if use_stacking else "flat_weights"
    final_metric = stacking_metric if use_stacking else flat_metric

    if verbose:
        print(f"\n  Combination comparison:")
        print(f"    Flat weights:  {flat_metric:.6f}")
        print(f"    Stacking:      {stacking_metric:.6f}")
        print(f"    Improvement:   {improvement:.6f} (threshold: {STACKING_MIN_IMPROVEMENT})")
        print(f"    Winner:        {combination_method}")

    # Save stacking comparison
    comparison = {
        "flat_metric": float(flat_metric),
        "stacking_metric": float(stacking_metric),
        "improvement": float(improvement),
        "threshold": STACKING_MIN_IMPROVEMENT,
        "selected": combination_method,
    }
    with open(out_dir / "stacking_vs_flat.json", "w") as f:
        json.dump(comparison, f, indent=2)

    # --- Retrain and pickle final ensemble ---
    if verbose:
        print(f"\n  Retraining {len(ensemble)} specialists on full data...")

    trained_models = []
    all_specs_map = {s.name: s for s in _build_model_specs(task)}

    for i, (r, w) in enumerate(zip(ensemble, weights_flat)):
        spec = all_specs_map.get(r.model_name)
        if spec is None:
            continue

        feats = groups_available.get(r.feature_subset, [])
        if not feats:
            continue

        X_full = df_raw[feats].copy()
        impute_median = None
        scale_mean = None
        scale_std = None

        if spec.needs_imputation or spec.needs_scaling:
            impute_median = X_full.median()
            X_full = X_full.fillna(impute_median)
            if spec.needs_scaling:
                scale_mean = X_full.mean()
                scale_std = X_full.std().replace(0, 1)
                X_full = (X_full - scale_mean) / scale_std

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl = spec.build_fn()
            mdl.fit(X_full, y_series)

        trained_models.append({
            "uid": r.uid,
            "model_name": r.model_name,
            "model": mdl,
            "feature_group": r.feature_subset,
            "features": feats,
            "weight": float(w),
            "needs_scaling": spec.needs_scaling,
            "needs_imputation": spec.needs_imputation,
            "scale_mean": scale_mean.to_dict() if scale_mean is not None else None,
            "scale_std": scale_std.to_dict() if scale_std is not None else None,
            "impute_median": impute_median.to_dict() if impute_median is not None else None,
        })

        if verbose:
            print(f"    [{i+1}/{len(ensemble)}] {r.uid}")

    # Build final pkl
    pkl_data = {
        "target": target,
        "task": task,
        "combination_method": combination_method,
        "specialists": trained_models,
        "weights": weights_flat.tolist(),
        "meta_model": meta_model if use_stacking else None,
        "meta_features": [r.uid for r in ensemble],
        "training_seasons": sorted(seasons_series.unique().tolist()),
        "skip_seasons": list(SKIP_SEASONS),
        "metrics": {
            "final_metric": float(final_metric),
            "flat_metric": float(flat_metric),
            "stacking_metric": float(stacking_metric),
            "best_single_metric": float(good_results[0].metric),
        },
    }

    # Auto-calibration: derive all distributional parameters from OOF data
    from strategy.calibration import calibrate_bundle
    oof_stds = np.std(
        np.column_stack([r.oof_preds[common_mask] for r in ensemble]), axis=1
    ) if len(ensemble) > 1 else None
    pkl_data = calibrate_bundle(pkl_data, preds_flat, y_valid, oof_stds)
    if verbose:
        cal = pkl_data.get("calibration", {})
        if "residual_dist" in cal:
            rd = cal["residual_dist"]
            print(f"  Calibration: t(df={rd['df']:.2f}, scale={rd['scale']:.2f})")
        if "std_thresholds" in cal:
            print(f"  Std thresholds: {cal['std_thresholds']}")
        if "isotonic_calibrator" in cal:
            print(f"  Isotonic calibrator fitted")

    pkl_path = out_dir / "ensemble.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(pkl_data, f)

    if verbose:
        print(f"\n  Saved ensemble.pkl -> {pkl_path}")

    # Save config JSON (human-readable)
    config = {
        "target": target,
        "task": task,
        "combination_method": combination_method,
        "n_candidates": len(candidates),
        "n_successful": len(good_results),
        "n_ensemble": len(ensemble),
        "final_metric": float(final_metric),
        "best_single_metric": float(good_results[0].metric),
        "models": [
            {"uid": r.uid, "weight": float(w), "metric": float(r.metric),
             "family": r.family, "feature_group": r.feature_subset,
             "n_features": r.n_features}
            for r, w in zip(ensemble, weights_flat) if w > 0.001
        ],
    }
    with open(out_dir / "ensemble_config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Save leaderboard
    leaderboard = pd.DataFrame([
        {"uid": r.uid, "model_name": r.model_name, "family": r.family,
         "feature_group": r.feature_subset, "n_features": r.n_features,
         "train_metric": r.train_metric, "val_metric": r.metric,
         "overfit_gap": r.overfit_gap, "train_time": r.train_time}
        for r in good_results
    ])
    leaderboard.to_csv(out_dir / "leaderboard.csv", index=False)

    # Save OOF predictions
    oof_df = pd.DataFrame({"y_true": y_valid})
    for r in ensemble:
        oof_df[f"pred_{r.uid}"] = r.oof_preds[common_mask]
    oof_df["pred_ensemble"] = preds_flat
    oof_df["season"] = seasons_series.values[common_mask]
    oof_df["game_date"] = df_raw["game_date"].values[common_mask]
    # game_id/home/away captured live from the same in-memory df_raw this run's
    # oof_preds/common_mask were computed against — never re-joined from a
    # separately-loaded parquet later, which is what let nba_winner_oof.csv's
    # positional index go stale against a since-rebuilt game_features.parquet.
    oof_df["game_id"] = df_raw["game_id"].values[common_mask]
    oof_df["home_team_abbr"] = df_raw["home_team_abbr"].values[common_mask]
    oof_df["away_team_abbr"] = df_raw["away_team_abbr"].values[common_mask]
    oof_df.to_csv(out_dir / "ensemble_oof.csv", index=False)

    if verbose:
        print(f"\n  All outputs saved to: {out_dir}/")
        print(f"  Final {combination_method} metric: {final_metric:.6f}")

    return {
        "all_results": all_results,
        "good_results": good_results,
        "ensemble": ensemble,
        "weights": weights_flat,
        "combination_method": combination_method,
        "meta_model": meta_model if use_stacking else None,
        "final_metric": final_metric,
        "config": config,
    }


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    parser = argparse.ArgumentParser(description="NBA ensemble model training")
    parser.add_argument("--target", default="winner")
    parser.add_argument("--max-candidates", type=int, default=None,
                        help="Cap total candidates (for quick test runs)")
    parser.add_argument("--retrain-from-config", action="store_true",
                        help="Skip candidate search — retrain only the selected models "
                             "from the saved config JSON and pickle them.")
    parser.add_argument("--specialist", action="store_true",
                        help="Use feature-routed specialist ensemble (requires feature routing)")
    args = parser.parse_args()

    if args.retrain_from_config:
        retrain_from_config(args.target)
    elif args.specialist:
        run_specialist_ensemble(args.target)
    else:
        run_ensemble(args.target, max_candidates=args.max_candidates)
