"""
Build Massey ratings from game scores and save as parquet.

Computes pregame ratings for each team at each game date using only
games played BEFORE that date (no lookahead). Outputs a parquet with
one row per (season, game_date, team_id) with ratings from all 7 designs.

Output: data_curation/data/MasseyRatings.parquet
Columns: season, game_date, team_id, default_massey, default_massey_rank,
         location_adjusted_massey, ..., context_adjusted_massey, ...

Usage:
    python -m data_curation.scripts.build_massey_ratings
    python -m data_curation.scripts.build_massey_ratings --min-season 2015-16
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from feature_pipeline.engineering.massey_ratings import (
    DEFAULT_MASSEY_DESIGNS,
    MasseyDesign,
    build_massey_team_features,
    prepare_massey_context,
    fit_massey,
)
from feature_pipeline.engineering.data_loader import (
    load_box_scores,
    load_game_ids,
    load_team_map,
    load_arenas,
)
from feature_pipeline.engineering.game_builder import parse_home_away


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "MasseyRatings.parquet"


def build_game_scores() -> pd.DataFrame:
    """Load box scores and construct the game-level input for Massey fitting."""
    bs = load_box_scores(DATA_DIR, season_types=("Regular", "Playoffs"))
    gi = load_game_ids(DATA_DIR)
    tm = load_team_map(DATA_DIR)

    parsed = parse_home_away(bs["MATCH UP"])
    bs["team_abbr"] = parsed["team_abbr"]
    bs["is_home"] = parsed["is_home"]
    bs["game_date"] = pd.to_datetime(bs["GAME DATE"])

    abbr_to_id = (
        tm.drop_duplicates("TEAM_ABBREVIATION")
        .set_index("TEAM_ABBREVIATION")["TEAM_ID"]
        .to_dict()
    )
    bs["team_id"] = bs["team_abbr"].map(abbr_to_id)
    bs["PTS"] = pd.to_numeric(bs["PTS"], errors="coerce")

    # Split home/away and merge into game rows
    home = bs[bs["is_home"]][["game_date", "team_id", "PTS", "season_type"]].copy()
    home = home.rename(columns={"team_id": "home_team_id", "PTS": "home_score"})

    away = bs[~bs["is_home"]][["game_date", "team_id", "PTS", "team_abbr"]].copy()
    away = away.rename(columns={"team_id": "away_team_id", "PTS": "away_score"})
    away["_jk"] = away["game_date"].dt.strftime("%Y-%m-%d") + "|" + away["team_abbr"]

    # Match home with away
    home["opponent_abbr"] = bs[bs["is_home"]]["team_abbr"].map(
        lambda x: x  # placeholder
    )
    # Better: use the parsed opponent
    home_mask = bs["is_home"]
    home["_jk"] = (
        bs[home_mask]["game_date"].dt.strftime("%Y-%m-%d").values + "|" +
        parsed[home_mask]["opponent_abbr"].values
    )
    # away's join key is date + away_team_abbr (which is the home's opponent)
    away["_jk"] = (
        away["game_date"].dt.strftime("%Y-%m-%d") + "|" +
        away["team_abbr"]
    )

    # Simpler approach: just merge on date + the opponent relationship
    home_df = bs[bs["is_home"]][["game_date", "team_id", "PTS", "season_type"]].copy()
    home_df.columns = ["game_date", "home_team_id", "home_score", "season_type"]
    home_df["_jk"] = (
        home_df["game_date"].dt.strftime("%Y-%m-%d") + "|" +
        parsed[bs["is_home"].values]["team_abbr"].values
    )

    away_df = bs[~bs["is_home"]][["game_date", "team_id", "PTS"]].copy()
    away_df.columns = ["game_date", "away_team_id", "away_score"]
    away_df["_jk"] = (
        away_df["game_date"].dt.strftime("%Y-%m-%d") + "|" +
        parsed[~bs["is_home"].values]["opponent_abbr"].values
    )

    games = home_df.merge(away_df.drop(columns=["game_date"]), on="_jk", how="inner")
    games = games.drop(columns=["_jk"])

    # Attach season
    gi_dedup = gi.drop_duplicates("GAME_DATE")
    games = games.merge(
        gi_dedup[["GAME_DATE", "SEASON_FILTER"]],
        left_on="game_date",
        right_on="GAME_DATE",
        how="left",
    ).drop(columns=["GAME_DATE"])
    games = games.rename(columns={"SEASON_FILTER": "season"})

    # Ensure numeric
    games["home_score"] = pd.to_numeric(games["home_score"], errors="coerce")
    games["away_score"] = pd.to_numeric(games["away_score"], errors="coerce")
    games = games.dropna(subset=["home_score", "away_score", "home_team_id", "away_team_id"])
    games["home_team_id"] = games["home_team_id"].astype(int)
    games["away_team_id"] = games["away_team_id"].astype(int)
    games["game_id"] = range(len(games))

    return games


def compute_pregame_ratings(games: pd.DataFrame, min_season: str | None = None) -> pd.DataFrame:
    """
    For each (season, game_date), fit Massey on all prior games in that season,
    producing team ratings as of that date.
    """
    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])

    if min_season:
        games = games[games["season"] >= min_season]

    games = prepare_massey_context(games)

    all_ratings = []
    seasons = sorted(games["season"].dropna().unique())
    total_seasons = len(seasons)

    for i, season in enumerate(seasons):
        t0 = time.time()
        season_games = games[games["season"] == season].sort_values("game_date").reset_index(drop=True)
        game_dates = sorted(season_games["game_date"].unique())

        season_ratings = []
        for game_date in game_dates:
            prior = season_games[season_games["game_date"] < game_date]
            if len(prior) < 10:
                continue

            # Fit all designs on prior games
            for design in DEFAULT_MASSEY_DESIGNS:
                fit = fit_massey(
                    prior,
                    design,
                    season=season,
                    as_of_date=game_date - pd.Timedelta(microseconds=1),
                    preview_rows=0,
                )
                if fit.ratings.empty:
                    continue

                ratings = fit.ratings.copy()
                ratings["game_date"] = game_date
                season_ratings.append(ratings)

        if season_ratings:
            season_df = pd.concat(season_ratings, ignore_index=True)
            # Pivot: one row per (season, game_date, team_id) with all design ratings
            pivot = season_df.pivot_table(
                index=["season", "game_date", "team_id"],
                values=[c for c in season_df.columns if c not in ("season", "game_date", "team_id")],
                aggfunc="first",
            ).reset_index()
            # Flatten multi-level columns if any
            if isinstance(pivot.columns, pd.MultiIndex):
                pivot.columns = ["_".join(str(c) for c in col).strip("_") for col in pivot.columns]
            all_ratings.append(pivot)

        elapsed = time.time() - t0
        print(f"  [{i+1}/{total_seasons}] {season}: {len(game_dates)} dates, {len(season_games)} games ({elapsed:.1f}s)")

    if not all_ratings:
        return pd.DataFrame()

    result = pd.concat(all_ratings, ignore_index=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="Build Massey ratings parquet")
    parser.add_argument("--min-season", default=None, help="Skip seasons before this (e.g. 2015-16)")
    args = parser.parse_args()

    print("Building Massey ratings...")
    print(f"  Output: {OUTPUT_PATH}")

    t0 = time.time()
    print("\n  Loading game scores...")
    games = build_game_scores()
    print(f"  {len(games)} games loaded ({time.time()-t0:.1f}s)")

    print("\n  Computing pregame ratings (this takes a while)...")
    ratings = compute_pregame_ratings(games, min_season=args.min_season)

    if ratings.empty:
        print("  ERROR: No ratings computed")
        return

    print(f"\n  Ratings shape: {ratings.shape}")
    print(f"  Columns: {list(ratings.columns)}")
    print(f"  Date range: {ratings['game_date'].min()} to {ratings['game_date'].max()}")

    ratings.to_parquet(OUTPUT_PATH, index=False)
    print(f"\n  Saved to {OUTPUT_PATH}")
    print(f"  Total time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
