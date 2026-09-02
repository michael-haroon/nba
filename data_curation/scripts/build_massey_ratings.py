"""
Build Massey ratings from game scores and save as parquet.

Computes pregame ratings for each team at each game date using only
games played BEFORE that date (no lookahead). Outputs a parquet with
one row per (season, game_date, team_id) with ratings from all 7 designs.

Output: data_curation/data/MasseyRatings.parquet
Columns: season, game_date, team_id, default_massey, default_massey_rank,
         location_adjusted_massey, ..., context_adjusted_massey, ...

Usage:
    python -m data_curation.scripts.build_massey_ratings --league nba
    python -m data_curation.scripts.build_massey_ratings --league wnba --min-season 2024
"""

from __future__ import annotations

import argparse
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from league_config import get_league_config, add_league_arg

from feature_pipeline.engineering.massey_ratings import (
    DEFAULT_MASSEY_DESIGNS,
    QUARTERS,
    MasseyDesign,
    build_massey_team_features,
    prepare_massey_context,
    schedule_is_connected,
    fit_massey,
    fit_massey_offdef,
    fit_colley,
    fit_massey_quarter,
    fit_colley_quarter,
    fit_wolfe,
    fit_wobus,
    fit_whitlock,
)
from feature_pipeline.engineering.data_loader import (
    load_box_scores,
    load_game_ids,
    load_game_summaries,
    load_team_map,
    load_arenas,
)
from feature_pipeline.engineering.game_builder import parse_home_away


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "MasseyRatings.parquet"


def _build_season_progress(gi: pd.DataFrame) -> pd.DataFrame:
    """Compute fraction of regular season elapsed per (season, game_date)."""
    reg = gi[gi["SEASON_TYPE_FILTER"] == "Regular Season"].copy()
    reg["GAME_DATE"] = pd.to_datetime(reg["GAME_DATE"])
    records = []
    for season, group in reg.groupby("SEASON_FILTER"):
        dates = sorted(group["GAME_DATE"].unique())
        total = len(dates)
        for i, d in enumerate(dates):
            records.append({"season": season, "game_date": d, "season_progress": (i + 1) / total})
    return pd.DataFrame(records)


def _estimate_arena_capacity(gs: pd.DataFrame, gi: pd.DataFrame) -> dict:
    """
    Estimate arena capacity as 95th percentile of attendance from
    Regular Season + Playoffs only (excludes preseason and attendance=0).
    """
    gi_slim = gi[["GAME_ID", "SEASON_TYPE_FILTER"]].copy()
    gi_slim["game_id"] = gi_slim["GAME_ID"].astype(str).str.zfill(10)
    merged = gs.merge(gi_slim[["game_id", "SEASON_TYPE_FILTER"]], on="game_id", how="left")
    valid = merged[
        merged["SEASON_TYPE_FILTER"].isin(["Regular Season", "Playoffs"]) &
        (merged["attendance"] > 0)
    ]
    return valid.groupby("arena_name")["attendance"].quantile(0.95).to_dict()


def build_game_scores(cfg=None, data_dir=None) -> pd.DataFrame:
    """Load box scores and construct the game-level input for Massey fitting."""
    _dir = data_dir or DATA_DIR
    bs = load_box_scores(_dir, season_types=("Regular", "Playoffs"))
    gi = load_game_ids(_dir, game_ids_file=cfg.game_ids_file if cfg else None)
    tm = load_team_map(_dir)

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

    # Ensure OFFRTG/DEFRTG are numeric
    for col in ("OFFRTG", "DEFRTG"):
        if col not in bs.columns:
            bs[col] = np.nan
        else:
            bs[col] = pd.to_numeric(bs[col], errors="coerce")

    # Ensure game_id is zero-padded string
    bs["game_id"] = bs["game_id"].astype(str).str.zfill(10)

    # Split home/away and merge on real game_id (exactly 2 rows per game_id)
    home_df = bs[bs["is_home"]][["game_id", "game_date", "team_id", "PTS", "season_type", "OFFRTG", "DEFRTG"]].copy()
    home_df.columns = ["game_id", "game_date", "home_team_id", "home_score", "season_type", "home_offrtg", "home_defrtg"]

    away_df = bs[~bs["is_home"]][["game_id", "team_id", "PTS", "OFFRTG", "DEFRTG"]].copy()
    away_df.columns = ["game_id", "away_team_id", "away_score", "away_offrtg", "away_defrtg"]

    games = home_df.merge(away_df, on="game_id", how="inner")
    games = games.drop_duplicates(subset=["game_id"])

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

    # --- Travel distance: haversine from away team's arena to home team's arena ---
    arenas = load_arenas(_dir, arenas_file=cfg.arenas_file if cfg else None)
    id_to_name = tm.drop_duplicates("TEAM_ID").set_index("TEAM_ID")["TEAM_NAME"].to_dict()
    arena_coords = arenas.set_index("team")[["lat", "lon"]].to_dict("index")

    home_names = games["home_team_id"].map(id_to_name)
    away_names = games["away_team_id"].map(id_to_name)

    def _haversine(lat1, lon1, lat2, lon2):
        R = 3959
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        return 2 * R * np.arcsin(np.sqrt(a))

    home_lat = home_names.map(lambda t: arena_coords.get(t, {}).get("lat", np.nan))
    home_lon = home_names.map(lambda t: arena_coords.get(t, {}).get("lon", np.nan))
    away_lat = away_names.map(lambda t: arena_coords.get(t, {}).get("lat", np.nan))
    away_lon = away_names.map(lambda t: arena_coords.get(t, {}).get("lon", np.nan))

    games["travel_distance_miles"] = _haversine(away_lat, away_lon, home_lat, home_lon)

    tz_home = home_lon / 15.0
    tz_away = away_lon / 15.0
    direction = tz_home - tz_away
    games["travel_direction"] = np.where(direction > 0.5, "east",
                                np.where(direction < -0.5, "west", "same"))

    # --- Crowd density from GameSummaries ---
    gs = load_game_summaries(_dir)
    if not gs.empty and "attendance" in gs.columns:
        gs["game_id"] = gs["game_id"].astype(str).str.zfill(10)

        arena_capacity = _estimate_arena_capacity(gs, gi)
        season_progress = _build_season_progress(gi)

        # Attach season_type from NBAGameIDs
        gi_type = gi[["GAME_ID", "SEASON_TYPE_FILTER"]].copy()
        gi_type["game_id"] = gi_type["GAME_ID"].astype(str).str.zfill(10)
        gs = gs.merge(gi_type[["game_id", "SEASON_TYPE_FILTER"]], on="game_id", how="left")

        # Merge attendance + arena_name + season_type onto games
        games = games.merge(
            gs[["game_id", "attendance", "arena_name", "SEASON_TYPE_FILTER"]],
            on="game_id",
            how="left",
        )

        # Merge season progress
        season_progress["game_date"] = pd.to_datetime(season_progress["game_date"])
        games = games.merge(season_progress, on=["season", "game_date"], how="left")

        # Compute capacity using user's rules:
        #   Playoffs + end-of-regular-season (>=90% through): capacity = attendance
        #   Everything else: p95 arena estimate
        arena_cap_est = games["arena_name"].map(arena_capacity)
        is_playoff = games["SEASON_TYPE_FILTER"] == "Playoffs"
        is_end_of_reg = (
            (games["SEASON_TYPE_FILTER"] == "Regular Season") &
            (games["season_progress"] >= 0.9)
        )
        games["capacity"] = np.where(
            is_playoff | is_end_of_reg,
            games["attendance"],
            arena_cap_est,
        )

        # Compute crowd_density (attendance=0 → NaN, unknown arena → NaN)
        valid_attendance = games["attendance"].replace(0, np.nan)
        valid_capacity = pd.to_numeric(games["capacity"], errors="coerce").replace(0, np.nan)
        games["crowd_density"] = (valid_attendance / valid_capacity).clip(lower=0.0, upper=1.5)

        n_valid = games["crowd_density"].notna().sum()
        print(f"  Crowd density: {n_valid}/{len(games)} games ({100*n_valid/len(games):.1f}% coverage)")

        # Clean up temp columns
        games = games.drop(columns=["arena_name", "SEASON_TYPE_FILTER", "season_progress"], errors="ignore")
    else:
        print("  WARNING: GameSummaries not available, crowd_density will be NaN")

    # Experience-based features require player-level career data
    print("  [skip] visitor_inexperience: need player experience data to implement")

    # --- Per-quarter scores from TeamQuarterScores ---
    quarter_path = _dir / "TeamQuarterScores.parquet"
    if quarter_path.exists():
        qs = pd.read_parquet(quarter_path)
        qs["period_score"] = pd.to_numeric(qs["period_score"], errors="coerce")
        qs["team_id"] = pd.to_numeric(qs["team_id"], errors="coerce").astype(int)
        qs["game_id"] = qs["game_id"].astype(str).str.zfill(10)

        qs_reg = qs[qs["period_label"].isin(["Q1", "Q2", "Q3", "Q4"])].copy()
        qs_reg["period_label"] = qs_reg["period_label"].str.lower() + "_score"
        qs_pivot = qs_reg.pivot_table(
            index=["game_id", "team_id"],
            columns="period_label",
            values="period_score",
            aggfunc="first",
        ).reset_index()
        qs_pivot.columns.name = None

        home_qs = qs_pivot.rename(columns={
            "team_id": "home_team_id",
            "q1_score": "home_q1_score", "q2_score": "home_q2_score",
            "q3_score": "home_q3_score", "q4_score": "home_q4_score",
        })
        games = games.merge(
            home_qs[["game_id", "home_team_id", "home_q1_score", "home_q2_score", "home_q3_score", "home_q4_score"]],
            on=["game_id", "home_team_id"], how="left",
        )

        away_qs = qs_pivot.rename(columns={
            "team_id": "away_team_id",
            "q1_score": "away_q1_score", "q2_score": "away_q2_score",
            "q3_score": "away_q3_score", "q4_score": "away_q4_score",
        })
        games = games.merge(
            away_qs[["game_id", "away_team_id", "away_q1_score", "away_q2_score", "away_q3_score", "away_q4_score"]],
            on=["game_id", "away_team_id"], how="left",
        )

    return games


def _fit_all_ratings_for_date(season_games, game_date, season, rating_kwargs=None):
    """
    Fit all rating systems for a single game_date using prior games.
    Returns a list of rating DataFrames (one per system/design).

    This function is the parallelization unit — called independently per date.
    rating_kwargs: dict with keys wolfe_home_bonus, wobus_sigma, margin_cap,
                   whitlock_win_bonus, whitlock_home_penalty (from league config).
    """
    rk = rating_kwargs or {}
    prior = season_games[season_games["game_date"] < game_date]
    if len(prior) < 10:
        return []

    date_ratings = []

    # Standard Massey designs
    for design in DEFAULT_MASSEY_DESIGNS:
        fit = fit_massey(prior, design, season=season,
                         as_of_date=game_date - pd.Timedelta(microseconds=1),
                         preview_rows=0)
        if not fit.ratings.empty:
            r = fit.ratings.copy()
            r["game_date"] = game_date
            date_ratings.append(r)

    # Colley
    colley_fit = fit_colley(prior, season=season,
                            as_of_date=game_date - pd.Timedelta(microseconds=1))
    if not colley_fit.ratings.empty:
        r = colley_fit.ratings.copy()
        r["game_date"] = game_date
        date_ratings.append(r)

    # Per-quarter Massey and Colley
    has_quarters = all(
        f"home_{q}_score" in prior.columns and prior[f"home_{q}_score"].notna().sum() > 5
        for q in QUARTERS
    )
    if has_quarters:
        for quarter in QUARTERS:
            for design in DEFAULT_MASSEY_DESIGNS:
                qfit = fit_massey_quarter(prior, design, quarter, season=season,
                                         as_of_date=game_date - pd.Timedelta(microseconds=1))
                if not qfit.ratings.empty:
                    qr = qfit.ratings.copy()
                    qr["game_date"] = game_date
                    date_ratings.append(qr)

            cqfit = fit_colley_quarter(prior, quarter, season=season,
                                       as_of_date=game_date - pd.Timedelta(microseconds=1))
            if not cqfit.ratings.empty:
                cqr = cqfit.ratings.copy()
                cqr["game_date"] = game_date
                date_ratings.append(cqr)

    # Alternative rating systems (Wolfe, Wobus, Whitlock)
    wolfe_fit = fit_wolfe(prior, season=season,
                          as_of_date=game_date - pd.Timedelta(microseconds=1),
                          home_advantage=rk.get("wolfe_home_bonus", 3.0))
    if not wolfe_fit.ratings.empty:
        wr = wolfe_fit.ratings.copy()
        wr["game_date"] = game_date
        date_ratings.append(wr)

    wobus_fit = fit_wobus(prior, season=season,
                          as_of_date=game_date - pd.Timedelta(microseconds=1),
                          sigma=rk.get("wobus_sigma", 13.0),
                          margin_cap=rk.get("margin_cap", 24))
    if not wobus_fit.ratings.empty:
        wbr = wobus_fit.ratings.copy()
        wbr["game_date"] = game_date
        date_ratings.append(wbr)

    whitlock_fit = fit_whitlock(prior, season=season,
                               as_of_date=game_date - pd.Timedelta(microseconds=1),
                               margin_cap=rk.get("margin_cap", 24),
                               win_bonus=rk.get("whitlock_win_bonus", 5.0),
                               home_penalty=rk.get("whitlock_home_penalty", 3.0))
    if not whitlock_fit.ratings.empty:
        wlr = whitlock_fit.ratings.copy()
        wlr["game_date"] = game_date
        date_ratings.append(wlr)

    # Per-quarter alternative ratings
    if has_quarters:
        for quarter in QUARTERS:
            h_col = f"home_{quarter}_score"
            a_col = f"away_{quarter}_score"
            q_prior = prior.dropna(subset=[h_col, a_col]).copy()
            if len(q_prior) >= 10:
                q_prior_q = q_prior.copy()
                q_prior_q["home_score"] = q_prior_q[h_col]
                q_prior_q["away_score"] = q_prior_q[a_col]

                wf_q = fit_wolfe(q_prior_q, season=season,
                                 as_of_date=game_date - pd.Timedelta(microseconds=1),
                                 home_advantage=rk.get("wolfe_home_bonus", 3.0))
                if not wf_q.ratings.empty:
                    r = wf_q.ratings.rename(columns={"wolfe": f"wolfe_{quarter}"})
                    r = r.drop(columns=["wolfe_rank"], errors="ignore")
                    r[f"wolfe_{quarter}_rank"] = r[f"wolfe_{quarter}"].rank(ascending=False, method="min").astype(int)
                    r["game_date"] = game_date
                    date_ratings.append(r)

                wb_q = fit_wobus(q_prior_q, season=season,
                                 as_of_date=game_date - pd.Timedelta(microseconds=1),
                                 sigma=rk.get("wobus_sigma", 13.0),
                                 margin_cap=rk.get("margin_cap", 24))
                if not wb_q.ratings.empty:
                    r = wb_q.ratings.rename(columns={"wobus": f"wobus_{quarter}"})
                    r = r.drop(columns=["wobus_rank"], errors="ignore")
                    r[f"wobus_{quarter}_rank"] = r[f"wobus_{quarter}"].rank(ascending=False, method="min").astype(int)
                    r["game_date"] = game_date
                    date_ratings.append(r)

                wl_q = fit_whitlock(q_prior_q, season=season,
                                    as_of_date=game_date - pd.Timedelta(microseconds=1),
                                    margin_cap=rk.get("margin_cap", 24),
                                    win_bonus=rk.get("whitlock_win_bonus", 5.0),
                                    home_penalty=rk.get("whitlock_home_penalty", 3.0))
                if not wl_q.ratings.empty:
                    r = wl_q.ratings.rename(columns={"whitlock": f"whitlock_{quarter}"})
                    r = r.drop(columns=["whitlock_rank"], errors="ignore")
                    r[f"whitlock_{quarter}_rank"] = r[f"whitlock_{quarter}"].rank(ascending=False, method="min").astype(int)
                    r["game_date"] = game_date
                    date_ratings.append(r)

    # Off/Def Massey splits
    has_offdef = (
        "home_offrtg" in prior.columns and
        prior["home_offrtg"].notna().sum() > 10
    )
    if has_offdef:
        for off_design in (DEFAULT_MASSEY_DESIGNS[0], DEFAULT_MASSEY_DESIGNS[1]):
            off_fit = fit_massey_offdef(
                prior, off_design,
                target_col_home="home_offrtg", target_col_away="away_offrtg",
                rating_name=f"off_{off_design.name}",
                season=season,
                as_of_date=game_date - pd.Timedelta(microseconds=1),
            )
            if not off_fit.ratings.empty:
                r = off_fit.ratings.copy()
                r["game_date"] = game_date
                date_ratings.append(r)

            def_fit = fit_massey_offdef(
                prior, off_design,
                target_col_home="home_defrtg", target_col_away="away_defrtg",
                rating_name=f"def_{off_design.name}",
                season=season,
                as_of_date=game_date - pd.Timedelta(microseconds=1),
            )
            if not def_fit.ratings.empty:
                r = def_fit.ratings.copy()
                r["game_date"] = game_date
                date_ratings.append(r)

    return date_ratings


def compute_pregame_ratings(games: pd.DataFrame, min_season: str | None = None, cfg=None) -> pd.DataFrame:
    """
    For each (season, game_date), fit all rating systems on prior games.
    Parallelized across game_dates within each season using joblib.
    """
    import os
    from joblib import Parallel, delayed

    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])

    if min_season:
        games = games[games["season"] >= min_season]

    games = prepare_massey_context(games)

    rating_kwargs = {}
    if cfg:
        rating_kwargs = {
            "wolfe_home_bonus": cfg.wolfe_home_bonus,
            "wobus_sigma": cfg.wobus_sigma,
            "margin_cap": cfg.margin_cap,
            "whitlock_win_bonus": cfg.whitlock_win_bonus,
            "whitlock_home_penalty": cfg.whitlock_home_penalty,
        }

    n_jobs = min(os.cpu_count() or 8, 96)
    print(f"  Parallelism: {n_jobs} workers")

    all_ratings = []
    seasons = sorted(games["season"].dropna().unique())
    total_seasons = len(seasons)

    for i, season in enumerate(seasons):
        t0 = time.time()
        season_games = games[games["season"] == season].sort_values("game_date").reset_index(drop=True)
        game_dates = sorted(season_games["game_date"].unique())

        # Filter dates with enough prior games and a connected schedule graph.
        # Early-season disconnected graphs yield unidentified cross-island levels.
        valid_dates = []
        skipped_disconnected = 0
        for d in game_dates:
            prior = season_games[season_games["game_date"] < d]
            if len(prior) < 10:
                continue
            if schedule_is_connected(prior):
                valid_dates.append(d)
            else:
                skipped_disconnected += 1

        # Parallel across dates within this season
        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_fit_all_ratings_for_date)(season_games, gd, season, rating_kwargs)
            for gd in valid_dates
        )

        # Flatten results
        season_ratings = [r for date_results in results for r in date_results]

        if season_ratings:
            season_df = pd.concat(season_ratings, ignore_index=True)
            # Pivot: one row per (season, game_date, team_id) with all design ratings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
                pivot = season_df.pivot_table(
                    index=["season", "game_date", "team_id"],
                    values=[c for c in season_df.columns if c not in ("season", "game_date", "team_id")],
                    aggfunc="first",
                ).reset_index().copy()
            # Flatten multi-level columns if any
            if isinstance(pivot.columns, pd.MultiIndex):
                pivot.columns = ["_".join(str(c) for c in col).strip("_") for col in pivot.columns]
            all_ratings.append(pivot)

        elapsed = time.time() - t0
        skip_note = (
            f", {skipped_disconnected} dates skipped (disconnected schedule)"
            if skipped_disconnected
            else ""
        )
        print(
            f"  [{i+1}/{total_seasons}] {season}: {len(valid_dates)} rating dates, "
            f"{len(season_games)} games{skip_note} ({elapsed:.1f}s)"
        )

    if not all_ratings:
        return pd.DataFrame()

    result = pd.concat(all_ratings, ignore_index=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="Build Massey ratings parquet")
    add_league_arg(parser)
    parser.add_argument("--min-season", default=None, help="Skip seasons before this (e.g. 2015-16)")
    parser.add_argument("--data-dir", default=None, help="Override data directory")
    args = parser.parse_args()

    cfg = get_league_config(args.league)

    global DATA_DIR, OUTPUT_PATH
    if args.data_dir:
        DATA_DIR = Path(args.data_dir)
    else:
        DATA_DIR = cfg.data_path
    OUTPUT_PATH = DATA_DIR / "MasseyRatings.parquet"

    print(f"Building Massey ratings [{cfg.league.upper()}]...")
    print(f"  Data dir: {DATA_DIR}")
    print(f"  Output: {OUTPUT_PATH}")

    t0 = time.time()
    print("\n  Loading game scores...")
    games = build_game_scores(cfg, data_dir=DATA_DIR)
    print(f"  {len(games)} games loaded ({time.time()-t0:.1f}s)")

    print("\n  Computing pregame ratings (this takes a while)...")
    ratings = compute_pregame_ratings(games, min_season=args.min_season, cfg=cfg)

    if ratings.empty:
        print("  ERROR: No ratings computed")
        return

    print(f"\n  Ratings shape: {ratings.shape}")
    print(f"  Columns: {list(ratings.columns)}")
    print(f"  Date range: {ratings['game_date'].min()} to {ratings['game_date'].max()}")

    # When --min-season is set, upsert: keep existing rows for prior seasons,
    # replace only the rows at or after min_season with freshly computed ratings.
    if args.min_season and OUTPUT_PATH.exists():
        existing = pd.read_parquet(OUTPUT_PATH)
        kept = existing[existing["season"] < args.min_season]
        ratings = pd.concat([kept, ratings], ignore_index=True)
        print(f"  Upserted: kept {len(kept)} rows from prior seasons, added {len(ratings)-len(kept)} new rows")

    ratings.to_parquet(OUTPUT_PATH, index=False)
    print(f"\n  Saved to {OUTPUT_PATH}")
    print(f"  Total time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
