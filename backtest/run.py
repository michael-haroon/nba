"""
backtest/run.py
---------------
NBA Kalshi market-making backtest.

For each game × model (lgbm, logreg, xgb, catboost):
  1. Load per-model OOF probability (no data leakage).
  2. Fetch hourly candlesticks from market open through occurrence_datetime.
  3. Use the last candle before tipoff as the opening book.
  4. Compute bid/ask quotes via compute_quotes().
  5. Fetch pre-game trades and simulate fills.
  6. Compute two P&L scenarios: hold (settle at 0/100) and exit (close at last mid).

Usage:
    python -m backtest.run [--season 2025-26] [--output backtest/output]
                           [--models lgbm,logreg,xgb,catboost]

Output:
    backtest/output/backtest_results.csv  — one row per game × model
    backtest/output/model_comparison.csv  — one row per model summary
    backtest/output/report.txt            — text comparison table
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.kalshi_client import make_client
from backtest.quoting import compute_quotes, extract_book_top, parse_candle_book, candle_mid_cents
from backtest.match_markets import build_ticker_index, match_game_to_ticker


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_CONTRACTS = 100
KALSHI_FEE_CENTS_PER_CONTRACT = 0.07  # cents
MIN_FILL_SIZE = 1.0
TRADES_PER_MARKET = 1000


# ── Path constants ────────────────────────────────────────────────────────────

PROJECT_ROOT  = Path(__file__).resolve().parents[1]
MODELS_DIR    = PROJECT_ROOT / "output" / "nba"
OOF_PATH      = PROJECT_ROOT / "output" / "nba" / "nba_winner_oof.csv"
FEATURES_PATH = PROJECT_ROOT / "output" / "features" / "winner" / "game_features.parquet"
FEATURE_LIST  = PROJECT_ROOT / "output" / "features" / "winner" / "filtered" / "feature_list.txt"

_MODEL_FILES = {
    "lgbm":     "winner_lgbm.joblib",
    "logreg":   "winner_logreg.joblib",
    "xgb":      "winner_xgb.joblib",
    "catboost": "winner_catboost.joblib",
}


# ── Model helpers ─────────────────────────────────────────────────────────────

def _load_models() -> dict:
    """Load all available winner joblib models."""
    import joblib
    models = {}
    for name, fname in _MODEL_FILES.items():
        path = MODELS_DIR / fname
        if not path.exists():
            continue
        try:
            models[name] = joblib.load(path)
            print(f"  loaded {name} ({type(models[name]).__name__})")
        except Exception as e:
            print(f"  skip {name}: {e}")
    if not models:
        raise RuntimeError(f"No models found in {MODELS_DIR}")
    return models


def _feature_list() -> list[str]:
    return FEATURE_LIST.read_text().strip().splitlines()


def _needs_imputation(name: str) -> bool:
    return name in {"logreg"}


# ── Per-model predictions ─────────────────────────────────────────────────────

def load_per_model_predictions(season: Optional[str] = None) -> dict[str, pd.DataFrame]:
    """
    Return a dict keyed by model name. Each value is a DataFrame with columns:
        game_date, home_team_abbr, away_team_abbr, target_winner,
        home_win_prob, season, index

    OOF predictions are used where available (no leakage). For games not in
    the OOF CSV, fall back to direct inference.
    """
    features = _feature_list()

    df = pd.read_parquet(FEATURES_PATH)
    df = df[df["target_winner"].notna()].reset_index(drop=False)

    if season:
        df = df[df["season"] == season].copy()

    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date

    # Load OOF CSV once — columns: model, index, season, y_true, y_pred
    oof_by_model: dict[str, dict[int, float]] = {m: {} for m in _MODEL_FILES}
    if OOF_PATH.exists():
        oof = pd.read_csv(OOF_PATH)
        for model_name, grp in oof.groupby("model"):
            if model_name in oof_by_model:
                oof_by_model[model_name] = dict(zip(grp["index"], grp["y_pred"]))

    # For any model, identify rows missing from OOF and run direct inference
    all_missing_idx = set()
    for model_name in _MODEL_FILES:
        covered = set(oof_by_model[model_name].keys())
        missing = set(df["index"]) - covered
        all_missing_idx |= missing

    inferred: dict[str, dict[int, float]] = {m: {} for m in _MODEL_FILES}
    if all_missing_idx:
        print(f"  {len(all_missing_idx)} games need direct inference (no OOF coverage)")
        models_loaded = _load_models()
        sub = df[df["index"].isin(all_missing_idx)].copy()
        X_base = sub[features].copy()

        for name, mdl in models_loaded.items():
            X_in = X_base.copy()
            if _needs_imputation(name):
                X_in = X_in.fillna(X_in.median())
            proba = mdl.predict_proba(X_in)[:, 1]
            for idx, prob in zip(sub["index"], proba):
                inferred[name][idx] = float(prob)

    meta_cols = ["game_date", "home_team_abbr", "away_team_abbr",
                 "target_winner", "season", "index"]

    result: dict[str, pd.DataFrame] = {}
    for model_name in _MODEL_FILES:
        prob_map = {**oof_by_model[model_name], **inferred[model_name]}
        sub = df.copy()
        sub["home_win_prob"] = sub["index"].map(prob_map)
        sub = sub[sub["home_win_prob"].notna()]
        result[model_name] = sub[meta_cols + ["home_win_prob"]].reset_index(drop=True)

    return result


# ── Kalshi helpers ────────────────────────────────────────────────────────────

def _get_all_nba_markets(client) -> list[dict]:
    """Paginate through all KXNBAGAME markets."""
    all_markets = []
    cursor = None
    while True:
        params = {"series_ticker": "KXNBAGAME", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        result = client.get_markets(**params)
        all_markets.extend(result["markets"])
        cursor = result.get("cursor")
        if not cursor or len(result["markets"]) < 200:
            break
    return all_markets


def _fetch_candlesticks(client, ticker: str, occurrence_datetime: str) -> list[dict]:
    """
    Fetch hourly candlesticks from market open through occurrence_datetime.
    Returns list of candle dicts, or empty list on failure.
    """
    import dateutil.parser

    try:
        end_dt = dateutil.parser.parse(occurrence_datetime)
        # Use a 7-day window before tipoff to capture market open
        start_dt = end_dt - pd.Timedelta(days=7)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        resp = client.get_candlesticks(
            "KXNBAGAME", ticker, start_ts, end_ts, period_interval=60
        )
        return resp.get("candlesticks", [])
    except Exception as e:
        # Try historical endpoint for settled markets
        try:
            resp = client.get_historical_candlesticks(
                ticker, start_ts, end_ts, period_interval=60
            )
            return resp.get("candlesticks", [])
        except Exception as e2:
            print(f"    [warn] candlestick fetch failed for {ticker}: {e2}")
            return []


def _fetch_trades(client, ticker: str) -> list[dict]:
    """Fetch up to TRADES_PER_MARKET trades for a ticker."""
    try:
        result = client.get_trades(ticker=ticker, limit=TRADES_PER_MARKET)
        return result.get("trades", [])
    except Exception:
        try:
            result = client.get_historical_trades(ticker=ticker, limit=TRADES_PER_MARKET)
            return result.get("trades", [])
        except Exception as e:
            print(f"    [warn] trade fetch failed for {ticker}: {e}")
            return []


# ── Simulation ────────────────────────────────────────────────────────────────

def _parse_occurrence_ts(occurrence_datetime: str) -> float:
    """Parse ISO occurrence_datetime to Unix timestamp."""
    import dateutil.parser
    try:
        return dateutil.parser.parse(occurrence_datetime).timestamp()
    except Exception:
        return float("inf")


def simulate_game(
    win_prob: float,
    candles: list[dict],
    trades: list[dict],
    occurrence_datetime: str,
    market_result: str,  # "yes" or "no"
    ticker: str,
) -> dict:
    """
    Simulate market-making for a single game.

    Returns a dict with both hold and exit P&L scenarios.
    """
    tipoff_ts = _parse_occurrence_ts(occurrence_datetime)

    # ── Book from last candle before tipoff ───────────────────────────────────
    book_bid: Optional[int] = None
    book_ask: Optional[int] = None
    exit_price_cents: Optional[int] = None
    n_candles = 0

    if candles:
        # Filter candles to those before tipoff
        pre_candles = []
        for c in candles:
            # Candle end_period_ts or start_period_ts
            c_ts = c.get("end_period_ts") or c.get("start_period_ts") or 0
            if isinstance(c_ts, str):
                try:
                    import dateutil.parser as dp
                    c_ts = dp.parse(c_ts).timestamp()
                except Exception:
                    c_ts = 0
            if float(c_ts) <= tipoff_ts:
                pre_candles.append(c)

        n_candles = len(pre_candles)
        if pre_candles:
            last = pre_candles[-1]
            book_bid, book_ask = parse_candle_book(last)
            exit_price_cents = candle_mid_cents(last)

    # Sanitize book
    if book_bid is not None and book_ask is not None and book_bid >= book_ask:
        book_bid = None
        book_ask = None

    quote = compute_quotes(win_prob, book_bid, book_ask)

    # ── Filter to pre-game trades ─────────────────────────────────────────────
    pre_trades = []
    for t in trades:
        ct = t.get("created_time", "")
        try:
            import dateutil.parser as dp
            ct_ts = dp.parse(ct).timestamp() if ct else 0.0
        except Exception:
            ct_ts = 0.0
        if ct_ts < tipoff_ts:
            pre_trades.append(t)

    n_pre_game_trades = len(pre_trades)

    # ── Fill simulation ───────────────────────────────────────────────────────
    buy_fills: list[dict] = []
    sell_fills: list[dict] = []
    net_inventory = 0.0

    for t in pre_trades:
        try:
            trade_price = round(float(t["yes_price_dollars"]) * 100)
            size = float(t.get("count_fp", 1))
            taker_outcome_side = t.get("taker_outcome_side", "") or t.get("taker_side", "")
        except (ValueError, KeyError):
            continue

        if size < MIN_FILL_SIZE:
            continue

        if taker_outcome_side == "yes":
            # Taker is BUYING YES (lifting the ask). We are the passive SELLER.
            # Fill if trade price >= our ask.
            if trade_price >= quote.ask:
                room = MAX_CONTRACTS + min(net_inventory, 0)
                fill_sz = min(size, max(room, 0))
                if fill_sz > 0:
                    sell_fills.append({"price": quote.ask, "size": fill_sz})
                    net_inventory -= fill_sz

        elif taker_outcome_side == "no":
            # Taker is SELLING YES (hitting the bid). We are the passive BUYER.
            # Fill if trade price <= our bid.
            if trade_price <= quote.bid:
                room = MAX_CONTRACTS - max(net_inventory, 0)
                fill_sz = min(size, max(room, 0))
                if fill_sz > 0:
                    buy_fills.append({"price": quote.bid, "size": fill_sz})
                    net_inventory += fill_sz

    total_bought = sum(f["size"] for f in buy_fills)
    total_sold   = sum(f["size"] for f in sell_fills)
    avg_buy  = (sum(f["price"] * f["size"] for f in buy_fills)  / total_bought) if buy_fills  else 0.0
    avg_sell = (sum(f["price"] * f["size"] for f in sell_fills) / total_sold)   if sell_fills else 0.0

    # ── Settlement ────────────────────────────────────────────────────────────
    settlement_price = 100 if market_result == "yes" else 0

    # hold scenario
    pnl_buys_hold  = (settlement_price - avg_buy)  * total_bought if buy_fills  else 0.0
    pnl_sells_hold = (avg_sell - settlement_price)  * total_sold   if sell_fills else 0.0
    gross_hold = pnl_buys_hold + pnl_sells_hold

    # exit scenario — use last candle mid; fall back to settlement if unavailable
    exit_px = exit_price_cents if exit_price_cents is not None else settlement_price
    pnl_buys_exit  = (exit_px - avg_buy)  * total_bought if buy_fills  else 0.0
    pnl_sells_exit = (avg_sell - exit_px)  * total_sold   if sell_fills else 0.0
    gross_exit = pnl_buys_exit + pnl_sells_exit

    fees = (total_bought + total_sold) * KALSHI_FEE_CENTS_PER_CONTRACT
    net_hold = gross_hold - fees
    net_exit = gross_exit - fees

    return {
        "ticker":               ticker,
        "fair_cents":           quote.fair,
        "bid_cents":            quote.bid,
        "ask_cents":            quote.ask,
        "book_bid":             book_bid,
        "book_ask":             book_ask,
        "spread_cents":         quote.spread,
        "total_bought":         total_bought,
        "total_sold":           total_sold,
        "avg_buy_price":        round(avg_buy,  2),
        "avg_sell_price":       round(avg_sell, 2),
        "settlement_price":     settlement_price,
        "exit_price_cents":     exit_px,
        "gross_pnl_hold_cents": round(gross_hold, 2),
        "gross_pnl_exit_cents": round(gross_exit, 2),
        "net_pnl_hold_cents":   round(net_hold, 2),
        "net_pnl_exit_cents":   round(net_exit, 2),
        "fees_cents":           round(fees,  2),
        "home_win_prob":        round(win_prob, 4),
        "n_pre_game_trades":    n_pre_game_trades,
        "n_candles":            n_candles,
    }


# ── Report ────────────────────────────────────────────────────────────────────

def _sharpe(series: pd.Series) -> float:
    if len(series) < 2 or series.std() == 0:
        return 0.0
    return float(series.mean() / series.std() * np.sqrt(252))


def _max_drawdown(series: pd.Series) -> float:
    cum = series.cumsum()
    peak = cum.cummax()
    dd = (cum - peak)
    return float(dd.min()) if len(dd) > 0 else 0.0


def _print_report(df: pd.DataFrame, output_path: Path) -> None:
    rows = []
    for model_name, grp in df.groupby("model"):
        filled = grp[(grp["total_bought"] > 0) | (grp["total_sold"] > 0)]
        n_games  = len(grp)
        n_filled = len(filled)

        net_hold_series = filled["net_pnl_hold_cents"] if not filled.empty else pd.Series([], dtype=float)
        net_exit_series = filled["net_pnl_exit_cents"] if not filled.empty else pd.Series([], dtype=float)

        rows.append({
            "Model":          model_name,
            "Games":          n_games,
            "Filled":         n_filled,
            "Net P&L Hold $": round(net_hold_series.sum() / 100, 2),
            "Net P&L Exit $": round(net_exit_series.sum() / 100, 2),
            "Sharpe Hold":    round(_sharpe(net_hold_series), 3),
            "Sharpe Exit":    round(_sharpe(net_exit_series), 3),
            "Max DD Hold $":  round(_max_drawdown(net_hold_series) / 100, 2),
            "Max DD Exit $":  round(_max_drawdown(net_exit_series) / 100, 2),
            "Win% Hold":      round((net_hold_series > 0).mean() * 100, 1) if not filled.empty else 0.0,
            "Win% Exit":      round((net_exit_series > 0).mean() * 100, 1) if not filled.empty else 0.0,
        })

    comparison = pd.DataFrame(rows)

    header = (
        f"{'Model':<12} | {'Games':>5} | {'Filled':>6} | "
        f"{'Net P&L Hold':>14} | {'Net P&L Exit':>14} | "
        f"{'Sharpe Hold':>12} | {'Sharpe Exit':>12} | "
        f"{'Max DD Hold':>12} | {'Max DD Exit':>12} | "
        f"{'Win% Hold':>10} | {'Win% Exit':>10}"
    )
    sep = "-" * len(header)
    lines = ["\nNBA KALSHI MARKET-MAKING BACKTEST — MODEL COMPARISON",
             sep, header, sep]
    for _, r in comparison.iterrows():
        lines.append(
            f"{r['Model']:<12} | {r['Games']:>5} | {r['Filled']:>6} | "
            f"{r['Net P&L Hold $']:>13.2f}$ | {r['Net P&L Exit $']:>13.2f}$ | "
            f"{r['Sharpe Hold']:>12.3f} | {r['Sharpe Exit']:>12.3f} | "
            f"{r['Max DD Hold $']:>11.2f}$ | {r['Max DD Exit $']:>11.2f}$ | "
            f"{r['Win% Hold']:>9.1f}% | {r['Win% Exit']:>9.1f}%"
        )
    lines.append(sep + "\n")
    report_text = "\n".join(lines)

    print(report_text)

    report_path = output_path / "report.txt"
    report_path.write_text(report_text)
    print(f"  Saved report -> {report_path}")

    comp_path = output_path / "model_comparison.csv"
    comparison.to_csv(comp_path, index=False)
    print(f"  Saved model_comparison -> {comp_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_backtest(
    season: str = "2025-26",
    output_dir: str = "backtest/output",
    models: list[str] | None = None,
) -> None:
    if models is None:
        models = list(_MODEL_FILES.keys())

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  NBA Kalshi Market-Making Backtest")
    print(f"  Season: {season}  Models: {', '.join(models)}")
    print(f"{'='*60}\n")

    # Per-model predictions
    print("Loading predictions...")
    all_preds = load_per_model_predictions(season=season)
    # Filter to requested models
    all_preds = {m: v for m, v in all_preds.items() if m in models}
    for m, df_m in all_preds.items():
        print(f"  {m}: {len(df_m)} games")
    print()

    # Kalshi connection
    print("Connecting to Kalshi...")
    client = make_client("prod")
    bal = client.get_balance()
    print(f"  Balance: ${bal.get('balance', 0)/100:.2f}\n")

    # All NBA markets
    print("Fetching Kalshi NBA markets...")
    all_markets = _get_all_nba_markets(client)
    finalized = [m for m in all_markets if m["status"] == "finalized"]
    print(f"  Total: {len(all_markets)}, Finalized: {len(finalized)}\n")

    ticker_index = build_ticker_index(all_markets)

    # Caches: keyed by ticker so we only hit the API once per game, not per game×model
    candles_cache: dict[str, list[dict]] = {}
    trades_cache:  dict[str, list[dict]] = {}

    results = []

    for model_name in models:
        pred_df = all_preds.get(model_name)
        if pred_df is None or pred_df.empty:
            print(f"  [{model_name}] no predictions, skipping")
            continue

        matched = 0
        unmatched = 0
        print(f"--- Model: {model_name} ---")

        for _, row in pred_df.iterrows():
            home_abbr     = row["home_team_abbr"]
            away_abbr     = row["away_team_abbr"]
            game_date     = row["game_date"]
            win_prob      = float(row["home_win_prob"])
            actual_winner = int(row["target_winner"])

            mkt = match_game_to_ticker(
                game_date, home_abbr, away_abbr, home_abbr, ticker_index
            )
            if mkt is None:
                unmatched += 1
                continue

            ticker         = mkt["ticker"]
            market_result  = mkt.get("result", "")
            occurrence_dt  = (
                mkt.get("occurrence_datetime") or
                mkt.get("close_time") or
                ""
            )

            if not market_result:
                unmatched += 1
                continue

            matched += 1

            # Fetch candles and trades — cached per ticker
            if ticker not in candles_cache:
                candles_cache[ticker] = _fetch_candlesticks(client, ticker, occurrence_dt)
                time.sleep(0.05)
            if ticker not in trades_cache:
                trades_cache[ticker] = _fetch_trades(client, ticker)
                time.sleep(0.05)

            sim = simulate_game(
                win_prob=win_prob,
                candles=candles_cache[ticker],
                trades=trades_cache[ticker],
                occurrence_datetime=occurrence_dt,
                market_result=market_result,
                ticker=ticker,
            )

            sim["model"]          = model_name
            sim["game_date"]      = str(game_date)
            sim["home_team"]      = home_abbr
            sim["away_team"]      = away_abbr
            sim["actual_home_won"] = actual_winner

            results.append(sim)

            if matched % 10 == 0:
                filled_so_far = [r for r in results
                                 if r["model"] == model_name
                                 and (r["total_bought"] + r["total_sold"]) > 0]
                cum_pnl = sum(r["net_pnl_hold_cents"] for r in results
                              if r["model"] == model_name)
                print(f"  [{matched} matched, {unmatched} skip] "
                      f"filled={len(filled_so_far)} cum_pnl_hold=${cum_pnl/100:.2f}")

        print(f"  {model_name}: matched={matched}, unmatched={unmatched}\n")

    if not results:
        print("  No results to summarize.")
        return

    # Reorder columns
    col_order = [
        "model", "game_date", "home_team", "away_team", "ticker",
        "fair_cents", "bid_cents", "ask_cents", "book_bid", "book_ask", "spread_cents",
        "total_bought", "total_sold", "avg_buy_price", "avg_sell_price",
        "settlement_price", "exit_price_cents",
        "gross_pnl_hold_cents", "gross_pnl_exit_cents",
        "net_pnl_hold_cents", "net_pnl_exit_cents",
        "fees_cents", "home_win_prob", "actual_home_won",
        "n_pre_game_trades", "n_candles",
    ]
    df = pd.DataFrame(results)
    # Add any columns missing from col_order at the end
    extra = [c for c in df.columns if c not in col_order]
    df = df[[c for c in col_order if c in df.columns] + extra]

    results_path = output_path / "backtest_results.csv"
    df.to_csv(results_path, index=False)
    print(f"  Saved results -> {results_path}")

    _print_report(df, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Kalshi backtest")
    parser.add_argument("--season",  default="2025-26")
    parser.add_argument("--output",  default="backtest/output")
    parser.add_argument("--models",  default="lgbm,logreg,xgb,catboost",
                        help="Comma-separated list of models to run")
    args = parser.parse_args()
    run_backtest(
        season=args.season,
        output_dir=args.output,
        models=args.models.split(","),
    )
