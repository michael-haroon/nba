"""
espn_client.py
--------------
ESPN API client for box score fallback.

Provides:
  fetch_espn_full_game(espn_event_id) → flat dict of scores + venue + box score stats (single call)
  fetch_espn_traditional(espn_event_id) → flat dict of team box score stats
  fetch_espn_game_meta(espn_event_id, game_date_et) → attendance, venue, neutral_site
  find_espn_event_id(game_date_et, home_tricode, away_tricode) → espn_event_id | None

Field names map from ESPN → our NBA column naming convention.
Headers rotate per-request to avoid ESPN's soft rate limiting.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ---------------------------------------------------------------------------
# Header rotation
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

_ACCEPT_LANGS = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
]

_REFERERS = [
    "https://www.espn.com/nba/",
    "https://www.espn.com/nba/scoreboard",
    "https://www.espn.com/",
]


def _random_headers() -> dict:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANGS),
        "Referer": random.choice(_REFERERS),
        "Origin": "https://www.espn.com",
        "DNT": "1",
    }


# ---------------------------------------------------------------------------
# ESPN stat name → our NBA column names
# ---------------------------------------------------------------------------

# Split fields like "fieldGoalsMade-fieldGoalsAttempted" need parsing
_STAT_MAP = {
    "fieldGoalsMade-fieldGoalsAttempted": ("fieldGoalsMade", "fieldGoalsAttempted"),
    "fieldGoalPct":                        ("fieldGoalsPercentage",),
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted": ("threePointersMade", "threePointersAttempted"),
    "threePointFieldGoalPct":              ("threePointersPercentage",),
    "freeThrowsMade-freeThrowsAttempted":  ("freeThrowsMade", "freeThrowsAttempted"),
    "freeThrowPct":                        ("freeThrowsPercentage",),
    "totalRebounds":                       ("reboundsTotal",),
    "offensiveRebounds":                   ("reboundsOffensive",),
    "defensiveRebounds":                   ("reboundsDefensive",),
    "assists":                             ("assists",),
    "steals":                              ("steals",),
    "blocks":                              ("blocks",),
    "turnovers":                           ("turnovers",),
    "teamTurnovers":                       ("turnoversTeam",),
    "totalTurnovers":                      ("turnoversTotal",),
    "fouls":                               ("foulsPersonal",),
    "pointsInPaint":                       ("pointsInThePaint",),
    "fastBreakPoints":                     ("pointsFastBreak",),
    "turnoverPoints":                      ("pointsFromTurnovers",),
    "largestLead":                         ("biggestLead",),
    "leadChanges":                         ("leadChanges",),
}

# Normalise NBA Stats tricodes → ESPN abbreviations
_NBA_TO_ESPN = {
    "GSW": "GS", "SAS": "SA", "NYK": "NY", "UTA": "UTAH",
    "WAS": "WSH", "NOP": "NO", "NOH": "NO", "NOK": "NO",
    "BKN": "BKN", "UTH": "UTAH", "SAN": "SA", "GOS": "GS",
    "GNS": "GS", "PHL": "PHI", "NJN": "NJ",
}

_ESPN_NAME_TO_TRICODE = {
    "Utah Jazz": "UTAH",
    "Atlanta Hawks": "ATL",
    "Kansas City Kings": "KCK",
    "Kansas City-Omaha Kings": "KCK",
    "Rochester Royals": "ROC",
    "San Diego Rockets": "SDR",
    "Washington Bullets": "WSH",
    "New Jersey Nets": "NJ",
    "Seattle SuperSonics": "SEA",
    "Vancouver Grizzlies": "VAN",
    "San Diego Clippers": "SDC",
    "Buffalo Braves": "BUF",
    "Cincinnati Royals": "CIN",
    "Baltimore Bullets": "BAL",
    "Capital Bullets": "CAP",
    "New Orleans Jazz": "NOJ",
}


def _norm(abbr: str, year: int) -> str:
    if abbr in ("BKN", "NJN") and year < 2012:
        return "NJ"
    if abbr in ("NOH", "NOK", "NOP"):
        return "NO"
    return _NBA_TO_ESPN.get(abbr, abbr)


def _parse_stat(name: str, display_value: str) -> dict:
    cols = _STAT_MAP.get(name)
    if not cols:
        return {}
    if len(cols) == 2:
        parts = display_value.split("-")
        if len(parts) == 2:
            try:
                return {cols[0]: int(parts[0]), cols[1]: int(parts[1])}
            except ValueError:
                return {}
        return {}
    try:
        val = float(display_value) / 100 if "Pct" in name or "pct" in name.lower() else float(display_value)
        return {cols[0]: val}
    except ValueError:
        return {}


# ---------------------------------------------------------------------------
# HTTP helper — rotates headers per call
# ---------------------------------------------------------------------------

def _get(url: str, params: dict, timeout: int = 15) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout, headers=_random_headers())
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.debug("ESPN request failed %s %s: %s", url, params, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_espn_full_game(espn_event_id: str) -> Optional[dict]:
    """
    Single summary-endpoint call that returns scores + venue + box score stats.
    Used in the circuit-open ESPN fallback path — avoids two separate calls.
    Returns a flat dict with home_/away_ prefixed columns, or None if unavailable.
    """
    data = _get(_SUMMARY_URL, {"event": espn_event_id})
    if not data:
        return None

    result: dict = {}

    # Scores + neutral site from header.competitions
    header = data.get("header") or {}
    header_comp = ((header.get("competitions") or [{}])[0])
    result["espn_neutral_site"] = header_comp.get("neutralSite")
    for competitor in header_comp.get("competitors", []):
        ha = competitor.get("homeAway", "")
        if ha not in ("home", "away"):
            continue
        try:
            result[f"{ha}_score"] = int(competitor.get("score", 0) or 0)
        except (ValueError, TypeError):
            pass
        team = competitor.get("team") or {}
        result[f"{ha}_team_tricode_espn"] = team.get("abbreviation", "").strip().upper() or None

    # Venue + attendance from gameInfo (most reliable location in summary)
    game_info = data.get("gameInfo") or {}
    venue = game_info.get("venue") or {}
    addr = venue.get("address") or {}
    result["espn_attendance"] = game_info.get("attendance")
    result["espn_venue_capacity"] = venue.get("capacity")
    result["espn_venue_name"] = venue.get("fullName")
    result["espn_venue_city"] = addr.get("city")
    result["espn_venue_state"] = addr.get("state")

    # Fallback: attendance sometimes lives in competitions
    if result["espn_attendance"] is None:
        comps = (data.get("competitions") or [{}])[0]
        result["espn_attendance"] = comps.get("attendance")
        if result["espn_venue_name"] is None:
            v2 = comps.get("venue") or {}
            result["espn_venue_name"] = v2.get("fullName")
            result["espn_venue_capacity"] = v2.get("capacity")
            a2 = v2.get("address") or {}
            result["espn_venue_city"] = a2.get("city")
            result["espn_venue_state"] = a2.get("state")

    # Box score statistics from boxscore.teams
    teams = (data.get("boxscore") or {}).get("teams", [])
    for team_data in teams:
        ha = team_data.get("homeAway", "")
        if ha not in ("home", "away"):
            continue
        prefix = f"{ha}_"
        for stat in team_data.get("statistics", []):
            name = stat.get("name", "")
            display = stat.get("displayValue", "")
            for col, val in _parse_stat(name, display).items():
                result[f"{prefix}{col}"] = val

    # Derive missing percentages from made/attempted
    for side in ("home_", "away_"):
        for made_col, att_col, pct_col in [
            (f"{side}fieldGoalsMade", f"{side}fieldGoalsAttempted", f"{side}fieldGoalsPercentage"),
            (f"{side}threePointersMade", f"{side}threePointersAttempted", f"{side}threePointersPercentage"),
            (f"{side}freeThrowsMade", f"{side}freeThrowsAttempted", f"{side}freeThrowsPercentage"),
        ]:
            if pct_col not in result and made_col in result and att_col in result:
                att = result[att_col]
                result[pct_col] = result[made_col] / att if att else 0.0

    # BPI pre-game win probability
    predictor = data.get("predictor") or {}
    if predictor:
        try:
            result["espn_bpi_home_win_pct"] = float(
                (predictor.get("homeTeam") or {}).get("gameProjection", 0) or 0
            ) / 100
        except (ValueError, TypeError):
            pass

    return result if result else None


def fetch_espn_traditional(espn_event_id: str) -> Optional[dict]:
    """
    Fetch team-level traditional box score from ESPN summary endpoint.
    Returns a flat dict with home_/away_ prefixed columns matching our NBA naming,
    or None if unavailable.
    """
    data = _get(_SUMMARY_URL, {"event": espn_event_id})
    if not data:
        return None

    teams = (data.get("boxscore") or {}).get("teams", [])
    if not teams:
        return None

    result = {}
    for team_data in teams:
        ha = team_data.get("homeAway", "")
        if ha not in ("home", "away"):
            continue
        prefix = f"{ha}_"
        for stat in team_data.get("statistics", []):
            name = stat.get("name", "")
            display = stat.get("displayValue", "")
            for col, val in _parse_stat(name, display).items():
                result[f"{prefix}{col}"] = val

    for side in ("home_", "away_"):
        for made_col, att_col, pct_col in [
            (f"{side}fieldGoalsMade", f"{side}fieldGoalsAttempted", f"{side}fieldGoalsPercentage"),
            (f"{side}threePointersMade", f"{side}threePointersAttempted", f"{side}threePointersPercentage"),
            (f"{side}freeThrowsMade", f"{side}freeThrowsAttempted", f"{side}freeThrowsPercentage"),
        ]:
            if pct_col not in result and made_col in result and att_col in result:
                att = result[att_col]
                result[pct_col] = result[made_col] / att if att else 0.0

    return result if result else None


def fetch_espn_game_meta(espn_event_id: str, game_date_et: str) -> Optional[dict]:
    """
    Fetch attendance, venue (including capacity), and neutral_site from ESPN scoreboard.
    game_date_et: 'YYYY-MM-DD' in Eastern Time.
    Returns dict or None.
    """
    api_date = game_date_et.replace("-", "")
    data = _get(_SCOREBOARD_URL, {"dates": api_date})
    if not data:
        return None

    for event in data.get("events", []):
        if str(event.get("id")) == str(espn_event_id):
            comp = (event.get("competitions") or [{}])[0]
            venue = comp.get("venue") or {}
            addr = venue.get("address") or {}
            return {
                "espn_attendance": comp.get("attendance"),
                "espn_neutral_site": comp.get("neutralSite"),
                "espn_venue_name": venue.get("fullName"),
                "espn_venue_capacity": venue.get("capacity"),
                "espn_venue_city": addr.get("city"),
                "espn_venue_state": addr.get("state"),
            }
    return None


def find_espn_event_id(
    game_date_et: str,
    home_tricode: str,
    away_tricode: str,
    *,
    try_adjacent: bool = True,
) -> tuple[Optional[str], str]:
    """
    Search ESPN scoreboard for a game by date + team abbreviations.
    Returns (espn_event_id, match_method) where match_method is:
      'same_day', 'day_shift', or 'no_match'
    """
    from datetime import datetime, timedelta

    year = int(game_date_et[:4])
    h_espn = _norm(home_tricode, year)
    a_espn = _norm(away_tricode, year)

    def _search_date(date_str: str) -> Optional[str]:
        api_date = date_str.replace("-", "")
        data = _get(_SCOREBOARD_URL, {"dates": api_date})
        if not data:
            return None
        for event in data.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            def _abbr(c: dict) -> str:
                team = c.get("team") or {}
                abbr = team.get("abbreviation", "").strip().upper()
                if not abbr:
                    name = team.get("displayName", "")
                    abbr = _ESPN_NAME_TO_TRICODE.get(name, "").upper()
                return abbr

            e_home = _abbr(home)
            e_away = _abbr(away)
            if e_home == h_espn and e_away == a_espn:
                return str(event["id"])
            if e_home == a_espn and e_away == h_espn:
                return str(event["id"])
        return None

    eid = _search_date(game_date_et)
    if eid:
        return eid, "same_day"

    if try_adjacent:
        dt = datetime.strptime(game_date_et, "%Y-%m-%d")
        for delta in (-1, 1):
            shifted = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
            eid = _search_date(shifted)
            if eid:
                return eid, "day_shift"

    return None, "no_match"
