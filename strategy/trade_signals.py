"""
trade_signals.py
----------------
Generate trade signals combining model predictions (winner + spread) with
FLB structural bias signals.

Models price the market independently. FLB adjusts position confidence.
Winner and spread are treated as separate markets with separate sizing.

Usage:
    # Show model fair prices only (no Kalshi prices needed)
    python -m strategy.trade_signals SAS NYK

    # With Kalshi prices
    python -m strategy.trade_signals SAS NYK \\
        --spread-markets "4.5:0.51:0.50" "3.5:0.53:0.48" \\
        --winner-market "0.62:0.39" \\
        --bankroll 1000 --check-flb
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

import strategy.config as _cfg
from strategy.config import (
    KELLY_FRACTION, MIN_EDGE_PCT, MAX_POSITION_PCT,
    SPREAD_RESID_DF, SPREAD_RESID_SCALE,
    WINNER_STD_THRESHOLDS, WINNER_CONFIDENCE_MULTIPLIERS,
    FLB_AGREE_MULT, FLB_DISAGREE_MULT, FLB_NEUTRAL_MULT,
)
from strategy.predict import build_matchup_row
from strategy.ensemble import predict_from_pkl


def _setup_logging():
    log_dir = _cfg.OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "trade_signals.log",
        level=logging.INFO,
        format="%(asctime)s %(message)s",
    )
logger = logging.getLogger(__name__)

FLB_SIGNALS_DIR = Path(__file__).resolve().parents[1] / "backtest" / "output" / "flb" / "signals"


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TradeSignal:
    market_type: str        # "winner" | "spread"
    label: str              # e.g. "SAS wins by 4.5+"
    side: str               # "YES" | "NO"
    model_prob: float       # model's fair probability for the YES side
    kalshi_yes: float       # Kalshi yes price
    kalshi_no: float        # Kalshi no price
    edge: float             # signed edge on the recommended side
    kelly_base: float       # raw Kelly fraction
    kelly_scaled: float     # after confidence and FLB scaling
    bet_size: float         # dollar amount (kelly_scaled * bankroll, capped)
    confidence: str         # "HIGH" | "MEDIUM" | "LOW" (winner) | "FIXED" (spread)
    flb_status: str         # "AGREES" | "DISAGREES" | "NO SIGNAL"
    flb_edge_cents: float   # FLB edge in cents (0 if no signal)
    actionable: bool        # edge >= MIN_EDGE_PCT


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_bundle(target: str) -> dict:
    pkl = _cfg.OUTPUT_DIR / "ensemble" / f"{target}_ensemble_models.pkl"
    if not pkl.exists():
        raise FileNotFoundError(f"No pkl for {target} at {pkl}")
    with open(pkl, "rb") as f:
        return pickle.load(f)


def _get_features(bundle: dict) -> list[str]:
    return sorted(set(f for m in bundle["models"] for f in m["features"]))


def _predict(bundle: dict, X: pd.DataFrame, target: str) -> float:
    pkl = _cfg.OUTPUT_DIR / "ensemble" / f"{target}_ensemble_models.pkl"
    return float(predict_from_pkl(pkl, X)[0])


def _ensemble_std(bundle: dict, X: pd.DataFrame) -> float:
    """Std of individual model predictions — useful for winner model confidence."""
    preds = []
    for m in bundle["models"]:
        X_sub = X[m["features"]].copy()
        if m["impute_median"]:
            X_sub = X_sub.fillna(pd.Series(m["impute_median"]))
        if m["needs_scaling"]:
            X_sub = (X_sub - pd.Series(m["scale_mean"])) / pd.Series(m["scale_std"])
        if bundle["task"] == "classification":
            p = m["model"].predict_proba(X_sub)[:, 1][0]
        else:
            p = m["model"].predict(X_sub)[0]
        preds.append(p)
    return float(np.std(preds)) if len(preds) > 1 else 0.0


# ── Pricing ───────────────────────────────────────────────────────────────────

def price_winner_market(win_prob: float, ensemble_std: float) -> tuple[float, str]:
    """Return (model_yes_prob, confidence_tier)."""
    lo, hi = WINNER_STD_THRESHOLDS
    if ensemble_std <= lo:
        confidence = "HIGH"
    elif ensemble_std <= hi:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    return win_prob, confidence


def price_spread_market(spread_pred: float, threshold: float) -> float:
    """P(actual spread > threshold) using t-distribution residual model."""
    return float(1 - t_dist.cdf((threshold - spread_pred) / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))


# ── Edge and Kelly ────────────────────────────────────────────────────────────

def compute_edge(model_prob: float, kalshi_yes: float, kalshi_no: float) -> tuple[str, float, float]:
    """
    Returns (side, edge_fraction, kelly_base).
    Side is the bet direction with positive edge.
    """
    edge_yes = model_prob - kalshi_yes
    edge_no = (1 - model_prob) - kalshi_no

    if edge_yes >= edge_no:
        side = "YES"
        edge = edge_yes
        price = kalshi_yes
    else:
        side = "NO"
        edge = edge_no
        price = kalshi_no

    # Kelly for binary contract: f* = (p - price) / (1 - price)
    # where p = model prob of winning the bet, price = cost of the contract
    kelly = edge / (1.0 - price) if price < 1.0 and edge > 0 else 0.0
    return side, edge, kelly


def check_flb_agreement(home: str, away: str, side: str, model_side: str) -> tuple[str, float]:
    """
    Look up the latest FLB signal for this matchup.
    Returns (status, flb_edge_cents).
    side: "YES" | "NO"  (what model recommends)
    model_side: which team model favors (e.g. "SAS")
    """
    if not FLB_SIGNALS_DIR.exists():
        return "NO SIGNAL", 0.0

    signal_files = sorted(FLB_SIGNALS_DIR.glob("*.json"))
    if not signal_files:
        return "NO SIGNAL", 0.0

    latest = signal_files[-1]
    try:
        signals = json.loads(latest.read_text())
    except Exception:
        return "NO SIGNAL", 0.0

    # Match on home/away team abbreviations in ticker
    home_u = home.upper()
    away_u = away.upper()
    relevant = [
        s for s in signals
        if home_u in s["ticker"] and away_u in s["ticker"]
        and s["hours_to_tipoff"] > 0
    ]
    if not relevant:
        return "NO SIGNAL", 0.0

    # Use signal for the favored team (model_side)
    match = next(
        (s for s in relevant if model_side.upper() in s["ticker"]),
        relevant[0]
    )

    flb_edge = match.get("edge_cents", 0.0)
    flb_signal = match.get("signal", "NO TRADE")

    if flb_signal == "NO TRADE" or flb_edge == 0:
        return "NO SIGNAL", flb_edge

    # FLB "FADE" = buy NO on the favored team = agrees if model says NO
    # FLB "BACK" = buy YES = agrees if model says YES
    flb_side = "NO" if flb_signal == "FADE" else "YES"
    if flb_side == side:
        return "AGREES", flb_edge
    else:
        return "DISAGREES", flb_edge


def size_position(
    kelly_base: float,
    confidence: str,
    flb_status: str,
    bankroll: float,
    market_type: str,
) -> float:
    """Quarter-Kelly with confidence scaling and position cap."""
    conf_mult = WINNER_CONFIDENCE_MULTIPLIERS.get(confidence, 1.0) if market_type == "winner" else 1.0

    flb_mult = {
        "AGREES": FLB_AGREE_MULT,
        "DISAGREES": FLB_DISAGREE_MULT,
        "NO SIGNAL": FLB_NEUTRAL_MULT,
    }[flb_status]

    scaled = kelly_base * KELLY_FRACTION * conf_mult * flb_mult
    max_frac = MAX_POSITION_PCT / 100.0
    return round(min(scaled, max_frac) * bankroll, 2)


# ── Main signal generation ────────────────────────────────────────────────────

def generate_signals(
    home: str,
    away: str,
    winner_market: tuple[float, float] | None = None,
    spread_markets: list[tuple[float, float, float]] | None = None,
    bankroll: float = 1000.0,
    check_flb: bool = False,
) -> dict:
    """
    Core signal generation.

    winner_market: (kalshi_yes, kalshi_no) or None
    spread_markets: list of (threshold, kalshi_yes, kalshi_no) or None
    """
    df = pd.read_parquet(_cfg.GAME_PARQUET)
    latest_date = df["game_date"].max().strftime("%Y-%m-%d")

    winner_bundle = _load_bundle("winner")
    spread_bundle = _load_bundle("spread")

    X_winner = build_matchup_row(df, home.upper(), away.upper(), _get_features(winner_bundle))
    X_spread = build_matchup_row(df, home.upper(), away.upper(), _get_features(spread_bundle))

    win_prob = _predict(winner_bundle, X_winner, "winner")
    spread_pred = _predict(spread_bundle, X_spread, "spread")
    winner_std = _ensemble_std(winner_bundle, X_winner)

    # Spread-implied win prob for cross-check
    spread_implied_win = float(1 - t_dist.cdf(-spread_pred / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))
    model_agree_pp = abs(win_prob - spread_implied_win) * 100

    signals: list[TradeSignal] = []

    # ── Winner market ─────────────────────────────────────────────────────────
    if winner_market is not None:
        kal_yes, kal_no = winner_market
        model_prob, confidence = price_winner_market(win_prob, winner_std)
        side, edge, kelly = compute_edge(model_prob, kal_yes, kal_no)

        favored = home if side == "YES" else away
        flb_status, flb_edge_c = ("NO SIGNAL", 0.0)
        if check_flb:
            flb_status, flb_edge_c = check_flb_agreement(home, away, side, favored)

        bet = size_position(kelly, confidence, flb_status, bankroll, "winner")
        label = f"{home} wins" if side == "YES" else f"{away} wins"
        from strategy.calibration import min_edge_for_profit
        price = kal_yes if side == "YES" else kal_no
        min_edge = min_edge_for_profit(price)
        signals.append(TradeSignal(
            market_type="winner", label=label, side=side,
            model_prob=model_prob, kalshi_yes=kal_yes, kalshi_no=kal_no,
            edge=edge, kelly_base=kelly, kelly_scaled=kelly * KELLY_FRACTION,
            bet_size=bet, confidence=confidence,
            flb_status=flb_status, flb_edge_cents=flb_edge_c,
            actionable=edge >= min_edge,
        ))

    # ── Spread markets ────────────────────────────────────────────────────────
    for threshold, kal_yes, kal_no in (spread_markets or []):
        model_prob = price_spread_market(spread_pred, threshold)
        side, edge, kelly = compute_edge(model_prob, kal_yes, kal_no)

        favored = home if threshold > 0 else away
        flb_status, flb_edge_c = ("NO SIGNAL", 0.0)
        if check_flb:
            flb_status, flb_edge_c = check_flb_agreement(home, away, side, favored)

        bet = size_position(kelly, "FIXED", flb_status, bankroll, "spread")
        dir_team = home if threshold > 0 else away
        label = f"{dir_team} by {abs(threshold)}+"
        from strategy.calibration import min_edge_for_profit
        price_used = kal_yes if side == "YES" else kal_no
        min_edge = min_edge_for_profit(price_used)
        signals.append(TradeSignal(
            market_type="spread", label=label, side=side,
            model_prob=model_prob, kalshi_yes=kal_yes, kalshi_no=kal_no,
            edge=edge, kelly_base=kelly, kelly_scaled=kelly * KELLY_FRACTION,
            bet_size=bet, confidence="FIXED",
            flb_status=flb_status, flb_edge_cents=flb_edge_c,
            actionable=edge >= min_edge,
        ))

    result = {
        "home": home.upper(), "away": away.upper(),
        "latest_date": latest_date,
        "win_prob": win_prob, "winner_std": winner_std,
        "spread_pred": spread_pred,
        "spread_implied_win": spread_implied_win,
        "model_agree_pp": model_agree_pp,
        "signals": signals,
        "bankroll": bankroll,
    }

    logger.info(
        f"{home.upper()} vs {away.upper()} | "
        f"win_prob={win_prob:.3f} | spread={spread_pred:+.1f} | "
        f"agree={model_agree_pp:.1f}pp | "
        f"signals={len([s for s in signals if s.actionable])} actionable"
    )
    return result


# ── Display ───────────────────────────────────────────────────────────────────

def print_signals(r: dict) -> None:
    home, away = r["home"], r["away"]
    W = 66

    print(f"\n{'=' * W}")
    print(f"  TRADE SIGNALS: {home} (home) vs {away} (away)")
    print(f"  Data through: {r['latest_date']} | Bankroll: ${r['bankroll']:.0f}")
    print(f"{'=' * W}")

    # Model predictions
    lo, hi = WINNER_STD_THRESHOLDS
    std = r["winner_std"]
    conf = "HIGH" if std <= lo else ("MEDIUM" if std <= hi else "LOW")
    print(f"\n  MODEL PREDICTIONS:")
    print(f"    Winner model:  P({home}) = {r['win_prob']*100:.1f}%  "
          f"[conf: {conf}, std={std:.3f}]")
    print(f"    Spread model:  {home} by {r['spread_pred']:+.1f} pts  "
          f"[σ=12.44, constant]")
    print(f"    Cross-check:   Spread implies P({home}) = {r['spread_implied_win']*100:.1f}%  "
          f"(disagree {r['model_agree_pp']:.1f}pp)")

    # Winner signals
    winner_sigs = [s for s in r["signals"] if s.market_type == "winner"]
    if winner_sigs:
        print(f"\n  WINNER MARKET:")
        print(f"  {'Market':<22} {'Model':>7} {'Kalshi Y/N':>12} {'Edge':>7} "
              f"{'Side':<4} {'Kelly$':>7} {'FLB':>10}")
        print(f"  {'-'*72}")
        for s in winner_sigs:
            flag = " ✓" if s.actionable else ""
            flb_str = f"{s.flb_status[:6]}({s.flb_edge_cents:+.0f}¢)" if s.flb_status != "NO SIGNAL" else "—"
            print(f"  {s.label:<22} {s.model_prob*100:>6.1f}%  "
                  f"{s.kalshi_yes*100:.0f}c/{s.kalshi_no*100:.0f}c  "
                  f"{s.edge*100:>+5.1f}%  {s.side:<4} "
                  f"${s.bet_size:>6.2f}  {flb_str:>10}{flag}")

    # Spread signals
    spread_sigs = [s for s in r["signals"] if s.market_type == "spread"]
    if spread_sigs:
        print(f"\n  SPREAD MARKETS (σ=12.44, formula: P = 1-Φ((t-{r['spread_pred']:+.1f})/12.44)):")
        print(f"  {'Market':<22} {'Model':>7} {'Kalshi Y/N':>12} {'Edge':>7} "
              f"{'Side':<4} {'Kelly$':>7} {'FLB':>10}")
        print(f"  {'-'*72}")
        for s in spread_sigs:
            flag = " ✓" if s.actionable else ""
            flb_str = f"{s.flb_status[:6]}({s.flb_edge_cents:+.0f}¢)" if s.flb_status != "NO SIGNAL" else "—"
            print(f"  {s.label:<22} {s.model_prob*100:>6.1f}%  "
                  f"{s.kalshi_yes*100:.0f}c/{s.kalshi_no*100:.0f}c  "
                  f"{s.edge*100:>+5.1f}%  {s.side:<4} "
                  f"${s.bet_size:>6.2f}  {flb_str:>10}{flag}")

    # Fair prices — always shown (full range 1.5 to 31.5 both sides)
    print(f"\n  FAIR PRICES (all thresholds, spread = {r['spread_pred']:+.1f}):")
    print(f"  {'Market':<22} {'P(Yes)':>8} {'Fair Yes':>9} {'Fair No':>9}")
    print(f"  {'-'*52}")
    thresholds = [t / 2 for t in range(3, 65, 2)]  # 1.5, 2.5, ..., 31.5
    for t in thresholds:
        p = price_spread_market(r["spread_pred"], t)
        label = f"{home} by {t}+"
        print(f"  {label:<22} {p*100:>7.1f}%   {p*100:>7.1f}c  {(1-p)*100:>7.1f}c")
    print(f"  {'-'*52}")
    for t in thresholds:
        p = price_spread_market(r["spread_pred"], -t)
        label = f"{away} by {t}+"
        print(f"  {label:<22} {(1-p)*100:>7.1f}%   {(1-p)*100:>7.1f}c  {p*100:>7.1f}c")

    # Recommendations
    actionable = [s for s in r["signals"] if s.actionable]
    print(f"\n  {'=' * (W-2)}")
    if actionable:
        total_exposure = sum(s.bet_size for s in actionable)
        print(f"  RECOMMENDED TRADES  (edge ≥ {MIN_EDGE_PCT}%):")
        for i, s in enumerate(sorted(actionable, key=lambda x: x.edge, reverse=True), 1):
            flb_note = f" | FLB {s.flb_status.lower()}" if s.flb_status != "NO SIGNAL" else ""
            print(f"  {i}. {s.label} → {s.side} at "
                  f"{(s.kalshi_yes if s.side=='YES' else s.kalshi_no)*100:.0f}¢ "
                  f"| ${s.bet_size:.2f} | edge {s.edge*100:.1f}%{flb_note}")
        print(f"\n  Total exposure: ${total_exposure:.2f} "
              f"({total_exposure/r['bankroll']*100:.1f}% of bankroll)")
    else:
        print(f"  No trades above {MIN_EDGE_PCT}% edge threshold.")
    print(f"{'=' * W}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate NBA trade signals (winner + spread models + FLB)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m strategy.trade_signals SAS NYK
  python -m strategy.trade_signals SAS NYK --spread-markets "4.5:0.51:0.50" "3.5:0.53:0.48"
  python -m strategy.trade_signals SAS NYK --winner-market "0.62:0.39" --bankroll 1000 --check-flb
        """,
    )
    parser.add_argument("home", help="Home team abbreviation (e.g. SAS)")
    parser.add_argument("away", help="Away team abbreviation (e.g. NYK)")
    parser.add_argument(
        "--winner-market", default=None,
        help="Kalshi winner prices as 'yes:no' e.g. '0.62:0.39'",
    )
    parser.add_argument(
        "--spread-markets", nargs="*", default=None,
        help="Spread markets as 'threshold:yes:no' e.g. '4.5:0.51:0.50' (negative threshold = away wins by X+)",
    )
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--check-flb", action="store_true",
                        help="Check FLB scanner signals for agreement")
    args = parser.parse_args()

    winner_market = None
    if args.winner_market:
        parts = args.winner_market.split(":")
        winner_market = (float(parts[0]), float(parts[1]))

    spread_markets = None
    if args.spread_markets:
        spread_markets = []
        for m in args.spread_markets:
            parts = m.split(":")
            spread_markets.append((float(parts[0]), float(parts[1]), float(parts[2])))

    result = generate_signals(
        home=args.home, away=args.away,
        winner_market=winner_market,
        spread_markets=spread_markets,
        bankroll=args.bankroll,
        check_flb=args.check_flb,
    )
    print_signals(result)
