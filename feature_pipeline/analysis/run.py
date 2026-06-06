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

import feature_pipeline.compute  # noqa: F401 — BLAS thread config (must precede numpy)

import argparse
import json
import logging
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from feature_pipeline.logging_config import setup_pipeline_logger

from feature_pipeline.engineering.data_loader import load_all
from feature_pipeline.engineering.game_builder import (
    build_game_rows, attach_quarter_scores, build_targets, build_series_targets,
)
from feature_pipeline.engineering.feature_engineering import (
    align_ratings_to_games,
    align_massey_to_games,
    compute_rolling_features,
    compute_venue_rolling_features,
    compute_score_momentum,
    compute_context_features,
    compute_travel_sequence_features,
    compute_referee_features,
    compute_roster_features,
    compute_h2h_features,
    compute_conditional_matchup_stats,
    compute_matchup_advantage,
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
    time_decay_weights,
)
from feature_pipeline.analysis.feature_importance import (
    run_all_importance, synthetic_validation, plot_cfi_mda_distributions,
)


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
         with_desub: bool = False,
         data_dir: str | None = None):

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    setup_pipeline_logger(log_dir)
    logger = logging.getLogger("feature_pipeline")

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
    logger.info("=== STEP 1: Loading data ===")
    print("Step 1: Loading data...")
    data = load_all(data_dir)
    print(f"  Box scores: {data['box_scores'].shape}")
    print(f"  BPI: {data['bpi'].shape}, Sagarin: {data['sagarin'].shape}")
    logger.info("[step1] elapsed: %s", _elapsed(t0))
    print(f"  [{_elapsed(t0)}]")

    # ── Step 2: Build game-level dataset ─────────────────────────────────────
    t0 = time.time()
    logger.info("=== STEP 2: Build game dataset ===")
    print("\nStep 2: Building game-level dataset...")
    games = build_game_rows(data["box_scores"], data["game_ids"], data["team_map"])
    games = attach_quarter_scores(games, data["quarter_scores"], data["team_map"])
    games = build_targets(games)
    games = build_series_targets(games)
    print(f"  Games: {games.shape[0]}, Columns: {games.shape[1]}")
    if target in games.columns:
        print(f"  Target '{target}' balance: {games[target].mean():.3f}")
    logger.info("[step2] games=%d cols=%d target='%s' balance=%.3f elapsed=%s",
                games.shape[0], games.shape[1], target,
                games[target].mean() if target in games.columns else float("nan"),
                _elapsed(t0))
    print(f"  [{_elapsed(t0)}]")

    # ── Step 3: Feature engineering ──────────────────────────────────────────
    t0 = time.time()
    logger.info("=== STEP 3: Feature engineering ===")
    print("\nStep 3: Engineering features...")

    print("  Aligning ratings to games (temporal safety)...")
    games = align_ratings_to_games(games, data["bpi"], data["sagarin"], data["team_map"])

    print("  Computing rolling features (windows: 5, 10, 20)...")
    games = compute_rolling_features(games, windows=[5, 10, 20])

    print("  Computing venue-conditioned rolling features (home/road splits)...")
    games = compute_venue_rolling_features(games)

    print("  Computing score momentum...")
    games = compute_score_momentum(games)

    print("  Computing context & travel features...")
    games = compute_context_features(games, data["arenas"], data.get("game_summaries"))

    print("  Computing travel sequence & fatigue features...")
    games = compute_travel_sequence_features(games, data["arenas"])

    print("  Computing referee features...")
    games = compute_referee_features(games, data["officials"])

    print("  Computing roster features...")
    games = compute_roster_features(games, data["player_box_scores"], data["game_ids"])

    print("  Computing head-to-head history features...")
    games = compute_h2h_features(games)

    print("  Computing conditional matchup stats (offrtg vs good/bad defenses)...")
    games = compute_conditional_matchup_stats(games)

    print("  Computing de Prado features (entropy, CUSUM)...")
    games = compute_deprado_features(games)

    print("  Aligning Massey + alternative ratings (from precomputed parquet)...")
    massey_df = data.get("massey", pd.DataFrame())
    if massey_df.empty:
        print("    WARNING: MasseyRatings.parquet not found. Run: python -m data_curation.scripts.build_massey_ratings")
    else:
        games = align_massey_to_games(games, massey_df)
        massey_cols = [c for c in games.columns if "massey" in c.lower() and c.startswith(("home_", "away_"))]
        alt_cols = [c for c in games.columns if any(x in c for x in ["wolfe", "wobus", "whitlock"]) and c.startswith(("home_", "away_"))]
        offdef_cols = [c for c in games.columns if c.startswith(("home_off_", "away_off_", "home_def_", "away_def_")) and "massey" in c]
        print(f"    Aligned {len(massey_cols)} Massey + {len(alt_cols)} alt rating + {len(offdef_cols)} off/def columns")
        if massey_cols:
            print(f"    Massey coverage: {games[massey_cols[0]].notna().mean():.1%}")

    print("  Computing matchup advantage (off vs def asymmetry)...")
    games = compute_matchup_advantage(games)

    # Interaction features: crowd × location
    if "crowd_density" in games.columns and "away_travel_distance" in games.columns:
        print("  Computing interaction features (crowd × location)...")
        games["hostile_crowd_pressure"] = games["crowd_density"] * (games["away_travel_distance"] > 0).astype(float)
        games["crowd_home_lift"] = games["crowd_density"].fillna(0)

    # --- New features (Tier 1-3) ---
    print("  Computing Pythagorean expectation & residual...")
    games = compute_pythagorean_features(games)

    print("  Computing Four Factors composite...")
    games = compute_four_factors_composite(games)

    print("  Computing pace mismatch...")
    games = compute_pace_mismatch(games)

    print("  Computing scoring entropy...")
    games = compute_scoring_entropy(games)

    print("  Computing ACWR (workload ratio)...")
    games = compute_acwr_features(games)

    print("  Computing directional travel fatigue...")
    games = compute_directional_travel(games, data["arenas"], data["team_map"])

    print("  Computing half-point totals from quarter rolling...")
    for side in ("home", "away"):
        q1, q2 = f"{side}_roll10_q1", f"{side}_roll10_q2"
        q3, q4 = f"{side}_roll10_q3", f"{side}_roll10_q4"
        if all(c in games.columns for c in [q1, q2, q3, q4]):
            games[f"{side}_roll10_h1_pts"] = games[q1] + games[q2]
            games[f"{side}_roll10_h2_pts"] = games[q3] + games[q4]

    print("  Computing blowout & close game rates...")
    games = compute_blowout_close_features(games)

    print("  Computing overtime history...")
    games = compute_overtime_history(games, data["quarter_scores"])

    print("  Computing margin autocorrelation...")
    games = compute_margin_autocorrelation(games)

    print("  Computing defensive consistency...")
    games = compute_defensive_consistency(games)

    print("  Computing scoring concentration (Gini)...")
    games = compute_scoring_concentration(games)

    print("  Computing series-specific features...")
    games = compute_series_features(games)

    print("  Computing team hustle aggregates...")
    games = compute_hustle_features(games, data.get("hustle", None))
    # --- End new features ---

    print("  Computing differential features (home - away)...")
    games = compute_diffs(games)

    print("  Computing sum features (home + away)...")
    games = compute_sums(games)

    # Venue-conditioned diffs: home_roll10_pts_athome - away_roll10_pts_onroad → diff_roll10_pts_venue
    venue_athome_cols = [c for c in games.columns if c.startswith("home_roll") and c.endswith("_athome")]
    for hcol in venue_athome_cols:
        stat_window = hcol.replace("home_", "").replace("_athome", "")  # e.g. roll10_pts
        acol = f"away_{stat_window}_onroad"
        if acol in games.columns:
            games[f"diff_{stat_window}_venue"] = games[hcol] - games[acol]

    # Post-diff/sum features that need diff or sum columns
    print("  Computing Log5 implied probability...")
    games = compute_log5_features(games)

    print("  Computing half scoring rate...")
    games = compute_half_scoring_rate(games)

    if not skip_random:
        print("  Generating symbolic features (diff × sum interactions)...")
        games, recipes = generate_symbolic_features(games)
        sf_cols = [c for c in games.columns if c.startswith("sf_")]
        print(f"    Generated {len(sf_cols)} symbolic features from diff_* + sum_* pool")
        # Save recipes for interpretability
        import json as _json
        recipes_path = output / "symbolic_recipes.json"
        with open(recipes_path, "w") as f:
            _json.dump(recipes, f, indent=2)
    else:
        print("  Skipped symbolic features (--skip-random)")

    logger.info("[step3] feature engineering complete: %d total features  elapsed=%s",
                games.shape[1], _elapsed(t0))
    print(f"  Feature engineering complete. Shape: {games.shape}")
    print(f"  [{_elapsed(t0)}]")

    # Save intermediate dataset
    games.to_parquet(output / "game_features.parquet", index=False)
    print(f"  Saved to {output / 'game_features.parquet'}")

    # ── Step 4: De Prado feature importance analysis ─────────────────────────
    t0 = time.time()
    logger.info("=== STEP 4: Feature importance ===")
    print("\nStep 4: De Prado feature importance analysis...")

    synth = synthetic_validation()
    print(f"  Synthetic MDI validation: {'PASS' if synth['mdi_pass'] else 'FAIL'}")

    # Build X, y — ONLY pregame features (no same-game leakage)
    # Valid prefixes: rolling stats, ratings, momentum, context, series, random combos
    PREGAME_PREFIXES = (
        "diff_roll",        # rolling averages of prior games (includes venue-conditioned)
        "diff_bpi", "diff_bpioffense", "diff_bpidefense", "diff_bpirank",
        "diff_playoffbpi", "diff_offtalent", "diff_deftalent",
        "diff_sag_rating", "diff_elo_score", "diff_predictor",
        "diff_pure_elo", "diff_golden_mean", "diff_recent",
        "diff_default_massey", "diff_location_adjusted_massey",
        "diff_crowd_adjusted_massey", "diff_crowd_weighted_massey",
        "diff_experience_adjusted_massey", "diff_travel_adjusted_massey",
        "diff_context_adjusted_massey",
        "diff_colley",
        "diff_win_streak", "diff_win_pct", "diff_win_entropy",
        "diff_margin_last", "diff_cusum",
        "diff_days_rest", "diff_is_back_to_back",
        "diff_travel_distance", "diff_timezone_shift",
        "diff_away_streak", "diff_days_span_", "diff_games_per_week_",
        "diff_venue_switches_", "diff_travel_intensity_",
        "diff_active_players", "diff_dnp_count",
        "diff_h2h_",            # head-to-head history (win rate, avg margin vs this opponent)
        "diff_offrtg_vs_good_def", "diff_offrtg_vs_bad_def",  # conditional matchup stats
        "diff_off_default_massey", "diff_off_location_adjusted_massey",  # offensive Massey
        "diff_def_default_massey", "diff_def_location_adjusted_massey",  # defensive Massey
        "diff_matchup_advantage",   # off vs def asymmetry
        "diff_whitlock", "diff_wolfe", "diff_wobus",  # alternative rating systems
        # New features
        "diff_pyth_", "diff_ff_",  # Pythagorean, Four Factors composite
        "diff_scoring_entropy", "diff_scoring_gini",  # scoring diversity
        "diff_acwr_",              # workload ratio
        "diff_roll10_q", "diff_roll10_h1_", "diff_roll10_h2_",  # quarter rolling
        "diff_blowout_rate", "diff_close_game_rate",  # game variance
        "diff_ot_",                # overtime history
        "diff_margin_autocorr",    # momentum pattern
        "diff_def_consistency",    # defensive reliability
        "diff_deflections_", "diff_contestedshots_", "diff_looseballsrecoveredtotal_", "diff_screenassists_",  # hustle
        "diff_h1_scoring_rate", "diff_h2_scoring_rate",  # half scoring rates
        # Sum features (predict totals, combined intensity)
        "sum_roll", "sum_bpi", "sum_sag_rating", "sum_elo_score",
        "sum_predictor", "sum_pure_elo", "sum_golden_mean", "sum_recent",
        "sum_default_massey", "sum_location_adjusted_massey",
        "sum_crowd_adjusted_massey", "sum_crowd_weighted_massey",
        "sum_experience_adjusted_massey", "sum_travel_adjusted_massey",
        "sum_context_adjusted_massey", "sum_colley",
        "sum_win_streak", "sum_win_pct", "sum_days_rest",
        "sum_pyth_", "sum_ff_", "sum_scoring_entropy", "sum_scoring_gini",
        "sum_acwr_", "sum_roll10_q", "sum_roll10_h1_", "sum_roll10_h2_",
        "sum_blowout_rate", "sum_close_game_rate", "sum_ot_",
        "sum_def_consistency", "sum_deflections_", "sum_contestedshots_",
        "sum_h1_scoring_rate", "sum_h2_scoring_rate",
        "sf_",              # symbolic features (replaces rc_ random linear combos)
    )
    PREGAME_EXACT = {
        "away_travel_distance", "away_timezone_shift",
        "crowd_density", "sellout_flag",
        "crew_home_win_rate", "crew_avg_total", "crew_experience",
        "series_game_number", "series_lead",
        "hostile_crowd_pressure", "crowd_home_lift",
        "log5_implied_prob",        # Log5 matchup probability
        "pace_mismatch", "combined_pace",  # pace features (matchup-level)
        "away_directional_fatigue", "away_eastward_hours",  # directional travel
        "higher_seed_flag", "series_rest_days", "series_home_win_rate",  # series
    }

    # Also catch any diff_*_massey columns dynamically (future-proofs new Massey designs)
    massey_diff_cols = [c for c in games.columns
                       if c.startswith("diff_") and "massey" in c
                       and games[c].dtype.kind in "fi"]

    feat_cols = [c for c in games.columns
                 if (c.startswith(PREGAME_PREFIXES) or c in PREGAME_EXACT)
                 and games[c].dtype.kind in "fi"]
    # Add any Massey diffs not already caught by prefix
    for c in massey_diff_cols:
        if c not in feat_cols:
            feat_cols.append(c)

    X = games[feat_cols].copy()
    y = games[target].copy()

    REGRESSION_TARGETS = {"target_spread", "target_total", "target_home_score", "target_away_score",
                          "target_h1_spread", "target_h2_spread", "target_h1_total", "target_h2_total",
                          "target_series_total_games", "target_series_spread"}
    SMALL_SAMPLE_TARGETS = {"target_series_winner", "target_series_total_games",
                            "target_series_spread", "target_series_exact"}
    is_regression = target in REGRESSION_TARGETS
    cv_splits = 5 if target in SMALL_SAMPLE_TARGETS else None

    valid_mask = y.notna()
    X = X[valid_mask]
    if is_regression:
        y = y[valid_mask].astype(float)
    elif target in {"target_series_exact"}:
        y = y[valid_mask].astype(str)
    else:
        y = y[valid_mask].astype(int)
    seasons = games.loc[valid_mask, "season"]

    X = X.fillna(X.median())

    logger.info("[step4] X.shape=%s target='%s' type=%s",
                X.shape, target, "regression" if is_regression else "classification")
    print(f"  Features: {X.shape[1]}, Samples: {X.shape[0]}")
    print(f"  Target: {target} ({'regression' if is_regression else 'classification'})")
    if cv_splits:
        print(f"  CV: {cv_splits}-fold (grouped years) — small sample mode")

    sample_weight = time_decay_weights(games.loc[valid_mask, "game_date"], c=0.85)

    importance_results = run_all_importance(
        X, y, seasons,
        sample_weight=sample_weight,
        run_sfi=True,
        run_desub_mda=with_desub,
        run_pca_mda=True,
        run_residual_mda=True,
        regression=is_regression,
        cv_splits=cv_splits,
    )
    logger.info("[step4] importance done  elapsed=%s", _elapsed(t0))
    print(f"  [{_elapsed(t0)}]")

    # ── Step 5: Save results ─────────────────────────────────────────────────
    t0 = time.time()
    logger.info("=== STEP 5: Save results ===")
    print("\nStep 5: Saving results...")

    # Use target-specific subdirectory so winner/spread results don't overwrite each other
    target_short = target.replace("target_", "")  # e.g. "winner", "spread"
    target_dir = output / target_short
    target_dir.mkdir(exist_ok=True)

    importance_results["summary"].to_csv(target_dir / "feature_importance_catalog.csv")
    importance_results["mdi"].to_csv(target_dir / "importance_mdi.csv")
    importance_results["cfi_mda"].to_csv(target_dir / "importance_cfi_mda.csv")
    if importance_results.get("sfi") is not None:
        importance_results["sfi"].to_csv(target_dir / "importance_sfi.csv")
    if importance_results.get("desub_mda") is not None:
        importance_results["desub_mda"].to_csv(target_dir / "importance_desub_mda.csv")
        importance_results["desub_mda_raw"].to_csv(target_dir / "importance_desub_mda_raw.csv")
    if importance_results.get("pca_mda") is not None:
        importance_results["pca_mda"].to_csv(target_dir / "importance_pca_mda.csv")
        importance_results["pca_mda_raw"].to_csv(target_dir / "importance_pca_mda_raw.csv")
        importance_results["pca_mda_pc_summary"].to_csv(target_dir / "importance_pca_mda_pc_summary.csv")
    if importance_results.get("resid_mda") is not None:
        importance_results["resid_mda"].to_csv(target_dir / "importance_resid_mda.csv")
        importance_results["resid_mda_raw"].to_csv(target_dir / "importance_resid_mda_raw.csv")

    importance_results["mdi_raw"].to_csv(target_dir / "importance_mdi_raw.csv")
    importance_results["cfi_mda_raw"].to_csv(target_dir / "importance_cfi_mda_raw.csv")

    # Denoising report
    with open(target_dir / "denoising_report.json", "w") as f:
        json.dump(importance_results["denoising_info"], f, indent=2)

    # Cluster map
    cluster_map = {str(cid): members for cid, members in importance_results["clusters"].items()}
    with open(target_dir / "cluster_map.json", "w") as f:
        json.dump(cluster_map, f, indent=2)

    filtered_dir = target_dir / "filtered"
    filtered_dir.mkdir(exist_ok=True)
    importance_results["filter_report"].to_csv(filtered_dir / "feature_report.csv")
    survivors = importance_results["survivors"]
    with open(filtered_dir / "feature_list.txt", "w") as f:
        f.write("\n".join(survivors))
    logger.info("[step5] saving results to %s", target_dir)
    mdi_top10 = importance_results["mdi"].head(10).index.tolist()
    logger.info("[step5] MDI top-10: %s", mdi_top10)
    if importance_results.get("desub_mda") is not None:
        desub_top10 = importance_results["desub_mda"].nlargest(10, "mean").index.tolist()
        logger.info("[step5] Desub-MDA top-10: %s", desub_top10)
    if importance_results.get("sfi") is not None:
        sfi_top10 = importance_results["sfi"].head(10).index.tolist()
        logger.info("[step5] SFI top-10: %s", sfi_top10)
    logger.info("[step5] survivors=%d  elapsed=%s", len(survivors), _elapsed(t0))
    print(f"  {len(survivors)} surviving features -> {filtered_dir}/feature_list.txt")

    importance_results["pca_info"].to_csv(target_dir / "pca_cross_check.csv")
    with open(target_dir / "kendall_tau.json", "w") as f:
        json.dump(importance_results["tau_results"], f, indent=2)

    plot_cfi_mda_distributions(
        importance_results["cfi_mda_raw"],
        importance_results["clusters"],
        output_path=str(target_dir / "cfi_mda_distributions.png"),
    )

    print(f"\nTop 15 features by de-substituted MDA:")
    desub = importance_results.get("desub_mda")
    if desub is not None:
        top = desub.nlargest(15, "mean")
        for feat, row in top.iterrows():
            print(f"  {feat:<42} desub_MDA={row['mean']:.4f}")

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
                        choices=["target_winner", "target_home_score", "target_away_score",
                                 "target_spread", "target_total",
                                 "target_h1_spread", "target_h2_spread",
                                 "target_h1_total", "target_h2_total",
                                 "target_home_wins_h1", "target_home_wins_h2",
                                 "target_overtime",
                                 "target_series_winner", "target_series_total_games",
                                 "target_series_spread", "target_series_exact"])
    parser.add_argument("--skip-massey", action="store_true")
    parser.add_argument("--skip-random", action="store_true")
    parser.add_argument("--with-desub", action="store_true",
                        help="Include de-substituted MDA (slow, ~34k model fits). Off by default.")
    args = parser.parse_args()
    main(args.output_dir, args.target, args.skip_massey, args.skip_random, args.with_desub, args.data_dir)
