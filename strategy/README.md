# Strategy Module

**Purpose:** Train, evaluate, and compare prediction models for NBA game outcomes.

---

## 🎯 Overview

The strategy module builds supervised ML models that predict:
- **Classification:** `target_winner` (binary: home win or away win)
- **Regression:** `target_spread` (continuous: home_pts - away_pts)

Models are trained using **PurgedYearKFold** cross-validation to prevent temporal leakage:
- Train on prior seasons/years
- Validate on future dates
- No information leakage across folds

---

## 🔄 Training Pipeline

```
1. Load game_features.parquet + target
   ├─ features (100+)
   └─ target (winner or spread)
   ↓
2. Initialize models
   ├─ LGBM (boosting)
   ├─ LogReg / Ridge (linear)
   ├─ SVC / SVR (kernel)
   └─ Naive Bayes / Lasso (other)
   ↓
3. For each model:
   ├─ PurgedYearKFold CV (5 splits, seasons 2019-2025)
   ├─ Train on each fold
   ├─ Predict OOF (out-of-fold)
   ├─ Compute metrics (accuracy, AUC, R², MAE, etc.)
   └─ Store results
   ↓
4. Model comparison
   ├─ Rank by CV loss / AUC
   ├─ Plot calibration curves
   └─ Detect overfitting (train loss vs OOF loss)
   ↓
5. Save winners
   ├─ Best model: model.pkl
   ├─ OOF predictions: oof_preds.csv
   └─ Trade recommendations: trade_recs.csv
```

---

## 📦 Modules

### `data.py`
**Loads features and targets from parquets.**

```python
from strategy.data import load

X, y, seasons = load("winner")  # or "spread"
# X: (n_games, n_features) feature matrix
# y: (n_games,) target vector
# seasons: (n_games,) season labels for PurgedYearKFold
```

**What it does:**
1. Loads `output/features/{target}/game_features.parquet`
2. Aligns feature columns to `feature_list.txt` (survivors from importance analysis)
3. Fillna with column medians (matches feature pipeline)
4. Validates shapes + NaN counts
5. Returns (X, y, seasons) tuple

### `models.py`
**Model builders + hyperparameter definitions.**

```python
from strategy.models import (
    build_classifier, build_regressor,
    available_classifiers, available_regressors
)

# Classifiers (for target_winner)
available_classifiers()  # ['lgbm', 'logreg', 'svc', 'naive_bayes', ...]

clf = build_classifier("lgbm")  # LightGBM
# Returns sklearn-like estimator with fit/predict

# Regressors (for target_spread)
available_regressors()  # ['lgbm', 'ridge', 'lasso', 'svr', ...]

reg = build_regressor("ridge")  # Ridge regression
```

**Hyperparameters tuned per model in `config.py`:**
- LGBM: n_estimators=500, max_depth=7, learning_rate=0.05
- LogReg: C=1.0, max_iter=1000
- Ridge: alpha=1.0, fit_intercept=True
- etc.

### `train.py`
**Cross-validation + training loop.**

```python
from strategy.train import train_and_evaluate

results = train_and_evaluate(
    X, y, seasons,
    model_name="lgbm",
    build_fn=build_classifier,
    task="classification"  # or "regression"
)

# Returns:
# {
#   "cv_df": pd.DataFrame with per-fold metrics,
#   "oof_preds": (n_games,) OOF predictions,
#   "model": trained model object,
#   "feature_importance": dict of feature importances,
# }
```

**Cross-validation strategy:** `PurgedYearKFold`
- 5 splits: Year 1 train → Year 2 validate, Year 1-2 train → Year 3 validate, etc.
- Purging: No date overlap between train + test
- No information leakage across seasons

### `config.py`
**Global config + hyperparameters.**

```python
# Model hyperparameters
CLASSIFIER_PARAMS = {
    "lgbm": {"n_estimators": 500, "max_depth": 7, ...},
    "logreg": {"C": 1.0, "max_iter": 1000},
    ...
}

REGRESSOR_PARAMS = {
    "lgbm": {"n_estimators": 500, "objective": "regression", ...},
    "ridge": {"alpha": 1.0},
    ...
}

# CV settings
CV_RANDOM_STATE = 42
N_SPLITS = 5

# Output
OUTPUT_DIR = Path("strategy/output")
```

### `evaluate.py`
**Metrics computation + residual analysis.**

```python
from strategy.evaluate import (
    print_model_comparison,
    fit_spread_residuals,
    save_results
)

# Compare models side-by-side
print_model_comparison(results, task="classification")
# Prints: Accuracy, AUC, Precision, Recall, F1 for each model + fold

# Fit residual distribution (for spread predictions)
residual_dist = fit_spread_residuals(oof_preds)
# Fits Student-t: useful for position sizing + Kelly criterion

# Save model artifacts
save_results(results, output_dir, target="winner")
```

### `run.py`
**Main entry point.**

```bash
python -m strategy.run                    # Train winner + spread
python -m strategy.run --target winner    # Only winner
python -m strategy.run --target spread    # Only spread
```

**Output:**
- `strategy/output/{target}/model.pkl` — best model
- `strategy/output/{target}/oof_preds.csv` — out-of-fold predictions
- `strategy/output/{target}/cv_results.csv` — per-fold metrics
- `strategy/output/{target}/trade_recs.csv` — recommended trades

---

## 📊 Example: Train a Model

```bash
# 1. Ensure features are built
python -m feature_pipeline.build_features_only --output-dir output/features/winner

# 2. Train all models for winner prediction
python -m strategy.run --target winner

# Output:
# ============================================================
#   Target: winner  (classification)
# ============================================================
#   Samples: 1234, Features: 45, Seasons: 7
#
#   [lgbm] training...
#   [lgbm] done — 5 folds [2.3s]
#
#   [logreg] training...
#   [logreg] done — 5 folds [0.8s]
#
#   ... (other models)
#
#   Model Comparison (Classification):
#   ┌─ lgbm       Accuracy: 0.584, AUC: 0.631, F1: 0.512
#   ├─ ridge      Accuracy: 0.562, AUC: 0.610, F1: 0.495
#   └─ naive_bayes Accuracy: 0.541, AUC: 0.585, F1: 0.461
#
#   Total: 5.2s
#
#   ✓ Results saved to strategy/output/winner/
```

---

## 🚨 Overfitting Detection

After training, compare:
- **Train loss** (in-fold accuracy on training data)
- **OOF loss** (out-of-fold accuracy on validation data)

If `(train_loss - oof_loss) > 0.10`:
- Potential overfitting signal
- Reduce model complexity (LGBM: lower n_estimators or max_depth)
- Add regularization (Ridge: increase alpha; LGBM: increase min_child_samples)
- Feature selection: drop lowest-importance features

**PCA cross-check:** If feature importance (MDI) doesn't match PCA structure (Kendall's tau < 0.7), suspect overfitting.

---

## 💰 Risk Management

See `RISK_MANAGEMENT.md` for:
- Position sizing (Kelly criterion)
- Confidence intervals (predicted probability ± std)
- Drawdown limits
- Win/loss streak detection

**Quick example:**
```python
# Kelly criterion: f = (p * b - q) / b
# p = win probability, b = odds, q = loss probability
p = 0.55  # Model predicts home 55% to win
b = 1.9   # Kalshi offers 1.9x return
q = 1 - p
f = (p * b - q) / b  # ≈ 0.05 = 5% of bankroll
```

---

## 🔧 Common Tasks

### Load predictions for analysis
```python
import pandas as pd

# Load OOF predictions
oof = pd.read_csv("strategy/output/winner/oof_preds.csv")
print(oof.head())
# Columns: game_id, pred_prob, actual_winner, correct, ...

# Compute custom metrics
accuracy = (oof['pred_class'] == oof['actual_winner']).mean()
print(f"Accuracy: {accuracy:.3f}")
```

### Compare two models
```python
import json

with open("strategy/output/winner/cv_results.csv") as f:
    results = pd.read_csv(f)
    print(results[["model", "fold", "val_accuracy", "val_auc"]])

# Plot calibration
import matplotlib.pyplot as plt
for model in results['model'].unique():
    model_data = results[results['model'] == model]
    plt.plot(model_data['fold'], model_data['val_accuracy'], label=model)
plt.legend()
plt.show()
```

### Feature importance inspection
```python
import pickle

with open("strategy/output/winner/model.pkl", "rb") as f:
    best_model = pickle.load(f)

if hasattr(best_model, "feature_importances_"):
    for feat, imp in sorted(best_model.feature_importances_.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"{feat}: {imp:.4f}")
```

---

## 📈 Model Selection Guide

| Model | Strengths | Weaknesses | Best For |
|-------|-----------|-----------|----------|
| **LGBM** | Fast, feature importance, handles nonlinearity | Can overfit on small datasets | Benchmarking, complex patterns |
| **LogReg** | Interpretable, stable, fast | Assumes linearity | Baseline, when explainability matters |
| **Ridge/Lasso** | Regularized linear, prevents overfitting | Limited nonlinearity | Sparse features, high dimensionality |
| **SVC/SVR** | Kernel methods, RBF for nonlinearity | Slow on large datasets, hyperparameter tuning | Custom kernels, small-medium datasets |
| **Naive Bayes** | Fast, interpretable | Assumes feature independence | Baseline, quick iteration |

---

## 🎓 Next Steps

- [ ] Implement ensemble voting (weighted avg of best 3 models)
- [ ] Add hyperparameter tuning (Optuna / Hyperband)
- [ ] Implement neural network (simple FCNN for comparison)
- [ ] Add live calibration (retrain on recent games only)
- [ ] Implement player-prop models (prop_leader, game_total_player_pts, etc.)

---

## 📚 References

- **PurgedYearKFold:** mlfinlab.modeling_utils.cross_validation.PurgedYearKFold
- **Kelly Criterion:** de Prado Appendix D, Thorp "The Mathematics of Gambling"
- **Model Calibration:** Guo et al. "On Calibration of Modern Neural Networks"
- **Feature Importance:** Lundberg, Lee "A unified approach to interpreting model predictions" (SHAP)
