"""
Normalize all parquet files in data_curation/data/:
  1. Replace non-breaking spaces (\xa0) in column names with regular spaces.
  2. Drop rows that look like re-scraped headers (non-date values in date columns,
     non-numeric values in columns that should be numeric).

Usage:
    # Dry run (default) — logs what would change, modifies nothing:
    python -m data_curation.scripts.normalize_parquets

    # Apply changes:
    python -m data_curation.scripts.normalize_parquets --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import numpy as np


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Columns that should contain dates (across all our parquets)
DATE_COLUMNS = {"GAME DATE", "GAME_DATE", "as_of_date", "snapshot_timestamp", "game_date"}

# Columns that should never contain date-like or numeric values
# (used to detect header rows that leaked into data)
IDENTIFIER_COLUMNS = {"TEAM", "MATCH UP", "W/L", "team", "team_abbrev"}


def normalize_one(path: Path, apply: bool) -> dict:
    """
    Normalize a single parquet file. Returns a report dict.
    """
    report = {
        "file": path.name,
        "columns_renamed": [],
        "rows_dropped": 0,
        "total_rows": 0,
        "modified": False,
        "error": None,
    }

    try:
        df = pd.read_parquet(path)
    except Exception as e:
        report["error"] = str(e)[:120]
        return report

    report["total_rows"] = len(df)
    original_len = len(df)

    # --- Step 1: Fix non-breaking spaces in column names ---
    new_columns = [c.replace("\xa0", " ") for c in df.columns]
    renamed = [(old, new) for old, new in zip(df.columns, new_columns) if old != new]
    if renamed:
        report["columns_renamed"] = renamed
        report["modified"] = True
        df.columns = new_columns

    # --- Step 2: Drop header-leak rows ---
    # Strategy: if a file has a known date column, try to parse it.
    # Rows where the date column can't parse are header artifacts.
    rows_to_drop = pd.Series(False, index=df.index)

    for date_col in DATE_COLUMNS:
        if date_col not in df.columns:
            continue
        if df[date_col].dtype == object or str(df[date_col].dtype) == "large_string":
            parsed = pd.to_datetime(df[date_col], errors="coerce")
            bad_mask = parsed.isna() & df[date_col].notna()
            rows_to_drop |= bad_mask

    # Also check: if an identifier column (TEAM, W/L) contains what looks like
    # a numeric column header (e.g., "OREB%", "3PM"), that row is a header leak.
    for id_col in IDENTIFIER_COLUMNS:
        if id_col not in df.columns:
            continue
        if df[id_col].dtype == object or str(df[id_col].dtype) == "large_string":
            # Real team abbreviations are 2-4 uppercase letters (or team names).
            # Header leaks contain things like "OREB%", "AST/TO", numbers, etc.
            suspicious = df[id_col].str.contains(r"[%/]|\d{2,}", na=False)
            rows_to_drop |= suspicious

    n_dropped = rows_to_drop.sum()
    if n_dropped > 0:
        report["rows_dropped"] = int(n_dropped)
        report["modified"] = True
        # Collect sample of dropped rows for logging
        dropped_sample = df[rows_to_drop].head(5)
        report["dropped_sample"] = dropped_sample.to_dict("records")
        df = df[~rows_to_drop].reset_index(drop=True)

    # --- Step 3: Write if applying and something changed ---
    if apply and report["modified"]:
        df.to_parquet(path, index=False)

    return report


def main():
    parser = argparse.ArgumentParser(description="Normalize parquet files (dry run by default)")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"{'='*70}")
    print(f"  Parquet Normalization — {mode}")
    print(f"  Directory: {DATA_DIR}")
    print(f"{'='*70}\n")

    parquet_files = sorted(DATA_DIR.glob("*.parquet"))
    print(f"  Found {len(parquet_files)} parquet files\n")

    modified_count = 0
    total_rows_dropped = 0
    total_cols_renamed = 0

    for path in parquet_files:
        report = normalize_one(path, apply=args.apply)

        if report.get("error"):
            print(f"  {'─'*60}")
            print(f"  FILE: {report['file']}  *** UNREADABLE ***")
            print(f"    ERROR: {report['error']}")
            continue

        if not report["modified"]:
            continue

        modified_count += 1
        print(f"  {'─'*60}")
        print(f"  FILE: {report['file']}  ({report['total_rows']} rows)")

        if report["columns_renamed"]:
            total_cols_renamed += len(report["columns_renamed"])
            print(f"    COLUMNS RENAMED ({len(report['columns_renamed'])}):")
            for old, new in report["columns_renamed"]:
                print(f"      '{repr(old)}' → '{new}'")

        if report["rows_dropped"] > 0:
            total_rows_dropped += report["rows_dropped"]
            print(f"    ROWS DROPPED: {report['rows_dropped']}")
            if "dropped_sample" in report:
                print(f"    Sample of dropped rows (first 5):")
                for i, row in enumerate(report["dropped_sample"]):
                    # Show first 4 columns to keep output readable
                    items = list(row.items())[:4]
                    preview = ", ".join(f"{k}={v!r}" for k, v in items)
                    print(f"      [{i}] {preview}")

    print(f"\n{'='*70}")
    print(f"  SUMMARY ({mode})")
    print(f"    Files modified:    {modified_count}/{len(parquet_files)}")
    print(f"    Columns renamed:   {total_cols_renamed}")
    print(f"    Rows dropped:      {total_rows_dropped}")
    if not args.apply and modified_count > 0:
        print(f"\n  Run with --apply to write changes.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
