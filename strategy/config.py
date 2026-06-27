"""
config.py
---------
Strategy configuration for NBA winner and spread models.
"""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURES_ROOT = PROJECT_ROOT / "output" / "features"

# One shared parquet (all features + all targets) saved by feature pipeline
# Feature lists are target-specific (each target has its own importance results)
GAME_PARQUET = FEATURES_ROOT / "game_features.parquet"

WINNER_PARQUET = GAME_PARQUET
WINNER_FEATURES = FEATURES_ROOT / "winner" / "filtered" / "feature_list.txt"

SPREAD_PARQUET = GAME_PARQUET
SPREAD_FEATURES = FEATURES_ROOT / "spread" / "filtered" / "feature_list.txt"

FEATURE_PATHS = {
    "winner": FEATURES_ROOT / "winner" / "filtered" / "feature_list.txt",
    "home_score": FEATURES_ROOT / "home_score" / "filtered" / "feature_list.txt",
    "away_score": FEATURES_ROOT / "away_score" / "filtered" / "feature_list.txt",
    "spread": FEATURES_ROOT / "spread" / "filtered" / "feature_list.txt",
    "total": FEATURES_ROOT / "total" / "filtered" / "feature_list.txt",
    "h1_spread": FEATURES_ROOT / "h1_spread" / "filtered" / "feature_list.txt",
    "h2_spread": FEATURES_ROOT / "h2_spread" / "filtered" / "feature_list.txt",
    "h1_total": FEATURES_ROOT / "h1_total" / "filtered" / "feature_list.txt",
    "h2_total": FEATURES_ROOT / "h2_total" / "filtered" / "feature_list.txt",
    "home_wins_h1": FEATURES_ROOT / "home_wins_h1" / "filtered" / "feature_list.txt",
    "home_wins_h2": FEATURES_ROOT / "home_wins_h2" / "filtered" / "feature_list.txt",
    "overtime": FEATURES_ROOT / "overtime" / "filtered" / "feature_list.txt",
    "series_winner": FEATURES_ROOT / "series_winner" / "filtered" / "feature_list.txt",
    "series_total_games": FEATURES_ROOT / "series_total_games" / "filtered" / "feature_list.txt",
    "series_spread": FEATURES_ROOT / "series_spread" / "filtered" / "feature_list.txt",
    "series_exact": FEATURES_ROOT / "series_exact" / "filtered" / "feature_list.txt",
}


def get_feature_list_path(target: str, model_name: str) -> Path:
    """
    Resolve per-model feature list with fallback to shared list.
    Looks for: output/features/{target}/filtered/feature_list_{model}.txt
    Falls back to: output/features/{target}/filtered/feature_list.txt
    """
    base = FEATURES_ROOT / target / "filtered"
    model_specific = base / f"feature_list_{model_name}.txt"
    if model_specific.exists():
        return model_specific
    return base / "feature_list.txt"

OUTPUT_DIR = PROJECT_ROOT / "strategy" / "output" / "nba"

# ── CV settings ──────────────────────────────────────────────────────────────
SKIP_SEASONS = {"2019-20"}   # COVID bubble
LOYO_MIN_TRAIN_SEASONS = 3   # need at least this many seasons to train

# ── Huber delta ──────────────────────────────────────────────────────────────
# NBA spread IQR ≈ 19 pts; delta=10 keeps Huber quadratic for most games
# and linear for blowouts
HUBER_DELTA = 10.0

# Adaptive delta: nested inner-loop CV selects from MAD-scaled grid per target.
# Multipliers on sigma_hat = MAD / 0.6745 (robust scale estimate).
HUBER_DELTA_MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5]

# ── Model hyperparams ────────────────────────────────────────────────────────
LGBM_CLF_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "n_estimators": 600,
    "learning_rate": 0.03,
    "max_depth": 4,
    "num_leaves": 15,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": 42,
    "verbosity": -1,
    "n_jobs": -1,
}

LGBM_REG_PARAMS = {
    "objective": "huber",
    "alpha": HUBER_DELTA,
    "metric": "huber",
    "n_estimators": 600,
    "learning_rate": 0.03,
    "max_depth": 4,
    "num_leaves": 15,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": 42,
    "verbosity": -1,
    "n_jobs": -1,
}

XGB_CLF_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "n_estimators": 600,
    "learning_rate": 0.03,
    "max_depth": 4,
    "min_child_weight": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": 42,
    "verbosity": 0,
    "nthread": -1,
}

XGB_REG_PARAMS = {
    "objective": "reg:pseudohubererror",
    "eval_metric": "mae",
    "n_estimators": 600,
    "learning_rate": 0.03,
    "max_depth": 4,
    "min_child_weight": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": 42,
    "verbosity": 0,
    "nthread": -1,
}

LOGREG_PARAMS = {
    "C": 0.1,
    "penalty": "l2",
    "solver": "lbfgs",
    "max_iter": 1000,
    "random_state": 42,
}

RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0]

# CatBoost params set at build time (GPU auto-detect in models.py)
CATBOOST_CLF_PARAMS = {
    "iterations": 600,
    "learning_rate": 0.03,
    "depth": 4,
    "loss_function": "Logloss",
    "eval_metric": "Logloss",
    "random_seed": 42,
    "verbose": 0,
}

CATBOOST_REG_PARAMS = {
    "iterations": 600,
    "learning_rate": 0.03,
    "depth": 4,
    "loss_function": f"Huber:delta={HUBER_DELTA}",
    "eval_metric": "MAE",
    "random_seed": 42,
    "verbose": 0,
}


# ── Multiclass params (for target_series_exact: 4-0, 4-1, 4-2, 4-3) ────────
LGBM_MULTI_PARAMS = {
    **{k: v for k, v in LGBM_CLF_PARAMS.items() if k not in ("objective", "metric")},
    "objective": "multiclass",
    "metric": "multi_logloss",
    "num_class": 4,
}

XGB_MULTI_PARAMS = {
    **{k: v for k, v in XGB_CLF_PARAMS.items() if k not in ("objective", "eval_metric")},
    "objective": "multi:softprob",
    "eval_metric": "mlogloss",
    "num_class": 4,
}

CATBOOST_MULTI_PARAMS = {
    **{k: v for k, v in CATBOOST_CLF_PARAMS.items() if k not in ("loss_function", "eval_metric")},
    "loss_function": "MultiClass",
    "eval_metric": "MultiClass",
}

LOGREG_MULTI_PARAMS = {
    **LOGREG_PARAMS,
    "multi_class": "multinomial",
}


# ── Feature routing & forward selection ──────────────────────────────────────
FORWARD_SELECT_CLF_THRESHOLD = 0.0003   # log-loss improvement to keep a feature
FORWARD_SELECT_REG_THRESHOLD = 0.05     # MAE improvement to keep a feature
FORWARD_SELECT_PATIENCE = 5             # stop after N consecutive non-improvements

# Stacking: meta-learner must beat flat weights by this much to be selected
STACKING_MIN_IMPROVEMENT = 0.002

# Specialist routing: maps feature groups to model families
SPECIALIST_ROUTING = {
    "trees": {
        "feature_group": "trees",
        "models": ["lgbm", "xgb", "catboost", "rf", "extratrees", "hgb"],
    },
    "linear": {
        "feature_group": "linear",
        "models": ["logreg", "ridge", "lda", "sgd", "elasticnet"],
    },
    "deep": {
        "feature_group": "full",
        "models": ["mlp"],
    },
    "diversity": {
        "feature_group": "diversity",
        "models": ["logreg", "knn", "gnb", "lda"],
    },
    "strict": {
        "feature_group": "accepted",
        "models": ["knn", "gnb", "qda"],
    },
}

# ── Risk management ──────────────────────────────────────────────────────────
KELLY_FRACTION = 0.25           # Quarter-Kelly baseline
MIN_EDGE_PCT = 3.0              # Minimum edge % to recommend a bet
MAX_POSITION_PCT = 5.0          # Max single bet as % of bankroll
MAX_DAILY_EXPOSURE_PCT = 20.0   # Max total daily exposure as % of bankroll
SIGMA_SPREAD = 12.44            # Measured OOF spread error std (homoscedastic) — kept for reference
# t-distribution fit to OOF residuals (MLE, floc=0): KS p=0.30 vs normal KS p=4.9e-6
SPREAD_RESID_DF = 15.71         # t degrees of freedom
SPREAD_RESID_SCALE = 11.62      # t scale parameter (≈ std for large df, but not identical)

# Total model: t-dist fit to OOF residuals (MLE, floc=0): KS p=0.10 vs normal KS p=0.07
TOTAL_RESID_DF = 26.61          # t degrees of freedom (heavier tails than spread)
TOTAL_RESID_SCALE = 16.22       # t scale parameter

# Winner model: ensemble disagreement IS useful for confidence scaling
# Thresholds from calibration: low std → high accuracy (70.6% vs 62.7%)
WINNER_STD_THRESHOLDS = (0.028, 0.038)  # tercile boundaries from OOF data
WINNER_CONFIDENCE_MULTIPLIERS = {
    "HIGH": 1.0,    # ensemble_std in lowest third
    "MEDIUM": 0.75,
    "LOW": 0.5,
}

# FLB agreement multipliers (applied on top of Kelly)
FLB_AGREE_MULT = 1.5
FLB_DISAGREE_MULT = 0.5
FLB_NEUTRAL_MULT = 1.0


def load_feature_list(path: Path) -> list[str]:
    return path.read_text().strip().splitlines()
