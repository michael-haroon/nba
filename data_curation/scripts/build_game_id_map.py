"""
build_game_id_map.py
--------------------
Builds data/game_id_map.parquet: NBA game_id ↔ ESPN event_id cross-reference.
Uses team_mappings.parquet as the source of truth for tricode conversions.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "build_game_id_map.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

class TeamMapper:
    """Handles tricode conversions using team_mappings.parquet."""
    def __init__(self, mapping_path: Path):
        if not mapping_path.exists():
            logger.error(f"Mapping file not found: {mapping_path}")
            sys.exit(1)
        
        df = pd.read_parquet(mapping_path)
        
        # Primary lookup: NBA Tricode -> ESPN Abbreviation
        # We use a dictionary for O(1) lookups during the matching loop
        self.nba_to_espn_abbr = df.set_index("TEAM_ABBREVIATION")["ESPN_ABBR"].to_dict()
        
        # Fallback lookup: ESPN Display Name -> ESPN Abbreviation
        # Useful for older ESPN API responses where the abbreviation field is null
        self.espn_name_to_abbr = df.dropna(subset=["ESPN_NAME"]).set_index("ESPN_NAME")["ESPN_ABBR"].to_dict()
        
        # Set of valid NBA franchises (anything not in here is likely a foreign/preseason team)
        self.valid_nba_tricodes = set(df["TEAM_ABBREVIATION"].unique())

    def get_espn_abbr(self, nba_abbr: str) -> str | None:
        """Returns the ESPN version of an NBA tricode."""
        return self.nba_to_espn_abbr.get(nba_abbr)

    def resolve_espn_scoreboard_abbr(self, display_name: str, current_abbr: str) -> str:
        """Fixes blank or weird abbreviations directly from the ESPN scoreboard response."""
        if current_abbr and current_abbr.strip():
            return current_abbr.strip().upper()
        return self.espn_name_to_abbr.get(display_name, "").upper()

def _fetch_espn_date(date_str: str, mapper: TeamMapper) -> dict[tuple[str, str], str]:
    """
    Fetch ESPN scoreboard for one YYYY-MM-DD date.
    Returns {(home_espn_abbr, away_espn_abbr): espn_event_id}.
    """
    api_date = date_str.replace("-", "")
    try:
        r = requests.get(_SCOREBOARD_URL, params={"dates": api_date}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.debug("ESPN fetch failed %s: %s", date_str, exc)
        return {}

    result: dict[tuple[str, str], str] = {}
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        h_team = home.get("team", {})
        a_team = away.get("team", {})
        
        h = mapper.resolve_espn_scoreboard_abbr(h_team.get("displayName", ""), h_team.get("abbreviation", ""))
        a = mapper.resolve_espn_scoreboard_abbr(a_team.get("displayName", ""), a_team.get("abbreviation", ""))
        
        eid = str(event.get("id", ""))
        if h and a and eid:
            result[(h, a)] = eid
            result[(a, h)] = eid  # handles flip edge cases
    return result

def _get_nba_games(seasons: list[str] | None, start_year: int | None) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguegamefinder

    if seasons:
        season_list = seasons
    else:
        current = datetime.now().year
        begin = start_year or 1946
        season_list = [f"{y}-{str(y+1)[-2:]}" for y in range(begin, current + 1)]

    all_frames = []
    for season in season_list:
        logger.info("  Fetching NBA game IDs for %s...", season)
        for attempt in range(4):
            try:
                gf = leaguegamefinder.LeagueGameFinder(season_nullable=season, league_id_nullable="00")
                df = gf.get_data_frames()[0]
                if df.empty: break
                all_frames.append(df)
                time.sleep(random.uniform(0.8, 1.5))
                break
            except Exception as exc:
                wait = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"Retry {attempt+1} for {season}: {exc}")
                time.sleep(wait)

    if not all_frames: return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True).drop_duplicates(subset=["GAME_ID"])
    combined["is_home"] = combined["MATCHUP"].str.contains(r"vs\.", regex=True)
    combined["home_abbr_nba"] = combined.apply(
        lambda r: r["TEAM_ABBREVIATION"] if r["is_home"] else r["MATCHUP"].split(" @ ")[-1].strip(), axis=1)
    combined["away_abbr_nba"] = combined.apply(
        lambda r: r["MATCHUP"].split(" vs. ")[-1].strip() if r["is_home"] else r["TEAM_ABBREVIATION"], axis=1)
    combined["game_date_et"] = pd.to_datetime(combined["GAME_DATE"]).dt.strftime("%Y-%m-%d")
    
    return combined[["GAME_ID", "game_date_et", "home_abbr_nba", "away_abbr_nba"]].rename(columns={"GAME_ID": "game_id"})

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build NBA→ESPN game ID map.")
    p.add_argument("--seasons", nargs="+", default=None)
    p.add_argument("--start-year", type=int, default=None)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    map_path = DATA_DIR / "game_id_map.parquet"
    mapping_path = DATA_DIR / "team_mappings.parquet"

    # Initialize Mapper
    mapper = TeamMapper(mapping_path)

    existing_matched: set[str] = set()
    existing_df = pd.DataFrame()
    if map_path.exists() and not args.force:
        existing_df = pd.read_parquet(map_path)
        existing_matched = set(existing_df.loc[existing_df["espn_event_id"].notna(), "game_id"].astype(str))

    nba_games = _get_nba_games(args.seasons, args.start_year)
    if nba_games.empty: return 1

    to_process = nba_games[~nba_games["game_id"].astype(str).isin(existing_matched)].copy()
    if to_process.empty:
        logger.info("Nothing to do.")
        return 0

    # Convert using our dynamic mapper
    to_process["home_espn"] = to_process["home_abbr_nba"].apply(mapper.get_espn_abbr)
    to_process["away_espn"] = to_process["away_abbr_nba"].apply(mapper.get_espn_abbr)

    dates_to_fetch = sorted(to_process["game_date_et"].unique().tolist())
    date_results: dict[str, dict] = {}
    
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_fetch_espn_date, d, mapper): d for d in dates_to_fetch}
        for i, fut in enumerate(as_completed(futures), 1):
            date_results[futures[fut]] = fut.result()
            if i % 100 == 0: logger.info(f"Fetched {i}/{len(dates_to_fetch)} dates")

    rows = []
    for _, g in to_process.iterrows():
        gid = str(g["game_id"])
        date = g["game_date_et"]
        h = g["home_espn"]
        a = g["away_espn"]
        
        # Capture the keys available for this date to diagnose mismatches
        day_map = date_results.get(date, {})
        available_keys = list(day_map.keys())

        if h is None or a is None:
            rows.append({
                **g,
                "espn_event_id": None,
                "home_abbr_espn": h,
                "away_abbr_espn": a,
                "match_method": "non_nba_team",
                "espn_map_keys": str(available_keys) # Full payload of keys for that day
            })
            continue

        eid = day_map.get((h, a))
        method = "same_day" if eid else None

        if not eid:
            # Try adjacent dates for UTC/ET boundary edge cases
            dt = datetime.strptime(date, "%Y-%m-%d")
            for delta in (-1, 1):
                adj = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
                adj_map = date_results.get(adj, {})
                eid = adj_map.get((h, a))
                if eid:
                    method = "day_shift"
                    available_keys = list(adj_map.keys()) # Update keys to the shifted day
                    break

        rows.append({
            "game_id": gid,
            "espn_event_id": eid,
            "game_date_et": date,
            "home_abbr_nba": g["home_abbr_nba"],
            "away_abbr_nba": g["away_abbr_nba"],
            "home_abbr_espn": h,
            "away_abbr_espn": a,
            "match_method": method or "no_match",
            "espn_map_keys": str(available_keys) # See what ESPN actually had
        })

    new_df = pd.DataFrame(rows)
    combined = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=["game_id"], keep="last")
    combined.sort_values("game_date_et").to_parquet(map_path, index=False)
    
    logger.info(f"Done. Match rate: {combined['espn_event_id'].notna().sum() / len(combined):.1%}")
    return 0

if __name__ == "__main__":
    sys.exit(main())