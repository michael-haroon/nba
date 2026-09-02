"""
league_config.py
----------------
Single source of truth for league-specific constants.

Every script that varies by league (sync, features, strategy, trading)
imports from here. Add --league as a REQUIRED CLI arg everywhere.

Usage:
    from league_config import get_league_config, add_league_arg
    add_league_arg(parser)   # adds --league to argparse
    args = parser.parse_args()
    cfg = get_league_config(args.league)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class LeagueConfig:
    league: str
    league_id: str
    season_format: str  # "split" for 2024-25, "calendar" for 2024

    # Directories (relative to PROJECT_ROOT)
    data_dir: str
    output_dir: str
    models_dir: str

    # File names
    game_ids_file: str
    team_map_file: str
    arenas_file: str

    # Season schedule
    active_months: tuple[int, ...]

    # Kalshi series tickers
    kalshi_series: dict[str, str] = field(default_factory=dict)

    # Domain constants
    pythagorean_exp: float = 13.91
    blowout_threshold: int = 15
    close_threshold: int = 5
    margin_cap: int = 24
    wolfe_home_bonus: float = 3.0
    wobus_sigma: float = 13.0
    whitlock_win_bonus: float = 5.0
    whitlock_home_penalty: float = 3.0

    # Rolling feature windows
    rolling_windows: tuple[int, ...] = (5, 10, 20)

    # Data availability flags
    has_hustle: bool = True
    has_bpi: bool = True
    has_sagarin: bool = True

    # S3 prefix
    s3_prefix: str = ""

    @property
    def data_path(self) -> Path:
        return PROJECT_ROOT / self.data_dir

    @property
    def output_path(self) -> Path:
        return PROJECT_ROOT / self.output_dir

    @property
    def models_path(self) -> Path:
        return PROJECT_ROOT / self.models_dir

    def current_season(self, ref_date=None) -> str:
        """Return the current season string for this league."""
        from datetime import date
        d = ref_date or date.today()
        if self.season_format == "split":
            year = d.year if d.month >= 8 else d.year - 1
            return f"{year}-{str(year + 1)[-2:]}"
        else:
            # WNBA: calendar year. Season starts in May.
            return str(d.year)

    def is_active(self, ref_date=None) -> bool:
        """Return True if the league is in-season."""
        from datetime import date
        d = ref_date or date.today()
        return d.month in self.active_months


NBA_CONFIG = LeagueConfig(
    league="nba",
    league_id="00",
    season_format="split",
    data_dir="data_curation/data",
    output_dir="output/features",
    models_dir="strategy/output/nba",
    game_ids_file="NBAGameIDs.parquet",
    team_map_file="TeamMap.parquet",
    arenas_file="nba_arenas_geocoded.csv",
    active_months=(10, 11, 12, 1, 2, 3, 4, 5, 6),
    kalshi_series={
        "winner": "KXNBAGAME",
        "spread": "KXNBASPREAD",
        "h1_spread": "KXNBA1HSPREAD",
        "h1_total": "KXNBA1HTOTAL",
        "h2_total": "KXNBA2HTOTAL",
        "home_wins_h1": "KXNBA1HWINNER",
    },
    pythagorean_exp=13.91,
    blowout_threshold=15,
    close_threshold=5,
    margin_cap=24,
    wolfe_home_bonus=3.0,
    wobus_sigma=13.0,
    whitlock_win_bonus=5.0,
    whitlock_home_penalty=3.0,
    rolling_windows=(5, 10, 20),
    has_hustle=True,
    has_bpi=True,
    has_sagarin=True,
    s3_prefix="nba/data_curation/data",
)

WNBA_CONFIG = LeagueConfig(
    league="wnba",
    league_id="10",
    season_format="calendar",
    data_dir="data_curation/data_wnba",
    output_dir="output/features_wnba",
    models_dir="strategy/output/wnba",
    game_ids_file="WNBAGameIDs.parquet",
    team_map_file="TeamMap.parquet",
    arenas_file="wnba_arenas_geocoded.csv",
    active_months=(5, 6, 7, 8, 9, 10),
    kalshi_series={
        "winner": "KXWNBAGAME",
        "spread": "KXWNBASPREAD",
        "h1_spread": "KXWNBA1HSPREAD",
        "h1_total": "KXWNBA1HTOTAL",
        "h2_total": "KXWNBA2HTOTAL",
        "home_wins_h1": "KXWNBA1HWINNER",
    },
    # WNBA-specific constants (to be calibrated from data)
    pythagorean_exp=11.5,
    blowout_threshold=12,
    close_threshold=5,
    margin_cap=20,
    wolfe_home_bonus=2.5,
    wobus_sigma=11.0,
    whitlock_win_bonus=4.0,
    whitlock_home_penalty=2.5,
    rolling_windows=(3, 5, 10),
    has_hustle=False,
    has_bpi=False,
    has_sagarin=False,
    s3_prefix="nba/data_curation/data_wnba",
)

_CONFIGS = {
    "nba": NBA_CONFIG,
    "wnba": WNBA_CONFIG,
}


def get_league_config(league: str) -> LeagueConfig:
    """Get config for a league. Raises ValueError if unknown."""
    league = league.lower()
    if league not in _CONFIGS:
        raise ValueError(f"Unknown league '{league}'. Available: {list(_CONFIGS.keys())}")
    return _CONFIGS[league]


def add_league_arg(parser: argparse.ArgumentParser) -> None:
    """Add --league as a REQUIRED argument to an argparse parser."""
    parser.add_argument(
        "--league",
        required=True,
        choices=list(_CONFIGS.keys()),
        help="League to operate on (nba or wnba)",
    )
