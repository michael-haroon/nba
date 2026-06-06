"""
Logging configuration for the NBA feature pipeline.

Usage (in entry-point scripts only):
    from feature_pipeline.logging_config import setup_pipeline_logger
    setup_pipeline_logger(log_dir, run_id)   # call once in main()

In all other modules:
    import logging
    logger = logging.getLogger(__name__)
    # Logs propagate automatically to the root 'feature_pipeline' logger.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def setup_pipeline_logger(log_dir: str | Path, run_id: str | None = None) -> logging.Logger:
    """Create the root 'feature_pipeline' logger writing to file + stderr."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"pipeline_{run_id}.log"

    logger = logging.getLogger("feature_pipeline")
    logger.setLevel(logging.DEBUG)

    # Clear handlers to avoid duplication on re-import (e.g. notebooks)
    if logger.handlers:
        logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.info("Pipeline logger initialised — log: %s", log_path)
    return logger


def log_step_summary(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    step_name: str,
    logger: logging.Logger,
) -> None:
    """Log shape delta and per-new-column null/range stats."""
    new_cols = [c for c in df_after.columns if c not in df_before.columns]
    logger.info(
        "[%s] shape %s -> %s | +%d cols",
        step_name, df_before.shape, df_after.shape, len(new_cols),
    )
    for col in new_cols:
        s = df_after[col]
        null_pct = s.isna().mean()
        if s.dtype.kind in "fi":
            logger.debug(
                "[%s]  %-50s null=%.1f%%  min=%.3g  med=%.3g  max=%.3g",
                step_name, col, 100 * null_pct,
                s.min(skipna=True), s.median(skipna=True), s.max(skipna=True),
            )
        elif null_pct > 0:
            logger.debug(
                "[%s]  %-50s null=%.1f%% (non-numeric)",
                step_name, col, 100 * null_pct,
            )


def log_value_stats(
    series: pd.Series,
    name: str,
    logger: logging.Logger,
    percentiles: tuple = (5, 50, 95),
) -> None:
    """Log P5/P50/P95 distribution for a numeric series."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        logger.debug("[stats]  %s: all NaN", name)
        return
    vals = np.percentile(s, percentiles)
    logger.debug(
        "[stats]  %-50s n=%d  P%d=%.3g  P%d=%.3g  P%d=%.3g",
        name, len(s),
        percentiles[0], vals[0],
        percentiles[1], vals[1],
        percentiles[2], vals[2],
    )
