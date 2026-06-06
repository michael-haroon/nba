"""
run.py
------
Entry point for NBA strategy model training.

Usage:
    python -m strategy.run                   # all targets
    python -m strategy.run --target winner
    python -m strategy.run --target spread
    python -m strategy.run --target h1_spread
"""

from __future__ import annotations

import argparse
import time

from strategy.config import OUTPUT_DIR
from strategy.data import load, TARGET_MAP
from strategy.models import (
    build_classifier, build_regressor, build_multiclass,
    available_classifiers, available_regressors, available_multiclass,
)
from strategy.train import train_and_evaluate
from strategy.evaluate import print_model_comparison, fit_spread_residuals, save_results


def _elapsed(t0: float) -> str:
    s = time.time() - t0
    return f"{s:.1f}s" if s < 60 else f"{s/60:.1f}m"


def run_target(target: str) -> dict:
    t0 = time.time()
    _, task = TARGET_MAP[target]

    if task == "multiclass":
        build_fn = build_multiclass
        model_names = available_multiclass()
    elif task == "classification":
        build_fn = build_classifier
        model_names = available_classifiers()
    else:
        build_fn = build_regressor
        model_names = available_regressors()

    print(f"\n{'='*60}")
    print(f"  Target: {target}  ({task})")
    print(f"{'='*60}")

    results = {}
    for name in model_names:
        X, y, seasons = load(target, model_name=name)
        if not results:
            print(f"  Samples: {len(X)}, Seasons: {seasons.nunique()}")
        print(f"\n  [{name}] training... ({X.shape[1]} features)")
        t1 = time.time()
        results[name] = train_and_evaluate(X, y, seasons, name, build_fn, task)
        folds = len(results[name]["cv_df"])
        print(f"  [{name}] done — {folds} folds [{_elapsed(t1)}]")

    print_model_comparison(results, task)

    residual_dist = None
    if task == "regression":
        best_name = min(results, key=lambda n: results[n]["cv_df"]["val_loss"].mean()
                        if not results[n]["cv_df"].empty else float("inf"))
        residual_dist = fit_spread_residuals(results[best_name]["oof_preds"])
        print(f"\n  Residual Student-t fit (model={best_name}):")
        print(f"    df={residual_dist.kwds['df']:.2f}, "
              f"loc={residual_dist.kwds['loc']:.2f}, "
              f"scale={residual_dist.kwds['scale']:.2f}")

    save_results(results, OUTPUT_DIR, target, spread_residual_dist=residual_dist)

    print(f"\n  Total: {_elapsed(t0)}")
    return results


ALL_TARGETS = list(TARGET_MAP.keys())


def run_full_pipeline(targets: list[str] | None = None, resume: bool = False) -> None:
    """
    End-to-end automated pipeline:
      Phase 0: Feature routing (feature_report.csv → per-group lists)
      Phase 1: Forward selection of complementary features (cached)
      Phase 2: Train all specialist models via LOYO CV
      Phase 3: Compare flat weights vs stacking, auto-select
      Phase 4: Retrain final ensemble on full data, pickle
      Phase 5: Log results
    """
    from strategy.feature_routing import run_routing
    from strategy.forward_select import run_forward_selection
    from strategy.ensemble import run_specialist_ensemble
    from strategy.config import FEATURES_ROOT

    if targets is None:
        targets = ALL_TARGETS

    for target in targets:
        pipeline_t0 = time.time()
        print(f"\n{'#'*70}")
        print(f"  FULL PIPELINE — {target}")
        print(f"{'#'*70}")

        # Pre-check: feature_report.csv must exist
        report_path = FEATURES_ROOT / target / "filtered" / "feature_report.csv"
        if not report_path.exists():
            print(f"\n  SKIP '{target}': no feature_report.csv found.")
            print(f"  Run first: python -m feature_pipeline.analysis.run "
                  f"--target target_{target} --output-dir output/features/{target}")
            continue

        # Phase 0: Feature routing
        print(f"\n  Phase 0: Feature routing...")
        t0 = time.time()
        feature_lists = run_routing(target)
        print(f"    trees={len(feature_lists['trees'])}, "
              f"linear={len(feature_lists['linear'])}, "
              f"diversity={len(feature_lists['diversity'])}, "
              f"full={len(feature_lists['full'])}  [{_elapsed(t0)}]")

        # Phase 0.5: Logistic validation (classification targets only, cached)
        _, task = TARGET_MAP[target]
        if task == "classification":
            from strategy.logistic_validation import run_logistic_validation
            from strategy.config import FEATURES_ROOT
            # Use logistic_validation.csv as cache marker — only written by this phase,
            # never by Phase 0 routing (which writes feature_list_linear.txt).
            marker_path = FEATURES_ROOT / target / "logistic_validation.csv"
            report_mtime = (FEATURES_ROOT / target / "filtered" / "feature_report.csv").stat().st_mtime
            is_fresh = marker_path.exists() and marker_path.stat().st_mtime > report_mtime
            linear_list_path = FEATURES_ROOT / target / "filtered" / "feature_list_linear.txt"
            if is_fresh and linear_list_path.exists():
                qualified = linear_list_path.read_text().strip().splitlines()
                print(f"\n  Phase 0.5: Logistic validation (cached — {len(qualified)} qualified features)")
            else:
                print(f"\n  Phase 0.5: Logistic validation (running Box-Tidwell + iterative VIF + LOYO stability)...")
                t0 = time.time()
                qualified = run_logistic_validation(target, make_plots=False)
                print(f"    {len(qualified)} features qualified for LogReg  [{_elapsed(t0)}]")

        # Phase 1: Forward selection
        print(f"\n  Phase 1: Forward selection...")
        t0 = time.time()
        tree_features = run_forward_selection(target)
        print(f"    Final tree set: {len(tree_features)} features  [{_elapsed(t0)}]")

        # Phase 2-4: Specialist ensemble (trains, selects, stacks, pickles)
        print(f"\n  Phase 2-4: Specialist ensemble training...")
        results = run_specialist_ensemble(target)

        print(f"\n  Pipeline complete for '{target}' [{_elapsed(pipeline_t0)}]")
        print(f"  Final metric: {results.get('final_metric', 'N/A')}")
        print(f"  Method: {results.get('combination_method', 'N/A')}")


def main(target: str = "all", full_pipeline: bool = False,
         targets_flag: list[str] | None = None) -> None:
    if full_pipeline:
        pipeline_targets = targets_flag if targets_flag else (
            ALL_TARGETS if target == "all" else [target]
        )
        run_full_pipeline(pipeline_targets)
    else:
        targets = ALL_TARGETS if target == "all" else [target]
        for t in targets:
            run_target(t)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA strategy model training")
    parser.add_argument("--target", default="all",
                        choices=ALL_TARGETS + ["all"])
    parser.add_argument("--full-pipeline", action="store_true",
                        help="Run end-to-end: routing → forward selection → specialist ensemble")
    parser.add_argument("--targets", nargs="+", default=None,
                        choices=ALL_TARGETS,
                        help="Specific targets for --full-pipeline (default: all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint (uses cached results)")
    args = parser.parse_args()
    main(args.target, full_pipeline=args.full_pipeline, targets_flag=args.targets)
