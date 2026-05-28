# NBA Prediction Markets System

This repository implements an end-to-end machine learning system for trading NBA games on Kalshi, following the de Prado framework outlined in `CLAUDE.md`. The system follows a linear pipeline: **data curation → feature engineering → strategy → backtesting**.

---

## 📊 Pipeline Overview

```
DATA CURATION
  ├─ fetch games, box scores, rosters
  ├─ sync ratings (BPI, Sagarin, Massey)
  └─ output: parquet files in data_curation/data/
        ↓
FEATURE ENGINEERING
  ├─ build game-level rows (home vs away)
  ├─ engineer 100+ features (ratings, rolling stats, momentum, travel, refs)
  ├─ run feature analysis (MDI/MDA/SFI/PCA)
  └─ output: game_features.parquet + feature importance rankings
        ↓
STRATEGY
  ├─ train multiple models (LGBM, LogReg, Ridge, etc.)
  ├─ cross-validate with PurgedYearKFold (prevent temporal leakage)
  ├─ compare winner/spread predictions
  └─ output: model.pkl + predictions + trade recs
        ↓
BACKTESTING
  ├─ match predictions to Kalshi markets
  ├─ simulate fills + slippage
  ├─ detect overfitting signals
  └─ evaluate P&L
```

---

## 🗂️ Directory Structure

### `data_curation/`
**Fetches and curates raw NBA data from ESPN/NBA.com.**

- **`data/`** — parquet files (games, box scores, rosters, ratings)
  - `GamesInfo.parquet` — game IDs, dates, teams, arenas
  - `BoxScoresTrad*.parquet` — traditional box scores (PTS, FGM, REB, etc.)
  - `AdvBoxScores*.parquet` — advanced stats (OFFRTG, NETRTG, etc.)
  - `Hustlestats*.parquet` — hustle metrics
  - `MasseyRatings.parquet` — Massey matrix solution (built by `build_massey_ratings.py`)
  - `Sagarin.parquet` — Sagarin ratings (BPI, Elo, Predictor, etc.)
  - `PlayerBoxScores.parquet` — per-player game stats
  - `Arenas.parquet` — venue info (capacity, location)
  - `OfficialCrews.parquet` — referee crew info
  - `TeamRosters.parquet` — active rosters per date

- **`scripts/`** — data fetchers
  - `sync_games.py` — **Main data sync entrypoint**. Fetches new games from nba_api, rebuilds Massey ratings. Use: `python data_curation/scripts/sync_games.py --season 2025-26`
  - `build_massey_ratings.py` — Solves Massey matrix using game results
  - `scrape_nba.py` — Fetches detailed player+hustle stats from NBA.com
  - `get_hustle_and_summary.py` — Hustle stats + game summaries
  - `roster_summary_fetcher.py` — Active roster snapshots
  - `parse_bpi.py`, `parse_sag.py` — Parses ESPN/Sagarin ratings
  - Obsolete: `build_game_id_map.py`, `get_player_data.py` (scheduled for cleanup)

- **`api_docs/`** — ESPN/NBA.com API schema documentation (read-only reference)

### `feature_pipeline/`
**Transforms raw data into ML-ready features and analyzes feature importance.**

- **`engineering/`** — feature construction
  - `data_loader.py` — Loads all parquets into memory (games, ratings, rosters, etc.)
  - `game_builder.py` — Creates game rows (home vs away, targets, playoff flags)
  - `feature_engineering.py` — Computes 100+ features:
    - Rating features (BPI, Sagarin, Massey with context adjustments)
    - Rolling box score stats (5/10/20 game windows)
    - Momentum features (win streaks, CUSUM, Shannon entropy)
    - Travel + crowd + referee features
    - Random combinations (de Prado weak learners)
  - `feature_utils.py` — Helpers (fillna, encode, normalize)

- **`analysis/`** — feature importance analysis
  - `feature_importance.py` — MDI/MDA/SFI pipeline + PCA cross-check
  - `run.py` — Runs full analysis pipeline (cluster, rank, filter features)

- **`FEATURES.md`** — Complete feature inventory and selection criteria
- **`TARGETS.md`** — Prediction targets (winner, spread, total, series, OT, etc.)
- **`build_features_only.py`** — Build game_features.parquet without analysis (faster iteration)

**Output:** `output/features/{target}/game_features.parquet` + feature rankings

### `strategy/`
**Trains and evaluates prediction models.**

- **`models.py`** — Model builders
  - `build_classifier()` — LGBM/LogReg/SVC/Naive Bayes (winner prediction)
  - `build_regressor()` — LGBM/Ridge/Lasso/SVR (spread prediction)
  - Hyperparameters tuned per model

- **`train.py`** — Training loop
  - PurgedYearKFold cross-validation (no temporal leakage)
  - Per-fold: train on prior seasons/years, validate on future
  - Tracks OOF predictions for model stacking

- **`data.py`** — Feature loader
  - Loads `game_features.parquet`
  - Aligns columns to feature list
  - Fillna with column medians (matches pipeline)
  - Returns (X, y, seasons) for training

- **`config.py`** — Model hyperparameters, feature lists, CV settings
- **`evaluate.py`** — Metrics + residual analysis
- **`run.py`** — Main entry point: `python -m strategy.run --target winner`
- **`RISK_MANAGEMENT.md`** — Position sizing, Kelly criterion notes

**Output:** `strategy/output/{target}/` with models, predictions, trade recs

### `backtest/`
**Simulates trades against Kalshi API.**

- `run.py` — Main backtest loop
- `match_markets.py` — Maps predictions to Kalshi contracts
- `quoting.py` — Simulates order fills + slippage
- `kalshi_client.py` — Kalshi API wrapper

### `tests/`
**Unit tests (currently minimal).**

- `test_sync_games.py` — Data sync tests
- `test_massey_ratings.py` — Massey solver tests
- `test_game_model.py` — Game row building tests

### `notebooks/`
**Interactive exploration (for reference only, not part of pipeline).**

- `tedious.ipynb` — EDA on ratings + features

### `output/`
**Pipeline outputs (generated, not committed).**

- `output/features/{winner|spread|total|series}/`
  - `game_features.parquet` — final feature matrix
  - `feature_importance_mdi.json` — MDI ranks
  - `feature_importance_mda.json` — MDA ranks
  - `feature_importance_sfi.json` — SFI ranks
  - `kendall_tau.json` — PCA vs supervised ranks correlation

---

## ⚙️ Quick Start

### 1. Setup
```bash
conda activate pred
cd ~/Projects/prediction_markets/nba
```

### 2. Data Curation
```bash
# Fetch new games and rebuild Massey ratings
python data_curation/scripts/sync_games.py --season 2025-26

# View sync log
tail -f data_curation/logs/sync_games.log
```

**Output:** Updated parquets in `data_curation/data/`

### 3. Build Features
```bash
# Fast: just compute features (no importance analysis)
python -m feature_pipeline.build_features_only --output-dir output/features/winner

# Full: compute features + run analysis (MDI/MDA/SFI/PCA)
python -m feature_pipeline.analysis.run --target winner
```

**Output:** `output/features/winner/game_features.parquet` + importance JSONs

### 4. Train Strategy
```bash
# Train both winner + spread models
python -m strategy.run

# Or just one target
python -m strategy.run --target winner
```

**Output:** Models + CV results in `strategy/output/`

### 5. Backtest
```bash
python backtest/run.py
```

---

## 🚨 Critical Guidelines

### Data Leakage Prevention
**All features must come from BEFORE the game date.** See `CLAUDE.md` for details:
- Ratings from day T can only predict games on T+1+
- Purging in cross-validation prevents temporal overlap
- Same-game box scores are outcomes, not features
- Ask: "Could I know this value before tipoff?"

### Feature Engineering
1. Features are ranked by MDI/MDA/SFI (de Prado framework)
2. PCA cross-check: weighted Kendall's tau ≥ 0.7 indicates no overfitting
3. Features must pass STRONG or MODERATE tier in ≥2 of {MDI, MDA, SFI}
4. Update `feature_pipeline/FEATURES.md` after adding features

### Model Training
- Cross-validation: PurgedYearKFold (leave-one-season-out)
- Calibration: Compare CV loss to OOF loss (detect overfitting)
- Spread models: Residuals must be analyzed for outliers

---

## 📝 Key Files to Know

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project requirements + behavioral guidelines |
| `TODOS.md` | Ongoing work + blockers |
| `feature_pipeline/FEATURES.md` | Complete feature inventory |
| `data_curation/data/team_mappings.parquet` | ESPN ↔ NBA API team ID mapping (reference) |
| `strategy/config.py` | Model hyperparameters + feature lists |
| `.env` | Kaggle API key (for nba_api access) |

---

## 🔄 Data Sync Workflow

When new NBA games complete:

1. **Manual trigger:** `python data_curation/scripts/sync_games.py`
2. **Dry-run mode:** `python data_curation/scripts/sync_games.py --dry-run` (shows what would be synced)
3. **Auto rebuild:** After sync completes, Massey ratings are rebuilt automatically
4. **Circuit breaker:** If sync fails, script logs error and exits without corrupting data

---

## 🧪 Testing

```bash
pytest tests/
```

Current test coverage:
- Data sync + parquet writing
- Massey matrix solver
- Game row building + target computation
- (Missing: feature engineering tests, model tests — PRs welcome)

---

## 🛠️ Common Tasks

### Add a new feature
1. Implement in `feature_pipeline/engineering/feature_engineering.py`
2. Call it from `build_features_only.py`
3. Document in `feature_pipeline/FEATURES.md`
4. Run `python -m feature_pipeline.analysis.run --target winner` to rank importance

### Debug data issues
```bash
# Load + inspect a parquet
python -c "import pandas as pd; df = pd.read_parquet('data_curation/data/GamesInfo.parquet'); print(df.info()); print(df.head())"

# Check for missing features
python -c "import pandas as pd; df = pd.read_parquet('output/features/winner/game_features.parquet'); print(df.isnull().sum())"
```

### Generate predictions for a specific date range
```python
# In strategy/run.py or a notebook:
from strategy.data import load
X, y, seasons = load("winner")
# Filter to specific dates, predict
```

---

## 📚 References

- **de Prado framework** → Advances in Financial Machine Learning (AFML)
- **Data leak prevention** → CLAUDE.md "CRITICAL: DATA LEAKAGE PREVENTION"
- **Massey ratings** → Massey matrix (least-squares game outcome fitting)
- **PurgedYearKFold** → mlfinlab.modeling_utils.cross_validation
- **Kalshi API** → backtest/kalshi_client.py

---

## 🚀 Next Steps

See `TODOS.md` for:
- Automatic daily data curation
- Play-by-play data integration
- Player prop predictions
- Live market sync

---

Generated: 2026-05-27
Last updated in MEMORY: Check project_data_curation.md + project_ensembling_plan.md for ongoing work details.
