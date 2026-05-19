"""
NBA Feature Pipeline Orchestrator.

Loads data -> builds game-level dataset -> engineers features -> runs de Prado
feature importance analysis (MDI/MDA/SFI with PCA cross-check).

Usage:
    python -m feature_pipeline.analysis.run [--output-dir output/]
    python -m feature_pipeline.analysis.run --target target_spread
    python -m feature_pipeline.analysis.run --skip-massey  # faster iteration
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from feature_pipeline.engineering.data_loader import load_all
from feature_pipeline.engineering.game_builder import (
    build_game_rows, build_targets, build_series_targets,
)
from feature_pipeline.engineering.feature_engineering import (
    align_ratings_to_games,
    compute_rolling_features,
    compute_score_momentum,
    compute_context_features,
    compute_referee_features,
    compute_roster_features,
    compute_deprado_features,
    compute_diffs,
    generate_random_combinations,
    handle_missing,
    time_decay_weights,
)
from feature_pipeline.analysis.feature_importance import run_all_importance, synthetic_validation


def _elapsed(t0: float) -> str:
    elapsed = time.time() - t0
    if elapsed < 60:
        return f"{elapsed:.1f}s"
    elif elapsed < 3600:
        return f"{elapsed/60:.1f}m"
    return f"{elapsed/3600:.1f}h"


def main(output_dir: str = "output/features",
         target: str = "target_winner",
         skip_massey: bool = False,
         skip_random: bool = False,
         data_dir: str | None = None):

    pipeline_start = time.time()

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # ── Banner ───────────────────────────────────────────────────────────────
    from feature_pipeline.compute import get_n_jobs, get_n_random_combos
    print("=" * 60)
    print(f"  CPU cores: {os.cpu_count()}, n_jobs: {get_n_jobs()}")
    print(f"  Random combos: {get_n_random_combos()}")
    print(f"  Instance: {os.uname().nodename} ({os.uname().machine})")
    print(f"  Target: {target}")
    print("=" * 60)
    print()

    # ── Step 1: Load all data ────────────────────────────────────────────────
    t0 = time.time()
    print("Step 1: Loading data...")
    data = load_all(data_dir)
    print(f"  Box scores: {data['box_scores'].shape}")
    print(f"  BPI: {data['bpi'].shape}, Sagarin: {data['sagarin'].shape}")
    print(f"  [{_elapsed(t0)}]")

    # ── Step 2: Build game-level dataset ─────────────────────────────────────
    t0 = time.time()
    print("\nStep 2: Building game-level dataset...")
    games = build_game_rows(data["box_scores"], data["game_ids"], data["team_map"])
    games = build_targets(games)
    games = build_series_targets(games)
    print(f"  Games: {games.shape[0]}, Columns: {games.shape[1]}")
    if target in games.columns:
        print(f"  Target '{target}' balance: {games[target].mean():.3f}")
    print(f"  [{_elapsed(t0)}]")

    # ── Step 3: Feature engineering ──────────────────────────────────────────
    t0 = time.time()
    print("\nStep 3: Engineering features...")

    print("  Aligning ratings to games (temporal safety)...")
    games = align_ratings_to_games(games, data["bpi"], data["sagarin"], data["team_map"])

    print("  Computing rolling features (windows: 5, 10, 20)...")
    games = compute_rolling_features(games, windows=[5, 10, 20])

    print("  Computing score momentum...")
    games = compute_score_momentum(games)

    print("  Computing context & travel features...")
    games = compute_context_features(games, data["arenas"], data.get("game_summaries"))

    print("  Computing referee features...")
    games = compute_referee_features(games, data["officials"])

    print("  Computing roster features...")
    games = compute_roster_features(games, data["player_box_scores"])

    print("  Computing de Prado features (entropy, CUSUM)...")
    games = compute_deprado_features(games)

    if not skip_massey:
        print("  Fitting Massey ratings (pregame, no lookahead)...")
        try:
            from feature_pipeline.engineering.massey_ratings import (
                build_pregame_massey_game_features,
                prepare_massey_context,
            )
            massey_input = games[["game_date", "home_team_id", "away_team_id",
                                  "home_pts", "away_pts", "season_type"]].copy()
            massey_input = massey_input.rename(columns={
                "home_pts": "home_score",
                "away_pts": "away_score",
            })
            massey_input["season"] = games["season"]
            massey_input["game_id"] = range(len(massey_input))

            if "away_travel_distance" in games.columns:
                massey_input["travel_distance"] = games["away_travel_distance"]
            if "crowd_density" in games.columns:
                massey_input["crowd_density"] = games["crowd_density"]

            massey_input = prepare_massey_context(massey_input)
            massey_features = build_pregame_massey_game_features(massey_input)
            massey_cols = [c for c in massey_features.columns if "massey" in c.lower()]
            for col in massey_cols:
                games[col] = massey_features[col].values
            print(f"    Added {len(massey_cols)} Massey feature columns")
        except Exception as e:
            warnings.warn(f"  Massey fitting failed: {e}")
    else:
        print("  Skipped Massey (--skip-massey)")

    print("  Computing differential features (home - away)...")
    games = compute_diffs(games)

    if not skip_random:
        print("  Generating random weighted combinations...")
        games = generate_random_combinations(games)
        rc_cols = [c for c in games.columns if c.startswith("rc_")]
        print(f"    Generated {len(rc_cols)} random combination features")
    else:
        print("  Skipped random combinations (--skip-random)")

    print(f"  Feature engineering complete. Shape: {games.shape}")
    print(f"  [{_elapsed(t0)}]")

    # Save intermediate dataset
    games.to_parquet(output / "game_features.parquet", index=False)
    print(f"  Saved to {output / 'game_features.parquet'}")

    # ── Step 4: De Prado feature importance analysis ─────────────────────────
    t0 = time.time()
    print("\nStep 4: De Prado feature importance analysis...")

    synth = synthetic_validation()
    print(f"  Synthetic MDI validation: {'PASS' if synth['mdi_pass'] else 'FAIL'}")

    # Build X, y
    skip_cols = {
        "game_date", "season", "season_type", "game_id",
        "home_team_id", "away_team_id", "home_team_abbr", "away_team_abbr",
        "home_team_name", "away_team_name", "home_wl", "away_wl",
        "home_min_trad", "away_min_trad", "sample_weight",
    }
    skip_cols.update(c for c in games.columns if c.startswith("target_"))
    skip_cols.update(c for c in games.columns if c.startswith("home_") or c.startswith("away_"))

    feat_cols = [c for c in games.columns
                 if c not in skip_cols and games[c].dtype.kind in "fi"]

    X = games[feat_cols].copy()
    y = games[target].copy()

    valid_mask = y.notna()
    X = X[valid_mask]
    y = y[valid_mask].astype(int) if target == "target_winner" else y[valid_mask]
    seasons = games.loc[valid_mask, "season"]

    X = X.fillna(X.median())

    print(f"  Features: {X.shape[1]}, Samples: {X.shape[0]}")
    print(f"  Target: {target}")

    sample_weight = time_decay_weights(games.loc[valid_mask, "game_date"], c=0.3)

    importance_results = run_all_importance(X, y, seasons, run_sfi=True)
    print(f"  [{_elapsed(t0)}]")

    # ── Step 5: Save results ─────────────────────────────────────────────────
    t0 = time.time()
    print("\nStep 5: Saving results...")

    importance_results["summary"].to_csv(output / "feature_importance_catalog.csv")
    importance_results["mdi"].to_csv(output / "importance_mdi.csv")
    importance_results["mda"].to_csv(output / "importance_mda.csv")
    if importance_results.get("sfi") is not None:
        importance_results["sfi"].to_csv(output / "importance_sfi.csv")

    importance_results["mdi_raw"].to_csv(output / "importance_mdi_raw.csv")
    importance_results["mda_raw"].to_csv(output / "importance_mda_raw.csv")

    filtered_dir = output / "filtered"
    filtered_dir.mkdir(exist_ok=True)
    importance_results["filter_report"].to_csv(filtered_dir / "feature_report.csv")
    survivors = importance_results["survivors"]
    with open(filtered_dir / "feature_list.txt", "w") as f:
        f.write("\n".join(survivors))
    print(f"  {len(survivors)} surviving features -> {filtered_dir}/feature_list.txt")

    importance_results["pca_info"].to_csv(output / "pca_cross_check.csv")
    with open(output / "kendall_tau.json", "w") as f:
        json.dump(importance_results["tau_results"], f, indent=2)

    print(f"\nTop 15 features by SFI mean:")
    sfi = importance_results.get("sfi")
    if sfi is not None:
        top = sfi.nlargest(15, "mean")
        for feat, row in top.iterrows():
            print(f"  {feat:<42} SFI={row['mean']:.4f}")

    print(f"  [{_elapsed(t0)}]")

    # ── Done ─────────────────────────────────────────────────────────────────
    total = _elapsed(pipeline_start)
    print(f"\n{'=' * 60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Total wall time: {total}")
    print(f"  Output: {output}/")
    print(f"  Survivors: {len(survivors)} features")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA feature pipeline")
    parser.add_argument("--output-dir", default="output/features")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--target", default="target_winner",
                        choices=["target_winner", "target_spread", "target_total",
                                 "target_h1_spread", "target_h2_spread", "target_overtime",
                                 "target_series_winner"])
    parser.add_argument("--skip-massey", action="store_true")
    parser.add_argument("--skip-random", action="store_true")
    args = parser.parse_args()
    main(args.output_dir, args.target, args.skip_massey, args.skip_random, args.data_dir)
