"""
quoting.py
----------
Market-making quoting algorithm.

Given our model's fair probability (0-1) and the current best bid/ask
from the order book, compute bid/ask quotes in cents (1-99).

Rules:
  - Never cross fair price (bid < fair, ask > fair).
  - Quote at the top of book (inside the spread) when possible.
  - Never tighten the spread unnecessarily — only move inside when
    there is room without crossing fair.
  - Minimum spread enforced to avoid printing at fair value.

Taker-side convention (Kalshi):
  - taker_outcome_side == "yes"  → taker is BUYING YES (lifting ask)
                                   → we are the passive SELLER
  - taker_outcome_side == "no"   → taker is SELLING YES (hitting bid)
                                   → we are the passive BUYER

Example:
  fair=0.50, book bid=46, book ask=51
  → our bid = min(fair-1, book_bid+1) = min(49, 47) = 47
  → our ask = max(fair+1, book_ask-1) = max(51, 50) = 51  (already at top)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Minimum half-spread in cents. We never quote tighter than fair ± MIN_HALF_SPREAD.
MIN_HALF_SPREAD = 1


@dataclass
class Quote:
    bid: int       # cents, what we pay for YES
    ask: int       # cents, what we sell YES for
    fair: int      # our fair value in cents (rounded)
    book_bid: Optional[int]
    book_ask: Optional[int]

    @property
    def spread(self) -> int:
        return self.ask - self.bid

    def __str__(self) -> str:
        bb = f"{self.book_bid}" if self.book_bid is not None else "—"
        ba = f"{self.book_ask}" if self.book_ask is not None else "—"
        return (f"fair={self.fair}¢  book=[{bb}×{ba}]  "
                f"quote=[{self.bid}×{self.ask}]  spread={self.spread}¢")


def compute_quotes(
    win_prob: float,
    book_bid: Optional[int],
    book_ask: Optional[int],
) -> Quote:
    """
    Compute bid/ask quotes (in cents) for a YES contract.

    Args:
        win_prob:  model P(home wins), in [0, 1]
        book_bid:  best bid in book (cents), or None if empty
        book_ask:  best ask in book (cents), or None if empty

    Returns:
        Quote with bid, ask, fair values.

    Note on taker-side convention:
        taker_outcome_side == "yes"  → taker BUYING YES (lifting ask)  → we are passive SELLER
        taker_outcome_side == "no"   → taker SELLING YES (hitting bid)  → we are passive BUYER
    """
    fair = round(win_prob * 100)
    fair = max(1, min(99, fair))

    # Floor/ceiling so we never cross fair
    max_bid = fair - MIN_HALF_SPREAD
    min_ask = fair + MIN_HALF_SPREAD

    # --- Compute bid ---
    if book_bid is None:
        # No market: quote at max_bid (tight to fair)
        bid = max_bid
    else:
        # Try to step inside the book by 1 cent (beat book bid)
        inside_bid = book_bid + 1
        # Never go above max_bid (would cross fair)
        bid = min(inside_bid, max_bid)
        # Never go below 1
        bid = max(1, bid)

    # --- Compute ask ---
    if book_ask is None:
        ask = min_ask
    else:
        # Try to step inside by 1 cent (undercut book ask)
        inside_ask = book_ask - 1
        # Never go below min_ask (would cross fair)
        ask = max(inside_ask, min_ask)
        # Never go above 99
        ask = min(99, ask)

    # Safety: ensure bid < ask always
    if bid >= ask:
        bid = fair - MIN_HALF_SPREAD
        ask = fair + MIN_HALF_SPREAD

    return Quote(bid=bid, ask=ask, fair=fair,
                 book_bid=book_bid, book_ask=book_ask)


def extract_book_top(orderbook: dict) -> tuple[Optional[int], Optional[int]]:
    """
    Parse Kalshi orderbook response to get best bid/ask.

    Kalshi orderbook: {"yes": [[price, size], ...], "no": [[price, size], ...]}
    YES bids = yes side sorted descending.
    YES asks = 100 - (NO bids sorted descending).
    """
    yes_levels = orderbook.get("yes", [])
    no_levels = orderbook.get("no", [])

    # Best bid: highest YES price
    book_bid: Optional[int] = None
    if yes_levels:
        # levels are [price, qty] pairs, already sorted desc
        book_bid = int(yes_levels[0][0])

    # Best ask: 100 - highest NO price (NO buyer = YES seller)
    book_ask: Optional[int] = None
    if no_levels:
        best_no_bid = int(no_levels[0][0])
        book_ask = 100 - best_no_bid

    # Sanity: if bid >= ask, treat as crossed/empty
    if book_bid is not None and book_ask is not None and book_bid >= book_ask:
        book_bid = None
        book_ask = None

    return book_bid, book_ask


def parse_candle_book(candle: dict) -> tuple[Optional[int], Optional[int]]:
    """
    Extract best bid/ask in cents from a Kalshi candlestick dict.

    Kalshi candle fields: yes_bid.close_dollars, yes_ask.close_dollars
    Returns (book_bid_cents, book_ask_cents).
    """
    try:
        bid = round(float(candle["yes_bid"]["close_dollars"]) * 100)
        ask = round(float(candle["yes_ask"]["close_dollars"]) * 100)
        if bid >= ask:
            return None, None
        return bid, ask
    except (KeyError, TypeError, ValueError):
        return None, None


def candle_mid_cents(candle: dict) -> Optional[int]:
    """Mid price in cents from a candle's mean_dollars field."""
    try:
        return round(float(candle["price"]["mean_dollars"]) * 100)
    except (KeyError, TypeError, ValueError):
        return None
