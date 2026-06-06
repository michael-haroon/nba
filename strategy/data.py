"""
data.py
-------
Load game_features parquet and return aligned X, y, seasons for LOYO CV.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from strategy.config import (
    GAME_PARQUET, FEATURE_PATHS,
    get_feature_list_path,
    load_feature_list,
)


TARGET_MAP = {
    "winner": ("target_winner", "classification"),
    "home_score": ("target_home_score", "regression"),
    "away_score": ("target_away_score", "regression"),
    "spread": ("target_spread", "regression"),
    "total": ("target_total", "regression"),
    "h1_spread": ("target_h1_spread", "regression"),
    "h2_spread": ("target_h2_spread", "regression"),
    "h1_total": ("target_h1_total", "regression"),
    "h2_total": ("target_h2_total", "regression"),
    "home_wins_h1": ("target_home_wins_h1", "classification"),
    "home_wins_h2": ("target_home_wins_h2", "classification"),
    "overtime": ("target_overtime", "classification"),
    "series_winner": ("target_series_winner", "classification"),
    "series_total_games": ("target_series_total_games", "regression"),
    "series_spread": ("target_series_spread", "regression"),
    "series_exact": ("target_series_exact", "multiclass"),
}

MULTICLASS_TARGETS = {"series_exact"}


def load(target: str, model_name: str | None = None) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Load data for any supported target.

    Args:
        target      — key from TARGET_MAP (e.g. 'winner', 'spread', 'h1_spread')
        model_name  — optional model name to load a model-specific feature list

    Returns:
        X        — feature DataFrame, NaNs preserved (tree models handle them natively)
        y        — target Series
        seasons  — season string per row (for LOYO CV)
    """
    if target not in TARGET_MAP:
        raise ValueError(f"Unknown target '{target}'. Choose from: {list(TARGET_MAP.keys())}")

    target_col, task = TARGET_MAP[target]

    if model_name:
        feature_path = get_feature_list_path(target, model_name)
    else:
        feature_path = FEATURE_PATHS[target]

    df = pd.read_parquet(GAME_PARQUET)

    features = load_feature_list(feature_path)
    missing = [f for f in features if f not in df.columns]
    if missing:
        raise KeyError(f"{len(missing)} features in {feature_path.name} not found in parquet: {missing[:5]}")

    valid = df[target_col].notna()
    df = df[valid].reset_index(drop=True)

    X = df[features].copy()
    y = df[target_col].copy()
    seasons = df["season"].copy()

    if task == "regression":
        y = y.astype(float)
    elif task == "multiclass":
        y = y.astype(str)
    else:
        y = y.astype(int)

    return X, y, seasons


def load_by_group(target: str, group: str) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Load data using a feature-group-specific list (trees, linear, diversity, full).
    Uses the same mechanism as model-specific lists via get_feature_list_path().
    """
    return load(target, model_name=group)


def impute_with_train_median(X_train: pd.DataFrame, X_val: pd.DataFrame
                              ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Impute NaNs using training-fold medians only.
    Used exclusively for Ridge/LogReg which cannot handle NaN.
    Tree models should receive raw X without calling this.
    """
    medians = X_train.median()
    return X_train.fillna(medians), X_val.fillna(medians)
