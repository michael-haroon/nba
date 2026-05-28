# Data Curation Module

**Purpose:** Fetch, normalize, and persist NBA data from ESPN & NBA.com APIs.

---

## 📋 Data Model

All data is stored as parquets in `data/` directory. This ensures fast I/O and schema consistency across runs.

### Core Tables

| File | Source | Update Frequency | Key Columns |
|------|--------|------------------|------------|
| `GamesInfo.parquet` | nba_api | Every sync | game_id, game_date, season, home_team, away_team, home_pts, away_pts |
| `BoxScoresTrad*.parquet` (Pre/Regular/Playoffs) | nba_api v3 | Every sync | game_id, team, MIN, PTS, FGM, FGA, REB, AST, etc. |
| `AdvBoxScores*.parquet` (Trad/Adv/FourFactors/Misc/Scoring) | nba_api v3 | Every sync | game_id, team, OFFRTG, DEFRTG, NETRTG, EFG%, TS%, PACE, etc. |
| `Hustlestats*.parquet` (Pre/Regular/Playoffs) | NBA.com scrape | Every sync | game_id, team, contested_shots, deflections, loose_balls, etc. |
| `MasseyRatings.parquet` | Computed | Auto-rebuilt after sync | game_id, home_massey_rating, away_massey_rating, home_crowd_adj, away_crowd_adj, etc. |
| `Sagarin.parquet` | Scraped (ESPN/Massey website) | Manual (needs selenium) | date, team, bpi, elo, predictor, pure_elo, etc. |
| `PlayerBoxScores.parquet` | nba_api v3 | Every sync | game_id, player_id, team, MIN, PTS, REB, AST, etc. |
| `Arenas.parquet` | nba_api | Once per season | team, arena_name, capacity, city, lat, lon |
| `OfficialCrews.parquet` | nba_api | Manual | crew_id, official_name, crew_experience, crew_home_win_pct |
| `TeamRosters.parquet` | nba_api | Every sync | game_id, team, player_ids, active_count, dnp_count |
| `team_mappings.parquet` | Manual mapping | Static (reference) | espn_id, nba_api_id, team_name, team_abbr |

---

## 🔄 Sync Workflow: `sync_games.py`

**Entry point:** `python data_curation/scripts/sync_games.py [--dry-run] [--season 2025-26] [--workers 3]`

### What it does:

1. **Query completed games** → nba_api (all seasons or --season)
2. **Find missing games** → compare to local GamesInfo.parquet
3. **Fetch + normalize data** → box scores, player stats, etc.
4. **Append to parquets** → per-game-type parquets (Trad, Adv, etc.)
5. **Rebuild Massey ratings** → calls `build_massey_ratings.py` automatically
6. **Log results** → data_curation/logs/sync_games.log

### Circuit breaker:
- If any step fails, script exits without writing partial data
- Check logs before re-running

### Column normalization:
nba_api v3 uses camelCase (e.g., `fieldGoalsMade`), but local parquets use shorthand (e.g., `FGM`). Sync handles renaming automatically via `_TRAD_RENAME`, `_ADV_RENAME`, etc.

---

## 📊 Key Scripts

### `build_massey_ratings.py`
Solves the Massey matrix equation: **X @ β = y**
- X = home advantage + strength differential + margin encoding
- y = game outcomes (1 = home win, 0 = away win)
- β = team ratings

**Also computes context-adjusted Massey:**
- `crowd_adjusted` — scales ratings by attendance / capacity
- `experience_adjusted` — penalizes road teams with new rosters
- `travel_adjusted` — haversine distance + timezone effects
- `context_adjusted` — all factors combined

**Output:** `MasseyRatings.parquet` with columns:
- `home_massey_rating`, `away_massey_rating` (base)
- `home_massey_crowd_adj`, `away_massey_crowd_adj` (crowd-weighted)
- `home_massey_experience_adj`, etc. (experience-weighted)

### `scrape_nba.py`
Fetches detailed box scores + player stats from NBA.com (faster + more complete than nba_api).

**Syncs:**
- Player traditional box scores (PTS, REB, AST, etc.)
- Advanced stats (OFFRTG, NETRTG, etc.)
- Shooting splits (2PT%, 3PT%, etc.)

### `get_hustle_and_summary.py`
Fetches:
- Hustle stats (contested shots, loose balls, deflections)
- Game summaries (includes ESPN BPI win probability projections)

### `roster_summary_fetcher.py`
Fetches active roster snapshots per game date.

Used later for features: `diff_active_players`, `diff_dnp_count`

### `parse_bpi.py`, `parse_sag.py`
Parse ESPN/Sagarin rating CSV/HTML exports into `Sagarin.parquet`.

**Requires manual CSV/download:** ESPN BPI and Sagarin ratings are not exposed via public API, so we parse HTML/CSV dumps.

---

## 🗂️ Output Structure

After a sync, `data/` contains:

```
data_curation/data/
├── GamesInfo.parquet                          (all games)
├── BoxScoresTradPre.parquet
├── BoxScoresTradRegular.parquet
├── BoxScoresTradPlayoffs.parquet
├── AdvBoxScoresTradPre.parquet
├── AdvBoxScoresTradRegular.parquet
├── AdvBoxScoresTradPlayoffs.parquet
├── AdvBoxScoresFourFactorsPre.parquet
├── ... (and Misc, Scoring variants)
├── HustlestatsPre.parquet
├── Hustle statsRegular.parquet
├── Hustle statsPlayoffs.parquet
├── MasseyRatings.parquet                      (auto-rebuilt each sync)
├── Sagarin.parquet                            (manual update)
├── PlayerBoxScores.parquet
├── Arenas.parquet
├── OfficialCrews.parquet
├── TeamRosters.parquet
└── team_mappings.parquet                      (reference only)
```

---

## ⚠️ Known Issues & Gaps

| Issue | Impact | Workaround |
|-------|--------|-----------|
| Sagarin ratings are not API-exposed | Features rely on manual HTML parse | Download CSV from massey.rating.net, run `parse_sag.py` |
| ESPN BPI exposure is undocumented | Limited historical BPI | Parse from game summaries (see `parse_bpi.py`) |
| nba_api v3 playbyplay is slow | Can't fetch live PBP for in-game updates | Consider caching; may need rate limiting |
| OfficialCrews data is sparse | Referee features have many NaN | Backfill via scrape_usatoday.py when available |

---

## 🔧 Configuration

- **Season:** Defaults to current season; override with `--season 2025-26`
- **Workers:** Parallel fetch threads; default 3. Increase for faster sync (but watch ESPN rate limits).
- **Dry-run:** Show what would be synced without writing: `--dry-run`

---

## 🚀 Common Operations

### Sync all missing games
```bash
python data_curation/scripts/sync_games.py
```

### Sync only 2024-25 season
```bash
python data_curation/scripts/sync_games.py --season 2024-25
```

### Dry-run to see what would sync
```bash
python data_curation/scripts/sync_games.py --dry-run
```

### Inspect a parquet
```bash
python -c "import pandas as pd; df = pd.read_parquet('data_curation/data/GamesInfo.parquet'); print(df.info()); print(df.head())"
```

### Rebuild Massey ratings manually (if corrupted)
```bash
python data_curation/scripts/build_massey_ratings.py
```

---

## 📌 Maintenance

**After adding a new data source:**
1. Add fetcher script (e.g., `get_new_endpoint.py`)
2. Call it from `sync_games.py`
3. Document the parquet schema here
4. Add unit test to `tests/test_sync_games.py`
5. Update `TODOS.md` with status

---

## 📚 References

- **nba_api:** https://github.com/swar/nba_api (v3 branch)
- **ESPN API docs:** `data_curation/api_docs/espn_api_docs/`
- **Massey matrix:** https://www.masseyratings.com/
- **Team mappings:** `data_curation/data/team_mappings.parquet` (reference for ESPN ↔ NBA ID mapping)
