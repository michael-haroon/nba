"""
Load and normalize all NBA parquet data sources.

Handles dtype coercion (many columns stored as str that should be float64),
team identity mapping across NBA/ESPN systems, and merging box score categories.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import numpy as np


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
    df = pd.read_parquet(data_dir / "TeamMap.parquet")
    return df


def load_arenas(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    df = pd.read_csv(data_dir / "nba_arenas_geocoded.csv")
    return df


def load_game_ids(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    df = pd.read_parquet(data_dir / "NBAGameIDs.parquet")
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
            cat_df["GAME DATE"] = pd.to_datetime(cat_df["GAME DATE"])

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
    df = _coerce_numeric(df, exclude=set(JOIN_COLS) | {"season_type", "MIN_TRAD"})
    return df


def load_ratings_bpi(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    df = pd.read_parquet(data_dir / "BPI.parquet")
    df["snapshot_timestamp"] = pd.to_datetime(df["snapshot_timestamp"])
    return df


def load_ratings_sagarin(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    df = pd.read_parquet(data_dir / "SagarinRatings.parquet")
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


def load_game_summaries(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "GameSummaries.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_officials(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "GameOfficials.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["game_id", "official_id", "official_name"])
    return pd.read_parquet(path)


def load_quarter_scores(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "TeamQuarterScores.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["game_id", "team_id", "period_label", "period_score"])
    return pd.read_parquet(path)


def load_player_box_scores(data_dir: Path | None = None) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    path = data_dir / "PlayerStatus.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["game_id", "team_id", "player_id", "player_name", "roster_status", "dnp_comment"])
    return pd.read_parquet(path)


def load_all(data_dir: Path | None = None, season_types=("Regular", "Playoffs")) -> dict:
    """Load all data sources into a dict for the pipeline."""
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    return {
        "box_scores": load_box_scores(data_dir, season_types),
        "game_ids": load_game_ids(data_dir),
        "team_map": load_team_map(data_dir),
        "arenas": load_arenas(data_dir),
        "bpi": load_ratings_bpi(data_dir),
        "sagarin": load_ratings_sagarin(data_dir),
        "game_summaries": load_game_summaries(data_dir),
        "officials": load_officials(data_dir),
        "quarter_scores": load_quarter_scores(data_dir),
        "player_box_scores": load_player_box_scores(data_dir),
    }
