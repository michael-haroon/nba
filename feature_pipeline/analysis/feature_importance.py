"""
feature_importance.py
---------------------
Implements de Prado's four feature importance methods:
  MDI  – Mean Decrease Impurity     (in-sample, fast)
  MDA  – Mean Decrease Accuracy     (OOS, marginal)
  SFI  – Single Feature Importance  (OOS, standalone, no substitution bias)
  CFI  – Clustered Feature Importance (corrects for multicollinearity)

Plus:
  - Purged K-Fold cross-validation (no temporal leakage)
  - Cluster detection via ONC (Optimal Number of Clusters)
  - Synthetic data validation (can MDI/MDA find a known signal?)

References:
  AFML   Ch.7 (purged CV), Ch.8 (feature importance)
  MLAM   Ch.4 (ONC), Ch.6 (CFI)
"""

import warnings
import numpy as np
import pandas as pd
from itertools import combinations
from joblib import Parallel, delayed
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import BaggingClassifier, RandomForestClassifier
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import KFold
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from scipy.stats import wilcoxon as scipy_wilcoxon, weightedtau
from sklearn.decomposition import PCA
from feature_pipeline.config import RF_PARAMS
from feature_pipeline.compute import get_n_jobs, get_parallel_split


# ─────────────────────────────────────────────────────────────────────────────
#  Purged K-Fold  (de Prado AFML Ch.7)
# ─────────────────────────────────────────────────────────────────────────────

class PurgedYearKFold:
    """
    Leave-one-year-out cross-validation for temporal data.
    Train on all years except the held-out year.
    No purging needed when the fold boundary is a whole year,
    because there is no overlap between years (one row per team per year).

    This is appropriate for our dataset: each row = team × year.
    Holding out a year means the model has never seen any data from that year.
    """

    def __init__(self, years: pd.Series):
        self.unique_years = sorted(years.unique())

    def split(self, X, y=None, groups=None):
        years = groups  # pass df['year'] as groups
        if years is None:
            raise ValueError("Pass df['year'] as the groups argument.")
        for test_year in self.unique_years:
            train_idx = np.where(years != test_year)[0]
            test_idx  = np.where(years == test_year)[0]
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue
            yield train_idx, test_idx

    def get_n_splits(self):
        return len(self.unique_years)


# ─────────────────────────────────────────────────────────────────────────────
#  Build a base RF classifier (de Prado's recommended setup)
# ─────────────────────────────────────────────────────────────────────────────

def build_rf(n_estimators: int = 1000, n_jobs: int = -1) -> BaggingClassifier:
    """
    de Prado's recommended setup (AFML Ch.8):
    - Decision trees with max_features=1 (one random feature per split)
    - Wrapped in BaggingClassifier for OOB and ensemble variance reduction
    - balanced_subsample to handle class imbalance in Final Four data
    """
    base = DecisionTreeClassifier(
        criterion="entropy",
        max_features=1,          # key for MDI: every feature gets a fair shot
        class_weight="balanced",
        min_weight_fraction_leaf=0.02,
    )
    return BaggingClassifier(
        estimator=base,
        n_estimators=n_estimators,
        max_features=1.0,
        max_samples=1.0,
        oob_score=False,         # don't use OOB — use purged CV instead
        n_jobs=n_jobs,
        random_state=42,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  MDI  (de Prado AFML Ch.8 §8.3.1)
# ─────────────────────────────────────────────────────────────────────────────

def feat_imp_mdi(fit: BaggingClassifier,
                 feat_names: list) -> tuple:
    """
    Mean Decrease Impurity across all trees in the ensemble.

    Returns:
        summary: DataFrame(index=feature, columns=[mean, std]) — CLT-normalised
        raw:     DataFrame(index=tree_id, columns=features) — per-tree importances,
                 normalised to sum to 1 per tree. Use for distribution plots and
                 t-tests vs. null (H0: mean == 1/n_features).
    Zeros are set to NaN (feature was never chosen — an artefact of max_features=1).
    """
    imp_dict = {
        i: tree.feature_importances_
        for i, tree in enumerate(fit.estimators_)
    }
    imp_df = pd.DataFrame.from_dict(imp_dict, orient="index")
    imp_df.columns = feat_names
    imp_df = imp_df.replace(0, np.nan)          # never selected → NaN

    # Normalise each tree row to sum to 1 (so per-tree values are comparable)
    raw = imp_df.div(imp_df.sum(axis=1), axis=0)

    result = pd.concat({
        "mean": raw.mean(),
        "std":  raw.std() * raw.shape[0] ** -0.5,  # CLT SE
    }, axis=1)
    return result.sort_values("mean", ascending=False), raw


# ─────────────────────────────────────────────────────────────────────────────
#  MDA  (de Prado AFML Ch.8 §8.3.2)
# ─────────────────────────────────────────────────────────────────────────────

def _mda_one_fold(clf_params, X_tr_vals, X_te_vals, y_tr_vals, y_te_vals,
                  col_names, w_tr_vals, scoring, seed):
    """
    Run one MDA fold: fit model, score base + all permutations.

    Uses backend="multiprocessing" (fork on Linux) at the outer level so
    BaggingClassifier's inner n_jobs threads actually run — loky blocks nested
    subprocess spawning, but forked processes can use threads freely.
    """
    import os
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import BaggingClassifier

    rng = np.random.default_rng(seed)
    base = DecisionTreeClassifier(
        criterion="entropy", max_features=1,
        class_weight="balanced", min_weight_fraction_leaf=0.02,
    )
    clf = BaggingClassifier(
        estimator=base, n_estimators=clf_params["n_estimators"],
        max_features=1.0, max_samples=1.0, oob_score=False,
        n_jobs=clf_params["n_jobs"], random_state=clf_params["random_state"],
    )
    X_tr = pd.DataFrame(X_tr_vals, columns=col_names)
    X_te = pd.DataFrame(X_te_vals, columns=col_names)
    y_tr = pd.Series(y_tr_vals)
    y_te = pd.Series(y_te_vals)

    fit = clf.fit(X_tr, y_tr, sample_weight=w_tr_vals)
    prob = fit.predict_proba(X_te)

    if scoring == "log_loss":
        base_score = -log_loss(y_te, prob, labels=fit.classes_)
    else:
        base_score = roc_auc_score(y_te, prob[:, 1])

    perm_fold = {}
    for col in col_names:
        X_perm = X_te.copy()
        X_perm[col] = rng.permutation(X_perm[col].values)
        prob_perm = fit.predict_proba(X_perm)
        if scoring == "log_loss":
            perm_fold[col] = -log_loss(y_te, prob_perm, labels=fit.classes_)
        else:
            perm_fold[col] = roc_auc_score(y_te, prob_perm[:, 1])

    return base_score, perm_fold


def feat_imp_mda(clf,
                 X: pd.DataFrame,
                 y: pd.Series,
                 years: pd.Series,
                 sample_weight: pd.Series = None,
                 scoring: str = "log_loss") -> tuple:
    """
    Mean Decrease Accuracy via purged year-CV.
    Shuffles one feature at a time and measures accuracy drop.
    scoring: 'log_loss' (recommended) or 'roc_auc'

    Parallelism: outer loop over folds via backend="multiprocessing" (fork on
    Linux). Each forked worker gets n_inner threads for BaggingClassifier.
    Fork avoids loky's nested-spawn restriction so inner n_jobs actually works.

    Returns:
        summary: DataFrame(index=feature, columns=[mean, std])
        raw:     DataFrame(index=fold, columns=features) — per-fold importance
                 (base_score - permuted_score). Use for distribution plots and
                 t-tests vs. null H0: mean == 0 (shuffling has no effect).
    """
    cv = PurgedYearKFold(years)
    n_folds = cv.get_n_splits()
    n_outer, n_inner = get_parallel_split(n_folds)

    clf_params = {
        "n_estimators": clf.n_estimators,
        "n_jobs": n_inner,   # threads inside each forked worker — works with fork
        "random_state": 42,
    }

    folds = list(cv.split(X, y, groups=years.values))
    # backend="multiprocessing" → fork on Linux; forked processes can thread freely
    results = Parallel(n_jobs=n_outer, backend="multiprocessing")(
        delayed(_mda_one_fold)(
            clf_params,
            X.iloc[tr].values, X.iloc[te].values,
            y.iloc[tr].values, y.iloc[te].values,
            list(X.columns),
            sample_weight.iloc[tr].values if sample_weight is not None else None,
            scoring,
            seed=i,
        )
        for i, (tr, te) in enumerate(folds)
    )

    base_scores = [r[0] for r in results]
    base_arr = np.array(base_scores)

    records = {}
    raw_records = {}
    for col in X.columns:
        perm = np.array([r[1][col] for r in results])
        imp  = base_arr - perm
        records[col] = {"mean": imp.mean(),
                        "std":  imp.std() * len(imp) ** -0.5}
        raw_records[col] = imp

    result = pd.DataFrame(records).T
    result.columns = ["mean", "std"]
    raw = pd.DataFrame(raw_records)
    return result.sort_values("mean", ascending=False), raw


# ─────────────────────────────────────────────────────────────────────────────
#  SFI  (de Prado AFML Ch.8 §8.4.1)
# ─────────────────────────────────────────────────────────────────────────────

def _sfi_one_task(col_idx, X_col_vals, X_tr_idx, X_te_idx,
                  y_vals, w_vals, n_estimators):
    """
    Single atomic SFI task: train on one (feature, fold) pair.
    No inner n_jobs — this IS the leaf-level unit of work.
    Flattenining to (feature × fold) tasks eliminates all nesting.
    """
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import BaggingClassifier

    base = DecisionTreeClassifier(
        criterion="entropy", max_features=1,
        class_weight="balanced", min_weight_fraction_leaf=0.02,
    )
    clf = BaggingClassifier(
        estimator=base, n_estimators=n_estimators,
        max_features=1.0, max_samples=1.0, oob_score=False,
        n_jobs=1, random_state=42,
    )

    X_tr = X_col_vals[X_tr_idx]
    X_te = X_col_vals[X_te_idx]
    y_tr = y_vals[X_tr_idx]
    y_te = y_vals[X_te_idx]
    w_tr = w_vals[X_tr_idx] if w_vals is not None else None

    if len(np.unique(y_tr)) < 2:
        return None
    try:
        fit = clf.fit(X_tr, y_tr, sample_weight=w_tr)
        prob = fit.predict_proba(X_te)
        return -log_loss(y_te, prob, labels=fit.classes_)
    except Exception:
        return None


def feat_imp_sfi(clf,
                 X: pd.DataFrame,
                 y: pd.Series,
                 years: pd.Series,
                 sample_weight: pd.Series = None) -> tuple:
    """
    Single Feature Importance: train the model on ONE feature at a time.
    Immune to substitution effects between correlated features.

    Parallelism: flattened to (feature × fold) atomic tasks so there is zero
    nesting. n_features × n_folds tasks run across all CPUs with n_jobs=-1 and
    n_jobs=1 inside each task — avoids loky's nested-spawn restriction entirely.

    Returns:
        summary: DataFrame(index=feature, columns=[mean, std])
        raw:     DataFrame(index=fold, columns=features) — per-fold log-loss scores.
    """
    cv = PurgedYearKFold(years)
    folds = list(cv.split(X, y, groups=years.values))
    n_folds = len(folds)

    p_pos = y.mean()
    null_ll = np.log(p_pos) * p_pos + np.log(1 - p_pos) * (1 - p_pos)

    X_vals = X.values
    y_vals = y.values
    w_vals = sample_weight.values if sample_weight is not None else None
    n_estimators = clf.n_estimators
    col_names = list(X.columns)

    # Build flat task list: one entry per (feature_idx, fold_idx)
    tasks = [
        (ci, fi, X_vals[:, ci:ci + 1], tr, te)
        for ci in range(len(col_names))
        for fi, (tr, te) in enumerate(folds)
    ]

    results = Parallel(n_jobs=-1, backend="loky")(
        delayed(_sfi_one_task)(ci, X_col, tr, te, y_vals, w_vals, n_estimators)
        for ci, fi, X_col, tr, te in tasks
    )

    # Reconstruct per-feature score lists
    raw_records = {col: [None] * n_folds for col in col_names}
    for (ci, fi, *_), score in zip(tasks, results):
        if score is not None:
            raw_records[col_names[ci]][fi] = score

    records = {}
    final_raw = {}
    for col in col_names:
        scores = [s for s in raw_records[col] if s is not None]
        if scores:
            records[col] = {"mean": np.mean(scores),
                            "std":  np.std(scores) * len(scores) ** -0.5,
                            "null_log_loss": null_ll}
            final_raw[col] = scores

    result = pd.DataFrame(records).T
    result.columns = ["mean", "std", "null_log_loss"]

    max_folds = max(len(v) for v in final_raw.values()) if final_raw else 0
    raw = pd.DataFrame(
        {col: vals + [np.nan] * (max_folds - len(vals))
         for col, vals in final_raw.items()}
    )
    return result.sort_values("mean", ascending=False), raw


# ─────────────────────────────────────────────────────────────────────────────
#  ONC  –  Optimal Number of Clusters  (de Prado MLAM Ch.4)
# ─────────────────────────────────────────────────────────────────────────────

def _cluster_quality(X: np.ndarray, labels: np.ndarray) -> float:
    """t-stat of silhouette scores (mean / std)."""
    sil = silhouette_samples(X, labels)
    return sil.mean() / (sil.std() + 1e-10)


def _onc_one_combo(X_vals, k, seed):
    """Try one (k, seed) combination; return (quality, labels) or None."""
    km = KMeans(n_clusters=k, n_init=1, random_state=seed)
    labels = km.fit_predict(X_vals)
    if len(np.unique(labels)) < 2:
        return None
    q = _cluster_quality(X_vals, labels)
    return q, labels


def onc_cluster(corr: pd.DataFrame,
                max_clusters: int = None,
                n_init: int = 20) -> dict:
    """
    Optimal Number of Clusters for a correlation matrix.
    Returns dict: {cluster_id: [feature_names]}.
    Uses silhouette t-stat as the quality criterion (de Prado MLAM §4.4).
    Grid search over seeds × k is parallelized.
    """
    X = ((1 - corr.fillna(0)) / 2.0) ** 0.5   # correlation → distance
    X_vals = X.values
    if max_clusters is None:
        max_clusters = X.shape[1] - 1

    n_total = n_init * (max_clusters - 1)
    n_jobs = min(get_n_jobs(), n_total)

    combos = [(k, seed) for seed in range(n_init) for k in range(2, max_clusters + 1)]
    results = Parallel(n_jobs=n_jobs, prefer="threads")(
        delayed(_onc_one_combo)(X_vals, k, seed) for k, seed in combos
    )

    best_quality = -np.inf
    best_labels  = None
    for r in results:
        if r is None:
            continue
        q, labels = r
        if q > best_quality:
            best_quality = q
            best_labels  = labels

    if best_labels is None:
        return {i: [col] for i, col in enumerate(corr.columns)}

    clusters = {}
    for i, label in enumerate(best_labels):
        clusters.setdefault(label, []).append(corr.columns[i])
    return clusters


# ─────────────────────────────────────────────────────────────────────────────
#  CFI  –  Clustered Feature Importance  (de Prado MLAM Ch.6)
# ─────────────────────────────────────────────────────────────────────────────

def feat_imp_cfi_mdi(fit: BaggingClassifier,
                     feat_names: list,
                     clusters: dict) -> pd.DataFrame:
    """Clustered MDI: sum the MDI values for all features in each cluster."""
    mdi, _ = feat_imp_mdi(fit, feat_names)
    records = {}
    for cluster_id, members in clusters.items():
        present = [m for m in members if m in mdi.index]
        if not present:
            continue
        cluster_name = f"Cluster_{cluster_id} ({', '.join(present)})"
        records[cluster_name] = {
            "mean": mdi.loc[present, "mean"].sum(),
            "std":  (mdi.loc[present, "std"] ** 2).sum() ** 0.5,
        }
    result = pd.DataFrame(records).T
    result.columns = ["mean", "std"]
    return result.sort_values("mean", ascending=False)


def feat_imp_cfi_mda(clf,
                     X: pd.DataFrame,
                     y: pd.Series,
                     years: pd.Series,
                     clusters: dict,
                     sample_weight: pd.Series = None) -> pd.DataFrame:
    """Clustered MDA: shuffle all features in a cluster simultaneously."""
    cv = PurgedYearKFold(years)
    base_scores   = []
    cluster_perms = {cid: [] for cid in clusters}

    for train_idx, test_idx in cv.split(X, y, groups=years.values):
        X_tr = X.iloc[train_idx]
        X_te = X.iloc[test_idx]
        y_tr = y.iloc[train_idx]
        y_te = y.iloc[test_idx]
        w_tr = sample_weight.iloc[train_idx] if sample_weight is not None else None

        if y_tr.nunique() < 2:
            continue
        fit = clf.fit(X_tr, y_tr, sample_weight=w_tr)
        prob = fit.predict_proba(X_te)
        base_scores.append(-log_loss(y_te, prob, labels=fit.classes_))

        for cid, members in clusters.items():
            present = [m for m in members if m in X.columns]
            if not present:
                cluster_perms[cid].append(base_scores[-1])
                continue
            X_te_perm = X_te.copy()
            shuffle_vals = X_te_perm[present].values.copy()
            np.random.shuffle(shuffle_vals)        # shuffle rows
            X_te_perm[present] = shuffle_vals
            prob_perm = fit.predict_proba(X_te_perm)
            cluster_perms[cid].append(
                -log_loss(y_te, prob_perm, labels=fit.classes_)
            )

    base = np.array(base_scores)
    records = {}
    for cid, members in clusters.items():
        perm = np.array(cluster_perms[cid])
        imp  = base - perm
        label = f"Cluster_{cid} ({', '.join([m for m in members if m in X.columns])})"
        records[label] = {"mean": imp.mean(),
                          "std":  imp.std() * len(imp) ** -0.5}

    result = pd.DataFrame(records).T
    result.columns = ["mean", "std"]
    return result.sort_values("mean", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
#  Synthetic validation  (de Prado MLAM §1.4 / AFML §8.6)
# ─────────────────────────────────────────────────────────────────────────────

def synthetic_validation(n_samples: int = 500,
                         n_informative: int = 3,
                         n_redundant: int = 3,
                         n_noise: int = 2,
                         random_state: int = 42) -> dict:
    """
    Generate a synthetic dataset where we KNOW which features are signal.
    Run MDI and SFI.  Confirm they recover the injected signal.

    Returns a dict with MDI and SFI DataFrames and a pass/fail summary.
    """
    from sklearn.datasets import make_classification

    rng = np.random.RandomState(random_state)
    n_features = n_informative + n_redundant + n_noise

    X_raw, y = make_classification(
        n_samples=n_samples,
        n_features=n_informative + n_noise,
        n_informative=n_informative,
        n_redundant=0,
        n_repeated=0,
        shuffle=False,
        random_state=random_state,
    )
    feat_names = (
        [f"INFO_{i}"   for i in range(n_informative)] +
        [f"NOISE_{i}"  for i in range(n_noise)]
    )

    # Add redundant features as noisy copies of informative ones
    redundant_cols = []
    for i in range(n_redundant):
        src = i % n_informative
        noisy = X_raw[:, src] + rng.normal(0, 0.5, n_samples)
        redundant_cols.append(noisy.reshape(-1, 1))
        feat_names.append(f"REDUND_{i}")

    X_full = np.hstack([X_raw] + redundant_cols)
    X_df   = pd.DataFrame(X_full, columns=feat_names)
    y_ser  = pd.Series(y)
    # Fake years for purged CV (treat every 50 samples as a "year")
    years  = pd.Series(np.repeat(np.arange(n_samples // 50), 50)[:n_samples])

    clf = build_rf(n_estimators=200)
    clf.fit(X_df, y_ser)

    mdi_result, _ = feat_imp_mdi(clf, feat_names)
    sfi_result, _ = feat_imp_sfi(
        build_rf(n_estimators=100), X_df, y_ser, years
    )

    # Evaluate: are all INFO features ranked above all NOISE features in MDI?
    info_rank  = mdi_result.index.get_indexer([f"INFO_{i}" for i in range(n_informative)])
    noise_rank = mdi_result.index.get_indexer([f"NOISE_{i}" for i in range(n_noise)])
    mdi_pass   = max(info_rank) < min(noise_rank) if len(noise_rank) > 0 else True

    print("\n=== Synthetic Validation ===")
    print(f"MDI recovers informative features above noise: {'✅' if mdi_pass else '❌'}")
    print("\nMDI top features:")
    print(mdi_result.head(n_informative + 2).to_string())

    return {"mdi": mdi_result, "sfi": sfi_result, "mdi_pass": mdi_pass}


# ─────────────────────────────────────────────────────────────────────────────
#  Statistical significance
# ─────────────────────────────────────────────────────────────────────────────

def compute_pvalues(raw: pd.DataFrame,
                    null_mean: float = 0.0,
                    alternative: str = "greater") -> pd.Series:
    """
    Wilcoxon signed-rank test per feature: H0 = importance equals null_mean.
    Non-parametric — no normality assumption required.

    For MDI raw: null_mean = 1 / n_features  (uniform importance)
    For MDA raw: null_mean = 0               (shuffling has no effect)
    For SFI raw: null_mean = null_log_loss   (no better than base-rate predictor)

    alternative: 'greater' (one-sided, we expect importance > null)
    Returns Series(index=feature, values=p_value).
    """
    pvals = {}
    for col in raw.columns:
        vals = raw[col].dropna().values
        diffs = vals - null_mean
        diffs = diffs[diffs != 0]  # Wilcoxon requires non-zero differences
        if len(diffs) < 4:
            pvals[col] = np.nan
        else:
            _, p = scipy_wilcoxon(diffs, alternative=alternative)
            pvals[col] = p
    return pd.Series(pvals, name="p_value")


# ─────────────────────────────────────────────────────────────────────────────
#  Bootstrap CI  (non-parametric confidence interval for the mean)
# ─────────────────────────────────────────────────────────────────────────────

def bootstrap_ci(values: np.ndarray,
                 n_boot: int = 2000,
                 ci: float = 0.95,
                 seed: int = 42) -> tuple:
    """
    Bootstrap confidence interval for the mean. No normality assumption.
    Returns (mean, lower_ci, upper_ci).
    """
    rng = np.random.default_rng(seed)
    boot_means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(n_boot)
    ])
    alpha = 1 - ci
    return (values.mean(),
            np.percentile(boot_means, 100 * alpha / 2),
            np.percentile(boot_means, 100 * (1 - alpha / 2)))


# ─────────────────────────────────────────────────────────────────────────────
#  Feature filtering  (de Prado MDI/MDA/SFI criteria + tiering)
# ─────────────────────────────────────────────────────────────────────────────

def filter_features(mdi_raw: pd.DataFrame,
                    mda_raw: pd.DataFrame,
                    sfi_raw: pd.DataFrame = None,
                    sfi_null: float = None,
                    mda_z_threshold: float = 1.0,
                    p_threshold: float = 0.10) -> pd.DataFrame:
    """
    Apply de Prado's filtering criteria to raw importance distributions.

    MDI pass: mean > 1/F AND (bootstrap CI lower > 1/F OR Wilcoxon p < p_threshold)
    MDA pass: mean > 0, z-score > mda_z_threshold, not detrimental (mean < 0)
    SFI pass: mean > sfi_null AND bootstrap CI lower > sfi_null

    Returns DataFrame with per-feature pass/fail, tier assignment, composite rank.
    Tiers: STRONG (all pass), MODERATE (2/3), WEAK (1/3), REJECTED (0 or detrimental).
    """
    all_features = set()
    for df in [mdi_raw, mda_raw, sfi_raw]:
        if df is not None and not df.empty:
            all_features.update(df.columns.tolist())

    n_features = len(all_features)
    threshold_1F = 1.0 / n_features if n_features > 0 else 0.0

    rows = []
    for feat in sorted(all_features):
        row = {"feature": feat}

        # ── MDI ──────────────────────────────────────────────────────────
        if mdi_raw is not None and feat in mdi_raw.columns:
            vals = mdi_raw[feat].dropna().values.astype(float)
            if len(vals) >= 4:
                mdi_mean, mdi_ci_lo, mdi_ci_hi = bootstrap_ci(vals)
                diffs = vals - threshold_1F
                diffs = diffs[diffs != 0]
                p_mdi = scipy_wilcoxon(diffs, alternative='greater')[1] if len(diffs) >= 4 else np.nan
                row.update({
                    "mdi_mean": mdi_mean, "mdi_ci_lo": mdi_ci_lo,
                    "mdi_ci_hi": mdi_ci_hi, "mdi_p": p_mdi,
                    "mdi_passes": (
                        mdi_mean > threshold_1F and
                        (mdi_ci_lo > threshold_1F or (not np.isnan(p_mdi) and p_mdi < p_threshold))
                    ),
                })
            else:
                row.update({"mdi_mean": np.nan, "mdi_passes": False})
        else:
            row.update({"mdi_mean": np.nan, "mdi_passes": np.nan})

        # ── MDA ──────────────────────────────────────────────────────────
        if mda_raw is not None and feat in mda_raw.columns:
            vals = mda_raw[feat].dropna().values.astype(float)
            if len(vals) >= 2:
                mda_mean = vals.mean()
                mda_std = vals.std()
                n = len(vals)
                mda_se = mda_std / np.sqrt(n) if n > 1 else np.inf
                mda_z = mda_mean / mda_se if mda_se > 0 else 0
                row.update({
                    "mda_mean": mda_mean, "mda_z": mda_z,
                    "mda_detrimental": mda_mean < 0,
                    "mda_passes": (
                        mda_mean > 0 and
                        mda_z >= mda_z_threshold and
                        not (mda_mean < 0)
                    ),
                })
            else:
                row.update({"mda_mean": np.nan, "mda_detrimental": False, "mda_passes": False})
        else:
            row.update({"mda_mean": np.nan, "mda_detrimental": False, "mda_passes": np.nan})

        # ── SFI ──────────────────────────────────────────────────────────
        if sfi_raw is not None and feat in sfi_raw.columns and sfi_null is not None:
            vals = sfi_raw[feat].dropna().values.astype(float)
            if len(vals) >= 4:
                sfi_mean, sfi_ci_lo, sfi_ci_hi = bootstrap_ci(vals)
                row.update({
                    "sfi_mean": sfi_mean, "sfi_ci_lo": sfi_ci_lo,
                    "sfi_ci_hi": sfi_ci_hi,
                    # Pass: mean better than coin-flip AND CI lower > null
                    # Scores are -log_loss: higher (less negative) = better
                    "sfi_passes": (sfi_mean > sfi_null and sfi_ci_lo > sfi_null),
                })
            else:
                row.update({"sfi_mean": np.nan, "sfi_passes": False})
        else:
            row.update({"sfi_mean": np.nan, "sfi_passes": np.nan})

        rows.append(row)

    report = pd.DataFrame(rows).set_index("feature")

    # Count methods available and passed
    for col in ["mdi_passes", "mda_passes", "sfi_passes"]:
        if col not in report.columns:
            report[col] = np.nan

    report["n_methods_available"] = (
        report["mdi_passes"].notna().astype(int) +
        report["mda_passes"].notna().astype(int) +
        report["sfi_passes"].notna().astype(int)
    )
    report["n_methods_passed"] = (
        report["mdi_passes"].fillna(False).astype(int) +
        report["mda_passes"].fillna(False).astype(int) +
        report["sfi_passes"].fillna(False).astype(int)
    )
    report["mda_kills"] = report.get("mda_detrimental", pd.Series(False, index=report.index)).fillna(False)

    def assign_tier(r):
        if r["mda_kills"]:
            return "REJECTED (detrimental)"
        n_avail = r["n_methods_available"]
        if n_avail == 0:
            return "UNKNOWN"
        ratio = r["n_methods_passed"] / n_avail
        if ratio == 1.0:
            return "STRONG"
        elif ratio >= 0.67:
            return "MODERATE"
        elif ratio >= 0.34:
            return "WEAK"
        return "REJECTED"

    report["tier"] = report.apply(assign_tier, axis=1)

    # Composite rank (lower = better)
    for method in ["mdi", "mda", "sfi"]:
        col = f"{method}_mean"
        if col in report.columns:
            report[f"{method}_rank"] = report[col].rank(ascending=False, na_option="bottom")
    rank_cols = [c for c in ["mdi_rank", "mda_rank", "sfi_rank"] if c in report.columns]
    if rank_cols:
        report["composite_rank"] = report[rank_cols].mean(axis=1)
        report = report.sort_values("composite_rank")

    return report


# ─────────────────────────────────────────────────────────────────────────────
#  PCA cross-check + weighted Kendall's tau  (de Prado structural validation)
# ─────────────────────────────────────────────────────────────────────────────

def pca_cross_check(X: pd.DataFrame,
                    importance_summary: pd.DataFrame) -> tuple:
    """
    De Prado's PCA cross-check:
    1. Run PCA on the feature matrix
    2. Rank features by variance-weighted absolute loading
    3. Compute weighted Kendall's tau between PCA ranks and MDI/MDA/SFI ranks

    A tau near 1 means supervised importance aligns with unsupervised structure —
    evidence the signal is not overfit.

    Args:
        X: feature matrix (samples × features)
        importance_summary: DataFrame with rank_MDI, rank_MDA, rank_SFI columns

    Returns:
        (pca_info, tau_results)
        pca_info: DataFrame with per-feature PCA rank and weighted loading
        tau_results: dict {method: {"tau": float, "p_value": float}}
    """
    # Drop columns that are all-NaN (median would still be NaN), then impute remainder
    X_clean = X.dropna(axis=1, how="all")
    X_filled = X_clean.fillna(X_clean.median())
    # Drop any remaining NaN columns (e.g. constant columns where median doesn't help)
    X_filled = X_filled.dropna(axis=1)

    pca = PCA()
    pca.fit(X_filled)

    # Variance-weighted absolute loadings: how much each feature contributes
    # to the overall variance structure
    loadings = np.abs(pca.components_)            # (n_components, n_features)
    var_ratios = pca.explained_variance_ratio_
    weighted_loadings = (loadings.T * var_ratios).sum(axis=1)

    pca_info = pd.DataFrame({
        "pca_weighted_loading": weighted_loadings,
        "pca_rank": pd.Series(weighted_loadings).rank(ascending=False).values,
    }, index=X_filled.columns)

    # Weighted Kendall's tau vs each importance method
    tau_results = {}
    for method in ["MDI", "MDA", "SFI"]:
        rank_col = f"rank_{method}"
        if rank_col not in importance_summary.columns:
            continue
        ranks = importance_summary[rank_col].dropna()
        common = pca_info.index.intersection(ranks.index)
        if len(common) < 3:
            tau_results[method] = {"tau": np.nan, "p_value": np.nan}
            continue
        # weightedtau: higher-ranked items get more weight (hyperbolic weighing)
        tau, p = weightedtau(
            pca_info.loc[common, "pca_rank"].values,
            ranks[common].values,
        )
        tau_results[method] = {
            "tau": float(tau) if not np.isnan(tau) else None,
            "p_value": float(p) if not np.isnan(p) else None,
        }

    # Print summary
    n_components_90 = np.searchsorted(np.cumsum(var_ratios), 0.90) + 1
    print(f"  PCA: {n_components_90} components explain 90% variance "
          f"(of {len(var_ratios)} total)")
    for method, res in tau_results.items():
        tau_str = f"{res['tau']:.3f}" if res['tau'] is not None else "N/A"
        p_str = f"{res['p_value']:.3f}" if res['p_value'] is not None else "N/A"
        print(f"  Kendall's tau (PCA vs {method}): {tau_str} (p={p_str})")

    return pca_info, tau_results


# ─────────────────────────────────────────────────────────────────────────────
#  Master importance runner
# ─────────────────────────────────────────────────────────────────────────────

def run_all_importance(X: pd.DataFrame,
                       y: pd.Series,
                       years: pd.Series,
                       sample_weight: pd.Series = None,
                       run_sfi: bool = True) -> dict:
    """
    Run feature importance following de Prado's full protocol:
      1. Unsupervised Pre-processing  — denoise/detone correlation matrix
      2. Unsupervised Discovery       — ONC clustering on denoised corr
      3. Supervised Attribution       — CFI (MDI + MDA on clusters)
      4. Unsupervised Orthogonalization — PCA on features, rank by eigenvalue
      5. Supervised Orthogonal Importance — MDI/MDA/SFI on PCA components
      6. Validation                   — weighted Kendall's tau (eigenvalue rank vs importance rank)
      7. Algorithmic Filtering        — drop MDI < 1/F, drop MDA < 0

    NOTE — functions that must be updated to fully implement this protocol:
      • denoise_corr() + detone_corr(): Not yet implemented. Step 1 currently uses
        the raw correlation matrix as a placeholder.
      • pca_cross_check(): Must be restructured to (a) project X into PCA components,
        (b) run MDI/MDA/SFI on those components, (c) rank components by eigenvalue,
        and (d) compute Kendall's tau between eigenvalue ranks and importance ranks.
        Currently it ranks original features by variance-weighted PCA loading and
        compares against a pre-built importance_summary — this does NOT match the
        new protocol. It will also need clf, y, and years passed in so it can run
        supervised importance directly on the components.
      • filter_features(): Step 7 filtering should ultimately use the importance
        results from the PCA components (Step 5) once pca_cross_check is updated.
        Until then it continues to operate on raw-feature MDI/MDA/SFI distributions.

    Returns a dict of DataFrames.
    """
    print(f"\nRunning feature importance on {X.shape[0]} samples, "
          f"{X.shape[1]} features, {years.nunique()} years...")

    # ── Step 1: Unsupervised pre-processing — denoise / detone corr ──────
    # TODO: replace with denoise_corr(corr) + detone_corr(...) once implemented.
    # Denoising (Marcenko-Pastur) removes random eigenvectors; detoning removes
    # the market "tone" (first eigenvector) so cluster structure is cleaner.
    print("\n1/7  Unsupervised pre-processing (denoising / detoning)...")
    corr = X.corr()
    corr_denoised = corr  # placeholder until denoise_corr / detone_corr exist

    # ── Step 2: Unsupervised discovery — ONC clustering ──────────────────
    print("2/7  ONC clustering (unsupervised structure discovery)...")
    clusters = onc_cluster(corr_denoised, max_clusters=max(2, X.shape[1] // 2))
    print(f"    Found {len(clusters)} clusters:")
    for cid, members in clusters.items():
        print(f"    Cluster {cid}: {members}")

    # ── Step 3: Supervised attribution — CFI (MDI + MDA on clusters) ─────
    print("3/7  CFI — Clustered Feature Importance (MDI + MDA on clusters)...")
    # These run in the main process so give them full CPU budget
    n_jobs_full = get_n_jobs()
    clf = build_rf(n_estimators=1000, n_jobs=n_jobs_full)
    clf.fit(X, y, sample_weight=sample_weight)

    cfi_mdi = feat_imp_cfi_mdi(clf, list(X.columns), clusters)
    cfi_mda = feat_imp_cfi_mda(
        build_rf(n_estimators=300, n_jobs=n_jobs_full), X, y, years, clusters, sample_weight
    )

    # ── Steps 4–6: PCA + importance on components + Kendall's tau ────────
    # TODO: once pca_cross_check() is updated, Steps 4–6 will live entirely
    # inside that call:
    #   Step 4 — fit PCA on X; rank components by eigenvalue
    #   Step 5 — run MDI/MDA/SFI on PCA-transformed X (components as features)
    #   Step 6 — weighted Kendall's tau between eigenvalue ranks and importance ranks
    #
    # For now, MDI/MDA/SFI still run on the original features (not PCA components)
    # so that the existing pca_cross_check() signature is satisfied and Step 7
    # filtering has per-feature distributions to work with.

    print("4/7  MDI (in-sample, on original features — will move to PCA components)...")
    mdi, mdi_raw = feat_imp_mdi(clf, list(X.columns))
    mdi_pvals = compute_pvalues(mdi_raw, null_mean=1.0 / X.shape[1])

    print("5/7  MDA (purged year-CV, on original features — will move to PCA components)...")
    # MDA folds are parallelized internally; pass n_estimators so _mda_one_fold reconstructs correctly
    mda, mda_raw = feat_imp_mda(
        build_rf(n_estimators=500, n_jobs=1), X, y, years, sample_weight
    )
    mda_pvals = compute_pvalues(mda_raw, null_mean=0.0)

    sfi = None
    sfi_raw = None
    sfi_pvals = None
    null_ll = 0.0
    if run_sfi:
        print("5/7  SFI (standalone, purged year-CV — will move to PCA components)...")
        # SFI features are parallelized externally; inner jobs set in _sfi_one_feature
        sfi, sfi_raw = feat_imp_sfi(
            build_rf(n_estimators=300, n_jobs=1), X, y, years, sample_weight
        )
        null_ll = sfi["null_log_loss"].iloc[0] if "null_log_loss" in sfi.columns else 0.0
        sfi_pvals = compute_pvalues(sfi_raw, null_mean=null_ll, alternative="greater")

    # Build per-feature summary for pca_cross_check (temporary until Step 5
    # moves inside pca_cross_check and runs on PCA components)
    summary = mdi[["mean"]].rename(columns={"mean": "MDI"})
    summary = summary.join(mdi_pvals.rename("p_MDI"), how="left")
    summary = summary.join(mda[["mean"]].rename(columns={"mean": "MDA"}), how="outer")
    summary = summary.join(mda_pvals.rename("p_MDA"), how="left")
    if sfi is not None:
        summary = summary.join(sfi[["mean"]].rename(columns={"mean": "SFI"}), how="outer")
        summary = summary.join(sfi_pvals.rename("p_SFI"), how="left")
    summary["rank_MDI"] = summary["MDI"].rank(ascending=False)
    summary["rank_MDA"] = summary["MDA"].rank(ascending=False)
    if sfi is not None:
        summary["rank_SFI"] = summary["SFI"].rank(ascending=False)
    summary["avg_rank"] = summary[[c for c in summary.columns if c.startswith("rank_")]].mean(axis=1)
    summary = summary.sort_values("avg_rank")

    print("\n=== Feature Importance Summary ===")
    print(summary.to_string())

    print("\n6/7  PCA cross-check + weighted Kendall's tau...")
    pca_info, tau_results = pca_cross_check(X, summary)

    # ── Step 7: Algorithmic filtering ─────────────────────────────────────
    print("\n7/7  Algorithmic filtering (MDI < 1/F + MDA detrimental)...")
    sfi_null_val = null_ll if run_sfi else None
    filter_report = filter_features(
        mdi_raw, mda_raw,
        sfi_raw=sfi_raw,
        sfi_null=sfi_null_val,
    )
    tier_counts = filter_report["tier"].value_counts()
    for tier, count in tier_counts.items():
        print(f"    {tier}: {count}")
    survivors = filter_report[filter_report["tier"].isin(["STRONG", "MODERATE"])]
    print(f"    → {len(survivors)} features survive (STRONG + MODERATE)")

    return {
        "mdi":             mdi,
        "mdi_raw":         mdi_raw,
        "mda":             mda,
        "mda_raw":         mda_raw,
        "sfi":             sfi,
        "sfi_raw":         sfi_raw,
        "cfi_mdi":         cfi_mdi,
        "cfi_mda":         cfi_mda,
        "clusters":        clusters,
        "summary":         summary,
        "filter_report":   filter_report,
        "survivors":       survivors.index.tolist(),
        "pca_info":        pca_info,
        "tau_results":     tau_results,
    }
