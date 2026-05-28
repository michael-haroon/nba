# System Review Checklist

Use this document to verify the integrity of the pipeline and identify issues.

---

## ✅ Data Curation Verification

**Run:** `python data_curation/scripts/sync_games.py --dry-run`

- [ ] Last sync completed without errors (check `data_curation/logs/sync_games.log`)
- [ ] `GamesInfo.parquet` has games from current season
- [ ] `MasseyRatings.parquet` was rebuilt after last sync (check timestamp)
- [ ] All BoxScores*.parquet files exist and have consistent schema
- [ ] Sagarin.parquet has recent ratings (within last week)
- [ ] `team_mappings.parquet` maps all teams in GamesInfo

**Command to check:**
```bash
tail -20 data_curation/logs/sync_games.log
python -c "
import pandas as pd
games = pd.read_parquet('data_curation/data/GamesInfo.parquet')
print(f'Latest game: {games[\"game_date\"].max()}')
print(f'Total games: {len(games)}')
print(f'Seasons: {games[\"season\"].unique()}')
"
```

---

## ✅ Feature Engineering Verification

**Run:** `python -m feature_pipeline.build_features_only --output-dir output/features/winner`

- [ ] `game_features.parquet` exists and has > 1000 rows
- [ ] Feature count: 100+ features present
- [ ] Column names follow naming convention (`diff_*`, `home_*`, `away_*`, `rc_*`)
- [ ] No columns are all NaN
- [ ] Target column present (e.g., `target_winner`)

**Command to check:**
```bash
python -c "
import pandas as pd
df = pd.read_parquet('output/features/winner/game_features.parquet')
print(f'Shape: {df.shape}')
print(f'NaN counts (top 10):', df.isnull().sum().nlargest(10).to_dict())
print(f'Memory usage: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB')
"
```

---

## ✅ Feature Importance Verification

**Run:** `python -m feature_pipeline.analysis.run --target winner`

- [ ] `feature_importance_mdi.json` exists and has 50+ features ranked
- [ ] `feature_importance_mda.json` exists
- [ ] `feature_importance_sfi.json` exists
- [ ] `kendall_tau.json` shows correlation between supervised and unsupervised ranks
- [ ] Kendall's tau value is ≥ 0.7 (indicates no overfitting)
- [ ] No feature has MDI rank = NaN (indicates training issue)

**Command to check:**
```bash
python -c "
import json
with open('output/features/winner/kendall_tau.json') as f:
    kt = json.load(f)
    print(f'Kendall tau (PCA vs MDI): {kt.get(\"kendall_tau_mdi\", \"N/A\")}')
    print(f'Kendall tau (PCA vs MDA): {kt.get(\"kendall_tau_mda\", \"N/A\")}')
    print(f'Status: {kt.get(\"status\", \"Unknown\")}')
"
```

**Green flag:** Kendall's tau ≥ 0.7 (overfitting unlikely)  
**Yellow flag:** 0.5 < tau < 0.7 (questionable, investigate)  
**Red flag:** tau < 0.5 (probable overfitting, drop bottom features)

---

## ✅ Model Training Verification

**Run:** `python -m strategy.run --target winner`

- [ ] All models trained successfully (LGBM, LogReg, Ridge, SVC, Naive Bayes)
- [ ] CV results: accuracy ≥ 0.52 for winner prediction (baseline: 0.50)
- [ ] CV results: AUC ≥ 0.55 for winner prediction
- [ ] Overfitting check: `(train_accuracy - oof_accuracy) < 0.10`
- [ ] `model.pkl` exists and is loadable
- [ ] `oof_preds.csv` has columns: pred_prob, actual_winner, correct

**Command to check:**
```bash
python -c "
import pandas as pd
cv_results = pd.read_csv('strategy/output/winner/cv_results.csv')
print(cv_results.groupby('model')[['val_accuracy', 'val_auc']].mean())
print()
oof = pd.read_csv('strategy/output/winner/oof_preds.csv')
print(f'OOF accuracy: {(oof[\"pred_class\"] == oof[\"actual\"]).mean():.3f}')
"
```

**Green flag:** Accuracy ≥ 0.55, AUC ≥ 0.60  
**Yellow flag:** 0.52 ≤ accuracy < 0.55  
**Red flag:** accuracy < 0.52 (model not learning signal)

---

## ✅ Data Leakage Detection

**Check:** Features contain only pre-game data

**Manual inspection:**
```bash
python -c "
import pandas as pd
df = pd.read_parquet('output/features/winner/game_features.parquet')

# Should NOT have these columns (post-game data):
forbidden = ['home_pts', 'away_pts', 'home_fgm', 'away_fgm', 'home_offrtg', 'away_offrtg']
found = [c for c in forbidden if c in df.columns]
if found:
    print(f'⚠️ LEAKAGE DETECTED: {found}')
else:
    print('✅ No obvious post-game features found')

# Should have these (pre-game data):
required = ['diff_bpi', 'diff_sag_rating', 'diff_roll5_pts', 'diff_days_rest']
missing = [c for c in required if c not in df.columns]
if missing:
    print(f'⚠️ MISSING PRE-GAME FEATURES: {missing}')
else:
    print('✅ All core pre-game features present')
"
```

**Check rolling features for leakage:**
- Rolling stats should use **prior games only**
- If a rolling stat has same-game data, it's leakage
- Check: `diff_roll5_pts` excludes the game being predicted

---

## ✅ Model Generalization

**Cross-validation type:** PurgedYearKFold (temporal, no leakage)

**Verify:**
- [ ] CV folds are season-based (Fold 0: train 2019-2021, test 2022, etc.)
- [ ] No date overlap between train and test splits
- [ ] Out-of-fold (OOF) predictions cover entire dataset with no overlap

**Command to check:**
```bash
python -c "
# This should be in strategy/train.py
# Verify PurgedYearKFold is being used, not RandomKFold
with open('strategy/train.py') as f:
    content = f.read()
    if 'PurgedYearKFold' in content:
        print('✅ Using PurgedYearKFold (correct)')
    else:
        print('⚠️ NOT using PurgedYearKFold (potential leakage)')
"
```

---

## ✅ Documentation Completeness

- [ ] `README.md` exists and links to all submodule READMEs
- [ ] `ARCHITECTURE.md` exists with full system diagram
- [ ] `CLAUDE.md` is up-to-date with latest requirements
- [ ] `data_curation/README.md` documents all parquets
- [ ] `feature_pipeline/README.md` documents feature engineering
- [ ] `feature_pipeline/FEATURES.md` lists all 100+ features with tiers
- [ ] `feature_pipeline/TARGETS.md` lists all prediction targets
- [ ] `strategy/README.md` documents model training
- [ ] `strategy/RISK_MANAGEMENT.md` documents position sizing

**Command to check:**
```bash
for file in README.md ARCHITECTURE.md CLAUDE.md; do
    [ -f $file ] && echo "✅ $file" || echo "❌ $file"
done

for file in data_curation/README.md feature_pipeline/README.md strategy/README.md; do
    [ -f $file ] && echo "✅ $file" || echo "❌ $file"
done
```

---

## ✅ Code Quality

- [ ] No uncommitted changes to critical files (check `git status`)
- [ ] Recent commits have clear messages (check `git log --oneline | head -5`)
- [ ] Tests pass: `pytest tests/` (if applicable)
- [ ] No obvious circular imports in Python modules
- [ ] Feature lists are consistent between FEATURES.md and code

**Command to check:**
```bash
# Check git status
git status --short | grep -E "^ M|^\?\?" | head -10

# Check recent commits
git log --oneline | head -5

# Check for circular imports (Python)
python -c "import feature_pipeline; import strategy; print('✅ No import errors')" 2>&1
```

---

## ⚠️ Red Flags

| Flag | What to Check | Action |
|------|---------------|--------|
| **Kendall's tau < 0.5** | Probable overfitting | Drop bottom 20% of features by tier |
| **Model accuracy < 0.52** | Not learning signal | Check feature quality + data leakage |
| **OOF loss >> train loss** | Temporal leakage or distribution shift | Review CV strategy + feature alignment |
| **Many features with NaN > 50%** | Data quality issue | Check data_curation logs + rebuild |
| **Last sync > 1 week old** | Stale data | Run `python data_curation/scripts/sync_games.py` |
| **Kendall's tau = NaN** | PCA analysis failed | Rerun `python -m feature_pipeline.analysis.run` |

---

## 🔧 Recovery Steps

### If data sync fails:
```bash
# Check log
tail -100 data_curation/logs/sync_games.log

# Retry with detailed output
python data_curation/scripts/sync_games.py --dry-run

# If issue persists, rebuild one parquet
python data_curation/scripts/build_massey_ratings.py
```

### If feature engineering fails:
```bash
# Check which feature is causing the issue
python -c "from feature_pipeline.engineering.feature_engineering import *"

# Reduce complexity
export N_RANDOM_COMBOS=10  # Reduce random combinations
python -m feature_pipeline.build_features_only
```

### If model training fails:
```bash
# Check data loading
python -c "from strategy.data import load; X, y, s = load('winner'); print(X.shape, y.shape)"

# Try one model at a time
python -c "from strategy.models import build_classifier; m = build_classifier('lgbm'); print(m)"

# Check CV setup
python -c "from strategy.train import train_and_evaluate; print('Import successful')"
```

### If Kendall's tau < 0.7:
```bash
# Inspect feature importance
python -c "
import json
with open('output/features/winner/feature_importance_mdi.json') as f:
    mdi = json.load(f)
    # Bottom features (most likely to cause overfitting)
    bottom_20 = sorted(mdi.items(), key=lambda x: x[1])[:20]
    print('Bottom 20 features by MDI:', [f[0] for f in bottom_20])
"

# Drop bottom features and retrain
# (modify strategy/config.py to exclude them)
```

---

## 📋 Quick Checklist (Weekly)

```
Every week, run:

[ ] python data_curation/scripts/sync_games.py --dry-run
[ ] python -m feature_pipeline.build_features_only --output-dir output/features/winner
[ ] python -c "import pandas as pd; df = pd.read_parquet('output/features/winner/game_features.parquet'); print(f'Latest game: {df[\"game_date\"].max()}')"
[ ] tail -20 data_curation/logs/sync_games.log
[ ] git status  # Check for uncommitted changes
```

If all pass: ✅ System is healthy  
If any fail: Check corresponding section above + take recovery steps

---

Generated: 2026-05-27
