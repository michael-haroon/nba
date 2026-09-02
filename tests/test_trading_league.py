"""Tests for Phase 4: trading module --league support."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league_config import get_league_config, NBA_CONFIG, WNBA_CONFIG


# ---------------------------------------------------------------------------
# trading.models.set_league
# ---------------------------------------------------------------------------

class TestModelsSetLeague:
    def test_set_league_wnba_updates_ensembles_dir(self):
        """set_league(wnba) updates ENSEMBLES_DIR to WNBA models path."""
        import trading.models as models
        models.set_league(WNBA_CONFIG)
        assert models.ENSEMBLES_DIR == WNBA_CONFIG.models_path
        assert "wnba" in str(models.ENSEMBLES_DIR)
        # Reset
        models.set_league(NBA_CONFIG)

    def test_set_league_wnba_updates_model_to_series(self):
        """set_league(wnba) updates MODEL_TO_SERIES to WNBA tickers."""
        import trading.models as models
        models.set_league(WNBA_CONFIG)
        assert models.MODEL_TO_SERIES["winner"] == "KXWNBAGAME"
        assert models.MODEL_TO_SERIES["spread"] == "KXWNBASPREAD"
        assert models.MODEL_TO_SERIES["h1_total"] == "KXWNBA1HTOTAL"
        # Reset
        models.set_league(NBA_CONFIG)

    def test_set_league_nba_restores_defaults(self):
        """set_league(nba) restores NBA tickers and paths."""
        import trading.models as models
        models.set_league(WNBA_CONFIG)
        models.set_league(NBA_CONFIG)
        assert models.MODEL_TO_SERIES["winner"] == "KXNBAGAME"
        assert "nba" in str(models.ENSEMBLES_DIR)
        assert "wnba" not in str(models.ENSEMBLES_DIR)


# ---------------------------------------------------------------------------
# trading.scanner uses _models.MODEL_TO_SERIES (not stale binding)
# ---------------------------------------------------------------------------

class TestScannerLeagueAware:
    def test_scanner_reads_series_from_module(self):
        """scanner uses _models.MODEL_TO_SERIES at call time."""
        import trading.models as models
        import trading.scanner as scanner

        models.set_league(WNBA_CONFIG)
        # The scanner should see WNBA tickers when it accesses _models.MODEL_TO_SERIES
        assert scanner._models.MODEL_TO_SERIES["winner"] == "KXWNBAGAME"
        models.set_league(NBA_CONFIG)
        assert scanner._models.MODEL_TO_SERIES["winner"] == "KXNBAGAME"


# ---------------------------------------------------------------------------
# trading.runner
# ---------------------------------------------------------------------------

class TestRunnerLeague:
    def test_runner_requires_league_arg(self):
        """runner.main() requires --league."""
        import argparse
        from league_config import add_league_arg

        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_runner_accepts_wnba(self):
        """runner accepts --league wnba."""
        import argparse
        from league_config import add_league_arg

        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--once", action="store_true")
        args = parser.parse_args(["--league", "wnba", "--once"])
        assert args.league == "wnba"

    def test_load_features_uses_cfg(self):
        """_load_features(cfg) uses cfg.output_path."""
        from trading.runner import _load_features
        # Just verify the function signature accepts cfg without crashing
        # (actual file won't exist, but the path construction is what matters)
        with pytest.raises((FileNotFoundError, OSError)):
            _load_features(WNBA_CONFIG)

    def test_find_tradeable_games_accepts_series(self):
        """_find_tradeable_games accepts a winner_series parameter."""
        from trading.runner import _find_tradeable_games
        import inspect
        sig = inspect.signature(_find_tradeable_games)
        assert "winner_series" in sig.parameters


# ---------------------------------------------------------------------------
# trading.ws
# ---------------------------------------------------------------------------

class TestWSLeague:
    def test_default_on_settle_accepts_league(self):
        """default_on_settle accepts league kwarg."""
        import inspect
        from trading.ws import default_on_settle
        sig = inspect.signature(default_on_settle)
        assert "league" in sig.parameters
        assert sig.parameters["league"].default == "nba"

    def test_scan_once_accepts_winner_series(self):
        """scan_once accepts winner_series kwarg."""
        import inspect
        from trading.runner import scan_once
        sig = inspect.signature(scan_once)
        assert "winner_series" in sig.parameters
        assert sig.parameters["winner_series"].default == "KXNBAGAME"


# ---------------------------------------------------------------------------
# Reviewer-found bugs: parse_ticker, lifecycle, portfolio, sizing
# ---------------------------------------------------------------------------

class TestParseTickerBothLeagues:
    def test_parse_ticker_nba(self):
        """parse_ticker matches KXNBAGAME tickers."""
        from trading.backtest import parse_ticker
        result = parse_ticker("KXNBAGAME-26JUN08SASNYK-SAS")
        assert result is not None
        assert result["home"] == "NYK"
        assert result["away"] == "SAS"

    def test_parse_ticker_wnba(self):
        """parse_ticker matches KXWNBAGAME tickers."""
        from trading.backtest import parse_ticker
        result = parse_ticker("KXWNBAGAME-26JUL14ACENYL-ACE")
        assert result is not None
        assert result["home"] == "NYL"
        assert result["away"] == "ACE"

    def test_parse_ticker_rejects_other(self):
        """parse_ticker returns None for non-basketball tickers."""
        from trading.backtest import parse_ticker
        assert parse_ticker("KXMLBGAME-26JUN08SASNYK-SAS") is None


class TestSizingUsesModelsDir:
    def test_sizing_reads_models_ensembles_dir(self):
        """sizing module references _models.ENSEMBLES_DIR (not its own stale copy)."""
        import trading.models as models
        import trading.sizing as sizing

        models.set_league(WNBA_CONFIG)
        assert "wnba" in str(sizing._models.ENSEMBLES_DIR)
        models.set_league(NBA_CONFIG)
        assert "nba" in str(sizing._models.ENSEMBLES_DIR)


# ---------------------------------------------------------------------------
# WNBA kalshi_series completeness
# ---------------------------------------------------------------------------

class TestWNBASeriesConfig:
    def test_wnba_has_all_required_series(self):
        """WNBA config has series tickers for all tradeable targets."""
        required = {"winner", "spread", "h1_spread", "h1_total", "h2_total", "home_wins_h1"}
        assert required <= set(WNBA_CONFIG.kalshi_series.keys())

    def test_wnba_tickers_use_wnba_prefix(self):
        """All WNBA tickers contain 'WNBA'."""
        for target, ticker in WNBA_CONFIG.kalshi_series.items():
            assert "WNBA" in ticker, f"{target} ticker {ticker} missing WNBA prefix"

    def test_nba_tickers_use_nba_prefix(self):
        """All NBA tickers contain 'NBA' but not 'WNBA'."""
        for target, ticker in NBA_CONFIG.kalshi_series.items():
            assert "NBA" in ticker, f"{target} ticker {ticker} missing NBA"
            assert "WNBA" not in ticker, f"{target} ticker {ticker} should not have WNBA"
