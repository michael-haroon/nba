"""
pregame_brier_vs_market.py
---------------------------
Does the NBA classical winner ensemble beat the Kalshi market on PREGAME home-win
pricing, in Brier-score units?

This is independent of backtest/run.py's market-making PnL simulation (whose
accuracy the user distrusts) — it builds its own join from three sources:

  1. Model: per-model OOF home_win_prob from output/nba/nba_winner_oof.csv,
     joined to output/features/winner/game_features.parquet by row index
     (OOF's "index" column is the pre-filter row position, per
     backtest/run.py::load_per_model_predictions).
  2. Tipoff time: data_curation/data/SummaryGameMeta.parquet's gameTimeUTC,
     joined by game_id. The Kalshi historical /markets endpoint does NOT
     return occurrence_datetime (only the live-window /markets does), so this
     is the only source of an exact tipoff timestamp for aged-out markets.
  3. Market: our own freshly-downloaded KXNBAGAME candlesticks
     (kalshi_history/KXNBAGAME/historical/candlesticks_batch_*.parquet,
     pulled directly from Kalshi via backtest/download_kalshi_history.py,
     2026-09-02). Market probability = (yes_bid_close + yes_ask_close) / 2
     from the LAST candle at or before tipoff (the closing pregame line) —
     same convention as MLB's kalshi_topbook_accuracy.py. Candle columns are
     stored as str; cast to float before any arithmetic.

KXNBAGAME lists one market per team (YES = that team wins) per game. Where
both sides have a valid pregame quote, this averages the two implied
home-win probabilities (home-YES mid, and 1 - away-YES mid) for a more
robust estimate; where only one side quoted, uses that one.

Run:
    python3 scripts/pregame_brier_vs_market.py [--local-dir DIR]
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.match_markets import _parse_ticker  # noqa: E402

OOF_PATH = ROOT / "output" / "nba" / "nba_winner_oof.csv"
FEATURES_PATH = ROOT / "output" / "features" / "winner" / "game_features.parquet"
META_PATH = ROOT / "data_curation" / "data" / "SummaryGameMeta.parquet"

S3_BUCKET = "nba-265753586044-us-east-1-an"
S3_PREFIX = "kalshi_history/KXNBAGAME/historical"


def load_candles(local_dir: str | None) -> pd.DataFrame:
    if local_dir:
        paths = glob.glob(str(Path(local_dir) / "candlesticks_batch_*.parquet"))
        frames = [pd.read_parquet(p) for p in paths]
    else:
        import boto3
        s3 = boto3.client("s3", region_name="us-east-1")
        paths = []
        token = None
        while True:
            kw = {"Bucket": S3_BUCKET, "Prefix": f"{S3_PREFIX}/candlesticks_batch_"}
            if token:
                kw["ContinuationToken"] = token
            resp = s3.list_objects_v2(**kw)
            paths.extend(o["Key"] for o in resp.get("Contents", []))
            token = resp.get("NextContinuationToken")
            if not token:
                break
        print(f"  {len(paths)} candlestick files in s3://{S3_BUCKET}/{S3_PREFIX}/")
        frames = []
        for i, key in enumerate(paths):
            buf = s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
            frames.append(pd.read_parquet(pd.io.common.BytesIO(buf)))
            if (i + 1) % 500 == 0:
                print(f"    loaded {i+1}/{len(paths)}")
    df = pd.concat(frames, ignore_index=True)
    for c in ("yes_bid_close", "yes_ask_close", "end_period_ts"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["yes_bid_close", "yes_ask_close", "end_period_ts"])
    df["mid"] = (df["yes_bid_close"] + df["yes_ask_close"]) / 2.0
    return df[["market_ticker", "end_period_ts", "mid"]]


def parse_candle_tickers(candles: pd.DataFrame) -> pd.DataFrame:
    """Attach game_date/home/away/yes_team parsed from market_ticker to every candle row."""
    tickers = candles["market_ticker"].unique()
    parsed = {t: _parse_ticker(t) for t in tickers}
    parsed = {t: p for t, p in parsed.items() if p is not None}
    print(f"  {len(parsed)}/{len(tickers)} tickers parsed")
    tick_df = pd.DataFrame([{"market_ticker": t, **p} for t, p in parsed.items()])
    return candles.merge(tick_df, on="market_ticker", how="inner")


def asof_pregame_mid(games: pd.DataFrame, side_candles: pd.DataFrame, out_col: str) -> pd.DataFrame:
    """Vectorized last-candle-at-or-before-tipoff join via merge_asof, exact-matched
    on (game_date, home, away) and asof-matched on tipoff_ts <= end_period_ts."""
    side = side_candles.sort_values("end_period_ts")
    g = games.sort_values("tipoff_ts").reset_index(drop=True)
    g["tipoff_ts"] = g["tipoff_ts"].astype("int64")
    out = pd.merge_asof(
        g, side[["game_date", "home", "away", "end_period_ts", "mid"]],
        left_on="tipoff_ts", right_on="end_period_ts",
        left_by=["game_date", "home_team_abbr", "away_team_abbr"],
        right_by=["game_date", "home", "away"],
        direction="backward",
    )
    return out.rename(columns={"mid": out_col}).drop(columns=["home", "away", "end_period_ts"], errors="ignore")


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-dir", default=None,
                         help="Local dir of candlesticks_batch_*.parquet instead of S3")
    args = parser.parse_args()

    print("Loading OOF predictions + game features + tipoff times...")
    oof = pd.read_csv(OOF_PATH)
    feat = pd.read_parquet(
        FEATURES_PATH,
        columns=["game_id", "game_date", "home_team_abbr", "away_team_abbr", "target_winner"],
    ).reset_index()  # "index" = pre-filter row position, matches OOF's index column
    meta = pd.read_parquet(META_PATH, columns=["gameId", "gameTimeUTC"])
    feat = feat.merge(meta, left_on="game_id", right_on="gameId", how="left")
    # gameTimeUTC parses to datetime64[us] on this pandas version, not [ns] —
    # .astype("int64") // 1e9 silently undershoots 1000x (same gotcha as MLB's
    # kalshi_pnl_backtest.py::to_unix_s). Resolution-agnostic instead, and NaT
    # must be masked explicitly since (NaT - epoch) // Timedelta does NOT give NaN.
    tipoff_dt = pd.to_datetime(feat["gameTimeUTC"], utc=True, errors="coerce")
    tipoff_ts = (tipoff_dt - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")
    feat["tipoff_ts"] = tipoff_ts.where(tipoff_dt.notna())
    feat["game_date"] = pd.to_datetime(feat["game_date"]).dt.date

    print("Loading Kalshi KXNBAGAME candlesticks (our own pull, 2026-09-02)...")
    candles = load_candles(args.local_dir)
    candles = parse_candle_tickers(candles)
    home_side_candles = candles[candles["yes_team"] == candles["home"]]
    away_side_candles = candles[candles["yes_team"] == candles["away"]]

    games = feat.dropna(subset=["target_winner", "tipoff_ts"]).copy()
    games = asof_pregame_mid(games, home_side_candles, "home_side_mid")
    games = asof_pregame_mid(games, away_side_candles, "away_side_mid")
    implied_home = games[["home_side_mid", "away_side_mid"]].copy()
    implied_home["away_side_mid"] = 1 - implied_home["away_side_mid"]
    games["market_home_prob"] = implied_home.mean(axis=1, skipna=True)
    games = games.dropna(subset=["market_home_prob"])
    print(f"  {len(games)} games with a matched pregame market quote "
          f"({games['game_date'].min()} .. {games['game_date'].max()})")

    models = sorted(oof["model"].unique())
    results = []
    for model_name in models:
        m = oof[oof.model == model_name][["index", "y_pred"]].rename(columns={"y_pred": "home_win_prob"})
        j = games.merge(m, on="index", how="inner").dropna(subset=["home_win_prob"])

        y = j["target_winner"].to_numpy(float)
        p_model = j["home_win_prob"].to_numpy(float)
        p_market = j["market_home_prob"].to_numpy(float)

        results.append({
            "model": model_name,
            "n_games": len(j),
            "date_range": f"{j.game_date.min()} .. {j.game_date.max()}" if len(j) else "n/a",
            "brier_model": brier(p_model, y),
            "brier_market": brier(p_market, y),
            "brier_delta_model_minus_market": brier(p_model, y) - brier(p_market, y),
            "acc_model": float(((p_model > 0.5).astype(int) == y).mean()),
            "acc_market": float(((p_market > 0.5).astype(int) == y).mean()),
        })

    res_df = pd.DataFrame(results)
    pd.set_option("display.width", 140)
    print("\n" + "=" * 100)
    print("NBA PREGAME WIN PRICING — MODEL vs KALSHI MARKET (Brier score, lower is better)")
    print("=" * 100)
    print(res_df.to_string(index=False))
    print("\nNegative brier_delta_model_minus_market = model BEATS the market.")
    print("Positive = model LOSES to the market (market is better calibrated/accurate).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
