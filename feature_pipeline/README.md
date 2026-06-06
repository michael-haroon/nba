# Feature Pipeline Module

**Purpose:** Transform raw NBA data into ML-ready features and identify which ones carry genuine predictive signal — without data leakage or multicollinearity distortion.

**Framework:** Marcos López de Prado's *Advances in Financial Machine Learning* (AFML) Ch. 7–8 and *Machine Learning for Asset Managers* (MLAM) Ch. 4–6.

---

## Pipeline Overview

```
1. Load raw data           (parquets: box scores, ratings, arenas, officials, rosters)
   ↓
2. Build game rows         (home vs away structure, prediction targets)
   ↓
3. Engineer features       (1700+ pregame predictors — no same-game leakage)
   ├─ ratings              BPI, Sagarin, Massey (12 context variants), Colley, Wolfe, Wobus, Whitlock
   ├─ rolling stats        5/10/20-game windows, venue-conditioned splits (home/road)
   ├─ momentum             win streaks, CUSUM, win entropy, margin autocorrelation
   ├─ travel + fatigue     distance, timezone shift, directional fatigue, ACWR workload
   ├─ context              crowd density, rest days, back-to-back, crowd × travel interaction
   ├─ roster               active players, DNP count
   ├─ referees             crew home win %, crew avg total, crew experience
   ├─ head-to-head         historical win rate and avg margin vs specific opponent
   ├─ matchup advantage    offensive rating vs good/bad defenses (conditional stats)
   ├─ advanced             Pythagorean residual, Four Factors composite, pace mismatch
   ├─ game variance        blowout rate, close-game rate, overtime history
   ├─ series (playoffs)    game number, series lead, series rest, home win rate
   ├─ hustle               deflections, contested shots, loose balls, screen assists
   ├─ symbolic features    random diff × sum interactions (weak-learner pool)
   └─ diffs / sums         home − away and home + away for all numeric features
   ↓
4. De Prado importance     7-step analysis (see below)
   ↓
5. Filter + save           feature_list.txt, feature_report.csv, game_features.parquet
```

---

## Step-by-Step Feature Engineering

### Step 1 — Load

`data_loader.load_all()` reads all parquets and rating files into a dict:

| Key | Source | Content |
|-----|--------|---------|
| `box_scores` | `BoxScores*.parquet` | Team-level box score per game |
| `game_ids` | `GamesInfo.parquet` | Game metadata (date, season, arena) |
| `team_map` | `team_mappings.parquet` | ESPN ↔ Sagarin ↔ Massey team ID translation |
| `bpi` | `Sagarin.parquet` | ESPN BPI + opponent adjustment ratings |
| `sagarin` | `Sagarin.parquet` | Sagarin predictor, pure ELO, golden mean |
| `massey` | `MasseyRatings.parquet` | 12 context-adjusted Massey variants + off/def |
| `arenas` | `Arenas.parquet` | Lat/lon + capacity for travel/crowd features |
| `officials` | `OfficialCrews.parquet` | Per-game referee crew |
| `player_box_scores` | `PlayerBoxScores.parquet` | Player-level stats for roster features |
| `hustle` | `HustleStats.parquet` | Per-game hustle aggregates |
| `game_summaries` | `GameSummaries.parquet` | ESPN game summary data |
| `quarter_scores` | `QuarterScores.parquet` | Q1–Q4 scores for momentum features |

### Step 2 — Build game rows

`build_game_rows()` pivots team-level box score rows into a single row per game:
- Columns prefixed `home_*` and `away_*`
- `game_date`, `season`, `home_team`, `away_team`

`build_targets()` appends prediction targets (see `TARGETS.md`).

### Step 3 — Feature engineering

All features are **pregame-only** — verified against the leakage rule: *"could I know this value before tipoff?"*

Temporal alignment: ratings at date T are joined to games on date T+1 or later only.
Rolling windows: `games.groupby("team").shift(1).rolling(N)` — shift(1) ensures current game is never included.

---

## De Prado Feature Importance Analysis (7 Steps)

Called via `run_all_importance(X, y, years, ...)` in `feature_importance.py`.

The core problem this solves: with 1700+ correlated features, naive MDI/MDA rankings are distorted by the **substitution effect** — permuting one feature has little apparent impact because correlated substitutes compensate. The de Prado framework corrects this by clustering correlated features first and evaluating importance at the cluster level.

---

### Step 1 — Correlation Matrix

```python
corr = X.corr().fillna(0)
```

Raw Pearson correlation. Marcenko-Pastur denoising and detoning are intentionally skipped: engineered NBA features are already clean signals, not raw equity returns. Empirical testing showed denoising collapses meaningful cluster structure.

---

### Step 2 — ONC Clustering (Optimal Number of Clusters)

**Goal:** group correlated features into coherent "information sources" before importance is measured.

**Distance:** correlation → distance via

$$d_{ij} = \sqrt{\frac{1 - \rho_{ij}}{2}}$$

so perfectly correlated features map to distance 0 and uncorrelated to distance $\frac{1}{\sqrt{2}}$.

**Quality criterion:** silhouette t-statistic for a given partition:

$$q(\mathcal{P}) = \frac{\bar{s}}{\sigma_s}$$

where $s_i$ is the silhouette score for feature $i$, $\bar{s}$ its mean across all features, and $\sigma_s$ its standard deviation. This is the de Prado MLAM §4.4 criterion — it rewards partitions that are both high-quality on average *and* consistent.

**Flat pass** (`_onc_flat`): for each $(k, \text{seed})$ in a grid of $k \in [2, n-1]$ and 20 random seeds, run KMeans, compute $q$, keep the best-scoring partition. Parallelized with `joblib`.

**Recursive pass** (`onc_cluster`, MLAM Ch.4): the flat pass is the initializer; recursion refines it with two quality-gated base cases:

1. **K₁ ≤ 1** — fewer than 2 clusters have below-average quality. No sub-groups left to refine. Return current partition.

   $$K_1 = \left|\{k : q_k < \bar{q}\}\right| \leq 1 \implies \text{terminate}$$

2. **New avg quality ≤ old avg quality** — re-clustering the "bad" features and merging back does not improve the global partition. Discard sub-result and return the previous partition.

   $$\bar{q}(\mathcal{P}') \leq \bar{q}(\mathcal{P}) \implies \text{discard and terminate}$$

Only if $K_1 \geq 2$ *and* $\bar{q}(\mathcal{P}') > \bar{q}(\mathcal{P})$ does the algorithm accept the new partition and recurse. This ensures splitting never adds noise.

---

### Step 3 — CFI: Clustered Feature Importance

**Goal:** defeat the substitution effect by permuting entire clusters simultaneously.

**CFI-MDI** — sum MDI importances within each cluster:

$$\text{CFI-MDI}_c = \sum_{j \in c} \text{MDI}_j$$

**CFI-MDA** — permute all features in cluster $c$ simultaneously:

For each CV fold $(X_{tr}, X_{te})$:

$$\text{imp}_c = \ell(y_{te},\ \hat{y}_{te}) - \ell\!\left(y_{te},\ \hat{y}_{te}^{(c\text{-permuted})}\right)$$

where $\ell$ is $-\log\text{loss}$ for classification or $R^2$ for regression. Shuffling all cluster members at once prevents correlated substitutes from masking the signal.

Summary: $\text{mean}(\text{imp}_c)$ and $\text{std}(\text{imp}_c)$ across folds.

A cluster is considered informative if $\text{mean} > 0$ and $z\text{-score} = \frac{\text{mean}}{\text{se}} \geq 1.0$.

---

### Step 4 — MDI: Mean Decrease Impurity (per-feature)

**When:** in-sample, uses the already-fitted full RF.

For each tree $t$ in the ensemble, feature $j$'s importance is the total reduction in node impurity (entropy for classification, variance for regression) weighted by the fraction of samples reaching each split:

$$\text{MDI}_j = \frac{1}{T}\sum_{t=1}^{T} \sum_{\text{node} \in t,\; v(\text{node})=j} \frac{n_{\text{node}}}{n} \cdot \Delta I_{\text{node}}$$

Each tree is normalised to sum to 1 before averaging, so per-tree values are comparable across ensemble sizes.

Zeros are set to NaN: if a feature was never selected as a split in a given tree (an artefact of `max_features=1`), it carries no information for that tree.

**Note:** MDI is biased toward high-cardinality features and is in-sample. It is used for ranking, not the primary importance gate.

---

### Step 5 — SFI: Single Feature Importance

**When:** out-of-sample, purged year-CV, one feature at a time.

SFI trains an independent RF on each feature alone and scores it on held-out folds:

$$\text{SFI}_j = \frac{1}{K}\sum_{k=1}^{K} \ell\!\left(y_{te}^{(k)},\ \hat{y}_{te}^{(k)}\right)$$

where $\ell = -\log\text{loss}$ (classification) or $R^2$ (regression).

SFI is immune to substitution: since only one feature is present, correlated substitutes cannot compensate. The tradeoff is that it ignores interaction effects between features.

**Null score** (no-skill baseline):

- Classification: $\ell_0 = \sum_c p_c \log p_c$ (log-likelihood of the class prior)
- Regression: $\ell_0 = 0$ ($R^2 = 0$ means predicting the mean)

**Cross-validation:** `PurgedYearKFold` — leave-one-year-out (default) or k-fold over years. The purging eliminates temporal leakage: test fold is isolated to one year, training uses only other years with no overlap.

---

### Step 6 — PCA Cross-Check + Weighted Kendall's τ

**Goal:** verify that supervised importance rankings align with unsupervised variance structure. Divergence suggests overfitting.

**PCA loading:** variance-weighted absolute loading for each feature:

$$w_j = \sum_{m=1}^{M} \lambda_m \cdot |v_{mj}|$$

where $\lambda_m$ is the explained variance ratio of component $m$ and $v_{mj}$ is feature $j$'s loading on it.

**Weighted Kendall's τ:** rank correlation between PCA ranks and MDI/MDA/SFI ranks, using Kendall's τ with larger discordant-pair weights for rank disagreements at the top:

$$\tau_w(\mathbf{r}^A, \mathbf{r}^B) \approx 1.0 \implies \text{signal is structural, not overfit}$$

P-values via permutation test (1000 permutations of one rank vector), since `scipy.stats.weightedtau` always returns NaN for p-values.

---

### Step 7 — Algorithmic Filtering

Three tests, one vote each:

| Method | Pass condition |
|--------|---------------|
| **MDI** | $\text{mean} > \frac{1}{F}$ AND ($\text{CI}_{lower} > \frac{1}{F}$ OR Wilcoxon $p < 0.10$) |
| **CFI-MDA** | cluster $\text{mean} > 0$ AND cluster $z\text{-score} \geq 1.0$ |
| **SFI** | $\text{mean} > \ell_0$ AND $\text{CI}_{lower} > \ell_0$ |

The MDI threshold $\frac{1}{F}$ is the uniform importance baseline: if a feature is no more important than chance, it gets $\frac{1}{F}$. Confidence intervals are bootstrap (2000 resamples, 95% CI). Wilcoxon signed-rank test is non-parametric — no normality assumption.

**Tier assignment:**

| Tier | Condition | Disposition |
|------|-----------|-------------|
| STRONG | all available tests pass | always keep |
| MODERATE | ≥ 67% of available tests pass | keep |
| WEAK | ≥ 34% of available tests pass | drop |
| REJECTED | < 34% pass | drop |
| REJECTED (detrimental) | CFI-MDA mean < 0 | always drop — actively hurts predictions |

Features where CFI-MDA cluster mean is negative are immediately rejected regardless of MDI/SFI, because permuting the cluster *improves* accuracy — the feature is adding noise or anti-signal.

---

## Scoring: entropy vs log_loss

These are two distinct roles and must not be confused:

| | Role | Where | Formula |
|---|---|---|---|
| `criterion="entropy"` | Tree **split criterion** during training | `DecisionTreeClassifier` | $H = -\sum_c p_c \log_2 p_c$ — maximised at each node split |
| `-log_loss(y, p)` | **OOS evaluation metric** during MDA/SFI | fold scoring | $\ell = -\sum_i \sum_c y_{ic} \log p_{ic}$ — computed on held-out set |

The tree uses entropy internally to decide how to split. The fold scorer uses log_loss to measure how well the fitted tree's probability estimates match held-out labels. Negated so that higher = better (consistent with $R^2$ direction).

---

## Usage

```bash
# Full pipeline (features + importance analysis)
conda run -n pred python -m feature_pipeline.analysis.run --target target_winner

# Features only (skips importance, ~5 min)
conda run -n pred python -m feature_pipeline.build_features_only

# Regression target (spread)
conda run -n pred python -m feature_pipeline.analysis.run --target target_spread

# Skip Massey ratings (faster iteration)
conda run -n pred python -m feature_pipeline.analysis.run --skip-massey

# Skip symbolic features
conda run -n pred python -m feature_pipeline.analysis.run --skip-random
```

## Outputs

All outputs written to `output/features/<target>/`:

| File | Content |
|------|---------|
| `game_features.parquet` | Full feature matrix (all engineered features, pre-filter) |
| `feature_pipeline/logs/pipeline_*.log` | Timestamped run log with per-step metrics (DEBUG level to file, INFO to stderr) |
| `feature_importance_catalog.csv` | Per-feature MDI, CFI-MDA, SFI scores + avg rank |
| `importance_mdi.csv` | MDI summary (mean, std) |
| `importance_mdi_raw.csv` | Per-tree MDI importances |
| `importance_cfi_mda.csv` | CFI-MDA cluster-level summary |
| `importance_cfi_mda_raw.csv` | Per-fold CFI-MDA scores per cluster |
| `importance_sfi.csv` | SFI summary (mean, std, null score) |
| `cfi_mda_distributions.png` | Per-cluster fold-score histograms with z-scores |
| `pca_cross_check.csv` | PCA variance-weighted loadings per feature |
| `kendall_tau.json` | Weighted Kendall's τ (PCA vs MDI/MDA/SFI) |
| `filtered/feature_report.csv` | Full per-feature pass/fail + tier |
| `filtered/feature_list.txt` | Surviving feature names (STRONG + MODERATE) |

---

## Leakage Prevention

**Rule:** all features must be knowable before tipoff.

- Ratings at date T are joined to games on date T+1 or later (strict `<` join).
- Rolling windows use `.shift(1)` before `.rolling(N)` so the current game is excluded.
- Same-game box score stats (pts, fgm, offrtg) are targets, not features.
- `PurgedYearKFold` ensures no training sample is temporally adjacent to a test sample.

---

## References

- AFML Ch. 7: Purged cross-validation, combinatorial purging
- AFML Ch. 8: MDI, MDA, SFI definitions and bias analysis
- MLAM Ch. 4: ONC algorithm, silhouette t-statistic
- MLAM Ch. 6: Clustered Feature Importance (CFI), substitution effect
