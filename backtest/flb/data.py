"""
data.py — Load trades, compute hours_to_tipoff, build the edge lookup grid.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.flb.config import (
    ROOT, TRADES_CSV, TRADES_PARQUET, TIPOFF_CACHE, TIME_BINS, PRICE_BINS, Strategy,
)

log = logging.getLogger(__name__)

# ── .env loading ──────────────────────────────────────────────────────────────

_env_path = ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))


# ── Tipoff Time Cache ─────────────────────────────────────────────────────────

def fetch_tipoff_times() -> dict[str, str]:
    """Fetch occurrence_datetime for all settled KXNBAGAME markets. Cache to disk."""
    if TIPOFF_CACHE.exists():
        log.info(f"Loading cached tipoff times from {TIPOFF_CACHE}")
        return json.loads(TIPOFF_CACHE.read_text())

    log.info("Fetching tipoff times from Kalshi API...")
    sys.path.insert(0, str(ROOT))
    from backtest.kalshi_client import make_client

    client = make_client(env="prod")
    tipoff_map = {}

    cursor = None
    while True:
        params: dict = {"series_ticker": "KXNBAGAME", "status": "settled", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        resp = client.get_markets(**params)
        for m in resp.get("markets", []):
            ticker = m.get("ticker", "")
            occ = m.get("occurrence_datetime")
            if occ and ticker not in tipoff_map:
                tipoff_map[ticker] = occ
        cursor = resp.get("cursor")
        if not cursor or not resp.get("markets"):
            break

    TIPOFF_CACHE.write_text(json.dumps(tipoff_map, indent=2))
    log.info(f"Cached {len(tipoff_map)} tipoff times to {TIPOFF_CACHE}")
    return tipoff_map


# ── Load Trades ───────────────────────────────────────────────────────────────

def load_trades() -> pd.DataFrame:
    """Load trades from Parquet (fast) or fall back to CSV."""
    if TRADES_PARQUET.exists():
        log.info(f"Loading trades from {TRADES_PARQUET}...")
        df = pd.read_parquet(TRADES_PARQUET)
    elif TRADES_CSV.exists():
        log.info(f"Loading trades from {TRADES_CSV} (slow, consider converting to parquet)...")
        df = pd.read_csv(
            TRADES_CSV,
            dtype={"ticker": "category", "actual_win": "int8"},
        )
        df["trade_time"] = pd.to_datetime(df["trade_time"], format="ISO8601", utc=True)
        df["settlement_dt"] = pd.to_datetime(df["settlement_dt"], format="ISO8601", utc=True)
        df["yes_price"] = df["yes_price"].astype("float32")
        df["pct_elapsed"] = df["pct_elapsed"].astype("float32")
    else:
        raise FileNotFoundError(
            f"Neither {TRADES_PARQUET} nor {TRADES_CSV} found. Run backtest.longshot_bias first."
        )

    log.info(f"  Loaded {len(df):,} trades, {df['ticker'].nunique()} markets")
    return df


# ── Add Hours to Tipoff ──────────────────────────────────────────────────────

def add_hours_to_tipoff(df: pd.DataFrame, tipoff_map: dict[str, str]) -> pd.DataFrame:
    """Add hours_to_tipoff column using exact occurrence_datetime from API."""
    df = df.copy()
    df["hours_to_tipoff"] = np.nan

    tipoff_dt_map = {
        ticker: pd.to_datetime(occ, utc=True) for ticker, occ in tipoff_map.items()
    }

    for ticker, occ_dt in tipoff_dt_map.items():
        mask = df["ticker"] == ticker
        if mask.any():
            df.loc[mask, "hours_to_tipoff"] = (
                (occ_dt - df.loc[mask, "trade_time"]).dt.total_seconds() / 3600
            )

    matched = df["hours_to_tipoff"].notna().sum()
    log.info(f"  Tipoff timing matched: {matched:,} / {len(df):,} trades")
    return df


# ── Binning ───────────────────────────────────────────────────────────────────

def assign_time_bin(hours: float) -> str | None:
    """Map hours_to_tipoff to a named time bin."""
    for label, lo, hi in TIME_BINS:
        if lo <= hours < hi:
            return label
    return None


def assign_price_bin(price: float) -> str | None:
    """Map yes_price (0-1) to a named price bin."""
    for label, lo, hi in PRICE_BINS:
        if lo <= price < hi:
            return label
    return None


# ── Edge Grid ─────────────────────────────────────────────────────────────────

def build_edge_grid(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the calibration lookup table: time_bin × price_bin → edge metrics.
    Only uses pre-game trades (hours_to_tipoff > 0).
    """
    valid = df[(df["hours_to_tipoff"].notna()) & (df["hours_to_tipoff"] > 0)].copy()

    valid["time_bin"] = valid["hours_to_tipoff"].apply(assign_time_bin)
    valid["price_bin"] = valid["yes_price"].apply(assign_price_bin)
    valid = valid.dropna(subset=["time_bin", "price_bin"])

    grid = (
        valid.groupby(["time_bin", "price_bin"], observed=True)
        .agg(
            implied_prob=("yes_price", "mean"),
            actual_win_rate=("actual_win", "mean"),
            n_trades=("actual_win", "count"),
            n_markets=("ticker", "nunique"),
        )
        .reset_index()
    )
    grid["edge_cents"] = (grid["actual_win_rate"] - grid["implied_prob"]) * 100
    log.info(f"  Edge grid: {len(grid)} cells")
    return grid


def lookup_edge(grid: pd.DataFrame, hours_to_tipoff: float, price: float) -> dict:
    """Look up edge for a specific time/price. Returns dict with edge_cents, n_markets, etc."""
    time_bin = assign_time_bin(hours_to_tipoff)
    price_bin = assign_price_bin(price)

    if time_bin is None or price_bin is None:
        return {"edge_cents": 0.0, "n_trades": 0, "n_markets": 0,
                "implied_prob": price, "actual_win_rate": price}

    match = grid[(grid["time_bin"] == time_bin) & (grid["price_bin"] == price_bin)]
    if match.empty:
        return {"edge_cents": 0.0, "n_trades": 0, "n_markets": 0,
                "implied_prob": price, "actual_win_rate": price}

    row = match.iloc[0]
    return {
        "edge_cents": float(row["edge_cents"]),
        "n_trades": int(row["n_trades"]),
        "n_markets": int(row["n_markets"]),
        "implied_prob": float(row["implied_prob"]),
        "actual_win_rate": float(row["actual_win_rate"]),
    }


# ── Strategy Filtering ────────────────────────────────────────────────────────

def first_entry_per_market(df: pd.DataFrame, strategy: Strategy) -> pd.DataFrame:
    """
    For a given strategy, find the first qualifying trade in each market.
    Returns one row per market (for paper P&L calculation).
    """
    valid = df[df["hours_to_tipoff"].notna()].copy()

    time_lo, time_hi = strategy.time_range
    price_lo, price_hi = strategy.price_range

    mask = (
        (valid["hours_to_tipoff"] >= time_lo)
        & (valid["hours_to_tipoff"] < time_hi)
        & (valid["yes_price"] >= price_lo)
        & (valid["yes_price"] < price_hi)
    )
    qualifying = valid[mask]

    if qualifying.empty:
        return pd.DataFrame()

    entries = qualifying.sort_values("trade_time").groupby("ticker").first().reset_index()
    return entries
