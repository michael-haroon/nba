"""
curate_history.py
-----------------
Fetches and stores one row per completed NBA game with full box score context.

ID SYSTEM NOTES
---------------
NBA Stats game IDs  : 10-char strings, e.g. "0022500165"
NBA Stats team IDs  : 10-digit ints,   e.g.  1610612744  (Warriors)
ESPN event IDs      : strings,          e.g. "401765432"
ESPN team IDs       : small ints,       e.g.  9           (Warriors)
ESPN venue IDs      : strings,          ESPN-specific, no NBA Stats counterpart

Join key for NBA ↔ ESPN:  (game_date, home_team_abbreviation, away_team_abbreviation)
Abbreviations are standard 3-letter NBA codes in both APIs with minor historical
exceptions (handled in get_norm_abbreviation below).

OUTPUT FILES
------------
data/games.parquet        — one row per game, all box score columns
data/game_id_map.parquet  — NBA game_id ↔ ESPN event_id cross-reference
data/state.json           — lightweight resume state (processed IDs + permanent failures)
data/failed_games.jsonl   — structured failure log
logs/curate_history.log   — persistent log file
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
LOG_DIR = Path(__file__).parent / "logs"
GAMES_OUT = DATA_DIR / "games.parquet"
ID_MAP_OUT = DATA_DIR / "game_id_map.parquet"
STATE_FILE = DATA_DIR / "state.json"
FAILED_GAMES_LOG = DATA_DIR / "failed_games.jsonl"
FETCH_LOG = DATA_DIR / "fetch_log.jsonl"  # per-game structured fetch audit

LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging — file + console
# ---------------------------------------------------------------------------

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = logging.FileHandler(LOG_DIR / "curate_history.log")
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_fh, _sh])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECKPOINT_EVERY = 50       # flush parquet after this many successful rows
WINDOW_SIZE = 20            # rolling window for success-rate monitoring
SUCCESS_THRESHOLD = 0.90    # drop workers if success rate falls below this
INITIAL_WORKERS = 2         # start here; adaptive logic adjusts up/down
MAX_WORKERS_CAP = 4         # never exceed this regardless of success rate
JITTER_BASE = (1.5, 3.0)    # base sleep between requests (seconds)

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Game ID prefixes that BoxScoreSummaryV3 does not support — permanent skip
_UNSUPPORTED_PREFIXES = ("003",)  # All-Star / special events

# ---------------------------------------------------------------------------
# Shared persistent HTTP session with rotating headers
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_ACCEPT_LANGUAGES = [
    "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9",
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
]


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Host": "stats.nba.com",
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Connection": "keep-alive",
    })
    return s


def _rotate_session() -> None:
    """Replace the nba_api library's shared session with a fresh one (new headers)."""
    from nba_api.stats.library.http import NBAStatsHTTP
    NBAStatsHTTP._session = _make_session()


# ---------------------------------------------------------------------------
# State persistence (fast resume without scanning parquet)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"processed_ids": [], "permanent_failures": []}


def _save_state(processed_ids: set[str], permanent_failures: set[str]) -> None:
    STATE_FILE.write_text(json.dumps({
        "processed_ids": sorted(processed_ids),
        "permanent_failures": sorted(permanent_failures),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


# ---------------------------------------------------------------------------
# Failure logging
# ---------------------------------------------------------------------------

def _log_failure(game_id: str, reason: str, permanent: bool, detail: str = "") -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "game_id": game_id,
        "reason": reason,
        "permanent": permanent,
        "detail": detail,
    }
    with open(FAILED_GAMES_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


# Outcome codes written to fetch_log.jsonl for every endpoint attempted per game:
#   "ok"          — data returned, columns populated
#   "no_data"     — endpoint returned null stats (metric not tracked this era)
#   "rate_limit"  — empty response / 30s timeout — likely IP throttle or ban
#   "timeout"     — read timed out after retries
#   "parse_error" — response arrived but couldn't be parsed
#   "skipped"     — summary failed so all subsequent endpoints were never attempted
#   "unsupported" — game type (All-Star etc.) not supported by BoxScoreSummaryV3

_ENDPOINT_NAMES = [
    "summary", "traditional", "advanced", "fourfactors",
    "misc", "scoring", "hustle", "espn_match",
]


def _write_fetch_log(record: dict) -> None:
    with open(FETCH_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Adaptive throttle
# ---------------------------------------------------------------------------

class AdaptiveThrottle:
    """
    Tracks a rolling success-rate window and adjusts worker count + sleep time.
    - If success rate stays above threshold, increment workers (up to cap).
    - If success rate drops below threshold, halve workers and rotate session.
    """

    def __init__(self, initial_workers: int):
        self.workers = initial_workers
        self._window: deque[bool] = deque(maxlen=WINDOW_SIZE)
        self._since_last_increase = 0

    def record(self, success: bool) -> None:
        self._window.append(success)
        self._since_last_increase += 1

    def success_rate(self) -> float:
        if not self._window:
            return 1.0
        return sum(self._window) / len(self._window)

    def jitter(self) -> float:
        rate = self.success_rate()
        if rate < SUCCESS_THRESHOLD:
            # Back off hard: base sleep * 4
            return random.uniform(JITTER_BASE[0] * 4, JITTER_BASE[1] * 4)
        return random.uniform(*JITTER_BASE)

    def maybe_adjust(self) -> None:
        if len(self._window) < WINDOW_SIZE:
            return
        rate = self.success_rate()
        if rate < SUCCESS_THRESHOLD and self.workers > 1:
            old = self.workers
            self.workers = max(1, self.workers // 2)
            logger.warning(
                "Success rate %.0f%% — reducing workers %d→%d and rotating session.",
                rate * 100, old, self.workers,
            )
            _rotate_session()
            self._since_last_increase = 0
        elif rate >= SUCCESS_THRESHOLD and self._since_last_increase >= WINDOW_SIZE:
            if self.workers < MAX_WORKERS_CAP:
                self.workers += 1
                logger.info(
                    "Success rate %.0f%% — increasing workers to %d.",
                    rate * 100, self.workers,
                )
            self._since_last_increase = 0

    def check_rate_limit_headers(self, headers: dict) -> None:
        """Respect Retry-After and X-RateLimit-Remaining if present."""
        retry_after = headers.get("Retry-After")
        if retry_after:
            wait = float(retry_after)
            logger.warning("Retry-After header: sleeping %.1fs", wait)
            time.sleep(wait)
        remaining = headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            reset = headers.get("X-RateLimit-Reset", 60)
            logger.warning("Rate limit exhausted — sleeping %ss", reset)
            time.sleep(float(reset))


throttle = AdaptiveThrottle(initial_workers=INITIAL_WORKERS)

# ---------------------------------------------------------------------------
# NBA API helpers
# ---------------------------------------------------------------------------

def _safe_call(fn, *args, retries: int = 4, **kwargs):
    """
    Retry wrapper with exponential backoff + jitter for all transient NBA Stats errors.
    Classifies errors as transient (retry) vs permanent (give up immediately).
    """
    _TRANSIENT = (
        "RemoteDisconnected", "Connection aborted", "Connection reset",
        "Remote end closed", "Read timed out", "timed out",
        "Max retries exceeded", "Failed to establish", "ConnectionError",
        "Expecting value",  # empty JSON body
    )

    for attempt in range(retries + 1):
        try:
            result = fn(*args, **kwargs)
            throttle.record(True)
            return result

        except Exception as exc:
            msg = str(exc)
            is_transient = any(t in msg for t in _TRANSIENT)

            if is_transient and attempt < retries:
                wait = (2 ** attempt) + random.uniform(1, 3)
                logger.debug("Transient error (attempt %d/%d), retrying in %.1fs: %s",
                             attempt + 1, retries, wait, exc)
                time.sleep(wait)
                continue

            if is_transient:
                logger.warning("API call failed after %d retries: %s", retries, exc)
                throttle.record(False)
                throttle.maybe_adjust()
                return None

            # Permanent error (NoneType attr, 404, bad params, etc.)
            logger.warning("API call failed (non-retryable): %s", exc)
            throttle.record(False)
            throttle.maybe_adjust()
            return None

    return None


def _flat(stats: dict, prefix: str) -> dict:
    return {f"{prefix}{k}": v for k, v in stats.items()}


# ---------------------------------------------------------------------------
# Per-game fetch
# ---------------------------------------------------------------------------

def _classify_exc(exc: Exception) -> str:
    """Map an exception to a fetch log outcome code."""
    msg = str(exc)
    if "NoneType" in msg and "attribute" in msg:
        return "no_data"
    if "Expecting value" in msg:
        return "rate_limit"
    if "timed out" in msg or "Timeout" in msg:
        return "timeout"
    if any(t in msg for t in ("RemoteDisconnected", "Connection aborted",
                               "Remote end closed", "ConnectionError")):
        return "rate_limit"
    return "parse_error"


def fetch_game(game_id: str) -> dict | None:
    """
    Fetch all box score endpoints for one game and return a flat dict.
    Emits one structured record to fetch_log.jsonl recording the outcome of
    every endpoint: ok / no_data / rate_limit / timeout / parse_error / skipped.
    """
    from nba_api.stats.endpoints import (
        boxscoreadvancedv3,
        boxscorefourfactorsv3,
        boxscorehustlev2,
        boxscoremiscv3,
        boxscorescoringv3,
        boxscoresummaryv3,
        boxscoretraditionalv3,
    )

    audit: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "game_id": game_id,
        "endpoints": {},   # endpoint_name → outcome code
        "missing_cols": [], # column groups that came back empty
        "espn_matched": None,
    }

    def _mark(ep_name: str, outcome: str) -> None:
        audit["endpoints"][ep_name] = outcome

    # --- Summary ---
    summ_ep = _safe_call(boxscoresummaryv3.BoxScoreSummaryV3, game_id)
    if summ_ep is None:
        prefix = str(game_id)[:3]
        permanent = prefix in _UNSUPPORTED_PREFIXES
        reason = "unsupported_game_type" if permanent else "summary_api_failure"
        outcome = "unsupported" if permanent else "rate_limit"
        _mark("summary", outcome)
        for ep in ["traditional", "advanced", "fourfactors", "misc", "scoring", "hustle"]:
            _mark(ep, "skipped")
        audit["espn_matched"] = "skipped"
        _log_failure(game_id, reason, permanent=permanent,
                     detail=f"prefix={prefix}" if permanent else "returned None after retries")
        _write_fetch_log(audit)
        if permanent:
            logger.warning("Permanent skip %s: unsupported game type (prefix=%s)", game_id, prefix)
        else:
            logger.warning("Transient skip %s: will retry next run", game_id)
        return None

    try:
        gs_headers = summ_ep.game_summary.get_dict()["headers"]
        gs_row = dict(zip(gs_headers, summ_ep.game_summary.get_dict()["data"][0]))
        gi_headers = summ_ep.game_info.get_dict()["headers"]
        gi_row = dict(zip(gi_headers, summ_ep.game_info.get_dict()["data"][0]))
        ai_headers = summ_ep.arena_info.get_dict()["headers"]
        ai_row = dict(zip(ai_headers, summ_ep.arena_info.get_dict()["data"][0]))
        ls_data = summ_ep.line_score.get_dict()
        ls_rows = [dict(zip(ls_data["headers"], r)) for r in ls_data["data"]]
        os_data = summ_ep.other_stats.get_dict()
        os_rows = [dict(zip(os_data["headers"], r)) for r in os_data["data"]]
        _mark("summary", "ok")
    except Exception as exc:
        is_none_attr = "NoneType" in str(exc) and "attribute" in str(exc)
        permanent = is_none_attr or str(game_id)[:3] in _UNSUPPORTED_PREFIXES
        _mark("summary", "no_data" if is_none_attr else "parse_error")
        for ep in ["traditional", "advanced", "fourfactors", "misc", "scoring", "hustle"]:
            _mark(ep, "skipped")
        audit["espn_matched"] = "skipped"
        _log_failure(game_id, "summary_parse_failure", permanent=permanent, detail=str(exc))
        _write_fetch_log(audit)
        logger.warning("Summary parse failed %s (%s): %s",
                       game_id, "permanent" if permanent else "transient", exc)
        return None

    home_team_id = gs_row.get("homeTeamId")
    away_team_id = gs_row.get("awayTeamId")

    def _for(rows, team_id):
        return next((r for r in rows if r.get("teamId") == team_id), {})

    home_ls = _for(ls_rows, home_team_id)
    away_ls = _for(ls_rows, away_team_id)
    home_os = _for(os_rows, home_team_id)
    away_os = _for(os_rows, away_team_id)

    row: dict = {
        "game_id": gs_row.get("gameId"),
        "game_code": gs_row.get("gameCode"),
        "game_date": gi_row.get("gameDate"),
        "game_time_utc": gs_row.get("gameTimeUTC"),
        "game_et": gs_row.get("gameEt"),
        "game_status": gs_row.get("gameStatus"),
        "game_status_text": gs_row.get("gameStatusText"),
        "period": gs_row.get("period"),
        "game_duration": gi_row.get("gameDuration"),
        "is_neutral": False,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team_tricode": home_ls.get("teamTricode"),
        "away_team_tricode": away_ls.get("teamTricode"),
        "home_team_name": home_ls.get("teamName"),
        "away_team_name": away_ls.get("teamName"),
        "home_team_city": home_ls.get("teamCity"),
        "away_team_city": away_ls.get("teamCity"),
        "arena_id": ai_row.get("arenaId"),
        "arena_name": ai_row.get("arenaName"),
        "arena_city": ai_row.get("arenaCity"),
        "arena_state": ai_row.get("arenaState"),
        "arena_country": ai_row.get("arenaCountry"),
        "attendance": gs_row.get("attendance"),
        "sellout": gs_row.get("sellout"),
        "home_wins_before": home_ls.get("teamWins"),
        "home_losses_before": home_ls.get("teamLosses"),
        "away_wins_before": away_ls.get("teamWins"),
        "away_losses_before": away_ls.get("teamLosses"),
        "home_q1": home_ls.get("period1Score"),
        "home_q2": home_ls.get("period2Score"),
        "home_q3": home_ls.get("period3Score"),
        "home_q4": home_ls.get("period4Score"),
        "home_score": home_ls.get("score"),
        "away_q1": away_ls.get("period1Score"),
        "away_q2": away_ls.get("period2Score"),
        "away_q3": away_ls.get("period3Score"),
        "away_q4": away_ls.get("period4Score"),
        "away_score": away_ls.get("score"),
    }

    for k in ["pointsInThePaint", "pointsSecondChance", "pointsFastBreak",
              "biggestLead", "leadChanges", "timesTied", "biggestScoringRun",
              "turnoversTeam", "turnoversTotal", "reboundsTeam",
              "pointsFromTurnovers", "benchPoints"]:
        row[f"home_{k}"] = home_os.get(k)
        row[f"away_{k}"] = away_os.get(k)

    # --- Traditional V3 ---
    trad_ep = _safe_call(boxscoretraditionalv3.BoxScoreTraditionalV3,
                         game_id=game_id, end_period=10, end_range=28800,
                         range_type=0, start_period=1, start_range=0)
    if trad_ep:
        try:
            d = trad_ep.get_dict()["boxScoreTraditional"]
            for team_key, prefix in [("homeTeam", "home_"), ("awayTeam", "away_")]:
                td = d[team_key]
                row.update(_flat(td["statistics"], prefix))
                row[f"{prefix}bench_pts_trad"] = (td.get("bench") or {}).get("points")
                row[f"{prefix}starters_pts"] = (td.get("starters") or {}).get("points")
            _mark("traditional", "ok")
        except Exception as exc:
            _mark("traditional", _classify_exc(exc))
            audit["missing_cols"].append("traditional")
    else:
        _mark("traditional", "rate_limit" if summ_ep else "skipped")
        audit["missing_cols"].append("traditional")

    # --- Modern V3 endpoints (null statistics on pre-~2014 games) ---
    def _call_modern_ep(ep_class, ep_name, root_key, prefix_home, prefix_away, **kwargs):
        try:
            ep = ep_class(**kwargs)
            d = ep.get_dict()[root_key]
            row.update(_flat(d["homeTeam"]["statistics"], prefix_home))
            row.update(_flat(d["awayTeam"]["statistics"], prefix_away))
            throttle.record(True)
            _mark(ep_name, "ok")
        except AttributeError:
            # statistics is None — metric not tracked this era
            _mark(ep_name, "no_data")
            audit["missing_cols"].append(ep_name)
        except Exception as exc:
            outcome = _classify_exc(exc)
            _mark(ep_name, outcome)
            audit["missing_cols"].append(ep_name)
            if outcome in ("rate_limit", "timeout"):
                throttle.record(False)
                throttle.maybe_adjust()

    _call_modern_ep(boxscoreadvancedv3.BoxScoreAdvancedV3, "advanced", "boxScoreAdvanced",
                    "home_adv_", "away_adv_",
                    game_id=game_id, end_period=10, end_range=28800,
                    range_type=0, start_period=1, start_range=0)

    _call_modern_ep(boxscorefourfactorsv3.BoxScoreFourFactorsV3, "fourfactors", "boxScoreFourFactors",
                    "home_ff_", "away_ff_",
                    game_id=game_id, end_period=10, end_range=28800,
                    range_type=0, start_period=1, start_range=0)

    _call_modern_ep(boxscoremiscv3.BoxScoreMiscV3, "misc", "boxScoreMisc",
                    "home_misc_", "away_misc_",
                    game_id=game_id, end_period=10, end_range=28800,
                    range_type=0, start_period=1, start_range=0)

    _call_modern_ep(boxscorescoringv3.BoxScoreScoringV3, "scoring", "boxScoreScoring",
                    "home_scr_", "away_scr_",
                    game_id=game_id, end_period=10, end_range=28800,
                    range_type=0, start_period=1, start_range=0)

    # --- Hustle V2 ---
    hustle_ep = _safe_call(boxscorehustlev2.BoxScoreHustleV2, game_id=game_id)
    if hustle_ep:
        try:
            hd = hustle_ep.get_dict()["boxScoreHustle"]
            row.update(_flat(hd["homeTeam"]["statistics"], "home_hustle_"))
            row.update(_flat(hd["awayTeam"]["statistics"], "away_hustle_"))
            _mark("hustle", "ok")
        except Exception as exc:
            _mark("hustle", _classify_exc(exc))
            audit["missing_cols"].append("hustle")
    else:
        _mark("hustle", "rate_limit")
        audit["missing_cols"].append("hustle")

    _write_fetch_log(audit)
    return row


# ---------------------------------------------------------------------------
# ESPN enrichment
# ---------------------------------------------------------------------------

def _fetch_arena_capacities(team_ids: list[int]) -> dict[int, int | None]:
    from nba_api.stats.endpoints import teamdetails
    result: dict[int, int | None] = {}
    for tid in team_ids:
        try:
            td = teamdetails.TeamDetails(team_id=tid)
            df = td.team_background.get_data_frame()
            if not df.empty and "ARENACAPACITY" in df.columns:
                val = df.iloc[0]["ARENACAPACITY"]
                result[tid] = int(val) if pd.notna(val) else None
            else:
                result[tid] = None
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as exc:
            logger.debug("TeamDetails failed for %s: %s", tid, exc)
            result[tid] = None
    return result


# ESPN team name → NBA Stats tricode for teams whose abbreviation ESPN leaves blank.
# Discovered by sampling ESPN scoreboard across 1947-2015 for blank-abbreviation entries.
_ESPN_NAME_TO_TRICODE = {
    # Confirmed blank-abbr from systematic survey
    "Utah Jazz":                "UTA",
    "Atlanta Hawks":            "ATL",
    "Kansas City Kings":        "KCK",
    "Kansas City-Omaha Kings":  "KCK",
    "Rochester Royals":         "ROC",
    "San Diego Rockets":        "SDR",
    "Washington Bullets":       "WAS",
    # Other historical franchises likely to be blank
    "New Jersey Nets":          "NJN",
    "Seattle SuperSonics":      "SEA",
    "Vancouver Grizzlies":      "VAN",
    "San Diego Clippers":       "SDC",
    "Buffalo Braves":           "BUF",
    "Cincinnati Royals":        "CIN",
    "Baltimore Bullets":        "BAL",
    "Capital Bullets":          "CAP",
    "Chicago Packers":          "CHI",
    "Chicago Zephyrs":          "CHI",
    "New Orleans Jazz":         "NOJ",
}


def _fetch_espn_day(date_str: str) -> list[dict]:
    api_date = date_str.replace("-", "")
    try:
        resp = requests.get(ESPN_SCOREBOARD_URL, params={"dates": api_date}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("ESPN fetch failed for %s: %s", date_str, exc)
        return []

    results = []
    for event in data.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        if not event.get("status", {}).get("type", {}).get("completed", False):
            continue
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        venue = comp.get("venue") or {}

        def _abbr(c: dict) -> str:
            team = c.get("team") or {}
            abbr = team.get("abbreviation", "").strip().upper()
            if not abbr:
                # Fall back to name lookup for teams ESPN leaves blank (e.g. 1984 Jazz)
                name = team.get("displayName", "")
                abbr = _ESPN_NAME_TO_TRICODE.get(name, "").upper()
            return abbr

        results.append({
            "espn_event_id": str(event.get("id")),
            "espn_venue_id": str(venue.get("id")) if venue.get("id") else None,
            "date": date_str,
            "home_abbr": _abbr(home),
            "away_abbr": _abbr(away),
        })
    return results


def get_norm_abbreviation(abbr: str, date_str: str) -> str:
    """
    Normalise NBA Stats tricodes to match ESPN abbreviations for the join.
    Source: team_code_audit.csv cross-reference + systematic blank-abbr survey.
    ESPN uses shorter codes for several current franchises; historical teams with
    blank ESPN abbreviations are resolved via _ESPN_NAME_TO_TRICODE name lookup.
    """
    year = int(date_str[:4])

    if abbr in ("BKN", "NJN") and year < 2012:
        return "NJ"

    if abbr in ("NOH", "NOK", "NOP"):
        return "NO"

    static = {
        # Current teams ESPN shortens vs NBA Stats
        "SAS": "SA",
        "GSW": "GS",
        "NYK": "NY",
        "UTA": "UTAH",
        "WAS": "WSH",
        # Historical NBA Stats tricodes → ESPN equivalent (or name-lookup key)
        "UTH": "UTA",   # early Utah Jazz — ESPN blank, resolved by name
        "SAN": "SA",    # San Antonio Spurs pre-SAS
        "GOS": "GS",    # Golden State Warriors pre-GSW
        "GNS": "GS",    # Golden State Warriors (another old code)
        "PHL": "PHI",   # Philadelphia 76ers pre-PHI
        "NJN": "NJ",    # New Jersey Nets
        "SDR": "SDR",   # San Diego Rockets — ESPN blank
        "SDC": "SDC",   # San Diego Clippers — ESPN blank
        "KCK": "KCK",   # Kansas City Kings — ESPN blank
        "ROC": "ROC",   # Rochester Royals — ESPN blank
        "SEA": "SEA",
        "VAN": "VAN",
        "NOJ": "NOJ",   # New Orleans Jazz (pre-Utah)
        "BUF": "BUF",   # Buffalo Braves
        "CIN": "CIN",   # Cincinnati Royals
        "BAL": "BAL",   # Baltimore Bullets
        "CAP": "CAP",   # Capital Bullets
    }
    return static.get(abbr, abbr)


def enrich_espn(games_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    games_df = games_df.copy()
    for col in ["espn_event_id", "espn_venue_id", "capacity", "crowd_density"]:
        games_df.drop(columns=[col], errors="ignore", inplace=True)

    games_df["_date_str"] = pd.to_datetime(games_df["game_date"]).dt.strftime("%Y-%m-%d")
    unique_dates = games_df["_date_str"].dropna().unique().tolist()

    espn_rows: list[dict] = []
    dates_with_coverage: set[str] = set()  # dates ESPN returned ≥1 completed event
    logger.info("Fetching ESPN scoreboard for %d dates...", len(unique_dates))
    with ThreadPoolExecutor(max_workers=20) as ex:
        for date_str, rows in zip(unique_dates, ex.map(_fetch_espn_day, unique_dates)):
            if rows:
                dates_with_coverage.add(date_str)
            espn_rows.extend(rows)

    espn_df = pd.DataFrame(espn_rows)
    if espn_df.empty:
        logger.warning("No ESPN data retrieved.")
        for col in ["espn_event_id", "espn_venue_id", "capacity", "crowd_density"]:
            games_df[col] = None
        games_df.drop(columns=["_date_str"], inplace=True)
        id_map = pd.DataFrame(columns=["game_id", "espn_event_id", "game_date",
                                        "home_team_tricode", "away_team_tricode"])
        return games_df, id_map

    games_df["_h_norm"] = games_df.apply(
        lambda r: get_norm_abbreviation(str(r.get("home_team_tricode") or ""), r["_date_str"]), axis=1)
    games_df["_a_norm"] = games_df.apply(
        lambda r: get_norm_abbreviation(str(r.get("away_team_tricode") or ""), r["_date_str"]), axis=1)

    merged = games_df.merge(
        espn_df[["date", "home_abbr", "away_abbr", "espn_event_id", "espn_venue_id"]],
        left_on=["_date_str", "_h_norm", "_a_norm"],
        right_on=["date", "home_abbr", "away_abbr"],
        how="left",
    )
    # Timezone fallback: try +1 day shift
    espn_shifted = espn_df.copy()
    espn_shifted["date"] = (pd.to_datetime(espn_shifted["date"]) - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    merged2 = games_df.merge(
        espn_shifted[["date", "home_abbr", "away_abbr", "espn_event_id", "espn_venue_id"]],
        left_on=["_date_str", "_h_norm", "_a_norm"],
        right_on=["date", "home_abbr", "away_abbr"],
        how="left", suffixes=("", "_shift"),
    )
    for col in ["espn_event_id", "espn_venue_id"]:
        if col not in merged.columns:
            merged[col] = None
        if f"{col}_shift" in merged2.columns:
            merged[col] = merged[col].fillna(merged2[f"{col}_shift"])

    # Arena capacity from NBA Stats TeamDetails
    unique_home_ids = [int(x) for x in games_df["home_team_id"].dropna().unique()]
    logger.info("Fetching arena capacities for %d home teams...", len(unique_home_ids))
    cap_map = _fetch_arena_capacities(unique_home_ids)
    merged["capacity"] = merged["home_team_id"].map(cap_map)
    merged["attendance_num"] = pd.to_numeric(merged["attendance"], errors="coerce")
    merged["crowd_density"] = merged["attendance_num"] / merged["capacity"]

    merged.drop(columns=["attendance_num", "_h_norm", "_a_norm",
                          "date", "home_abbr", "away_abbr"], errors="ignore", inplace=True)
    # _date_str kept until after ESPN patch, dropped below

    rate = merged["espn_event_id"].notna().mean()
    logger.info("ESPN match rate: %.1f%%", rate * 100)

    # Split unmatched into coverage gap vs bad tricode mapping
    unmatched_rows = merged[merged["espn_event_id"].isna()][["game_id", "_date_str"]].copy()
    no_coverage = set(
        unmatched_rows.loc[~unmatched_rows["_date_str"].isin(dates_with_coverage), "game_id"].astype(str)
    )
    bad_mapping = set(
        unmatched_rows.loc[unmatched_rows["_date_str"].isin(dates_with_coverage), "game_id"].astype(str)
    )
    matched = set(merged.loc[merged["espn_event_id"].notna(), "game_id"].astype(str))
    if bad_mapping:
        logger.warning("%d games unmatched due to bad tricode mapping (ESPN had data for those dates): %s",
                       len(bad_mapping), sorted(bad_mapping)[:5])
    _patch_fetch_log_espn(matched, no_coverage, bad_mapping)
    merged.drop(columns=["_date_str"], errors="ignore", inplace=True)

    id_map = merged[["game_id", "espn_event_id", "game_date",
                      "home_team_tricode", "away_team_tricode", "espn_venue_id"]].copy()
    return merged, id_map


def _patch_fetch_log_espn(matched: set[str], no_coverage: set[str], bad_mapping: set[str]) -> None:
    """
    Rewrite fetch_log.jsonl with one of four espn_matched outcomes:
      ok               — matched by (date, home_abbr, away_abbr)
      espn_no_coverage — ESPN returned zero events for that date (historical gap)
      espn_bad_mapping — ESPN had events for that date but our tricode didn't match
      skipped          — game was already skipped at summary stage
    """
    if not FETCH_LOG.exists():
        return
    lines = FETCH_LOG.read_text().splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            gid = str(rec.get("game_id", ""))
            if rec.get("espn_matched") == "skipped":
                pass  # don't overwrite
            elif gid in matched:
                rec["espn_matched"] = "ok"
            elif gid in no_coverage:
                rec["espn_matched"] = "espn_no_coverage"
            elif gid in bad_mapping:
                rec["espn_matched"] = "espn_bad_mapping"
            out.append(json.dumps(rec))
        except json.JSONDecodeError:
            out.append(line)
    FETCH_LOG.write_text("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# Game ID discovery
# ---------------------------------------------------------------------------

def _fetch_season_game_ids(season_label: str) -> list[str]:
    from nba_api.stats.endpoints import leaguegamefinder
    for attempt in range(5):
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                league_id_nullable="00",
                season_nullable=season_label,
            )
            df = finder.get_data_frames()[0]
            return df["GAME_ID"].unique().tolist()
        except Exception as exc:
            wait = 2 ** attempt + random.uniform(0, 1)
            logger.warning("LeagueGameFinder attempt %d failed for %s: %s. Retrying in %.1fs...",
                           attempt + 1, season_label, exc, wait)
            time.sleep(wait)
    logger.error("LeagueGameFinder gave up on %s.", season_label)
    return []


def discover_game_ids(season: str | None, start_year: int | None) -> list[str]:
    from datetime import date as _date
    logger.info("Discovering game IDs (season=%s, start_year=%s)...", season, start_year)

    if season:
        return _fetch_season_game_ids(season)

    current_year = _date.today().year
    begin = start_year or 1946
    all_ids: list[str] = []
    for year in range(begin, current_year + 1):
        label = f"{year}-{str(year + 1)[-2:]}"
        ids = _fetch_season_game_ids(label)
        if ids:
            logger.info("  %s: %d games", label, len(ids))
            all_ids.extend(ids)
        time.sleep(random.uniform(1.0, 2.0))

    return list(dict.fromkeys(all_ids))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def _checkpoint(new_rows: list[dict], existing: pd.DataFrame,
                processed_ids: set[str], permanent_failures: set[str],
                skip_espn: bool) -> pd.DataFrame:
    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([existing, new_df], ignore_index=True, sort=False)
    combined["game_id"] = combined["game_id"].astype(str)
    combined = combined.drop_duplicates(subset=["game_id"], keep="last")
    combined = combined.sort_values("game_date").reset_index(drop=True)

    if not skip_espn:
        combined, id_map = enrich_espn(combined)
        _write_parquet(id_map, ID_MAP_OUT)

    _write_parquet(combined, GAMES_OUT)
    _save_state(processed_ids, permanent_failures)
    logger.info("Checkpoint: %d total games on disk. Workers=%d  SuccessRate=%.0f%%",
                len(combined), throttle.workers, throttle.success_rate() * 100)
    return combined


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False, compression="snappy")
    tmp.replace(path)


def load_existing(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Curate NBA historical box score data.")
    p.add_argument("--season", default=None, help="Single season, e.g. 2025-26")
    p.add_argument("--start-year", type=int, default=None)
    p.add_argument("--skip-espn", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Fetch only 5 games for testing")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_session()  # fresh session with random headers on startup

    # --- Resume state ---
    state = _load_state()
    processed_ids: set[str] = set(state.get("processed_ids", []))
    permanent_failures: set[str] = set(state.get("permanent_failures", []))

    # Also cross-check against parquet (in case state.json is stale)
    existing = load_existing(GAMES_OUT)
    if not existing.empty and "game_id" in existing.columns:
        processed_ids |= set(existing["game_id"].dropna().astype(str))
    if processed_ids:
        logger.info("Resuming: %d games already curated, %d permanent failures excluded.",
                    len(processed_ids), len(permanent_failures))

    # --- Discover ---
    game_ids = discover_game_ids(season=args.season, start_year=args.start_year)
    new_ids = [g for g in game_ids
               if str(g) not in processed_ids and str(g) not in permanent_failures]
    logger.info("%d new game IDs to fetch.", len(new_ids))

    if args.dry_run:
        new_ids = new_ids[:5]
        logger.info("Dry run: capped at 5 games.")

    # --- Fetch loop ---
    pending: list[dict] = []
    total = len(new_ids)

    executor = ThreadPoolExecutor(max_workers=throttle.workers)
    # Submit in batches so worker count changes take effect
    BATCH = 50
    completed = 0

    try:
        for batch_start in range(0, total, BATCH):
            batch = new_ids[batch_start: batch_start + BATCH]
            # Re-submit with current worker count
            executor = ThreadPoolExecutor(max_workers=throttle.workers)
            futures = {executor.submit(fetch_game, gid): gid for gid in batch}

            for fut in as_completed(futures):
                gid = futures[fut]
                row = fut.result()
                completed += 1

                if row is not None:
                    pending.append(row)
                    processed_ids.add(str(gid))
                else:
                    # Check if it was a permanent failure (logged inside fetch_game)
                    if str(gid)[:3] in _UNSUPPORTED_PREFIXES:
                        permanent_failures.add(str(gid))

                if completed % 20 == 0:
                    logger.info("Progress: %d / %d  pending=%d  workers=%d  success=%.0f%%",
                                completed, total, len(pending),
                                throttle.workers, throttle.success_rate() * 100)

                if len(pending) >= CHECKPOINT_EVERY:
                    existing = _checkpoint(pending, existing, processed_ids,
                                           permanent_failures, args.skip_espn)
                    pending = []

                time.sleep(throttle.jitter())

            executor.shutdown(wait=False)

    except KeyboardInterrupt:
        logger.info("Interrupted. Flushing %d pending rows...", len(pending))
        for f in futures:
            f.cancel()
        executor.shutdown(wait=False)

    # Final flush
    if pending:
        existing = _checkpoint(pending, existing, processed_ids,
                                permanent_failures, args.skip_espn)

    if not args.skip_espn and pending:
        combined, id_map = enrich_espn(existing)
        _write_parquet(id_map, ID_MAP_OUT)
        _write_parquet(combined, GAMES_OUT)
        logger.info("Final ESPN enrichment complete: %d games.", len(combined))

    _save_state(processed_ids, permanent_failures)
    logger.info("Done. State saved. %d games total.", len(existing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
