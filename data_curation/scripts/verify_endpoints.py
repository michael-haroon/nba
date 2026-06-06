"""
verify_endpoints.py
-------------------
Proves each NBA API endpoint returns data matching existing local parquets.

For a known game_id already in local data, hits the API and compares
column-by-column to verify correctness of the sync pipeline.

Usage:
    python data_curation/scripts/verify_endpoints.py --game-id 0042500315
    python data_curation/scripts/verify_endpoints.py  # uses a default from synccomplete
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "verify_endpoints.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


_PCT_COLS = {"FG%", "3P%", "FT%", "EFG%", "TS%", "FTA RATE",
             "TOV%", "OREB%", "DREB%", "REB%", "AST%",
             "OPP EFG%", "OPP FTA RATE", "OPP TOV%", "OPP OREB%", "PIE",
             "%FGA 2PT", "%FGA 3PT", "%PTS 2PT", "%PTS 2PT MR", "%PTS 3PT",
             "%PTS FBPS", "%PTS FT", "%PTS OFF TO", "%PTS PITP",
             "2FGM %AST", "2FGM %UAST", "3FGM %AST", "3FGM %UAST",
             "FGM %AST", "FGM %UAST"}


def _compare_values(local_val, api_val, col: str, tol: float = 0.01) -> tuple[bool, str]:
    """Compare a single value. Returns (passed, message).

    For percentage columns, local stores whole numbers (47.3) while API returns
    decimals (0.473). We scale the API value by 100 before comparing.
    """
    if pd.isna(local_val) and pd.isna(api_val):
        return True, "both NaN"
    if pd.isna(local_val) or pd.isna(api_val):
        return False, f"local={local_val} vs api={api_val}"
    try:
        lf = float(local_val)
        af = float(api_val)
        if col in _PCT_COLS:
            af = af * 100
        if abs(lf - af) <= tol:
            return True, f"{lf} ≈ {af}"
        return False, f"{lf} != {af} (diff={abs(lf-af):.4f})"
    except (ValueError, TypeError):
        if str(local_val).strip() == str(api_val).strip():
            return True, f"'{local_val}'"
        return False, f"'{local_val}' != '{api_val}'"


def verify_boxscore_traditional(game_id: str) -> dict:
    """Verify BoxScoreTraditionalV3 against AdvBoxScoresTrad*.parquet."""
    from nba_api.stats.endpoints import boxscoretraditionalv3

    logger.info("[%s] Verifying BoxScoreTraditionalV3...", game_id)
    ep = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
    dfs = ep.get_data_frames()
    team_df = dfs[-1]

    rename = {
        "teamTricode": "TEAM", "fieldGoalsMade": "FGM", "fieldGoalsAttempted": "FGA",
        "fieldGoalsPercentage": "FG%", "threePointersMade": "3PM", "threePointersAttempted": "3PA",
        "threePointersPercentage": "3P%", "freeThrowsMade": "FTM", "freeThrowsAttempted": "FTA",
        "freeThrowsPercentage": "FT%", "reboundsOffensive": "OREB", "reboundsDefensive": "DREB",
        "reboundsTotal": "REB", "assists": "AST", "turnovers": "TOV", "steals": "STL",
        "blocks": "BLK", "foulsPersonal": "PF", "plusMinusPoints": "+/-", "points": "PTS",
    }
    team_df = team_df.rename(columns=rename)

    for suffix in ("Regular", "Playoffs", "Pre"):
        path = DATA_DIR / f"AdvBoxScoresTrad{suffix}.parquet"
        if not path.exists():
            continue
        local = pd.read_parquet(path)
        if "game_id" not in local.columns:
            continue
        match = local[local["game_id"].astype(str).str.zfill(10) == game_id]
        if not match.empty:
            break
    else:
        return {"status": "SKIP", "reason": "game_id not found in local AdvBoxScoresTrad"}

    results = {"status": "PASS", "checks": []}
    check_cols = ["PTS", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "REB", "AST", "TOV", "STL", "BLK"]

    for _, api_row in team_df.iterrows():
        team = api_row.get("TEAM", "")
        local_row = match[match["TEAM"] == team]
        if local_row.empty:
            continue
        local_row = local_row.iloc[0]
        for col in check_cols:
            if col in api_row.index and col in local_row.index:
                passed, msg = _compare_values(local_row[col], api_row[col], col)
                results["checks"].append({"team": team, "col": col, "passed": passed, "detail": msg})
                if not passed:
                    results["status"] = "FAIL"

    return results


def verify_boxscore_advanced(game_id: str) -> dict:
    """Verify BoxScoreAdvancedV3 against AdvBoxScoresAdv*.parquet."""
    from nba_api.stats.endpoints import boxscoreadvancedv3

    logger.info("[%s] Verifying BoxScoreAdvancedV3...", game_id)
    ep = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id)
    dfs = ep.get_data_frames()
    team_df = dfs[-1]

    rename = {
        "teamTricode": "TEAM", "offensiveRating": "OFFRTG", "defensiveRating": "DEFRTG",
        "netRating": "NETRTG", "assistPercentage": "AST%", "assistToTurnover": "AST/TO",
        "assistRatio": "AST RATIO", "offensiveReboundPercentage": "OREB%",
        "defensiveReboundPercentage": "DREB%", "reboundPercentage": "REB%",
        "turnoverRatio": "TOV%", "effectiveFieldGoalPercentage": "EFG%",
        "trueShootingPercentage": "TS%", "pace": "PACE", "PIE": "PIE",
    }
    team_df = team_df.rename(columns=rename)

    for suffix in ("Regular", "Playoffs", "Pre"):
        path = DATA_DIR / f"AdvBoxScoresAdv{suffix}.parquet"
        if not path.exists():
            continue
        local = pd.read_parquet(path)
        if "game_id" not in local.columns:
            continue
        match = local[local["game_id"].astype(str).str.zfill(10) == game_id]
        if not match.empty:
            break
    else:
        return {"status": "SKIP", "reason": "game_id not found in local AdvBoxScoresAdv"}

    results = {"status": "PASS", "checks": []}
    check_cols = ["OFFRTG", "DEFRTG", "NETRTG", "PACE", "TS%", "EFG%", "PIE"]

    for _, api_row in team_df.iterrows():
        team = api_row.get("TEAM", "")
        local_row = match[match["TEAM"] == team]
        if local_row.empty:
            continue
        local_row = local_row.iloc[0]
        for col in check_cols:
            if col in api_row.index and col in local_row.index:
                passed, msg = _compare_values(local_row[col], api_row[col], col)
                results["checks"].append({"team": team, "col": col, "passed": passed, "detail": msg})
                if not passed:
                    results["status"] = "FAIL"

    return results


def verify_playbyplay(game_id: str) -> dict:
    """Verify PlayByPlayV3 against PlayByPlay.parquet."""
    from nba_api.stats.endpoints import playbyplayv3

    logger.info("[%s] Verifying PlayByPlayV3...", game_id)
    ep = playbyplayv3.PlayByPlayV3(game_id=game_id)
    api_df = ep.play_by_play.get_data_frame()

    path = DATA_DIR / "PlayByPlay.parquet"
    if not path.exists():
        return {"status": "SKIP", "reason": "PlayByPlay.parquet not found"}

    local = pd.read_parquet(path)
    local_match = local[local["gameId"].astype(str).str.zfill(10) == game_id]

    if local_match.empty:
        return {"status": "SKIP", "reason": f"game_id {game_id} not found in PlayByPlay.parquet"}

    results = {"status": "PASS", "checks": []}

    results["checks"].append({
        "col": "row_count",
        "passed": len(api_df) == len(local_match),
        "detail": f"api={len(api_df)} vs local={len(local_match)}",
    })
    if len(api_df) != len(local_match):
        results["status"] = "FAIL"

    check_cols = ["actionNumber", "period", "actionType", "description"]
    sample_idx = [0, len(api_df) // 2, len(api_df) - 1] if len(api_df) > 2 else [0]

    for idx in sample_idx:
        api_row = api_df.iloc[idx]
        local_rows = local_match[local_match["actionNumber"] == api_row.get("actionNumber")]
        if local_rows.empty:
            results["checks"].append({"col": f"action_{idx}", "passed": False, "detail": "not found locally"})
            results["status"] = "FAIL"
            continue
        local_row = local_rows.iloc[0]
        for col in check_cols:
            if col in api_row.index and col in local_row.index:
                passed, msg = _compare_values(local_row[col], api_row[col], col)
                results["checks"].append({"col": f"{col}@{idx}", "passed": passed, "detail": msg})
                if not passed:
                    results["status"] = "FAIL"

    return results


def verify_hustle(game_id: str) -> dict:
    """Verify BoxScoreHustleV2 against HustleGames.parquet."""
    from nba_api.stats.endpoints import boxscorehustlev2

    logger.info("[%s] Verifying BoxScoreHustleV2...", game_id)
    ep = boxscorehustlev2.BoxScoreHustleV2(game_id=game_id)
    team_stats = ep.team_stats.get_data_frame()
    player_stats = ep.player_stats.get_data_frame()

    results = {"status": "PASS", "checks": []}

    # Check HustleGames
    hg_path = DATA_DIR / "HustleGames.parquet"
    if hg_path.exists():
        hg = pd.read_parquet(hg_path)
        local_match = hg[hg["gameId"].astype(str).str.zfill(10) == game_id]
        results["checks"].append({
            "col": "HustleGames_found",
            "passed": not local_match.empty,
            "detail": f"local has {len(local_match)} rows for this game",
        })
        if local_match.empty:
            results["status"] = "WARN"

    # Check HustlePlayerStats
    hp_path = DATA_DIR / "HustlePlayerStats.parquet"
    if hp_path.exists():
        hp = pd.read_parquet(hp_path)
        local_match = hp[hp["gameId"].astype(str).str.zfill(10) == game_id]
        results["checks"].append({
            "col": "HustlePlayerStats_count",
            "passed": len(local_match) == len(player_stats),
            "detail": f"api={len(player_stats)} vs local={len(local_match)}",
        })
        if len(local_match) != len(player_stats):
            results["status"] = "WARN"

    results["checks"].append({
        "col": "api_team_rows",
        "passed": len(team_stats) == 2,
        "detail": f"team_stats has {len(team_stats)} rows (expected 2)",
    })

    return results


def verify_summary_raw_json(game_id: str) -> dict:
    """Verify BoxScoreSummaryV3 raw JSON structure for Summary* parquets."""
    from nba_api.stats.endpoints import boxscoresummaryv3

    logger.info("[%s] Verifying BoxScoreSummaryV3 raw JSON...", game_id)
    ep = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id)
    raw = json.loads(ep.nba_response.get_json())

    results = {"status": "PASS", "checks": []}

    game_data = raw.get("boxScoreSummary") or raw.get("boxScoreGame") or raw.get("game") or {}
    if not game_data:
        results["status"] = "FAIL"
        results["checks"].append({"col": "raw_json_structure", "passed": False, "detail": f"top-level keys: {list(raw.keys())}"})
        results["raw_keys"] = list(raw.keys())
        return results

    # Check for expected nested fields used by Summary* parquets
    expected_fields = {
        "SummaryGameMeta": ["gameId", "gameStatus", "arenaName"],
        "SummaryBroadcasters": ["broadcasters"],
        "SummaryTeamScores": ["homeTeam", "awayTeam"],
    }

    for parquet_name, fields in expected_fields.items():
        for field in fields:
            found = field in game_data or any(field in str(k) for k in game_data.keys())
            results["checks"].append({
                "col": f"{parquet_name}.{field}",
                "passed": found,
                "detail": f"field '{field}' {'found' if found else 'MISSING'} in game data",
            })
            if not found:
                results["status"] = "WARN"

    results["raw_top_keys"] = list(raw.keys())
    results["game_data_keys"] = list(game_data.keys())[:30]

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify NBA API endpoints against local parquets")
    parser.add_argument("--game-id", default=None, help="Game ID to verify (default: latest from synccomplete)")
    args = parser.parse_args()

    game_id = args.game_id
    if not game_id:
        sc_path = DATA_DIR / "synccomplete.parquet"
        if sc_path.exists():
            sc = pd.read_parquet(sc_path)
            game_id = str(sc["game_id"].iloc[-1]).zfill(10)
        else:
            logger.error("No --game-id provided and synccomplete.parquet not found")
            return 1

    logger.info("=== verify_endpoints start | game_id=%s ===", game_id)

    verifications = [
        ("BoxScoreTraditionalV3 → AdvBoxScoresTrad", verify_boxscore_traditional),
        ("BoxScoreAdvancedV3 → AdvBoxScoresAdv", verify_boxscore_advanced),
        ("PlayByPlayV3 → PlayByPlay", verify_playbyplay),
        ("BoxScoreHustleV2 → HustleGames/PlayerStats", verify_hustle),
        ("BoxScoreSummaryV3 raw JSON → Summary*", verify_summary_raw_json),
    ]

    all_passed = True
    for name, func in verifications:
        time.sleep(1.0)
        try:
            result = func(game_id)
            status = result["status"]
            checks = result.get("checks", [])
            failed = [c for c in checks if not c["passed"]]

            if status == "FAIL":
                all_passed = False
                logger.error("  FAIL  %s", name)
                for c in failed:
                    logger.error("    ✗ %s: %s", c.get("col", "?"), c.get("detail", ""))
            elif status == "WARN":
                logger.warning("  WARN  %s", name)
                for c in failed:
                    logger.warning("    ? %s: %s", c.get("col", "?"), c.get("detail", ""))
            elif status == "SKIP":
                logger.info("  SKIP  %s: %s", name, result.get("reason", ""))
            else:
                passed_count = len([c for c in checks if c["passed"]])
                logger.info("  PASS  %s (%d checks)", name, passed_count)

            # Print extra diagnostic info if present
            for key in ("raw_top_keys", "game_data_keys"):
                if key in result:
                    logger.info("    %s: %s", key, result[key])

        except Exception as e:
            all_passed = False
            logger.error("  ERROR %s: %s", name, e)

    logger.info("=== verify_endpoints complete | overall=%s ===", "PASS" if all_passed else "FAIL")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
