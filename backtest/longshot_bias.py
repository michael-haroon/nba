"""
longshot_bias.py
----------------
In-game calibration analysis for Kalshi NBA winner markets.

Key question: When the market says 75% for team A, do they actually win 75%
of the time? Or is there a longshot-favorite bias where high-probability
outcomes are MORE certain than priced, and longshots LESS likely?

Approach:
  1. Fetch all settled KXNBAGAME markets and their outcomes
  2. For each market, fetch the full trade tape (every transaction)
  3. Tag each trade with: implied probability, time elapsed in market life
  4. Bin trades by probability bucket → compute actual win rate per bucket
  5. Cross-cut by time-remaining bucket (early, mid, late game)
  6. Apply recency weighting to test if bias has changed recently

Run:
    conda run -n pred python -m backtest.longshot_bias
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_env_path = ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

from backtest.kalshi_client import make_client

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "longshot_bias.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ── Step 1: Fetch all settled markets ─────────────────────────────────────────

def fetch_all_settled_markets(client) -> list[dict]:
    """Paginate all settled KXNBAGAME markets."""
    markets = []
    cursor = None
    while True:
        params: dict = {"series_ticker": "KXNBAGAME", "status": "settled", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        resp = client.get_markets(**params)
        page = resp.get("markets", [])
        markets.extend(page)
        log.info(f"  Markets page: {len(page)} (total: {len(markets)})")
        cursor = resp.get("cursor")
        if not cursor or not page:
            break
    return markets


# ── Step 2: Fetch full trade tape for a market ────────────────────────────────

def fetch_trades(client, ticker: str) -> list[dict]:
    """Paginate all trades for a single market ticker. Uses regular endpoint."""
    trades = []
    cursor = None
    while True:
        params: dict = {"ticker": ticker, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        resp = client.get("/markets/trades", params=params)
        page = resp.get("trades", [])
        trades.extend(page)
        cursor = resp.get("cursor")
        if not cursor or not page:
            break
    return trades


# ── Step 3: Build trade-level DataFrame ───────────────────────────────────────

def build_trade_df(markets: list[dict], client) -> pd.DataFrame:
    """
    For each market, fetch trades and tag each trade with:
      - yes_price (implied probability)
      - actual_win (did the 'yes' team actually win?)
      - pct_market_elapsed (0=market open, 1=market close)
      - settlement_dt (for recency weighting)
    """
    all_rows = []
    n_markets = len(markets)

    for i, m in enumerate(markets):
        ticker = m.get("ticker", "")
        result = m.get("result", "")
        if result not in ("yes", "no"):
            continue

        actual_win = 1 if result == "yes" else 0

        open_time = m.get("open_time")
        close_time = m.get("close_time")
        settlement_ts = m.get("settlement_ts", "")

        if not open_time or not close_time:
            continue

        open_dt = pd.to_datetime(open_time, utc=True)
        close_dt = pd.to_datetime(close_time, utc=True)
        market_duration = (close_dt - open_dt).total_seconds()

        if market_duration <= 0:
            continue

        # Fetch trades
        trades = fetch_trades(client, ticker)
        if not trades:
            continue

        for t in trades:
            yes_price = float(t.get("yes_price_dollars", 0))
            if yes_price <= 0.01 or yes_price >= 0.99:
                continue

            trade_dt = pd.to_datetime(t["created_time"], utc=True)
            elapsed = (trade_dt - open_dt).total_seconds()
            pct_elapsed = min(max(elapsed / market_duration, 0.0), 1.0)

            all_rows.append({
                "ticker": ticker,
                "yes_price": yes_price,
                "actual_win": actual_win,
                "pct_elapsed": pct_elapsed,
                "trade_time": trade_dt,
                "settlement_ts": settlement_ts,
            })

        if (i + 1) % 20 == 0:
            log.info(f"  Processed {i+1}/{n_markets} markets ({len(all_rows)} trades so far)")

        # Rate limit: be gentle
        time.sleep(0.05)

    log.info(f"  Total trades collected: {len(all_rows)} from {n_markets} markets")
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["settlement_dt"] = pd.to_datetime(df["settlement_ts"], utc=True, errors="coerce")
    return df


# ── Step 4: Calibration by probability bucket ─────────────────────────────────

def calibration_by_prob(df: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """
    Bin all trades by yes_price (implied probability).
    For each bin: what fraction of the time did the team actually win?
    Perfect calibration: actual_win_rate == implied_prob in every bin.
    """
    df = df.copy()
    edges = np.linspace(0, 1, n_bins + 1)
    df["prob_bin"] = pd.cut(df["yes_price"], bins=edges)

    result = (
        df.groupby("prob_bin", observed=True)
        .agg(
            implied_prob_avg=("yes_price", "mean"),
            actual_win_rate=("actual_win", "mean"),
            n_trades=("actual_win", "count"),
            n_unique_markets=("ticker", "nunique"),
        )
        .reset_index()
    )
    result["bias"] = result["actual_win_rate"] - result["implied_prob_avg"]
    return result


# ── Step 5: Calibration by time remaining ─────────────────────────────────────

TIME_BUCKETS = [
    ("early (0-33%)", 0.0, 0.33),
    ("mid (33-66%)", 0.33, 0.66),
    ("late (66-100%)", 0.66, 1.0),
]


def calibration_by_time_and_prob(df: pd.DataFrame, n_prob_bins: int = 5) -> pd.DataFrame:
    """
    Cross-cut: for each time bucket × probability bucket, what is the actual win rate?
    This shows whether late-game prices are more accurate than early-game prices.
    """
    df = df.copy()
    edges = np.linspace(0, 1, n_prob_bins + 1)
    df["prob_bin"] = pd.cut(df["yes_price"], bins=edges)

    rows = []
    for label, lo, hi in TIME_BUCKETS:
        subset = df[(df["pct_elapsed"] >= lo) & (df["pct_elapsed"] < hi)]
        if subset.empty:
            continue
        grouped = (
            subset.groupby("prob_bin", observed=True)
            .agg(
                implied_prob_avg=("yes_price", "mean"),
                actual_win_rate=("actual_win", "mean"),
                n_trades=("actual_win", "count"),
            )
            .reset_index()
        )
        grouped["time_bucket"] = label
        grouped["bias"] = grouped["actual_win_rate"] - grouped["implied_prob_avg"]
        rows.append(grouped)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ── Step 6: Recency-weighted calibration ──────────────────────────────────────

def calibration_recency_weighted(df: pd.DataFrame, half_life_days: int = 90,
                                  n_bins: int = 10) -> pd.DataFrame:
    """
    Same as calibration_by_prob but weights recent games more heavily.
    """
    df = df.copy()
    now = pd.Timestamp.now(tz="UTC")
    df["days_old"] = (now - df["settlement_dt"]).dt.total_seconds() / 86400
    df["weight"] = np.exp(-df["days_old"] / half_life_days)

    edges = np.linspace(0, 1, n_bins + 1)
    df["prob_bin"] = pd.cut(df["yes_price"], bins=edges)

    rows = []
    for bin_label, group in df.groupby("prob_bin", observed=True):
        if group.empty:
            continue
        w = group["weight"]
        total_w = w.sum()
        w_implied = (group["yes_price"] * w).sum() / total_w
        w_actual = (group["actual_win"] * w).sum() / total_w
        rows.append({
            "prob_bin": bin_label,
            "implied_prob_avg": w_implied,
            "actual_win_rate": w_actual,
            "bias": w_actual - w_implied,
            "effective_n": total_w,
            "n_trades": len(group),
        })

    return pd.DataFrame(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=" * 70)
    log.info("IN-GAME CALIBRATION ANALYSIS — Kalshi NBA")
    log.info("=" * 70)

    client = make_client(env="prod")

    # Step 1: Fetch settled markets
    log.info("\n[Step 1] Fetching settled KXNBAGAME markets...")
    markets = fetch_all_settled_markets(client)
    # Keep only markets with a definitive result
    markets = [m for m in markets if m.get("result") in ("yes", "no")]
    log.info(f"  {len(markets)} markets with yes/no result")

    # Step 2-3: Fetch trades and build DataFrame
    log.info("\n[Step 2-3] Fetching trade tapes (this may take a few minutes)...")
    df = build_trade_df(markets, client)
    if df.empty:
        log.error("No trade data collected")
        return

    # Save raw trades
    csv_path = LOG_DIR / "kalshi_nba_trades.csv"
    df.to_csv(csv_path, index=False)
    log.info(f"\n  Trade data saved: {csv_path}")
    log.info(f"  Total trades: {len(df):,}")
    log.info(f"  Unique markets: {df['ticker'].nunique()}")
    log.info(f"  Price range: {df['yes_price'].min():.2f} – {df['yes_price'].max():.2f}")

    # Step 4: Calibration by probability
    log.info("\n" + "─" * 70)
    log.info("[Step 4] CALIBRATION BY PROBABILITY BUCKET")
    log.info("─" * 70)
    log.info("  (bias > 0 → team wins MORE than market implies = favorite bias)")
    log.info("  (bias < 0 → team wins LESS than market implies = longshot bias)")
    log.info("")

    cal = calibration_by_prob(df, n_bins=10)
    log.info(f"  {'Prob Bin':<18} {'Implied':>9} {'Actual':>9} {'Bias':>8} {'Trades':>10} {'Markets':>8}")
    log.info("  " + "─" * 66)
    for _, row in cal.iterrows():
        log.info(
            f"  {str(row['prob_bin']):<18} "
            f"{row['implied_prob_avg']:>8.1%} "
            f"{row['actual_win_rate']:>8.1%} "
            f"{row['bias']:>+7.1%} "
            f"{int(row['n_trades']):>10,} "
            f"{int(row['n_unique_markets']):>8}"
        )

    # Step 5: Cross-cut by time × probability
    log.info("\n" + "─" * 70)
    log.info("[Step 5] CALIBRATION BY TIME REMAINING × PROBABILITY")
    log.info("─" * 70)
    log.info("  Does late-game pricing become more 'certain' than early-game?")
    log.info("")

    cross = calibration_by_time_and_prob(df, n_prob_bins=5)
    if not cross.empty:
        for time_label in [t[0] for t in TIME_BUCKETS]:
            subset = cross[cross["time_bucket"] == time_label]
            if subset.empty:
                continue
            log.info(f"  --- {time_label} ---")
            for _, row in subset.iterrows():
                log.info(
                    f"    {str(row['prob_bin']):<15} "
                    f"implied={row['implied_prob_avg']:.1%}  "
                    f"actual={row['actual_win_rate']:.1%}  "
                    f"bias={row['bias']:+.1%}  "
                    f"n={int(row['n_trades']):,}"
                )
            log.info("")

    # Step 6: Recency-weighted calibration
    log.info("─" * 70)
    log.info("[Step 6] RECENCY-WEIGHTED CALIBRATION (half-life = 90 days)")
    log.info("─" * 70)
    log.info("  More weight on recent games — does the bias persist NOW?")
    log.info("")

    rw = calibration_recency_weighted(df, half_life_days=90, n_bins=10)
    if not rw.empty:
        log.info(f"  {'Prob Bin':<18} {'Implied':>9} {'Actual':>9} {'Bias':>8} {'Eff. N':>8}")
        log.info("  " + "─" * 56)
        for _, row in rw.iterrows():
            log.info(
                f"  {str(row['prob_bin']):<18} "
                f"{row['implied_prob_avg']:>8.1%} "
                f"{row['actual_win_rate']:>8.1%} "
                f"{row['bias']:>+7.1%} "
                f"{row['effective_n']:>8.0f}"
            )

    # Summary
    log.info("\n" + "=" * 70)
    log.info("KEY TAKEAWAYS")
    log.info("=" * 70)

    # Overall calibration error
    overall_implied = df["yes_price"].mean()
    overall_actual = df["actual_win"].mean()
    log.info(f"  Overall: implied={overall_implied:.1%}, actual={overall_actual:.1%}, bias={overall_actual - overall_implied:+.1%}")

    # Late-game certainty check
    late = df[df["pct_elapsed"] >= 0.80]
    if not late.empty:
        high_conf = late[late["yes_price"] >= 0.75]
        if not high_conf.empty:
            log.info(f"  Late-game (>80% elapsed) at >=75% price: actual win rate = {high_conf['actual_win'].mean():.1%} (n={len(high_conf):,})")

    log.info("\nDone.")


if __name__ == "__main__":
    run()
