"""
match_markets.py
----------------
Map feature-engineering games to Kalshi KXNBAGAME market tickers.

Kalshi ticker format: KXNBAGAME-{YYMMMdd}{AWAY}{HOME}-{YES_TEAM}
Example: KXNBAGAME-26MAY26SASOKC-SAS  → away=SAS, home=OKC, YES=SAS wins

Index key: (game_date, team_a, team_b, yes_team) where team_a/b are sorted
to make lookups order-independent.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional


KALSHI_ABBR_TO_NBA: dict[str, str] = {
    "BOS": "BOS", "NYK": "NYK", "PHI": "PHI", "TOR": "TOR", "BKN": "BKN",
    "CHI": "CHI", "CLE": "CLE", "DET": "DET", "IND": "IND", "MIL": "MIL",
    "ATL": "ATL", "CHA": "CHA", "MIA": "MIA", "ORL": "ORL", "WAS": "WAS",
    "DEN": "DEN", "MIN": "MIN", "OKC": "OKC", "POR": "POR", "UTA": "UTA",
    "GSW": "GSW", "LAC": "LAC", "LAL": "LAL", "PHX": "PHX", "SAC": "SAC",
    "DAL": "DAL", "HOU": "HOU", "MEM": "MEM", "NOP": "NOP", "SAS": "SAS",
}
KALSHI_VARIANT: dict[str, str] = {
    "NY": "NYK", "GS": "GSW", "SA": "SAS", "NO": "NOP",
}


def _normalize(k: str) -> str:
    k = k.upper()
    return KALSHI_ABBR_TO_NBA.get(k) or KALSHI_VARIANT.get(k, k)


def _parse_ticker(ticker: str) -> Optional[dict]:
    """
    Parse KXNBAGAME-{YYMMMdd}{AWAY}{HOME}-{YES_TEAM}.

    Returns: game_date, away, home, yes_team  — all normalized NBA abbrs.
    """
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


def build_ticker_index(markets: list[dict]) -> dict:
    """
    Build lookup: (game_date, frozenset{team_a, team_b}, yes_team) → market dict.

    Using frozenset for the two teams makes the lookup order-independent.
    """
    index: dict = {}
    for m in markets:
        parsed = _parse_ticker(m["ticker"])
        if not parsed:
            continue
        key = (
            parsed["game_date"],
            frozenset([parsed["home"], parsed["away"]]),
            parsed["yes_team"],
        )
        index[key] = {**m, **parsed}
    return index


def match_game_to_ticker(
    game_date,
    home_abbr: str,
    away_abbr: str,
    yes_team_abbr: str,
    ticker_index: dict,
) -> Optional[dict]:
    """
    Find the Kalshi market for a given game and YES side.

    game_date: datetime.date or pd.Timestamp
    home_abbr / away_abbr: team abbreviations from our feature data
    yes_team_abbr: which team we want the YES contract for
    """
    if hasattr(game_date, "date"):
        game_date = game_date.date()

    key = (game_date, frozenset([home_abbr, away_abbr]), yes_team_abbr)
    return ticker_index.get(key)
