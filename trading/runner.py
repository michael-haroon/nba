"""
trading/runner.py
-----------------
Main trading loop. Multi-model, diversified across all market types.

Strategy:
- Scans ALL sub-markets (winner, spread, total, H1) for the next game
- Picks best signal per correlation cluster (direction, magnitude, total, h1)
- Sizes by model confidence × calibration accuracy × distribution tail quality
- Quotes at top of book (tight, not wide spreads)
- Cluster inventory caps prevent correlated concentration

Usage:
    conda run -n pred python -m trading.runner --league nba --dry-run --once
    conda run -n pred python -m trading.runner --league wnba --dry-run --interval 30
    conda run -n pred python -m trading.runner --league nba --live --once --bankroll 350
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from league_config import get_league_config, add_league_arg
from backtest.kalshi_client import make_client, make_write_client
from backtest.quoting import extract_book_top
from trading.ws import KalshiWS, make_ws, default_on_settle
import trading.models as _models
from trading.models import load_all_models
from trading.scanner import scan_all_markets, Signal
from trading.sizing import size_signals, CLUSTER_MAX_CONTRACTS
from trading.config import (
    STRATEGY, SCAN_INTERVAL_MINUTES, EXIT_BUFFER_MINUTES,
    MAX_CONTRACTS_PER_MARKET, TAKER_EDGE_THRESHOLD, CANCEL_BEFORE_TIPOFF_MIN,
    MAX_DAILY_EXPOSURE_PCT, REPRICE_MIN_TICK_MOVE,
)
from trading.executor import execute_taker, execute_maker, cancel_order
import trading.portfolio as portfolio
from trading.portfolio import (
    has_position, has_filled_position, has_open_order, get_open_order,
    add_position, add_open_order, remove_open_order,
    get_open_orders, summary, position_count, get_positions,
)
from trading.risk import check_limits
from trading.backtest import parse_ticker
from strategy.calibration import min_edge_for_profit

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "runner.log"),
    ],
)
logger = logging.getLogger(__name__)


def _load_features(cfg=None) -> pd.DataFrame:
    if cfg is not None:
        return pd.read_parquet(cfg.output_path / "game_features.parquet")
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    return pd.read_parquet(PROJECT_ROOT / "output" / "features" / "game_features.parquet")


def _find_tradeable_games(client, winner_series: str = "KXNBAGAME") -> list[dict]:
    """
    Find all tradeable games across open winner markets.

    Markov constraint: a team is "locked" if it has an open game with tipoff
    in the past (live or awaiting settlement). Locked teams' future games are
    excluded — their features are stale until the current game settles and
    the sync pipeline runs.

    Returns list of {home, away, game_key, tipoff} sorted by tipoff.
    """
    from collections import defaultdict

    result = client.get_markets(series_ticker=winner_series, status="open", limit=200)
    all_markets = result.get("markets", [])
    if not all_markets:
        return []

    # Group by matchup, keep only earliest per matchup
    matchups: dict[tuple, list] = defaultdict(list)
    for m in all_markets:
        parsed = parse_ticker(m.get("ticker", ""))
        # expected_expiration_time = when the market settles (~game end).
        # Subtract 3h to get approximate tipoff.
        exp = m.get("expected_expiration_time") or m.get("occurrence_datetime")
        if not parsed or not exp:
            continue
        key = tuple(sorted([parsed["home"], parsed["away"]]))
        tipoff = pd.Timestamp(exp, tz="UTC") - pd.Timedelta(hours=3)
        matchups[key].append({
            "parsed": parsed,
            "tipoff": tipoff,
            "ticker": m["ticker"],
        })

    now = pd.Timestamp.now(tz="UTC")

    # Collect all earliest games per matchup
    earliest_per_matchup = []
    for matchup, games in matchups.items():
        games.sort(key=lambda g: g["tipoff"])
        earliest_per_matchup.append(games[0])

    # Find locked teams: teams with a game whose tipoff is in the past (live/unsettled)
    locked_teams = set()
    for g in earliest_per_matchup:
        if g["tipoff"] < now:
            p = g["parsed"]
            locked_teams.add(p["home"])
            locked_teams.add(p["away"])

    # Filter to tradeable games (future tipoff, no locked teams)
    tradeable = []
    for g in earliest_per_matchup:
        p = g["parsed"]
        if g["tipoff"] < now:
            continue
        if p["home"] in locked_teams or p["away"] in locked_teams:
            logger.info(f"  Skipping {p['away']}@{p['home']}: team locked (prior game unsettled)")
            continue
        game_key = g["ticker"].split("-")[1]
        tradeable.append({
            "home": p["home"],
            "away": p["away"],
            "game_key": game_key,
            "tipoff": g["tipoff"],
        })

    tradeable.sort(key=lambda g: g["tipoff"])
    return tradeable


def _get_cluster_inventory() -> dict[str, int]:
    """Compute current net contracts per cluster from open positions."""
    from trading.sizing import classify_cluster
    positions = get_positions()
    inventory = {}
    for pos in positions:
        ticker = pos["ticker"]
        # Rough cluster assignment from ticker
        if "SPREAD" in ticker or "spread" in pos.get("strategy", ""):
            import re
            m = re.search(r"[A-Z]{2,3}(\d+)", ticker.split("-")[-1])
            threshold = float(m.group(1)) if m else 5
            if "1H" in ticker:
                cluster = "h1"
            elif threshold <= 3:
                cluster = "direction"
            else:
                cluster = "magnitude"
        elif "TOTAL" in ticker:
            cluster = "total" if "1H" not in ticker else "h1"
        elif "1HWINNER" in ticker:
            cluster = "h1"
        else:
            cluster = "direction"
        inventory[cluster] = inventory.get(cluster, 0) + pos["contracts"]
    return inventory


def _quote_at_top(book_bid: int | None, book_ask: int | None,
                  model_prob: float, side: str) -> int:
    """
    Quote at top of book — sit at best price, not a wide spread.
    Only quote if the top-of-book price is aligned with model fair value.
    Returns price in cents to post, or 0 if not worth quoting.
    """
    fair_cents = round(model_prob * 100)

    if side == "yes":
        # We want to BUY YES. Post bid at top of book (best_bid + 1)
        # but only if that price is BELOW our fair value (we're getting a bargain)
        if book_bid is not None:
            our_bid = book_bid + 1
        else:
            our_bid = fair_cents - 1
        # Don't bid above fair — that's overpaying
        if our_bid >= fair_cents:
            our_bid = fair_cents - 1
        return max(1, our_bid)
    else:
        # We want to BUY NO. Post at top of NO book.
        # Buying NO at X cents = selling YES at (100-X) cents.
        # Best NO bid = 100 - book_ask (YES ask)
        # NOTE: model_prob here is already P(NO), so fair_cents IS the NO fair value.
        if book_ask is not None:
            our_no_bid = (100 - book_ask) + 1
        else:
            our_no_bid = fair_cents - 1
        # Don't bid above NO fair value (fair_cents is already P(NO)*100)
        if our_no_bid >= fair_cents:
            our_no_bid = fair_cents - 1
        return max(1, our_no_bid)


def _reprice_resting_orders(client, ws, dry_run: bool) -> None:
    """
    Re-quote all resting orders to top-of-book if the book has moved.

    For each open order, fetch the current book and compute the target price
    (best_bid + 1 for YES, adjusted for NO). If the target differs from the
    current order price by at least REPRICE_MIN_TICK_MOVE cents AND the new
    price still has positive edge vs the stored model_prob, cancel the old
    order and post a new one at the better price.

    If we're already at top-of-book (target == current price) or the spread
    is too tight to improve (bb + 1 >= fair_value), we leave the order alone.
    """
    open_orders = get_open_orders()
    if not open_orders:
        return

    repriced = 0
    for order in open_orders:
        ticker = order.get("ticker", "")
        side = order.get("side", "")
        order_id = order.get("order_id", "")
        current_price = order.get("price_cents", 0)
        model_prob = order.get("model_prob", None)
        contracts = order.get("contracts", 1)

        if not ticker or not order_id or contracts <= 0:
            continue

        # Fetch current book
        if ws and ws.book.has_ticker(ticker):
            bb, ba = ws.get_book(ticker)
        else:
            try:
                book = client.get_orderbook(ticker, depth=5)
                bb, ba = extract_book_top(book)
            except Exception:
                continue

        if ba is None:
            continue

        # Compute where we should be quoting now
        target_price = _quote_at_top(bb, ba, model_prob if model_prob else current_price / 100.0, side)
        if target_price <= 0:
            continue

        # Skip if we haven't moved enough to be worth repricing
        if abs(target_price - current_price) < REPRICE_MIN_TICK_MOVE:
            continue

        # Skip if we're already at or better than target (shouldn't happen, but be safe)
        if target_price <= current_price:
            continue

        # Verify still +EV at new price: edge must still be positive
        if model_prob is not None:
            new_market_price = target_price / 100.0
            new_edge = model_prob - new_market_price
            min_edge = min_edge_for_profit(new_market_price, maker=True)
            if new_edge < min_edge:
                logger.debug(f"[REPRICE] {ticker}: target={target_price}c but edge gone ({new_edge*100:.1f}%), leaving")
                continue

        # Cancel old order, post new one at improved price
        cancelled = cancel_order(client, order_id, dry_run)
        if not cancelled:
            continue
        time.sleep(0.6)  # brief pause between cancel and resubmit to avoid 429

        remove_open_order(order_id)
        result = execute_taker(
            client, ticker, side, contracts, target_price, dry_run,
            reason=f"REPRICE {current_price}c→{target_price}c",
        )
        if result and result.get("status") in ("SUBMITTED", "DRY_RUN"):
            new_order_id = result.get("client_order_id", "")
            add_open_order(ticker, side, target_price, contracts, new_order_id,
                           model_prob=model_prob)
            logger.info(f"[REPRICE] {ticker} {side.upper()} {current_price}c → {target_price}c")
            repriced += 1

    if repriced:
        logger.info(f"[REPRICE] Repriced {repriced} resting order(s) to top-of-book")


def _cancel_stale_orders(client, game: dict | None, dry_run: bool):
    """Cancel unfilled resting orders when approaching tipoff.
    Only cancels orders still in open_orders — filled orders have already
    been moved to positions and are held through settlement.
    """
    if not game:
        return

    now = pd.Timestamp.now(tz="UTC")
    minutes_to_tipoff = (game["tipoff"] - now).total_seconds() / 60.0

    if minutes_to_tipoff > CANCEL_BEFORE_TIPOFF_MIN:
        return

    open_orders = get_open_orders()
    if not open_orders:
        return

    logger.info(f"Tipoff in {minutes_to_tipoff:.0f}min — cancelling {len(open_orders)} unfilled resting orders")
    for order in open_orders:
        order_id = order.get("order_id", "")
        if order_id:
            cancelled = cancel_order(client, order_id, dry_run)
            if cancelled:
                remove_open_order(order_id)
                logger.info(f"  Cancelled: {order['ticker']} {order['side']} x{order['contracts']} @ {order['price_cents']}c")


def scan_once(client, bundles: dict, gf: pd.DataFrame, bankroll: float,
              dry_run: bool, strategy: str, max_exposure: float | None = None,
              ws: KalshiWS | None = None, winner_series: str = "KXNBAGAME"):
    """Single scan iteration — multi-model, multi-game, diversified."""
    if max_exposure is None:
        max_exposure = bankroll * MAX_DAILY_EXPOSURE_PCT / 100.0

    portfolio.refresh()
    _reprice_resting_orders(client, ws, dry_run)
    logger.info(f"{'='*60}")
    logger.info(f"SCAN at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"Strategy: {strategy} | Mode: {'DRY_RUN' if dry_run else 'LIVE'}")
    logger.info(f"Exposure ceiling: ${max_exposure:.2f} ({max_exposure/bankroll*100:.0f}%)")
    logger.info(f"Portfolio: {summary()}")
    logger.info(f"{'='*60}")

    # Find all tradeable games
    games = _find_tradeable_games(client, winner_series=winner_series)
    if not games:
        logger.info("No tradeable games found.")
        return

    logger.info(f"Found {len(games)} tradeable game(s)")

    now = pd.Timestamp.now(tz="UTC")

    # Filter by exit buffer
    eligible = []
    for game in games:
        hours_to_tipoff = (game["tipoff"] - now).total_seconds() / 3600
        if hours_to_tipoff < EXIT_BUFFER_MINUTES / 60.0:
            logger.info(f"  {game['away']}@{game['home']}: too close to tipoff ({hours_to_tipoff:.1f}h). Skipping.")
            continue
        game["hours_to_tipoff"] = hours_to_tipoff
        eligible.append(game)

    if not eligible:
        logger.info("All games too close to tipoff.")
        return

    # Staleness check: features must contain data from AFTER the last played game.
    # In playoffs, gaps between games can be 2-4 days. The check is: the most recent
    # game in our features should match what's in GameSummaries (last settled game).
    # Use a 5-day window as max acceptable staleness.
    latest_feature_date = pd.Timestamp(gf["game_date"].max(), tz="UTC")
    earliest_tipoff = min(g["tipoff"] for g in eligible)
    days_stale = (earliest_tipoff - latest_feature_date).total_seconds() / 86400
    if days_stale > 5.0:
        logger.error(
            f"[STALE DATA] Features last updated {latest_feature_date.strftime('%Y-%m-%d')} "
            f"but next game is {earliest_tipoff.strftime('%Y-%m-%d')} ({days_stale:.1f} days gap). "
            f"Sync may have failed. Refusing to trade on stale features."
        )
        return

    # First pass: scan all games, collect signals, compute edge scores
    game_signals: list[tuple[dict, list]] = []
    for game in eligible:
        logger.info(f"\n{'─'*40}")
        import zoneinfo
        pst = zoneinfo.ZoneInfo("America/Los_Angeles")
        tipoff_pst = game['tipoff'].to_pydatetime().astimezone(pst).strftime('%Y-%m-%d %I:%M %p %Z')
        logger.info(f"Scanning: {game['away']}@{game['home']} | "
            f"Tipoff: {tipoff_pst} "
            f"({game['hours_to_tipoff']:.1f}h)")
        signals = scan_all_markets(
            client, bundles, gf,
            home=game["home"], away=game["away"],
            game_key=game["game_key"], ws=ws,
        )
        game_signals.append((game, signals))

    # Compute edge scores per game for proportional allocation
    edge_scores = []
    for game, signals in game_signals:
        score = sum(s.edge * s.model_prob for s in signals) if signals else 0.0
        edge_scores.append(score)

    total_score = sum(edge_scores)
    if total_score <= 0:
        logger.info("No signals with edge across any game.")
        return

    # Allocate budget proportionally (with minimum floor)
    n_games = len(game_signals)
    min_per_game = max_exposure / n_games * 0.3  # floor: 30% of equal share
    for i, (game, signals) in enumerate(game_signals):
        proportion = edge_scores[i] / total_score if total_score > 0 else 1.0 / n_games
        game_budget = max(min_per_game, proportion * max_exposure)
        game_budget = min(game_budget, max_exposure)  # can't exceed total
        hours_to_tipoff = game["hours_to_tipoff"]

        logger.info(f"\n  Budget for {game['away']}@{game['home']}: "
                    f"${game_budget:.2f} ({proportion*100:.0f}% of edge)")

        _execute_game_signals(
            client, signals, game, game_budget, bankroll,
            hours_to_tipoff, dry_run, strategy, max_exposure, ws,
        )


def _execute_game_signals(
    client, signals: list, game: dict, game_budget: float, bankroll: float,
    hours_to_tipoff: float, dry_run: bool, strategy: str,
    max_exposure: float, ws: KalshiWS | None = None,
):
    """Execute signals for a single game with its allocated budget."""

    # Size signals into two tiers:
    # TAKE tier: edge clears taker fee → immediate fill, cluster caps apply
    # MAKE tier: edge clears maker fee only → resting limit, NO caps (leverage)
    #   Sizing engine (Kelly × confidence × accuracy × tail_discount) handles risk per-signal.
    #   Unfilled resting orders are cancelled before tipoff.
    existing_inventory = _get_cluster_inventory()
    sized = size_signals(signals, game_budget, existing_inventory)

    logger.info(f"\nRaw signals: {len(signals)} | Sized positions: {len(sized)}")

    executed_take = 0
    executed_make = 0
    for s in sized:
        if has_filled_position(s.ticker):
            continue

        allowed, reason = check_limits(
            s.ticker, s.market_price, s.contracts, hours_to_tipoff, bankroll,
            max_exposure_dollars=max_exposure,
        )
        if not allowed:
            logger.debug(f"Risk blocked {s.ticker}: {reason}")
            continue

        # Get current book
        if ws and ws.book.has_ticker(s.ticker):
            bb, ba = ws.get_book(s.ticker)
        else:
            try:
                book = client.get_orderbook(s.ticker, depth=5)
                bb, ba = extract_book_top(book)
            except Exception:
                continue
        if ba is None:
            continue

        # Determine tier
        taker_breakeven = min_edge_for_profit(s.market_price, maker=False)
        clears_taker = s.edge >= taker_breakeven * TAKER_EDGE_THRESHOLD

        if clears_taker or strategy == "taker":
            # TAKE: aggress the book, guaranteed fill
            price_cents = ba if s.side == "yes" else (100 - (bb or 1))
            result = execute_taker(
                client, s.ticker, s.side, s.contracts, price_cents, dry_run,
                reason=(f"[{s.cluster}] TAKE edge={s.edge*100:.1f}% "
                        f"model={s.model_prob:.3f} mkt={s.market_price:.3f} "
                        f"acc={s.weight_breakdown['accuracy_mult']:.2f}"),
            )
            if result and result.get("status") in ("SUBMITTED", "DRY_RUN"):
                add_position(s.ticker, s.side, price_cents / 100.0, s.contracts, "taker")
                executed_take += 1
        else:
            # MAKE: post resting limit at top of book
            price_cents = _quote_at_top(bb, ba, s.model_prob, s.side)
            if price_cents <= 0:
                continue

            result = execute_taker(
                client, s.ticker, s.side, s.contracts, price_cents, dry_run,
                reason=(f"[{s.cluster}] MAKE@top edge={s.edge*100:.1f}% "
                        f"model={s.model_prob:.3f} quote={price_cents}c "
                        f"acc={s.weight_breakdown['accuracy_mult']:.2f}"),
            )
            if result and result.get("status") in ("SUBMITTED", "DRY_RUN"):
                order_id = result.get("client_order_id", "")
                add_open_order(s.ticker, s.side, price_cents, s.contracts, order_id,
                               model_prob=s.model_prob)
                executed_make += 1

    # Post resting orders on signals with edge (no cluster caps).
    # Only post where model accuracy multiplier is reasonable (>= 0.5).
    # Risk limits (exposure cap, price range, timing) still apply.
    all_sized = size_signals(signals, game_budget, enforce_caps=False)
    already_handled = {s.ticker for s in sized}
    for s in all_sized:
        if s.ticker in already_handled or has_filled_position(s.ticker):
            continue

        # Skip low-accuracy deciles — model historically unreliable at this confidence level
        if s.weight_breakdown["accuracy_mult"] < 0.5:
            continue

        # Skip signals that would be takes — those were already handled above
        taker_breakeven = min_edge_for_profit(s.market_price, maker=False)
        if s.edge >= taker_breakeven * TAKER_EDGE_THRESHOLD:
            continue

        # Risk limits apply to resting orders too (exposure cap, etc.)
        allowed, reason = check_limits(
            s.ticker, s.market_price, s.contracts, hours_to_tipoff, bankroll,
            max_exposure_dollars=max_exposure,
        )
        if not allowed:
            logger.debug(f"Risk blocked resting {s.ticker}: {reason}")
            continue

        if ws and ws.book.has_ticker(s.ticker):
            bb, ba = ws.get_book(s.ticker)
        else:
            try:
                book = client.get_orderbook(s.ticker, depth=5)
                bb, ba = extract_book_top(book)
            except Exception:
                continue
        if ba is None:
            continue

        price_cents = _quote_at_top(bb, ba, s.model_prob, s.side)
        if price_cents <= 0:
            continue

        result = execute_taker(
            client, s.ticker, s.side, s.contracts, price_cents, dry_run,
            reason=(f"[{s.cluster}] MAKE@top edge={s.edge*100:.1f}% "
                    f"model={s.model_prob:.3f} quote={price_cents}c "
                    f"acc={s.weight_breakdown['accuracy_mult']:.2f}"),
        )
        if result and result.get("status") in ("SUBMITTED", "DRY_RUN"):
            order_id = result.get("client_order_id", "")
            add_open_order(s.ticker, s.side, price_cents, s.contracts, order_id,
                           model_prob=s.model_prob)
            executed_make += 1

    # Cancel stale resting orders approaching tipoff
    _cancel_stale_orders(client, game, dry_run)

    # Final summary
    logger.info(f"\nExecuted: {executed_take} taken + {executed_make} resting / {len(sized)} sized")
    for s in sized[:10]:
        w = s.weight_breakdown
        logger.info(
            f"  [{s.cluster:10s}] {s.ticker:52s} {s.side:3s} x{s.contracts:2d} "
            f"edge={s.edge*100:.1f}% acc={w['accuracy_mult']:.2f} "
            f"comp={w['composite']:.4f}"
        )


def main():
    parser = argparse.ArgumentParser(description="Trading runner (multi-model)")
    add_league_arg(parser)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL_MINUTES)
    parser.add_argument("--strategy", default=STRATEGY,
                        choices=["taker", "maker", "hybrid"])
    parser.add_argument("--bankroll", type=float, default=350.0)
    parser.add_argument("--exposure", type=float, default=MAX_DAILY_EXPOSURE_PCT / 100.0,
                        help="Fraction of bankroll for max exposure (0.0-1.0). Default: 0.4")
    parser.add_argument("--no-ws", action="store_true")
    args = parser.parse_args()

    cfg = get_league_config(args.league)
    _models.set_league(cfg)

    dry_run = not args.live
    strategy = args.strategy
    max_exposure = args.exposure * args.bankroll
    winner_series = cfg.kalshi_series["winner"]

    logger.info(f"League: {cfg.league.upper()} | Models: {cfg.models_path}")
    logger.info("Loading all models...")
    bundles = load_all_models()
    gf = _load_features(cfg)
    logger.info(f"Loaded {len(bundles)} models, {len(gf)} game rows.")

    # Connect to Kalshi REST
    if dry_run:
        client = make_client("prod")
    else:
        client = make_write_client("prod")

    try:
        bal = client.get_balance()
        logger.info(f"Connected to Kalshi. Balance: ${bal.get('balance', 0)/100:.2f}")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        sys.exit(1)

    portfolio.init(client, dry_run)

    # WebSocket for real-time book + settlement triggers
    ws = None
    if not args.no_ws:
        try:
            def on_settle(ticker: str):
                nonlocal bundles, gf
                default_on_settle(ticker, league=cfg.league)

                # Verify sync actually ingested the settled game
                gf_new = _load_features(cfg)
                latest_date = gf_new["game_date"].max()
                prev_date = gf["game_date"].max()
                if latest_date <= prev_date:
                    logger.error(
                        f"[SYNC VERIFY] FAILED — features not updated after settlement. "
                        f"Latest game_date still {latest_date}. NOT reloading. "
                        f"Trading paused until next successful sync."
                    )
                    return

                logger.info(f"[SYNC VERIFY] OK — features updated: {prev_date} → {latest_date}")
                bundles = load_all_models()
                gf = gf_new
                logger.info("Models reloaded with fresh data.")

            ws = make_ws("prod", on_settle=on_settle)
            ws.start()
            logger.info("WebSocket started (lifecycle listener active)")
        except Exception as e:
            logger.warning(f"WebSocket failed, falling back to REST: {e}")
            ws = None

    if args.once:
        scan_once(client, bundles, gf, args.bankroll, dry_run, strategy,
                  max_exposure=max_exposure, ws=ws, winner_series=winner_series)
        if ws:
            ws.stop()
        portfolio.stop()
    else:
        logger.info(f"Starting continuous scan (interval={args.interval}min)")
        while True:
            try:
                scan_once(client, bundles, gf, args.bankroll, dry_run, strategy,
                          max_exposure=max_exposure, ws=ws, winner_series=winner_series)
            except KeyboardInterrupt:
                logger.info("Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"Scan error: {e}", exc_info=True)

            logger.info(f"Sleeping {args.interval} minutes...")
            time.sleep(args.interval * 60)

        if ws:
            ws.stop()
        portfolio.stop()


if __name__ == "__main__":
    main()
