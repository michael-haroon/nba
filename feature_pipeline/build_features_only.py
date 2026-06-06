"""
Build game_features.parquet without running the full analysis pipeline (MDI/MDA/SFI).

Usage:
    python -m feature_pipeline.build_features_only [--output-dir output/features/winner]
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from feature_pipeline.logging_config import setup_pipeline_logger

from feature_pipeline.engineering.data_loader import load_all
from feature_pipeline.engineering.game_builder import build_game_rows, attach_quarter_scores, build_targets, build_series_targets
from feature_pipeline.engineering.feature_engineering import (
    align_ratings_to_games,
    align_massey_to_games,
    compute_rolling_features,
    compute_score_momentum,
    compute_context_features,
    compute_travel_sequence_features,
    compute_referee_features,
    compute_roster_features,
    compute_deprado_features,
    compute_diffs,
    compute_sums,
    compute_pythagorean_features,
    compute_log5_features,
    compute_four_factors_composite,
    compute_pace_mismatch,
    compute_scoring_entropy,
    compute_acwr_features,
    compute_directional_travel,
    compute_blowout_close_features,
    compute_overtime_history,
    compute_margin_autocorrelation,
    compute_defensive_consistency,
    compute_scoring_concentration,
    compute_series_features,
    compute_hustle_features,
    compute_half_scoring_rate,
    generate_symbolic_features,
    handle_missing,
)


def main(output_dir: str = "output/features/winner", data_dir: str | None = None) -> None:
    log_dir = Path(__file__).resolve().parent / "logs"
    setup_pipeline_logger(log_dir)
    logger = logging.getLogger("feature_pipeline")

    t_start = time.time()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    logger.info("=== build_features_only: start ===")
    print("Loading data...")
    data = load_all(data_dir)

    print("Building game rows...")
    games = build_game_rows(data["box_scores"], data["game_ids"], data["team_map"])
    games = attach_quarter_scores(games, data["quarter_scores"], data["team_map"])
    games = build_targets(games)
    games = build_series_targets(games)
    print(f"  {len(games)} games")
    logger.info("[build] %d games  %d cols", len(games), games.shape[1])

    massey_df = data.get("massey", pd.DataFrame())

    def _align_massey(g):
        if not massey_df.empty:
            g = align_massey_to_games(g, massey_df)
        else:
            print("  WARNING: MasseyRatings.parquet not found")
        return g

    def _quarter_h1h2(g):
        for side in ("home", "away"):
            q1, q2, q3, q4 = (f"{side}_roll10_q{i}" for i in range(1, 5))
            if all(c in g.columns for c in [q1, q2, q3, q4]):
                g[f"{side}_roll10_h1_pts"] = g[q1] + g[q2]
                g[f"{side}_roll10_h2_pts"] = g[q3] + g[q4]
        return g

    def _crowd_pressure(g):
        if "crowd_density" in g.columns and "away_travel_distance" in g.columns:
            g["hostile_crowd_pressure"] = g["crowd_density"] * (g["away_travel_distance"] > 0).astype(float)
            g["crowd_home_lift"] = g["crowd_density"].fillna(0)
        return g

    steps = [
        ("align_ratings",          lambda g: align_ratings_to_games(g, data["bpi"], data["sagarin"], data["team_map"])),
        ("rolling_features",       lambda g: compute_rolling_features(g, windows=[5, 10, 20])),
        ("score_momentum",         lambda g: compute_score_momentum(g)),
        ("context_features",       lambda g: compute_context_features(g, data["arenas"], data.get("game_summaries"))),
        ("travel_sequence",        lambda g: compute_travel_sequence_features(g, data["arenas"])),
        ("referee_features",       lambda g: compute_referee_features(g, data["officials"])),
        ("roster_features",        lambda g: compute_roster_features(g, data["player_box_scores"])),
        ("deprado_features",       lambda g: compute_deprado_features(g)),
        ("massey_align",           _align_massey),
        ("crowd_pressure",         _crowd_pressure),
        ("pythagorean",            lambda g: compute_pythagorean_features(g)),
        ("four_factors",           lambda g: compute_four_factors_composite(g)),
        ("pace_mismatch",          lambda g: compute_pace_mismatch(g)),
        ("scoring_entropy",        lambda g: compute_scoring_entropy(g)),
        ("acwr",                   lambda g: compute_acwr_features(g)),
        ("directional_travel",     lambda g: compute_directional_travel(g, data["arenas"], data["team_map"])),
        ("quarter_h1h2",           _quarter_h1h2),
        ("blowout_close",          lambda g: compute_blowout_close_features(g)),
        ("overtime_history",       lambda g: compute_overtime_history(g, data["quarter_scores"])),
        ("margin_autocorr",        lambda g: compute_margin_autocorrelation(g)),
        ("def_consistency",        lambda g: compute_defensive_consistency(g)),
        ("scoring_concentration",  lambda g: compute_scoring_concentration(g)),
        ("series_features",        lambda g: compute_series_features(g)),
        ("hustle_features",        lambda g: compute_hustle_features(g, data.get("hustle"))),
        ("diffs",                  lambda g: compute_diffs(g)),
        ("sums",                   lambda g: compute_sums(g)),
        ("log5",                   lambda g: compute_log5_features(g)),
        ("half_scoring_rate",      lambda g: compute_half_scoring_rate(g)),
    ]

    print("Engineering features...")
    for name, fn in tqdm(steps, desc="feature steps", unit="step"):
        _t = time.time()
        _cols_before = games.shape[1]
        games = fn(games)
        elapsed = time.time() - _t
        logger.info("[step] %-25s +%d cols  %.1fs", name, games.shape[1] - _cols_before, elapsed)

    print("  Generating symbolic features (500)...")
    _t = time.time()
    games, recipes = generate_symbolic_features(games)
    logger.info("[step] %-25s +%d cols  %.1fs", "symbolic_features", len([c for c in games.columns if c.startswith("sf_")]), time.time() - _t)

    import json
    recipes_path = output / "symbolic_recipes.json"
    with open(recipes_path, "w") as f:
        json.dump(recipes, f, indent=2)
    print(f"  Saved {len(recipes)} recipes → {recipes_path}")

    out_path = output / "game_features.parquet"
    games.to_parquet(out_path, index=False)
    total_elapsed = time.time() - t_start
    logger.info("=== build_features_only: done  games=%d  cols=%d  elapsed=%.1fs ===",
                len(games), games.shape[1], total_elapsed)
    print(f"Saved {len(games)} rows → {out_path}  ({total_elapsed:.1f}s)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", default="output/features/winner")
    p.add_argument("--data-dir", default=None)
    args = p.parse_args()
    main(output_dir=args.output_dir, data_dir=args.data_dir)
