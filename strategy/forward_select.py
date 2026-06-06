"""
forward_select.py
-----------------
LOYO-based forward selection of complementary features for tree models.

Starts with the ACCEPTED feature set, then greedily adds COMPLEMENTARY features
(sorted by residual-MDA) one at a time. Each candidate is validated with a full
Leave-One-Year-Out CV loop. Features are kept if they improve the validation
metric beyond a significance threshold.

Results are cached: if feature_list_trees.txt is newer than feature_report.csv,
forward selection is skipped entirely.

Usage:
    python -m strategy.forward_select --target winner
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_absolute_error

from strategy.config import (
    FEATURES_ROOT, GAME_PARQUET, SKIP_SEASONS,
    LOYO_MIN_TRAIN_SEASONS, LGBM_CLF_PARAMS, LGBM_REG_PARAMS, OUTPUT_DIR,
)
from strategy.data import TARGET_MAP

logger = logging.getLogger(__name__)

CLF_IMPROVEMENT_THRESHOLD = 0.0003
REG_IMPROVEMENT_THRESHOLD = 0.05
PATIENCE = 5


def _is_cached(target: str) -> bool:
    """
    Check if forward selection results are cached and fresh.
    Uses forward_selection_log.csv as the marker — this file is ONLY written
    by forward_select, never by Phase 0 routing. Prevents false cache hits.
    """
    marker_path = FEATURES_ROOT / target / "filtered" / "forward_selection_log.csv"
    report_path = FEATURES_ROOT / target / "filtered" / "feature_report.csv"

    if not marker_path.exists() or not report_path.exists():
        return False

    return marker_path.stat().st_mtime > report_path.stat().st_mtime


def _loyo_evaluate(X: pd.DataFrame, y: pd.Series, seasons: pd.Series,
                   task: str, feature_cols: list[str]) -> float:
    """
    Run LOYO CV with LGBM on the given feature subset. Returns mean val metric.
    Classification: log_loss (lower is better)
    Regression: MAE (lower is better)
    """
    import lightgbm as lgb

    unique_seasons = sorted(seasons.unique())
    val_scores = []

    params = dict(LGBM_CLF_PARAMS if task == "classification" else LGBM_REG_PARAMS)
    params["n_jobs"] = min(os.cpu_count() or 4, 8)

    for test_season in unique_seasons:
        if test_season in SKIP_SEASONS:
            continue

        train_mask = (seasons != test_season) & (~seasons.isin(SKIP_SEASONS))
        test_mask = seasons == test_season

        n_train_seasons = seasons[train_mask].nunique()
        if n_train_seasons < LOYO_MIN_TRAIN_SEASONS:
            continue

        X_train = X.loc[train_mask, feature_cols]
        X_test = X.loc[test_mask, feature_cols]
        y_train = y[train_mask]
        y_test = y[test_mask]

        if task == "classification":
            model = lgb.LGBMClassifier(**params)
            model.fit(X_train, y_train)
            preds = model.predict_proba(X_test)[:, 1]
            score = log_loss(y_test, preds)
        else:
            model = lgb.LGBMRegressor(**params)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            score = mean_absolute_error(y_test, preds)

        val_scores.append(score)

    return float(np.mean(val_scores)) if val_scores else float("inf")


def run_forward_selection(target: str, force: bool = False) -> list[str]:
    """
    Run greedy forward selection of complementary features for a target.
    Returns the final validated feature list for tree models.
    """
    if not force and _is_cached(target):
        trees_path = FEATURES_ROOT / target / "filtered" / "feature_list_trees.txt"
        features = trees_path.read_text().strip().splitlines()
        logger.info("Forward selection cached for '%s' (%d features)", target, len(features))
        return features

    report_path = FEATURES_ROOT / target / "filtered" / "feature_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"No feature_report.csv for target '{target}'")

    df = pd.read_csv(report_path)
    target_col, task = TARGET_MAP[target]

    # Get accepted + complementary features
    accepted = df[df["tier"] == "ACCEPTED"]["feature"].tolist()

    # Complementary: MDI+PCA+RESID pass, SFI fails
    complementary = df[
        (df["mdi_passes"] == True) &
        (df["sfi_passes"] == False) &
        (df["pca_mda_passes"] == True) &
        (df["resid_mda_passes"] == True)
    ].sort_values("resid_mda_mean", ascending=False)["feature"].tolist()

    if not complementary:
        logger.info("No complementary features for '%s', using accepted only", target)
        return accepted

    threshold = CLF_IMPROVEMENT_THRESHOLD if task == "classification" else REG_IMPROVEMENT_THRESHOLD

    # Load full dataset
    logger.info("Loading data for forward selection (target=%s)...", target)
    game_df = pd.read_parquet(GAME_PARQUET)
    valid = game_df[target_col].notna()
    game_df = game_df[valid].reset_index(drop=True)

    all_candidate_features = accepted + complementary
    missing = [f for f in all_candidate_features if f not in game_df.columns]
    if missing:
        logger.warning("Dropping %d features not in parquet: %s", len(missing), missing[:5])
        complementary = [f for f in complementary if f not in missing]
        accepted = [f for f in accepted if f not in missing]

    X = game_df[accepted + complementary]
    y = game_df[target_col].astype(int if task == "classification" else float)
    seasons = game_df["season"]

    # Baseline: accepted only
    logger.info("Computing baseline with %d accepted features...", len(accepted))
    t0 = time.time()
    baseline = _loyo_evaluate(X, y, seasons, task, accepted)
    logger.info("  Baseline %s: %.6f (%.1fs)", "log_loss" if task == "classification" else "MAE",
                baseline, time.time() - t0)

    # Forward selection
    current_features = list(accepted)
    best_score = baseline
    no_improvement_count = 0
    selection_log = []

    logger.info("Starting forward selection: %d candidates, threshold=%.4f, patience=%d",
                len(complementary), threshold, PATIENCE)

    for i, candidate in enumerate(complementary):
        trial_features = current_features + [candidate]

        t0 = time.time()
        score = _loyo_evaluate(X, y, seasons, task, trial_features)
        elapsed = time.time() - t0

        delta = best_score - score  # positive = improvement (lower is better for both metrics)
        kept = delta > threshold

        if kept:
            current_features.append(candidate)
            best_score = score
            no_improvement_count = 0
            status = "KEEP"
        else:
            no_improvement_count += 1
            status = "SKIP"

        selection_log.append({
            "step": i + 1,
            "feature": candidate,
            "score": score,
            "delta": delta,
            "kept": kept,
            "n_features": len(current_features),
        })

        if (i + 1) % 10 == 0 or kept:
            logger.info("  [%3d/%d] %s %s  score=%.6f  delta=%.6f  (%.1fs)",
                        i + 1, len(complementary), status, candidate[:40],
                        score, delta, elapsed)

        if no_improvement_count >= PATIENCE:
            logger.info("  Stopping: %d consecutive non-improvements", PATIENCE)
            break

    logger.info("Forward selection complete: %d/%d candidates kept, final %s=%.6f",
                len(current_features) - len(accepted), len(complementary),
                "log_loss" if task == "classification" else "MAE", best_score)

    # Write results
    trees_path = FEATURES_ROOT / target / "filtered" / "feature_list_trees.txt"
    trees_path.write_text("\n".join(current_features) + "\n")

    log_path = FEATURES_ROOT / target / "filtered" / "forward_selection_log.csv"
    pd.DataFrame(selection_log).to_csv(log_path, index=False)

    # Save to strategy output too
    out_dir = OUTPUT_DIR / target
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(selection_log).to_csv(out_dir / "forward_selection_log.csv", index=False)

    return current_features


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Forward selection for complementary features")
    parser.add_argument("--target", required=True, help="Target name (e.g., winner, spread)")
    parser.add_argument("--force", action="store_true", help="Force re-run even if cached")
    args = parser.parse_args()

    features = run_forward_selection(args.target, force=args.force)
    print(f"\nFinal tree feature set: {len(features)} features")
