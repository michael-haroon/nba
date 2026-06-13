"""
trading/backtest.py
-------------------
Historical simulation of three trading strategies using:
  - Ensemble model predictions (generated from LOYO-trained pkl, honest for 2025-26)
  - Kalshi historical trade tape (11M trades, Mar-May 2026)
  - FLB edge grid
  - Kalshi fee model

Strategies:
  A) Directional Taker: aggress when edge > threshold, hold to settlement
  B) Market-Make + Exit Pre-Tipoff: post bid/ask, close before tipoff
  C) Hybrid: market-make + selectively hold aligned positions

Usage:
    conda run -n pred python -m trading.backtest [--strategy all|taker|maker|hybrid]
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.calibration import kalshi_taker_fee, kalshi_maker_fee, min_edge_for_profit
from strategy.config import (
    KELLY_FRACTION, WINNER_STD_THRESHOLDS, WINNER_CONFIDENCE_MULTIPLIERS,
    FLB_AGREE_MULT, FLB_DISAGREE_MULT, FLB_NEUTRAL_MULT,
)
from backtest.quoting import compute_quotes

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADES_CSV = PROJECT_ROOT / "backtest" / "logs" / "kalshi_nba_trades.csv"
TIPOFF_JSON = PROJECT_ROOT / "backtest" / "logs" / "tipoff_times.json"
GAME_PARQUET = PROJECT_ROOT / "output" / "features" / "game_features.parquet"
ENSEMBLE_PKL = PROJECT_ROOT / "strategy" / "output" / "nba" / "winner" / "ensemble.pkl"
FLB_TRADES = TRADES_CSV  # same file
OUTPUT_DIR = PROJECT_ROOT / "trading" / "output"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Ticker parsing ───────────────────────────────────────────────────────────

KALSHI_VARIANT = {"NY": "NYK", "GS": "GSW", "SA": "SAS", "NO": "NOP"}

def _normalize(k: str) -> str:
    k = k.upper()
    return KALSHI_VARIANT.get(k, k)


def parse_ticker(ticker: str) -> dict | None:
    m = re.match(
        r"KXNBAGAME-(\d{2}[A-Z]{3}\d{2})([A-Z]{2,3})([A-Z]{2,3})-([A-Z]{2,3})$",
        ticker,
    )
    if not m:
        return None
    date_str, away_raw, home_raw, yes_raw = m.groups()
    try:
        game_date = datetime.strptime("20" + date_str, "%Y%b%d").date()
    except ValueError:
        return None
    return {
        "game_date": game_date,
        "away": _normalize(away_raw),
        "home": _normalize(home_raw),
        "yes_team": _normalize(yes_raw),
    }


# ── Data loading ─────────────────────────────────────────────────────────────

def load_game_features() -> pd.DataFrame:
    gf = pd.read_parquet(GAME_PARQUET)
    gf["game_date"] = pd.to_datetime(gf["game_date"]).dt.date
    return gf


def load_tipoff_times() -> dict[str, pd.Timestamp]:
    if TIPOFF_JSON.exists():
        raw = json.loads(TIPOFF_JSON.read_text())
        return {k: pd.Timestamp(v) for k, v in raw.items()}
    return {}


def load_ensemble_bundle() -> dict:
    with open(ENSEMBLE_PKL, "rb") as f:
        return pickle.load(f)


def load_trades() -> pd.DataFrame:
    logger.info("Loading trade tape (this may take a moment)...")
    df = pd.read_csv(TRADES_CSV)
    df["trade_time"] = pd.to_datetime(df["trade_time"], format="ISO8601", utc=True)
    df["settlement_dt"] = pd.to_datetime(df["settlement_dt"], format="ISO8601", utc=True)
    logger.info(f"Loaded {len(df):,} trades across {df['ticker'].nunique()} tickers")
    return df


# ── Model prediction ─────────────────────────────────────────────────────────

def generate_predictions(bundle: dict, gf: pd.DataFrame, game_indices: list[int]) -> dict[int, dict]:
    """
    Generate ensemble predictions for specified game indices.
    Returns {index: {prob, std, confidence}} for each game.
    """
    specialists = bundle["specialists"]
    weights = np.array(bundle["weights"])

    results = {}
    for idx in game_indices:
        row = gf.iloc[idx:idx+1]
        preds = []
        for s in specialists:
            X_sub = row[s["features"]].copy()
            if s.get("impute_median"):
                X_sub = X_sub.fillna(pd.Series(s["impute_median"]))
            if s.get("needs_scaling"):
                X_sub = (X_sub - pd.Series(s["scale_mean"])) / pd.Series(s["scale_std"])
            try:
                p = s["model"].predict_proba(X_sub)[:, 1][0]
            except Exception:
                p = 0.5
            preds.append(p)

        preds = np.array(preds)
        prob = float(np.dot(preds, weights))
        std = float(np.std(preds))

        lo, hi = WINNER_STD_THRESHOLDS
        if std <= lo:
            confidence = "HIGH"
        elif std <= hi:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        results[idx] = {"prob": prob, "std": std, "confidence": confidence}

    return results


# ── Edge and sizing ──────────────────────────────────────────────────────────

def compute_edge(model_prob: float, market_price: float) -> tuple[str, float]:
    """Returns (side, edge) where side is YES or NO."""
    edge_yes = model_prob - market_price
    edge_no = (1 - model_prob) - (1 - market_price)

    if edge_yes >= edge_no:
        return "YES", edge_yes
    else:
        return "NO", edge_no


def kelly_size(edge: float, price: float, confidence: str, kelly_frac: float) -> float:
    """Fractional Kelly with confidence scaling. Returns fraction of bankroll."""
    if edge <= 0 or price <= 0 or price >= 1:
        return 0.0
    kelly_raw = edge / (1.0 - price)
    conf_mult = WINNER_CONFIDENCE_MULTIPLIERS.get(confidence, 0.5)
    return kelly_raw * kelly_frac * conf_mult


# ── Strategy A: Taker ────────────────────────────────────────────────────────

def backtest_taker(
    trades_by_ticker: dict[str, pd.DataFrame],
    predictions: dict[int, dict],
    game_map: dict[str, int],
    tipoff_times: dict[str, pd.Timestamp],
    decision_hours: float = 24.0,
    min_edge_buffer: float = 1.5,
    kelly_frac: float = 0.25,
    confidence_gate: str = "HIGH+MED",
    bankroll: float = 1000.0,
) -> pd.DataFrame:
    """
    Taker strategy: at T-decision_hours, check edge. If sufficient, buy at market.
    Hold to settlement.
    """
    results = []

    for ticker, ticker_trades in trades_by_ticker.items():
        idx = game_map.get(ticker)
        if idx is None:
            continue
        pred = predictions.get(idx)
        if pred is None:
            continue

        # Confidence gate
        if confidence_gate == "HIGH" and pred["confidence"] != "HIGH":
            continue
        if confidence_gate == "HIGH+MED" and pred["confidence"] == "LOW":
            continue

        tipoff = tipoff_times.get(ticker)
        if tipoff is None:
            continue

        # Get market price at decision time using pct_elapsed
        # pct_elapsed = (trade_time - market_open) / (tipoff - market_open)
        # At T-Xh: pct_elapsed ≈ 1 - X/(total_market_hours)
        # Approximate: find trades where hours_to_tipoff ≈ decision_hours
        ticker_trades_copy = ticker_trades.copy()
        ticker_trades_copy["hours_to_tipoff"] = (
            (tipoff - ticker_trades_copy["trade_time"]).dt.total_seconds() / 3600
        )

        # Find trades within decision_hours ± tolerance
        tolerance = max(decision_hours * 0.3, 2.0)  # 30% or 2h, whichever larger
        window = ticker_trades_copy[
            (ticker_trades_copy["hours_to_tipoff"] >= decision_hours - tolerance) &
            (ticker_trades_copy["hours_to_tipoff"] <= decision_hours + tolerance)
        ]
        if window.empty:
            # Fallback: use earliest 20% of trades as "early" market price
            if decision_hours >= 24:
                n = max(1, len(ticker_trades) // 5)
                window = ticker_trades.head(n)
            else:
                continue

        market_price = float(window["yes_price"].median())

        # Parse ticker to determine if this is the home team's YES contract
        parsed = parse_ticker(ticker)
        if parsed is None:
            continue

        # Model prob is P(home_wins). Adjust for YES team.
        model_prob = pred["prob"]
        if parsed["yes_team"] != parsed["home"]:
            model_prob = 1.0 - model_prob

        # Compute edge
        side, edge = compute_edge(model_prob, market_price)
        price = market_price if side == "YES" else (1.0 - market_price)

        # Fee threshold
        min_edge = min_edge_for_profit(price, maker=False) * min_edge_buffer
        if edge < min_edge:
            continue

        # Size
        kelly = kelly_size(edge, price, pred["confidence"], kelly_frac)
        bet_frac = min(kelly, 0.05)  # cap at 5%
        bet_dollars = bet_frac * bankroll
        contracts = max(1, int(bet_dollars / price))
        contracts = min(contracts, 20)

        # Settlement
        actual_win = int(ticker_trades["actual_win"].iloc[0])
        # actual_win=1 means YES team won
        won = (side == "YES" and actual_win == 1) or (side == "NO" and actual_win == 0)

        # P&L per contract (in dollars, 0-1 scale)
        fee = 0.07 * price * (1 - price)
        if won:
            pnl_per = (1.0 - price) - fee
        else:
            pnl_per = -price - fee

        total_pnl = pnl_per * contracts

        results.append({
            "ticker": ticker,
            "game_date": str(parsed["game_date"]),
            "home": parsed["home"],
            "away": parsed["away"],
            "yes_team": parsed["yes_team"],
            "model_prob": model_prob,
            "market_price": market_price,
            "side": side,
            "edge": edge,
            "confidence": pred["confidence"],
            "contracts": contracts,
            "entry_price": price,
            "won": won,
            "fee_per_contract": fee,
            "pnl_per_contract": pnl_per,
            "total_pnl": total_pnl,
            "decision_hours": decision_hours,
        })

    return pd.DataFrame(results)


# ── Strategy B: Market-Make + Exit Pre-Tipoff ────────────────────────────────

def backtest_maker(
    trades_by_ticker: dict[str, pd.DataFrame],
    predictions: dict[int, dict],
    game_map: dict[str, int],
    tipoff_times: dict[str, pd.Timestamp],
    spread_width: int = 2,
    max_inventory: int = 10,
    exit_buffer_hours: float = 0.5,
    confidence_gate: str = "HIGH+MED",
    bankroll: float = 1000.0,
) -> pd.DataFrame:
    """
    Market-making: post bid/ask around model fair value, simulate fills from tape.
    Exit ALL positions before tipoff. P&L = spread capture only.
    """
    results = []

    for ticker, ticker_trades in trades_by_ticker.items():
        idx = game_map.get(ticker)
        if idx is None:
            continue
        pred = predictions.get(idx)
        if pred is None:
            continue

        if confidence_gate == "HIGH" and pred["confidence"] != "HIGH":
            continue
        if confidence_gate == "HIGH+MED" and pred["confidence"] == "LOW":
            continue

        tipoff = tipoff_times.get(ticker)
        if tipoff is None:
            continue

        parsed = parse_ticker(ticker)
        if parsed is None:
            continue

        model_prob = pred["prob"]
        if parsed["yes_team"] != parsed["home"]:
            model_prob = 1.0 - model_prob

        # Compute our quotes (in cents)
        fair_cents = round(model_prob * 100)
        fair_cents = max(1, min(99, fair_cents))
        bid_cents = fair_cents - spread_width
        ask_cents = fair_cents + spread_width

        if bid_cents < 1 or ask_cents > 99:
            continue

        # Filter to pre-tipoff trades (with exit buffer)
        exit_time = tipoff - pd.Timedelta(hours=exit_buffer_hours)
        pre_trades = ticker_trades[ticker_trades["trade_time"] < exit_time]

        if pre_trades.empty:
            continue

        # Simulate fills
        inventory = 0
        buy_fills = []
        sell_fills = []

        for _, trade in pre_trades.iterrows():
            trade_price_cents = round(float(trade["yes_price"]) * 100)

            # If trade happens at or below our bid → we get filled buying
            if trade_price_cents <= bid_cents and inventory < max_inventory:
                buy_fills.append(bid_cents / 100.0)
                inventory += 1

            # If trade happens at or above our ask → we get filled selling
            elif trade_price_cents >= ask_cents and inventory > -max_inventory:
                sell_fills.append(ask_cents / 100.0)
                inventory -= 1

        # Exit: close remaining inventory at last pre-tipoff mid-price
        exit_trades = ticker_trades[
            (ticker_trades["trade_time"] >= exit_time - pd.Timedelta(hours=1)) &
            (ticker_trades["trade_time"] < tipoff)
        ]
        exit_price = float(exit_trades["yes_price"].median()) if not exit_trades.empty else model_prob

        # P&L calculation
        # Spread income: each completed round-trip earns (ask - bid) in cents
        n_buys = len(buy_fills)
        n_sells = len(sell_fills)
        round_trips = min(n_buys, n_sells)
        spread_pnl = round_trips * (ask_cents - bid_cents) / 100.0

        # Residual inventory P&L (closed at exit_price)
        if inventory > 0:
            # Long inventory: bought at bid, exit at exit_price
            residual_pnl = inventory * (exit_price - bid_cents / 100.0)
        elif inventory < 0:
            # Short inventory: sold at ask, exit at exit_price
            residual_pnl = abs(inventory) * (ask_cents / 100.0 - exit_price)
        else:
            residual_pnl = 0.0

        # Fees: maker for entry fills, taker for exit
        n_fills = n_buys + n_sells
        maker_fees = sum(0.0175 * p * (1 - p) for p in buy_fills + sell_fills)
        # Exit fees (taker rate) for residual inventory
        exit_fees = abs(inventory) * 0.07 * exit_price * (1 - exit_price) if inventory != 0 else 0.0

        total_pnl = spread_pnl + residual_pnl - maker_fees - exit_fees

        results.append({
            "ticker": ticker,
            "game_date": str(parsed["game_date"]),
            "home": parsed["home"],
            "away": parsed["away"],
            "model_prob": model_prob,
            "fair_cents": fair_cents,
            "bid_cents": bid_cents,
            "ask_cents": ask_cents,
            "n_buys": n_buys,
            "n_sells": n_sells,
            "round_trips": round_trips,
            "net_inventory": inventory,
            "spread_pnl": spread_pnl,
            "residual_pnl": residual_pnl,
            "maker_fees": maker_fees,
            "exit_fees": exit_fees,
            "total_pnl": total_pnl,
            "exit_price": exit_price,
            "confidence": pred["confidence"],
        })

    return pd.DataFrame(results)


# ── Strategy C: Hybrid (MM + Selective Hold) ─────────────────────────────────

def backtest_hybrid(
    trades_by_ticker: dict[str, pd.DataFrame],
    predictions: dict[int, dict],
    game_map: dict[str, int],
    tipoff_times: dict[str, pd.Timestamp],
    spread_width: int = 2,
    max_inventory: int = 10,
    hold_edge_threshold: float = 0.05,
    confidence_gate: str = "HIGH+MED",
    bankroll: float = 1000.0,
) -> pd.DataFrame:
    """
    Hybrid: market-make pre-game, then at T-1h:
      - Close positions OPPOSING model direction
      - HOLD positions aligned with model (if edge > threshold)
    P&L = spread income + directional settlement on held positions.
    """
    results = []

    for ticker, ticker_trades in trades_by_ticker.items():
        idx = game_map.get(ticker)
        if idx is None:
            continue
        pred = predictions.get(idx)
        if pred is None:
            continue

        if confidence_gate == "HIGH" and pred["confidence"] != "HIGH":
            continue
        if confidence_gate == "HIGH+MED" and pred["confidence"] == "LOW":
            continue

        tipoff = tipoff_times.get(ticker)
        if tipoff is None:
            continue

        parsed = parse_ticker(ticker)
        if parsed is None:
            continue

        model_prob = pred["prob"]
        if parsed["yes_team"] != parsed["home"]:
            model_prob = 1.0 - model_prob

        fair_cents = round(model_prob * 100)
        fair_cents = max(1, min(99, fair_cents))
        bid_cents = fair_cents - spread_width
        ask_cents = fair_cents + spread_width

        if bid_cents < 1 or ask_cents > 99:
            continue

        # MM phase: trade until T-1h
        decision_time = tipoff - pd.Timedelta(hours=1)
        mm_trades = ticker_trades[ticker_trades["trade_time"] < decision_time]

        if mm_trades.empty:
            continue

        inventory = 0
        buy_fills = []
        sell_fills = []

        for _, trade in mm_trades.iterrows():
            trade_price_cents = round(float(trade["yes_price"]) * 100)
            if trade_price_cents <= bid_cents and inventory < max_inventory:
                buy_fills.append(bid_cents / 100.0)
                inventory += 1
            elif trade_price_cents >= ask_cents and inventory > -max_inventory:
                sell_fills.append(ask_cents / 100.0)
                inventory -= 1

        # Decision: hold aligned positions, close opposing
        # Model says YES if model_prob > 0.5, NO otherwise
        model_side = "YES" if model_prob > 0.5 else "NO"

        # inventory > 0 means we're long YES (bought at bid)
        # inventory < 0 means we're short YES (sold at ask) = long NO
        position_side = "YES" if inventory > 0 else ("NO" if inventory < 0 else None)

        # Get exit price for closing
        exit_window = ticker_trades[
            (ticker_trades["trade_time"] >= decision_time - pd.Timedelta(minutes=30)) &
            (ticker_trades["trade_time"] < tipoff)
        ]
        exit_price = float(exit_window["yes_price"].median()) if not exit_window.empty else model_prob

        # Compute edge at decision time
        side, edge = compute_edge(model_prob, exit_price)

        # Spread income from round trips
        round_trips = min(len(buy_fills), len(sell_fills))
        spread_pnl = round_trips * (ask_cents - bid_cents) / 100.0

        # Decide hold vs close
        aligned = (position_side == model_side) if position_side else False
        hold_position = aligned and edge >= hold_edge_threshold

        # Maker fees on all fills
        maker_fees = sum(0.0175 * p * (1 - p) for p in buy_fills + sell_fills)

        if hold_position and inventory != 0:
            # Hold to settlement
            actual_win = int(ticker_trades["actual_win"].iloc[0])
            abs_inv = abs(inventory)

            if inventory > 0:
                # Long YES, settlement
                won = actual_win == 1
                entry = bid_cents / 100.0
                settle_pnl = abs_inv * ((1.0 - entry) if won else -entry)
            else:
                # Short YES = long NO, settlement
                won = actual_win == 0
                entry = ask_cents / 100.0
                settle_pnl = abs_inv * ((entry) if won else -(1.0 - entry))

            # No exit fees (held to settlement)
            total_pnl = spread_pnl + settle_pnl - maker_fees
            exit_mode = "HOLD"
            held_contracts = abs_inv
        else:
            # Close all at exit_price
            if inventory > 0:
                residual_pnl = inventory * (exit_price - bid_cents / 100.0)
            elif inventory < 0:
                residual_pnl = abs(inventory) * (ask_cents / 100.0 - exit_price)
            else:
                residual_pnl = 0.0

            exit_fees = abs(inventory) * 0.07 * exit_price * (1 - exit_price) if inventory != 0 else 0.0
            total_pnl = spread_pnl + residual_pnl - maker_fees - exit_fees
            exit_mode = "EXIT"
            held_contracts = 0
            won = None

        results.append({
            "ticker": ticker,
            "game_date": str(parsed["game_date"]),
            "home": parsed["home"],
            "away": parsed["away"],
            "model_prob": model_prob,
            "model_side": model_side,
            "position_side": position_side,
            "inventory": inventory,
            "aligned": aligned,
            "edge_at_decision": edge,
            "exit_mode": exit_mode,
            "held_contracts": held_contracts,
            "round_trips": round_trips,
            "spread_pnl": spread_pnl,
            "total_pnl": total_pnl,
            "confidence": pred["confidence"],
            "won": won,
        })

    return pd.DataFrame(results)


# ── Metrics ──────────────────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame, label: str) -> dict:
    if df.empty or "total_pnl" not in df.columns:
        return {"strategy": label, "n_trades": 0}

    pnl = df["total_pnl"]
    cumulative = pnl.cumsum()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak).min()

    return {
        "strategy": label,
        "n_trades": len(df),
        "total_pnl": round(pnl.sum(), 2),
        "avg_pnl": round(pnl.mean(), 4),
        "win_rate": round((pnl > 0).mean() * 100, 1),
        "sharpe": round(pnl.mean() / pnl.std() * np.sqrt(len(pnl)), 3) if pnl.std() > 0 else 0.0,
        "max_drawdown": round(drawdown, 2),
        "avg_trade_size": round(pnl.abs().mean(), 4),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def run_backtest(strategy: str = "all"):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    gf = load_game_features()
    trades = load_trades()
    tipoff_times = load_tipoff_times()
    bundle = load_ensemble_bundle()

    # Build ticker → game_index map
    # For each ticker in trade tape, find corresponding game in game_features
    unique_tickers = trades["ticker"].unique()
    game_map: dict[str, int] = {}  # ticker → game_features index

    for ticker in unique_tickers:
        parsed = parse_ticker(ticker)
        if not parsed:
            continue
        home, away, gd = parsed["home"], parsed["away"], parsed["game_date"]
        mask = (gf["game_date"] == gd) & (
            ((gf["home_team_abbr"] == home) & (gf["away_team_abbr"] == away)) |
            ((gf["home_team_abbr"] == away) & (gf["away_team_abbr"] == home))
        )
        matches = gf[mask]
        if not matches.empty:
            game_map[ticker] = matches.index[0]

    logger.info(f"Matched {len(game_map)}/{len(unique_tickers)} tickers to game_features")

    # Generate predictions for all matched games
    game_indices = list(set(game_map.values()))
    logger.info(f"Generating predictions for {len(game_indices)} games...")
    predictions = generate_predictions(bundle, gf, game_indices)
    logger.info("Predictions generated.")

    # Derive tipoff times from settlement_dt column (= occurrence_datetime ≈ tipoff)
    # This covers all 466 tickers, overriding the JSON where available
    ticker_tipoffs = trades.groupby("ticker")["settlement_dt"].first()
    for ticker, dt in ticker_tipoffs.items():
        tipoff_times[ticker] = dt

    # Group trades by ticker
    trades_by_ticker = {t: g for t, g in trades.groupby("ticker")}

    # ── Run strategies ────────────────────────────────────────────────────────
    all_metrics = []

    if strategy in ("all", "taker"):
        logger.info("=" * 60)
        logger.info("STRATEGY A: DIRECTIONAL TAKER")
        logger.info("=" * 60)

        for hours in [48, 24, 6, 1]:
            for buffer in [1.0, 1.5, 2.0, 3.0]:
                for gate in ["ALL", "HIGH+MED", "HIGH"]:
                    label = f"taker_h{hours}_b{buffer}_g{gate}"
                    df = backtest_taker(
                        trades_by_ticker, predictions, game_map, tipoff_times,
                        decision_hours=hours, min_edge_buffer=buffer,
                        kelly_frac=KELLY_FRACTION, confidence_gate=gate,
                    )
                    m = compute_metrics(df, label)
                    m["params"] = f"hours={hours}, buffer={buffer}, gate={gate}"
                    all_metrics.append(m)
                    if m["n_trades"] > 0:
                        logger.info(f"  {label}: N={m['n_trades']}, PnL=${m['total_pnl']:.2f}, "
                                    f"Sharpe={m['sharpe']:.2f}, Win={m['win_rate']:.1f}%")

        # Save best taker detail
        best_taker = max(
            [m for m in all_metrics if m["strategy"].startswith("taker") and m["n_trades"] > 5],
            key=lambda x: x.get("sharpe", -999), default=None
        )
        if best_taker:
            logger.info(f"\n  BEST TAKER: {best_taker['strategy']} → Sharpe={best_taker['sharpe']}")

    if strategy in ("all", "maker"):
        logger.info("=" * 60)
        logger.info("STRATEGY B: MARKET-MAKE + EXIT PRE-TIPOFF")
        logger.info("=" * 60)

        for spread in [2, 3, 4, 5]:
            for max_inv in [5, 10, 20]:
                for gate in ["ALL"]:
                    label = f"maker_s{spread}_i{max_inv}_g{gate}"
                    df = backtest_maker(
                        trades_by_ticker, predictions, game_map, tipoff_times,
                        spread_width=spread, max_inventory=max_inv,
                        confidence_gate=gate,
                    )
                    m = compute_metrics(df, label)
                    m["params"] = f"spread={spread}, max_inv={max_inv}, gate={gate}"
                    all_metrics.append(m)
                    if m["n_trades"] > 0:
                        logger.info(f"  {label}: N={m['n_trades']}, PnL=${m['total_pnl']:.2f}, "
                                    f"Sharpe={m['sharpe']:.2f}, Win={m['win_rate']:.1f}%")

    if strategy in ("all", "hybrid"):
        logger.info("=" * 60)
        logger.info("STRATEGY C: HYBRID (MM + SELECTIVE HOLD)")
        logger.info("=" * 60)

        for spread in [2, 3, 4]:
            for hold_edge in [0.03, 0.05, 0.08, 0.10]:
                for gate in ["ALL"]:
                    label = f"hybrid_s{spread}_e{hold_edge}_g{gate}"
                    df = backtest_hybrid(
                        trades_by_ticker, predictions, game_map, tipoff_times,
                        spread_width=spread, hold_edge_threshold=hold_edge,
                        confidence_gate=gate,
                    )
                    m = compute_metrics(df, label)
                    m["params"] = f"spread={spread}, hold_edge={hold_edge}, gate={gate}"
                    all_metrics.append(m)
                    if m["n_trades"] > 0:
                        logger.info(f"  {label}: N={m['n_trades']}, PnL=${m['total_pnl']:.2f}, "
                                    f"Sharpe={m['sharpe']:.2f}, Win={m['win_rate']:.1f}%")

    # ── Summary ───────────────────────────────────────────────────────────────
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df = metrics_df.sort_values("sharpe", ascending=False)
    metrics_path = OUTPUT_DIR / "strategy_comparison.csv"
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"\nSaved comparison → {metrics_path}")

    # Print top 10
    logger.info("\n" + "=" * 70)
    logger.info("TOP 10 STRATEGIES BY SHARPE")
    logger.info("=" * 70)
    top = metrics_df[metrics_df["n_trades"] > 5].head(10)
    for _, r in top.iterrows():
        logger.info(
            f"  {r['strategy']:<35} | N={r['n_trades']:>3} | "
            f"PnL=${r['total_pnl']:>8.2f} | Sharpe={r['sharpe']:>6.2f} | "
            f"Win={r['win_rate']:>5.1f}% | DD=${r['max_drawdown']:>7.2f}"
        )

    # Generate equity curve for best of each type
    logger.info("\nGenerating detailed results for best configs...")
    best_configs = {}
    for prefix in ["taker", "maker", "hybrid"]:
        candidates = metrics_df[
            (metrics_df["strategy"].str.startswith(prefix)) & (metrics_df["n_trades"] > 5)
        ]
        if not candidates.empty:
            best_configs[prefix] = candidates.iloc[0]["strategy"]

    # Re-run best configs and save detail
    for strat_type, label in best_configs.items():
        # Parse params from label
        if strat_type == "taker":
            parts = label.replace("taker_h", "").split("_b")
            hours = float(parts[0])
            rest = parts[1].split("_g")
            buffer = float(rest[0])
            gate = rest[1]
            df = backtest_taker(
                trades_by_ticker, predictions, game_map, tipoff_times,
                decision_hours=hours, min_edge_buffer=buffer,
                kelly_frac=KELLY_FRACTION, confidence_gate=gate,
            )
        elif strat_type == "maker":
            parts = label.replace("maker_s", "").split("_i")
            spread = int(parts[0])
            rest = parts[1].split("_g")
            max_inv = int(rest[0])
            gate = rest[1]
            df = backtest_maker(
                trades_by_ticker, predictions, game_map, tipoff_times,
                spread_width=spread, max_inventory=max_inv,
                confidence_gate=gate,
            )
        elif strat_type == "hybrid":
            parts = label.replace("hybrid_s", "").split("_e")
            spread = int(parts[0])
            rest = parts[1].split("_g")
            hold_edge = float(rest[0])
            gate = rest[1]
            df = backtest_hybrid(
                trades_by_ticker, predictions, game_map, tipoff_times,
                spread_width=spread, hold_edge_threshold=hold_edge,
                confidence_gate=gate,
            )
        else:
            continue

        detail_path = OUTPUT_DIR / f"best_{strat_type}_detail.csv"
        df.to_csv(detail_path, index=False)
        logger.info(f"  Saved {strat_type} detail → {detail_path}")

    return metrics_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading strategy backtest")
    parser.add_argument("--strategy", default="all", choices=["all", "taker", "maker", "hybrid"])
    args = parser.parse_args()
    run_backtest(strategy=args.strategy)
