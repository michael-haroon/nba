"""
Feature engineering for NBA game prediction.

Translates de Prado's AFML concepts into NBA-domain features:
  Finance → NBA
  ──────────────────────────────────────────────────
  Price series           → Win-rate trajectory across games
  Entropy (LZ)           → Entropy of recent win/loss sequence
  CUSUM filter           → Detect momentum shift in win rate
  Fracdiff               → Season-over-season rating changes
  Sample weight          → Recency weighting
  MDI / MDA / SFI / CFI  → Feature importance on game-level frame
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from feature_pipeline.compute import get_n_random_combos


# ─────────────────────────────────────────────────────────────────────────────
#  1.  Entropy of win/loss sequence  (de Prado Ch.18)
# ─────────────────────────────────────────────────────────────────────────────

def lz_entropy(binary_string: str) -> float:
    """
    Lempel-Ziv complexity of a binary string.
    Low entropy = streak. High entropy = alternating.
    """
    s = binary_string.replace(" ", "")
    if len(s) < 2:
        return np.nan
    i, k, c = 0, 1, 1
    while k + c <= len(s):
        if s[k: k + c] in s[i: k]:
            c += 1
        else:
            i = k
            k += c
            c = 1
    n = len(s)
    return (c * np.log2(n)) / n if n > 1 else np.nan


def win_sequence_entropy(wins: float, losses: float) -> float:
    """Shannon entropy proxy from win/loss counts."""
    try:
        wins = int(wins) if wins is not None and not (isinstance(wins, float) and np.isnan(wins)) else 0
        losses = int(losses) if losses is not None and not (isinstance(losses, float) and np.isnan(losses)) else 0
    except (ValueError, TypeError):
        return np.nan
    total = wins + losses
    if total < 2:
        return np.nan
    p = wins / total
    if p == 0 or p == 1:
        return 0.0
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


# ─────────────────────────────────────────────────────────────────────────────
#  2.  CUSUM – detect momentum shift in win rate  (de Prado Ch.2 & Ch.17)
# ─────────────────────────────────────────────────────────────────────────────

def cusum_peak(series: pd.Series, h: float = 0.05) -> float:
    """
    Symmetric CUSUM filter on a time series.
    Returns the peak absolute cumulative deviation above threshold h.
    """
    s_pos = 0.0
    s_neg = 0.0
    peak = 0.0
    y_prev = series.iloc[0] if len(series) > 0 else 0.5

    for y_t in series:
        delta = y_t - y_prev
        s_pos = max(0.0, s_pos + delta)
        s_neg = min(0.0, s_neg + delta)
        peak = max(peak, abs(s_pos), abs(s_neg))
        if abs(s_pos) >= h:
            s_pos = 0.0
        if abs(s_neg) >= h:
            s_neg = 0.0
        y_prev = y_t

    return peak


# ─────────────────────────────────────────────────────────────────────────────
#  3.  Time-decay sample weights  (de Prado Ch.4)
# ─────────────────────────────────────────────────────────────────────────────

def time_decay_weights(dates: pd.Series, c: float = 0.5) -> pd.Series:
    """
    Assign higher weight to more recent games.
    c=1 → no decay. c=0 → oldest gets zero weight.
    Returns weights summing to len(dates).
    """
    min_date = dates.min()
    max_date = dates.max()
    if min_date == max_date:
        return pd.Series(1.0, index=dates.index)

    raw = (dates - min_date) / (max_date - min_date)
    weights = c + (1 - c) * raw
    total = weights.sum()
    if total > 0:
        weights = weights * len(dates) / total
    return weights


# ─────────────────────────────────────────────────────────────────────────────
#  4.  Missing data handling  (de Prado: indicator + median fill)
# ─────────────────────────────────────────────────────────────────────────────

def handle_missing(df: pd.DataFrame, strategy: str = "median") -> pd.DataFrame:
    """
    Handle missing values in feature columns.
    strategy: "median" fills with column median, "zero" fills with 0.
    """
    df = df.copy()
    numeric_cols = df.select_dtypes(include=np.number).columns
    if strategy == "median":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    elif strategy == "zero":
        df[numeric_cols] = df[numeric_cols].fillna(0)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  5.  Feature redundancy audit  (correlation + ONC clustering)
# ─────────────────────────────────────────────────────────────────────────────

def audit_feature_redundancy(df: pd.DataFrame,
                             feature_cols: list = None,
                             threshold: float = 0.85,
                             verbose: bool = True) -> dict:
    """
    Compute correlation matrix, flag highly-correlated pairs, group via ONC.
    """
    from feature_pipeline.analysis.feature_importance import onc_cluster

    if feature_cols is None:
        exclude = {"game_id", "game_date", "season", "season_type",
                   "home_team_id", "away_team_id", "sample_weight"}
        exclude.update(c for c in df.columns if c.startswith("target_"))
        feature_cols = [
            c for c in df.select_dtypes(include=np.number).columns
            if c not in exclude
        ]

    sub = df[feature_cols].dropna(thresh=int(0.5 * len(df)))
    sub = sub.loc[:, sub.notna().sum() > 30]
    feature_cols = list(sub.columns)

    corr = sub.corr()

    high_corr_pairs = []
    for i, col_a in enumerate(feature_cols):
        for col_b in feature_cols[i + 1:]:
            r = corr.loc[col_a, col_b]
            if abs(r) >= threshold:
                high_corr_pairs.append((col_a, col_b, round(r, 3)))

    high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)

    if verbose:
        print(f"  Features analysed: {len(feature_cols)}")
        print(f"  Highly correlated pairs (|r| >= {threshold}): {len(high_corr_pairs)}")
        for a, b, r in high_corr_pairs[:10]:
            print(f"    {a:30s} <-> {b:30s}  r={r:+.3f}")

    clusters = onc_cluster(corr, max_clusters=max(2, len(feature_cols) // 3))

    keep_list = []
    for cid, members in clusters.items():
        keep_list.append(members[0])

    return {
        "corr": corr,
        "high_corr_pairs": high_corr_pairs,
        "clusters": clusters,
        "keep_list": keep_list,
        "feature_cols": feature_cols,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  6.  PCA reduction
# ─────────────────────────────────────────────────────────────────────────────

def reduce_features_pca(df: pd.DataFrame,
                        feature_cols: list,
                        prefix: str = "pc",
                        variance_threshold: float = 0.90,
                        verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Replace a set of features with PCA components.
    Standardizes within each season to handle era differences.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA

    if len(feature_cols) < 2:
        return df, pd.DataFrame()

    df = df.copy()
    valid_cols = [c for c in feature_cols if c in df.columns]
    if len(valid_cols) < 2:
        return df, pd.DataFrame()

    X = df[valid_cols].copy()
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X.fillna(X.median())),
        index=df.index,
        columns=valid_cols,
    )

    pca = PCA()
    pca.fit(X_scaled.values)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n_components = int(np.searchsorted(cumvar, variance_threshold)) + 1
    n_components = max(2, min(n_components, len(valid_cols)))

    pca_final = PCA(n_components=n_components)
    components = pca_final.fit_transform(X_scaled.values)

    pc_cols = [f"{prefix}_{i+1}" for i in range(n_components)]
    for i, col in enumerate(pc_cols):
        df[col] = components[:, i]

    loadings = pd.DataFrame(
        pca_final.components_.T,
        index=valid_cols,
        columns=pc_cols,
    )

    if verbose:
        print(f"  PCA on {len(valid_cols)} features -> {n_components} components ({cumvar[n_components-1]:.1%} variance)")

    df = df.drop(columns=valid_cols, errors="ignore")
    return df, loadings


# ─────────────────────────────────────────────────────────────────────────────
#  7.  Temporal rating alignment (BPI and Sagarin)
# ─────────────────────────────────────────────────────────────────────────────

def align_ratings_to_games(games: pd.DataFrame,
                           bpi: pd.DataFrame,
                           sagarin: pd.DataFrame,
                           team_map: pd.DataFrame) -> pd.DataFrame:
    """
    For each game, find the most recent rating BEFORE the game date.
    Strict temporal safety: rating_date < game_date.
    """
    df = games.copy()
    df["game_date"] = pd.to_datetime(df["game_date"]).astype("datetime64[us]")
    df = df.sort_values("game_date").reset_index(drop=True)

    # --- BPI alignment ---
    bpi_cols = ["bpi", "bpirank", "bpioffense", "bpidefense", "playoffbpi", "offtalent", "deftalent"]
    if not bpi.empty:
        # Map BPI team_abbrev to team_id via team_map
        abbr_to_id = team_map.drop_duplicates("TEAM_ABBREVIATION").set_index("TEAM_ABBREVIATION")["TEAM_ID"].to_dict()
        bpi_work = bpi.copy()
        bpi_work["team_id"] = bpi_work["team_abbrev"].map(abbr_to_id)
        bpi_work = bpi_work.dropna(subset=["team_id"])
        bpi_work["team_id"] = bpi_work["team_id"].astype(int)
        bpi_work["snapshot_timestamp"] = pd.to_datetime(bpi_work["snapshot_timestamp"]).astype("datetime64[us]")
        bpi_work = bpi_work.sort_values("snapshot_timestamp")

        for side in ["home", "away"]:
            team_col = f"{side}_team_id"
            side_games = df[["game_date", team_col]].copy()
            side_games = side_games.rename(columns={team_col: "team_id"})
            side_games["team_id"] = pd.to_numeric(side_games["team_id"], errors="coerce")
            valid = side_games["team_id"].notna()
            side_games = side_games[valid].copy()
            side_games["team_id"] = side_games["team_id"].astype("int64")

            bpi_merge = bpi_work[["snapshot_timestamp", "team_id"] + bpi_cols].copy()
            bpi_merge["team_id"] = bpi_merge["team_id"].astype("int64")

            merged = pd.merge_asof(
                side_games.sort_values("game_date").reset_index(),
                bpi_merge.sort_values("snapshot_timestamp"),
                left_on="game_date",
                right_on="snapshot_timestamp",
                by="team_id",
                direction="backward",
                allow_exact_matches=False,
            )
            for col in bpi_cols:
                df.loc[merged["index"].values, f"{side}_{col}"] = merged[col].values

    # --- Sagarin alignment ---
    sag_cols = ["sag_rating", "elo_score", "predictor", "pure_elo", "golden_mean", "recent"]
    if not sagarin.empty and len(sagarin) > 0:
        # Sagarin uses team name — map via team_map
        name_to_abbr = team_map.drop_duplicates("TEAM_NAME").set_index("TEAM_NAME")["TEAM_ABBREVIATION"].to_dict()
        sag_work = sagarin.copy()
        sag_work["team_abbr"] = sag_work["team"].map(name_to_abbr)
        # Fallback: try partial matching for edge cases
        if sag_work["team_abbr"].isna().sum() > 0:
            for sag_name in sag_work.loc[sag_work["team_abbr"].isna(), "team"].unique():
                for map_name, abbr in name_to_abbr.items():
                    if sag_name.lower() in map_name.lower() or map_name.lower() in sag_name.lower():
                        sag_work.loc[sag_work["team"] == sag_name, "team_abbr"] = abbr
                        break

        abbr_to_id_map = team_map.drop_duplicates("TEAM_ABBREVIATION").set_index("TEAM_ABBREVIATION")["TEAM_ID"].to_dict()
        sag_work["team_id"] = sag_work["team_abbr"].map(abbr_to_id_map)
        sag_work = sag_work.dropna(subset=["team_id"])
        sag_work["team_id"] = sag_work["team_id"].astype(int)
        sag_work["as_of_date"] = pd.to_datetime(sag_work["as_of_date"]).astype("datetime64[us]")
        sag_work = sag_work.dropna(subset=["as_of_date"])
        sag_work = sag_work.sort_values("as_of_date")

        available_sag_cols = [c for c in sag_cols if c in sag_work.columns]

        for side in ["home", "away"]:
            team_col = f"{side}_team_id"
            side_games = df[["game_date", team_col]].copy()
            side_games = side_games.rename(columns={team_col: "team_id"})
            side_games["team_id"] = pd.to_numeric(side_games["team_id"], errors="coerce")
            valid = side_games["team_id"].notna()
            side_games = side_games[valid].copy()
            side_games["team_id"] = side_games["team_id"].astype("int64")

            sag_merge = sag_work[["as_of_date", "team_id"] + available_sag_cols].copy()
            sag_merge["team_id"] = sag_merge["team_id"].astype("int64")

            merged = pd.merge_asof(
                side_games.sort_values("game_date").reset_index(),
                sag_merge.sort_values("as_of_date"),
                left_on="game_date",
                right_on="as_of_date",
                by="team_id",
                direction="backward",
                allow_exact_matches=False,
            )
            for col in available_sag_cols:
                df.loc[merged["index"].values, f"{side}_{col}"] = merged[col].values

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  8.  Rolling box score features
# ─────────────────────────────────────────────────────────────────────────────

def compute_rolling_features(games: pd.DataFrame,
                             windows: list[int] = (5, 10, 20),
                             stat_cols: list[str] | None = None) -> pd.DataFrame:
    """
    For each team, compute rolling mean/std of box score stats over last N games.
    Strict temporal ordering: only uses games BEFORE the current game.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if stat_cols is None:
        stat_cols = [c.replace("home_", "") for c in df.columns
                     if c.startswith("home_")
                     and c not in {"home_team_abbr", "home_team_id", "home_team_name",
                                   "home_wl", "home_min_trad"}
                     and not c.startswith("home_roll")
                     and df[c].dtype in (np.float64, np.int64, float, int)]

    # Build per-team game history (one row per team-game)
    home_games = df[["game_date", "home_team_id", "home_wl"] +
                    [f"home_{s}" for s in stat_cols if f"home_{s}" in df.columns]].copy()
    home_games = home_games.rename(columns=lambda c: c.replace("home_", "") if c != "game_date" else c)
    home_games = home_games.rename(columns={"team_id": "team_id"})

    away_games = df[["game_date", "away_team_id", "away_wl"] +
                    [f"away_{s}" for s in stat_cols if f"away_{s}" in df.columns]].copy()
    away_games = away_games.rename(columns=lambda c: c.replace("away_", "") if c != "game_date" else c)
    away_games = away_games.rename(columns={"team_id": "team_id"})

    team_history = pd.concat([home_games, away_games], ignore_index=True)
    team_history = team_history.sort_values(["team_id", "game_date"]).reset_index(drop=True)

    # Ensure stat columns are numeric
    available_stats = [s for s in stat_cols if s in team_history.columns]
    for col in available_stats:
        team_history[col] = pd.to_numeric(team_history[col], errors="coerce")

    # Compute rolling stats per team
    rolling_results = {}
    for window in windows:
        for stat in available_stats:
            col_mean = f"roll{window}_{stat}"
            col_std = f"roll{window}_{stat}_std"
            team_history[col_mean] = (
                team_history.groupby("team_id")[stat]
                .transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
            )
            team_history[col_std] = (
                team_history.groupby("team_id")[stat]
                .transform(lambda x: x.shift(1).rolling(window, min_periods=2).std())
            )

    # Win streak
    team_history["_win"] = (team_history["wl"] == "W").astype(int)
    team_history["win_streak"] = (
        team_history.groupby("team_id")["_win"]
        .transform(lambda x: x.shift(1).rolling(20, min_periods=1).sum())
    )

    # Days since last game
    team_history["days_rest"] = (
        team_history.groupby("team_id")["game_date"]
        .transform(lambda x: x.diff().dt.days)
    )
    team_history["is_back_to_back"] = (team_history["days_rest"] == 1).astype(int)

    roll_cols = [c for c in team_history.columns
                 if c.startswith("roll") or c in ("win_streak", "days_rest", "is_back_to_back")]

    # Deduplicate: keep first occurrence per (team_id, game_date) — handles rare same-day games
    team_history = team_history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    # Map back to game rows
    home_merge = team_history[["team_id", "game_date"] + roll_cols].rename(
        columns={c: f"home_{c}" for c in roll_cols}
    ).rename(columns={"team_id": "home_team_id"})

    away_merge = team_history[["team_id", "game_date"] + roll_cols].rename(
        columns={c: f"away_{c}" for c in roll_cols}
    ).rename(columns={"team_id": "away_team_id"})

    df = df.merge(home_merge, on=["home_team_id", "game_date"], how="left")
    df = df.merge(away_merge, on=["away_team_id", "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  9.  Score momentum features
# ─────────────────────────────────────────────────────────────────────────────

def compute_score_momentum(games: pd.DataFrame) -> pd.DataFrame:
    """Compute win streaks, margin trends, quarter momentum per team."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    # Build margin per team per game
    if "home_pts" in df.columns and "away_pts" in df.columns:
        home_margins = df[["game_date", "home_team_id", "home_pts", "away_pts"]].copy()
        home_margins["margin"] = home_margins["home_pts"] - home_margins["away_pts"]
        home_margins = home_margins.rename(columns={"home_team_id": "team_id"})

        away_margins = df[["game_date", "away_team_id", "home_pts", "away_pts"]].copy()
        away_margins["margin"] = away_margins["away_pts"] - away_margins["home_pts"]
        away_margins = away_margins.rename(columns={"away_team_id": "team_id"})

        margins = pd.concat([
            home_margins[["game_date", "team_id", "margin"]],
            away_margins[["game_date", "team_id", "margin"]],
        ]).sort_values(["team_id", "game_date"]).reset_index(drop=True)

        for lag in [1, 3, 5]:
            col = f"margin_last{lag}"
            margins[col] = (
                margins.groupby("team_id")["margin"]
                .transform(lambda x: x.shift(1).rolling(lag, min_periods=1).mean())
            )

        margin_cols = [c for c in margins.columns if c.startswith("margin_last")]

        # Deduplicate before merge
        margins = margins.drop_duplicates(subset=["team_id", "game_date"], keep="last")

        # Map back
        home_m = margins[["game_date", "team_id"] + margin_cols].rename(
            columns={c: f"home_{c}" for c in margin_cols}
        ).rename(columns={"team_id": "home_team_id"})

        away_m = margins[["game_date", "team_id"] + margin_cols].rename(
            columns={c: f"away_{c}" for c in margin_cols}
        ).rename(columns={"team_id": "away_team_id"})

        df = df.merge(home_m, on=["home_team_id", "game_date"], how="left")
        df = df.merge(away_m, on=["away_team_id", "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  10.  Context & travel features
# ─────────────────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    """Haversine distance in miles."""
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def _timezone_from_lon(lon: float) -> float:
    """Approximate timezone offset from longitude (hours from UTC)."""
    return lon / 15.0


def compute_context_features(games: pd.DataFrame,
                             arenas: pd.DataFrame,
                             game_summaries: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute rest days, travel distance, crowd density, timezone shift."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    # Arena lookup by team name
    arena_lookup = arenas.set_index("team")[["lat", "lon"]].to_dict("index")

    # Travel distance: distance from team's home arena to game location
    # For home team: 0. For away team: haversine from their home to the game arena.
    home_lats, home_lons = [], []
    away_lats, away_lons = [], []

    team_map_by_abbr = {}
    for team_name, coords in arena_lookup.items():
        team_map_by_abbr[team_name] = coords

    # Map team abbreviation to team name for arena lookup
    # Use the arenas df directly - join on team name
    if "home_team_name" in df.columns:
        home_coords = df["home_team_name"].map(
            lambda t: arena_lookup.get(t, {"lat": np.nan, "lon": np.nan})
        )
        away_coords = df["away_team_name"].map(
            lambda t: arena_lookup.get(t, {"lat": np.nan, "lon": np.nan})
        )

        df["_home_lat"] = home_coords.apply(lambda x: x["lat"])
        df["_home_lon"] = home_coords.apply(lambda x: x["lon"])
        df["_away_lat"] = away_coords.apply(lambda x: x["lat"])
        df["_away_lon"] = away_coords.apply(lambda x: x["lon"])

        # Travel distance for away team (from their home to this game's arena = home team arena)
        df["away_travel_distance"] = _haversine(
            df["_away_lat"], df["_away_lon"],
            df["_home_lat"], df["_home_lon"]
        )
        df["home_travel_distance"] = 0.0

        # Timezone shift (away team perspective: negative = lost hours going east)
        df["away_timezone_shift"] = (
            _timezone_from_lon(df["_home_lon"]) - _timezone_from_lon(df["_away_lon"])
        )
        df["home_timezone_shift"] = 0.0

        df = df.drop(columns=["_home_lat", "_home_lon", "_away_lat", "_away_lon"])

    # Crowd density from game summaries
    if game_summaries is not None and "attendance" in game_summaries.columns:
        # Derive capacity as max attendance per arena
        if "arena_name" in game_summaries.columns:
            arena_capacity = game_summaries.groupby("arena_name")["attendance"].max().to_dict()
            if "game_id" in df.columns and "game_id" in game_summaries.columns:
                gs_merge = game_summaries[["game_id", "attendance", "arena_name", "sellout_flag"]].copy()
                gs_merge["arena_capacity"] = gs_merge["arena_name"].map(arena_capacity)
                gs_merge["crowd_density"] = gs_merge["attendance"] / gs_merge["arena_capacity"].replace(0, np.nan)
                df = df.merge(gs_merge[["game_id", "crowd_density", "sellout_flag"]], on="game_id", how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  11.  Referee features
# ─────────────────────────────────────────────────────────────────────────────

def compute_referee_features(games: pd.DataFrame,
                             officials: pd.DataFrame) -> pd.DataFrame:
    """
    For each game's referee crew, compute historical home win rate and avg total points.
    Only uses history from BEFORE the current game (temporal safety).
    """
    df = games.copy()

    if "game_id" not in df.columns or "game_id" not in officials.columns:
        return df

    # Build referee history: for each referee, rolling stats from prior games
    game_outcomes = df[["game_id", "game_date", "target_winner", "target_total"]].drop_duplicates("game_id")
    ref_games = officials.merge(game_outcomes, on="game_id", how="inner")
    ref_games = ref_games.sort_values("game_date")

    # Compute rolling stats per referee
    ref_stats = {}
    for ref_id, grp in ref_games.groupby("official_id"):
        grp = grp.sort_values("game_date")
        grp["ref_home_win_rate"] = grp["target_winner"].expanding().mean().shift(1)
        grp["ref_avg_total"] = grp["target_total"].expanding().mean().shift(1)
        grp["ref_game_count"] = range(len(grp))
        ref_stats[ref_id] = grp[["game_id", "ref_home_win_rate", "ref_avg_total", "ref_game_count"]]

    if not ref_stats:
        return df

    all_ref_stats = pd.concat(ref_stats.values())

    # Average across the crew for each game
    crew_stats = all_ref_stats.groupby("game_id").agg(
        crew_home_win_rate=("ref_home_win_rate", "mean"),
        crew_avg_total=("ref_avg_total", "mean"),
        crew_experience=("ref_game_count", "mean"),
    ).reset_index()

    # Only use refs with sufficient history (min 30 games)
    crew_stats.loc[crew_stats["crew_experience"] < 30, ["crew_home_win_rate", "crew_avg_total"]] = np.nan

    df = df.merge(crew_stats, on="game_id", how="left")
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  12.  Roster features
# ─────────────────────────────────────────────────────────────────────────────

def compute_roster_features(games: pd.DataFrame,
                            player_box: pd.DataFrame) -> pd.DataFrame:
    """Compute active roster size, DNP count, roster continuity."""
    df = games.copy()

    if "game_id" not in df.columns or "game_id" not in player_box.columns:
        return df

    # Active vs DNP per team per game
    roster_stats = player_box.groupby(["game_id", "team_id"]).agg(
        total_roster=("player_id", "count"),
        dnp_count=("dnp_comment", lambda x: x.notna().sum()),
    ).reset_index()
    roster_stats["active_players"] = roster_stats["total_roster"] - roster_stats["dnp_count"]

    # Merge for home
    home_roster = roster_stats.rename(columns={
        "team_id": "home_team_id",
        "active_players": "home_active_players",
        "dnp_count": "home_dnp_count",
    })
    df = df.merge(
        home_roster[["game_id", "home_team_id", "home_active_players", "home_dnp_count"]],
        on=["game_id", "home_team_id"],
        how="left",
    )

    # Merge for away
    away_roster = roster_stats.rename(columns={
        "team_id": "away_team_id",
        "active_players": "away_active_players",
        "dnp_count": "away_dnp_count",
    })
    df = df.merge(
        away_roster[["game_id", "away_team_id", "away_active_players", "away_dnp_count"]],
        on=["game_id", "away_team_id"],
        how="left",
    )

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  13.  Random weighted combinations (de Prado approach)
# ─────────────────────────────────────────────────────────────────────────────

def generate_random_combinations(games: pd.DataFrame,
                                 base_cols: list[str] | None = None,
                                 n_combos: int | None = None,
                                 seed: int = 42) -> pd.DataFrame:
    """
    Generate random weighted linear combinations of box score features.
    De Prado's approach: yolo random combos, then filter via importance.
    If they survive MDI/MDA/SFI, investigate theory post-hoc.
    """
    df = games.copy()

    if n_combos is None:
        n_combos = get_n_random_combos()

    if base_cols is None:
        base_cols = [c for c in df.columns
                     if c.startswith("diff_") and df[c].dtype in (np.float64, np.int64, float, int)
                     and not c.startswith("diff_roll")]
    base_cols = [c for c in base_cols if c in df.columns]

    if len(base_cols) < 2:
        return df

    rng = np.random.default_rng(seed)
    X = df[base_cols].values

    for i in range(n_combos):
        weights = rng.standard_normal(len(base_cols))
        weights = weights / np.linalg.norm(weights)
        df[f"rc_{i:03d}"] = X @ weights

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  14.  Differential features
# ─────────────────────────────────────────────────────────────────────────────

def compute_diffs(games: pd.DataFrame) -> pd.DataFrame:
    """
    For every home_X / away_X pair, compute diff_X = home_X - away_X.
    This is the final representation for classification.
    """
    df = games.copy()

    home_cols = [c for c in df.columns
                 if c.startswith("home_") and df[c].dtype in (np.float64, np.int64, float, int)]

    for hcol in home_cols:
        suffix = hcol[5:]  # strip "home_"
        acol = f"away_{suffix}"
        if acol in df.columns and df[acol].dtype in (np.float64, np.int64, float, int):
            df[f"diff_{suffix}"] = df[hcol] - df[acol]

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  15.  De Prado features (entropy, CUSUM applied to team game histories)
# ─────────────────────────────────────────────────────────────────────────────

def compute_deprado_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    Compute de Prado-inspired features per team:
    - Win sequence entropy (rolling)
    - CUSUM momentum shift
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    # Build team-game history
    home = df[["game_date", "home_team_id", "home_wl"]].rename(
        columns={"home_team_id": "team_id", "home_wl": "wl"}
    )
    away = df[["game_date", "away_team_id", "away_wl"]].rename(
        columns={"away_team_id": "team_id", "away_wl": "wl"}
    )
    history = pd.concat([home, away]).sort_values(["team_id", "game_date"]).reset_index(drop=True)
    history["_win"] = (history["wl"] == "W").astype(float)

    # Rolling win pct (last 20 games)
    history["win_pct_20"] = (
        history.groupby("team_id")["_win"]
        .transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    )

    # Rolling entropy (from last 10 W/L)
    def _rolling_entropy(x):
        x_shifted = x.shift(1)
        result = x_shifted.rolling(10, min_periods=5).apply(
            lambda w: win_sequence_entropy(w.sum(), len(w) - w.sum()), raw=False
        )
        return result

    history["win_entropy"] = history.groupby("team_id")["_win"].transform(_rolling_entropy)

    # CUSUM on win pct
    def _cusum_rolling(x):
        x_shifted = x.shift(1)
        return x_shifted.rolling(20, min_periods=5).apply(
            lambda w: cusum_peak(pd.Series(w), h=0.05), raw=False
        )

    history["cusum_momentum"] = history.groupby("team_id")["_win"].transform(_cusum_rolling)

    deprado_cols = ["win_pct_20", "win_entropy", "cusum_momentum"]

    # Deduplicate before merge
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    # Map back to game rows
    home_dp = history[["game_date", "team_id"] + deprado_cols].rename(
        columns={c: f"home_{c}" for c in deprado_cols}
    ).rename(columns={"team_id": "home_team_id"})

    away_dp = history[["game_date", "team_id"] + deprado_cols].rename(
        columns={c: f"away_{c}" for c in deprado_cols}
    ).rename(columns={"team_id": "away_team_id"})

    df = df.merge(home_dp, on=["home_team_id", "game_date"], how="left")
    df = df.merge(away_dp, on=["away_team_id", "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Feature group constants
# ─────────────────────────────────────────────────────────────────────────────

RATING_FEATURES = [
    "diff_bpi", "diff_bpioffense", "diff_bpidefense", "diff_playoffbpi",
    "diff_offtalent", "diff_deftalent",
    "diff_sag_rating", "diff_elo_score", "diff_predictor",
    "diff_pure_elo", "diff_golden_mean", "diff_recent",
]

MASSEY_FEATURES = [
    "diff_default_massey", "diff_location_adjusted_massey",
    "diff_crowd_adjusted_massey", "diff_crowd_weighted_massey",
    "diff_experience_adjusted_massey", "diff_travel_adjusted_massey",
    "diff_context_adjusted_massey",
]

ROLLING_BOX_FEATURES = [
    "diff_roll5_pts", "diff_roll5_offrtg", "diff_roll5_defrtg", "diff_roll5_netrtg",
    "diff_roll5_pace", "diff_roll5_pie", "diff_roll5_efgpct", "diff_roll5_tspct",
    "diff_roll10_pts", "diff_roll10_offrtg", "diff_roll10_defrtg", "diff_roll10_netrtg",
    "diff_roll20_pts", "diff_roll20_offrtg", "diff_roll20_defrtg",
]

MOMENTUM_FEATURES = [
    "diff_win_streak", "diff_margin_last1", "diff_margin_last3", "diff_margin_last5",
    "diff_win_pct_20", "diff_win_entropy", "diff_cusum_momentum",
]

CONTEXT_FEATURES = [
    "diff_days_rest", "diff_is_back_to_back",
    "away_travel_distance", "away_timezone_shift",
    "crowd_density", "sellout_flag",
    "crew_home_win_rate", "crew_avg_total", "crew_experience",
]

ROSTER_FEATURES = [
    "diff_active_players", "diff_dnp_count",
]

SERIES_FEATURES = [
    "series_game_number", "series_lead",
]

ALL_FEATURES = (
    RATING_FEATURES + MASSEY_FEATURES + ROLLING_BOX_FEATURES +
    MOMENTUM_FEATURES + CONTEXT_FEATURES + ROSTER_FEATURES
)

PLAYOFF_FEATURES = ALL_FEATURES + SERIES_FEATURES
