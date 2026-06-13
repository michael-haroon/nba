"""
Multi-target feature importance runner.

Computes feature engineering ONCE, then runs per-target importance analysis
using all available cores (each target computes its own ONC clustering on
its own valid rows — correct q-ratio for Marcenko-Pastur denoising).

Usage:
    python -m feature_pipeline.analysis.run_all_targets
    python -m feature_pipeline.analysis.run_all_targets --skip-massey
    python -m feature_pipeline.analysis.run_all_targets --targets target_winner target_spread
"""

from __future__ import annotations

import feature_pipeline.compute  # noqa: F401 — BLAS thread config (must precede numpy)

import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from feature_pipeline.compute import get_n_jobs
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
from feature_pipeline.logging_config import setup_pipeline_logger
from feature_pipeline.analysis.feature_importance import (
    run_all_importance,
    synthetic_validation,
    plot_cfi_mda_distributions,
)

ALL_TARGETS = [
    "target_winner", "target_spread", "target_total",
    "target_home_score", "target_away_score",
    "target_h1_spread", "target_h2_spread",
    "target_h1_total", "target_h2_total",
    "target_home_wins_h1", "target_home_wins_h2",
    "target_overtime",
    "target_series_winner", "target_series_total_games",
    "target_series_spread", "target_series_exact",
]

REGRESSION_TARGETS = {
    "target_spread", "target_total", "target_home_score", "target_away_score",
    "target_h1_spread", "target_h2_spread", "target_h1_total", "target_h2_total",
    "target_series_total_games", "target_series_spread",
}
SMALL_SAMPLE_TARGETS = {
    "target_series_winner", "target_series_total_games",
    "target_series_spread", "target_series_exact",
}

PREGAME_PREFIXES = (
    "diff_roll",
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
    "diff_h2h_",
    "diff_offrtg_vs_good_def", "diff_offrtg_vs_bad_def",
    "diff_off_default_massey", "diff_off_location_adjusted_massey",
    "diff_def_default_massey", "diff_def_location_adjusted_massey",
    "diff_matchup_advantage",
    "diff_whitlock", "diff_wolfe", "diff_wobus",
    "diff_pyth_", "diff_ff_",
    "diff_scoring_entropy", "diff_scoring_gini",
    "diff_acwr_",
    "diff_roll10_q", "diff_roll10_h1_", "diff_roll10_h2_",
    "diff_blowout_rate", "diff_close_game_rate",
    "diff_ot_",
    "diff_margin_autocorr",
    "diff_def_consistency",
    "diff_deflections_", "diff_contestedshots_", "diff_looseballsrecoveredtotal_", "diff_screenassists_",
    "diff_h1_scoring_rate", "diff_h2_scoring_rate",
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
    "sf_",
)
PREGAME_EXACT = {
    "away_travel_distance", "away_timezone_shift",
    "crowd_density", "sellout_flag",
    "crew_home_win_rate", "crew_avg_total", "crew_experience",
    "series_game_number", "series_lead",
    "hostile_crowd_pressure", "crowd_home_lift",
    "log5_implied_prob",
    "pace_mismatch", "combined_pace",
    "away_directional_fatigue", "away_eastward_hours",
    "higher_seed_flag", "series_rest_days", "series_home_win_rate",
}


def _elapsed(t0: float) -> str:
    elapsed = time.time() - t0
    if elapsed < 60:
        return f"{elapsed:.1f}s"
    elif elapsed < 3600:
        return f"{elapsed/60:.1f}m"
    return f"{elapsed/3600:.1f}h"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _run_single_target(target: str, X: pd.DataFrame, games: pd.DataFrame,
                       output: Path, with_desub: bool = False):
    """Run feature importance for a single target using all available cores."""
    logger = logging.getLogger("feature_pipeline")
    t0 = time.time()
    target_short = target.replace("target_", "")
    print(f"\n{'─'*40}\n  [{_now()}] TARGET: {target} ({target_short})\n{'─'*40}")
    logger.info("[%s] starting", target_short)

    y = games[target].copy()
    is_regression = target in REGRESSION_TARGETS
    cv_splits = 5 if target in SMALL_SAMPLE_TARGETS else None

    valid_mask = y.notna()
    X_target = X[valid_mask].copy()
    if is_regression:
        y = y[valid_mask].astype(float)
    elif target in {"target_series_exact"}:
        y = y[valid_mask].astype(str)
    else:
        y = y[valid_mask].astype(int)
    seasons = games.loc[valid_mask, "season"]

    X_target = X_target.fillna(X_target.median())
    sample_weight = time_decay_weights(games.loc[valid_mask, "game_date"], c=0.85)

    print(f"  Features: {X_target.shape[1]}, Samples: {X_target.shape[0]}")
    print(f"  Type: {'regression' if is_regression else 'classification'}")
    logger.info("[%s] X.shape=%s type=%s cv_splits=%s",
                target_short, X_target.shape,
                "regression" if is_regression else "classification", cv_splits)

    t_importance = time.time()
    importance_results = run_all_importance(
        X_target, y, seasons, sample_weight=sample_weight,
        run_sfi=True,
        run_desub_mda=with_desub,
        run_pca_mda=True,
        run_residual_mda=True,
        regression=is_regression, cv_splits=cv_splits,
    )
    logger.info("[%s] run_all_importance elapsed=%s", target_short, _elapsed(t_importance))

    # Log subop summaries from results
    dni = importance_results.get("denoising_info", {})
    logger.debug("[%s] MP denoising: lambda_plus=%.4f signal_evals=%d noise_evals=%d signal_var=%.1f%%",
                 target_short,
                 dni.get("lambda_plus", float("nan")),
                 dni.get("n_signal_eigenvalues", -1),
                 dni.get("n_noise_eigenvalues", -1),
                 dni.get("signal_variance_pct", float("nan")))
    clusters = importance_results["clusters"]
    logger.debug("[%s] ONC clusters=%d sizes=%s", target_short, len(clusters),
                 {cid: len(m) for cid, m in clusters.items()})
    mdi = importance_results["mdi"]
    logger.info("[%s] MDI top-10: %s", target_short, mdi.head(10).index.tolist())
    sfi = importance_results.get("sfi")
    if sfi is not None:
        sfi_folds = importance_results["sfi_raw"].shape[0] if importance_results.get("sfi_raw") is not None else "?"
        logger.info("[%s] SFI top-10: %s (n_folds=%s)", target_short,
                    sfi.head(10).index.tolist(), sfi_folds)
    cfi_mda = importance_results["cfi_mda"]
    n_pos_cfi = int((cfi_mda["mean"] > 0).sum())
    logger.info("[%s] CFI-MDA: %d/%d clusters positive", target_short, n_pos_cfi, len(cfi_mda))
    pca_mda = importance_results.get("pca_mda")
    if pca_mda is not None:
        logger.info("[%s] PCA-MDA top-10: %s", target_short, pca_mda.head(10).index.tolist())
    resid_mda = importance_results.get("resid_mda")
    if resid_mda is not None:
        logger.info("[%s] resid-MDA top-10: %s", target_short, resid_mda.head(10).index.tolist())
    filter_report = importance_results["filter_report"]
    tier_counts = filter_report["tier"].value_counts().to_dict()
    survivors = importance_results["survivors"]
    logger.info("[%s] filter: %s | survivors=%d", target_short, tier_counts, len(survivors))

    # Save results
    t_save = time.time()
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

    with open(target_dir / "denoising_report.json", "w") as f:
        json.dump(importance_results["denoising_info"], f, indent=2)

    cluster_map = {str(cid): members for cid, members in importance_results["clusters"].items()}
    with open(target_dir / "cluster_map.json", "w") as f:
        json.dump(cluster_map, f, indent=2)

    filtered_dir = target_dir / "filtered"
    filtered_dir.mkdir(exist_ok=True)
    importance_results["filter_report"].to_csv(filtered_dir / "feature_report.csv")
    with open(filtered_dir / "feature_list.txt", "w") as f:
        f.write("\n".join(survivors))

    importance_results["pca_info"].to_csv(target_dir / "pca_cross_check.csv")
    with open(target_dir / "kendall_tau.json", "w") as f:
        json.dump(importance_results["tau_results"], f, indent=2)

    plot_cfi_mda_distributions(
        importance_results["cfi_mda_raw"],
        importance_results["clusters"],
        output_path=str(target_dir / "cfi_mda_distributions.png"),
    )
    logger.debug("[%s] results saved to %s elapsed=%s", target_short, target_dir, _elapsed(t_save))

    elapsed = _elapsed(t0)
    print(f"\n  [{_now()}] [{target_short}] DONE — {len(survivors)} survivors — {elapsed}")
    logger.info("[%s] DONE — survivors=%d total_elapsed=%s", target_short, len(survivors), elapsed)
    return target_short, len(survivors), elapsed


def main(output_dir: str = "output/features",
         skip_massey: bool = False,
         skip_random: bool = False,
         with_desub: bool = False,
         data_dir: str | None = None,
         targets: list[str] | None = None):

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    setup_pipeline_logger(log_dir)
    logger = logging.getLogger("feature_pipeline")

    pipeline_start = time.time()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    n_cpus = get_n_jobs()
    if targets is None:
        targets = ALL_TARGETS

    # ── Banner ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"  MULTI-TARGET FEATURE IMPORTANCE")
    print(f"  CPU cores: {n_cpus} (all cores per target — sequential targets)")
    print(f"  Targets: {len(targets)}")
    print(f"  Instance: {os.uname().nodename} ({os.uname().machine})")
    print("=" * 60)
    print()
    logger.info("=== MULTI-TARGET RUN: %d targets on %s ===", len(targets), os.uname().nodename)

    # ── Step 1: Load data (ONCE) ─────────────────────────────────────────────
    t0 = time.time()
    print(f"[{_now()}] Step 1: Loading data...")
    data = load_all(data_dir)
    print(f"  Box scores: {data['box_scores'].shape}")
    print(f"  [{_elapsed(t0)}]")
    logger.info("[step1] box_scores=%s bpi=%s sagarin=%s elapsed=%s",
                data['box_scores'].shape, data['bpi'].shape, data['sagarin'].shape, _elapsed(t0))

    # ── Step 2: Build game-level dataset (ONCE) ──────────────────────────────
    t0 = time.time()
    print(f"\n[{_now()}] Step 2: Building game-level dataset...")
    games = build_game_rows(data["box_scores"], data["game_ids"], data["team_map"])
    games = attach_quarter_scores(games, data["quarter_scores"], data["team_map"])
    games = build_targets(games)
    games = build_series_targets(games)
    print(f"  Games: {games.shape[0]}, Columns: {games.shape[1]}")
    print(f"  [{_elapsed(t0)}]")
    logger.info("[step2] games=%d cols=%d elapsed=%s", games.shape[0], games.shape[1], _elapsed(t0))

    # ── Step 3: Feature engineering (ONCE) ───────────────────────────────────
    t0 = time.time()
    print(f"\n[{_now()}] Step 3: Engineering features...")

    games = align_ratings_to_games(games, data["bpi"], data["sagarin"], data["team_map"])
    games = compute_rolling_features(games, windows=[5, 10, 20])
    games = compute_venue_rolling_features(games)
    games = compute_score_momentum(games)
    games = compute_context_features(games, data["arenas"], data.get("game_summaries"))
    games = compute_travel_sequence_features(games, data["arenas"])
    games = compute_referee_features(games, data["officials"])
    games = compute_roster_features(games, data["player_box_scores"], data["game_ids"])
    games = compute_h2h_features(games)
    games = compute_conditional_matchup_stats(games)
    games = compute_deprado_features(games)

    if not skip_massey:
        massey_df = data.get("massey", pd.DataFrame())
        if not massey_df.empty:
            games = align_massey_to_games(games, massey_df)
        else:
            logger.warning("[step3] MasseyRatings.parquet not found — Massey features skipped")
    games = compute_matchup_advantage(games)

    if "crowd_density" in games.columns and "away_travel_distance" in games.columns:
        games["hostile_crowd_pressure"] = games["crowd_density"] * (games["away_travel_distance"] > 0).astype(float)
        games["crowd_home_lift"] = games["crowd_density"].fillna(0)

    games = compute_pythagorean_features(games)
    games = compute_four_factors_composite(games)
    games = compute_pace_mismatch(games)
    games = compute_scoring_entropy(games)
    games = compute_acwr_features(games)
    games = compute_directional_travel(games, data["arenas"], data["team_map"])

    for side in ("home", "away"):
        q1, q2 = f"{side}_roll10_q1", f"{side}_roll10_q2"
        q3, q4 = f"{side}_roll10_q3", f"{side}_roll10_q4"
        if all(c in games.columns for c in [q1, q2, q3, q4]):
            games[f"{side}_roll10_h1_pts"] = games[q1] + games[q2]
            games[f"{side}_roll10_h2_pts"] = games[q3] + games[q4]

    games = compute_blowout_close_features(games)
    games = compute_overtime_history(games, data["quarter_scores"])
    games = compute_margin_autocorrelation(games)
    games = compute_defensive_consistency(games)
    games = compute_scoring_concentration(games)
    games = compute_series_features(games)
    games = compute_hustle_features(games, data.get("hustle", None))
    games = compute_diffs(games)
    games = compute_sums(games)

    venue_athome_cols = [c for c in games.columns if c.startswith("home_roll") and c.endswith("_athome")]
    for hcol in venue_athome_cols:
        stat_window = hcol.replace("home_", "").replace("_athome", "")
        acol = f"away_{stat_window}_onroad"
        if acol in games.columns:
            games[f"diff_{stat_window}_venue"] = games[hcol] - games[acol]

    games = compute_log5_features(games)
    games = compute_half_scoring_rate(games)

    if not skip_random:
        games, recipes = generate_symbolic_features(games)
        recipes_path = output / "symbolic_recipes.json"
        with open(recipes_path, "w") as f:
            json.dump(recipes, f, indent=2)

    print(f"  Feature engineering complete. Shape: {games.shape}")
    print(f"  [{_elapsed(t0)}]")
    logger.info("[step3] feature engineering complete shape=%s elapsed=%s", games.shape, _elapsed(t0))

    games.to_parquet(output / "game_features.parquet", index=False)

    # ── Step 4: Build feature matrix X (ONCE) ────────────────────────────────
    massey_diff_cols = [c for c in games.columns
                       if c.startswith("diff_") and "massey" in c
                       and games[c].dtype.kind in "fi"]
    feat_cols = [c for c in games.columns
                 if (c.startswith(PREGAME_PREFIXES) or c in PREGAME_EXACT)
                 and games[c].dtype.kind in "fi"]
    for c in massey_diff_cols:
        if c not in feat_cols:
            feat_cols.append(c)

    X = games[feat_cols].copy()

    # Drop BPI and Sagarin columns — coverage is 10.6% and 44.5% respectively, all
    # concentrated in 2022+ (BPI) and 2013+ (SAG). Global median imputation would stamp
    # a single modern-era constant into 89%/55% of rows, destroying importance scores
    # and poisoning ONC clustering for all other features.
    # Skipping BPI and SAG — must get more data to implement them.
    bpi_sag_cols = [c for c in X.columns if any(x in c for x in ("bpi", "sag_", "sagarin"))]
    if bpi_sag_cols:
        logger.info("[step4] dropping %d BPI/SAG cols (insufficient coverage): %s ...",
                    len(bpi_sag_cols), bpi_sag_cols[:5])
        X = X.drop(columns=bpi_sag_cols)

    print(f"\n  Feature matrix: {X.shape[1]} features, {X.shape[0]} samples")
    logger.info("[step4] feature matrix X.shape=%s", X.shape)

    # ── Step 5: Synthetic validation (once) ──────────────────────────────────
    print(f"\n[{_now()}] Step 5: Synthetic MDI validation...")
    synth = synthetic_validation()
    synth_result = "PASS" if synth["mdi_pass"] else "FAIL"
    print(f"  Synthetic MDI validation: {synth_result}")
    logger.info("[step5] synthetic MDI validation: %s", synth_result)
    if not synth["mdi_pass"]:
        logger.warning("[step5] Synthetic MDI validation FAILED — importance estimates may be unreliable")

    # ── Step 6: Per-target importance (sequential, each uses all cores) ─────
    t0 = time.time()
    print(f"\n[{_now()}] Step 6: Running {len(targets)} targets sequentially "
          f"(each uses all {n_cpus} cores)...")
    logger.info("[step6] starting %d targets: %s", len(targets), targets)

    # Filter to targets that exist in the dataset
    valid_targets = [t for t in targets if t in games.columns]
    skipped = [t for t in targets if t not in games.columns]
    if skipped:
        print(f"  WARNING: Skipping targets not in data: {skipped}")
        logger.warning("[step6] skipping targets not in data: %s", skipped)

    results = []
    for i, target in enumerate(valid_targets):
        print(f"\n  [{_now()}] ── Target {i+1}/{len(valid_targets)}: {target}")
        result = _run_single_target(target, X, games, output, with_desub=with_desub)
        results.append(result)

    print(f"\n  [{_now()}] All targets complete. [{_elapsed(t0)}]")
    logger.info("[step6] all targets complete elapsed=%s", _elapsed(t0))

    # ── Summary ──────────────────────────────────────────────────────────────
    total = _elapsed(pipeline_start)
    print(f"\n{'='*60}")
    print(f"  ALL TARGETS COMPLETE")
    print(f"  Total wall time: {total}")
    print(f"  Output: {output}/")
    print(f"  Results:")
    for target_short, n_survivors, elapsed in results:
        print(f"    {target_short:<25} {n_survivors:>3} survivors  ({elapsed})")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-target NBA feature importance")
    parser.add_argument("--output-dir", default="output/features")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--targets", nargs="+", default=None,
                        choices=ALL_TARGETS,
                        help="Specific targets to run (default: all 16)")
    parser.add_argument("--skip-massey", action="store_true")
    parser.add_argument("--skip-random", action="store_true")
    parser.add_argument("--with-desub", action="store_true",
                        help="Include de-substituted MDA (slow, ~34k model fits). Off by default.")
    args = parser.parse_args()
    main(args.output_dir, args.skip_massey, args.skip_random, args.with_desub,
         args.data_dir, args.targets)
