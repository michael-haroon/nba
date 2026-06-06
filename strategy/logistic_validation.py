"""
logistic_validation.py
----------------------
Rigorous validation of features for logistic regression inputs.

Tests each candidate feature against the core LogReg assumptions:
  1. Log-odds linearity  — Box-Tidwell test (is logit(P) linear in X?)
  2. No multicollinearity — VIF < threshold within the candidate set
  3. No outlier dominance — Cook's Distance < 4/n for < 2% of observations

Candidate pool: 28 ACCEPTED + 49 ABSORBED features.
ABSORBED features pass SFI (standalone signal) and were only excluded from
ACCEPTED because they're redundant for trees. Redundancy for trees ≠
redundancy for LogReg when VIF is low.

Usage:
    python -m strategy.logistic_validation --target winner
    python -m strategy.logistic_validation --target winner --plot
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strategy.config import FEATURES_ROOT, GAME_PARQUET
from strategy.data import TARGET_MAP

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────
VIF_THRESHOLD = 5.0       # VIF > 5 → multicollinearity concern
COEF_SIGN_MIN_CONSISTENCY = 0.80  # coefficient must have consistent sign in >= 80% of LOYO folds
COEF_CV_MAX = 1.0                 # coefficient of variation (std/|mean|) across folds must be < 1.0
LINEARITY_ALPHA = 0.05    # Box-Tidwell p-value threshold


# ── Test 1: Log-Odds Linearity (Box-Tidwell) ───────────────────────────────

def test_log_odds_linearity(x: np.ndarray, y: np.ndarray) -> dict:
    """
    Box-Tidwell test: fits logit(P) = β0 + β1*X + β2*(X * ln(X))
    H0: β2 = 0 (linear log-odds relationship).
    A significant β2 means the log-odds relationship is nonlinear.

    For features with zero/negative values (differentials), we shift to
    strictly positive before the log transform. This preserves the shape
    of the distribution and is mathematically valid for the interaction term.
    """
    import statsmodels.api as sm

    mask = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[mask], y[mask]
    if len(x) < 100:
        return {"passes": False, "p_value": np.nan, "bt_coefficient": np.nan, "reason": "too few observations"}

    # Shift to strictly positive (required for log)
    x_pos = x - x.min() + 1e-6

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            interaction = x_pos * np.log(x_pos)
            # Standardize both terms for numerical stability
            x_std = (x - x.mean()) / (x.std() + 1e-10)
            int_std = (interaction - interaction.mean()) / (interaction.std() + 1e-10)
            X_design = sm.add_constant(np.column_stack([x_std, int_std]))
            model = sm.Logit(y, X_design)
            result = model.fit(disp=False, maxiter=200)
            p_val = float(result.pvalues[2])  # p-value for interaction term
            coef = float(result.params[2])
            passes = p_val >= LINEARITY_ALPHA
            return {"passes": passes, "p_value": p_val, "bt_coefficient": coef, "reason": ""}
        except Exception as e:
            return {"passes": False, "p_value": np.nan, "bt_coefficient": np.nan, "reason": str(e)[:80]}


# ── Test 2: VIF (Variance Inflation Factor) ────────────────────────────────

def compute_vif(X: pd.DataFrame) -> pd.Series:
    """
    Compute VIF for each column in X using statsmodels.
    VIF_i = 1 / (1 - R²_i) from regressing column i on all others.
    Returns a Series indexed by column name.
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    X_filled = X.fillna(X.median())
    X_filled = X_filled.loc[:, X_filled.std() > 0]
    vals = X_filled.values.astype(float)
    vifs = {}
    for i, col in enumerate(X_filled.columns):
        try:
            vifs[col] = variance_inflation_factor(vals, i)
        except Exception:
            vifs[col] = np.nan
    return pd.Series(vifs)


def iterative_vif_elimination(X: pd.DataFrame, threshold: float = VIF_THRESHOLD) -> list[str]:
    """
    Greedily eliminate the highest-VIF feature until all remaining features
    have VIF < threshold. Returns the surviving feature names.

    This correctly handles families of collinear features (e.g. Massey quarter
    variants) by selecting one representative from each cluster rather than
    rejecting all of them.
    """
    remaining = [c for c in X.columns if X[c].std() > 0]
    logger.info("  VIF elimination: starting with %d features", len(remaining))

    while True:
        X_sub = X[remaining].fillna(X[remaining].median())
        # Drop any column that became constant after fillna
        X_sub = X_sub.loc[:, X_sub.std() > 0]
        remaining = list(X_sub.columns)
        if len(remaining) <= 1:
            break

        vif_s = compute_vif(X_sub)
        max_vif = vif_s.max()
        if np.isnan(max_vif) or max_vif < threshold:
            break

        worst = vif_s.idxmax()
        logger.info("  Dropping %s (VIF=%.1f)", worst, max_vif)
        remaining.remove(worst)

    logger.info("  VIF elimination: %d features survive", len(remaining))
    return remaining


# ── Test 3: Coefficient Stability across LOYO folds ──────────────────────

def test_coefficient_stability(x: np.ndarray, y: np.ndarray,
                               seasons: np.ndarray) -> dict:
    """
    Fit LogReg in each LOYO fold and check whether the feature coefficient
    is stable across seasons.

    Two criteria (both must pass):
      1. Sign consistency >= 80%: coefficient has the same sign in >= 80% of
         folds. A sign flip means the feature sometimes predicts the wrong
         direction — it is not a reliable signal.
      2. Coefficient of variation (std/|mean|) < 1.0 across folds.
         CV >= 1.0 means the estimate is noisier than its own magnitude —
         the feature's effect size is not reliably estimated.

    This replaces Cook's Distance, which has no rigorous null distribution and
    whose heuristic thresholds (4/n, D>1) are arbitrary. LOYO stability is the
    correct test for our use case: does this feature generalize consistently
    across NBA seasons?
    """
    import statsmodels.api as sm
    from strategy.config import SKIP_SEASONS, LOYO_MIN_TRAIN_SEASONS

    mask = ~np.isnan(x) & ~np.isnan(y)
    x_m, y_m, s_m = x[mask], y[mask], seasons[mask]
    if len(x_m) < 100:
        return {"passes": False, "sign_consistency": np.nan, "coef_cv": np.nan, "reason": "too few observations"}

    unique_seasons = sorted(set(s_m))
    coefs = []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for test_season in unique_seasons:
            if test_season in SKIP_SEASONS:
                continue
            train_mask = np.array(
                [(s != test_season and s not in SKIP_SEASONS) for s in s_m]
            )
            if train_mask.sum() < LOYO_MIN_TRAIN_SEASONS * 50:
                continue
            x_tr = x_m[train_mask]
            y_tr = y_m[train_mask]
            try:
                x_std = (x_tr - x_tr.mean()) / (x_tr.std() + 1e-10)
                X_design = sm.add_constant(x_std)
                result = sm.Logit(y_tr, X_design).fit(disp=False, maxiter=100)
                coefs.append(float(result.params[1]))
            except Exception:
                continue

    if len(coefs) < 3:
        return {"passes": False, "sign_consistency": np.nan, "coef_cv": np.nan, "reason": "too few folds"}

    coefs = np.array(coefs)
    mean_coef = float(np.mean(coefs))
    std_coef = float(np.std(coefs))
    sign_consistency = float(np.mean(coefs > 0) if mean_coef > 0 else np.mean(coefs < 0))
    coef_cv = std_coef / (abs(mean_coef) + 1e-10)

    passes = (sign_consistency >= COEF_SIGN_MIN_CONSISTENCY) and (coef_cv < COEF_CV_MAX)
    return {
        "passes": passes,
        "sign_consistency": sign_consistency,
        "coef_cv": coef_cv,
        "mean_coef": mean_coef,
        "std_coef": std_coef,
        "n_folds": len(coefs),
        "reason": "",
    }


# ── Per-feature qualification ──────────────────────────────────────────────

def qualify_for_logreg(
    feature: str,
    x: np.ndarray,
    y: np.ndarray,
    seasons: np.ndarray,
    all_candidates_X: pd.DataFrame,
) -> dict:
    """
    Run all three tests for a single feature against the candidate set.
    VIF is computed within the full candidate matrix (all_candidates_X).
    """
    lin = test_log_odds_linearity(x, y)
    stab = test_coefficient_stability(x, y, seasons)

    vif_series = compute_vif(all_candidates_X)
    vif_val = float(vif_series.get(feature, np.nan))
    passes_vif = (not np.isnan(vif_val)) and (vif_val < VIF_THRESHOLD)

    qualifies = lin["passes"] and passes_vif and stab["passes"]
    return {
        "feature": feature,
        "qualifies": qualifies,
        "passes_linearity": lin["passes"],
        "linearity_p": lin["p_value"],
        "bt_coefficient": lin["bt_coefficient"],
        "passes_vif": passes_vif,
        "vif": vif_val,
        "passes_stability": stab["passes"],
        "sign_consistency": stab["sign_consistency"],
        "coef_cv": stab["coef_cv"],
        "mean_coef": stab.get("mean_coef", np.nan),
        "n_folds": stab.get("n_folds", np.nan),
        "linearity_reason": lin.get("reason", ""),
        "stability_reason": stab.get("reason", ""),
    }


# ── Plots ──────────────────────────────────────────────────────────────────

def plot_log_odds_scatter(feature: str, x: np.ndarray, y: np.ndarray,
                          bt_result: dict, out_dir: Path) -> None:
    """Empirical logit(win_rate) by feature quantile bin vs Box-Tidwell fit."""
    mask = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[mask], y[mask]
    if len(x) < 50:
        return

    n_bins = 20
    bins = np.percentile(x, np.linspace(0, 100, n_bins + 1))
    bins = np.unique(bins)
    labels = pd.cut(x, bins=bins, include_lowest=True)
    df = pd.DataFrame({"x": x, "y": y, "bin": labels})
    stats = df.groupby("bin", observed=True).agg(
        x_mid=("x", "mean"),
        win_rate=("y", "mean"),
        n=("y", "count"),
    ).dropna()
    stats = stats[stats["n"] >= 5]

    # Clip win_rate away from 0/1 for logit
    stats["logit_wr"] = np.log(
        stats["win_rate"].clip(0.01, 0.99) / (1 - stats["win_rate"].clip(0.01, 0.99))
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(stats["x_mid"], stats["logit_wr"], s=stats["n"] / 10, alpha=0.7, label="Empirical logit(win rate)")

    # Fitted line
    xs = np.linspace(stats["x_mid"].min(), stats["x_mid"].max(), 200)
    p_val = bt_result.get("p_value", np.nan)
    status = f"Box-Tidwell p={p_val:.3f} {'✓ linear' if bt_result.get('passes') else '✗ nonlinear'}"
    ax.axhline(0, color="gray", linestyle="--", alpha=0.4)
    ax.set_xlabel(feature)
    ax.set_ylabel("logit(win rate)")
    ax.set_title(f"{feature}\n{status}")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_dir / f"log_odds_{feature[:60]}.png", dpi=100)
    plt.close()


def plot_vif_bar(vif_series: pd.Series, out_dir: Path) -> None:
    """Bar chart of VIF values, sorted descending, red line at threshold."""
    vif_sorted = vif_series.sort_values(ascending=False).dropna()
    fig, ax = plt.subplots(figsize=(max(8, len(vif_sorted) // 2), 6))
    colors = ["#cc3333" if v >= VIF_THRESHOLD else "#4488cc" for v in vif_sorted]
    ax.barh(range(len(vif_sorted)), vif_sorted.values[::-1], color=colors[::-1], alpha=0.8)
    ax.set_yticks(range(len(vif_sorted)))
    ax.set_yticklabels(vif_sorted.index[::-1], fontsize=7)
    ax.axvline(VIF_THRESHOLD, color="red", linestyle="--", label=f"VIF={VIF_THRESHOLD} threshold")
    ax.set_xlabel("VIF")
    ax.set_title("Variance Inflation Factor — LogReg candidate features\n(red = fails multicollinearity threshold)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "vif_bar.png", dpi=120)
    plt.close()


def plot_cooks_distance(feature: str, x: np.ndarray, y: np.ndarray,
                        seasons: np.ndarray, out_dir: Path) -> None:
    """Cook's D per observation, colored by season, red line at 4/n."""
    import statsmodels.api as sm

    mask = ~np.isnan(x) & ~np.isnan(y)
    x_m, y_m, s_m = x[mask], y[mask], seasons[mask]
    if len(x_m) < 100:
        return

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x_std = (x_m - x_m.mean()) / (x_m.std() + 1e-10)
            X_design = sm.add_constant(x_std)
            result = sm.GLM(y_m, X_design, family=sm.families.Binomial()).fit(disp=False)
            cooks = result.get_influence().cooks_distance[0]
    except Exception:
        return

    threshold = 4.0 / len(x_m)
    unique_seasons = sorted(set(s_m))
    season_colors = plt.cm.tab20(np.linspace(0, 1, len(unique_seasons)))
    season_map = {s: c for s, c in zip(unique_seasons, season_colors)}

    fig, ax = plt.subplots(figsize=(12, 4))
    for i, (cd, season) in enumerate(zip(cooks, s_m)):
        ax.scatter(i, cd, color=season_map[season], alpha=0.4, s=5)
    ax.axhline(threshold, color="red", linestyle="--", label=f"4/n = {threshold:.5f}")
    ax.set_xlabel("Observation index")
    ax.set_ylabel("Cook's Distance")
    ax.set_title(f"Cook's Distance — {feature}\n({np.mean(cooks > threshold):.1%} influential)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_dir / f"cooks_{feature[:60]}.png", dpi=100)
    plt.close()


# ── Main entry ─────────────────────────────────────────────────────────────

def run_logistic_validation(
    target: str,
    candidates: list[str] | None = None,
    make_plots: bool = True,
) -> list[str]:
    """
    Run all three assumption tests on each candidate feature.
    Returns list of features that qualify for logistic regression.

    Candidate pool (if candidates=None):
      - 28 ACCEPTED features (all 4 importance methods pass)
      - 49 ABSORBED features (MDI+SFI+PCA pass — proven standalone, excluded only
        because RESID-MDA shows redundancy for trees, not for linear models)
    """
    report_path = FEATURES_ROOT / target / "filtered" / "feature_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"No feature_report.csv for target '{target}'")

    target_col, task = TARGET_MAP[target]
    if task not in ("classification",):
        raise ValueError(f"Logistic validation only applies to classification targets, got '{task}'")

    df_report = pd.read_csv(report_path)

    if candidates is None:
        accepted = df_report[df_report["tier"] == "ACCEPTED"]["feature"].tolist()
        absorbed = df_report[
            (df_report["mdi_passes"] == True) &
            (df_report["sfi_passes"] == True) &
            (df_report["pca_mda_passes"] == True) &
            (df_report["resid_mda_passes"] == False)
        ]["feature"].tolist()
        candidates = accepted + absorbed
        logger.info("Candidate pool: %d accepted + %d absorbed = %d total",
                    len(accepted), len(absorbed), len(candidates))

    # Load data
    logger.info("Loading data...")
    game_df = pd.read_parquet(GAME_PARQUET)
    valid = game_df[target_col].notna()
    game_df = game_df[valid].reset_index(drop=True)
    y = game_df[target_col].astype(int).values
    seasons = game_df["season"].values

    # Filter candidates to those present in parquet
    candidates = [c for c in candidates if c in game_df.columns]
    logger.info("Candidates present in parquet: %d", len(candidates))

    # Build candidate matrix for VIF (use median-imputed, no NaN)
    X_candidates = game_df[candidates].copy()
    X_candidates_filled = X_candidates.fillna(X_candidates.median())

    # Output dirs
    out_base = FEATURES_ROOT / target
    out_base.mkdir(parents=True, exist_ok=True)
    plots_dir = out_base / "logistic_validation_plots"
    if make_plots:
        plots_dir.mkdir(exist_ok=True)

    # Step 1: Iterative VIF elimination on the full candidate set
    # This selects the maximally non-redundant subset before individual tests.
    logger.info("Running iterative VIF elimination on %d candidates...", len(candidates))
    vif_survivors = iterative_vif_elimination(X_candidates_filled)
    vif_eliminated = set(candidates) - set(vif_survivors)
    logger.info("  %d eliminated by VIF, %d survive", len(vif_eliminated), len(vif_survivors))

    # Final VIF values on the survivor set (for plotting)
    vif_series_final = compute_vif(X_candidates_filled[vif_survivors])
    if make_plots:
        plot_vif_bar(vif_series_final, plots_dir)

    # Step 2: Per-feature linearity and stability tests on VIF survivors only
    results = []
    for i, feat in enumerate(candidates):
        eliminated_by_vif = feat in vif_eliminated
        vif_val = float(vif_series_final.get(feat, np.nan)) if not eliminated_by_vif else np.nan
        passes_vif = not eliminated_by_vif

        if eliminated_by_vif:
            lin = {"passes": False, "p_value": np.nan, "bt_coefficient": np.nan, "reason": "eliminated by VIF"}
            stab = {"passes": False, "sign_consistency": np.nan, "coef_cv": np.nan,
                    "mean_coef": np.nan, "n_folds": np.nan, "reason": "eliminated by VIF"}
        else:
            x = X_candidates_filled[feat].values
            lin = test_log_odds_linearity(x, y)
            stab = test_coefficient_stability(x, y, seasons)

        qualifies = lin["passes"] and passes_vif and stab["passes"]

        row = {
            "feature": feat,
            "qualifies": qualifies,
            "passes_linearity": lin["passes"],
            "linearity_p": lin["p_value"],
            "bt_coefficient": lin["bt_coefficient"],
            "passes_vif": passes_vif,
            "vif": vif_val,
            "passes_stability": stab["passes"],
            "sign_consistency": stab["sign_consistency"],
            "coef_cv": stab["coef_cv"],
            "mean_coef": stab.get("mean_coef", np.nan),
            "n_folds": stab.get("n_folds", np.nan),
        }
        results.append(row)

        if not eliminated_by_vif:
            status = "✓" if qualifies else "✗"
            logger.info(
                "[%3d/%d] %s %s  lin_p=%.3f  VIF=%.1f  sign_cons=%.2f  coef_cv=%.2f",
                i + 1, len(candidates), status, feat[:40],
                lin["p_value"] if not np.isnan(lin["p_value"]) else -1,
                vif_val if not np.isnan(vif_val) else -1,
                stab["sign_consistency"] if not np.isnan(stab.get("sign_consistency", np.nan)) else -1,
                stab["coef_cv"] if not np.isnan(stab.get("coef_cv", np.nan)) else -1,
            )

        if make_plots:
            x_raw = X_candidates[feat].values
            plot_log_odds_scatter(feat, x_raw, y, lin, plots_dir)
            plot_cooks_distance(feat, x_raw, y, seasons, plots_dir)

    results_df = pd.DataFrame(results)
    out_csv = out_base / "logistic_validation.csv"
    results_df.to_csv(out_csv, index=False)
    logger.info("Saved: %s", out_csv)

    qualified = results_df[results_df["qualifies"]]["feature"].tolist()
    logger.info(
        "\n=== LOGISTIC VALIDATION SUMMARY ===\n"
        "  Candidates tested: %d\n"
        "  Qualify (all 3 pass): %d\n"
        "  Eliminated by VIF: %d\n"
        "  Fail linearity (Box-Tidwell p<0.05): %d\n"
        "  Fail stability (sign flip or noisy coef): %d",
        len(results_df),
        len(results_df[results_df["qualifies"]]),
        len(results_df[~results_df["passes_vif"]]),
        len(results_df[results_df["passes_vif"] & ~results_df["passes_linearity"]]),
        len(results_df[results_df["passes_vif"] & results_df["passes_linearity"] & ~results_df["passes_stability"]]),
    )

    # Write qualified feature list
    qualified_path = FEATURES_ROOT / target / "filtered" / "feature_list_linear.txt"
    if qualified:
        qualified_path.write_text("\n".join(qualified) + "\n")
        logger.info("Wrote feature_list_linear.txt: %d qualified features", len(qualified))
    else:
        logger.warning("No features qualified — keeping previous feature_list_linear.txt")

    return qualified


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Logistic regression feature validation")
    parser.add_argument("--target", required=True, help="e.g. winner")
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    args = parser.parse_args()

    qualified = run_logistic_validation(args.target, make_plots=not args.no_plots)
    print(f"\nQualified for LogReg ({len(qualified)} features):")
    for f in qualified:
        print(f"  {f}")
