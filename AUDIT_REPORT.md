# Audit Report: NBA Prediction Markets Pipeline

## Executive Summary

The pipeline contains **two confirmed data leakage vulnerabilities** (attendance features and symbolic feature pool) that could inflate backtesting metrics and produce overconfident trade signals. A secondary architectural defect exposes same-game outcome columns (including the literal target) to the symbolic feature generator, though downstream importance filtering currently prevents these from entering production models. Performance bottlenecks in the Massey ratings pipeline (iterrows in 8 fit functions, ~59 fits per date) add unnecessary compute time but do not affect correctness.

---

## 1. CONFIRMED HIGH-SEVERITY FINDINGS

### LEAKAGE

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| **HIGH** | `feature_pipeline/engineering/feature_engineering.py:695` | `crowd_density` and `sellout_flag` use post-tipoff attendance data. Attendance is only known after the game starts. Derived features `hostile_crowd_pressure` and `crowd_home_lift` inherit the leak. All four are actively used via PREGAME_EXACT in `analysis/run.py:332`. | Remove `crowd_density`, `sellout_flag`, `hostile_crowd_pressure`, `crowd_home_lift` from PREGAME_EXACT and CONTEXT_FEATURES. If crowd signal is needed, use a rolling average of prior-game attendance or historical sellout frequency for that arena. |
| **HIGH** | `feature_pipeline/engineering/feature_engineering.py:2409` | `generate_symbolic_features` pools ALL `diff_*` and `sum_*` columns including same-game outcomes (`diff_pts` = target_spread, `diff_netrtg`, `sum_pts` = target_total). 142 of 500 generated recipes use leaking columns. `sf_` prefix passes PREGAME_PREFIXES filter. Currently no sf_ features survive importance filtering, but the vulnerability is active. | Whitelist the pool: `pool_cols` should only match `diff_roll*`, `diff_bpi*`, `diff_sag*`, `sum_roll*`, or other verified pregame prefixes. Alternatively, compute symbolic features BEFORE `compute_diffs`/`compute_sums`. |

### ARCHITECTURE

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| **MEDIUM** | `feature_pipeline/engineering/feature_engineering.py:1292` | `compute_diffs` creates `diff_pts` identical to `target_spread`. While PREGAME_PREFIXES correctly excludes it from direct use, the column feeds into `generate_symbolic_features` (same issue as above). | Add an explicit exclusion set in `compute_diffs` or tag outcome-derived diffs with a prefix like `outcome_diff_` that the symbolic generator can filter out. |
| **LOW** | `feature_pipeline/engineering/feature_engineering.py:1269` | `generate_random_combinations` has an inverted filter (keeps dangerous diffs, excludes safe rolling ones). Dead code -- never called, `rc_` prefix excluded from PREGAME_PREFIXES. | Delete the function or fix the filter for code hygiene. No operational risk. |

### EFFICIENCY

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| **HIGH** | `data_curation/scripts/build_massey_ratings.py:257` | O(N^2) per date: 59 model fits x iterrows over growing game history x 180 dates/season. Estimated 5-15 min/season, 50-150 min for full rebuild. | Vectorize normal-equation accumulation: build X via fancy indexing, compute `X.T @ W @ X` in one call. For Zermelo iterations, use `np.bincount` instead of per-team list comprehension scans. Expected 50-100x speedup per fit. |
| **MEDIUM** | `feature_pipeline/engineering/massey_ratings.py:408` | All 8 fit functions (`fit_massey`, `fit_colley`, `fit_wolfe`, `fit_wobus`, `fit_whitlock`, `fit_massey_quarter`, `fit_colley_quarter`, `fit_massey_offdef`) use `df.iterrows()` for matrix assembly. | Replace with vectorized numpy: fancy indexing for sparse matrix construction, `np.add.at` for Colley, `np.bincount` for Zermelo denominators. |

---

## 2. PLAUSIBLE HIGH-SEVERITY FINDINGS

None identified. All high-severity findings were adversarially verified.

---

## 3. LOWER-SEVERITY FINDINGS

### LEAKAGE

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| MEDIUM | `feature_pipeline/analysis/run.py:376` | Full-dataset median imputation (`X.fillna(X.median())`) before cross-validated feature importance. Validation-fold values influence imputed training values. | Perform per-fold imputation inside the CV loop, or use NaN-native tree estimators for importance. |
| MEDIUM | `feature_pipeline/engineering/feature_engineering.py:481` | Same-date doubleheader dedup uses `keep='last'` (comment says 'first'). First game of pair gets features contaminated by second game's outcome via shift(1). Repeats 14x across file. | Change to `keep='first'` or add game sequence number within each date. Impact is minimal (doubleheaders are extremely rare in modern NBA). |
| LOW | `strategy/train.py:92` | LOYO CV is bidirectional (trains on future seasons when validating past). Inflates estimated accuracy if concept drift exists. | Supplement with expanding-window CV for deployment accuracy estimates. Document that LOYO metrics are optimistic. |
| LOW | `feature_pipeline/engineering/game_builder.py:296` | Series targets assign eventual series winner to all games in the series (game 1 gets same label as game 7). Not feature leakage but affects target interpretation. | Document design choice. Consider separate evaluation for early-series vs late-series predictions. |

### MATH

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| MEDIUM | `feature_pipeline/engineering/feature_engineering.py:1737` | ACWR alpha_acute=0.25 gives half-life of 2.41 games, not 4 as commented. Formula error: code/comments used mean lifetime formula instead of half-life. | Change `alpha_acute` to 0.159 for true 4-game half-life, or fix comment to state ~2.4 games. |
| MEDIUM | `feature_pipeline/engineering/massey_ratings.py:991` | Wobus P_max = 0.522 for 24-pt blowout (dynamic range of 1.2%). Ratings are severely compressed; convergence may be incomplete at 100 iterations. | Increase slope to 0.01-0.02, or use logistic transform with sigma~13. Alternatively increase n_iter to 500+. |
| MEDIUM | `feature_pipeline/engineering/feature_engineering.py:1549` | Log5 uses rolling win% as probability input. Win% confounds skill with schedule strength, introducing 3-5% probability error for teams with extreme SOS. | Use Massey/Elo-derived implied win probability against league-average opponent instead of raw win%. |
| LOW | `feature_pipeline/engineering/feature_engineering.py:79` | CUSUM uses first-difference (y_t - y_prev) instead of de Prado's deviation-from-mean. Both are valid CUSUM variants but docstring claims de Prado Ch.2. | Update docstring to clarify this is a first-difference CUSUM variant. |
| LOW | Various | Colley system, Massey constraint, Wolfe/Zermelo denominator, Pythagorean exponent (13.91), Huber delta adaptive selection -- all verified CORRECT. | No fixes needed. |

### ARCHITECTURE

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| MEDIUM | `feature_pipeline/analysis/run.py:376` | Feature selection uses full-dataset median imputation while training uses train-only median. Features important under global imputation may perform differently under proper per-fold imputation. | Mirror training imputation procedure in importance analysis, or remove fillna and use NaN-capable estimators. |
| LOW | `feature_pipeline/engineering/game_builder.py:160` | `attach_quarter_scores` merges on game_id without type normalization. If int vs zero-padded string mismatch occurs, all quarter columns become NaN silently. | Add `.astype(str).str.zfill(10)` normalization before merge (pattern already used elsewhere in codebase). |
| LOW | `data_curation/scripts/build_massey_ratings.py:434` | Early-season games get NaN Massey ratings, imputed with mid/late-season training median. LogReg/Ridge treat these as real signals. | Impute Massey NaNs with 0.0 (league-average prior) instead of training median for linear models. |

### EFFICIENCY

| Severity | File:Line | Summary | Fix |
|----------|-----------|---------|-----|
| MEDIUM | `feature_pipeline/engineering/feature_engineering.py:1330` | `pd.concat([home, away]).sort_values()` pattern repeated in 8+ functions. Each creates ~30K row DataFrame independently. | Build unified team-game history ONCE at pipeline start; pass as parameter to all compute_* functions. |
| MEDIUM | `feature_pipeline/engineering/feature_engineering.py:1694` | `apply(axis=1)` in scoring entropy and series features forces pure-Python row iteration (~3s for 30K rows). | Vectorize with numpy: extract columns as 2D array, compute `-np.nansum(p * np.log2(p), axis=1)`. Expected 50-100x speedup. |
| MEDIUM | `feature_pipeline/analysis/run.py:251` | 500 symbolic features (71% of total) dominate SFI compute time despite most being noise. SFI alone estimated at ~3 hours. | Pre-filter sf_ features by univariate correlation (|r| > 0.02) before running SFI, or gate SFI to features passing MDI > median. |
| LOW | `data_curation/scripts/build_massey_ratings.py:437` | Joblib parallelizes across dates but 59 fits per date are sequential. Late-season dates create load imbalance. | Flatten work into (date, model_type) tuples for better load balancing, or use `batch_size='auto'`. |

---

## 4. REFUTED FINDINGS

None. All submitted findings were confirmed to varying degrees.

---

## Priority Action Items

1. **Immediate (blocks valid backtesting):** Remove `crowd_density`, `sellout_flag`, `hostile_crowd_pressure`, `crowd_home_lift` from feature lists.
2. **High priority (latent leakage):** Whitelist `generate_symbolic_features` pool to exclude same-game outcome columns.
3. **Medium priority (performance):** Vectorize Massey fit functions to reduce full-rebuild time from hours to minutes.
4. **Low priority (hygiene):** Fix ACWR half-life comment/parameter, delete dead `generate_random_combinations`, normalize game_id types in `attach_quarter_scores`.
