"""
Drop entirely-empty columns and rows from CRUDE* and Hustle* parquets.

Usage:
    python drop_empty.py            # dry run (default)
    python drop_empty.py --execute  # write changes to disk
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "drop_empty.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def process_file(path: Path, dry_run: bool) -> None:
    log.info(f"{'[DRY RUN] ' if dry_run else ''}Processing {path.name}")

    df = pd.read_parquet(path)
    orig_rows, orig_cols = df.shape

    # Entirely-empty columns: all values are NaN/None
    empty_cols = [c for c in df.columns if df[c].isna().all()]

    # Entirely-empty rows: all values in the row are NaN/None
    empty_rows_mask = df.isna().all(axis=1)
    empty_row_count = empty_rows_mask.sum()

    log.info(
        f"  {orig_rows} rows x {orig_cols} cols  |  "
        f"empty cols: {len(empty_cols)}  |  empty rows: {empty_row_count}"
    )

    if empty_cols:
        log.info(f"  Empty cols to drop: {empty_cols}")

    if len(empty_cols) == 0 and empty_row_count == 0:
        log.info(f"  Nothing to drop — skipping.")
        return

    if dry_run:
        log.info(
            f"  [DRY RUN] Would write {orig_rows - empty_row_count} rows x "
            f"{orig_cols - len(empty_cols)} cols"
        )
        return

    df = df.drop(columns=empty_cols)
    df = df[~empty_rows_mask]

    df.to_parquet(path, index=False)
    log.info(
        f"  Written: {len(df)} rows x {len(df.columns)} cols  "
        f"(dropped {empty_row_count} rows, {len(empty_cols)} cols)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes. Omit this flag to do a dry run (default).",
    )
    args = parser.parse_args()
    dry_run = not args.execute

    pattern = re.compile(r"^(CRUDE|Hustle).*\.parquet$")
    files = sorted(p for p in DATA_DIR.iterdir() if pattern.match(p.name))

    if not files:
        log.warning(f"No matching files found in {DATA_DIR}")
        return

    log.info(
        f"{'DRY RUN — no files will be modified' if dry_run else 'EXECUTE MODE — files will be modified'}"
    )
    log.info(f"Found {len(files)} file(s) to process")

    for f in files:
        process_file(f, dry_run)

    log.info("Done.")


if __name__ == "__main__":
    main()
