"""
Massey rating feature engineering for NBA game data.

The core system is X beta = y, where y is home_score - away_score.
Rows in X are intentionally sparse: +1 for the home team, -1 for the
away team, plus optional context columns such as home advantage, crowd
density, roster experience, and travel.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

logger = logging.getLogger(__name__)


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


def schedule_is_connected(games: pd.DataFrame) -> bool:
    """True when all teams sit in one connected schedule component."""
    if games.empty:
        return False
    teams = sorted(
        set(games["home_team_id"].astype(int).tolist())
        | set(games["away_team_id"].astype(int).tolist())
    )
    return len(_team_components(games, teams)) == 1


def _emit_fit_notes(notes: list[str]) -> None:
    """Route fit diagnostics: expected factor drops are debug, real issues stay warning."""
    for note in notes:
        if (
            "unavailable; dropped from" in note
            or ("coverage" in note and "below" in note)
            or "has no variation; dropped from" in note
            or ("unavailable;" in note and "used unweighted" in note)
        ):
            logger.debug("[fit_massey] %s", note)
        elif "disconnected" in note:
            logger.info("[fit_massey] %s", note)
        else:
            logger.warning("[fit_massey] %s", note)


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


def _build_normal_equations_vectorized(
    df: pd.DataFrame,
    team_to_idx: dict[int, int],
    teams: list[int],
    extra_columns: list[str],
    design: "MasseyDesign",
    weights: np.ndarray,
    y: np.ndarray,
    preview_rows: int = 8,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.Series]:
    """
    Vectorized normal equation assembly: M = X.T @ diag(W) @ X, p = X.T @ diag(W) @ y.

    Returns (normal_matrix, target_vector, x_preview, y_preview).
    """
    n_games = len(df)
    n_teams = len(teams)
    n_cols = n_teams + len(extra_columns)

    home_ids = df["home_team_id"].map(team_to_idx).values.astype(int)
    away_ids = df["away_team_id"].map(team_to_idx).values.astype(int)

    X = np.zeros((n_games, n_cols), dtype=float)
    X[np.arange(n_games), home_ids] = 1.0
    X[np.arange(n_games), away_ids] = -1.0

    for j, col in enumerate(extra_columns):
        if col == "home_advantage":
            is_neutral = df.get("is_neutral", pd.Series(False, index=df.index))
            vals = np.where(is_neutral.values, design.neutral_home_value, 1.0)
        else:
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0).values
        X[:, n_teams + j] = vals

    XW = X * weights[:, None]
    normal = XW.T @ X
    target = XW.T @ y

    columns = [f"team_{team}" for team in teams] + extra_columns
    x_preview = pd.DataFrame(X[:preview_rows], columns=columns)
    y_preview = pd.Series(y[:preview_rows], name="home_margin")

    return normal, target, x_preview, y_preview


def _build_colley_vectorized(
    df: pd.DataFrame,
    team_to_idx: dict[int, int],
    teams: list[int],
    home_score_col: str = "home_score",
    away_score_col: str = "away_score",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized Colley matrix and win/loss assembly.

    Returns (M, wins, losses) where C = 2I + M and b = 1 + 0.5*(wins - losses).
    """
    n = len(teams)
    home_ids = df["home_team_id"].map(team_to_idx).values.astype(int)
    away_ids = df["away_team_id"].map(team_to_idx).values.astype(int)

    M = np.zeros((n, n), dtype=float)
    np.add.at(M, (home_ids, home_ids), 1.0)
    np.add.at(M, (away_ids, away_ids), 1.0)
    np.add.at(M, (home_ids, away_ids), -1.0)
    np.add.at(M, (away_ids, home_ids), -1.0)

    home_scores = pd.to_numeric(df[home_score_col], errors="coerce").values
    away_scores = pd.to_numeric(df[away_score_col], errors="coerce").values

    home_wins_mask = home_scores > away_scores
    away_wins_mask = away_scores > home_scores
    ties_mask = home_scores == away_scores

    wins = np.zeros(n, dtype=float)
    losses = np.zeros(n, dtype=float)
    np.add.at(wins, home_ids[home_wins_mask], 1.0)
    np.add.at(losses, away_ids[home_wins_mask], 1.0)
    np.add.at(wins, away_ids[away_wins_mask], 1.0)
    np.add.at(losses, home_ids[away_wins_mask], 1.0)
    np.add.at(wins, home_ids[ties_mask], 0.5)
    np.add.at(losses, home_ids[ties_mask], 0.5)
    np.add.at(wins, away_ids[ties_mask], 0.5)
    np.add.at(losses, away_ids[ties_mask], 0.5)

    return M, wins, losses


def _zermelo_vectorized(
    team_a_ids: np.ndarray,
    team_b_ids: np.ndarray,
    win_weights_a: np.ndarray,
    win_weights_b: np.ndarray,
    n_teams: int,
    n_iter: int = 100,
) -> np.ndarray:
    """
    Vectorized Zermelo/Bradley-Terry iteration.

    team_a_ids[i], team_b_ids[i]: the two teams in game i.
    win_weights_a[i]: fractional win credit for team_a in game i.
    win_weights_b[i]: fractional win credit for team_b in game i.
    """
    all_team_ids = np.concatenate([team_a_ids, team_b_ids])
    all_opponent_ids = np.concatenate([team_b_ids, team_a_ids])
    all_win_weights = np.concatenate([win_weights_a, win_weights_b])

    frac_wins = np.bincount(all_team_ids, weights=all_win_weights, minlength=n_teams)

    pi = np.ones(n_teams, dtype=float)
    for _ in range(n_iter):
        pair_denoms = 1.0 / (pi[all_team_ids] + pi[all_opponent_ids])
        denom_per_team = np.bincount(all_team_ids, weights=pair_denoms, minlength=n_teams)
        pi = np.where(denom_per_team > 0, frac_wins / denom_per_team, 1.0)
        pi /= pi.mean()

    final_delta = float(np.abs(pi - np.ones_like(pi)).max())
    logger.debug("[_zermelo_vectorized] n_teams=%d n_iter=%d final_max_delta=%.4e",
                 n_teams, n_iter, final_delta)

    return pi


def _row_entries_for_game(
    game: pd.Series,
    team_to_idx: dict[int, int],
    team_count: int,
    extra_columns: list[str],
    design: "MasseyDesign",
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
    weights, weight_notes = _weights_for_design(df, design)
    notes.extend(weight_notes)

    y_vec = (df["home_score"].astype(float) - df["away_score"].astype(float)).values
    normal, target, x_preview, y_preview = _build_normal_equations_vectorized(
        df, team_to_idx, teams, extra_columns, design, weights, y_vec, preview_rows
    )

    unconstrained_cond = float("inf")
    if normal.size > 0:
        unconstrained_cond = float(np.linalg.cond(normal))
        matrix_rank = int(np.linalg.matrix_rank(normal))
        logger.info(
            "[fit_massey] design=%s season=%s games=%d teams=%d cond(M_unconstrained)=%.2e rank=%d/%d",
            design.name,
            season,
            len(df),
            len(teams),
            unconstrained_cond,
            matrix_rank,
            n_cols,
        )

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

    constrained_cond = float("inf")
    if constrained.size > 0:
        constrained_cond = float(np.linalg.cond(constrained))
        constrained_rank = int(np.linalg.matrix_rank(constrained))
        logger.info(
            "[fit_massey] design=%s season=%s cond(M_constrained)=%.2e rank=%d/%d components=%d",
            design.name,
            season,
            constrained_cond,
            constrained_rank,
            n_cols,
            len(components),
        )
        if constrained_cond > 1e10:
            logger.warning(
                "[fit_massey] design=%s season=%s ill-conditioned constrained matrix (cond=%.2e) — ratings may be unreliable",
                design.name,
                season,
                constrained_cond,
            )

    try:
        beta = np.linalg.solve(constrained, constrained_target)
        solver = "numpy.linalg.solve"
    except np.linalg.LinAlgError:
        beta, *_ = np.linalg.lstsq(constrained, constrained_target, rcond=None)
        solver = "numpy.linalg.lstsq"
        notes.append(
            "Normal equations remained singular after constraints; used least-squares fallback."
        )

    logger.debug("[fit_massey] design=%s season=%s solver=%s rating_range=[%.3f, %.3f]",
                 design.name, season, solver,
                 float(beta[:len(teams)].min()), float(beta[:len(teams)].max()))
    _emit_fit_notes(notes)

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
        x_preview=x_preview,
        y_preview=y_preview,
        components=components,
        dropped_columns=dropped,
        solver=solver,
        rank=int(np.linalg.matrix_rank(normal)) if n_cols else 0,
        warnings=notes,
    )


def fit_colley(
    games: pd.DataFrame,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
) -> MasseyFit:
    """
    Fit the Colley rating system for one season/snapshot.

    The Colley matrix C = 2I + M where M is the Massey matrix (team-team
    block only). The RHS is b_i = 1 + 0.5*(wins_i - losses_i). Unlike
    Massey, the Colley system is always invertible — no constraints needed.

    The solved ratings incorporate strength of schedule implicitly via the
    linear system coupling (each team's rating depends on opponents' ratings).
    """
    design = MasseyDesign("colley")

    df = normalize_massey_games(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    if df.empty:
        empty = pd.DataFrame(columns=["season", "team_id", "colley", "colley_rank"])
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
            y_preview=pd.Series(dtype=float, name="colley_b"),
            components=[],
            solver="empty",
            warnings=["No completed games available for Colley fit."],
        )

    teams = sorted(
        set(df["home_team_id"].astype(int).tolist())
        | set(df["away_team_id"].astype(int).tolist())
    )
    team_to_idx = {team: idx for idx, team in enumerate(teams)}
    n = len(teams)

    M, wins, losses = _build_colley_vectorized(df, team_to_idx, teams)

    # Colley matrix: C = 2I + M
    C = 2.0 * np.eye(n) + M

    # Colley RHS: b_i = 1 + 0.5*(w_i - l_i)
    b = 1.0 + 0.5 * (wins - losses)

    cond_c = np.linalg.cond(C) if n > 0 else float("inf")
    logger.info("[fit_colley] season=%s games=%d teams=%d cond(C)=%.2e",
                season, len(df), n, cond_c)

    try:
        r = np.linalg.solve(C, b)
        solver = "numpy.linalg.solve"
    except np.linalg.LinAlgError:
        r, *_ = np.linalg.lstsq(C, b, rcond=None)
        solver = "numpy.linalg.lstsq"

    logger.debug("[fit_colley] season=%s solver=%s rating_range=[%.3f, %.3f]",
                 season, solver, float(r.min()), float(r.max()))

    columns = [f"team_{team}" for team in teams]
    coeffs = {columns[i]: float(r[i]) for i in range(n)}

    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        "colley": r,
    })
    ratings["colley_rank"] = (
        ratings["colley"].rank(ascending=False, method="min").astype(int)
    )

    return MasseyFit(
        design=design,
        season=season if season is not None else df["season"].iloc[0],
        as_of_date=snapshot_date,
        teams=teams,
        columns=columns,
        ratings=ratings,
        coefficients=coeffs,
        normal_matrix=M,
        target_vector=b,
        constrained_matrix=C,
        constrained_target=b,
        x_preview=pd.DataFrame(),
        y_preview=pd.Series(b[:8], name="colley_b"),
        components=_team_components(df, teams),
        solver=solver,
        rank=int(np.linalg.matrix_rank(C)),
        warnings=[],
    )


QUARTERS = ("q1", "q2", "q3", "q4")


def fit_massey_quarter(
    games: pd.DataFrame,
    design: MasseyDesign,
    quarter: str,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
) -> MasseyFit:
    """
    Fit a Massey design using per-quarter scores as the target.

    Expects games to have columns `home_{quarter}_score` and `away_{quarter}_score`
    (e.g. home_q1_score, away_q1_score). The design matrix X is identical to
    full-game Massey; only the target vector changes.
    """
    home_col = f"home_{quarter}_score"
    away_col = f"away_{quarter}_score"
    suffix = f"_{quarter}"
    rating_name = f"{design.name}{suffix}"

    df = prepare_massey_context(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    # Drop rows missing quarter scores
    for col in (home_col, away_col):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
            return MasseyFit(
                design=MasseyDesign(rating_name),
                season=season, as_of_date=snapshot_date,
                teams=[], columns=[], ratings=empty, coefficients={},
                normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
                constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
                x_preview=pd.DataFrame(),
                y_preview=pd.Series(dtype=float, name=f"{quarter}_margin"),
                components=[], solver="empty",
                warnings=[f"Column {col} not found."],
            )
    df = df.dropna(subset=[home_col, away_col])

    if df.empty:
        empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
        return MasseyFit(
            design=MasseyDesign(rating_name),
            season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(),
            y_preview=pd.Series(dtype=float, name=f"{quarter}_margin"),
            components=[], solver="empty",
            warnings=[f"No games with {quarter} scores for this fit."],
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
    weights, weight_notes = _weights_for_design(df, design)
    notes.extend(weight_notes)

    y_vec = (pd.to_numeric(df[home_col], errors="coerce") - pd.to_numeric(df[away_col], errors="coerce")).values.astype(float)
    normal, target, _, _ = _build_normal_equations_vectorized(
        df, team_to_idx, teams, extra_columns, design, weights, y_vec, preview_rows=0
    )

    constrained = normal.copy()
    constrained_target = target.copy()
    components = _team_components(df, teams)

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

    _emit_fit_notes(notes)

    rating_values = beta[: len(teams)]
    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        rating_name: rating_values,
    })
    ratings[f"{rating_name}_rank"] = (
        ratings[rating_name].rank(ascending=False, method="min").astype(int)
    )

    return MasseyFit(
        design=MasseyDesign(rating_name),
        season=season if season is not None else df["season"].iloc[0],
        as_of_date=snapshot_date,
        teams=teams, columns=columns, ratings=ratings,
        coefficients={columns[i]: float(beta[i]) for i in range(n_cols)},
        normal_matrix=normal, target_vector=target,
        constrained_matrix=constrained, constrained_target=constrained_target,
        x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float, name=f"{quarter}_margin"),
        components=components, dropped_columns=dropped, solver=solver,
        rank=int(np.linalg.matrix_rank(normal)) if n_cols else 0,
        warnings=notes,
    )


def fit_colley_quarter(
    games: pd.DataFrame,
    quarter: str,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
) -> MasseyFit:
    """
    Fit Colley ratings using per-quarter wins/losses.

    A team 'wins' a quarter if it outscores the opponent in that quarter.
    Ties count as 0.5 win + 0.5 loss.
    """
    home_col = f"home_{quarter}_score"
    away_col = f"away_{quarter}_score"
    rating_name = f"colley_{quarter}"

    df = normalize_massey_games(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    for col in (home_col, away_col):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
            return MasseyFit(
                design=MasseyDesign(rating_name),
                season=season, as_of_date=snapshot_date,
                teams=[], columns=[], ratings=empty, coefficients={},
                normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
                constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
                x_preview=pd.DataFrame(),
                y_preview=pd.Series(dtype=float, name=f"colley_{quarter}_b"),
                components=[], solver="empty",
                warnings=[f"Column {col} not found."],
            )
    df = df.dropna(subset=[home_col, away_col])

    if df.empty:
        empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
        return MasseyFit(
            design=MasseyDesign(rating_name),
            season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(),
            y_preview=pd.Series(dtype=float, name=f"colley_{quarter}_b"),
            components=[], solver="empty",
            warnings=[f"No games with {quarter} scores for Colley fit."],
        )

    teams = sorted(
        set(df["home_team_id"].astype(int).tolist())
        | set(df["away_team_id"].astype(int).tolist())
    )
    team_to_idx = {team: idx for idx, team in enumerate(teams)}
    n = len(teams)

    M, wins, losses = _build_colley_vectorized(
        df, team_to_idx, teams, home_score_col=home_col, away_score_col=away_col
    )

    C = 2.0 * np.eye(n) + M
    b = 1.0 + 0.5 * (wins - losses)

    try:
        r = np.linalg.solve(C, b)
        solver = "numpy.linalg.solve"
    except np.linalg.LinAlgError:
        r, *_ = np.linalg.lstsq(C, b, rcond=None)
        solver = "numpy.linalg.lstsq"

    columns = [f"team_{team}" for team in teams]
    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        rating_name: r,
    })
    ratings[f"{rating_name}_rank"] = (
        ratings[rating_name].rank(ascending=False, method="min").astype(int)
    )

    return MasseyFit(
        design=MasseyDesign(rating_name),
        season=season if season is not None else df["season"].iloc[0],
        as_of_date=snapshot_date,
        teams=teams, columns=columns, ratings=ratings,
        coefficients={columns[i]: float(r[i]) for i in range(n)},
        normal_matrix=M, target_vector=b,
        constrained_matrix=C, constrained_target=b,
        x_preview=pd.DataFrame(),
        y_preview=pd.Series(b[:8], name=f"colley_{quarter}_b"),
        components=_team_components(df, teams),
        solver=solver, rank=int(np.linalg.matrix_rank(C)),
        warnings=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Alternative Rating Systems: Wolfe, Wobus, Whitlock
# ─────────────────────────────────────────────────────────────────────────────

def fit_wolfe(
    games: pd.DataFrame,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    home_advantage: float = 3.0,
    n_iter: int = 100,
) -> MasseyFit:
    """
    Wolfe (Bradley-Terry, win/loss only): P(i beats j) = πi / (πi + πj).
    Iterative Zermelo algorithm. Pure W/L — no margin. Home team gets
    opponent strength reduced by home_advantage equivalent.
    """
    design = MasseyDesign("wolfe")
    df = normalize_massey_games(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    if df.empty or len(df) < 5:
        empty = pd.DataFrame(columns=["season", "team_id", "wolfe", "wolfe_rank"])
        return MasseyFit(
            design=design, season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
            components=[], solver="empty", warnings=["Insufficient data."],
        )

    teams = sorted(set(df["home_team_id"].tolist()) | set(df["away_team_id"].tolist()))
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    # Vectorized Zermelo: pure W/L (winner gets 1.0, loser gets 0.0)
    home_ids = df["home_team_id"].map(team_to_idx).values.astype(int)
    away_ids = df["away_team_id"].map(team_to_idx).values.astype(int)
    home_scores = df["home_score"].values.astype(float)
    away_scores = df["away_score"].values.astype(float)

    home_wins = home_scores > away_scores
    away_wins = away_scores > home_scores

    # Only include decided games (no ties for Wolfe)
    decided = home_wins | away_wins
    team_a_ids = np.where(home_wins, home_ids, away_ids)[decided]
    team_b_ids = np.where(home_wins, away_ids, home_ids)[decided]
    win_weights_a = np.ones(decided.sum(), dtype=float)
    win_weights_b = np.zeros(decided.sum(), dtype=float)

    pi = _zermelo_vectorized(team_a_ids, team_b_ids, win_weights_a, win_weights_b, n, n_iter)

    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        "wolfe": pi,
    })
    ratings["wolfe_rank"] = ratings["wolfe"].rank(ascending=False, method="min").astype(int)

    return MasseyFit(
        design=design, season=season, as_of_date=snapshot_date,
        teams=teams, columns=[f"team_{t}" for t in teams], ratings=ratings,
        coefficients={}, normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
        constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
        x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
        components=_team_components(df, teams), solver="zermelo_iterative",
        warnings=[],
    )


def fit_wobus(
    games: pd.DataFrame,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    sigma: float = 13.0,
    margin_cap: int = 24,
    n_iter: int = 100,
) -> MasseyFit:
    """
    Wobus (Bradley-Terry with margin-weighted fractional wins).
    Convert margin to win probability via logistic: P = 1/(1+exp(-margin/sigma)).
    Feed fractional wins into Zermelo/B-T algorithm.
    """
    design = MasseyDesign("wobus")
    df = normalize_massey_games(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    if df.empty or len(df) < 5:
        empty = pd.DataFrame(columns=["season", "team_id", "wobus", "wobus_rank"])
        return MasseyFit(
            design=design, season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
            components=[], solver="empty", warnings=["Insufficient data."],
        )

    teams = sorted(set(df["home_team_id"].tolist()) | set(df["away_team_id"].tolist()))
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    # Vectorized fractional wins via logistic margin transform
    home_ids = df["home_team_id"].map(team_to_idx).values.astype(int)
    away_ids = df["away_team_id"].map(team_to_idx).values.astype(int)
    home_scores = df["home_score"].values.astype(float)
    away_scores = df["away_score"].values.astype(float)

    margins = np.abs(home_scores - away_scores)
    margins = np.minimum(margins, margin_cap)
    p_win = 1.0 / (1.0 + np.exp(-margins / sigma))

    home_wins = home_scores > away_scores
    away_wins = away_scores > home_scores
    ties = home_scores == away_scores

    # Winner gets p_win, loser gets 1-p_win; ties get 0.5 each
    win_weights_a = np.where(home_wins, p_win, np.where(away_wins, 1 - p_win, 0.5))
    win_weights_b = np.where(home_wins, 1 - p_win, np.where(away_wins, p_win, 0.5))

    pi = _zermelo_vectorized(home_ids, away_ids, win_weights_a, win_weights_b, n, n_iter)

    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        "wobus": pi,
    })
    ratings["wobus_rank"] = ratings["wobus"].rank(ascending=False, method="min").astype(int)

    return MasseyFit(
        design=design, season=season, as_of_date=snapshot_date,
        teams=teams, columns=[f"team_{t}" for t in teams], ratings=ratings,
        coefficients={}, normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
        constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
        x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
        components=_team_components(df, teams), solver="zermelo_fractional",
        warnings=[],
    )


def fit_whitlock(
    games: pd.DataFrame,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    margin_cap: int = 24,
    win_bonus: float = 5.0,
    home_penalty: float = 3.0,
) -> MasseyFit:
    """
    Whitlock (LP-formulated as linear system).
    Per-game: WinRank - LoseRank = sqrt(min(margin, cap)) + sqrt(win_bonus) - sqrt(home_penalty if home won)
    Solved as least-squares on the linear system with per-team slack balancing.
    """
    design = MasseyDesign("whitlock")
    df = normalize_massey_games(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    if df.empty or len(df) < 5:
        empty = pd.DataFrame(columns=["season", "team_id", "whitlock", "whitlock_rank"])
        return MasseyFit(
            design=design, season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
            components=[], solver="empty", warnings=["Insufficient data."],
        )

    teams = sorted(set(df["home_team_id"].tolist()) | set(df["away_team_id"].tolist()))
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    n_games = len(df)

    # Build system: one equation per game
    # WinRank - LoseRank = sqrt(min(margin, cap)) + sqrt(win_bonus) - sqrt(home_penalty) if home won
    X = np.zeros((n_games, n_teams))
    y = np.zeros(n_games)

    home_ids = df["home_team_id"].map(team_to_idx).values.astype(int)
    away_ids = df["away_team_id"].map(team_to_idx).values.astype(int)
    home_scores = df["home_score"].values.astype(float)
    away_scores = df["away_score"].values.astype(float)

    margins = np.minimum(np.abs(home_scores - away_scores), margin_cap)
    home_wins = home_scores > away_scores
    away_wins = away_scores > home_scores

    # Winner gets +1, loser gets -1
    winner_ids = np.where(home_wins, home_ids, np.where(away_wins, away_ids, home_ids))
    loser_ids = np.where(home_wins, away_ids, np.where(away_wins, home_ids, away_ids))
    decided = home_wins | away_wins

    X[np.arange(n_games)[decided], winner_ids[decided]] = 1.0
    X[np.arange(n_games)[decided], loser_ids[decided]] = -1.0

    # RHS: sqrt(margin) + sqrt(win_bonus) adjusted for home/away winner
    y = np.sqrt(margins) + np.sqrt(win_bonus)
    y[home_wins] -= np.sqrt(home_penalty)
    y[away_wins] += np.sqrt(home_penalty)
    y[~decided] = 0.0

    # Solve via normal equations with sum-to-zero constraint
    XtX = X.T @ X
    Xty = X.T @ y
    constrained = XtX.copy()
    constrained_target = Xty.copy()
    constrained[-1, :] = 1.0
    constrained_target[-1] = 0.0

    try:
        beta = np.linalg.solve(constrained, constrained_target)
    except np.linalg.LinAlgError:
        beta, *_ = np.linalg.lstsq(constrained, constrained_target, rcond=None)

    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        "whitlock": beta,
    })
    ratings["whitlock_rank"] = ratings["whitlock"].rank(ascending=False, method="min").astype(int)

    return MasseyFit(
        design=design, season=season, as_of_date=snapshot_date,
        teams=teams, columns=[f"team_{t}" for t in teams], ratings=ratings,
        coefficients={}, normal_matrix=XtX, target_vector=Xty,
        constrained_matrix=constrained, constrained_target=constrained_target,
        x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
        components=_team_components(df, teams), solver="normal_equations",
        warnings=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Off/Def Massey Split
# ─────────────────────────────────────────────────────────────────────────────

def fit_massey_offdef(
    games: pd.DataFrame,
    design: MasseyDesign,
    target_col_home: str,
    target_col_away: str,
    rating_name: str,
    *,
    season: int | str | None = None,
    as_of_date: str | pd.Timestamp | None = None,
) -> MasseyFit:
    """
    Fit Massey using a custom target: target_col_home - target_col_away.
    Same design matrix as standard Massey (team +1/-1 + context columns),
    only the y vector changes.

    Use for off/def splits:
      OFF: target_col_home="home_offrtg", target_col_away="away_offrtg"
      DEF: target_col_home="home_defrtg", target_col_away="away_defrtg"
    """
    df = prepare_massey_context(games)
    if season is not None:
        df = df[df["season"] == season].copy()
    snapshot_date = pd.to_datetime(as_of_date) if as_of_date is not None else None
    if snapshot_date is not None:
        df = df[df["game_date"] <= snapshot_date].copy()

    # Check target columns exist and have data
    for col in (target_col_home, target_col_away):
        if col not in df.columns:
            empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
            return MasseyFit(
                design=MasseyDesign(rating_name), season=season, as_of_date=snapshot_date,
                teams=[], columns=[], ratings=empty, coefficients={},
                normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
                constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
                x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
                components=[], solver="empty",
                warnings=[f"Column {col} not found."],
            )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[target_col_home, target_col_away])
    if df.empty or len(df) < 10:
        empty = pd.DataFrame(columns=["season", "team_id", rating_name, f"{rating_name}_rank"])
        return MasseyFit(
            design=MasseyDesign(rating_name), season=season, as_of_date=snapshot_date,
            teams=[], columns=[], ratings=empty, coefficients={},
            normal_matrix=np.zeros((0, 0)), target_vector=np.zeros(0),
            constrained_matrix=np.zeros((0, 0)), constrained_target=np.zeros(0),
            x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
            components=[], solver="empty",
            warnings=["Insufficient data for off/def fit."],
        )

    teams = sorted(set(df["home_team_id"].tolist()) | set(df["away_team_id"].tolist()))
    team_to_idx = {t: i for i, t in enumerate(teams)}

    usable_factors, dropped, notes = _usable_factor_columns(df, design)
    extra_columns = []
    if design.include_home_advantage:
        extra_columns.append("home_advantage")
    extra_columns.extend(usable_factors)

    columns = [f"team_{team}" for team in teams] + extra_columns
    n_cols = len(columns)
    weights, weight_notes = _weights_for_design(df, design)
    notes.extend(weight_notes)

    y_vec = (pd.to_numeric(df[target_col_home], errors="coerce") - pd.to_numeric(df[target_col_away], errors="coerce")).values.astype(float)
    normal, target, _, _ = _build_normal_equations_vectorized(
        df, team_to_idx, teams, extra_columns, design, weights, y_vec, preview_rows=0
    )

    constrained = normal.copy()
    constrained_target = target.copy()
    components = _team_components(df, teams)

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

    _emit_fit_notes(notes)

    rating_values = beta[:len(teams)]
    ratings = pd.DataFrame({
        "season": season if season is not None else df["season"].iloc[0],
        "team_id": teams,
        rating_name: rating_values,
    })
    ratings[f"{rating_name}_rank"] = (
        ratings[rating_name].rank(ascending=False, method="min").astype(int)
    )

    return MasseyFit(
        design=MasseyDesign(rating_name), season=season, as_of_date=snapshot_date,
        teams=teams, columns=columns, ratings=ratings,
        coefficients={columns[i]: float(beta[i]) for i in range(n_cols)},
        normal_matrix=normal, target_vector=target,
        constrained_matrix=constrained, constrained_target=constrained_target,
        x_preview=pd.DataFrame(), y_preview=pd.Series(dtype=float),
        components=components, dropped_columns=dropped, solver=solver,
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
