"""
sync_scheduler.py
-----------------
Season-aware wrapper for sync_games.py. Called by launchd daily.
Runs sync only during NBA season (Oct-Jun), skips offseason (Jul-Sep).

Also supports --check-schedule to detect postponed/rescheduled games weekly.

Usage:
    python data_curation/scripts/sync_scheduler.py
    python data_curation/scripts/sync_scheduler.py --check-schedule
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "sync_scheduler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _current_season() -> str:
    d = date.today()
    year = d.year if d.month >= 8 else d.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


def is_nba_active() -> bool:
    """NBA season runs Oct-June. Offseason is Jul-Sep."""
    return date.today().month >= 10 or date.today().month <= 6


def run_sync() -> None:
    """Run the main sync pipeline."""
    season = _current_season()
    logger.info("Running sync for season %s", season)
    result = subprocess.run(
        [sys.executable, "data_curation/scripts/sync_games.py", "--season", season, "--workers", "2"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("sync_games.py failed:\n%s", result.stderr[-2000:] if result.stderr else "no stderr")
    else:
        logger.info("sync_games.py completed successfully")


def check_schedule() -> None:
    """Check NBA schedule for postponements and newly added games."""
    from nba_api.stats.endpoints import leaguegamefinder

    season = _current_season()
    logger.info("Checking schedule for %s...", season)

    ids_path = DATA_DIR / "NBAGameIDs.parquet"
    if not ids_path.exists():
        logger.error("NBAGameIDs.parquet not found")
        return

    local_ids = pd.read_parquet(ids_path)
    local_game_ids = set(local_ids["GAME_ID"].astype(str))

    # Fetch current schedule from API
    api_game_ids = set()
    for season_type in ("Regular Season", "Playoffs", "Pre Season"):
        try:
            gf = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                league_id_nullable="00",
                season_type_nullable=season_type,
            )
            df = gf.get_data_frames()[0]
            if not df.empty:
                api_game_ids |= set(df["GAME_ID"].astype(str))
            time.sleep(1.0)
        except Exception as e:
            logger.warning("Failed to fetch %s schedule: %s", season_type, e)

    if not api_game_ids:
        logger.warning("No games fetched from API — network issue?")
        return

    new_games = api_game_ids - local_game_ids
    removed_games = local_game_ids - api_game_ids

    if new_games:
        logger.info("NEW games found in schedule: %d", len(new_games))
        for gid in sorted(new_games)[:10]:
            logger.info("  + %s", gid)

    if removed_games:
        logger.warning("Games in local but NOT in API schedule (possibly cancelled): %d", len(removed_games))
        for gid in sorted(removed_games)[:10]:
            logger.warning("  - %s", gid)

    if not new_games and not removed_games:
        logger.info("Schedule is in sync. No changes detected.")


def main():
    parser = argparse.ArgumentParser(description="NBA sync scheduler")
    parser.add_argument("--check-schedule", action="store_true", help="Check for schedule changes")
    parser.add_argument("--force", action="store_true", help="Run even during offseason")
    args = parser.parse_args()

    if args.check_schedule:
        check_schedule()
        return

    if not is_nba_active() and not args.force:
        logger.info("Offseason (Jul-Sep) — skipping sync. Use --force to override.")
        return

    run_sync()


if __name__ == "__main__":
    main()
