"""
backfill_game_id.py
-------------------
One-time migration: adds `game_id` column to all AdvBoxScores parquets
that currently lack it. Uses GameSummaries.game_code to map (date, team) -> game_id.

Usage:
    python data_curation/scripts/backfill_game_id.py [--dry-run]

This prevents the pandas NaN dedup bug where rows without game_id collapse
during upsert_parquet()'s drop_duplicates() call.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "backfill_game_id.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def build_game_id_lookup() -> pd.DataFrame:
    """Build a lookup table: (game_date, team_abbr) -> game_id.

    Uses GameSummaries.game_code format: 'YYYYMMDD/AWYHME' where AWY=away 3-letter,
    HME=home 3-letter. Each game produces two rows (one per team).
    """
    gs = pd.read_parquet(DATA_DIR / "GameSummaries.parquet")

    gs["_date"] = gs["game_code"].str[:8]
    gs["_away"] = gs["game_code"].str[9:12]
    gs["_home"] = gs["game_code"].str[12:15]
    gs["game_date"] = pd.to_datetime(gs["_date"], format="%Y%m%d")

    home_rows = gs[["game_id", "game_date", "_home"]].rename(columns={"_home": "team_abbr"})
    away_rows = gs[["game_id", "game_date", "_away"]].rename(columns={"_away": "team_abbr"})
    lookup = pd.concat([home_rows, away_rows], ignore_index=True)
    lookup = lookup.drop_duplicates(subset=["game_date", "team_abbr"])
    lookup["game_id"] = lookup["game_id"].astype(str).str.zfill(10)

    logger.info("Built lookup: %d (date, team) -> game_id mappings", len(lookup))
    return lookup


def backfill_file(path: Path, lookup: pd.DataFrame, dry_run: bool) -> None:
    """Add game_id column to a single AdvBoxScores parquet file."""
    df = pd.read_parquet(path)
    original_count = len(df)

    # Normalize non-breaking spaces in column names (some files have \xa0)
    df.columns = [c.replace("\xa0", " ") for c in df.columns]

    if "game_id" in df.columns and df["game_id"].notna().all():
        logger.info("SKIP %s: already has game_id for all %d rows", path.name, original_count)
        return

    # Drop header-leak rows (rows where GAME DATE is not a valid date)
    df["_game_date"] = pd.to_datetime(df["GAME DATE"], errors="coerce")
    bad_rows = df["_game_date"].isna()
    if bad_rows.any():
        logger.info("  Dropping %d header-leak rows from %s", bad_rows.sum(), path.name)
        df = df[~bad_rows].reset_index(drop=True)
        original_count = len(df)  # reset baseline after cleanup

    merged = df.merge(
        lookup[["game_date", "team_abbr", "game_id"]],
        left_on=["_game_date", "TEAM"],
        right_on=["game_date", "team_abbr"],
        how="left",
        suffixes=("_old", ""),
    )

    if "game_id_old" in merged.columns:
        merged["game_id"] = merged["game_id"].fillna(merged["game_id_old"])
        merged = merged.drop(columns=["game_id_old"])

    merged = merged.drop(columns=["_game_date", "game_date", "team_abbr"], errors="ignore")

    matched = merged["game_id"].notna().sum()
    unmatched = merged["game_id"].isna().sum()

    if len(merged) != original_count:
        logger.error(
            "ABORT %s: row count changed from %d to %d during merge (possible dup join). File unchanged.",
            path.name, original_count, len(merged),
        )
        return

    logger.info(
        "%s %s: %d/%d rows matched game_id (%d unmatched)",
        "DRY-RUN" if dry_run else "WRITE",
        path.name, matched, original_count, unmatched,
    )

    if not dry_run and matched > 0:
        merged.to_parquet(path, index=False)
        logger.info("  Saved %s (%d rows preserved)", path.name, len(merged))


def main():
    parser = argparse.ArgumentParser(description="Backfill game_id into AdvBoxScores parquets")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = parser.parse_args()

    logger.info("=== backfill_game_id start (dry_run=%s) ===", args.dry_run)

    lookup = build_game_id_lookup()

    targets = sorted(DATA_DIR.glob("AdvBoxScores*.parquet"))
    if not targets:
        logger.warning("No AdvBoxScores parquets found in %s", DATA_DIR)
        return

    for path in targets:
        backfill_file(path, lookup, dry_run=args.dry_run)

    logger.info("=== backfill_game_id complete ===")


if __name__ == "__main__":
    sys.exit(main() or 0)
