"""
config.py — All parameters for the favorite-longshot bias research system.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
BACKTEST_DIR = ROOT / "backtest"
TRADES_CSV = BACKTEST_DIR / "logs" / "kalshi_nba_trades.csv"
TRADES_PARQUET = BACKTEST_DIR / "logs" / "kalshi_nba_trades.parquet"
TIPOFF_CACHE = BACKTEST_DIR / "logs" / "tipoff_times.json"
OUTPUT_DIR = BACKTEST_DIR / "output" / "flb"
SIGNALS_DIR = OUTPUT_DIR / "signals"
LOG_DIR = BACKTEST_DIR / "logs"

# Ensure output dirs exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

# ── AWS Mode ──────────────────────────────────────────────────────────────────

AWS_MODE = os.environ.get("FLB_AWS", "0") == "1"
S3_BUCKET = "nba-flb-signals"

# ── Time Bins (hours to tipoff) ───────────────────────────────────────────────

TIME_BINS = [
    (">48h", 48, 999),
    ("24-48h", 24, 48),
    ("6-24h", 6, 24),
    ("3-6h", 3, 6),
    ("1-3h", 1, 3),
    ("30m-1h", 0.5, 1),
    ("<30m", 0, 0.5),
]

# ── Price Bins (implied probability, 0-1 scale) ──────────────────────────────

PRICE_BINS = [
    ("0-20%", 0.0, 0.20),
    ("20-35%", 0.20, 0.35),
    ("35-50%", 0.35, 0.50),
    ("50-65%", 0.50, 0.65),
    ("65-80%", 0.65, 0.80),
    ("80-100%", 0.80, 1.0),
]

# ── Strategy Definitions ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Strategy:
    name: str
    time_range: tuple[float, float]   # (min_hours, max_hours) to tipoff
    price_range: tuple[float, float]  # (min_price, max_price) in 0-1 scale
    side: str                         # "no" = fade favorite, "yes" = back team
    min_edge_cents: float = 5.0       # minimum historical edge to trigger signal
    min_markets: int = 30             # minimum historical markets in that cell


STRATEGIES = [
    Strategy(
        name="fade_heavy_fav_early",
        time_range=(24, 999),
        price_range=(0.80, 1.0),
        side="no",
        min_edge_cents=8.0,
        min_markets=30,
    ),
    Strategy(
        name="fade_heavy_fav_mid",
        time_range=(6, 24),
        price_range=(0.80, 1.0),
        side="no",
        min_edge_cents=5.0,
        min_markets=10,
    ),
    Strategy(
        name="back_momentum_late",
        time_range=(0.5, 1.0),
        price_range=(0.50, 0.65),
        side="yes",
        min_edge_cents=8.0,
        min_markets=30,
    ),
    Strategy(
        name="fade_fav_70_early",
        time_range=(24, 999),
        price_range=(0.70, 0.80),
        side="no",
        min_edge_cents=5.0,
        min_markets=30,
    ),
    Strategy(
        name="back_underdog_late",
        time_range=(0.5, 1.0),
        price_range=(0.35, 0.50),
        side="yes",
        min_edge_cents=5.0,
        min_markets=30,
    ),
]

# ── Kalshi ────────────────────────────────────────────────────────────────────

SERIES_TICKER = "KXNBAGAME"
