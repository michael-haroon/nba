"""
trading/risk.py
---------------
Risk management gates. Every order must pass these before execution.
"""

from __future__ import annotations

import logging

from trading.config import (
    MAX_POSITION_PCT, MAX_DAILY_EXPOSURE_PCT,
    MAX_CONCURRENT_POSITIONS, DAILY_LOSS_LIMIT_PCT,
    MAX_CONTRACTS_PER_MARKET, MIN_HOURS_TO_TIPOFF,
    MAX_HOURS_TO_TIPOFF, PRICE_FLOOR, PRICE_CEILING,
)
from trading.portfolio import (
    position_count, total_exposure, daily_pnl, has_position,
)

logger = logging.getLogger(__name__)


def check_limits(
    ticker: str,
    price: float,
    contracts: int,
    hours_to_tipoff: float,
    bankroll: float,
    max_exposure_dollars: float | None = None,
) -> tuple[bool, str]:
    """
    Returns (allowed, reason). If allowed=False, reason explains why.
    max_exposure_dollars overrides config-based cap if provided.
    """
    # Circuit breaker: daily loss limit
    day_loss = daily_pnl()
    loss_limit = bankroll * DAILY_LOSS_LIMIT_PCT / 100.0
    if day_loss < -loss_limit:
        return False, f"Daily loss circuit breaker: ${day_loss:.2f} exceeds -${loss_limit:.2f}"

    # Already have position in this market
    if has_position(ticker):
        return False, f"Already have position in {ticker}"

    # Max concurrent positions
    if position_count() >= MAX_CONCURRENT_POSITIONS:
        return False, f"Max concurrent positions ({MAX_CONCURRENT_POSITIONS}) reached"

    # Max contracts per market
    if contracts > MAX_CONTRACTS_PER_MARKET:
        return False, f"Contracts ({contracts}) exceeds max ({MAX_CONTRACTS_PER_MARKET})"

    # Single position size
    position_value = price * contracts
    max_single = bankroll * MAX_POSITION_PCT / 100.0
    if position_value > max_single:
        return False, f"Position ${position_value:.2f} exceeds max ${max_single:.2f} ({MAX_POSITION_PCT}%)"

    # Total exposure
    current_exposure = total_exposure()
    max_exp = max_exposure_dollars if max_exposure_dollars is not None else bankroll * MAX_DAILY_EXPOSURE_PCT / 100.0
    if current_exposure + position_value > max_exp:
        return False, f"Total exposure would be ${current_exposure + position_value:.2f} > max ${max_exp:.2f}"

    # Timing
    if hours_to_tipoff < MIN_HOURS_TO_TIPOFF:
        return False, f"Too close to tipoff ({hours_to_tipoff:.1f}h < {MIN_HOURS_TO_TIPOFF}h)"
    if hours_to_tipoff > MAX_HOURS_TO_TIPOFF:
        return False, f"Too far from tipoff ({hours_to_tipoff:.1f}h > {MAX_HOURS_TO_TIPOFF}h)"

    # Price range
    if price < PRICE_FLOOR:
        return False, f"Price {price:.2f} below floor {PRICE_FLOOR}"
    if price > PRICE_CEILING:
        return False, f"Price {price:.2f} above ceiling {PRICE_CEILING}"

    return True, "OK"
