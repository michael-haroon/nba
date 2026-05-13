"""
Massey rating feature engineering for NBA game data.

The core system is X beta = y, where y is home_score - away_score.
Rows in X are intentionally sparse: +1 for the home team, -1 for the
away team, plus optional context columns such as home advantage, crowd
density, roster experience, and travel.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype


try:  # Optional: the direct normal-equation path below does not require scipy.
    from scipy import sparse as sp  # type: ignore
except Exception:  # pragma: no cover - exercised when scipy is unavailable.
    sp = None


REQUIRED_GAME_COLUMNS = {
    "season",
    "game_id",
    "game_date",
    "home_team_id",
    "away_team_id",
    "home_score",
    "away_score",
}


@dataclass(frozen=True)
class MasseyDesign:
    """A single Massey permutation."""

    name: str
    include_home_advantage: bool = False
    factor_columns: tuple[str, ...] = ()
    weight_column: str | None = None
    min_factor_coverage: float = 0.75
    neutral_home_value: float = 0.0

    @property
    def rating_column(self) -> str:
        return self.name

    @property
    def rank_column(self) -> str:
        return f"{self.name}_rank"


@dataclass
class MasseyFit:
    """Solved ratings plus matrix diagnostics for one design/season."""

    design: MasseyDesign
    season: int | str | None
    as_of_date: pd.Timestamp | None
    teams: list[int]
    columns: list[str]
    ratings: pd.DataFrame
    coefficients: dict[str, float]
    normal_matrix: np.ndarray
    target_vector: np.ndarray
    constrained_matrix: np.ndarray
    constrained_target: np.ndarray
    x_preview: pd.DataFrame
    y_preview: pd.Series
    components: list[list[int]]
    dropped_columns: list[str] = field(default_factory=list)
    solver: str = "solve"
    rank: int = 0
    warnings: list[str] = field(default_factory=list)


DEFAULT_MASSEY_DESIGNS: tuple[MasseyDesign, ...] = (
    MasseyDesign("default_massey"),
    MasseyDesign("location_adjusted_massey", include_home_advantage=True),
    MasseyDesign(
        "crowd_adjusted_massey",
        include_home_advantage=True,
        factor_columns=("crowd_density",),
    ),
    MasseyDesign(
        "crowd_weighted_massey",
        include_home_advantage=True,
        weight_column="crowd_weight",
    ),
    MasseyDesign(
        "experience_adjusted_massey",
        include_home_advantage=True,
        factor_columns=("visitor_inexperience",),
    ),
    MasseyDesign(
        "travel_adjusted_massey",
        include_home_advantage=True,
        factor_columns=("log_travel_distance", "travel_direction"),
    ),
    MasseyDesign(
        "context_adjusted_massey",
        include_home_advantage=True,
        factor_columns=(
            "crowd_density",
            "visitor_inexperience",
            "log_travel_distance",
            "travel_direction",
        ),
        weight_column="crowd_weight",
    ),
)


def _as_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y", "neutral"})
    )


def _require_game_columns(games: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_GAME_COLUMNS - set(games.columns))
    if missing:
        raise ValueError(f"Missing required game columns: {missing}")


def normalize_massey_games(games: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and type-normalize completed NBA game rows.

    Required columns are:
    season, game_id, game_date, home_team_id, away_team_id, home_score, away_score.
    Optional columns can include attendance, capacity, is_neutral,
    away_avg_experience, travel_distance_miles, and travel_direction.
    """

    _require_game_columns(games)
    df = games.copy()
    df["season"] = df["season"]
    df["game_id"] = df["game_id"].astype(str)
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")

    for col in ("home_team_id", "away_team_id"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("home_score", "away_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=[
            "game_date",
            "home_team_id",
            "away_team_id",
            "home_score",
            "away_score",
        ]
    ).copy()
    df["home_team_id"] = df["home_team_id"].astype(int)
    df["away_team_id"] = df["away_team_id"].astype(int)
    df = df[df["home_team_id"] != df["away_team_id"]]

    for col in (
        "attendance",
        "capacity",
        "away_avg_experience",
        "travel_distance_miles",
    ):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "is_neutral" not in df.columns:
        df["is_neutral"] = False
    else:
        df["is_neutral"] = _as_bool_series(df["is_neutral"])

    return df.sort_values(["season", "game_date", "game_id"]).reset_index(drop=True)


def prepare_massey_context(games: pd.DataFrame) -> pd.DataFrame:
    """
    Add reusable context factors for the Massey design matrix when raw
    source fields are available.
    """

    df = normalize_massey_games(games)

    if "crowd_density" not in df.columns:
        if {"attendance", "capacity"}.issubset(df.columns):
            density = df["attendance"] / df["capacity"].replace(0, np.nan)
            df["crowd_density"] = density.clip(lower=0.0, upper=1.5)

    if "crowd_weight" not in df.columns and "crowd_density" in df.columns:
        density = pd.to_numeric(df["crowd_density"], errors="coerce")
        fill = density.median(skipna=True)
        if pd.isna(fill):
            fill = 0.0
        df["crowd_weight"] = 1.0 + density.fillna(fill).clip(lower=0.0)

    if "visitor_inexperience" not in df.columns:
        if "away_avg_experience" in df.columns:
            exp = pd.to_numeric(df["away_avg_experience"], errors="coerce")
            df["visitor_inexperience"] = np.where(exp > 0, 1.0 / exp, np.nan)

    if "log_travel_distance" not in df.columns:
        if "travel_distance_miles" in df.columns:
            dist = pd.to_numeric(df["travel_distance_miles"], errors="coerce")
            df["log_travel_distance"] = np.log1p(dist.clip(lower=0.0))

    if "travel_direction" in df.columns:
        direction = df["travel_direction"]
        if not is_numeric_dtype(direction):
            mapping = {
                "east": 1.0,
                "eastward": 1.0,
                "e": 1.0,
                "west": -1.0,
                "westward": -1.0,
                "w": -1.0,
                "same": 0.0,
                "neutral": 0.0,
                "north": 0.0,
                "south": 0.0,
                "n": 0.0,
                "s": 0.0,
            }
            df["travel_direction"] = (
                direction.astype(str).str.strip().str.lower().map(mapping)
            )
        else:
            df["travel_direction"] = pd.to_numeric(direction, errors="coerce")

    return df


def _team_components(games: pd.DataFrame, teams: list[int]) -> list[list[int]]:
    graph: dict[int, set[int]] = {team: set() for team in teams}
    for row in games[["home_team_id", "away_team_id"]].itertuples(index=False):
        home = int(row.home_team_id)
        away = int(row.away_team_id)
        graph.setdefault(home, set()).add(away)
        graph.setdefault(away, set()).add(home)

    seen: set[int] = set()
    components: list[list[int]] = []
    for team in teams:
        if team in seen:
            continue
        queue: deque[int] = deque([team])
        seen.add(team)
        comp: list[int] = []
        while queue:
            current = queue.popleft()
            comp.append(current)
            for neighbor in graph.get(current, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(comp))
    return components


def _usable_factor_columns(
    games: pd.DataFrame,
    design: MasseyDesign,
) -> tuple[list[str], list[str], list[str]]:
    usable: list[str] = []
    dropped: list[str] = []
    notes: list[str] = []

    for col in design.factor_columns:
        if col not in games.columns:
            dropped.append(col)
            notes.append(f"{col} unavailable; dropped from {design.name}.")
            continue
        s = pd.to_numeric(games[col], errors="coerce")
        coverage = float(s.notna().mean()) if len(s) else 0.0
        non_na = s.dropna()
        if coverage < design.min_factor_coverage:
            dropped.append(col)
            notes.append(
                f"{col} coverage {coverage:.1%} below "
                f"{design.min_factor_coverage:.0%}; dropped from {design.name}."
            )
            continue
        if non_na.nunique() <= 1:
            dropped.append(col)
            notes.append(f"{col} has no variation; dropped from {design.name}.")
            continue
        usable.append(col)

    return usable, dropped, notes


def _weights_for_design(games: pd.DataFrame, design: MasseyDesign) -> tuple[np.ndarray, list[str]]:
    if design.weight_column is None:
        return np.ones(len(games), dtype=float), []
    if design.weight_column not in games.columns:
        return np.ones(len(games), dtype=float), [
            f"{design.weight_column} unavailable; {design.name} used unweighted rows."
        ]
    weights = pd.to_numeric(games[design.weight_column], errors="coerce")
    fill = weights.median(skipna=True)
    if pd.isna(fill) or fill <= 0:
        fill = 1.0
    weights = weights.fillna(fill).clip(lower=1e-6)
    return weights.to_numpy(dtype=float), []


def _row_entries_for_game(
    game: pd.Series,
    team_to_idx: dict[int, int],
    team_count: int,
    extra_columns: list[str],
    design: MasseyDesign,
) -> dict[int, float]:
    entries: dict[int, float] = {
        team_to_idx[int(game["home_team_id"])]: 1.0,
        team_to_idx[int(game["away_team_id"])]: -1.0,
    }
    offset = team_count
    for j, col in enumerate(extra_columns):
        if col == "home_advantage":
            value = design.neutral_home_value if bool(game.get("is_neutral", False)) else 1.0
        else:
            value = game.get(col, np.nan)
            if pd.isna(value):
                value = 0.0
        if value != 0:
            entries[offset + j] = float(value)
    return entries


def fit_massey(
    games: pd.DataFrame,
    design: MasseyDesign = DEFAULT_MASSEY_DESIGNS[0],
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    preview_rows: int = 8,
) -> MasseyFit:
    """
    Fit one Massey design for one season/snapshot.

    The primary path accumulates X.T @ W @ X and X.T @ W @ y directly from
    row non-zero entries, which keeps memory bounded even when historical
    game counts grow. If scipy is installed, callers can still construct a
    full sparse X externally from the returned preview/column contract, but
    solving this small normal system does not require scipy.
    """

    df = prepare_massey_context(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    if df.empty:
        empty = pd.DataFrame(columns=["season", "team_id", design.rating_column, design.rank_column])
        return MasseyFit(
            design=design,
            season=season,
            as_of_date=snapshot_date,
            teams=[],
            columns=[],
            ratings=empty,
            coefficients={},
            normal_matrix=np.zeros((0, 0)),
            target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)),
            constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(),
            y_preview=pd.Series(dtype=float, name="home_margin"),
            components=[],
            solver="empty",
            warnings=["No completed games available for this Massey fit."],
        )

    teams = sorted(
        set(df["home_team_id"].astype(int).tolist())
        | set(df["away_team_id"].astype(int).tolist())
    )
    team_to_idx = {team: idx for idx, team in enumerate(teams)}

    usable_factors, dropped, notes = _usable_factor_columns(df, design)
    extra_columns = []
    if design.include_home_advantage:
        extra_columns.append("home_advantage")
    extra_columns.extend(usable_factors)

    columns = [f"team_{team}" for team in teams] + extra_columns
    n_cols = len(columns)
    normal = np.zeros((n_cols, n_cols), dtype=float)
    target = np.zeros(n_cols, dtype=float)
    weights, weight_notes = _weights_for_design(df, design)
    notes.extend(weight_notes)
    preview_records: list[dict[str, float]] = []
    preview_y: list[float] = []

    for pos, (_, game) in enumerate(df.iterrows()):
        entries = _row_entries_for_game(game, team_to_idx, len(teams), extra_columns, design)
        y = float(game["home_score"] - game["away_score"])
        w = float(weights[pos])
        for i, vi in entries.items():
            target[i] += w * vi * y
            for j, vj in entries.items():
                normal[i, j] += w * vi * vj
        if len(preview_records) < preview_rows:
            record = {col: 0.0 for col in columns}
            for i, value in entries.items():
                record[columns[i]] = value
            preview_records.append(record)
            preview_y.append(y)

    constrained = normal.copy()
    constrained_target = target.copy()
    components = _team_components(df, teams)

    if len(components) > 1:
        notes.append(
            "Schedule graph is disconnected; applied one sum-to-zero constraint "
            "per connected component. Cross-component rating levels are not identified yet."
        )

    for comp in components:
        row_idx = team_to_idx[comp[-1]]
        constrained[row_idx, :] = 0.0
        constrained[row_idx, [team_to_idx[t] for t in comp]] = 1.0
        constrained_target[row_idx] = 0.0

    try:
        beta = np.linalg.solve(constrained, constrained_target)
        solver = "numpy.linalg.solve"
    except np.linalg.LinAlgError:
        beta, *_ = np.linalg.lstsq(constrained, constrained_target, rcond=None)
        solver = "numpy.linalg.lstsq"
        notes.append(
            "Normal equations remained singular after constraints; used least-squares fallback."
        )

    coeffs = {columns[i]: float(beta[i]) for i in range(n_cols)}
    rating_values = beta[: len(teams)]
    ratings = pd.DataFrame(
        {
            "season": season if season is not None else df["season"].iloc[0],
            "team_id": teams,
            design.rating_column: rating_values,
        }
    )
    ratings[design.rank_column] = (
        ratings[design.rating_column]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    return MasseyFit(
        design=design,
        season=season if season is not None else df["season"].iloc[0],
        as_of_date=snapshot_date,
        teams=teams,
        columns=columns,
        ratings=ratings,
        coefficients=coeffs,
        normal_matrix=normal,
        target_vector=target,
        constrained_matrix=constrained,
        constrained_target=constrained_target,
        x_preview=pd.DataFrame(preview_records, columns=columns),
        y_preview=pd.Series(preview_y, name="home_margin"),
        components=components,
        dropped_columns=dropped,
        solver=solver,
        rank=int(np.linalg.matrix_rank(normal)) if n_cols else 0,
        warnings=notes,
    )


def build_massey_team_features(
    games: pd.DataFrame,
    *,
    designs: Iterable[MasseyDesign] = DEFAULT_MASSEY_DESIGNS,
    as_of_date: str | pd.Timestamp | None = None,
    preview_rows: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[int | str, str], MasseyFit]]:
    """
    Build one team-level rating snapshot per (season, team).

    Returns:
      features_df: team ratings/ranks, one row per season/team.
      coefficients_df: extra coefficients such as home advantage.
      fits: diagnostic fit objects keyed by (season, design_name).
    """

    df = prepare_massey_context(games)
    features: list[pd.DataFrame] = []
    coef_rows: list[dict[str, float | int | str | None]] = []
    fits: dict[tuple[int | str, str], MasseyFit] = {}

    for season, season_games in df.groupby("season", sort=True):
        season_features: pd.DataFrame | None = None
        for design in designs:
            fit = fit_massey(
                season_games,
                design,
                season=season,
                as_of_date=as_of_date,
                preview_rows=preview_rows,
            )
            fits[(season, design.name)] = fit
            ratings = fit.ratings.copy()
            if season_features is None:
                season_features = ratings
            else:
                season_features = season_features.merge(
                    ratings,
                    on=["season", "team_id"],
                    how="outer",
                )
            coef_row: dict[str, float | int | str | None] = {
                "season": season,
                "as_of_date": str(fit.as_of_date.date()) if fit.as_of_date is not None else None,
                "design": design.name,
                "solver": fit.solver,
                "rank": fit.rank,
                "n_games": int(len(season_games)),
                "n_teams": int(len(fit.teams)),
                "dropped_columns": ",".join(fit.dropped_columns),
                "warnings": " | ".join(fit.warnings),
            }
            for col, value in fit.coefficients.items():
                if not col.startswith("team_"):
                    coef_row[col] = value
            coef_rows.append(coef_row)
        if season_features is not None:
            features.append(season_features)

    features_df = pd.concat(features, ignore_index=True, sort=False) if features else pd.DataFrame()
    coefficients_df = pd.DataFrame(coef_rows)
    return features_df, coefficients_df, fits


def build_massey_matchup_diffs(
    matchups: pd.DataFrame,
    ratings: pd.DataFrame,
    *,
    rating_columns: Iterable[str] | None = None,
    season_col: str = "season",
    team_a_col: str = "team_a_id",
    team_b_col: str = "team_b_id",
) -> pd.DataFrame:
    """Add diff_* columns as Team A rating minus Team B rating."""

    if rating_columns is None:
        rating_columns = [
            c
            for c in ratings.columns
            if c not in {"season", "team_id"} and not c.endswith("_rank")
        ]
    rating_columns = list(rating_columns)

    left = ratings[[season_col, "team_id", *rating_columns]].rename(
        columns={"team_id": team_a_col, **{c: f"{c}__a" for c in rating_columns}}
    )
    right = ratings[[season_col, "team_id", *rating_columns]].rename(
        columns={"team_id": team_b_col, **{c: f"{c}__b" for c in rating_columns}}
    )
    out = matchups.merge(left, on=[season_col, team_a_col], how="left")
    out = out.merge(right, on=[season_col, team_b_col], how="left")

    for col in rating_columns:
        out[f"diff_{col}"] = out[f"{col}__a"] - out[f"{col}__b"]
    return out.drop(columns=[f"{c}__a" for c in rating_columns] + [f"{c}__b" for c in rating_columns])


def build_pregame_massey_game_features(
    games: pd.DataFrame,
    *,
    designs: Iterable[MasseyDesign] = DEFAULT_MASSEY_DESIGNS,
    min_completed_games: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build no-lookahead game-level diff features.

    For every game date, ratings are fit using only games from earlier dates
    in the same season, then diff_* values are Team A minus Team B. Team A is
    canonicalized as the lower team id to match the existing pairwise pipeline.
    """

    df = prepare_massey_context(games)
    rows: list[dict[str, object]] = []
    coef_frames: list[pd.DataFrame] = []

    for season, season_games in df.groupby("season", sort=True):
        season_games = season_games.sort_values(["game_date", "game_id"]).reset_index(drop=True)
        for game_date, games_on_date in season_games.groupby("game_date", sort=True):
            prior = season_games[season_games["game_date"] < game_date]
            if len(prior) >= min_completed_games:
                ratings, coefficients, _ = build_massey_team_features(
                    prior,
                    designs=designs,
                    as_of_date=game_date - pd.Timedelta(microseconds=1),
                    preview_rows=0,
                )
                coef_frames.append(coefficients)
                ratings_idx = ratings.set_index(["season", "team_id"])
            else:
                ratings_idx = pd.DataFrame()

            rating_cols = []
            if not ratings_idx.empty:
                rating_cols = [
                    c
                    for c in ratings_idx.columns
                    if not c.endswith("_rank")
                ]

            for _, game in games_on_date.iterrows():
                home = int(game["home_team_id"])
                away = int(game["away_team_id"])
                team_a = min(home, away)
                team_b = max(home, away)
                row: dict[str, object] = {
                    "season": season,
                    "game_id": game["game_id"],
                    "game_date": game_date,
                    "team_a_id": team_a,
                    "team_b_id": team_b,
                    "home_team_id": home,
                    "away_team_id": away,
                    "team_a_is_home": int(team_a == home),
                    "team_a_wins": int(
                        (team_a == home and game["home_score"] > game["away_score"])
                        or (team_a == away and game["away_score"] > game["home_score"])
                    ),
                    "home_margin": float(game["home_score"] - game["away_score"]),
                }
                for col in rating_cols:
                    try:
                        va = float(ratings_idx.loc[(season, team_a), col])
                        vb = float(ratings_idx.loc[(season, team_b), col])
                        row[f"diff_{col}"] = va - vb
                    except (KeyError, TypeError, ValueError):
                        row[f"diff_{col}"] = np.nan
                rows.append(row)

    features = pd.DataFrame(rows)
    coefficients = pd.concat(coef_frames, ignore_index=True, sort=False) if coef_frames else pd.DataFrame()
    return features, coefficients


def format_massey_matrix_report(
    fit: MasseyFit,
    *,
    max_matrix_size: int = 12,
) -> str:
    """Human-readable X, M, p, constrained system, and beta report."""

    lines: list[str] = []
    title = f"Massey design: {fit.design.name}"
    if fit.season is not None:
        title += f" | season={fit.season}"
    if fit.as_of_date is not None:
        title += f" | as_of={fit.as_of_date.date()}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append(f"Solver: {fit.solver}; rank(M)={fit.rank}; teams={len(fit.teams)}")
    if fit.dropped_columns:
        lines.append(f"Dropped columns: {', '.join(fit.dropped_columns)}")
    for note in fit.warnings:
        lines.append(f"Note: {note}")

    lines.append("\nX preview (first rows, sparse row made visible):")
    if fit.x_preview.empty:
        lines.append("<empty>")
    else:
        lines.append(fit.x_preview.to_string(index=False))
        y_df = pd.DataFrame({"y_home_margin": fit.y_preview})
        lines.append("\ny preview:")
        lines.append(y_df.to_string(index=False))

    if len(fit.columns) <= max_matrix_size:
        col_index = fit.columns
    else:
        col_index = fit.columns[:max_matrix_size]
        lines.append(
            f"\nMatrices truncated to first {max_matrix_size} columns/rows "
            f"out of {len(fit.columns)}."
        )

    idx = [fit.columns.index(c) for c in col_index] if fit.columns else []

    def _matrix_to_string(matrix: np.ndarray) -> str:
        if not idx:
            return "<empty>"
        return pd.DataFrame(matrix[np.ix_(idx, idx)], index=col_index, columns=col_index).to_string()

    def _vector_to_string(values: np.ndarray) -> str:
        if not idx:
            return "<empty>"
        return pd.Series(values[idx], index=col_index).to_string()

    lines.append("\nM = X.T @ W @ X:")
    lines.append(_matrix_to_string(fit.normal_matrix))
    lines.append("\np = X.T @ W @ y:")
    lines.append(_vector_to_string(fit.target_vector))
    lines.append("\nConstrained M:")
    lines.append(_matrix_to_string(fit.constrained_matrix))
    lines.append("\nConstrained p:")
    lines.append(_vector_to_string(fit.constrained_target))
    lines.append("\nSolved coefficients:")
    coef = pd.Series(fit.coefficients)
    if len(coef) > max_matrix_size:
        coef = coef.iloc[:max_matrix_size]
    lines.append(coef.to_string() if not coef.empty else "<empty>")
    return "\n".join(lines)


def summarize_massey_availability(coefficients: pd.DataFrame) -> pd.DataFrame:
    """Compact view of which optional Massey factors were usable."""

    if coefficients.empty:
        return pd.DataFrame()
    cols = ["season", "design", "dropped_columns", "warnings", "solver", "n_games", "n_teams"]
    return coefficients[[c for c in cols if c in coefficients.columns]].copy()


def sparse_backend_available() -> bool:
    """Expose scipy availability for diagnostics and environment checks."""

    return sp is not None
