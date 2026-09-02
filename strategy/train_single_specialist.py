"""
train_single_specialist.py
---------------------------
Train exactly one specialist (LOYO CV, same as run_specialist_ensemble) and
write its OOF predictions with join keys attached live — no re-join against a
separately-loaded parquet later.

Motivation: catboost_deep__trees carries 35.9% of the production winner
ensemble's weight and its own LOYO metric (0.6071 log_loss) is barely worse
than the full 17-model ensemble (0.6053) — see ensemble_config.json /
stacking_vs_flat.json. Training all 46 candidates to answer "does the model
beat the market" is wasted compute when the dominant single model already
answers it to within ~0.3% relative.

Run:
    python3.11 -m strategy.train_single_specialist --uid catboost_deep__trees
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.config import GAME_PARQUET, FEATURES_ROOT, load_feature_list
from strategy.data import TARGET_MAP
from strategy.ensemble import build_specialist_candidates, train_single_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid", required=True, help="e.g. catboost_deep__trees")
    parser.add_argument("--target", default="winner")
    args = parser.parse_args()

    target_col, task = TARGET_MAP[args.target]

    candidates = build_specialist_candidates(task)
    matches = [c for c in candidates if c.uid() == args.uid]
    if not matches:
        available = sorted(c.uid() for c in candidates)
        raise SystemExit(f"No candidate '{args.uid}'. Available: {available}")
    spec = matches[0]
    print(f"Training {spec.uid()} (family={spec.family}, feature_subset={spec.feature_subset})")

    df_raw = pd.read_parquet(GAME_PARQUET)
    valid = df_raw[target_col].notna()
    df_raw = df_raw[valid].reset_index(drop=True)
    print(f"Dataset: {len(df_raw)} games")

    y_series = df_raw[target_col].astype(int) if task == "classification" else df_raw[target_col].astype(float)
    seasons_series = df_raw["season"].copy()

    feat_path = FEATURES_ROOT / args.target / "filtered" / f"feature_list_{spec.feature_subset}.txt"
    feats = load_feature_list(feat_path)
    feats = [f for f in feats if f in df_raw.columns]
    print(f"Feature group '{spec.feature_subset}': {len(feats)} features")
    X = df_raw[feats].copy()

    result = train_single_model(spec, X, y_series, seasons_series, task,
                                curves_dir=None)
    if result.failed:
        raise SystemExit(f"Training failed: {result.error_msg}")

    valid_mask = result.oof_mask & ~np.isnan(result.oof_preds)
    print(f"Valid OOF rows: {valid_mask.sum()}/{len(df_raw)}  metric={result.metric:.4f}")

    oof_df = pd.DataFrame({
        "y_true": y_series.values[valid_mask],
        "y_pred": result.oof_preds[valid_mask],
        "season": seasons_series.values[valid_mask],
        "game_date": df_raw["game_date"].values[valid_mask],
        "game_id": df_raw["game_id"].values[valid_mask],
        "home_team_abbr": df_raw["home_team_abbr"].values[valid_mask],
        "away_team_abbr": df_raw["away_team_abbr"].values[valid_mask],
    })
    out_dir = Path("strategy/output/nba") / args.target
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"single_{spec.uid()}_oof.csv"
    oof_df.to_csv(out_path, index=False)
    print(f"Saved -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
