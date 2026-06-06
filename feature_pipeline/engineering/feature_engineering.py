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

import logging

import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm

from feature_pipeline.compute import get_n_random_combos
from feature_pipeline.logging_config import log_value_stats

logger = logging.getLogger(__name__)


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
    Symmetric CUSUM filter (de Prado AFML Ch.2, Sec 2.5.2.1).

    Detects structural breaks by accumulating deviations from the expanding
    mean of prior observations. Returns the peak absolute cumulative deviation.
    """
    s_pos = 0.0
    s_neg = 0.0
    peak = 0.0
    running_sum = 0.0
    count = 0

    for y_t in series:
        if count == 0:
            e_prev = y_t
        else:
            e_prev = running_sum / count

        delta = y_t - e_prev
        s_pos = max(0.0, s_pos + delta)
        s_neg = min(0.0, s_neg + delta)
        peak = max(peak, s_pos, abs(s_neg))

        if s_pos >= h:
            s_pos = 0.0
        if abs(s_neg) >= h:
            s_neg = 0.0

        running_sum += y_t
        count += 1

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
    nan_before = int(df[numeric_cols].isna().sum().sum())
    if strategy == "median":
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    elif strategy == "zero":
        df[numeric_cols] = df[numeric_cols].fillna(0)
    nan_after = int(df[numeric_cols].isna().sum().sum())
    logger.info("[handle_missing] strategy=%s  filled=%d NaN values across %d numeric cols",
                strategy, nan_before - nan_after, len(numeric_cols))
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

    for side in ("home", "away"):
        bpi_col = f"{side}_bpi"
        sag_col = f"{side}_sag_rating"
        bpi_cov = df[bpi_col].notna().mean() if bpi_col in df.columns else 0.0
        sag_cov = df[sag_col].notna().mean() if sag_col in df.columns else 0.0
        logger.info("[align_ratings_to_games] %s BPI coverage=%.1f%%  Sagarin coverage=%.1f%%",
                    side, 100 * bpi_cov, 100 * sag_cov)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  7b.  Massey rating alignment (from precomputed parquet)
# ─────────────────────────────────────────────────────────────────────────────

def align_massey_to_games(games: pd.DataFrame, massey: pd.DataFrame) -> pd.DataFrame:
    """
    Align precomputed Massey ratings to games. Massey parquet has one row per
    (season, game_date, team_id) — ratings are computed from games BEFORE that date.
    We merge on exact (season, game_date, team_id) since the parquet already
    encodes the temporal safety.
    """
    df = games.copy()

    if massey.empty:
        return df

    massey = massey.copy()
    massey["game_date"] = pd.to_datetime(massey["game_date"]).astype("datetime64[us]")
    massey["team_id"] = massey["team_id"].astype(int)

    # Identify rating columns (not season, game_date, team_id, or ranks)
    rating_cols = [c for c in massey.columns
                   if c not in ("season", "game_date", "team_id") and not c.endswith("_rank")]

    # Merge for home team
    home_massey = massey.rename(columns={c: f"home_{c}" for c in rating_cols})
    home_massey = home_massey.rename(columns={"team_id": "home_team_id"})
    df = df.merge(
        home_massey[["season", "game_date", "home_team_id"] + [f"home_{c}" for c in rating_cols]],
        on=["season", "game_date", "home_team_id"],
        how="left",
    )

    # Merge for away team
    away_massey = massey.rename(columns={c: f"away_{c}" for c in rating_cols})
    away_massey = away_massey.rename(columns={"team_id": "away_team_id"})
    df = df.merge(
        away_massey[["season", "game_date", "away_team_id"] + [f"away_{c}" for c in rating_cols]],
        on=["season", "game_date", "away_team_id"],
        how="left",
    )

    massey_game_cols = [c for c in df.columns if any(r in c for r in rating_cols) and c.startswith(("home_", "away_"))]
    if massey_game_cols:
        coverages = {c: df[c].notna().mean() for c in massey_game_cols}
        worst_col = min(coverages, key=coverages.get)
        worst_cov = coverages[worst_col]
        rep_cov = df[massey_game_cols[0]].notna().mean()
        logger.info("[align_massey_to_games] %d massey cols attached  representative coverage=%.1f%%",
                    len(massey_game_cols), 100 * rep_cov)
        if worst_cov < 0.8:
            logger.warning("[align_massey_to_games] low coverage col: %s = %.1f%%",
                           worst_col, 100 * worst_cov)

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

    # Force-cast home/away stat columns to numeric so string-encoded numbers
    # (e.g. plus_minus stored as object) are not excluded from rolling features.
    for side in ("home_", "away_"):
        for col in df.columns:
            if col.startswith(side) and col not in {
                f"{side}team_abbr", f"{side}team_id", f"{side}team_name",
                f"{side}wl", f"{side}min_trad",
            } and not col.startswith(f"{side}roll"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

    if stat_cols is None:
        stat_cols = [c.replace("home_", "") for c in df.columns
                     if c.startswith("home_")
                     and c not in {"home_team_abbr", "home_team_id", "home_team_name",
                                   "home_wl", "home_min_trad"}
                     and not c.startswith("home_roll")
                     and df[c].dtype.kind in "fi"]

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

    logger.info("[compute_rolling_features] team_history rows=%d  teams=%d  stats=%d  windows=%s",
                len(team_history), team_history["team_id"].nunique(), len(available_stats), list(windows))

    # Compute rolling stats per team — collect into dict, concat once to avoid fragmentation
    new_cols = {}
    for window in windows:
        for stat in tqdm(available_stats, desc=f"rolling w={window}", unit="stat", leave=False):
            grp = team_history.groupby("team_id")[stat]
            new_cols[f"roll{window}_{stat}"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).mean()
            )
            new_cols[f"roll{window}_{stat}_std"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=2).std()
            )

    # Win streak
    _win = (team_history["wl"] == "W").astype(int)
    new_cols["win_streak"] = (
        _win.groupby(team_history["team_id"])
        .transform(lambda x: x.shift(1).rolling(20, min_periods=1).sum())
    )

    # Days since last game
    new_cols["days_rest"] = (
        team_history.groupby("team_id")["game_date"]
        .transform(lambda x: x.diff().dt.days)
    )
    new_cols["is_back_to_back"] = (new_cols["days_rest"] == 1).astype(int)

    team_history = pd.concat([team_history, pd.DataFrame(new_cols, index=team_history.index)], axis=1)

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

    new_roll_cols = [c for c in df.columns if c.startswith(("home_roll", "away_roll"))]
    overall_null = df[new_roll_cols].isna().mean().mean() if new_roll_cols else float("nan")
    logger.info("[compute_rolling_features] %d roll cols added  overall null=%.1f%%",
                len(new_roll_cols), 100 * overall_null)
    if new_roll_cols:
        top_null = df[new_roll_cols].isna().mean().nlargest(5)
        logger.debug("[compute_rolling_features] top-5 null roll cols: %s", top_null.round(3).to_dict())

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  8b.  Venue-conditioned rolling stats (home/away performance splits)
# ─────────────────────────────────────────────────────────────────────────────

VENUE_STATS = ["pts", "offrtg", "defrtg", "netrtg", "pace", "efgpct"]
VENUE_WINDOWS = [10, 20]


def compute_venue_rolling_features(games: pd.DataFrame,
                                   windows: list[int] = VENUE_WINDOWS,
                                   stat_cols: list[str] = VENUE_STATS) -> pd.DataFrame:
    """
    Compute rolling stats SPLIT by venue: a team's recent performance at home
    vs on the road. This captures home-court advantage at the team level.

    For the home team, we use their rolling stats from home games only.
    For the away team, we use their rolling stats from away games only.
    The diff then becomes: how team X plays at home vs how team Y plays on the road.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    # Build separate histories for home and away appearances
    home_hist = df[["game_date", "home_team_id"] +
                   [f"home_{s}" for s in stat_cols if f"home_{s}" in df.columns]].copy()
    home_hist = home_hist.rename(columns=lambda c: c.replace("home_", "") if c != "game_date" else c)
    home_hist = home_hist.rename(columns={"team_id": "team_id"})
    home_hist["_venue"] = "home"

    away_hist = df[["game_date", "away_team_id"] +
                   [f"away_{s}" for s in stat_cols if f"away_{s}" in df.columns]].copy()
    away_hist = away_hist.rename(columns=lambda c: c.replace("away_", "") if c != "game_date" else c)
    away_hist = away_hist.rename(columns={"team_id": "team_id"})
    away_hist["_venue"] = "away"

    available_stats = [s for s in stat_cols if s in home_hist.columns]
    for col in available_stats:
        home_hist[col] = pd.to_numeric(home_hist[col], errors="coerce")
        away_hist[col] = pd.to_numeric(away_hist[col], errors="coerce")

    # Compute rolling per venue type
    venue_cols = []
    for venue_label, hist in [("athome", home_hist), ("onroad", away_hist)]:
        hist = hist.sort_values(["team_id", "game_date"]).reset_index(drop=True)
        for window in windows:
            for stat in available_stats:
                col_name = f"roll{window}_{stat}_{venue_label}"
                hist[col_name] = (
                    hist.groupby("team_id")[stat]
                    .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
                )
                venue_cols.append(col_name)

        # Deduplicate
        hist_dedup = hist.drop_duplicates(subset=["team_id", "game_date"], keep="last")

        # Merge back: home team gets "athome" stats, away team gets "onroad" stats
        if venue_label == "athome":
            merge_cols = [c for c in hist_dedup.columns if c.startswith("roll") and c.endswith("_athome")]
            home_venue_merge = hist_dedup[["team_id", "game_date"] + merge_cols].rename(
                columns={c: f"home_{c}" for c in merge_cols}
            ).rename(columns={"team_id": "home_team_id"})
            df = df.merge(home_venue_merge, on=["home_team_id", "game_date"], how="left")
        else:
            merge_cols = [c for c in hist_dedup.columns if c.startswith("roll") and c.endswith("_onroad")]
            away_venue_merge = hist_dedup[["team_id", "game_date"] + merge_cols].rename(
                columns={c: f"away_{c}" for c in merge_cols}
            ).rename(columns={"team_id": "away_team_id"})
            df = df.merge(away_venue_merge, on=["away_team_id", "game_date"], how="left")

    venue_cols_added = [c for c in df.columns if c.endswith(("_athome", "_onroad"))]
    avg_null = df[venue_cols_added].isna().mean().mean() if venue_cols_added else float("nan")
    logger.info("[compute_venue_rolling_features] %d venue cols added  avg null=%.1f%%",
                len(venue_cols_added), 100 * avg_null)

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

        if "home_margin_last1" in df.columns:
            log_value_stats(df["home_margin_last1"], "home_margin_last1", logger)

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

    # Crowd density: use rolling historical arena fill rate (not same-game attendance).
    # Sellout flag: playoffs always sell out; regular season uses historical sellout rate.
    if game_summaries is not None and "attendance" in game_summaries.columns:
        if "arena_name" in game_summaries.columns and "game_id" in df.columns and "game_id" in game_summaries.columns:
            arena_capacity = game_summaries.groupby("arena_name")["attendance"].max().to_dict()
            gs = game_summaries[["game_id", "attendance", "arena_name"]].copy()
            gs["arena_capacity"] = gs["arena_name"].map(arena_capacity)
            gs["_density"] = gs["attendance"] / gs["arena_capacity"].replace(0, np.nan)
            gs["_sellout"] = (gs["_density"] >= 0.98).astype(float)

            if "game_date" in df.columns:
                gs = gs.merge(
                    df[["game_id", "game_date"]].drop_duplicates("game_id"),
                    on="game_id", how="left"
                )
                gs = gs.sort_values("game_date")

                gs["crowd_density"] = (
                    gs.groupby("arena_name")["_density"]
                    .transform(lambda x: x.shift(1).rolling(10, min_periods=3).mean())
                )
                gs["_hist_sellout_rate"] = (
                    gs.groupby("arena_name")["_sellout"]
                    .transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
                )

                df = df.merge(gs[["game_id", "crowd_density", "_hist_sellout_rate"]], on="game_id", how="left")

                is_playoff = df.get("season_type", pd.Series("", index=df.index)).str.contains("Playoff", case=False, na=False)
                df["sellout_flag"] = np.where(
                    is_playoff, 1.0,
                    np.where(df["_hist_sellout_rate"] > 0.8, 1.0, 0.0)
                )
                df = df.drop(columns=["_hist_sellout_rate"], errors="ignore")

    if "away_travel_distance" in df.columns:
        valid = df["away_travel_distance"].dropna()
        if len(valid):
            p5, p50, p95 = np.percentile(valid, [5, 50, 95])
            logger.info("[compute_context_features] away_travel_distance: P5=%.0f  P50=%.0f  P95=%.0f miles",
                        p5, p50, p95)
    if "away_timezone_shift" in df.columns:
        log_value_stats(df["away_timezone_shift"], "away_timezone_shift_hours", logger)
    if "crowd_density" in df.columns:
        log_value_stats(df["crowd_density"], "crowd_density", logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  10b.  Travel sequence / fatigue features
# ─────────────────────────────────────────────────────────────────────────────

def compute_travel_sequence_features(games: pd.DataFrame,
                                     arenas: pd.DataFrame,
                                     windows: list[int] = (3, 5)) -> pd.DataFrame:
    """
    Per-team travel fatigue features capturing road trip length, schedule density,
    venue-switching frequency, cumulative game-to-game distance, and travel
    intensity (distance normalized by time between games).

    Features produced (per team, then differenced as home_ - away_):
      - away_streak: consecutive away games entering this game
      - days_span_{w}: calendar days spanned by last w games (schedule density)
      - games_per_week_{w}: games per 7 days over last w games
      - venue_switches_{w}: number of home/away flips in last w games
      - travel_distance_{w}: cumulative game-to-game miles in last w games
      - travel_intensity_{w}: travel_distance_{w} / days_span_{w} (miles per day)
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    arena_lookup = arenas.set_index("team")[["lat", "lon"]].to_dict("index")

    # Build per-team game history with venue info and game location
    home_games = df[["game_date", "home_team_id", "home_team_name"]].copy()
    home_games.columns = ["game_date", "team_id", "team_name"]
    home_games["is_away"] = 0
    home_games["game_arena_team"] = df["home_team_name"]

    away_games = df[["game_date", "away_team_id", "away_team_name"]].copy()
    away_games.columns = ["game_date", "team_id", "team_name"]
    away_games["is_away"] = 1
    away_games["game_arena_team"] = df["home_team_name"]  # game played at home team's arena

    team_history = pd.concat([home_games, away_games], ignore_index=True)
    team_history = team_history.sort_values(["team_id", "game_date"]).reset_index(drop=True)

    # Resolve lat/lon for the arena where each game is played
    team_history["_game_lat"] = team_history["game_arena_team"].map(
        lambda t: arena_lookup.get(t, {}).get("lat", np.nan)
    )
    team_history["_game_lon"] = team_history["game_arena_team"].map(
        lambda t: arena_lookup.get(t, {}).get("lon", np.nan)
    )

    # Consecutive away games entering this game (shifted: only prior games)
    def _away_streak(is_away_series):
        streak = np.zeros(len(is_away_series), dtype=float)
        current = 0
        for i in range(len(is_away_series)):
            streak[i] = current  # value entering this game
            if is_away_series.iloc[i] == 1:
                current += 1
            else:
                current = 0
        return pd.Series(streak, index=is_away_series.index)

    team_history["away_streak"] = (
        team_history.groupby("team_id")["is_away"]
        .transform(_away_streak)
    )

    # Game-to-game distance (from previous game's location to this game's location)
    team_history["_prev_lat"] = team_history.groupby("team_id")["_game_lat"].shift(1)
    team_history["_prev_lon"] = team_history.groupby("team_id")["_game_lon"].shift(1)
    team_history["_leg_distance"] = _haversine(
        team_history["_prev_lat"], team_history["_prev_lon"],
        team_history["_game_lat"], team_history["_game_lon"],
    )
    team_history["_leg_distance"] = team_history["_leg_distance"].fillna(0)

    # Venue switch (did they flip home/away from previous game?)
    team_history["_venue_switch"] = (
        team_history.groupby("team_id")["is_away"]
        .transform(lambda x: (x != x.shift(1)).astype(int))
    )

    # Days since previous game (for schedule density)
    team_history["_days_gap"] = (
        team_history.groupby("team_id")["game_date"]
        .transform(lambda x: x.diff().dt.days)
    ).fillna(3)  # assume ~3 day gap for first game

    # Rolling features over windows (shifted so only prior games count)
    for w in windows:
        team_history[f"venue_switches_{w}"] = (
            team_history.groupby("team_id")["_venue_switch"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).sum())
        )
        team_history[f"travel_distance_{w}"] = (
            team_history.groupby("team_id")["_leg_distance"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).sum())
        )
        # Days spanned by last w games (sum of inter-game gaps)
        team_history[f"days_span_{w}"] = (
            team_history.groupby("team_id")["_days_gap"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).sum())
        )
        # Games per week: how compressed the schedule is
        team_history[f"games_per_week_{w}"] = (
            w / team_history[f"days_span_{w}"].replace(0, np.nan) * 7
        )
        # Travel intensity: miles per day (captures "far games packed tight")
        team_history[f"travel_intensity_{w}"] = (
            team_history[f"travel_distance_{w}"]
            / team_history[f"days_span_{w}"].replace(0, np.nan)
        )

    # Columns to merge back
    feat_cols = (
        ["away_streak"] +
        [f"days_span_{w}" for w in windows] +
        [f"games_per_week_{w}" for w in windows] +
        [f"venue_switches_{w}" for w in windows] +
        [f"travel_distance_{w}" for w in windows] +
        [f"travel_intensity_{w}" for w in windows]
    )

    team_history = team_history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    home_merge = team_history[["team_id", "game_date"] + feat_cols].rename(
        columns={c: f"home_{c}" for c in feat_cols}
    ).rename(columns={"team_id": "home_team_id"})

    away_merge = team_history[["team_id", "game_date"] + feat_cols].rename(
        columns={c: f"away_{c}" for c in feat_cols}
    ).rename(columns={"team_id": "away_team_id"})

    df = df.merge(home_merge, on=["home_team_id", "game_date"], how="left")
    df = df.merge(away_merge, on=["away_team_id", "game_date"], how="left")

    seq_cols = [c for c in df.columns if any(x in c for x in ["travel_distance_", "travel_intensity_"])]
    logger.info("[compute_travel_sequence_features] %d travel seq cols added", len(seq_cols))
    for col in seq_cols[:4]:
        log_value_stats(df[col], col, logger)

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
                            player_box: pd.DataFrame,
                            game_ids: pd.DataFrame = None) -> pd.DataFrame:
    """
    Compute active roster size and DNP count per team per game.

    Joins PlayerStatus to games via (game_date, team_id) using NBAGameIDs
    as the bridge to get game_date from game_id.
    """
    df = games.copy()

    if player_box.empty or "game_id" not in player_box.columns:
        return df

    pb = player_box.copy()

    # Attach game_date to player_box via NBAGameIDs lookup
    if game_ids is not None and "game_date" not in pb.columns:
        gi = game_ids[["GAME_ID", "GAME_DATE"]].drop_duplicates("GAME_ID").copy()
        gi["GAME_ID"] = gi["GAME_ID"].astype(str).str.zfill(10)
        gi["GAME_DATE"] = pd.to_datetime(gi["GAME_DATE"])
        pb["game_id"] = pb["game_id"].astype(str).str.zfill(10)
        pb = pb.merge(gi.rename(columns={"GAME_ID": "game_id", "GAME_DATE": "game_date"}),
                      on="game_id", how="left")

    if "game_date" not in pb.columns:
        return df

    pb["game_date"] = pd.to_datetime(pb["game_date"])
    pb["team_id"] = pb["team_id"].astype(int)
    df["game_date"] = pd.to_datetime(df["game_date"])

    # Active vs DNP per team per game-date
    roster_stats = pb.groupby(["game_date", "team_id"]).agg(
        total_roster=("player_id", "count"),
        dnp_count=("dnp_comment", lambda x: x.notna().sum()),
    ).reset_index()
    roster_stats["active_players"] = roster_stats["total_roster"] - roster_stats["dnp_count"]

    # Merge for home
    df["home_team_id_int"] = df["home_team_id"].astype(float).astype("Int64")
    home_merge = roster_stats.rename(columns={
        "team_id": "home_team_id_int",
        "active_players": "home_active_players",
        "dnp_count": "home_dnp_count",
    })
    df = df.merge(
        home_merge[["game_date", "home_team_id_int", "home_active_players", "home_dnp_count"]],
        on=["game_date", "home_team_id_int"],
        how="left",
    )

    # Merge for away
    df["away_team_id_int"] = df["away_team_id"].astype(float).astype("Int64")
    away_merge = roster_stats.rename(columns={
        "team_id": "away_team_id_int",
        "active_players": "away_active_players",
        "dnp_count": "away_dnp_count",
    })
    df = df.merge(
        away_merge[["game_date", "away_team_id_int", "away_active_players", "away_dnp_count"]],
        on=["game_date", "away_team_id_int"],
        how="left",
    )

    df = df.drop(columns=["home_team_id_int", "away_team_id_int"])
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  12b.  Matchup advantage (from off/def Massey splits)
# ─────────────────────────────────────────────────────────────────────────────

def compute_matchup_advantage(games: pd.DataFrame) -> pd.DataFrame:
    """
    Compute asymmetric matchup advantage from off/def Massey splits.

    diff_matchup_advantage = (home_off - away_def) - (away_off - home_def)

    Positive = home team's offense exploits away's defense more than reverse.
    Requires align_massey_to_games to have already attached off/def massey columns.
    """
    df = games.copy()
    if ("home_off_default_massey" in df.columns and
        "away_def_default_massey" in df.columns and
        "away_off_default_massey" in df.columns and
        "home_def_default_massey" in df.columns):
        df["diff_matchup_advantage"] = (
            (df["home_off_default_massey"] - df["away_def_default_massey"]) -
            (df["away_off_default_massey"] - df["home_def_default_massey"])
        )
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  13.  Head-to-head history features
# ─────────────────────────────────────────────────────────────────────────────

def compute_h2h_features(games: pd.DataFrame, n_meetings: int = 5) -> pd.DataFrame:
    """
    Head-to-head history: for each game between teams A and B, compute
    the home team's win rate and average margin in their last n prior meetings.

    Uses canonical pair key (sorted team IDs) and tracks from one team's
    perspective, flipping at merge time. .shift(1) prevents leakage.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "home_pts" not in df.columns or "away_pts" not in df.columns:
        return df

    df["home_team_id"] = df["home_team_id"].astype(float)
    df["away_team_id"] = df["away_team_id"].astype(float)

    # Canonical pair: min/max of team IDs
    pair_a = df[["home_team_id", "away_team_id"]].min(axis=1)
    pair_b = df[["home_team_id", "away_team_id"]].max(axis=1)
    df["_pair_key"] = pair_a.astype(str) + "_" + pair_b.astype(str)

    # Determine game outcome from "team_a" (lower ID) perspective
    df["_home_won"] = (df["home_pts"].astype(float) > df["away_pts"].astype(float)).astype(float)
    df["_margin"] = df["home_pts"].astype(float) - df["away_pts"].astype(float)

    home_is_team_a = (df["home_team_id"] == pair_a)
    df["_team_a_won"] = np.where(home_is_team_a, df["_home_won"], 1 - df["_home_won"])
    df["_team_a_margin"] = np.where(home_is_team_a, df["_margin"], -df["_margin"])

    # Rolling stats from team_a's perspective within each pair (shifted)
    df["_h2h_a_winrate"] = (
        df.groupby("_pair_key")["_team_a_won"]
        .transform(lambda x: x.shift(1).rolling(n_meetings, min_periods=1).mean())
    )
    df["_h2h_a_margin"] = (
        df.groupby("_pair_key")["_team_a_margin"]
        .transform(lambda x: x.shift(1).rolling(n_meetings, min_periods=1).mean())
    )

    # Convert from team_a perspective to home/away perspective
    df["home_h2h_win_rate"] = np.where(
        home_is_team_a, df["_h2h_a_winrate"], 1 - df["_h2h_a_winrate"]
    )
    df["away_h2h_win_rate"] = np.where(
        home_is_team_a, 1 - df["_h2h_a_winrate"], df["_h2h_a_winrate"]
    )
    df["home_h2h_avg_margin"] = np.where(
        home_is_team_a, df["_h2h_a_margin"], -df["_h2h_a_margin"]
    )
    df["away_h2h_avg_margin"] = np.where(
        home_is_team_a, -df["_h2h_a_margin"], df["_h2h_a_margin"]
    )

    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])

    if "home_h2h_win_rate" in df.columns:
        cov = df["home_h2h_win_rate"].notna().mean()
        logger.info("[compute_h2h_features] h2h win rate coverage=%.1f%%  n_meetings=%d",
                    100 * cov, n_meetings)
        log_value_stats(df["home_h2h_avg_margin"], "home_h2h_avg_margin", logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  14.  Matchup-specific conditional stats
# ─────────────────────────────────────────────────────────────────────────────

def compute_conditional_matchup_stats(games: pd.DataFrame) -> pd.DataFrame:
    """
    Team performance conditioned on opponent defensive quality.

    For each team, splits their season games into those against top-half vs
    bottom-half defenses (by opponent's roll20_defrtg at game time). Computes
    an expanding average OffRtg for each bucket.

    Uses median split (not tercile) and expanding mean (not rolling window)
    to maximize data availability — conditional stats are inherently sparse.

    Requires compute_rolling_features to have run first (needs roll20_defrtg).
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "home_roll20_defrtg" not in df.columns or "away_roll20_defrtg" not in df.columns:
        return df
    if "home_offrtg" not in df.columns:
        return df

    # Build per-team game history
    home_hist = df[["game_date", "season", "home_team_id", "home_offrtg", "away_roll20_defrtg"]].copy()
    home_hist.columns = ["game_date", "season", "team_id", "offrtg", "opp_def"]

    away_hist = df[["game_date", "season", "away_team_id", "away_offrtg", "home_roll20_defrtg"]].copy()
    away_hist.columns = ["game_date", "season", "team_id", "offrtg", "opp_def"]

    team_hist = pd.concat([home_hist, away_hist]).sort_values(["team_id", "game_date"]).reset_index(drop=True)
    team_hist["offrtg"] = pd.to_numeric(team_hist["offrtg"], errors="coerce")
    team_hist["opp_def"] = pd.to_numeric(team_hist["opp_def"], errors="coerce")

    # League-wide expanding median DefRtg (no lookahead: shift by grouping on season)
    league_median_def = team_hist.groupby("season")["opp_def"].transform(
        lambda x: x.shift(1).expanding(min_periods=20).median()
    )

    # Lower DefRtg = better defense; below median = good defense
    vs_good = team_hist["opp_def"] < league_median_def
    vs_bad = team_hist["opp_def"] >= league_median_def

    # Expanding mean OffRtg against each bucket (within season, shifted)
    offrtg_good = team_hist["offrtg"].where(vs_good)
    offrtg_bad = team_hist["offrtg"].where(vs_bad)

    team_hist["offrtg_vs_good_def"] = (
        team_hist.groupby(["team_id", "season"]).apply(
            lambda g: offrtg_good.loc[g.index].shift(1).expanding(min_periods=3).mean(),
            include_groups=False,
        ).droplevel([0, 1])
    )
    team_hist["offrtg_vs_bad_def"] = (
        team_hist.groupby(["team_id", "season"]).apply(
            lambda g: offrtg_bad.loc[g.index].shift(1).expanding(min_periods=3).mean(),
            include_groups=False,
        ).droplevel([0, 1])
    )

    feat_cols = ["offrtg_vs_good_def", "offrtg_vs_bad_def"]
    team_hist = team_hist.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    home_merge = team_hist[["team_id", "game_date"] + feat_cols].copy()
    home_merge.columns = ["home_team_id", "game_date"] + [f"home_{c}" for c in feat_cols]
    home_merge["home_team_id"] = home_merge["home_team_id"].astype(float)
    df["home_team_id"] = df["home_team_id"].astype(float)

    away_merge = team_hist[["team_id", "game_date"] + feat_cols].copy()
    away_merge.columns = ["away_team_id", "game_date"] + [f"away_{c}" for c in feat_cols]
    away_merge["away_team_id"] = away_merge["away_team_id"].astype(float)
    df["away_team_id"] = df["away_team_id"].astype(float)

    df = df.merge(home_merge, on=["home_team_id", "game_date"], how="left")
    df = df.merge(away_merge, on=["away_team_id", "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  15.  Random weighted combinations (de Prado approach)
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

    new_cols = {}
    for hcol in home_cols:
        suffix = hcol[5:]  # strip "home_"
        acol = f"away_{suffix}"
        if acol in df.columns and df[acol].dtype in (np.float64, np.int64, float, int):
            new_cols[f"diff_{suffix}"] = df[hcol] - df[acol]

    df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
    logger.info("[compute_diffs] %d diff cols created", len(new_cols))

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

    if "home_win_entropy" in df.columns:
        log_value_stats(df["home_win_entropy"], "home_win_entropy", logger)
        logger.info("[compute_deprado_features] entropy range=[%.3f, %.3f]",
                    df["home_win_entropy"].min(skipna=True), df["home_win_entropy"].max(skipna=True))
    if "home_cusum_momentum" in df.columns:
        pct_nonzero = (df["home_cusum_momentum"] > 0).mean()
        log_value_stats(df["home_cusum_momentum"], "home_cusum_momentum", logger)
        logger.info("[compute_deprado_features] CUSUM h=0.05  pct series peak>0=%.1f%%", 100 * pct_nonzero)

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
    "diff_colley",
]

QUARTER_MASSEY_FEATURES = [
    f"diff_{design}_{q}"
    for q in ("q1", "q2", "q3", "q4")
    for design in (
        "default_massey", "location_adjusted_massey",
        "crowd_adjusted_massey", "crowd_weighted_massey",
        "experience_adjusted_massey", "travel_adjusted_massey",
        "context_adjusted_massey", "colley",
    )
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

VENUE_ROLLING_FEATURES = [
    "diff_roll10_pts_venue", "diff_roll10_offrtg_venue",
    "diff_roll10_defrtg_venue", "diff_roll10_netrtg_venue",
    "diff_roll20_pts_venue", "diff_roll20_offrtg_venue",
    "diff_roll20_defrtg_venue", "diff_roll20_netrtg_venue",
    "diff_roll10_pace_venue", "diff_roll10_efgpct_venue",
    "diff_roll20_pace_venue", "diff_roll20_efgpct_venue",
]

CONTEXT_FEATURES = [
    "diff_days_rest", "diff_is_back_to_back",
    "away_travel_distance", "away_timezone_shift",
    "crowd_density", "sellout_flag",
    "crew_home_win_rate", "crew_avg_total", "crew_experience",
]

TRAVEL_SEQUENCE_FEATURES = [
    "diff_away_streak",
    "diff_days_span_3", "diff_days_span_5",
    "diff_games_per_week_3", "diff_games_per_week_5",
    "diff_venue_switches_3", "diff_venue_switches_5",
    "diff_travel_distance_3", "diff_travel_distance_5",
    "diff_travel_intensity_3", "diff_travel_intensity_5",
]

ROSTER_FEATURES = [
    "diff_active_players", "diff_dnp_count",
]

SERIES_FEATURES = [
    "series_game_number", "series_lead",
]

ALL_FEATURES = (
    RATING_FEATURES + MASSEY_FEATURES + QUARTER_MASSEY_FEATURES + ROLLING_BOX_FEATURES +
    VENUE_ROLLING_FEATURES + MOMENTUM_FEATURES + CONTEXT_FEATURES +
    TRAVEL_SEQUENCE_FEATURES + ROSTER_FEATURES
)

PLAYOFF_FEATURES = ALL_FEATURES + SERIES_FEATURES


# ─────────────────────────────────────────────────────────────────────────────
#  16.  Sum features (complement to diffs — predicts total-type targets)
# ─────────────────────────────────────────────────────────────────────────────

def compute_sums(games: pd.DataFrame) -> pd.DataFrame:
    """
    For every home_X / away_X pair, compute sum_X = home_X + away_X.
    Diffs predict WHO wins; sums predict HOW MUCH scoring happens.
    """
    df = games.copy()

    home_cols = [c for c in df.columns
                 if c.startswith("home_") and df[c].dtype in (np.float64, np.int64, float, int)]

    new_cols = {}
    for hcol in home_cols:
        suffix = hcol[5:]  # strip "home_"
        acol = f"away_{suffix}"
        if acol in df.columns and df[acol].dtype in (np.float64, np.int64, float, int):
            new_cols[f"sum_{suffix}"] = df[hcol] + df[acol]

    df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
    logger.info("[compute_sums] %d sum cols created", len(new_cols))

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  17.  Pythagorean Expectation & Residual
# ─────────────────────────────────────────────────────────────────────────────

def compute_pythagorean_features(games: pd.DataFrame, exponent: float = 13.91) -> pd.DataFrame:
    """
    Morey Pythagorean expectation: exp_win% = PF^k / (PF^k + PA^k).
    Residual (actual - expected) is a mean-reversion signal.
    Expanding season-scoped with shift(1) for temporal safety.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "home_pts" not in df.columns or "away_pts" not in df.columns:
        return df

    # Build per-team game history
    home = df[["game_date", "season", "home_team_id", "home_pts", "away_pts", "home_wl"]].copy()
    home.columns = ["game_date", "season", "team_id", "pf", "pa", "wl"]

    away = df[["game_date", "season", "away_team_id", "away_pts", "home_pts", "away_wl"]].copy()
    away.columns = ["game_date", "season", "team_id", "pf", "pa", "wl"]

    history = pd.concat([home, away]).sort_values(["team_id", "game_date"]).reset_index(drop=True)
    history["pf"] = pd.to_numeric(history["pf"], errors="coerce")
    history["pa"] = pd.to_numeric(history["pa"], errors="coerce")
    history["_win"] = (history["wl"] == "W").astype(float)

    history["cum_pf"] = (
        history.groupby(["team_id", "season"])["pf"]
        .transform(lambda x: x.shift(1).expanding(min_periods=5).sum())
    )
    history["cum_pa"] = (
        history.groupby(["team_id", "season"])["pa"]
        .transform(lambda x: x.shift(1).expanding(min_periods=5).sum())
    )
    history["actual_winpct"] = (
        history.groupby(["team_id", "season"])["_win"]
        .transform(lambda x: x.shift(1).expanding(min_periods=5).mean())
    )

    pf_k = history["cum_pf"] ** exponent
    pa_k = history["cum_pa"] ** exponent
    denom = pf_k + pa_k
    history["pyth_exp_winpct"] = np.where(denom > 0, pf_k / denom, np.nan)
    history["pyth_residual"] = history["actual_winpct"] - history["pyth_exp_winpct"]

    feat_cols = ["pyth_exp_winpct", "pyth_residual"]
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    logger.info("[compute_pythagorean_features] exponent=%.2f", exponent)
    for side in ("home", "away"):
        for col_suffix in ("pyth_exp_winpct", "pyth_residual"):
            col = f"{side}_{col_suffix}"
            if col in df.columns:
                log_value_stats(df[col], col, logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  18.  Log5 Implied Probability (Ensemble from all rating systems)
# ─────────────────────────────────────────────────────────────────────────────

RATING_SIGMA_MAP = {
    "diff_default_massey": 10.0,
    "diff_colley": 0.15,
    "diff_sag_rating": 10.0,
    "diff_elo_score": 10.0,
    "diff_bpi": 10.0,
    "diff_pure_elo": 10.0,
    "diff_golden_mean": 10.0,
    "diff_predictor": 10.0,
    "diff_location_adjusted_massey": 10.0,
    "diff_context_adjusted_massey": 10.0,
}


def compute_log5_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    Ensemble implied matchup probability from all available rating systems.

    For each rating system with a known sigma, computes:
      P_i = 1 / (1 + 10^(-diff_i / sigma_i))

    The final probability is the mean across all available systems for each game.
    Falls back to Log5 on rolling win% where no ratings are available.
    """
    df = games.copy()

    probs = []
    for col, sigma in RATING_SIGMA_MAP.items():
        if col in df.columns:
            diff = pd.to_numeric(df[col], errors="coerce")
            p = 1.0 / (1.0 + np.power(10.0, -diff / sigma))
            probs.append(p)

    if probs:
        prob_matrix = np.column_stack(probs)
        with np.errstate(all="ignore"):
            df["log5_implied_prob"] = np.nanmean(prob_matrix, axis=1)
        all_nan = np.isnan(prob_matrix).all(axis=1)
        df.loc[all_nan, "log5_implied_prob"] = np.nan
    else:
        df["log5_implied_prob"] = np.nan

    # Fill NaN (early-season games without any ratings) with Log5 on rolling win%
    home_wp = "home_win_pct_20"
    away_wp = "away_win_pct_20"
    if home_wp in df.columns and away_wp in df.columns:
        needs_fallback = df["log5_implied_prob"].isna()
        if needs_fallback.any():
            pA = df.loc[needs_fallback, home_wp].astype(float)
            pB = df.loc[needs_fallback, away_wp].astype(float)
            denom = pA + pB - 2 * pA * pB
            fallback = np.where(denom.abs() > 1e-8, (pA - pA * pB) / denom, 0.5)
            df.loc[needs_fallback, "log5_implied_prob"] = fallback

    n_rating_systems = sum(1 for col in RATING_SIGMA_MAP if col in df.columns)
    logger.info("[compute_log5_features] %d rating systems used", n_rating_systems)
    if "log5_implied_prob" in df.columns:
        log_value_stats(df["log5_implied_prob"], "log5_implied_prob", logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  19.  Four Factors Composite
# ─────────────────────────────────────────────────────────────────────────────

def compute_four_factors_composite(games: pd.DataFrame) -> pd.DataFrame:
    """
    Dean Oliver Four Factors with nonlinear interaction:
      ff_composite = eFG% * (1 - TOV%)  [conditional shooting quality]
      ff_oliver_index = 0.4*eFG% + 0.25*(1-TOV%) + 0.2*ORB% + 0.15*FTRate
    """
    df = games.copy()

    for side in ("home", "away"):
        efg = f"{side}_roll10_efgpct"
        tov = f"{side}_roll10_tovpct"
        orb = f"{side}_roll10_orebpct"
        fta = f"{side}_roll10_fta_rate"

        if efg in df.columns and tov in df.columns:
            efg_v = pd.to_numeric(df[efg], errors="coerce")
            tov_v = pd.to_numeric(df[tov], errors="coerce")
            df[f"{side}_ff_composite"] = efg_v * (1 - tov_v)

            if orb in df.columns and fta in df.columns:
                orb_v = pd.to_numeric(df[orb], errors="coerce")
                fta_v = pd.to_numeric(df[fta], errors="coerce")
                df[f"{side}_ff_oliver_index"] = (
                    0.4 * efg_v + 0.25 * (1 - tov_v) + 0.2 * orb_v + 0.15 * fta_v
                )

    ff_cols = [c for c in df.columns if "ff_composite" in c or "ff_oliver_index" in c]
    for col in ff_cols:
        log_value_stats(df[col], col, logger)
    logger.info("[compute_four_factors_composite] cols added: %s", ff_cols)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  20.  Pace Mismatch
# ─────────────────────────────────────────────────────────────────────────────

def compute_pace_mismatch(games: pd.DataFrame) -> pd.DataFrame:
    """
    Pace mismatch and combined pace (matchup-level, not differenced).
    Extreme mismatch disrupts both teams; combined_pace predicts total.
    """
    df = games.copy()

    home_pace = "home_roll10_pace"
    away_pace = "away_roll10_pace"

    if home_pace in df.columns and away_pace in df.columns:
        hp = pd.to_numeric(df[home_pace], errors="coerce")
        ap = pd.to_numeric(df[away_pace], errors="coerce")
        df["pace_mismatch"] = (hp - ap).abs()
        df["combined_pace"] = (hp + ap) / 2

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  21.  Scoring Distribution Entropy
# ─────────────────────────────────────────────────────────────────────────────

def compute_scoring_entropy(games: pd.DataFrame) -> pd.DataFrame:
    """
    Shannon entropy of scoring source proportions (rolling 10-game).
    Higher entropy = more balanced/diverse scoring = harder to defend.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    scoring_cols = ["pctpts_2pt", "pctpts_3pt", "pctpts_ft", "fbps", "pitp"]
    available = {}
    for side in ("home", "away"):
        side_avail = []
        for c in scoring_cols:
            col = f"{side}_{c}"
            if col in df.columns:
                side_avail.append(col)
        available[side] = side_avail

    if not available["home"] or len(available["home"]) < 3:
        return df

    home_data = df[["game_date", "home_team_id"] + available["home"]].copy()
    home_data.columns = ["game_date", "team_id"] + [c.replace("home_", "") for c in available["home"]]

    away_data = df[["game_date", "away_team_id"] + available["away"]].copy()
    away_data.columns = ["game_date", "team_id"] + [c.replace("away_", "") for c in available["away"]]

    history = pd.concat([home_data, away_data]).sort_values(["team_id", "game_date"]).reset_index(drop=True)
    base_cols = [c.replace("home_", "") for c in available["home"]]

    for c in base_cols:
        history[c] = pd.to_numeric(history[c], errors="coerce")

    for c in base_cols:
        history[f"roll_{c}"] = (
            history.groupby("team_id")[c]
            .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        )

    roll_cols = [f"roll_{c}" for c in base_cols]

    def _shannon_entropy(row):
        props = row[roll_cols].values.astype(float)
        props = props[~np.isnan(props)]
        if len(props) < 2:
            return np.nan
        total = props.sum()
        if total <= 0:
            return np.nan
        props = props / total
        props = props[props > 0]
        return -np.sum(props * np.log2(props))

    history["scoring_entropy"] = history.apply(_shannon_entropy, axis=1)
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date", "scoring_entropy"]].rename(
            columns={"scoring_entropy": f"{side}_scoring_entropy", "team_id": id_col}
        )
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    for side in ("home", "away"):
        col = f"{side}_scoring_entropy"
        if col in df.columns:
            log_value_stats(df[col], col, logger)
    logger.info("[compute_scoring_entropy] entropy over %d source cols", len(available.get("home", [])))

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  22.  ACWR (Acute:Chronic Workload Ratio)
# ─────────────────────────────────────────────────────────────────────────────

def compute_acwr_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    EWMA-based Acute:Chronic Workload Ratio.
    ACWR sweet spot 0.80-1.30; outside = fatigue/detraining risk.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    load_cols = ["pts", "netrtg"]
    available_load = [c for c in load_cols if f"home_{c}" in df.columns]

    if not available_load:
        return df

    home_data = df[["game_date", "home_team_id"] + [f"home_{c}" for c in available_load]].copy()
    home_data.columns = ["game_date", "team_id"] + available_load

    away_data = df[["game_date", "away_team_id"] + [f"away_{c}" for c in available_load]].copy()
    away_data.columns = ["game_date", "team_id"] + available_load

    history = pd.concat([home_data, away_data]).sort_values(["team_id", "game_date"]).reset_index(drop=True)

    for c in available_load:
        history[c] = pd.to_numeric(history[c], errors="coerce")

    # EWMA per team (shift(1) for temporal safety)
    # Half-life = ln(2) / alpha. Acute: 4 games, Chronic: 10 games.
    alpha_acute = 0.159
    alpha_chronic = 0.069

    feat_cols = []
    for c in available_load:
        shifted = history.groupby("team_id")[c].shift(1)

        history[f"acute_{c}"] = shifted.ewm(alpha=alpha_acute, min_periods=3).mean()
        history[f"chronic_{c}"] = shifted.ewm(alpha=alpha_chronic, min_periods=8).mean()

        history[f"acwr_{c}"] = np.where(
            history[f"chronic_{c}"].abs() > 1e-6,
            history[f"acute_{c}"] / history[f"chronic_{c}"],
            np.nan
        )
        feat_cols.append(f"acwr_{c}")

    acwr_vals = history[[f"acwr_{c}" for c in available_load]].values
    history["acwr_risk"] = np.where(
        np.isnan(acwr_vals).all(axis=1), np.nan,
        ((np.nanmin(acwr_vals, axis=1) < 0.80) | (np.nanmax(acwr_vals, axis=1) > 1.30)).astype(float)
    )
    feat_cols.append("acwr_risk")

    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    acwr_risk_cols = [c for c in df.columns if "acwr_risk" in c]
    for col in acwr_risk_cols:
        pct_risk = df[col].mean()
        logger.info("[compute_acwr_features] %s: %.1f%% games in risk zone (ACWR outside 0.80-1.30)",
                    col, 100 * pct_risk)
    if "home_acwr_pts" in df.columns:
        log_value_stats(df["home_acwr_pts"], "home_acwr_pts", logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  23.  Directional Travel
# ─────────────────────────────────────────────────────────────────────────────

def compute_directional_travel(games: pd.DataFrame, arenas: pd.DataFrame,
                               team_map: pd.DataFrame = None) -> pd.DataFrame:
    """
    Eastward travel is ~50% more disruptive than westward (Leota et al. 2022).
    Computes directional fatigue = east_hours * 1.5 + west_hours * 1.0.
    """
    df = games.copy()

    if arenas is None or arenas.empty or "lon" not in arenas.columns:
        return df

    team_name_to_lon = arenas.drop_duplicates("team").set_index("team")["lon"].to_dict()

    abbr_to_lon = {}
    if team_map is not None and not team_map.empty:
        abbr_name = team_map.drop_duplicates("TEAM_ABBREVIATION").set_index("TEAM_ABBREVIATION")["TEAM_NAME"].to_dict()
        for abbr, name in abbr_name.items():
            if name in team_name_to_lon:
                abbr_to_lon[abbr] = team_name_to_lon[name]

    if not abbr_to_lon:
        return df

    home_lon = df["home_team_abbr"].map(abbr_to_lon) if "home_team_abbr" in df.columns else None
    away_lon = df["away_team_abbr"].map(abbr_to_lon) if "away_team_abbr" in df.columns else None

    if home_lon is None or away_lon is None:
        return df
    if home_lon.notna().sum() == 0 or away_lon.notna().sum() == 0:
        return df

    lon_shift = home_lon - away_lon
    east_hours = np.maximum(0, lon_shift / 15.0)
    west_hours = np.maximum(0, -lon_shift / 15.0)

    df["away_eastward_hours"] = east_hours
    df["away_directional_fatigue"] = east_hours * 1.5 + west_hours * 1.0

    coverage = df["away_directional_fatigue"].notna().mean()
    logger.info("[compute_directional_travel] coverage=%.1f%%", 100 * coverage)
    log_value_stats(df["away_directional_fatigue"], "away_directional_fatigue_hours", logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  24.  Quarter Rolling Stats
# ─────────────────────────────────────────────────────────────────────────────

def compute_quarter_rolling_features(games: pd.DataFrame,
                                     quarter_scores: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling 10-game mean of per-quarter scoring. Critical for half targets.
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if quarter_scores is None or quarter_scores.empty:
        return df

    qs = quarter_scores.copy()
    col_map = {c: c.lower() for c in qs.columns}
    qs = qs.rename(columns=col_map)

    if "game_id" not in qs.columns or "team_id" not in qs.columns:
        return df
    if "period_label" not in qs.columns or "period_score" not in qs.columns:
        return df

    qs["team_id"] = qs["team_id"].astype(int)
    qs["period_score"] = pd.to_numeric(qs["period_score"], errors="coerce")

    reg_quarters = qs[qs["period_label"].isin(["Q1", "Q2", "Q3", "Q4", "q1", "q2", "q3", "q4"])]
    reg_quarters = reg_quarters.copy()
    reg_quarters["period_label"] = reg_quarters["period_label"].str.lower()

    pivoted = reg_quarters.pivot_table(
        index=["game_id", "team_id"],
        columns="period_label",
        values="period_score",
        aggfunc="first",
    ).reset_index()
    pivoted.columns.name = None

    gid_col = "game_id" if "game_id" in df.columns else "home_game_id"
    if gid_col not in df.columns:
        return df
    game_dates = df[[gid_col, "game_date"]].drop_duplicates(gid_col)
    game_dates = game_dates.rename(columns={gid_col: "game_id"})
    game_dates["game_id"] = pd.to_numeric(game_dates["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    if "game_id" in pivoted.columns:
        pivoted["game_id"] = pivoted["game_id"].astype(str).str.zfill(10)
        pivoted = pivoted.merge(game_dates, on="game_id", how="left")
    else:
        return df

    pivoted["team_id"] = pd.to_numeric(pivoted["team_id"], errors="coerce")
    pivoted = pivoted.dropna(subset=["game_date", "team_id"])
    pivoted = pivoted.sort_values(["team_id", "game_date"]).reset_index(drop=True)

    quarters = ["q1", "q2", "q3", "q4"]
    available_q = [q for q in quarters if q in pivoted.columns]

    if len(available_q) < 4:
        return df

    feat_cols = []
    for q in available_q:
        col_name = f"roll10_{q}"
        pivoted[col_name] = (
            pivoted.groupby("team_id")[q]
            .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        )
        feat_cols.append(col_name)

    pivoted["roll10_h1_pts"] = pivoted["roll10_q1"] + pivoted["roll10_q2"]
    pivoted["roll10_h2_pts"] = pivoted["roll10_q3"] + pivoted["roll10_q4"]
    feat_cols.extend(["roll10_h1_pts", "roll10_h2_pts"])

    pivoted = pivoted.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = pivoted[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        merge_df[id_col] = merge_df[id_col].astype(float)
        df[id_col] = df[id_col].astype(float)
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  25.  Blowout & Close Game Rates
# ─────────────────────────────────────────────────────────────────────────────

def compute_blowout_close_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    Fraction of recent games that were blowouts (|margin|>15) or close (|margin|<=5).
    """
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "home_pts" not in df.columns or "away_pts" not in df.columns:
        return df

    home = df[["game_date", "home_team_id", "home_pts", "away_pts"]].copy()
    home["margin"] = pd.to_numeric(home["home_pts"], errors="coerce") - pd.to_numeric(home["away_pts"], errors="coerce")
    home = home.rename(columns={"home_team_id": "team_id"})[["game_date", "team_id", "margin"]]

    away = df[["game_date", "away_team_id", "away_pts", "home_pts"]].copy()
    away["margin"] = pd.to_numeric(away["away_pts"], errors="coerce") - pd.to_numeric(away["home_pts"], errors="coerce")
    away = away.rename(columns={"away_team_id": "team_id"})[["game_date", "team_id", "margin"]]

    history = pd.concat([home, away]).sort_values(["team_id", "game_date"]).reset_index(drop=True)

    history["is_blowout"] = (history["margin"].abs() > 15).astype(float)
    history["is_close"] = (history["margin"].abs() <= 5).astype(float)

    history["blowout_rate_10"] = (
        history.groupby("team_id")["is_blowout"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
    )
    history["close_game_rate_10"] = (
        history.groupby("team_id")["is_close"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
    )

    feat_cols = ["blowout_rate_10", "close_game_rate_10"]
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  26.  Overtime History
# ─────────────────────────────────────────────────────────────────────────────

def compute_overtime_history(games: pd.DataFrame,
                            quarter_scores: pd.DataFrame) -> pd.DataFrame:
    """OT frequency and win rate per team."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if quarter_scores is None or quarter_scores.empty:
        return df

    qs = quarter_scores.copy()
    col_map = {c: c.lower() for c in qs.columns}
    qs = qs.rename(columns=col_map)

    if "game_id" not in qs.columns or "period_label" not in qs.columns:
        return df

    ot_games = qs[qs["period_label"].str.upper().str.contains("OT", na=False)]["game_id"].unique()
    ot_set = set(ot_games)

    if "home_pts" not in df.columns or "away_pts" not in df.columns:
        return df

    gid_col = "game_id" if "game_id" in df.columns else "home_game_id"
    if gid_col not in df.columns:
        return df

    home = df[["game_date", gid_col, "home_team_id", "home_pts", "away_pts"]].copy()
    home = home.rename(columns={gid_col: "game_id"})
    home["game_id"] = pd.to_numeric(home["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    home["went_to_ot"] = home["game_id"].isin(ot_set).astype(float)
    home["won"] = (pd.to_numeric(home["home_pts"], errors="coerce") >
                   pd.to_numeric(home["away_pts"], errors="coerce")).astype(float)
    home = home.rename(columns={"home_team_id": "team_id"})

    away = df[["game_date", gid_col, "away_team_id", "away_pts", "home_pts"]].copy()
    away = away.rename(columns={gid_col: "game_id"})
    away["game_id"] = pd.to_numeric(away["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    away["went_to_ot"] = away["game_id"].isin(ot_set).astype(float)
    away["won"] = (pd.to_numeric(away["away_pts"], errors="coerce") >
                   pd.to_numeric(away["home_pts"], errors="coerce")).astype(float)
    away = away.rename(columns={"away_team_id": "team_id"})

    history = pd.concat([home[["game_date", "team_id", "went_to_ot", "won"]],
                         away[["game_date", "team_id", "went_to_ot", "won"]]
                         ]).sort_values(["team_id", "game_date"]).reset_index(drop=True)

    history["ot_frequency"] = (
        history.groupby("team_id")["went_to_ot"]
        .transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    )

    history["ot_won"] = history["won"] * history["went_to_ot"]
    history["ot_win_rate"] = (
        history.groupby("team_id").apply(
            lambda g: g["ot_won"].shift(1).expanding().sum() /
                      g["went_to_ot"].shift(1).expanding().sum().replace(0, np.nan),
            include_groups=False,
        ).droplevel(0)
    )

    feat_cols = ["ot_frequency", "ot_win_rate"]
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    for side in ("home", "away"):
        for sfx in ("blowout_rate_10", "close_game_rate_10"):
            col = f"{side}_{sfx}"
            if col in df.columns:
                log_value_stats(df[col], col, logger)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  27.  Margin Autocorrelation
# ─────────────────────────────────────────────────────────────────────────────

def compute_margin_autocorrelation(games: pd.DataFrame) -> pd.DataFrame:
    """Lag-1 autocorrelation of margin over rolling 20-game window."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "home_pts" not in df.columns:
        return df

    home = df[["game_date", "home_team_id", "home_pts", "away_pts"]].copy()
    home["margin"] = pd.to_numeric(home["home_pts"], errors="coerce") - pd.to_numeric(home["away_pts"], errors="coerce")
    home = home.rename(columns={"home_team_id": "team_id"})[["game_date", "team_id", "margin"]]

    away = df[["game_date", "away_team_id", "away_pts", "home_pts"]].copy()
    away["margin"] = pd.to_numeric(away["away_pts"], errors="coerce") - pd.to_numeric(away["home_pts"], errors="coerce")
    away = away.rename(columns={"away_team_id": "team_id"})[["game_date", "team_id", "margin"]]

    history = pd.concat([home, away]).sort_values(["team_id", "game_date"]).reset_index(drop=True)

    def _rolling_autocorr(x):
        shifted = x.shift(1)
        return shifted.rolling(20, min_periods=10).apply(
            lambda w: pd.Series(w).autocorr(lag=1) if len(w) >= 10 else np.nan,
            raw=False
        )

    history["margin_autocorr"] = history.groupby("team_id")["margin"].transform(_rolling_autocorr)

    feat_cols = ["margin_autocorr"]
    history = history.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = history[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    if "home_margin_autocorr" in df.columns:
        log_value_stats(df["home_margin_autocorr"], "home_margin_autocorr", logger)
        pct_positive = (df["home_margin_autocorr"] > 0).mean()
        logger.info("[compute_margin_autocorrelation] pct positive autocorr (trending)=%.1f%%",
                    100 * pct_positive)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  28.  Defensive Consistency
# ─────────────────────────────────────────────────────────────────────────────

def compute_defensive_consistency(games: pd.DataFrame) -> pd.DataFrame:
    """Coefficient of variation of DefRtg: mean/std."""
    df = games.copy()

    for side in ("home", "away"):
        mean_col = f"{side}_roll10_defrtg"
        std_col = f"{side}_roll10_defrtg_std"

        if mean_col in df.columns and std_col in df.columns:
            mean_v = pd.to_numeric(df[mean_col], errors="coerce")
            std_v = pd.to_numeric(df[std_col], errors="coerce")
            df[f"{side}_def_consistency"] = np.where(
                std_v > 0, mean_v / std_v, np.nan
            )

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  29.  Scoring Concentration (Simpson/Herfindahl)
# ─────────────────────────────────────────────────────────────────────────────

def compute_scoring_concentration(games: pd.DataFrame) -> pd.DataFrame:
    """Simpson diversity: 1 - sum(p_i^2)."""
    df = games.copy()

    scoring_cols = ["pctpts_2pt", "pctpts_3pt", "pctpts_ft"]

    for side in ("home", "away"):
        props = []
        for c in scoring_cols:
            col = f"{side}_roll10_{c}" if f"{side}_roll10_{c}" in df.columns else f"{side}_{c}"
            if col in df.columns:
                props.append(pd.to_numeric(df[col], errors="coerce"))

        if len(props) >= 3:
            prop_arr = np.column_stack(props)
            row_sums = np.nansum(prop_arr, axis=1, keepdims=True)
            row_sums = np.where(row_sums > 0, row_sums, np.nan)
            normalized = prop_arr / row_sums
            hhi = np.nansum(normalized ** 2, axis=1)
            df[f"{side}_scoring_gini"] = 1 - hhi

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  30.  Series-Specific Features (playoffs only)
# ─────────────────────────────────────────────────────────────────────────────

def compute_series_features(games: pd.DataFrame) -> pd.DataFrame:
    """Playoff series-specific features: higher seed, rest between series games."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if "season_type" not in df.columns:
        return df

    playoff_mask = df["season_type"].str.contains("Playoff", case=False, na=False)

    if playoff_mask.sum() == 0:
        return df

    if "series_game_number" in df.columns:
        df["_pair"] = (df[["home_team_id", "away_team_id"]].apply(
            lambda r: "_".join(sorted([str(r.iloc[0]), str(r.iloc[1])])), axis=1
        ))

        playoff_df = df[playoff_mask].copy()
        if not playoff_df.empty:
            game1_home = playoff_df.sort_values("game_date").drop_duplicates("_pair", keep="first")
            pair_to_higher_seed = dict(zip(game1_home["_pair"], game1_home["home_team_id"]))

            df["higher_seed_flag"] = np.where(
                playoff_mask,
                df.apply(lambda r: 1.0 if str(r.get("home_team_id")) == str(pair_to_higher_seed.get(r.get("_pair"), ""))
                         else -1.0, axis=1),
                np.nan
            )
        df = df.drop(columns=["_pair"], errors="ignore")

    if playoff_mask.any():
        playoff_idx = df[playoff_mask].index
        df["_pair_key"] = df[["home_team_id", "away_team_id"]].apply(
            lambda r: "_".join(sorted([str(r.iloc[0]), str(r.iloc[1])])), axis=1
        )
        df["game_date_dt"] = pd.to_datetime(df["game_date"])
        df["series_rest_days"] = np.nan

        for pair, grp in df.loc[playoff_idx].groupby("_pair_key"):
            grp_sorted = grp.sort_values("game_date_dt")
            rest = grp_sorted["game_date_dt"].diff().dt.days
            df.loc[grp_sorted.index, "series_rest_days"] = rest.values

        df = df.drop(columns=["_pair_key", "game_date_dt"], errors="ignore")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  31.  Team Hustle Aggregates
# ─────────────────────────────────────────────────────────────────────────────

def compute_hustle_features(games: pd.DataFrame,
                            hustle: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-player hustle stats to team-game level, then rolling 10-game."""
    df = games.copy().sort_values("game_date").reset_index(drop=True)

    if hustle is None or hustle.empty:
        return df

    h = hustle.copy()
    col_map = {c: c.lower() for c in h.columns}
    h = h.rename(columns=col_map)

    if "gameid" in h.columns:
        h = h.rename(columns={"gameid": "game_id"})
    if "teamid" in h.columns:
        h = h.rename(columns={"teamid": "team_id"})

    if "game_id" not in h.columns:
        return df

    hustle_stats = ["deflections", "contestedshots", "looseballsrecoveredtotal", "screenassists"]
    available_stats = [s for s in hustle_stats if s in h.columns]

    if not available_stats:
        return df

    for c in available_stats:
        h[c] = pd.to_numeric(h[c], errors="coerce")

    h["game_id"] = h["game_id"].astype(str)

    gid_col = "game_id" if "game_id" in df.columns else "home_game_id"
    if gid_col not in df.columns or "side" not in h.columns:
        return df

    game_team_lookup = pd.concat([
        df[[gid_col, "home_team_id"]].rename(columns={gid_col: "game_id", "home_team_id": "team_id"}).assign(side="homeTeam"),
        df[[gid_col, "away_team_id"]].rename(columns={gid_col: "game_id", "away_team_id": "team_id"}).assign(side="awayTeam"),
    ])
    game_team_lookup["game_id"] = pd.to_numeric(game_team_lookup["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    h["game_id"] = h["game_id"].astype(str).str.zfill(10)

    h = h.drop(columns=["team_id"], errors="ignore")
    h = h.merge(game_team_lookup, on=["game_id", "side"], how="inner")

    if h.empty or "team_id" not in h.columns:
        return df

    team_game = h.groupby(["game_id", "team_id"])[available_stats].sum().reset_index()

    gid_col = "game_id" if "game_id" in df.columns else "home_game_id"
    if gid_col not in df.columns:
        return df
    game_dates = df[[gid_col, "game_date"]].drop_duplicates(gid_col)
    game_dates = game_dates.rename(columns={gid_col: "game_id"})
    game_dates["game_id"] = pd.to_numeric(game_dates["game_id"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    team_game["game_id"] = team_game["game_id"].astype(str).str.zfill(10)
    team_game = team_game.merge(game_dates, on="game_id", how="left")
    team_game = team_game.dropna(subset=["game_date"])
    team_game["game_date"] = pd.to_datetime(team_game["game_date"])
    team_game["team_id"] = team_game["team_id"].astype(float).astype(int)
    team_game = team_game.sort_values(["team_id", "game_date"]).reset_index(drop=True)

    feat_cols = []
    for stat in available_stats:
        col_name = f"{stat}_10"
        team_game[col_name] = (
            team_game.groupby("team_id")[stat]
            .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        )
        feat_cols.append(col_name)

    team_game = team_game.drop_duplicates(subset=["team_id", "game_date"], keep="last")

    for side, id_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        merge_df = team_game[["team_id", "game_date"] + feat_cols].rename(
            columns={c: f"{side}_{c}" for c in feat_cols}
        ).rename(columns={"team_id": id_col})
        merge_df[id_col] = merge_df[id_col].astype(float)
        df[id_col] = df[id_col].astype(float)
        df = df.merge(merge_df, on=[id_col, "game_date"], how="left")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  32.  Half Scoring Rate
# ─────────────────────────────────────────────────────────────────────────────

def compute_half_scoring_rate(games: pd.DataFrame) -> pd.DataFrame:
    """Ratio of half scoring to total: captures teams that start/finish strong."""
    df = games.copy()

    for side in ("home", "away"):
        h1 = f"{side}_roll10_h1_pts"
        h2 = f"{side}_roll10_h2_pts"
        total = f"{side}_roll10_pts"

        if h1 in df.columns and total in df.columns:
            h1_v = pd.to_numeric(df[h1], errors="coerce")
            total_v = pd.to_numeric(df[total], errors="coerce")
            df[f"{side}_h1_scoring_rate"] = np.where(
                total_v > 0, h1_v / total_v, np.nan
            )

        if h2 in df.columns and total in df.columns:
            h2_v = pd.to_numeric(df[h2], errors="coerce")
            total_v = pd.to_numeric(df[total], errors="coerce")
            df[f"{side}_h2_scoring_rate"] = np.where(
                total_v > 0, h2_v / total_v, np.nan
            )

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  33.  Random Symbolic Features
# ─────────────────────────────────────────────────────────────────────────────

def _safe_divide(a, b):
    # Treat near-zero denominators as NaN rather than producing huge values
    threshold = 1e-3
    result = np.where(np.abs(b) >= threshold, a / b, np.nan)
    return result.astype(np.float64)


def _safe_log1p(x):
    return np.log1p(np.abs(x)) * np.sign(x)


def _safe_sqrt(x):
    return np.sqrt(np.abs(x)) * np.sign(x)


UNARY_OPS = [
    ("abs", np.abs),
    ("sq", lambda x: x ** 2),
    ("log1p", _safe_log1p),
    ("sqrt", _safe_sqrt),
]

BINARY_OPS = [
    ("mul", lambda a, b: a * b),
    ("div", _safe_divide),
    ("add", lambda a, b: a + b),
    ("sub", lambda a, b: a - b),
]

TERNARY_OPS = [
    ("mul_add", lambda a, b, c: a * b + c),
    ("triple", lambda a, b, c: a * b * c),
    ("div_sum", lambda a, b, c: _safe_divide(a, b + c)),
]


SYMBOLIC_POOL_PREFIXES = (
    "diff_roll", "diff_bpi", "diff_bpioffense", "diff_bpidefense",
    "diff_playoffbpi", "diff_offtalent", "diff_deftalent",
    "diff_sag_rating", "diff_elo_score", "diff_predictor",
    "diff_pure_elo", "diff_golden_mean", "diff_recent",
    "diff_default_massey", "diff_location_adjusted_massey",
    "diff_crowd_adjusted_massey", "diff_crowd_weighted_massey",
    "diff_experience_adjusted_massey", "diff_travel_adjusted_massey",
    "diff_context_adjusted_massey", "diff_colley",
    "diff_win_streak", "diff_win_pct", "diff_win_entropy",
    "diff_margin_last", "diff_cusum",
    "diff_days_rest", "diff_is_back_to_back",
    "diff_travel_distance", "diff_timezone_shift",
    "diff_away_streak", "diff_days_span_", "diff_games_per_week_",
    "diff_venue_switches_", "diff_travel_intensity_",
    "diff_active_players", "diff_dnp_count",
    "diff_h2h_", "diff_offrtg_vs_good_def", "diff_offrtg_vs_bad_def",
    "diff_off_default_massey", "diff_off_location_adjusted_massey",
    "diff_def_default_massey", "diff_def_location_adjusted_massey",
    "diff_matchup_advantage", "diff_whitlock", "diff_wolfe", "diff_wobus",
    "diff_pyth_", "diff_ff_", "diff_scoring_entropy", "diff_scoring_gini",
    "diff_acwr_", "diff_roll10_q", "diff_roll10_h1_", "diff_roll10_h2_",
    "diff_blowout_rate", "diff_close_game_rate", "diff_ot_",
    "diff_margin_autocorr", "diff_def_consistency",
    "diff_deflections_", "diff_contestedshots_",
    "diff_looseballsrecoveredtotal_", "diff_screenassists_",
    "diff_h1_scoring_rate", "diff_h2_scoring_rate",
    "sum_roll", "sum_bpi", "sum_sag_rating", "sum_elo_score",
    "sum_predictor", "sum_pure_elo", "sum_golden_mean", "sum_recent",
    "sum_default_massey", "sum_location_adjusted_massey",
    "sum_crowd_adjusted_massey", "sum_crowd_weighted_massey",
    "sum_experience_adjusted_massey", "sum_travel_adjusted_massey",
    "sum_context_adjusted_massey", "sum_colley",
    "sum_win_streak", "sum_win_pct", "sum_days_rest",
    "sum_pyth_", "sum_ff_", "sum_scoring_entropy", "sum_scoring_gini",
    "sum_acwr_", "sum_roll10_q", "sum_roll10_h1_", "sum_roll10_h2_",
    "sum_blowout_rate", "sum_close_game_rate", "sum_ot_",
    "sum_def_consistency", "sum_deflections_", "sum_contestedshots_",
    "sum_h1_scoring_rate", "sum_h2_scoring_rate",
)


def generate_symbolic_features(games: pd.DataFrame,
                               n_features: int | None = None,
                               seed: int = 42) -> tuple[pd.DataFrame, list[dict]]:
    """
    Generate random symbolic features from verified pregame diff_* + sum_* pool.
    Returns (dataframe_with_features, recipes_list).
    """
    import os
    df = games.copy()

    if n_features is None:
        n_features = int(os.environ.get("N_SYMBOLIC_FEATURES", "500"))

    # Build pool: only verified pregame diff_* and sum_* columns
    pool_cols = [c for c in df.columns
                 if c.startswith(SYMBOLIC_POOL_PREFIXES)
                 and df[c].dtype in (np.float64, np.int64, float, int)]

    if len(pool_cols) < 3:
        logger.warning("[generate_symbolic_features] pool too small (%d cols) — returning empty", len(pool_cols))
        return df, []

    logger.info("[generate_symbolic_features] pool=%d cols  n_features=%d  seed=%d",
                len(pool_cols), n_features, seed)
    rng = np.random.default_rng(seed)
    recipes = []

    pool_data = {c: df[c].values.astype(np.float64) for c in pool_cols}
    n_pool = len(pool_cols)

    for i in range(n_features):
        arity = 2 if rng.random() < 0.6 else 3

        col_indices = rng.choice(n_pool, size=arity, replace=False)
        cols = [pool_cols[j] for j in col_indices]
        arrays = [pool_data[c] for c in cols]

        unary_name = None
        if rng.random() < 0.3:
            u_idx = rng.integers(len(UNARY_OPS))
            unary_name, unary_fn = UNARY_OPS[u_idx]
            arrays[0] = unary_fn(arrays[0])

        if arity == 2:
            op_idx = rng.integers(len(BINARY_OPS))
            op_name, op_fn = BINARY_OPS[op_idx]
            result = op_fn(arrays[0], arrays[1])
        else:
            op_idx = rng.integers(len(TERNARY_OPS))
            op_name, op_fn = TERNARY_OPS[op_idx]
            result = op_fn(arrays[0], arrays[1], arrays[2])

        result = np.clip(result, -1e6, 1e6)
        result = np.where(np.isfinite(result), result, np.nan)

        col_name = f"sf_{i:03d}"
        df[col_name] = result

        recipes.append({
            "name": col_name,
            "columns": cols,
            "operation": op_name,
            "unary": unary_name,
            "arity": arity,
        })

    sf_cols = [c for c in df.columns if c.startswith("sf_")]
    logger.info("[generate_symbolic_features] %d symbolic features generated", len(sf_cols))
    return df, recipes
