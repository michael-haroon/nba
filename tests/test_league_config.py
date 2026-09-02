"""Tests for league_config.py — league configuration module."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league_config import (
    get_league_config,
    add_league_arg,
    LeagueConfig,
    NBA_CONFIG,
    WNBA_CONFIG,
    PROJECT_ROOT,
)


# ---------------------------------------------------------------------------
# get_league_config
# ---------------------------------------------------------------------------

class TestGetLeagueConfig:
    def test_nba_returns_nba_config(self):
        cfg = get_league_config("nba")
        assert cfg is NBA_CONFIG
        assert cfg.league_id == "00"

    def test_wnba_returns_wnba_config(self):
        cfg = get_league_config("wnba")
        assert cfg is WNBA_CONFIG
        assert cfg.league_id == "10"

    def test_case_insensitive(self):
        assert get_league_config("NBA") is NBA_CONFIG
        assert get_league_config("WNBA") is WNBA_CONFIG
        assert get_league_config("Wnba") is WNBA_CONFIG

    def test_unknown_league_raises(self):
        with pytest.raises(ValueError, match="Unknown league"):
            get_league_config("mlb")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            get_league_config("")


# ---------------------------------------------------------------------------
# LeagueConfig.current_season
# ---------------------------------------------------------------------------

class TestCurrentSeason:
    def test_nba_split_format_mid_season(self):
        cfg = get_league_config("nba")
        assert cfg.current_season(date(2025, 1, 15)) == "2024-25"

    def test_nba_split_format_preseason(self):
        cfg = get_league_config("nba")
        assert cfg.current_season(date(2025, 10, 1)) == "2025-26"

    def test_nba_split_format_august(self):
        cfg = get_league_config("nba")
        assert cfg.current_season(date(2025, 8, 1)) == "2025-26"

    def test_wnba_calendar_format(self):
        cfg = get_league_config("wnba")
        assert cfg.current_season(date(2025, 7, 15)) == "2025"

    def test_wnba_calendar_format_offseason(self):
        cfg = get_league_config("wnba")
        assert cfg.current_season(date(2025, 1, 15)) == "2025"

    def test_wnba_calendar_format_december(self):
        cfg = get_league_config("wnba")
        assert cfg.current_season(date(2025, 12, 1)) == "2025"


# ---------------------------------------------------------------------------
# LeagueConfig.is_active
# ---------------------------------------------------------------------------

class TestIsActive:
    def test_nba_active_in_january(self):
        cfg = get_league_config("nba")
        assert cfg.is_active(date(2025, 1, 15)) is True

    def test_nba_active_in_october(self):
        cfg = get_league_config("nba")
        assert cfg.is_active(date(2025, 10, 1)) is True

    def test_nba_inactive_in_july(self):
        cfg = get_league_config("nba")
        assert cfg.is_active(date(2025, 7, 15)) is False

    def test_nba_inactive_in_august(self):
        cfg = get_league_config("nba")
        assert cfg.is_active(date(2025, 8, 15)) is False

    def test_wnba_active_in_july(self):
        cfg = get_league_config("wnba")
        assert cfg.is_active(date(2025, 7, 15)) is True

    def test_wnba_active_in_may(self):
        cfg = get_league_config("wnba")
        assert cfg.is_active(date(2025, 5, 1)) is True

    def test_wnba_inactive_in_january(self):
        cfg = get_league_config("wnba")
        assert cfg.is_active(date(2025, 1, 15)) is False

    def test_wnba_inactive_in_march(self):
        cfg = get_league_config("wnba")
        assert cfg.is_active(date(2025, 3, 15)) is False


# ---------------------------------------------------------------------------
# LeagueConfig paths
# ---------------------------------------------------------------------------

class TestPaths:
    def test_nba_data_path(self):
        cfg = get_league_config("nba")
        assert cfg.data_path == PROJECT_ROOT / "data_curation" / "data"

    def test_wnba_data_path(self):
        cfg = get_league_config("wnba")
        assert cfg.data_path == PROJECT_ROOT / "data_curation" / "data_wnba"

    def test_nba_output_path(self):
        cfg = get_league_config("nba")
        assert cfg.output_path == PROJECT_ROOT / "output" / "features"

    def test_wnba_output_path(self):
        cfg = get_league_config("wnba")
        assert cfg.output_path == PROJECT_ROOT / "output" / "features_wnba"

    def test_nba_models_path(self):
        cfg = get_league_config("nba")
        assert cfg.models_path == PROJECT_ROOT / "strategy" / "output" / "nba"

    def test_wnba_models_path(self):
        cfg = get_league_config("wnba")
        assert cfg.models_path == PROJECT_ROOT / "strategy" / "output" / "wnba"


# ---------------------------------------------------------------------------
# Domain constants differ between leagues
# ---------------------------------------------------------------------------

class TestDomainConstants:
    def test_wnba_smaller_pythagorean(self):
        nba = get_league_config("nba")
        wnba = get_league_config("wnba")
        assert wnba.pythagorean_exp < nba.pythagorean_exp

    def test_wnba_smaller_blowout_threshold(self):
        nba = get_league_config("nba")
        wnba = get_league_config("wnba")
        assert wnba.blowout_threshold < nba.blowout_threshold

    def test_wnba_shorter_rolling_windows(self):
        nba = get_league_config("nba")
        wnba = get_league_config("wnba")
        assert max(wnba.rolling_windows) < max(nba.rolling_windows)

    def test_wnba_no_hustle(self):
        assert get_league_config("wnba").has_hustle is False
        assert get_league_config("nba").has_hustle is True

    def test_wnba_no_external_ratings(self):
        wnba = get_league_config("wnba")
        assert wnba.has_bpi is False
        assert wnba.has_sagarin is False


# ---------------------------------------------------------------------------
# Kalshi series tickers
# ---------------------------------------------------------------------------

class TestKalshiSeries:
    def test_nba_has_all_expected_series(self):
        cfg = get_league_config("nba")
        assert "winner" in cfg.kalshi_series
        assert cfg.kalshi_series["winner"] == "KXNBAGAME"

    def test_wnba_has_all_expected_series(self):
        cfg = get_league_config("wnba")
        assert "winner" in cfg.kalshi_series
        assert cfg.kalshi_series["winner"] == "KXWNBAGAME"

    def test_nba_wnba_tickers_differ(self):
        nba = get_league_config("nba")
        wnba = get_league_config("wnba")
        for key in nba.kalshi_series:
            if key in wnba.kalshi_series:
                assert nba.kalshi_series[key] != wnba.kalshi_series[key]


# ---------------------------------------------------------------------------
# add_league_arg
# ---------------------------------------------------------------------------

class TestAddLeagueArg:
    def test_adds_required_argument(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        # Should fail without --league
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_accepts_nba(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        args = parser.parse_args(["--league", "nba"])
        assert args.league == "nba"

    def test_accepts_wnba(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        args = parser.parse_args(["--league", "wnba"])
        assert args.league == "wnba"

    def test_rejects_invalid_league(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        with pytest.raises(SystemExit):
            parser.parse_args(["--league", "mlb"])


# ---------------------------------------------------------------------------
# S3 prefix
# ---------------------------------------------------------------------------

class TestS3:
    def test_nba_s3_prefix(self):
        cfg = get_league_config("nba")
        assert cfg.s3_prefix == "nba/data_curation/data"

    def test_wnba_s3_prefix(self):
        cfg = get_league_config("wnba")
        assert cfg.s3_prefix == "nba/data_curation/data_wnba"
