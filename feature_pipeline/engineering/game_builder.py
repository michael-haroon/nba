"""
Build game-level dataset: one row per game with both teams' stats and all targets.

Determines home/away from MATCH UP column, pivots box scores into home_/away_ prefixes,
attaches quarter scores, and computes all prediction targets including series outcomes.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def parse_home_away(match_up: pd.Series) -> pd.DataFrame:
    """
    Parse MATCH UP column (e.g., "ATL VS. CLE" or "ATL @ CLE")
    to determine if this row's team is home or away.

    Returns DataFrame with columns: team_abbr, opponent_abbr, is_home.
    """
    parts = match_up.str.split(r"\s+(?:VS\.|vs\.|@)\s+", expand=True, regex=True)
    is_home = match_up.str.upper().str.contains("VS.", regex=False)
    return pd.DataFrame({
        "team_abbr": parts[0].str.strip(),
        "opponent_abbr": parts[1].str.strip(),
        "is_home": is_home,
    })


def _normalize_col_name(col: str) -> str:
    """Convert raw column name to snake_case feature name."""
    return (
        col.lower()
        .replace("%", "pct")
        .replace("+/-", "plus_minus")
        .replace("/", "_")
        .replace(" ", "_")
    )


def build_game_rows(box_scores: pd.DataFrame, game_ids: pd.DataFrame,
                    team_map: pd.DataFrame) -> pd.DataFrame:
    """
    Construct one row per game from box scores.

    Each row has home_* and away_* prefixed stats for both teams.
    Merges home row with corresponding away row on (game_date, team matchup).
    """
    bs = box_scores.copy()

    parsed = parse_home_away(bs["MATCH UP"])
    bs["team_abbr"] = parsed["team_abbr"]
    bs["opponent_abbr"] = parsed["opponent_abbr"]
    bs["is_home"] = parsed["is_home"]
    bs["game_date"] = bs["GAME DATE"]

    abbr_to_id = (
        team_map.drop_duplicates("TEAM_ABBREVIATION")
        .set_index("TEAM_ABBREVIATION")["TEAM_ID"]
        .to_dict()
    )
    bs["team_id"] = bs["team_abbr"].map(abbr_to_id)

    # Identify stat columns to prefix
    meta_exclude = {
        "TEAM", "MATCH UP", "GAME DATE", "W/L", "season_type",
        "team_abbr", "opponent_abbr", "is_home", "team_id", "game_date",
    }
    stat_cols = [c for c in bs.columns if c not in meta_exclude]

    # Split home and away
    home = bs[bs["is_home"]].copy().reset_index(drop=True)
    away = bs[~bs["is_home"]].copy().reset_index(drop=True)

    # Build join key: date + home_team_abbr (from away's perspective, opponent_abbr is home)
    home["_jk"] = home["game_date"].dt.strftime("%Y-%m-%d") + "|" + home["team_abbr"]
    away["_jk"] = away["game_date"].dt.strftime("%Y-%m-%d") + "|" + away["opponent_abbr"]

    # Rename stat columns with prefix
    home_renames = {c: f"home_{_normalize_col_name(c)}" for c in stat_cols}
    home_renames["team_abbr"] = "home_team_abbr"
    home_renames["team_id"] = "home_team_id"
    home_renames["W/L"] = "home_wl"
    home_renames["TEAM"] = "home_team_name"
    home_renames["game_date"] = "game_date"
    home_renames["season_type"] = "season_type"

    away_renames = {c: f"away_{_normalize_col_name(c)}" for c in stat_cols}
    away_renames["team_abbr"] = "away_team_abbr"
    away_renames["team_id"] = "away_team_id"
    away_renames["W/L"] = "away_wl"
    away_renames["TEAM"] = "away_team_name"

    home_cols_to_keep = list(home_renames.keys()) + ["_jk"]
    away_cols_to_keep = list(away_renames.keys()) + ["_jk"]

    home_sub = home[home_cols_to_keep].rename(columns=home_renames)
    away_sub = away[away_cols_to_keep].rename(columns=away_renames)

    # Merge: each home row joins with its corresponding away row
    games = home_sub.merge(
        away_sub.drop(columns=["_jk"], errors="ignore"),
        left_on="_jk",
        right_on=away_sub["_jk"],
        how="inner",
    )
    games = games.drop(columns=["_jk", "key_0"], errors="ignore")

    unmapped = bs["team_id"].isna().sum()
    if unmapped > 0:
        logger.warning("[build_game_rows] %d team rows unmapped (no team_id) — abbr_to_id mismatch", unmapped)
    logger.info("[build_game_rows] home rows=%d  away rows=%d  merged games=%d  cols=%d",
                bs["is_home"].sum(), (~bs["is_home"]).sum(), len(games), games.shape[1])

    # Attach season from game_ids
    gi = game_ids.drop_duplicates("GAME_DATE")
    games = games.merge(
        gi[["GAME_DATE", "SEASON_FILTER"]],
        left_on="game_date",
        right_on="GAME_DATE",
        how="left",
    ).drop(columns=["GAME_DATE"], errors="ignore")
    games = games.rename(columns={"SEASON_FILTER": "season"})

    # Canonical game_id: one per row, sourced from home side (same as away)
    if "home_game_id" in games.columns:
        games["game_id"] = games["home_game_id"]

    # Final numeric coercion on all stat columns
    exclude = {"game_id", "game_date", "season", "season_type", "home_team_abbr", "away_team_abbr",
               "home_team_name", "away_team_name", "home_team_id", "away_team_id",
               "home_wl", "away_wl", "home_min_trad", "away_min_trad"}
    for col in games.columns:
        if col in exclude:
            continue
        if games[col].dtype == object or str(games[col].dtype).startswith("string"):
            games[col] = pd.to_numeric(games[col], errors="coerce")

    return games


def attach_quarter_scores(games: pd.DataFrame, quarter_scores: pd.DataFrame,
                          team_map: pd.DataFrame) -> pd.DataFrame:
    """Pivot quarter scores and attach to game rows."""
    qs = quarter_scores.copy()

    # Pivot: one row per (game_id, team_id) with columns q1, q2, q3, q4, ot1...
    qs_pivot = qs.pivot_table(
        index=["game_id", "team_id"],
        columns="period_label",
        values="period_score",
        aggfunc="first",
    ).reset_index()

    # Standardize period column names
    period_cols = [c for c in qs_pivot.columns if c not in ("game_id", "team_id")]

    if "game_id" not in games.columns:
        return games

    # Normalize game_id types to zero-padded 10-char string for both sides
    games["game_id"] = pd.to_numeric(games["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    qs_pivot["game_id"] = pd.to_numeric(qs_pivot["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)

    # Normalize team_id types
    qs_pivot["team_id"] = pd.to_numeric(qs_pivot["team_id"], errors="coerce").astype("Int64")
    games["home_team_id"] = pd.to_numeric(games["home_team_id"], errors="coerce").astype("Int64")
    games["away_team_id"] = pd.to_numeric(games["away_team_id"], errors="coerce").astype("Int64")

    # Merge home quarters
    home_qs = qs_pivot.rename(columns={c: f"home_{c.lower()}" for c in period_cols})
    home_qs = home_qs.rename(columns={"team_id": "home_team_id"})
    games = games.merge(
        home_qs,
        on=["game_id", "home_team_id"],
        how="left",
    )

    # Merge away quarters
    away_qs = qs_pivot.rename(columns={c: f"away_{c.lower()}" for c in period_cols})
    away_qs = away_qs.rename(columns={"team_id": "away_team_id"})
    games = games.merge(
        away_qs,
        on=["game_id", "away_team_id"],
        how="left",
    )

    qs_cols = [c for c in games.columns if c.startswith(("home_q", "away_q"))]
    null_rate = games[qs_cols].isna().mean().mean() if qs_cols else 1.0
    logger.info("[attach_quarter_scores] quarter cols=%d  avg null rate=%.1f%%",
                len(qs_cols), 100 * null_rate)

    return games


def build_targets(games: pd.DataFrame) -> pd.DataFrame:
    """Compute all prediction targets from game outcomes."""
    df = games.copy()

    # Ensure numeric scores
    for col in ["home_pts", "away_pts"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Winner
    df["target_winner"] = (df["home_wl"] == "W").astype(int)

    # Scores
    if "home_pts" in df.columns and "away_pts" in df.columns:
        df["target_home_score"] = df["home_pts"]
        df["target_away_score"] = df["away_pts"]
        df["target_spread"] = df["home_pts"] - df["away_pts"]
        df["target_total"] = df["home_pts"] + df["away_pts"]

    # Half targets from quarter scores
    q_cols_home = [c for c in df.columns if c.startswith("home_q")]
    q_cols_away = [c for c in df.columns if c.startswith("away_q")]

    if len(q_cols_home) >= 4:
        h1_home = df.get("home_q1", 0) + df.get("home_q2", 0)
        h1_away = df.get("away_q1", 0) + df.get("away_q2", 0)
        h2_home = df.get("home_q3", 0) + df.get("home_q4", 0)
        h2_away = df.get("away_q3", 0) + df.get("away_q4", 0)

        df["target_h1_spread"] = h1_home - h1_away
        df["target_h2_spread"] = h2_home - h2_away
        df["target_h1_total"] = h1_home + h1_away
        df["target_h2_total"] = h2_home + h2_away
        df["target_home_wins_h1"] = (h1_home > h1_away).astype(int)
        df["target_home_wins_h2"] = (h2_home > h2_away).astype(int)

    # Overtime
    ot_cols = [c for c in df.columns if "ot" in c.lower() and c.startswith("home_")]
    if ot_cols:
        df["target_overtime"] = df[ot_cols].notna().any(axis=1).astype(int)
    else:
        df["target_overtime"] = 0

    winner_bal = df["target_winner"].mean() if "target_winner" in df.columns else float("nan")
    spread_range = (df["target_spread"].min(), df["target_spread"].max()) if "target_spread" in df.columns else (float("nan"), float("nan"))
    total_range = (df["target_total"].min(), df["target_total"].max()) if "target_total" in df.columns else (float("nan"), float("nan"))
    ot_rate = df["target_overtime"].mean() if "target_overtime" in df.columns else float("nan")
    logger.info("[build_targets] winner_balance=%.3f  spread=[%.1f, %.1f]  total=[%.1f, %.1f]  ot_rate=%.1f%%",
                winner_bal, spread_range[0], spread_range[1],
                total_range[0], total_range[1], 100 * ot_rate)

    return df


def build_series_targets(games: pd.DataFrame) -> pd.DataFrame:
    """
    Compute playoff series targets. Each playoff game gets the eventual series outcome
    as its target, plus series-position features.

    Only applies to playoff games.
    """
    df = games.copy()

    playoff_mask = df["season_type"] == "Playoffs"
    if not playoff_mask.any():
        logger.info("[build_series_targets] no playoff games found — skipping")
        df["target_series_winner"] = np.nan
        df["target_series_total_games"] = np.nan
        df["target_series_spread"] = np.nan
        df["target_series_exact"] = np.nan
        df["series_game_number"] = np.nan
        df["series_lead"] = np.nan
        return df

    playoffs = df[playoff_mask].copy().sort_values("game_date")

    # Identify series: normalize matchup so same pair regardless of home/away
    playoffs["_team_pair"] = playoffs.apply(
        lambda r: tuple(sorted([r["home_team_abbr"], r["away_team_abbr"]])), axis=1
    )
    playoffs["_series_key"] = playoffs["season"].astype(str) + "|" + playoffs["_team_pair"].astype(str)

    series_targets = {}

    for series_key, group in playoffs.groupby("_series_key"):
        group = group.sort_values("game_date").reset_index(drop=False)
        team_a, team_b = group["_team_pair"].iloc[0]

        wins_a = 0
        wins_b = 0
        game_results = []

        for _, row in group.iterrows():
            if row["home_team_abbr"] == team_a:
                a_won = row.get("home_wl") == "W"
            else:
                a_won = row.get("away_wl") == "W"

            if a_won:
                wins_a += 1
            else:
                wins_b += 1
            game_results.append((wins_a, wins_b))

        total_games = len(group)
        series_winner_is_a = wins_a > wins_b
        series_spread = abs(wins_a - wins_b)
        winner_wins = max(wins_a, wins_b)
        loser_wins = min(wins_a, wins_b)
        exact_result = f"{winner_wins}-{loser_wins}"

        for i, (idx, row) in enumerate(group.iterrows()):
            orig_idx = group.loc[i, "index"] if "index" in group.columns else idx
            wa_before = game_results[i - 1][0] if i > 0 else 0
            wb_before = game_results[i - 1][1] if i > 0 else 0

            if row["home_team_abbr"] == team_a:
                home_is_a = True
            else:
                home_is_a = False

            # Series winner from home team perspective
            if home_is_a:
                home_wins_series = int(series_winner_is_a)
                lead = wa_before - wb_before
            else:
                home_wins_series = int(not series_winner_is_a)
                lead = wb_before - wa_before

            series_targets[orig_idx] = {
                "target_series_winner": home_wins_series,
                "target_series_total_games": total_games,
                "target_series_spread": series_spread,
                "target_series_exact": exact_result,
                "series_game_number": i + 1,
                "series_lead": lead,
            }

    logger.info("[build_series_targets] playoff games=%d  unique series=%d",
                playoff_mask.sum(), playoffs["_series_key"].nunique())
    series_df = pd.DataFrame.from_dict(series_targets, orient="index")

    for col in series_df.columns:
        if col == "target_series_exact":
            df[col] = pd.array([pd.NA] * len(df), dtype="string")
        else:
            df[col] = np.nan
        df.loc[series_df.index, col] = series_df[col].values

    return df


def build_full_game_dataset(data: dict) -> pd.DataFrame:
    """
    End-to-end: load data dict → game rows → targets.

    Args:
        data: dict from data_loader.load_all()
    """
    games = build_game_rows(
        data["box_scores"],
        data["game_ids"],
        data["team_map"],
    )

    if "quarter_scores" in data:
        games = attach_quarter_scores(games, data["quarter_scores"], data["team_map"])

    games = build_targets(games)
    games = build_series_targets(games)

    return games
