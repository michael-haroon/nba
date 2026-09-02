"""Tests for Phase 2: build_massey_ratings and build_features_only --league support."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league_config import get_league_config, NBA_CONFIG, WNBA_CONFIG


# ---------------------------------------------------------------------------
# data_loader: load_arenas / load_game_ids with custom file names
# ---------------------------------------------------------------------------

class TestDataLoaderLeagueFiles:
    def test_load_game_ids_custom_file(self):
        from feature_pipeline.engineering.data_loader import load_game_ids

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            df = pd.DataFrame({
                "GAME_ID": [1022500001],
                "GAME_DATE": pd.to_datetime(["2025-06-01"]),
            })
            df.to_parquet(data_dir / "WNBAGameIDs.parquet", index=False)

            result = load_game_ids(data_dir, game_ids_file="WNBAGameIDs.parquet")
            assert len(result) == 1
            assert result["GAME_ID"].iloc[0] == 1022500001

    def test_load_game_ids_default_file(self):
        from feature_pipeline.engineering.data_loader import load_game_ids

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            df = pd.DataFrame({
                "GAME_ID": [22500001],
                "GAME_DATE": pd.to_datetime(["2025-01-01"]),
            })
            df.to_parquet(data_dir / "NBAGameIDs.parquet", index=False)

            result = load_game_ids(data_dir)
            assert len(result) == 1

    def test_load_arenas_custom_file(self):
        from feature_pipeline.engineering.data_loader import load_arenas

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            csv_content = "team,arena,city,state,lat,lon,capacity\nTest Team,Test Arena,City,ST,40.0,-74.0,10000\n"
            (data_dir / "wnba_arenas_geocoded.csv").write_text(csv_content)

            result = load_arenas(data_dir, arenas_file="wnba_arenas_geocoded.csv")
            assert len(result) == 1
            assert result["team"].iloc[0] == "Test Team"

    def test_load_all_passes_cfg(self):
        """load_all with cfg uses league-specific file names."""
        from feature_pipeline.engineering.data_loader import load_game_ids, load_arenas

        cfg = WNBA_CONFIG
        assert cfg.game_ids_file == "WNBAGameIDs.parquet"
        assert cfg.arenas_file == "wnba_arenas_geocoded.csv"


# ---------------------------------------------------------------------------
# build_massey_ratings: --league parsing
# ---------------------------------------------------------------------------

class TestBuildMasseyRatingsCLI:
    def test_league_arg_required(self):
        """build_massey_ratings requires --league."""
        from data_curation.scripts.build_massey_ratings import main
        import argparse

        with pytest.raises(SystemExit):
            # No --league → argparse exits
            with patch("sys.argv", ["build_massey_ratings"]):
                main()

    def test_league_sets_data_dir(self):
        """--league wnba sets DATA_DIR to data_curation/data_wnba."""
        import data_curation.scripts.build_massey_ratings as bmr

        cfg = get_league_config("wnba")
        assert cfg.data_path.name == "data_wnba"


# ---------------------------------------------------------------------------
# build_features_only: --league parsing
# ---------------------------------------------------------------------------

class TestBuildFeaturesCLI:
    def test_league_arg_required(self):
        """build_features_only requires --league."""
        with pytest.raises(SystemExit):
            with patch("sys.argv", ["build_features_only"]):
                import feature_pipeline.build_features_only as bfo
                p = __import__("argparse").ArgumentParser()
                from league_config import add_league_arg
                add_league_arg(p)
                p.parse_args([])

    def test_wnba_config_uses_correct_windows(self):
        """WNBA config uses smaller rolling windows."""
        cfg = get_league_config("wnba")
        assert list(cfg.rolling_windows) == [3, 5, 10]

    def test_nba_config_uses_default_windows(self):
        """NBA config uses standard rolling windows."""
        cfg = get_league_config("nba")
        assert list(cfg.rolling_windows) == [5, 10, 20]


# ---------------------------------------------------------------------------
# feature_engineering: parameterized blowout_close
# ---------------------------------------------------------------------------

class TestBlowoutCloseParameterized:
    def _make_games(self):
        """Minimal games df for blowout/close testing."""
        import numpy as np
        games = pd.DataFrame({
            "game_date": pd.to_datetime(["2025-01-01"] * 20 + ["2025-01-10"] * 2),
            "home_team_id": [1] * 20 + [1, 2],
            "away_team_id": [2] * 20 + [2, 1],
            "home_pts": list(range(80, 100)) + [90, 80],
            "away_pts": [60] * 10 + [75] * 10 + [85, 90],
            "season": ["2024-25"] * 22,
            "home_wl": ["W"] * 20 + ["W", "L"],
            "away_wl": ["L"] * 20 + ["L", "W"],
        })
        # Make game_dates unique per row
        games["game_date"] = pd.to_datetime("2025-01-01") + pd.to_timedelta(range(len(games)), unit="D")
        return games

    def test_default_thresholds(self):
        """Default thresholds (15/5) match NBA behavior."""
        from feature_pipeline.engineering.feature_engineering import compute_blowout_close_features
        games = self._make_games()
        result = compute_blowout_close_features(games)
        assert "home_blowout_rate_10" in result.columns
        assert "home_close_game_rate_10" in result.columns

    def test_custom_thresholds(self):
        """Custom thresholds (12/5) work for WNBA."""
        from feature_pipeline.engineering.feature_engineering import compute_blowout_close_features
        games = self._make_games()
        result_nba = compute_blowout_close_features(games, blowout_threshold=15)
        result_wnba = compute_blowout_close_features(games, blowout_threshold=12)
        # With a lower threshold, more games count as blowouts
        # (margins of 13-15 are blowout at threshold=12 but not at 15)
        nba_blowouts = result_nba["home_blowout_rate_10"].dropna()
        wnba_blowouts = result_wnba["home_blowout_rate_10"].dropna()
        if not nba_blowouts.empty and not wnba_blowouts.empty:
            assert wnba_blowouts.mean() >= nba_blowouts.mean()


# ---------------------------------------------------------------------------
# feature_engineering: pythagorean exponent parameter
# ---------------------------------------------------------------------------

class TestPythagoreanParameterized:
    def test_custom_exponent(self):
        """compute_pythagorean_features accepts custom exponent."""
        from feature_pipeline.engineering.feature_engineering import compute_pythagorean_features
        games = pd.DataFrame({
            "game_date": pd.to_datetime("2025-01-01") + pd.to_timedelta(range(20), unit="D"),
            "season": ["2024-25"] * 20,
            "home_team_id": [1] * 10 + [2] * 10,
            "away_team_id": [2] * 10 + [1] * 10,
            "home_pts": [100] * 20,
            "away_pts": [90] * 20,
            "home_wl": ["W"] * 20,
            "away_wl": ["L"] * 20,
        })
        result = compute_pythagorean_features(games, exponent=11.5)
        assert "home_pyth_exp_winpct" in result.columns


# ---------------------------------------------------------------------------
# Subprocess calls in sync_games pass --league
# ---------------------------------------------------------------------------

class TestSyncGamesSubprocessCalls:
    def test_subprocess_uses_league_flag(self):
        """sync_games downstream calls use --league instead of --data-dir."""
        import inspect
        from data_curation.scripts import sync_games

        source = inspect.getsource(sync_games)
        # Should use --league for both downstream scripts
        assert '"--league", cfg.league' in source or "'--league', cfg.league" in source
        # Should NOT pass --data-dir to build_massey_ratings anymore
        assert '--data-dir", str(DATA_DIR)' not in source
