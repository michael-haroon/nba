# Documentation Index

**Last Updated:** 2026-05-27

Quick reference for all documentation in this project. Start here if you're new.

---

## 🚀 New to the Project?

1. **Read first:** [`README.md`](README.md) — 5 min overview of the entire system
2. **Understand the flow:** [`ARCHITECTURE.md`](ARCHITECTURE.md) — visual diagram + entry points
3. **Learn the rules:** [`CLAUDE.md`](CLAUDE.md) — project policy + data leakage prevention
4. **Pick your module** (see below)

---

## 📚 Documentation by Topic

### System Overview
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`README.md`](README.md) | System overview, quick start, pipeline flow | 5 min |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Visual diagrams, file structure, entry points, data flow | 10 min |
| [`DOC_INDEX.md`](DOC_INDEX.md) | This file — navigation guide | 2 min |

### Policy & Guidelines
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`CLAUDE.md`](CLAUDE.md) | Project requirements, behavioral rules, data leakage prevention | 10 min |
| [`TODOS.md`](TODOS.md) | Current work, blockers, sprint items | 3 min |

### Quality & Verification
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`SYSTEM_REVIEW.md`](SYSTEM_REVIEW.md) | Verification checklists, red flags, recovery steps | 10 min |

### Module Documentation
| Module | Documentation | Key Topics |
|--------|---------------|-----------|
| **Data Curation** | [`data_curation/README.md`](data_curation/README.md) | Data sources, parquet schema, sync workflow, known gaps |
| **Feature Pipeline** | [`feature_pipeline/README.md`](feature_pipeline/README.md) | Feature engineering, importance analysis, quality checks |
| | [`feature_pipeline/FEATURES.md`](feature_pipeline/FEATURES.md) | Complete inventory of 100+ features + tiers |
| | [`feature_pipeline/TARGETS.md`](feature_pipeline/TARGETS.md) | Prediction targets (winner, spread, series, OT, etc.) |
| **Strategy** | [`strategy/README.md`](strategy/README.md) | Model training, evaluation, cross-validation |
| | [`strategy/RISK_MANAGEMENT.md`](strategy/RISK_MANAGEMENT.md) | Position sizing, Kelly criterion, confidence intervals |
| **Backtesting** | `backtest/README.md` (TODO) | Market matching, fill simulation, P&L tracking |

---

## 🎯 Common Questions

### "I just cloned this repo, what do I do?"
→ Read [`README.md`](README.md) first, then [`ARCHITECTURE.md`](ARCHITECTURE.md)

### "How do I fetch new games?"
→ See [`data_curation/README.md`](data_curation/README.md) or run: `python data_curation/scripts/sync_games.py`

### "How do I add a new feature?"
→ See [`feature_pipeline/README.md`](feature_pipeline/README.md) section "Example: Adding a New Feature"

### "Why is my model accuracy so low?"
→ Check [`SYSTEM_REVIEW.md`](SYSTEM_REVIEW.md) for red flags and recovery steps

### "What features can I use?"
→ See [`feature_pipeline/FEATURES.md`](feature_pipeline/FEATURES.md) — all 100+ features listed with tiers

### "How do I prevent data leakage?"
→ See [`CLAUDE.md`](CLAUDE.md) section "CRITICAL: DATA LEAKAGE PREVENTION"

### "How do I train a model?"
→ See [`strategy/README.md`](strategy/README.md) section "Example: Train a Model"

### "What's the status of the project?"
→ Check [`TODOS.md`](TODOS.md) for current work and blockers

---

## 🔄 Pipeline Tour

```
START → README.md (overview)
          ↓
        ARCHITECTURE.md (understand the flow)
          ↓
        CLAUDE.md (understand the rules)
          ↓
        Pick a task:
          ├─ Fetch data → data_curation/README.md
          ├─ Engineer features → feature_pipeline/README.md
          ├─ Train models → strategy/README.md
          ├─ Add new feature → feature_pipeline/FEATURES.md + README.md
          └─ Debug issue → SYSTEM_REVIEW.md
          ↓
        Work on code
          ↓
        Verify → SYSTEM_REVIEW.md (quick checklist)
          ↓
        Commit + update docs
          ↓
        END
```

---

## 📂 File Structure Quick Reference

```
nba/
├── README.md                           ← Start here
├── ARCHITECTURE.md                     ← System diagram
├── CLAUDE.md                           ← Project policy
├── TODOS.md                            ← Current work
├── DOC_INDEX.md                        ← You are here
├── SYSTEM_REVIEW.md                    ← Verification
│
├── data_curation/
│   ├── README.md                       ← Data sources + workflow
│   ├── data/                           ← Parquets (generated)
│   └── scripts/                        ← Fetchers
│       ├── sync_games.py               ← Main entry point
│       ├── build_massey_ratings.py
│       └── ...
│
├── feature_pipeline/
│   ├── README.md                       ← Feature engineering guide
│   ├── FEATURES.md                     ← All features + tiers
│   ├── TARGETS.md                      ← Prediction targets
│   ├── build_features_only.py          ← Fast build (no analysis)
│   ├── engineering/
│   │   ├── data_loader.py
│   │   ├── game_builder.py
│   │   ├── feature_engineering.py
│   │   └── feature_utils.py
│   └── analysis/
│       ├── run.py                      ← Main entry point
│       └── feature_importance.py
│
├── strategy/
│   ├── README.md                       ← Model training guide
│   ├── RISK_MANAGEMENT.md              ← Position sizing
│   ├── run.py                          ← Main entry point
│   ├── config.py                       ← Hyperparameters
│   ├── data.py                         ← Data loading
│   ├── models.py                       ← Model builders
│   ├── train.py                        ← CV loop
│   └── evaluate.py                     ← Metrics
│
├── backtest/
│   ├── run.py                          ← Main entry point
│   ├── match_markets.py
│   ├── quoting.py
│   └── kalshi_client.py
│
└── output/                             ← Generated outputs
    └── features/
        ├── winner/
        └── spread/
```

---

## ⚡ Quick Commands

```bash
# Fetch new games + rebuild Massey ratings
python data_curation/scripts/sync_games.py

# Build features (fast, no analysis)
python -m feature_pipeline.build_features_only --output-dir output/features/winner

# Analyze feature importance (full pipeline)
python -m feature_pipeline.analysis.run --target winner

# Train all models
python -m strategy.run

# Train only winner model
python -m strategy.run --target winner

# Verify system health
python SYSTEM_REVIEW.md  # Just follow the checklist
```

---

## 🏆 What Each Module Does

### `data_curation/`
**Fetches + normalizes NBA data from ESPN/NBA.com**
- ✅ Input: ESPN APIs, NBA.com, Massey.com
- ✅ Output: 12+ parquets (games, box scores, ratings, rosters)
- ✅ Documentation: [`data_curation/README.md`](data_curation/README.md)

### `feature_pipeline/`
**Transforms data into 100+ ML features + ranks by importance**
- ✅ Input: 12+ parquets from data curation
- ✅ Output: game_features.parquet + importance rankings
- ✅ Documentation: [`feature_pipeline/README.md`](feature_pipeline/README.md), [`FEATURES.md`](feature_pipeline/FEATURES.md)

### `strategy/`
**Trains models to predict game outcomes**
- ✅ Input: game_features.parquet
- ✅ Output: model.pkl, predictions, trade recommendations
- ✅ Documentation: [`strategy/README.md`](strategy/README.md), [`RISK_MANAGEMENT.md`](strategy/RISK_MANAGEMENT.md)

### `backtest/`
**Simulates trades against Kalshi markets**
- ✅ Input: predictions from strategy module
- ✅ Output: P&L report, overfitting signals
- ⏳ Documentation: `backtest/README.md` (TODO)

---

## 🚨 Critical Files

These files contain essential information:

| File | Why It Matters |
|------|----------------|
| `CLAUDE.md` | Project policy + data leakage rules |
| `FEATURES.md` | Complete feature inventory (100+) |
| `strategy/config.py` | Model hyperparameters |
| `data_curation/data/team_mappings.parquet` | ESPN ↔ NBA API mapping |
| `data_curation/logs/sync_games.log` | Data sync history |

---

## 📝 Keeping Docs Updated

After making changes, update these files:

| Change | Update File |
|--------|------------|
| Add a new feature | `feature_pipeline/FEATURES.md` |
| Add a data source | `data_curation/README.md` |
| Change model hyperparameters | `strategy/README.md` + `strategy/config.py` |
| Add a prediction target | `feature_pipeline/TARGETS.md` |
| Discover data gap | `data_curation/README.md` "Known Issues" |
| Update project policy | `CLAUDE.md` |
| Current work / blockers | `TODOS.md` |

---

## 🆘 Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Model accuracy < 0.52 | Feature quality | [`SYSTEM_REVIEW.md`](SYSTEM_REVIEW.md) "Data Leakage Detection" |
| Kendall's tau < 0.7 | Feature importance | [`SYSTEM_REVIEW.md`](SYSTEM_REVIEW.md) "Red Flags" |
| Data sync failed | Logs | `tail -100 data_curation/logs/sync_games.log` |
| Feature NaN > 50% | Data coverage | [`data_curation/README.md`](data_curation/README.md) "Known Issues" |
| Import errors | Dependencies | Check `requirements.txt` + conda environment |

---

## 🎓 Learning Path

**If you're new and have 30 minutes:**
1. README.md (5 min)
2. ARCHITECTURE.md (10 min)
3. Pick one module README (10 min)
4. Explore the code (5 min)

**If you have 2 hours:**
1. README.md (5 min)
2. ARCHITECTURE.md (10 min)
3. CLAUDE.md (10 min)
4. All module READMEs (40 min)
5. Skim FEATURES.md (10 min)
6. Try a quick sync + feature build (25 min)

**If you have more time:**
Read everything + run all commands + verify with SYSTEM_REVIEW.md

---

## 📞 Getting Help

| Question | Answer |
|----------|--------|
| Where do I start? | [`README.md`](README.md) |
| How does the system work? | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| What are the rules? | [`CLAUDE.md`](CLAUDE.md) |
| How do I debug? | [`SYSTEM_REVIEW.md`](SYSTEM_REVIEW.md) |
| How do I do X? | [`TODOS.md`](TODOS.md) or search module READMEs |
| Is the system healthy? | Run SYSTEM_REVIEW.md checklist |

---

**Generated:** 2026-05-27  
**For updates:** See memory record `project_documentation_structure.md`
