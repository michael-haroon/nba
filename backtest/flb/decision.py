"""
decision.py — Single-market decision card.

Run:
    conda run -n pred python -m backtest.flb.decision --ticker KXNBAGAME-26JUN03NYKSAS-SAS
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.flb.config import STRATEGIES, Strategy
from backtest.flb.data import (
    load_trades, fetch_tipoff_times, add_hours_to_tipoff,
    build_edge_grid, lookup_edge, assign_time_bin, assign_price_bin,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def fetch_market_state(ticker: str) -> dict | None:
    """Fetch current market state from Kalshi API."""
    from backtest.kalshi_client import make_client
    client = make_client(env="prod")

    try:
        resp = client.get_market(ticker)
        m = resp.get("market", resp)
        return {
            "ticker": m.get("ticker", ticker),
            "title": m.get("title", ""),
            "yes_bid": float(m.get("yes_bid_dollars", 0)),
            "yes_ask": float(m.get("yes_ask_dollars", 0)),
            "mid_price": (float(m.get("yes_bid_dollars", 0)) + float(m.get("yes_ask_dollars", 0))) / 2,
            "occurrence_datetime": m.get("occurrence_datetime"),
            "status": m.get("status"),
        }
    except Exception as e:
        log.error(f"Failed to fetch market {ticker}: {e}")
        return None


def decide(market: dict, edge_grid: pd.DataFrame) -> dict:
    """Produce a decision for a market state."""
    now = datetime.now(timezone.utc)
    mid_price = market["mid_price"]

    occ = market.get("occurrence_datetime")
    if occ:
        occ_dt = pd.to_datetime(occ, utc=True)
        hours_to_tipoff = (occ_dt - now).total_seconds() / 3600
    else:
        hours_to_tipoff = -1

    time_bin = assign_time_bin(hours_to_tipoff) if hours_to_tipoff > 0 else "IN-GAME"
    price_bin = assign_price_bin(mid_price) or "UNKNOWN"

    # Lookup
    edge_info = lookup_edge(edge_grid, hours_to_tipoff, mid_price)

    # Confidence
    n_markets = edge_info["n_markets"]
    if n_markets >= 200:
        confidence = "HIGH"
    elif n_markets >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Match against strategies
    recommendation = "NO TRADE"
    reason = ""
    matched = None

    for strat in STRATEGIES:
        time_lo, time_hi = strat.time_range
        price_lo, price_hi = strat.price_range

        if (time_lo <= hours_to_tipoff < time_hi and
                price_lo <= mid_price < price_hi):
            matched = strat
            if abs(edge_info["edge_cents"]) < strat.min_edge_cents:
                reason = f"Edge ({edge_info['edge_cents']:+.1f}¢) below threshold ({strat.min_edge_cents}¢)"
            elif n_markets < strat.min_markets:
                reason = f"Sample size ({n_markets}) below minimum ({strat.min_markets})"
            else:
                if strat.side == "no":
                    recommendation = f"FADE — Buy NO at {1 - mid_price:.2f}"
                else:
                    recommendation = f"BACK — Buy YES at {mid_price:.2f}"
                reason = f"Edge={edge_info['edge_cents']:+.1f}¢, N={n_markets} markets, Strategy={strat.name}"
            break

    if not matched and not reason:
        reason = "No strategy matches this time/price combination"

    return {
        "ticker": market["ticker"],
        "title": market["title"],
        "mid_price": mid_price,
        "hours_to_tipoff": hours_to_tipoff,
        "time_bin": time_bin,
        "price_bin": price_bin,
        "edge_cents": edge_info["edge_cents"],
        "actual_win_rate": edge_info["actual_win_rate"],
        "implied_prob": edge_info["implied_prob"],
        "n_markets": n_markets,
        "confidence": confidence,
        "recommendation": recommendation,
        "reason": reason,
    }


def print_decision_card(d: dict):
    """Format and print the decision card."""
    print()
    print("=" * 55)
    print(f"  DECISION: {d['ticker']}")
    print("=" * 55)
    print(f"  Market:      {d['title']}")
    print(f"  Mid-price:   {d['mid_price']*100:.0f}¢ (implied {d['mid_price']:.0%})")
    print(f"  Tipoff:      {d['hours_to_tipoff']:.1f} hours away")
    print(f"  Time bin:    {d['time_bin']}")
    print(f"  Price bin:   {d['price_bin']}")
    print()
    print(f"  Historical edge:   {d['edge_cents']:+.1f}¢ "
          f"(actual {d['actual_win_rate']:.1%}, implied {d['implied_prob']:.1%})")
    print(f"  Sample size:       {d['n_markets']} markets")
    print(f"  Confidence:        {d['confidence']}")
    print()
    if "NO TRADE" in d["recommendation"]:
        print(f"  RECOMMENDATION:    NO TRADE")
    else:
        print(f"  RECOMMENDATION:    {d['recommendation']}")
    print(f"  Reason:            {d['reason']}")
    print("=" * 55)
    print()


def run():
    parser = argparse.ArgumentParser(description="FLB Decision Card")
    parser.add_argument("--ticker", required=True, help="Kalshi market ticker")
    args = parser.parse_args()

    # Build edge grid
    log.info("Loading data and building edge grid...")
    df = load_trades()
    tipoff_map = fetch_tipoff_times()
    df = add_hours_to_tipoff(df, tipoff_map)
    edge_grid = build_edge_grid(df)
    del df

    # Fetch live market state
    log.info(f"Fetching market state for {args.ticker}...")
    market = fetch_market_state(args.ticker)
    if not market:
        log.error("Could not fetch market. Exiting.")
        return

    # Decide
    decision = decide(market, edge_grid)
    print_decision_card(decision)


if __name__ == "__main__":
    run()
