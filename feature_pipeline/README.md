# Feature Pipeline Module

**Purpose:** Transform raw data into ML-ready features and analyze importance to prevent overfitting.

---

## 🔄 Pipeline Flow

```
1. Load raw data (parquets + ratings)
   ↓
2. Build game rows (home vs away, targets)
   ↓
3. Engineer features (100+ predictors)
   ├─ ratings (BPI, Sagarin, Massey + context adjustments)
   ├─ rolling box score stats (5/10/20 game windows)
   ├─ momentum (streaks, CUSUM, entropy)
   ├─ travel + crowd + refs + roster
   └─ random combinations (weak learners)
   ↓
4. Compute diffs (home - away for each feature)
   ↓
5. Analyze importance (MDI/MDA/SFI) + PCA cross-check
   ↓
6. Filter + save game_features.parquet
```

---

## 📦 Submodules

### `engineering/data_loader.py`
**Loads all parquets + ratings into memory.**

```python
data = load_all(data_dir=None)  # Returns dict with:
# - box_scores: merged all BoxScores*.parquet
# - game_ids: GamesInfo.parquet
# - team_map: team_mappings.parquet
# - bpi: parsed from Sagarin.parquet
# - sagarin: full Sagarin ratings
# - massey: MasseyRatings.parquet
# - arenas: Arenas.parquet
# - game_summaries: ESPN summaries with BPI projections
# - officials: OfficialCrews.parquet
# - player_box_scores: PlayerBoxScores.parquet
```

### `engineering/game_builder.py`
**Creates game-level rows + prediction targets.**

```python
games = build_game_rows(box_scores, game_ids, team_map)
# Creates (home_team, away_team, game_date, season, ...) rows

games = build_targets(games)
# Adds: target_winner (1=home), target_spread, target_total, target_overtime, etc.

games = build_series_targets(games)  # Playoffs only
# Adds: target_series_winner, target_series_games, target_series_spread
```

### `engineering/feature_engineering.py`
**Computes 100+ features.** See `FEATURES.md` for complete inventory.

Key functions:

| Function | Output Features | Example |
|----------|-----------------|---------|
| `align_ratings_to_games()` | BPI, Sagarin, Massey (pregame, no lookahead) | `home_bpi`, `away_predictor`, `home_massey_context_adj` |
| `compute_rolling_features()` | Box score rolling stats (5/10/20 windows) | `home_roll5_pts`, `away_roll10_pts_std`, `home_roll20_offrtg` |
| `compute_score_momentum()` | Win streaks, margin trends, entropy | `home_win_streak`, `away_margin_last3`, `home_win_entropy` |
| `compute_context_features()` | Travel, crowd, rest, B2B | `away_travel_distance`, `crowd_density`, `diff_days_rest` |
| `compute_referee_features()` | Crew home win %, crew avg total | `crew_home_win_rate`, `crew_avg_total` |
| `compute_roster_features()` | Active players, DNP count | `home_active_players`, `away_dnp_count` |
| `compute_deprado_features()` | de Prado special: CUSUM, path features | `home_cusum_momentum`, `home_path_best_opp_seed` |
| `generate_random_combinations()` | 50 random weak learner combos | `rc_000` through `rc_049` |
| `compute_diffs()` | Home - Away for all numeric features | `diff_bpi = home_bpi - away_bpi` |

### `analysis/feature_importance.py`
**Ranks features using supervised + unsupervised methods.**

```python
from feature_pipeline.analysis.feature_importance import (
    cluster_features, 
    compute_mdi, compute_mda, compute_sfi,
    compute_pca_importance,
    rank_features
)

# 1. Cluster correlated features (ONC = optimal number of clusters)
clusters = cluster_features(X, method="onc")

# 2. Compute importance metrics
mdi_ranks = compute_mdi(model, X, feature_names)      # in-sample
mda_ranks = compute_mda(model, X, y_oof, feature_names)  # out-of-sample
sfi_ranks = compute_sfi(model, X, y, feature_names)  # single-feature

# 3. PCA cross-check (unsupervised importance)
pca_ranks = compute_pca_importance(X)

# 4. Weighted Kendall's tau between supervised + unsupervised
kendall_tau = weighted_kendall_tau(mdi_ranks, pca_ranks)  # Should be ≈ 0.7+ for no overfitting

# 5. Filter by tier (STRONG, MODERATE, WEAK)
survivors = rank_features(mdi_ranks, mda_ranks, sfi_ranks)
# Only keep features in STRONG/MODERATE tier in ≥2 of the 3 methods
```

### `analysis/run.py`
**Main analysis entry point.**

```bash
python -m feature_pipeline.analysis.run --target winner
```

**Outputs:**
- `output/features/winner/game_features.parquet` — final feature matrix (survivors only)
- `output/features/winner/feature_importance_mdi.json` — MDI ranks
- `output/features/winner/feature_importance_mda.json` — MDA ranks
- `output/features/winner/feature_importance_sfi.json` — SFI ranks
- `output/features/winner/kendall_tau.json` — PCA vs supervised Kendall's tau

---

## 📖 Configuration

### `config.py`
```python
MASSEY_CONTEXT_VARIANTS = ["location_adjusted", "crowd_adjusted", "crowd_weighted", ...]
ROLLING_WINDOWS = [5, 10, 20]  # Game windows for rolling stats
N_RANDOM_COMBOS = 50  # de Prado weak learners (scale to 500+ on GPU)
FEATURE_TIERS = {
    "STRONG": 2,    # Must appear in ≥2 of {MDI, MDA, SFI}
    "MODERATE": 1,
    "WEAK": 0,
}
```

### `FEATURES.md`
**Complete inventory of all engineered features** + which ones survived analysis.

---

## ⚡ Quick Workflows

### Fast: Build features without importance analysis
```bash
python -m feature_pipeline.build_features_only --output-dir output/features/winner
```
**Output:** `output/features/winner/game_features.parquet` (5 min runtime)

### Full: Compute features + analyze importance
```bash
python -m feature_pipeline.analysis.run --target winner
```
**Output:** Feature importance JSONs + survivors parquet (30 min runtime)

### Inspect feature importance
```python
import json
with open("output/features/winner/feature_importance_mdi.json") as f:
    mdi = json.load(f)
    print(sorted(mdi.items(), key=lambda x: x[1], reverse=True)[:20])
```

---

## 🚨 Critical: Data Leakage Prevention

**All features must come from BEFORE the game date.**

Examples of **SAFE** features (no leakage):
- Rolling 5-game average points (from prior games only)
- Rating from day T-1 (used for games on day T+)
- Historical referee win rates

Examples of **LEAKAGE** features (NEVER):
- Same-game box scores (PTS, FGM, etc.) — these are outcomes
- Real-time updates during the game
- Post-game adjustments

**Temporal check:** When adding a feature, ask: "Could I know this value before tipoff?"

---

## 📊 Example: Adding a New Feature

1. **Implement in `feature_engineering.py`:**
   ```python
   def compute_my_feature(games):
       games["my_feature"] = games["home_pts"].rolling(5).mean()
       return games
   ```

2. **Call from `build_features_only.py`:**
   ```python
   games = compute_my_feature(games)
   ```

3. **Document in `FEATURES.md`:**
   ```
   - `my_feature` — rolling 5-game average points (de Prado style)
   ```

4. **Run importance analysis:**
   ```bash
   python -m feature_pipeline.analysis.run --target winner
   ```

5. **Check rankings:**
   - If MDI rank < 50th percentile AND MDA rank < 50th AND SFI rank < 50th → drop it
   - If appears in ≥2 of {MDI, MDA, SFI} → keep it

---

## 🎯 Feature Tiers

After importance analysis, features are classified:

| Tier | Criteria | Action |
|------|----------|--------|
| STRONG | Top 50% in ≥2 of {MDI, MDA, SFI} | Always keep |
| MODERATE | Top 50-75% in ≥2 of {MDI, MDA, SFI} | Keep if Kendall's tau > 0.7 |
| WEAK | <50th percentile across all 3 methods | Drop from final model |

**PCA cross-check:** If Kendall's tau (supervised vs PCA ranks) is close to 1.0, the pattern is confirmed as structural, not overfit.

---

## 📚 References

- **MDI (Mean Decrease Impurity):** In-sample importance from tree models
- **MDA (Mean Decrease Accuracy):** Out-of-sample importance via purged CV
- **SFI (Single Feature Importance):** Immune to substitution effects
- **PCA importance:** Unsupervised ranking of principal components
- **Kendall's tau:** Rank correlation between two importance rankings
- **de Prado framework:** Advances in Financial Machine Learning (AFML), Chapter 8-9

---

## 🔧 Troubleshooting

### "MemoryError during feature engineering"
- Reduce rolling windows: `ROLLING_WINDOWS = [5, 10]`
- Reduce random combos: `N_RANDOM_COMBOS = 10`

### "Kendall's tau < 0.7 (possible overfitting)"
- Drop bottom 20% of features by tier
- Increase N_RANDOM_COMBOS (weak learners add robustness)
- Retrain model + recalculate importance

### "Feature has 90% NaN"
- Check data source: was it curated for this date range?
- Use `handle_missing()` to fillna with column median
- Consider dropping if coverage < 50%

---

## 🎓 Next Steps

- [ ] Add playbyplay features (intra-game momentum shifts)
- [ ] Add player prop features (on-court combinations)
- [ ] Explore interaction features (crowd × travel × rest)
- [ ] Portfolio of Massey context variants (ensemble)
