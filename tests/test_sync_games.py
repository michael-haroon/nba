"""Tests for sync_games.py core logic (no network calls)."""
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_curation.scripts.sync_games import (
    _season_type_suffix,
    find_missing_games,
    upsert_parquet,
)
from league_config import get_league_config, NBA_CONFIG, WNBA_CONFIG


def _write(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# current_season (via LeagueConfig)
# ---------------------------------------------------------------------------

def test_current_season_nba_mid_season():
    assert NBA_CONFIG.current_season(date(2025, 1, 15)) == "2024-25"


def test_current_season_nba_new_season():
    assert NBA_CONFIG.current_season(date(2025, 9, 1)) == "2025-26"


def test_current_season_wnba():
    assert WNBA_CONFIG.current_season(date(2025, 7, 15)) == "2025"


# ---------------------------------------------------------------------------
# find_missing_games
# ---------------------------------------------------------------------------

def test_find_missing_games_returns_only_past_and_unsynced():
    yesterday = date.today() - timedelta(days=1)
    two_ago = date.today() - timedelta(days=2)
    tomorrow = date.today() + timedelta(days=1)

    game_ids = pd.DataFrame({
        "GAME_ID": [1, 2, 3, 4],
        "GAME_DATE": pd.to_datetime([two_ago, two_ago, yesterday, tomorrow]),
        "SEASON_FILTER": ["2024-25"] * 4,
        "SEASON_TYPE_FILTER": ["Regular Season"] * 4,
    })

    # Game 1 already synced via AdvBoxScoresTrad (moves watermark past test dates)
    adv_trad = pd.DataFrame({
        "TEAM": ["LAL", "BOS"],
        "MATCH UP": ["LAL vs. BOS", "BOS @ LAL"],
        "GAME DATE": [str(yesterday), str(yesterday)],
        "W/L": ["W", "L"],
        "game_id": ["0000000001", "0000000001"],
    })

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _write(data_dir / "NBAGameIDs.parquet", game_ids)
        _write(data_dir / "AdvBoxScoresTradRegular.parquet", adv_trad)

        missing = find_missing_games(data_dir, NBA_CONFIG)

    # Game 1 is in AdvBoxScoresTrad; game 4 is future; games 2 and 3 are missing
    assert set(missing) == {"0000000002", "0000000003"}


def test_find_missing_games_no_summary_file():
    yesterday = date.today() - timedelta(days=1)
    game_ids = pd.DataFrame({
        "GAME_ID": [10, 20],
        "GAME_DATE": pd.to_datetime([yesterday, yesterday]),
        "SEASON_FILTER": ["2024-25", "2024-25"],
        "SEASON_TYPE_FILTER": ["Regular Season", "Regular Season"],
    })

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _write(data_dir / "NBAGameIDs.parquet", game_ids)
        missing = find_missing_games(data_dir, NBA_CONFIG)

    assert set(missing) == {"0000000010", "0000000020"}


def test_find_missing_games_wnba():
    """WNBA uses WNBAGameIDs.parquet via cfg.game_ids_file."""
    yesterday = date.today() - timedelta(days=1)
    game_ids = pd.DataFrame({
        "GAME_ID": [1022500001, 1022500002],
        "GAME_DATE": pd.to_datetime([yesterday, yesterday]),
        "SEASON_FILTER": ["2025", "2025"],
        "SEASON_TYPE_FILTER": ["Regular Season", "Regular Season"],
    })

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _write(data_dir / "WNBAGameIDs.parquet", game_ids)
        missing = find_missing_games(data_dir, WNBA_CONFIG)

    assert set(missing) == {"1022500001", "1022500002"}


# ---------------------------------------------------------------------------
# upsert_parquet
# ---------------------------------------------------------------------------

def test_upsert_parquet_game_level_guard():
    """upsert_parquet uses game-level guards: rows for games already in file are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.parquet"

        df1 = pd.DataFrame({"game_id": ["001", "002"], "score": [100, 110]})
        df2 = pd.DataFrame({"game_id": ["002", "003"], "score": [115, 120]})  # 002 already exists

        upsert_parquet(path, df1, ["game_id"])
        upsert_parquet(path, df2, ["game_id"])

        result = pd.read_parquet(path)
        # game_id 002 already existed → only 003 is appended (game-level guard)
        assert len(result) == 3
        # 002 keeps its original score (not overwritten)
        assert result[result["game_id"] == "002"]["score"].iloc[0] == 110


def test_upsert_parquet_creates_new_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "new.parquet"
        df = pd.DataFrame({"game_id": ["001"], "score": [100]})
        added = upsert_parquet(path, df, ["game_id"])
        assert added == 1
        assert path.exists()


def test_upsert_parquet_empty_df_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.parquet"
        existing = pd.DataFrame({"game_id": ["001"]})
        _write(path, existing)

        added = upsert_parquet(path, pd.DataFrame(), ["game_id"])
        assert added == 0
        assert len(pd.read_parquet(path)) == 1


# ---------------------------------------------------------------------------
# _season_type_suffix
# ---------------------------------------------------------------------------

def test_season_type_suffix_routing():
    ids_df = pd.DataFrame({
        "GAME_ID": [1, 2, 3],
        "GAME_DATE": pd.to_datetime(["2025-01-01"] * 3),
        "SEASON_FILTER": ["2024-25"] * 3,
        "SEASON_TYPE_FILTER": ["Regular Season", "Playoffs", "Pre Season"],
    })

    assert _season_type_suffix("0000000001", ids_df) == "Regular"
    assert _season_type_suffix("0000000002", ids_df) == "Playoffs"
    assert _season_type_suffix("0000000003", ids_df) == "Pre"


def test_season_type_suffix_unknown_defaults_to_regular():
    ids_df = pd.DataFrame({
        "GAME_ID": [1],
        "GAME_DATE": pd.to_datetime(["2025-01-01"]),
        "SEASON_FILTER": ["2024-25"],
        "SEASON_TYPE_FILTER": ["Regular Season"],
    })
    assert _season_type_suffix("0000099999", ids_df) == "Regular"
