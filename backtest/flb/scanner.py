"""
scanner.py — Live market scanner (READ-ONLY). Never places orders.

Run:
    conda run -n pred python -m backtest.flb.scanner --once
    conda run -n pred python -m backtest.flb.scanner --loop 5
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.flb.config import (
    SERIES_TICKER, STRATEGIES, SIGNALS_DIR, LOG_DIR, OUTPUT_DIR, Strategy,
)
from backtest.flb.data import (
    load_trades, fetch_tipoff_times, add_hours_to_tipoff,
    build_edge_grid, lookup_edge,
)

# SAFETY: This module is READ-ONLY. It never places orders.
_FORBIDDEN_METHODS = {"create_order", "cancel_order", "post"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scanner.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

_SHUTDOWN = False


def _signal_handler(signum, frame):
    global _SHUTDOWN
    _SHUTDOWN = True
    log.info("Shutdown signal received, finishing current scan...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def scan_once(edge_grid: pd.DataFrame) -> list[dict]:
    """
    Fetch open KXNBAGAME markets and evaluate signals. READ-ONLY.
    """
    from backtest.kalshi_client import make_client
    client = make_client(env="prod")

    # SAFETY: This scanner ONLY calls get_markets. Never create_order/cancel_order/post.

    signals = []
    now = datetime.now(timezone.utc)

    for status in ["open"]:
        resp = client.get_markets(**{"series_ticker": SERIES_TICKER, "status": status, "limit": 200})
        for m in resp.get("markets", []):
            ticker = m.get("ticker", "")
            title = m.get("title", "")

            yes_bid = m.get("yes_bid_dollars")
            yes_ask = m.get("yes_ask_dollars")
            if not yes_bid or not yes_ask:
                continue

            mid_price = (float(yes_bid) + float(yes_ask)) / 2
            occurrence = m.get("occurrence_datetime")
            if not occurrence:
                continue

            occ_dt = pd.to_datetime(occurrence, utc=True)
            hours_to_tipoff = (occ_dt - now).total_seconds() / 3600
            if hours_to_tipoff < 0:
                continue

            # Look up historical edge
            edge_info = lookup_edge(edge_grid, hours_to_tipoff, mid_price)

            # Determine signal from strategies
            signal_type = "NO TRADE"
            action = ""
            matched_strategy = None

            for strat in STRATEGIES:
                time_lo, time_hi = strat.time_range
                price_lo, price_hi = strat.price_range

                if (time_lo <= hours_to_tipoff < time_hi and
                        price_lo <= mid_price < price_hi):
                    if (abs(edge_info["edge_cents"]) >= strat.min_edge_cents and
                            edge_info["n_markets"] >= strat.min_markets):
                        matched_strategy = strat
                        if strat.side == "no":
                            signal_type = "FADE"
                            action = f"Buy NO at {1 - mid_price:.2f}"
                        else:
                            signal_type = "BACK"
                            action = f"Buy YES at {mid_price:.2f}"
                        break

            signals.append({
                "timestamp": now.isoformat(),
                "ticker": ticker,
                "title": title,
                "mid_price": round(mid_price, 4),
                "yes_bid": float(yes_bid),
                "yes_ask": float(yes_ask),
                "hours_to_tipoff": round(hours_to_tipoff, 2),
                "edge_cents": round(edge_info["edge_cents"], 1),
                "n_markets": edge_info["n_markets"],
                "signal": signal_type,
                "action": action,
                "strategy": matched_strategy.name if matched_strategy else None,
            })

    return signals


def log_signals(signals: list[dict]):
    """Print signal table and write JSON."""
    if not signals:
        log.info("  No open KXNBAGAME markets found")
        return

    log.info(f"\n{'Ticker':<42} {'Mid':>5} {'Hrs':>6} {'Edge':>6} {'N':>4} {'Signal':<10} {'Action'}")
    log.info("─" * 95)

    for s in signals:
        log.info(
            f"{s['ticker']:<42} {s['mid_price']:>5.2f} "
            f"{s['hours_to_tipoff']:>6.1f} {s['edge_cents']:>+5.1f}¢ "
            f"{s['n_markets']:>4} {s['signal']:<10} {s['action']}"
        )

    # Write JSON signal file
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = SIGNALS_DIR / f"{ts}.json"
    json_path.write_text(json.dumps(signals, indent=2))
    log.info(f"\n  Signals written to {json_path}")


def run():
    parser = argparse.ArgumentParser(description="FLB Market Scanner (read-only)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Single scan then exit")
    group.add_argument("--loop", type=int, metavar="MIN", help="Scan every N minutes")
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("FLB SCANNER (READ-ONLY)")
    log.info("=" * 70)

    # Build edge grid from historical data
    log.info("Loading historical data and building edge grid...")
    df = load_trades()
    tipoff_map = fetch_tipoff_times()
    df = add_hours_to_tipoff(df, tipoff_map)
    edge_grid = build_edge_grid(df)
    del df  # Free memory after building grid
    log.info("Edge grid ready.\n")

    if args.once:
        signals = scan_once(edge_grid)
        log_signals(signals)
    else:
        log.info(f"Scanning every {args.loop} minutes. Ctrl+C to stop.\n")
        while not _SHUTDOWN:
            signals = scan_once(edge_grid)
            log_signals(signals)
            for _ in range(args.loop * 60):
                if _SHUTDOWN:
                    break
                time.sleep(1)

    log.info("Scanner stopped.")


if __name__ == "__main__":
    run()
