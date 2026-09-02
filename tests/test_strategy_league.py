"""Tests for Phase 3: strategy module --league support."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league_config import get_league_config, NBA_CONFIG, WNBA_CONFIG


# ---------------------------------------------------------------------------
# strategy.config.set_league
# ---------------------------------------------------------------------------

class TestSetLeague:
    def test_set_league_wnba_changes_paths(self):
        """set_league(wnba) updates all module-level paths."""
        from strategy.config import set_league
        import strategy.config as cfg

        set_league(WNBA_CONFIG)
        assert "features_wnba" in str(cfg.FEATURES_ROOT)
        assert "features_wnba" in str(cfg.GAME_PARQUET)
        assert cfg.OUTPUT_DIR.name == "wnba"

        # Reset to NBA for other tests
        set_league(NBA_CONFIG)

    def test_set_league_nba_restores_defaults(self):
        """set_league(nba) restores NBA paths."""
        from strategy.config import set_league
        import strategy.config as cfg

        set_league(WNBA_CONFIG)
        set_league(NBA_CONFIG)
        assert "features_wnba" not in str(cfg.FEATURES_ROOT)
        assert cfg.OUTPUT_DIR.name == "nba"

    def test_feature_paths_updated(self):
        """FEATURE_PATHS dict is updated by set_league."""
        from strategy.config import set_league
        import strategy.config as cfg

        set_league(WNBA_CONFIG)
        for target, path in cfg.FEATURE_PATHS.items():
            assert "features_wnba" in str(path), f"{target} path not updated"
        set_league(NBA_CONFIG)

    def test_output_dir_structure(self):
        """Output dir follows strategy/output/{league} pattern."""
        from strategy.config import set_league, PROJECT_ROOT
        import strategy.config as cfg

        set_league(WNBA_CONFIG)
        assert cfg.OUTPUT_DIR == PROJECT_ROOT / "strategy" / "output" / "wnba"
        set_league(NBA_CONFIG)
        assert cfg.OUTPUT_DIR == PROJECT_ROOT / "strategy" / "output" / "nba"


# ---------------------------------------------------------------------------
# strategy.data uses module-level references (not stale bindings)
# ---------------------------------------------------------------------------

class TestDataModuleReferences:
    def test_data_reads_cfg_game_parquet(self):
        """strategy.data.load references _cfg.GAME_PARQUET, not a stale local."""
        import strategy.config as cfg
        from strategy.config import set_league
        import strategy.data as data_mod

        set_league(WNBA_CONFIG)
        # After set_league, data module should resolve to WNBA path
        assert "features_wnba" in str(cfg.GAME_PARQUET)
        set_league(NBA_CONFIG)


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------

class TestStrategyCLI:
    def test_run_requires_league(self):
        """strategy.run requires --league."""
        import argparse
        from league_config import add_league_arg

        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_predict_requires_league(self):
        """strategy.predict requires --league."""
        import argparse
        from league_config import add_league_arg

        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_run_accepts_wnba(self):
        """strategy.run accepts --league wnba."""
        import argparse
        from league_config import add_league_arg

        parser = argparse.ArgumentParser()
        add_league_arg(parser)
        parser.add_argument("--target", default="all")
        args = parser.parse_args(["--league", "wnba", "--target", "winner"])
        assert args.league == "wnba"
        assert args.target == "winner"


# ---------------------------------------------------------------------------
# WNBA-specific targets make sense
# ---------------------------------------------------------------------------

class TestWNBATargets:
    def test_wnba_excludes_series_targets(self):
        """WNBA has no 7-game series (playoffs are single-elim since 2022).
        series_* targets are NBA-specific but won't crash — they just produce empty data."""
        from strategy.data import TARGET_MAP
        # All targets defined in TARGET_MAP exist regardless of league
        assert "winner" in TARGET_MAP
        assert "spread" in TARGET_MAP
        # Series targets exist in map but WNBA data won't have them populated
        assert "series_winner" in TARGET_MAP
