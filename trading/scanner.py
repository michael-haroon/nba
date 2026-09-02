"""
trading/scanner.py
------------------
Multi-market scanner. Generates signals across ALL market types where we have
a model and an edge. Diversification is the goal: spread bets across as many
uncorrelated (or weakly correlated) markets as possible.

Market types:
- Winner (moneyline): P(home wins)
- Spread: P(home wins by X+) for each threshold
- Total: P(total points >= X) for each threshold
- H1 spread/total: first half versions
- H1 winner: P(home wins first half)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

import trading.models as _models
from trading.models import (
    predict_regression, predict_classification,
    threshold_probability,
    parse_spread_ticker, parse_total_ticker,
)
from backtest.quoting import extract_book_top
from strategy.calibration import min_edge_for_profit
from trading.config import MIN_EDGE_BUFFER_MAKER, MIN_MODEL_CONVICTION

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    ticker: str
    market_type: str  # winner, spread, total, h1_spread, h1_total, h1_winner
    side: str  # yes or no
    model_prob: float
    market_price: float
    edge: float
    confidence: str  # HIGH, MEDIUM, LOW
    contracts: int
    reason: str
    prediction: float = 0.0   # point estimate from regression model
    scale: float = 0.0        # residual t-dist scale parameter (kept for backward compat)
    model_std: float = 0.0    # ensemble disagreement std for this prediction




def scan_all_markets(
    client,
    bundles: dict[str, dict],
    gf: pd.DataFrame,
    home: str,
    away: str,
    game_key: str,
    ws=None,
) -> list[Signal]:
    """
    Scan all available market types for a game. Returns signals.

    Args:
        bundles: {target_name: ensemble_bundle} from load_all_models()
        gf: game_features DataFrame
        home/away: team abbreviations
        game_key: e.g. "26JUN08SASNYK" (shared across all market types for this game)
        ws: optional KalshiWS instance for real-time books
    """
    from strategy.predict import build_matchup_row

    signals = []

    # Build feature row once — shared across all models
    gf_dated = gf.copy()
    gf_dated["game_date"] = pd.to_datetime(gf_dated["game_date"])
    all_features = set()
    for bundle in bundles.values():
        for s in bundle["specialists"]:
            all_features.update(s["features"])
    all_features = sorted(all_features)

    try:
        X = build_matchup_row(gf_dated, home, away, all_features)
    except Exception as e:
        logger.warning(f"Cannot build features for {home} vs {away}: {e}")
        return signals

    series = _models.MODEL_TO_SERIES

    # ── WINNER ───────────────────────────────────────────────────────────────
    if "winner" in bundles and "winner" in series:
        pred = predict_classification(bundles["winner"], X)
        if pred["prob"] >= MIN_MODEL_CONVICTION:
            _add_winner_signal(
                signals, client, ws, game_key, series["winner"],
                pred["prob"], pred["std"], home, away, "winner",
            )

    # ── H1 WINNER ────────────────────────────────────────────────────────────
    if "home_wins_h1" in bundles and "home_wins_h1" in series:
        pred = predict_classification(bundles["home_wins_h1"], X)
        if pred["prob"] >= MIN_MODEL_CONVICTION or pred["prob"] <= (1 - MIN_MODEL_CONVICTION):
            _add_winner_signal(
                signals, client, ws, game_key, series["home_wins_h1"],
                pred["prob"], pred["std"], home, away, "h1_winner",
            )

    # ── SPREAD ───────────────────────────────────────────────────────────────
    if "spread" in bundles and "spread" in series:
        pred = predict_regression(bundles["spread"], X)
        cal = bundles["spread"]["calibration"]
        _scan_spread_markets(
            signals, client, ws, game_key, series["spread"],
            pred["value"], pred["std"], cal, home, away, "spread",
        )

    # ── TOTAL (synthetic: h1_total + h2_total) ───────────────────────────────
    if "h1_total" in bundles and "h2_total" in bundles:
        total_series = series.get("h1_total", "").replace("1H", "")
        if not total_series:
            total_series = series.get("winner", "KXNBAGAME").replace("GAME", "TOTAL")
        pred_h1 = predict_regression(bundles["h1_total"], X)
        pred_h2 = predict_regression(bundles["h2_total"], X)
        synthetic_total = pred_h1["value"] + pred_h2["value"]
        from strategy.predict import _synthetic_total_params
        try:
            res_df, res_scale, _, rho_std = _synthetic_total_params()
            synthetic_std = float(np.sqrt(
                pred_h1["std"]**2 + pred_h2["std"]**2
                + 2 * rho_std * pred_h1["std"] * pred_h2["std"]
            ))
            syn_cal = {"residual_dist": {"df": res_df, "scale": res_scale}}
        except Exception:
            synthetic_std = pred_h1["std"] + pred_h2["std"]
            syn_cal = bundles["h1_total"].get("calibration", {})
        _scan_total_markets(
            signals, client, ws, game_key, total_series,
            synthetic_total, synthetic_std, syn_cal, "total",
        )

    # ── H1 SPREAD ────────────────────────────────────────────────────────────
    if "h1_spread" in bundles and "h1_spread" in series:
        pred = predict_regression(bundles["h1_spread"], X)
        cal = bundles["h1_spread"]["calibration"]
        _scan_spread_markets(
            signals, client, ws, game_key, series["h1_spread"],
            pred["value"], pred["std"], cal, home, away, "h1_spread",
        )

    # ── H1 TOTAL ─────────────────────────────────────────────────────────────
    if "h1_total" in bundles and "h1_total" in series:
        pred = predict_regression(bundles["h1_total"], X)
        cal = bundles["h1_total"]["calibration"]
        _scan_total_markets(
            signals, client, ws, game_key, series["h1_total"],
            pred["value"], pred["std"], cal, "h1_total",
        )

    logger.info(f"[{home}v{away}] {len(signals)} signals across "
                f"{sum(1 for t in bundles if t in series)} model types")

    # Log signal summary: side breakdown
    yes_sigs = [s for s in signals if s.side == "yes"]
    no_sigs = [s for s in signals if s.side == "no"]
    if signals:
        logger.info(f"  Signals: {len(yes_sigs)} YES, {len(no_sigs)} NO | "
                    f"Types: {', '.join(sorted(set(s.market_type for s in signals)))}")
        for s in signals:
            logger.info(f"    {s.ticker} {s.side.upper()} model={s.model_prob:.3f} "
                        f"mkt={s.market_price:.3f} edge={s.edge*100:.1f}%")
    return signals


def _get_book(client, ws, ticker) -> tuple[int | None, int | None]:
    """Get best bid/ask, preferring WS over REST."""
    if ws and ws.book.has_ticker(ticker):
        return ws.get_book(ticker)
    try:
        book = client.get_orderbook(ticker, depth=5)
        return extract_book_top(book)
    except Exception:
        return None, None


def _add_winner_signal(
    signals: list, client, ws, game_key: str, series: str,
    model_prob: float, model_std: float, home: str, away: str, market_type: str,
):
    """Add signal for winner/h1_winner market — only the aligned side."""
    # Determine which ticker is aligned with model
    if model_prob >= 0.5:
        aligned_team = home
        prob_yes = model_prob
    else:
        aligned_team = away
        prob_yes = 1 - model_prob

    ticker = f"{series}-{game_key}-{aligned_team}"
    bb, ba = _get_book(client, ws, ticker)
    if ba is None:
        return

    market_price = ba / 100.0
    edge = prob_yes - market_price
    min_edge = min_edge_for_profit(market_price, maker=True) * MIN_EDGE_BUFFER_MAKER

    if edge >= min_edge:
        signals.append(Signal(
            ticker=ticker, market_type=market_type, side="yes",
            model_prob=prob_yes, market_price=market_price, edge=edge,
            confidence="HIGH" if edge > 0.05 else "MEDIUM",
            contracts=0,  # sized later by runner
            reason=f"model={prob_yes:.3f} mkt={market_price:.3f}",
            model_std=model_std,
        ))


def _scan_spread_markets(
    signals: list, client, ws, game_key: str, series: str,
    predicted_spread: float, model_std: float, calibration: dict, home: str, away: str,
    market_type: str,
):
    """Scan all spread threshold markets for edge."""
    rd = calibration.get("residual_dist", {})
    res_scale = rd.get("scale", 10)

    try:
        result = client.get_markets(series_ticker=series, status="open", limit=100)
        markets = [m for m in result.get("markets", []) if game_key in m.get("ticker", "")]
    except Exception:
        return

    for m in markets:
        ticker = m["ticker"]
        parsed = parse_spread_ticker(ticker)
        if not parsed:
            continue

        team = parsed["team"]
        threshold = parsed["threshold"]

        # Convert: "SAS wins by 5+" means home_spread < -5 (if away=SAS)
        # Our model predicts home_spread (positive = home wins by more)
        if team == home:
            model_prob = threshold_probability(predicted_spread, threshold, calibration, "above")
            signed_threshold = threshold
        else:
            model_prob = threshold_probability(-predicted_spread, threshold, calibration, "above")
            signed_threshold = -threshold

        bb, ba = _get_book(client, ws, ticker)
        if ba is None:
            continue

        market_ask = ba / 100.0

        # Check YES side edge (no conviction filter — edge + t-value discount gate quality)
        edge = model_prob - market_ask
        min_edge = min_edge_for_profit(market_ask, maker=True) * MIN_EDGE_BUFFER_MAKER

        yes_skip = None
        if edge < min_edge:
            yes_skip = f"edge={edge*100:.1f}%<{min_edge*100:.1f}%"

        if edge >= min_edge:
            signals.append(Signal(
                ticker=ticker, market_type=market_type, side="yes",
                model_prob=model_prob, market_price=market_ask, edge=edge,
                confidence="HIGH" if edge > 0.05 else "MEDIUM",
                contracts=0,
                reason=f"pred_spread={predicted_spread:.1f} thresh={threshold} P={model_prob:.3f}",
                prediction=predicted_spread, scale=res_scale, model_std=model_std,
            ))

        # Check NO side edge (no conviction filter for regression thresholds)
        no_skip = "no_bid"
        edge_no = 0.0
        no_has_signal = False
        if bb is not None:
            market_no_price = (100 - bb) / 100.0
            edge_no = (1 - model_prob) - market_no_price
            min_edge_no = min_edge_for_profit(market_no_price, maker=True) * MIN_EDGE_BUFFER_MAKER
            if edge_no < min_edge_no:
                no_skip = f"edge={edge_no*100:.1f}%<{min_edge_no*100:.1f}%"
            else:
                no_skip = None
                no_has_signal = True
                signals.append(Signal(
                    ticker=ticker, market_type=market_type, side="no",
                    model_prob=1 - model_prob, market_price=market_no_price, edge=edge_no,
                    confidence="HIGH" if edge_no > 0.05 else "MEDIUM",
                    contracts=0,
                    reason=f"pred_spread={predicted_spread:.1f} thresh={threshold} P(NO)={1-model_prob:.3f}",
                    prediction=predicted_spread, scale=res_scale, model_std=model_std,
                ))

        # Log fair vs market for both sides
        no_price_str = f"{(100-bb)}c" if bb is not None else "—"
        yes_tag = "✓" if not yes_skip else f"skip({yes_skip})"
        no_tag = "✓" if no_has_signal else f"skip({no_skip})"
        logger.info(f"  {ticker}: fair_YES={model_prob*100:.0f}c ask={ba}c [{yes_tag}] | "
                    f"fair_NO={(1-model_prob)*100:.0f}c cost={no_price_str} [{no_tag}]")



def _scan_total_markets(
    signals: list, client, ws, game_key: str, series: str,
    predicted_total: float, model_std: float, calibration: dict, market_type: str,
):
    """Scan all total threshold markets for edge."""
    rd = calibration.get("residual_dist", {})
    res_scale = rd.get("scale", 10)

    try:
        result = client.get_markets(series_ticker=series, status="open", limit=100)
        markets = [m for m in result.get("markets", []) if game_key in m.get("ticker", "")]
    except Exception:
        return

    for m in markets:
        ticker = m["ticker"]
        parsed = parse_total_ticker(ticker)
        if not parsed:
            continue

        threshold = parsed["threshold"]
        model_prob = threshold_probability(predicted_total, threshold, calibration, "above")

        bb, ba = _get_book(client, ws, ticker)
        if ba is None:
            continue

        market_ask = ba / 100.0

        # YES edge (no conviction filter for regression thresholds)
        edge = model_prob - market_ask
        min_edge = min_edge_for_profit(market_ask, maker=True) * MIN_EDGE_BUFFER_MAKER
        if edge >= min_edge:
            signals.append(Signal(
                ticker=ticker, market_type=market_type, side="yes",
                model_prob=model_prob, market_price=market_ask, edge=edge,
                confidence="HIGH" if edge > 0.05 else "MEDIUM",
                contracts=0,
                reason=f"pred_total={predicted_total:.1f} thresh={threshold} P(over)={model_prob:.3f}",
                prediction=predicted_total, scale=res_scale, model_std=model_std,
            ))

        # NO edge (no conviction filter for regression thresholds)
        if bb is not None:
            market_no_price = (100 - bb) / 100.0
            edge_no = (1 - model_prob) - market_no_price
            min_edge_no = min_edge_for_profit(market_no_price, maker=True) * MIN_EDGE_BUFFER_MAKER
            if edge_no >= min_edge_no:
                signals.append(Signal(
                    ticker=ticker, market_type=market_type, side="no",
                    model_prob=1 - model_prob, market_price=market_no_price, edge=edge_no,
                    confidence="HIGH" if edge_no > 0.05 else "MEDIUM",
                    contracts=0,
                    reason=f"pred_total={predicted_total:.1f} thresh={threshold} P(under)={1-model_prob:.3f}",
                    prediction=predicted_total, scale=res_scale, model_std=model_std,
                ))

