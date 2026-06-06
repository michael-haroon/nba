"""
Backfill off_default_massey, def_default_massey, off_location_adjusted_massey,
and def_location_adjusted_massey into MasseyRatings.parquet for all seasons
where they are currently null (everything prior to 2025-26).

These columns were added to build_massey_ratings.py after the initial full run,
so older rows in the parquet are missing them. This script only runs the 4
off/def fits — it does not recompute any other rating columns.

Usage:
    python -m data_curation.scripts.backfill_offdef_massey
    python -m data_curation.scripts.backfill_offdef_massey --min-season 2010-11
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from feature_pipeline.engineering.massey_ratings import (
    DEFAULT_MASSEY_DESIGNS,
    fit_massey_offdef,
    prepare_massey_context,
)
from data_curation.scripts.build_massey_ratings import build_game_scores

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "MasseyRatings.parquet"

OFFDEF_DESIGNS = (DEFAULT_MASSEY_DESIGNS[0], DEFAULT_MASSEY_DESIGNS[1])  # default, location_adjusted


def _fit_offdef_for_date(season_games: pd.DataFrame, game_date: pd.Timestamp, season: str) -> list[pd.DataFrame]:
    prior = season_games[season_games["game_date"] < game_date]
    has_offdef = (
        "home_offrtg" in prior.columns and
        prior["home_offrtg"].notna().sum() > 10
    )
    if not has_offdef:
        return []

    results = []
    as_of = game_date - pd.Timedelta(microseconds=1)
    for des in OFFDEF_DESIGNS:
        for tgt_h, tgt_a, name in [
            ("home_offrtg", "away_offrtg", f"off_{des.name}"),
            ("home_defrtg", "away_defrtg", f"def_{des.name}"),
        ]:
            fit = fit_massey_offdef(prior, des, tgt_h, tgt_a, name, season=season, as_of_date=as_of)
            if not fit.ratings.empty:
                r = fit.ratings.copy()
                r["game_date"] = game_date
                results.append(r)
    return results


def compute_offdef_ratings(games: pd.DataFrame, min_season: str | None = None) -> pd.DataFrame:
    import os
    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])
    if min_season:
        games = games[games["season"] >= min_season]
    games = prepare_massey_context(games)

    n_jobs = min(os.cpu_count() or 8, 8)
    all_rows = []
    seasons = sorted(games["season"].dropna().unique())

    for i, season in enumerate(seasons):
        t0 = time.time()
        sg = games[games["season"] == season].sort_values("game_date").reset_index(drop=True)
        valid_dates = [d for d in sorted(sg["game_date"].unique())
                       if len(sg[sg["game_date"] < d]) >= 10]

        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_fit_offdef_for_date)(sg, gd, season) for gd in valid_dates
        )
        flat = [r for date_results in results for r in date_results]
        if flat:
            season_df = pd.concat(flat, ignore_index=True)
            pivot = season_df.pivot_table(
                index=["season", "game_date", "team_id"],
                values=[c for c in season_df.columns if c not in ("season", "game_date", "team_id")],
                aggfunc="first",
            ).reset_index()
            if isinstance(pivot.columns, pd.MultiIndex):
                pivot.columns = ["_".join(str(c) for c in col).strip("_") for col in pivot.columns]
            all_rows.append(pivot)

        print(f"  [{i+1}/{len(seasons)}] {season}: {len(valid_dates)} dates ({time.time()-t0:.1f}s)")

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-season", default=None)
    args = parser.parse_args()

    t0 = time.time()
    print("Loading existing MasseyRatings.parquet...")
    existing = pd.read_parquet(OUTPUT_PATH)
    print(f"  {len(existing)} rows, {existing.shape[1]} cols")

    offdef_cols = ["off_default_massey", "def_default_massey",
                   "off_location_adjusted_massey", "def_location_adjusted_massey"]
    already_have = [c for c in offdef_cols if c in existing.columns and existing[c].notna().any()]
    need_fill_mask = existing[offdef_cols[0]].isna() if offdef_cols[0] in existing.columns else pd.Series(True, index=existing.index)
    n_missing = need_fill_mask.sum()
    print(f"  Rows missing off/def columns: {n_missing}")

    print("\nLoading game scores...")
    games = build_game_scores()
    print(f"  {len(games)} game rows loaded")

    # Only recompute seasons that have missing rows
    if args.min_season:
        min_season = args.min_season
    else:
        if offdef_cols[0] in existing.columns:
            missing_seasons = existing.loc[need_fill_mask, "season"].unique()
            min_season = min(missing_seasons) if len(missing_seasons) else None
        else:
            min_season = None
    print(f"  Computing off/def from season: {min_season or 'all'}")

    print("\nComputing off/def Massey ratings...")
    new_offdef = compute_offdef_ratings(games, min_season=min_season)

    if new_offdef.empty:
        print("Nothing to update.")
        return

    print(f"\n  new_offdef shape: {new_offdef.shape}")
    print(f"  Columns: {list(new_offdef.columns)}")

    # Drop old off/def cols from existing, then merge in new values
    existing = existing.drop(columns=[c for c in offdef_cols if c in existing.columns], errors="ignore")
    rank_cols = [f"{c}_rank" for c in offdef_cols]
    existing = existing.drop(columns=[c for c in rank_cols if c in existing.columns], errors="ignore")

    existing["team_id"] = existing["team_id"].astype(int)
    new_offdef["team_id"] = new_offdef["team_id"].astype(int)
    existing["game_date"] = pd.to_datetime(existing["game_date"])
    new_offdef["game_date"] = pd.to_datetime(new_offdef["game_date"])

    merged = existing.merge(new_offdef, on=["season", "game_date", "team_id"], how="left")
    print(f"\n  Final shape: {merged.shape}")
    for col in offdef_cols:
        if col in merged.columns:
            cov = merged[col].notna().mean()
            print(f"  {col} coverage: {cov:.1%}")

    merged.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved to {OUTPUT_PATH}  ({time.time()-t0:.1f}s total)")


if __name__ == "__main__":
    main()
