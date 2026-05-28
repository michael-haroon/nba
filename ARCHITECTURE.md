# NBA Prediction System Architecture

This document provides a visual map of the entire system for engineers joining the project.

---

## 📊 System Blocks

```
┌─────────────────────────────────────────────────────────────────┐
│                  NBA PREDICTION MARKETS SYSTEM                   │
│                 (de Prado Framework Implementation)              │
└─────────────────────────────────────────────────────────────────┘

    [1] DATA CURATION
    ─────────────────
    Raw data → Normalize → Parquets
    
    Input:  ESPN API, NBA.com, Massey.com
    Output: 12+ parquets (games, box scores, ratings, rosters)
    Code:   data_curation/
    Docs:   data_curation/README.md
    
         ↓
    
    [2] FEATURE ENGINEERING
    ──────────────────────
    Parquets → Build game rows → Compute 100+ features → Importance analysis
    
    Input:  12+ parquets from [1]
    Output: game_features.parquet (with survivors only)
    Code:   feature_pipeline/
    Docs:   feature_pipeline/README.md, FEATURES.md, TARGETS.md
    
         ↓
    
    [3] STRATEGY
    ───────────
    Features → Train models → CV → Rank models → Save winner
    
    Input:  game_features.parquet from [2]
    Output: model.pkl, oof_preds.csv, trade_recs.csv
    Code:   strategy/
    Docs:   strategy/README.md, RISK_MANAGEMENT.md
    
         ↓
    
    [4] BACKTESTING
    ───────────────
    Predictions → Match Kalshi markets → Simulate fills → Evaluate P&L
    
    Input:  predictions from [3], Kalshi market data
    Output: P&L report, overfitting signals
    Code:   backtest/
    Docs:   backtest/README.md (TODO)
```

---

## 🗂️ File Structure Tree

```
nba/
│
├── README.md                          ← Start here! System overview
├── ARCHITECTURE.md                    ← You are here
├── CLAUDE.md                          ← Project policy + behavioral rules
├── TODOS.md                           ← Current work + blockers
│
├── data_curation/
│   ├── README.md                      ← Data sources + sync workflow
│   ├── data/                          ← Parquets (generated, not committed)
│   │   ├── GamesInfo.parquet
│   │   ├── BoxScoresTrad*.parquet
│   │   ├── AdvBoxScores*.parquet
│   │   ├── Hustlestats*.parquet
│   │   ├── MasseyRatings.parquet      ← Key: auto-built by sync_games.py
│   │   ├── Sagarin.parquet
│   │   ├── PlayerBoxScores.parquet
│   │   ├── Arenas.parquet
│   │   ├── OfficialCrews.parquet
│   │   ├── TeamRosters.parquet
│   │   └── team_mappings.parquet      ← Reference only (ESPN ↔ NBA API)
│   │
│   ├── scripts/
│   │   ├── sync_games.py              ← ⭐ MAIN ENTRY: fetches new games
│   │   ├── build_massey_ratings.py
│   │   ├── scrape_nba.py
│   │   ├── get_hustle_and_summary.py
│   │   ├── roster_summary_fetcher.py
│   │   ├── parse_bpi.py
│   │   ├── parse_sag.py
│   │   └── ... (other minor fetchers)
│   │
│   ├── api_docs/                      ← Read-only ESPN/NBA schema
│   │   └── espn_api_docs/
│   │
│   └── logs/
│       └── sync_games.log
│
├── feature_pipeline/
│   ├── README.md                      ← Feature engineering + importance analysis
│   ├── FEATURES.md                    ← Complete feature inventory (100+ features)
│   ├── TARGETS.md                     ← Prediction targets (winner, spread, etc.)
│   ├── build_features_only.py         ← Fast: build features (no analysis)
│   │
│   ├── engineering/
│   │   ├── data_loader.py             ← Load all parquets into memory
│   │   ├── game_builder.py            ← Create game rows + targets
│   │   ├── feature_engineering.py     ← Compute 100+ features
│   │   └── feature_utils.py           ← Helpers (fillna, encode, etc.)
│   │
│   ├── analysis/
│   │   ├── run.py                     ← ⭐ MAIN ENTRY: importance analysis
│   │   ├── feature_importance.py      ← MDI/MDA/SFI/PCA ranking
│   │   └── eda.py                     ← Exploratory data analysis
│   │
│   └── eda_plots/                     ← Generated plots (not committed)
│
├── strategy/
│   ├── README.md                      ← Model training + evaluation
│   ├── RISK_MANAGEMENT.md             ← Position sizing, Kelly criterion
│   ├── run.py                         ← ⭐ MAIN ENTRY: train models
│   ├── config.py                      ← Hyperparameters + CV settings
│   ├── data.py                        ← Load features + targets
│   ├── models.py                      ← Model builders (LGBM, LogReg, SVC, etc.)
│   ├── train.py                       ← PurgedYearKFold CV loop
│   ├── evaluate.py                    ← Metrics + residual analysis
│   │
│   ├── output/                        ← Generated model artifacts
│   │   ├── winner/
│   │   │   ├── model.pkl
│   │   │   ├── oof_preds.csv
│   │   │   ├── cv_results.csv
│   │   │   └── trade_recs.csv
│   │   └── spread/
│   │       └── (same structure)
│   │
│   └── __pycache__/
│
├── backtest/
│   ├── README.md (TODO)               ← Backtesting workflow
│   ├── run.py                         ← Main backtest loop
│   ├── match_markets.py               ← Map predictions to Kalshi
│   ├── quoting.py                     ← Fill simulation
│   └── kalshi_client.py               ← Kalshi API wrapper
│
├── output/                            ← Pipeline outputs (generated, not committed)
│   └── features/
│       ├── winner/
│       │   ├── game_features.parquet
│       │   ├── feature_importance_mdi.json
│       │   ├── feature_importance_mda.json
│       │   ├── feature_importance_sfi.json
│       │   └── kendall_tau.json       ← PCA cross-check
│       ├── spread/
│       ├── total/
│       ├── series/
│       └── ... (other targets)
│
├── tests/
│   ├── test_sync_games.py
│   ├── test_massey_ratings.py
│   └── test_game_model.py
│
├── notebooks/
│   └── tedious.ipynb                  ← EDA (reference only)
│
└── kalshi_mcp.py                      ← Kalshi MCP server (local tool)
```

---

## 🔄 Data Flow Diagram

```
ESPN/NBA APIs              Massey.com
    ↓                           ↓
sync_games.py ←────────────────┴─── build_massey_ratings.py
    ↓
data_curation/data/*.parquet
    ↓
feature_pipeline/engineering/data_loader.py (load all)
    ↓
game_builder.py (create rows)
    ↓
feature_engineering.py (compute 100+ features)
    ↓
analysis/run.py (MDI/MDA/SFI + PCA)
    ↓
output/features/{target}/game_features.parquet
    ↓
strategy/data.py (align + fillna)
    ↓
strategy/train.py (PurgedYearKFold CV)
    ↓
strategy/models.py (train + evaluate)
    ↓
strategy/output/{target}/*.pkl, *.csv
    ↓
backtest/run.py (match + simulate fills)
    ↓
P&L report
```

---

## ⭐ Main Entry Points

When running the system, use these commands:

### 1. Fetch new games
```bash
python data_curation/scripts/sync_games.py
```
**What it does:** Queries ESPN/NBA APIs for new games, appends to parquets, rebuilds Massey.

### 2. Build features (fast, no analysis)
```bash
python -m feature_pipeline.build_features_only --output-dir output/features/winner
```
**What it does:** Computes 100+ features, saves game_features.parquet (5 min).

### 3. Analyze features (full, with importance)
```bash
python -m feature_pipeline.analysis.run --target winner
```
**What it does:** Importance analysis (MDI/MDA/SFI/PCA), filters survivors (30 min).

### 4. Train models
```bash
python -m strategy.run --target winner
```
**What it does:** Trains LGBM/LogReg/Ridge/SVC/etc. with PurgedYearKFold CV, saves best model.

### 5. Backtest
```bash
python backtest/run.py
```
**What it does:** Matches predictions to Kalshi markets, simulates fills, reports P&L.

---

## 🛡️ Critical Guidelines

### Data Leakage Prevention
**Ask for every feature: "Could I know this BEFORE tipoff?"**

- ✅ Safe: rolling 5-game average points, prior season rating, historical referee record
- ❌ Leakage: same-game box scores, real-time updates, post-game stats

See `CLAUDE.md` "CRITICAL: DATA LEAKAGE PREVENTION" for details.

### Feature Engineering
1. Implement → run analysis → check Kendall's tau (should be ≈0.7+)
2. Features must survive ≥2 of {MDI, MDA, SFI} to be included
3. Update `FEATURES.md` after adding features

### Model Training
1. Use PurgedYearKFold (no temporal overlap between train/test)
2. Compare OOF loss vs train loss to detect overfitting
3. Rank models by CV loss, not training loss

---

## 📚 Documentation Map

| If you want to... | Read... |
|-------------------|---------|
| Understand the full system | `README.md` (root) |
| See the architecture | `ARCHITECTURE.md` (you are here) |
| Understand policy | `CLAUDE.md` (root) |
| Fetch data | `data_curation/README.md` |
| Engineer features | `feature_pipeline/README.md` |
| Train models | `strategy/README.md` |
| Understand risk | `strategy/RISK_MANAGEMENT.md` |
| See all features | `feature_pipeline/FEATURES.md` |
| See current work | `TODOS.md` (root) |

---

## 🎯 Common Workflows

### Add a new feature
1. Code: `feature_pipeline/engineering/feature_engineering.py`
2. Call: `feature_pipeline/build_features_only.py`
3. Docs: `feature_pipeline/FEATURES.md`
4. Analyze: `python -m feature_pipeline.analysis.run --target winner`

### Fix a data issue
1. Check logs: `data_curation/logs/sync_games.log`
2. Inspect parquet: `python -c "import pandas as pd; pd.read_parquet(...)"`
3. Rerun sync: `python data_curation/scripts/sync_games.py`

### Improve model performance
1. Check feature importance: `strategy/output/{target}/feature_importance_*.json`
2. Drop bottom 20% features
3. Tune hyperparameters: `strategy/config.py`
4. Retrain: `python -m strategy.run --target winner`

---

## 🚀 Next Steps

- [ ] Automate daily data sync (cron + circuit breaker)
- [ ] Add playbyplay features
- [ ] Implement player prop models
- [ ] Ensemble voting (weighted avg of top 3 models)
- [ ] Live calibration on recent games

See `TODOS.md` for full list.

---

## 🤝 Getting Help

- **Code questions:** See module README (e.g., `feature_pipeline/README.md`)
- **Policy questions:** See `CLAUDE.md` (root)
- **Data issues:** Check `data_curation/README.md` + `data_curation/logs/sync_games.log`
- **Feature selection:** See `feature_pipeline/FEATURES.md` + `CLAUDE.md` leakage prevention
- **Model tuning:** See `strategy/README.md` + `strategy/RISK_MANAGEMENT.md`

---

Generated: 2026-05-27
