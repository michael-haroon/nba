"""
Load and normalize all NBA parquet data sources.

Handles dtype coercion (many columns stored as str that should be float64),
team identity mapping across NBA/ESPN systems, and merging box score categories.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


DATA_DIR = Path(__file__).resolve().parents[2] / "data_curation" / "data"

BOX_SCORE_CATEGORIES = ("Trad", "Adv", "FourFactors", "Misc", "Scoring")
SEASON_TYPES = ("Regular", "Playoffs", "Pre")

JOIN_COLS = ["TEAM", "MATCH UP", "GAME DATE", "W/L"]


def _coerce_numeric(df: pd.DataFrame, exclude: set[str] | None = None) -> pd.DataFrame:
    """Convert string columns that should be numeric to float64."""
    if exclude is None:
        exclude = set()
    for col in df.columns:
        if col in exclude:
            continue
        if df[col].dtype == object:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() > 0.5 * df[col].notna().sum():
                df[col] = converted
    return df


def load_team_map(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "TeamMap.parquet"
    if not path.exists():
        # Fall back to NBA data dir (TeamMap is league-shared via nba_api)
        fallback = Path(__file__).resolve().parents[2] / "data_curation" / "data" / "TeamMap.parquet"
        if fallback.exists():
            logger.warning("[load_team_map] %s not found — using fallback from NBA data dir", path)
            return pd.read_parquet(fallback)
        logger.warning("[load_team_map] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    df = pd.read_parquet(path)
    return df


def load_arenas(data_dir: Path | None = None, arenas_file: str | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    fname = arenas_file or "nba_arenas_geocoded.csv"
    df = pd.read_csv(data_dir / fname)
    return df


def load_game_ids(data_dir: Path | None = None, game_ids_file: str | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    fname = game_ids_file or "NBAGameIDs.parquet"
    df = pd.read_parquet(data_dir / fname)
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    return df


def load_box_scores(
    data_dir: Path | None = None,
    season_types: tuple[str, ...] = ("Regular", "Playoffs"),
) -> pd.DataFrame:
    """
    Load and merge all box score categories for specified season types.

    Returns one DataFrame with all stats per team per game, with columns
    deduplicated across categories (joined on TEAM + MATCH UP + GAME DATE + W/L).
    """
    data_dir = data_dir or DATA_DIR
    frames = []

    for stype in season_types:
        merged = None
        for cat in BOX_SCORE_CATEGORIES:
            fname = f"AdvBoxScores{cat}{stype}.parquet"
            path = data_dir / fname
            if not path.exists():
                continue
            cat_df = pd.read_parquet(path)
            cat_df.columns = [c.replace("\xa0", " ") for c in cat_df.columns]
            cat_df["GAME DATE"] = pd.to_datetime(cat_df["GAME DATE"], format="mixed", errors="coerce")
            cat_df = cat_df.dropna(subset=["GAME DATE"])

            if cat == "Trad":
                cat_df = cat_df.rename(columns={"MIN": "MIN_TRAD"})
            else:
                cat_df = cat_df.drop(columns=["MIN"], errors="ignore")

            if "W/L" in cat_df.columns and cat != "Trad":
                pass

            if merged is None:
                merged = cat_df
            else:
                new_cols = [c for c in cat_df.columns if c not in merged.columns or c in JOIN_COLS]
                merged = merged.merge(
                    cat_df[new_cols],
                    on=JOIN_COLS,
                    how="left",
                )

        if merged is not None:
            merged["season_type"] = stype
            frames.append(merged)

    df = pd.concat(frames, ignore_index=True)
    df = _coerce_numeric(df, exclude=set(JOIN_COLS) | {"season_type", "MIN_TRAD", "game_id"})
    logger.info("[load_box_scores] loaded %d rows, %d cols | season_types=%s",
                df.shape[0], df.shape[1], list(season_types))
    top_null = df.select_dtypes(include="number").isna().mean().nlargest(5)
    logger.debug("[load_box_scores] top-5 null-rate cols: %s", top_null.round(3).to_dict())
    return df


def load_ratings_bpi(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "BPI.parquet"
    if not path.exists():
        logger.warning("[load_ratings_bpi] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["snapshot_timestamp"] = pd.to_datetime(df["snapshot_timestamp"])
    return df


def load_ratings_sagarin(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "SagarinRatings.parquet"
    if not path.exists():
        logger.warning("[load_ratings_sagarin] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


def load_game_summaries(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "GameSummaries.parquet"
    if not path.exists():
        logger.warning("[load_game_summaries] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_officials(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "GameOfficials.parquet"
    if not path.exists():
        logger.warning("[load_officials] %s not found — returning empty DataFrame", path)
        return pd.DataFrame(columns=["game_id", "official_id", "official_name"])
    return pd.read_parquet(path)


def load_quarter_scores(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "TeamQuarterScores.parquet"
    if not path.exists():
        logger.warning("[load_quarter_scores] %s not found — returning empty DataFrame", path)
        return pd.DataFrame(columns=["game_id", "team_id", "period_label", "period_score"])
    return pd.read_parquet(path)


def load_player_box_scores(data_dir: Path | None = None) -> pd.DataFrame:
    """Load player roster/status data from SummaryPlayers.parquet (syncer-updated).

    Maps SummaryPlayers schema to the columns expected by compute_roster_features:
    game_id, team_id, player_id, dnp_comment (non-null → inactive).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "SummaryPlayers.parquet"
    if not path.exists():
        logger.warning("[load_player_box_scores] %s not found — returning empty DataFrame", path)
        return pd.DataFrame(columns=["game_id", "team_id", "player_id", "player_name", "dnp_comment"])
    df = pd.read_parquet(path)
    result = pd.DataFrame({
        "game_id": df["gameId"],
        "team_id": df["teamId"],
        "player_id": df["personId"],
        "player_name": df["name"],
        "dnp_comment": df["inactive"].map({True: "INACTIVE", False: None}),
    })
    return result


def load_play_by_play(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "PlayByPlay.parquet"
    if not path.exists():
        logger.warning("[load_play_by_play] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_hustle_stats(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "HustlePlayerStats.parquet"
    if not path.exists():
        logger.warning("[load_hustle_stats] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_massey_ratings(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "MasseyRatings.parquet"
    if not path.exists():
        logger.warning("[load_massey_ratings] %s not found — returning empty DataFrame", path)
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def load_all(data_dir: Path | None = None, season_types=("Regular", "Playoffs"), cfg=None) -> dict:
    """Load all data sources into a dict for the pipeline.

    Args:
        cfg: Optional LeagueConfig for league-specific file names.
    """
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    arenas_file = cfg.arenas_file if cfg else None
    game_ids_file = cfg.game_ids_file if cfg else None
    data = {
        "box_scores": load_box_scores(data_dir, season_types),
        "game_ids": load_game_ids(data_dir, game_ids_file),
        "team_map": load_team_map(data_dir),
        "arenas": load_arenas(data_dir, arenas_file),
        "bpi": load_ratings_bpi(data_dir),
        "sagarin": load_ratings_sagarin(data_dir),
        "massey": load_massey_ratings(data_dir),
        "game_summaries": load_game_summaries(data_dir),
        "officials": load_officials(data_dir),
        "quarter_scores": load_quarter_scores(data_dir),
        "player_box_scores": load_player_box_scores(data_dir),
        "hustle": load_hustle_stats(data_dir),
        "play_by_play": load_play_by_play(data_dir),
    }
    logger.info(
        "[load_all] box_scores=%s  game_ids=%s  bpi=%s  sagarin=%s  massey=%s",
        data["box_scores"].shape, data["game_ids"].shape,
        data["bpi"].shape, data["sagarin"].shape, data["massey"].shape,
    )
    logger.info(
        "[load_all] quarter_scores=%s  officials=%s  player_box=%s  hustle=%s  pbp=%s",
        data["quarter_scores"].shape, data["officials"].shape,
        data["player_box_scores"].shape, data["hustle"].shape, data["play_by_play"].shape,
    )
    return data
