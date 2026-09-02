"""
sync_games.py
-------------
Fetches all completed games missing from local parquets and appends them.
Supports both NBA and WNBA via --league flag.

Usage:
    python data_curation/scripts/sync_games.py --league nba [--dry-run] [--season 2025-26] [--workers 3]
    python data_curation/scripts/sync_games.py --league wnba [--dry-run] [--season 2025] [--workers 3]

After new games are written, rebuilds MasseyRatings.parquet automatically.
"""
from __future__ import annotations

import argparse
import logging
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from league_config import get_league_config, add_league_arg, LeagueConfig

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "sync_games.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column normalization maps: nba_api V3 camelCase → existing parquet columns
# ---------------------------------------------------------------------------

_TRAD_RENAME = {
    "teamTricode": "TEAM",
    "matchup": "MATCH UP",
    "gameDate": "GAME DATE",
    "wl": "W/L",
    "minutes": "MIN",
    "points": "PTS",
    "fieldGoalsMade": "FGM",
    "fieldGoalsAttempted": "FGA",
    "fieldGoalsPercentage": "FG%",
    "threePointersMade": "3PM",
    "threePointersAttempted": "3PA",
    "threePointersPercentage": "3P%",
    "freeThrowsMade": "FTM",
    "freeThrowsAttempted": "FTA",
    "freeThrowsPercentage": "FT%",
    "reboundsOffensive": "OREB",
    "reboundsDefensive": "DREB",
    "reboundsTotal": "REB",
    "assists": "AST",
    "turnovers": "TOV",
    "steals": "STL",
    "blocks": "BLK",
    "foulsPersonal": "PF",
    "plusMinusPoints": "+/-",
}

_ADV_RENAME = {
    "teamTricode": "TEAM",
    "matchup": "MATCH UP",
    "gameDate": "GAME DATE",
    "wl": "W/L",
    "minutes": "MIN",
    "offensiveRating": "OFFRTG",
    "defensiveRating": "DEFRTG",
    "netRating": "NETRTG",
    "assistPercentage": "AST%",
    "assistToTurnover": "AST/TO",
    "assistRatio": "AST RATIO",
    "offensiveReboundPercentage": "OREB%",
    "defensiveReboundPercentage": "DREB%",
    "reboundPercentage": "REB%",
    "turnoverRatio": "TOV%",
    "effectiveFieldGoalPercentage": "EFG%",
    "trueShootingPercentage": "TS%",
    "pace": "PACE",
    "PIE": "PIE",
}

_FF_RENAME = {
    "teamTricode": "TEAM",
    "matchup": "MATCH UP",
    "gameDate": "GAME DATE",
    "wl": "W/L",
    "minutes": "MIN",
    "effectiveFieldGoalPercentage": "EFG%",
    "freeThrowAttemptRate": "FTA RATE",
    "teamTurnoverPercentage": "TOV%",
    "offensiveReboundPercentage": "OREB%",
    "oppEffectiveFieldGoalPercentage": "OPP EFG%",
    "oppFreeThrowAttemptRate": "OPP FTA RATE",
    "oppTeamTurnoverPercentage": "OPP TOV%",
    "oppOffensiveReboundPercentage": "OPP OREB%",
}

_MISC_RENAME = {
    "teamTricode": "TEAM",
    "matchup": "MATCH UP",
    "gameDate": "GAME DATE",
    "wl": "W/L",
    "minutes": "MIN",
    "pointsOffTurnovers": "PTS OFF TO",
    "pointsSecondChance": "2ND PTS",
    "pointsFastBreak": "FBPS",
    "pointsPaint": "PITP",
    "oppPointsOffTurnovers": "OPP PTS OFF TO",
    "oppPointsSecondChance": "OPP 2ND PTS",
    "oppPointsFastBreak": "OPP FBPS",
    "oppPointsPaint": "OPP PITP",
}

_SCORING_RENAME = {
    "teamTricode": "TEAM",
    "matchup": "MATCH UP",
    "gameDate": "GAME DATE",
    "wl": "W/L",
    "minutes": "MIN",
    "percentageFieldGoalsAttempted2pt": "%FGA 2PT",
    "percentageFieldGoalsAttempted3pt": "%FGA 3PT",
    "percentagePoints2pt": "%PTS 2PT",
    "percentagePointsMidrange2pt": "%PTS 2PT MR",
    "percentagePoints3pt": "%PTS 3PT",
    "percentagePointsFastBreak": "%PTS FBPS",
    "percentagePointsFreeThrow": "%PTS FT",
    "percentagePointsOffTurnovers": "%PTS OFF TO",
    "percentagePointsPaint": "%PTS PITP",
    "percentageAssisted2pt": "2FGM %AST",
    "percentageUnassisted2pt": "2FGM %UAST",
    "percentageAssisted3pt": "3FGM %AST",
    "percentageUnassisted3pt": "3FGM %UAST",
    "percentageAssistedFGM": "FGM %AST",
    "percentageUnassistedFGM": "FGM %UAST",
}

SEASON_TYPE_SUFFIX = {
    "Regular Season": "Regular",
    "Playoffs": "Playoffs",
    "Pre Season": "Pre",
}


# ---------------------------------------------------------------------------
# Parquet dedup keys
# ---------------------------------------------------------------------------

_ADV_DEDUP = ["game_id", "TEAM"]

PARQUET_DEDUP_KEYS: dict[str, list[str]] = {
    "BoxScoresHustleTeam.parquet": ["game_id", "TEAM_ID"],
    "GameSummaries.parquet": ["game_id"],
    "GameOfficials.parquet": ["game_id", "official_id"],
    "TeamQuarterScores.parquet": ["game_id", "team_id", "period_label"],
    "PlayByPlay.parquet": ["gameId", "actionId"],
    "HustleGames.parquet": ["gameId"],
    "HustlePlayerStats.parquet": ["gameId", "personId"],
    "SummaryGameMeta.parquet": ["gameId"],
    "SummaryBroadcasters.parquet": ["gameId", "broadcast_type", "broadcasterId"],
    "SummaryLastFive.parquet": ["gameId", "recencyOrder"],
    "SummaryOfficials.parquet": ["gameId", "personId"],
    "SummaryPlayers.parquet": ["gameId", "personId", "side"],
    "SummaryPostgameCharts.parquet": ["gameId"],
    "SummaryPregameCharts.parquet": ["gameId"],
    "SummaryTeamScores.parquet": ["gameId"],
}
for _suffix in ("Regular", "Playoffs", "Pre"):
    for _prefix in ("AdvBoxScoresTrad", "AdvBoxScoresAdv", "AdvBoxScoresFourFactors", "AdvBoxScoresMisc", "AdvBoxScoresScoring"):
        PARQUET_DEDUP_KEYS[f"{_prefix}{_suffix}.parquet"] = _ADV_DEDUP

# Percentage columns that the V3 API returns as decimals (0.473) but existing
# parquets store as whole numbers (47.3). Scale on write.
_PCT_COLS = {"FG%", "3P%", "FT%", "EFG%", "TS%", "FTA RATE",
             "TOV%", "OREB%", "DREB%", "REB%", "AST%",
             "OPP EFG%", "OPP FTA RATE", "OPP TOV%", "OPP OREB%",
             "%FGA 2PT", "%FGA 3PT", "%PTS 2PT", "%PTS 2PT MR", "%PTS 3PT",
             "%PTS FBPS", "%PTS FT", "%PTS OFF TO", "%PTS PITP",
             "2FGM %AST", "2FGM %UAST", "3FGM %AST", "3FGM %UAST",
             "FGM %AST", "FGM %UAST", "PIE"}

# BoxScoreAdvancedV3 returns turnoverRatio already as a percentage (17.4, not 0.174).
# Exclude TOV% from scaling for that endpoint only.
_ADV_SKIP_PCT = {"TOV%"}

# BoxScoreFourFactorsV3: FTA RATE and OPP FTA RATE are returned as decimals (0.364)
# and historical parquets store them as decimals too. Do NOT scale these.
_FF_SKIP_PCT = {"FTA RATE", "OPP FTA RATE"}


# ---------------------------------------------------------------------------
# Game ID refresh
# ---------------------------------------------------------------------------

def refresh_game_ids(data_dir: Path, season: str, cfg: LeagueConfig) -> None:
    """Fetches the latest game IDs for season and upserts the game IDs parquet."""
    from nba_api.stats.endpoints import leaguegamefinder

    path = data_dir / cfg.game_ids_file
    existing: set[str] = set()
    existing_df = pd.DataFrame()
    if path.exists():
        existing_df = pd.read_parquet(path)
        existing = set(existing_df["GAME_ID"].astype(str))

    frames = []
    for season_type in ("Regular Season", "Pre Season", "Playoffs"):
        for attempt in range(4):
            try:
                gf = leaguegamefinder.LeagueGameFinder(
                    season_nullable=season,
                    league_id_nullable=cfg.league_id,
                    season_type_nullable=season_type,
                )
                df = gf.get_data_frames()[0]
                if df.empty:
                    break
                df = df[["GAME_ID", "GAME_DATE"]].copy()
                df["SEASON_FILTER"] = season
                df["SEASON_TYPE_FILTER"] = season_type
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
                df["GAME_ID"] = df["GAME_ID"].astype("int64")
                frames.append(df)
                time.sleep(random.uniform(0.8, 1.5))
                break
            except Exception as exc:
                wait = 2 ** attempt + random.uniform(0, 1)
                logger.warning("Retry %d for %s/%s: %s", attempt + 1, season, season_type, exc)
                time.sleep(wait)

    if not frames:
        logger.warning("No game IDs fetched for %s", season)
        return

    new_df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["GAME_ID"])
    new_only = new_df[~new_df["GAME_ID"].astype(str).isin(existing)]
    if new_only.empty:
        logger.info("%s already current for %s", cfg.game_ids_file, season)
        return

    combined = pd.concat([existing_df, new_only], ignore_index=True).drop_duplicates(
        subset=["GAME_ID"], keep="last"
    )
    combined.to_parquet(path, index=False)
    logger.info("%s updated: +%d new games (total %d)", cfg.game_ids_file, len(new_only), len(combined))


# ---------------------------------------------------------------------------
# Find missing games
# ---------------------------------------------------------------------------

def find_missing_games(data_dir: Path, cfg: LeagueConfig) -> list[str]:
    """Returns zero-padded game IDs that are in the game IDs parquet but not yet synced.

    Completeness is determined by two sources, unioned:
      1. synccomplete.parquet — stamped only after all tables are written for a game.
      2. AdvBoxScoresTrad{suffix} game_id column — present only for rows written by
         this sync script (not the old scraper). This catches games synced before
         synccomplete.parquet existed.

    Games whose date is *after* the latest date in AdvBoxScoresTrad are
    always treated as missing, regardless of GameSummaries. This is the key check that
    catches the "GameSummaries has the row but AdvBoxScores is stale" failure mode.
    """
    ids_path = data_dir / cfg.game_ids_file
    if not ids_path.exists():
        logger.error("%s not found in %s", cfg.game_ids_file, data_dir)
        return []

    ids_df = pd.read_parquet(ids_path)
    today = pd.Timestamp(date.today())
    v3_cutoff = pd.Timestamp("2014-10-01")
    past = ids_df[
        (ids_df["GAME_DATE"].dt.normalize() <= today) &
        (ids_df["GAME_DATE"] >= v3_cutoff)
    ]
    all_ids_df = past[["GAME_ID", "GAME_DATE"]].copy()
    all_ids_df["GAME_ID_STR"] = all_ids_df["GAME_ID"].astype(str).str.zfill(10)

    # --- Source 1: games written by this sync script (have game_id in AdvBoxScoresTrad) ---
    done: set[str] = set()
    for suffix in ("Regular", "Playoffs", "Pre"):
        path = data_dir / f"AdvBoxScoresTrad{suffix}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "game_id" in df.columns:
            done |= set(df["game_id"].dropna().astype(str).str.zfill(10))

    # --- Source 2: synccomplete.parquet (stamped after all tables written) ---
    complete_path = data_dir / "synccomplete.parquet"
    if complete_path.exists():
        done |= set(pd.read_parquet(complete_path, columns=["game_id"])["game_id"].astype(str).str.zfill(10))

    # --- Source 3: GameSummaries as historical proxy for pre-watermark games ---
    # The old scraper populated GameSummaries for all historical games. For games
    # predating the V3 sync system (i.e. before the AdvBoxScores watermark), we trust
    # GameSummaries as a "done" signal since we are not trying to re-sync those.
    adv_watermark = pd.Timestamp("2014-10-01")
    for suffix in ("Regular", "Playoffs", "Pre"):
        path = data_dir / f"AdvBoxScoresTrad{suffix}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["GAME DATE"])
        mx = pd.to_datetime(df["GAME DATE"]).max()
        if pd.notna(mx) and mx > adv_watermark:
            adv_watermark = mx

    gs_path = data_dir / "GameSummaries.parquet"
    if gs_path.exists():
        gs_ids = set(pd.read_parquet(gs_path, columns=["game_id"])["game_id"].astype(str).str.zfill(10))
        # Only credit GameSummaries for games on or before the AdvBoxScores watermark.
        # Games after the watermark must be explicitly re-synced even if GameSummaries has them.
        pre_watermark_ids = set(
            all_ids_df[all_ids_df["GAME_DATE"].dt.normalize() <= adv_watermark]["GAME_ID_STR"]
        )
        done |= gs_ids & pre_watermark_ids

    # Any game after the watermark is missing from AdvBoxScores regardless of GameSummaries
    after_watermark = set(
        all_ids_df[all_ids_df["GAME_DATE"] > adv_watermark]["GAME_ID_STR"]
    )
    missing_ids = (set(all_ids_df["GAME_ID_STR"]) - done) | after_watermark

    missing = sorted(missing_ids)
    logger.info(
        "Missing games: %d (of %d V3-eligible past games) | AdvBoxScores watermark: %s",
        len(missing), len(all_ids_df), adv_watermark.date()
    )
    return missing


# ---------------------------------------------------------------------------
# Season type lookup
# ---------------------------------------------------------------------------

def _season_type_suffix(game_id: str, ids_df: pd.DataFrame) -> str:
    gid = int(game_id.lstrip("0") or "0")
    rows = ids_df[ids_df["GAME_ID"] == gid]
    if rows.empty:
        return "Regular"
    stype = rows.iloc[0]["SEASON_TYPE_FILTER"]
    return SEASON_TYPE_SUFFIX.get(stype, "Regular")


# ---------------------------------------------------------------------------
# Fetch one game
# ---------------------------------------------------------------------------

def _normalize_adv(df: pd.DataFrame, rename_map: dict, game_id: str, matchup: str, game_date: str, wl_map: dict) -> pd.DataFrame:
    """Add matchup/date/wl context from summary and rename to legacy column format."""
    df = df.copy()
    df["matchup"] = df["teamId"].map(lambda tid: matchup if tid else matchup)
    df["gameDate"] = pd.to_datetime(game_date)
    df["wl"] = df["teamId"].map(wl_map)
    return df.rename(columns=rename_map)[[c for c in rename_map.values() if c in df.rename(columns=rename_map).columns]]


def fetch_game(game_id: str, cfg: LeagueConfig | None = None) -> dict[str, pd.DataFrame | None]:
    """Fetches all box score data for one completed game.

    Returns a dict mapping parquet-stem keys to DataFrames (or None on failure).
    """
    import json as _json

    from nba_api.stats.endpoints import (
        boxscoreadvancedv3,
        boxscorefourfactorsv3,
        hustlestatsboxscore,
        boxscoremiscv3,
        boxscorescoringv3,
        boxscoresummaryv3,
        boxscoretraditionalv3,
    )

    gid = str(game_id).zfill(10)
    result: dict[str, pd.DataFrame | None] = {k: None for k in [
        "GameSummaries", "GameOfficials", "TeamQuarterScores", "BoxScoresHustleTeam",
        "AdvBoxScoresTrad", "AdvBoxScoresAdv",
        "AdvBoxScoresFourFactors", "AdvBoxScoresMisc", "AdvBoxScoresScoring",
        "PlayByPlay", "HustleGames", "HustlePlayerStats",
        "SummaryGameMeta", "SummaryBroadcasters", "SummaryLastFive",
        "SummaryOfficials", "SummaryPlayers", "SummaryPostgameCharts",
        "SummaryPregameCharts", "SummaryTeamScores",
    ]}

    # --- Summary (provides game context for adv box score normalization) ---
    summary_row = None
    summary_raw_json: dict | None = None
    matchup_by_team: dict[int, str] = {}
    wl_by_team: dict[int, str] = {}
    game_date_str = ""

    for attempt in range(3):
        try:
            logger.info("[%s] attempt %d: BoxScoreSummaryV3", gid, attempt + 1)
            ep = boxscoresummaryv3.BoxScoreSummaryV3(game_id=gid)
            summary_raw_json = _json.loads(ep.nba_response.get_json())
            gs = ep.game_summary.get_data_frame()
            ls = ep.line_score.get_data_frame()
            officials = ep.officials.get_data_frame()
            arena = ep.arena_info.get_data_frame()

            if gs.empty:
                logger.warning("[%s] BoxScoreSummaryV3 returned empty game_summary", gid)
                break

            row = gs.iloc[0]
            home_id = int(row["homeTeamId"])
            away_id = int(row["awayTeamId"])
            game_date_str = str(pd.to_datetime(row["gameEt"]).date())

            home_line = ls[ls["teamId"] == home_id].iloc[0] if not ls.empty else None
            away_line = ls[ls["teamId"] == away_id].iloc[0] if not ls.empty else None

            if home_line is not None and away_line is not None:
                home_score = int(home_line["score"] or 0)
                away_score = int(away_line["score"] or 0)
                home_tri = str(home_line["teamTricode"])
                away_tri = str(away_line["teamTricode"])

                matchup_by_team[home_id] = f"{home_tri} vs. {away_tri}"
                matchup_by_team[away_id] = f"{away_tri} @ {home_tri}"
                wl_by_team[home_id] = "W" if home_score > away_score else "L"
                wl_by_team[away_id] = "W" if away_score > home_score else "L"

                # GameSummaries — matches GameSummaries.parquet schema exactly
                arena_row = arena.iloc[0] if not arena.empty else None
                result["GameSummaries"] = pd.DataFrame([{
                    "game_id": gid,
                    "game_code": row.get("gameCode"),
                    "game_status": int(row.get("gameStatus", 0)),
                    "game_time_utc": str(row.get("gameTimeUTC", "")),
                    "arena_name": str(arena_row.get("arenaName", "")) if arena_row is not None else "",
                    "arena_city": str(arena_row.get("arenaCity", "")) if arena_row is not None else "",
                    "attendance": int(row.get("attendance") or 0),
                    "sellout_flag": int(row.get("sellout") or 0),
                }])

                # TeamQuarterScores — matches TeamQuarterScores.parquet schema exactly
                if not ls.empty:
                    qrows = []
                    for _, team_row in ls.iterrows():
                        tid = int(team_row["teamId"])
                        for q in range(1, 5):
                            col = f"period{q}Score"
                            if col in team_row:
                                qrows.append({
                                    "game_id": gid,
                                    "team_id": tid,
                                    "period_label": f"Q{q}",
                                    "period_score": int(team_row[col] or 0),
                                })
                    if qrows:
                        result["TeamQuarterScores"] = pd.DataFrame(qrows)

            # GameOfficials
            if not officials.empty:
                off_df = officials.copy()
                off_df["game_id"] = gid
                off_df = off_df.rename(columns={"personId": "official_id", "name": "official_name", "jerseyNum": "jersey_num"})
                result["GameOfficials"] = off_df[["game_id", "official_id", "official_name", "jersey_num"]]

            summary_row = row
            logger.info("[%s] BoxScoreSummaryV3 OK", gid)
            break
        except AttributeError as exc:
            # API returned None datasets — no data exists for this game, don't retry
            logger.warning("[%s] BoxScoreSummaryV3 no data (API returned None): %s — skipping", gid, exc)
            return result
        except Exception as exc:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logger.warning("[%s] BoxScoreSummaryV3 attempt %d failed (%s: %s) — retrying in %.1fs",
                           gid, attempt + 1, type(exc).__name__, exc, wait)
            time.sleep(wait)

    if summary_row is None:
        logger.error("[%s] BoxScoreSummaryV3 exhausted retries — skipping game", gid)
        return result

    # --- Hustle (only for games after 2016-10-01, and only for leagues with hustle data) ---
    # Uses HustleStatsBoxScore: df[2]=team stats, df[1]=player stats (BoxScoreHustleV2 deprecated)
    _has_hustle = cfg.has_hustle if cfg else True
    if _has_hustle and game_date_str >= "2016-10-01":
        time.sleep(random.uniform(0.6, 1.2))
        for attempt in range(3):
            try:
                logger.info("[%s] attempt %d: HustleStatsBoxScore", gid, attempt + 1)
                hustle_ep = hustlestatsboxscore.HustleStatsBoxScore(game_id=gid)
                hustle_dfs = hustle_ep.get_data_frames()
                df_hustle_raw = hustle_dfs[2]  # team stats
                df_player_raw = hustle_dfs[1]  # player stats

                if not df_hustle_raw.empty:
                    # Rename SCREAMING_SNAKE_CASE → camelCase to match existing parquet schema
                    team_rename = {
                        "GAME_ID": "gameId", "TEAM_ID": "teamId", "TEAM_NAME": "teamName",
                        "TEAM_ABBREVIATION": "teamTricode", "TEAM_CITY": "teamCity",
                        "MINUTES": "minutes", "PTS": "points",
                        "CONTESTED_SHOTS": "contestedShots", "CONTESTED_SHOTS_2PT": "contestedShots2pt",
                        "CONTESTED_SHOTS_3PT": "contestedShots3pt", "DEFLECTIONS": "deflections",
                        "CHARGES_DRAWN": "chargesDrawn", "SCREEN_ASSISTS": "screenAssists",
                        "SCREEN_AST_PTS": "screenAssistPoints",
                        "OFF_LOOSE_BALLS_RECOVERED": "looseBallsRecoveredOffensive",
                        "DEF_LOOSE_BALLS_RECOVERED": "looseBallsRecoveredDefensive",
                        "LOOSE_BALLS_RECOVERED": "looseBallsRecoveredTotal",
                        "OFF_BOXOUTS": "offensiveBoxOuts", "DEF_BOXOUTS": "defensiveBoxOuts",
                        "BOX_OUT_PLAYER_TEAM_REBS": "boxOutPlayerTeamRebounds",
                        "BOX_OUT_PLAYER_REBS": "boxOutPlayerRebounds", "BOX_OUTS": "boxOuts",
                    }
                    df_hustle = df_hustle_raw.rename(columns=team_rename).copy()
                    df_hustle["teamSlug"] = None  # not provided by this endpoint
                    df_hustle["game_id"] = gid
                    result["BoxScoresHustleTeam"] = df_hustle

                    # HustleGames: pivot 2 team rows into 1 game row with home/away prefixes
                    home_id = int(summary_row["homeTeamId"]) if summary_row is not None else None
                    if home_id is not None and len(df_hustle) == 2:
                        hustle_row = {"gameId": gid}
                        for _, hr in df_hustle.iterrows():
                            tid = hr.get("teamId")
                            prefix = "homeTeam" if int(tid) == home_id else "awayTeam"
                            hustle_row[f"{prefix}Id"] = tid
                            for col in df_hustle.columns:
                                if col not in ("game_id", "teamId"):
                                    hustle_row[f"{prefix}_{col}"] = hr[col]
                        result["HustleGames"] = pd.DataFrame([hustle_row])

                if not df_player_raw.empty:
                    player_rename = {
                        "GAME_ID": "gameId", "TEAM_ID": "teamId", "TEAM_CITY": "teamCity",
                        "TEAM_NAME": "teamName", "TEAM_ABBREVIATION": "teamTricode",
                        "PLAYER_ID": "personId", "PLAYER_NAME": "nameI",
                        "START_POSITION": "position", "COMMENT": "comment",
                        "MINUTES": "minutes", "PTS": "points",
                        "CONTESTED_SHOTS": "contestedShots", "CONTESTED_SHOTS_2PT": "contestedShots2pt",
                        "CONTESTED_SHOTS_3PT": "contestedShots3pt", "DEFLECTIONS": "deflections",
                        "CHARGES_DRAWN": "chargesDrawn", "SCREEN_ASSISTS": "screenAssists",
                        "SCREEN_AST_PTS": "screenAssistPoints",
                        "OFF_LOOSE_BALLS_RECOVERED": "looseBallsRecoveredOffensive",
                        "DEF_LOOSE_BALLS_RECOVERED": "looseBallsRecoveredDefensive",
                        "LOOSE_BALLS_RECOVERED": "looseBallsRecoveredTotal",
                        "OFF_BOXOUTS": "offensiveBoxOuts", "DEF_BOXOUTS": "defensiveBoxOuts",
                        "BOX_OUT_PLAYER_TEAM_REBS": "boxOutPlayerTeamRebounds",
                        "BOX_OUT_PLAYER_REBS": "boxOutPlayerRebounds", "BOX_OUTS": "boxOuts",
                    }
                    df_player = df_player_raw.rename(columns=player_rename).copy()
                    # Fill columns present in existing parquet but absent from this endpoint
                    for col in ("firstName", "familyName", "playerSlug", "teamSlug", "jerseyNum", "side", "slot"):
                        df_player[col] = None
                    df_player["gameId"] = gid
                    result["HustlePlayerStats"] = df_player

                logger.info("[%s] HustleStatsBoxScore OK (team=%d, player=%d rows)",
                            gid, len(df_hustle_raw), len(df_player_raw))
                break
            except Exception as exc:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning("[%s] HustleStatsBoxScore attempt %d failed (%s: %s) — retrying in %.1fs",
                               gid, attempt + 1, type(exc).__name__, exc, wait)
                time.sleep(wait)

    # --- Advanced box scores (V3) ---
    _adv_endpoints = [
        ("AdvBoxScoresTrad", boxscoretraditionalv3.BoxScoreTraditionalV3, _TRAD_RENAME),
        ("AdvBoxScoresAdv", boxscoreadvancedv3.BoxScoreAdvancedV3, _ADV_RENAME),
        ("AdvBoxScoresFourFactors", boxscorefourfactorsv3.BoxScoreFourFactorsV3, _FF_RENAME),
        ("AdvBoxScoresMisc", boxscoremiscv3.BoxScoreMiscV3, _MISC_RENAME),
        ("AdvBoxScoresScoring", boxscorescoringv3.BoxScoreScoringV3, _SCORING_RENAME),
    ]

    for key, EndpointClass, rename_map in _adv_endpoints:
        time.sleep(random.uniform(0.6, 1.2))
        for attempt in range(3):
            try:
                logger.info("[%s] attempt %d: %s", gid, attempt + 1, key)
                ep = EndpointClass(game_id=gid)
                dfs = ep.get_data_frames()
                team_df = dfs[-1].copy()
                team_df["matchup"] = team_df["teamId"].map(matchup_by_team)
                team_df["gameDate"] = pd.to_datetime(game_date_str) if game_date_str else pd.NaT
                team_df["wl"] = team_df["teamId"].map(wl_by_team)
                team_df = team_df.rename(columns=rename_map)
                keep = [c for c in rename_map.values() if c in team_df.columns]
                team_df = team_df[keep].copy()
                # Scale percentage columns from decimal (0.473) to whole number (47.3)
                skip = _ADV_SKIP_PCT if key == "AdvBoxScoresAdv" else (
                    _FF_SKIP_PCT if key == "AdvBoxScoresFourFactors" else set())
                for col in team_df.columns:
                    if col in _PCT_COLS and col not in skip:
                        team_df[col] = pd.to_numeric(team_df[col], errors="coerce") * 100
                        team_df[col] = team_df[col].round(1)
                # Convert MIN from "240:00" total team minutes to game minutes (48)
                if "MIN" in team_df.columns:
                    def _parse_min(val):
                        if pd.isna(val):
                            return val
                        s = str(val)
                        if ":" in s:
                            parts = s.split(":")
                            return str(int(int(parts[0]) / 5))
                        return s
                    team_df["MIN"] = team_df["MIN"].apply(_parse_min)
                team_df["game_id"] = gid
                result[key] = team_df
                logger.info("[%s] %s OK (%d rows)", gid, key, len(result[key]))
                break
            except Exception as exc:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning("[%s] %s attempt %d failed (%s: %s) — retrying in %.1fs",
                               gid, key, attempt + 1, type(exc).__name__, exc, wait)
                time.sleep(wait)

    # --- PlayByPlay (V3) ---
    time.sleep(random.uniform(0.6, 1.2))
    for attempt in range(3):
        try:
            from nba_api.stats.endpoints import playbyplayv3
            logger.info("[%s] attempt %d: PlayByPlayV3", gid, attempt + 1)
            pbp_ep = playbyplayv3.PlayByPlayV3(game_id=gid)
            pbp_df = pbp_ep.play_by_play.get_data_frame()
            if not pbp_df.empty:
                result["PlayByPlay"] = pbp_df
            logger.info("[%s] PlayByPlayV3 OK (%d rows)", gid, len(pbp_df))
            break
        except Exception as exc:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logger.warning("[%s] PlayByPlayV3 attempt %d failed (%s: %s) — retrying in %.1fs",
                           gid, attempt + 1, type(exc).__name__, exc, wait)
            time.sleep(wait)

    # --- Summary* parquets from raw JSON ---
    if summary_raw_json:
        _extract_summary_tables(gid, summary_raw_json, result)

    return result


def _extract_summary_tables(gid: str, raw: dict, result: dict) -> None:
    """Extract all Summary* parquet data from the BoxScoreSummaryV3 raw JSON."""
    game = raw.get("boxScoreSummary", {})
    if not game:
        return

    # --- SummaryGameMeta ---
    meta_fields = [
        "gameId", "gameCode", "gameStatus", "gameStatusText", "period",
        "gameClock", "gameTimeUTC", "gameEt", "awayTeamId", "homeTeamId",
        "duration", "attendance", "sellout", "seriesGameNumber", "gameLabel",
        "gameSubLabel", "seriesText", "ifNecessary", "isNeutral",
        "videoAvailableFlag", "ptAvailable", "ptXYZAvailable", "whStatus",
        "hustleStatus", "historicalStatus", "gameSubtype",
    ]
    meta_row = {k: game.get(k) for k in meta_fields}
    arena = game.get("arena", {})
    for k, v in arena.items():
        meta_row[f"arena.{k}"] = v
    result["SummaryGameMeta"] = pd.DataFrame([meta_row])

    # --- SummaryOfficials ---
    officials = game.get("officials", [])
    if officials:
        off_df = pd.DataFrame(officials)
        off_df["gameId"] = gid
        result["SummaryOfficials"] = off_df

    # --- SummaryTeamScores ---
    home_team = game.get("homeTeam", {})
    away_team = game.get("awayTeam", {})
    if home_team and away_team:
        ts_row = {"gameId": gid}
        for prefix, team in [("homeTeam", home_team), ("awayTeam", away_team)]:
            for k in ["teamId", "teamName", "teamCity", "teamTricode", "teamSlug",
                      "teamWins", "teamLosses", "score", "inBonus", "timeoutsRemaining", "seed"]:
                ts_row[f"{prefix}.{k}"] = team.get(k)
            periods = team.get("periods", [])
            for i in range(7):
                if i < len(periods):
                    ts_row[f"{prefix}.period_{i+1}_score"] = periods[i].get("score")
                    ts_row[f"{prefix}.period_{i+1}_type"] = periods[i].get("periodType")
                else:
                    ts_row[f"{prefix}.period_{i+1}_score"] = None
                    ts_row[f"{prefix}.period_{i+1}_type"] = None
        result["SummaryTeamScores"] = pd.DataFrame([ts_row])

    # --- SummaryPlayers ---
    player_rows = []
    for side, team in [("home", home_team), ("away", away_team)]:
        team_id = team.get("teamId")
        tricode = team.get("teamTricode")
        for p in team.get("players", []):
            player_rows.append({
                "gameId": gid, "side": side, "teamId": team_id, "teamTricode": tricode,
                "inactive": False, "personId": p.get("personId"),
                "name": p.get("name", ""), "nameI": p.get("nameI", ""),
                "firstName": p.get("firstName", ""), "familyName": p.get("familyName", ""),
                "jerseyNum": p.get("jerseyNum", ""),
            })
        for p in team.get("inactives", []):
            player_rows.append({
                "gameId": gid, "side": side, "teamId": team_id, "teamTricode": tricode,
                "inactive": True, "personId": p.get("personId"),
                "name": f"{p.get('firstName', '')} {p.get('familyName', '')}".strip(),
                "nameI": "", "firstName": p.get("firstName", ""),
                "familyName": p.get("familyName", ""), "jerseyNum": p.get("jerseyNum", ""),
            })
    if player_rows:
        result["SummaryPlayers"] = pd.DataFrame(player_rows)

    # --- SummaryPregameCharts / SummaryPostgameCharts ---
    for chart_key in ("pregameCharts", "postgameCharts"):
        charts = game.get(chart_key, {})
        if not charts:
            continue
        chart_row = {"gameId": gid}
        for side in ("homeTeam", "awayTeam"):
            team_data = charts.get(side, {})
            for k in ["teamId", "teamCity", "teamName", "teamTricode"]:
                chart_row[f"{chart_key}.{side}.{k}"] = team_data.get(k)
            stats = team_data.get("statistics", {})
            for sk, sv in stats.items():
                chart_row[f"{chart_key}.{side}.statistics.{sk}"] = sv
        parquet_key = "SummaryPregameCharts" if chart_key == "pregameCharts" else "SummaryPostgameCharts"
        result[parquet_key] = pd.DataFrame([chart_row])

    # --- SummaryBroadcasters ---
    broadcasters = game.get("broadcasters", {})
    if broadcasters:
        bc_rows = []
        for bc_type, bc_list in broadcasters.items():
            if not isinstance(bc_list, list):
                continue
            for bc in bc_list:
                bc_rows.append({
                    "gameId": gid,
                    "broadcast_type": bc_type,
                    "broadcasterId": bc.get("broadcasterId"),
                    "broadcastDisplay": bc.get("broadcastDisplay", ""),
                    "broadcasterDisplay": bc.get("broadcasterDisplay", ""),
                    "broadcasterVideoLink": bc.get("broadcasterVideoLink", ""),
                    "broadcasterDescription": bc.get("broadcasterDescription", ""),
                    "broadcasterTeamId": bc.get("broadcasterTeamId"),
                    "regionId": bc.get("regionId"),
                })
        if bc_rows:
            result["SummaryBroadcasters"] = pd.DataFrame(bc_rows)

    # --- SummaryLastFive ---
    last_five = game.get("lastFiveMeetings", {}).get("meetings", [])
    if last_five:
        lf_rows = []
        for i, meeting in enumerate(last_five):
            row = {"gameId": gid, "recencyOrder": i}
            for k, v in meeting.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        row[f"{k}.{sk}"] = sv
                else:
                    row[k] = v
            lf_rows.append(row)
        result["SummaryLastFive"] = pd.DataFrame(lf_rows)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert_parquet(path: Path, new_df: pd.DataFrame, dedup_keys: list[str]) -> int:
    """Appends new_df to path, deduplicating on dedup_keys. Returns rows added.

    Strategy:
    1. First, filter out new rows whose game already exists in the file (game-level guard).
    2. Then, deduplicate ONLY the new rows among themselves (not against existing data).
    3. Append. This guarantees the file never shrinks.
    """
    if new_df is None or new_df.empty:
        return 0
    new_df = new_df.copy()
    if path.exists():
        old_df = pd.read_parquet(path)
        old_count = len(old_df)

        # Determine game column
        game_col = "gameId" if "gameId" in new_df.columns else "game_id" if "game_id" in new_df.columns else None

        # Filter: only append rows for games NOT already in the file
        if game_col and game_col in old_df.columns:
            existing_games = set(old_df[game_col].dropna().astype(str))
            new_df = new_df[~new_df[game_col].astype(str).isin(existing_games)]
            if new_df.empty:
                return 0

        # Dedup new rows among themselves
        valid_keys = [k for k in dedup_keys if k in new_df.columns]
        if valid_keys:
            new_df = new_df.drop_duplicates(subset=valid_keys, keep="last")

        # Cast dtypes to match existing parquet schema
        for col in new_df.columns:
            if col in old_df.columns and old_df[col].dtype != new_df[col].dtype:
                try:
                    target = old_df[col].dtype
                    new_df[col] = new_df[col].astype(str) if target == object else new_df[col].astype(target)
                except Exception as e:
                    logger.warning("dtype cast failed for column '%s' (%s→%s): %s",
                                   col, new_df[col].dtype, old_df[col].dtype, e)

        combined = pd.concat([old_df, new_df], ignore_index=True)
        added = len(combined) - old_count
    else:
        combined = new_df.copy()
        added = len(combined)
    combined.to_parquet(path, index=False)
    return max(added, 0)


# ---------------------------------------------------------------------------
# Partial sync tracking
# ---------------------------------------------------------------------------

def _write_syncpartial(data_dir: Path, partial_games: dict[str, list[str]]) -> None:
    """Upsert partial_games into syncpartial.parquet (game_id, missing_tables)."""
    partial_path = data_dir / "syncpartial.parquet"
    new_rows = pd.DataFrame([
        {"game_id": gid, "missing_tables": ",".join(tables)}
        for gid, tables in partial_games.items()
    ])
    upsert_parquet(partial_path, new_rows, ["game_id"])
    logger.info("syncpartial.parquet: %d games recorded with missing tables", len(partial_games))


def _remove_from_syncpartial(data_dir: Path, resolved_ids: list[str]) -> None:
    """Remove resolved game IDs from syncpartial.parquet."""
    partial_path = data_dir / "syncpartial.parquet"
    if not partial_path.exists() or not resolved_ids:
        return
    df = pd.read_parquet(partial_path)
    df = df[~df["game_id"].astype(str).isin(set(resolved_ids))]
    df.to_parquet(partial_path, index=False)


def retry_partial(data_dir: Path, workers: int, cfg: LeagueConfig | None = None) -> int:
    """Re-fetch games listed in syncpartial.parquet that had missing tables.

    Returns the number of new rows written across all parquets.
    """
    if cfg is None:
        cfg = get_league_config("nba")

    partial_path = data_dir / "syncpartial.parquet"
    if not partial_path.exists():
        logger.info("syncpartial.parquet not found — nothing to retry")
        return 0

    partial_df = pd.read_parquet(partial_path)
    if partial_df.empty:
        logger.info("syncpartial.parquet is empty — nothing to retry")
        return 0

    ids_df = pd.read_parquet(data_dir / cfg.game_ids_file)
    game_ids = partial_df["game_id"].astype(str).str.zfill(10).tolist()
    logger.info("Retrying %d partially synced games: %s", len(game_ids), game_ids)

    total_added = 0
    resolved: list[str] = []
    still_partial: dict[str, list[str]] = {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_gid = {ex.submit(fetch_game, gid, cfg): gid for gid in game_ids}
        for future in as_completed(future_to_gid):
            gid = future_to_gid[future]
            try:
                game_data = future.result()
                suffix = _season_type_suffix(gid, ids_df)
                missing_tables = [k for k, v in game_data.items() if v is None]
                for key, df in game_data.items():
                    if df is None:
                        continue
                    full_key = f"{key}{suffix}" if key.startswith("AdvBoxScores") else key
                    path = data_dir / f"{full_key}.parquet"
                    dedup_keys = PARQUET_DEDUP_KEYS.get(f"{full_key}.parquet", ["game_id"])
                    added = upsert_parquet(path, df, dedup_keys)
                    if added > 0:
                        total_added += added
                        logger.info("  [retry] %s.parquet +%d rows for %s", full_key, added, gid)
                if missing_tables:
                    still_partial[gid] = missing_tables
                    logger.warning("  [retry] %s still missing: %s", gid, ", ".join(missing_tables))
                else:
                    resolved.append(gid)
                    logger.info("  [retry] %s fully resolved", gid)
            except Exception as err:
                logger.error("  [retry] Failed game %s: %s", gid, err)
                still_partial[gid] = ["FETCH_ERROR"]
            time.sleep(random.uniform(0.4, 0.9))

    _remove_from_syncpartial(data_dir, resolved)
    if still_partial:
        _write_syncpartial(data_dir, still_partial)
    logger.info("Retry complete: %d resolved, %d still partial, %d rows added",
                len(resolved), len(still_partial), total_added)
    return total_added


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(season: str, workers: int, dry_run: bool, cfg: LeagueConfig | None = None) -> None:
    if cfg is None:
        cfg = get_league_config("nba")
    DATA_DIR = cfg.data_path
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=== sync_games start | league=%s season=%s workers=%d dry_run=%s ===",
                cfg.league, season, workers, dry_run)

    # Step 1: refresh game IDs for this season
    logger.info("Refreshing %s for %s...", cfg.game_ids_file, season)
    refresh_game_ids(DATA_DIR, season, cfg)

    # Step 2: find what's missing
    missing = find_missing_games(DATA_DIR, cfg)
    if not missing:
        logger.info("Nothing to sync.")
        return

    ids_df = pd.read_parquet(DATA_DIR / cfg.game_ids_file)

    if dry_run:
        logger.info("DRY RUN: %d games would be synced. Sampling first game: %s", len(missing), missing[0])
        sample = fetch_game(missing[0], cfg=cfg)
        for k, df in sample.items():
            if df is not None:
                logger.info("  %s → %d rows", k, len(df))
        return

    # Step 3+4: fetch and upsert in batches of 20 games
    total_added = 0
    batch_size = 20
    failed_games: list[str] = []
    partial_games: dict[str, list[str]] = {}  # game_id -> list of tables that returned None

    for batch_start in range(0, len(missing), batch_size):
        batch = missing[batch_start: batch_start + batch_size]
        logger.info("Batch %d–%d of %d...", batch_start + 1, batch_start + len(batch), len(missing))

        results: dict[str, list[pd.DataFrame]] = {}

        with ThreadPoolExecutor(max_workers=workers) as ex:
            future_to_gid = {ex.submit(fetch_game, gid, cfg): gid for gid in batch}
            for future in as_completed(future_to_gid):
                gid = future_to_gid[future]
                try:
                    game_data = future.result()
                    suffix = _season_type_suffix(gid, ids_df)
                    missing_tables = [k for k, v in game_data.items() if v is None]
                    if missing_tables:
                        partial_games[gid] = missing_tables
                    for key, df in game_data.items():
                        if df is None:
                            continue
                        full_key = f"{key}{suffix}" if key.startswith("AdvBoxScores") else key
                        results.setdefault(full_key, []).append(df)
                except Exception as err:
                    logger.error("Failed game %s: %s", gid, err)
                    failed_games.append(gid)
                time.sleep(random.uniform(0.4, 0.9))

        # Write batch to parquets
        written_by_game: dict[str, set[str]] = {}  # game_id -> set of tables written
        for parquet_name, frames in results.items():
            if not frames:
                continue
            combined_new = pd.concat(frames, ignore_index=True)
            path = DATA_DIR / f"{parquet_name}.parquet"
            dedup_keys = PARQUET_DEDUP_KEYS.get(f"{parquet_name}.parquet", ["game_id"])
            added = upsert_parquet(path, combined_new, dedup_keys)
            if added > 0:
                total_added += added
                logger.info("  %s.parquet +%d rows", parquet_name, added)
            # Track which games had this table written (some use game_id, others gameId)
            id_col = "game_id" if "game_id" in combined_new.columns else "gameId" if "gameId" in combined_new.columns else None
            if id_col:
                for gid in combined_new[id_col].dropna().unique():
                    written_by_game.setdefault(str(gid).zfill(10), set()).add(parquet_name)

        # Stamp sync_complete only for games where ALL expected tables were written
        required = {"GameSummaries", "GameOfficials", "TeamQuarterScores"}
        if cfg.has_hustle:
            required.add("BoxScoresHustleTeam")
        adv_required = {"AdvBoxScoresTrad", "AdvBoxScoresAdv", "AdvBoxScoresFourFactors", "AdvBoxScoresMisc", "AdvBoxScoresScoring"}
        complete_ids = []
        for gid, written_tables in written_by_game.items():
            # Strip season suffix from written table names for comparison
            written_base = {t[:-len("Regular")] if t.endswith("Regular") else
                            t[:-len("Playoffs")] if t.endswith("Playoffs") else
                            t[:-len("Pre")] if t.endswith("Pre") else t
                            for t in written_tables}
            if required.issubset(written_tables) and adv_required.issubset(written_base):
                complete_ids.append(gid)

        if complete_ids:
            complete_path = DATA_DIR / "synccomplete.parquet"
            new_complete = pd.DataFrame({"game_id": complete_ids})
            upsert_parquet(complete_path, new_complete, ["game_id"])
            logger.info("  synccomplete.parquet: %d games fully synced", len(complete_ids))

        time.sleep(random.uniform(1.5, 3.0))

    logger.info("Sync complete. Total rows added across all parquets: %d", total_added)

    if failed_games:
        logger.warning("UNSYNCED — %d games failed entirely (no data written):", len(failed_games))
        for gid in failed_games:
            logger.warning("  FAILED: %s", gid)

    if partial_games:
        all_tables = {"GameSummaries", "GameOfficials", "TeamQuarterScores",
                      "AdvBoxScoresTrad", "AdvBoxScoresAdv", "AdvBoxScoresFourFactors", "AdvBoxScoresMisc", "AdvBoxScoresScoring"}
        if cfg.has_hustle:
            all_tables.add("BoxScoresHustleTeam")
        logger.warning("PARTIAL — %d games missing some tables:", len(partial_games))
        for gid, tables in partial_games.items():
            if set(tables) >= all_tables:
                logger.warning("  NO_DATA %s: API returned nothing — likely postponed/cancelled game", gid)
            else:
                logger.warning("  PARTIAL %s: missing %s", gid, ", ".join(tables))
        _write_syncpartial(DATA_DIR, partial_games)

    # Step 5: rebuild Massey + game_features if we wrote new game data
    if total_added > 0:
        repo_root = Path(__file__).resolve().parents[2]

        logger.info("Rebuilding MasseyRatings for %s...", season)
        subprocess.run(
            [sys.executable, "-m", "data_curation.scripts.build_massey_ratings",
             "--league", cfg.league, "--min-season", season],
            cwd=repo_root,
            check=True,
        )
        logger.info("MasseyRatings rebuild complete.")

        logger.info("Rebuilding game_features.parquet...")
        subprocess.run(
            [sys.executable, "-m", "feature_pipeline.build_features_only",
             "--league", cfg.league],
            cwd=repo_root,
            check=True,
        )
        logger.info("game_features.parquet rebuild complete.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Sync completed game data to parquets.")
    add_league_arg(p)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--season", default=None, help="e.g. 2025-26 for NBA, 2025 for WNBA (default: current)")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--retry-partial", action="store_true",
                   help="Re-fetch games in syncpartial.parquet that had missing tables")
    args = p.parse_args(argv)

    cfg = get_league_config(args.league)
    DATA_DIR = cfg.data_path
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    season = args.season or cfg.current_season()

    if args.retry_partial:
        added = retry_partial(DATA_DIR, args.workers, cfg=cfg)
        if added > 0:
            repo_root = Path(__file__).resolve().parents[2]
            logger.info("Rebuilding MasseyRatings after partial retry...")
            subprocess.run(
                [sys.executable, "-m", "data_curation.scripts.build_massey_ratings",
                 "--league", cfg.league, "--min-season", season],
                cwd=repo_root, check=True,
            )
            logger.info("Rebuilding game_features.parquet after partial retry...")
            subprocess.run(
                [sys.executable, "-m", "feature_pipeline.build_features_only",
                 "--league", cfg.league],
                cwd=repo_root, check=True,
            )
        return 0

    run(season=season, workers=args.workers, dry_run=args.dry_run, cfg=cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
