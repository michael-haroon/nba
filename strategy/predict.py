"""
predict.py
----------
Predict the next game(s) using the ensemble pkls and the latest team stats
from game_features.parquet.

Runs all trained targets by default. Cross-checks across models since they
predict each other (H1+H2 should sum to full game, spread implies winner, etc.).

Usage:
    python -m strategy.predict SAS NYK
    python -m strategy.predict SAS NYK --target winner
    python -m strategy.predict SAS NYK --target h1_spread
    python -m strategy.predict CLE IND BOS NYK   # multiple matchups
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

from strategy.config import (
    GAME_PARQUET, OUTPUT_DIR,
    SPREAD_RESID_DF, SPREAD_RESID_SCALE,
    TOTAL_RESID_DF, TOTAL_RESID_SCALE,
    WINNER_STD_THRESHOLDS, WINNER_CONFIDENCE_MULTIPLIERS,
)
from strategy.ensemble import predict_from_pkl


# ── Target metadata ───────────────────────────────────────────────────────────

_TARGET_ORDER = [
    "winner", "home_wins_h1", "home_wins_h2", "overtime",
    "spread", "h1_spread", "h2_spread",
    "h1_total", "h2_total", "total",   # halves must run before synthetic total
]

_TARGET_META = {
    "winner":       {"label": "GAME WINNER",   "task": "clf",        "spread_peer": "spread"},
    "home_wins_h1": {"label": "H1 WINNER",     "task": "clf",        "spread_peer": "h1_spread"},
    "home_wins_h2": {"label": "H2 WINNER",     "task": "clf",        "spread_peer": "h2_spread"},
    "overtime":     {"label": "OVERTIME",      "task": "clf",        "spread_peer": None},
    "spread":       {"label": "GAME SPREAD",   "task": "reg_spread"},
    "h1_spread":    {"label": "H1 SPREAD",     "task": "reg_spread"},
    "h2_spread":    {"label": "H2 SPREAD",     "task": "reg_spread"},
    "total":        {"label": "GAME TOTAL",    "task": "reg_total"},
    "h1_total":     {"label": "H1 TOTAL",      "task": "reg_total"},
    "h2_total":     {"label": "H2 TOTAL",      "task": "reg_total"},
}


# ── Bundle loading ────────────────────────────────────────────────────────────

def _load_bundle(target: str) -> dict:
    pkl_new = OUTPUT_DIR / target / "ensemble.pkl"
    pkl_legacy = OUTPUT_DIR / "ensemble" / f"{target}_ensemble_models.pkl"
    pkl = pkl_new if pkl_new.exists() else pkl_legacy
    if not pkl.exists():
        raise FileNotFoundError(
            f"No ensemble pkl for '{target}'. Checked:\n  {pkl_new}\n  {pkl_legacy}")
    with open(pkl, "rb") as f:
        return pickle.load(f)


def _get_features(bundle: dict) -> list[str]:
    models_list = bundle.get("specialists", bundle.get("models", []))
    return sorted(set(f for m in models_list for f in m["features"]))


# ── t-dist params — no hardcoded fallback for non-standard targets ────────────

def _fit_t_from_oof(target: str) -> tuple[float, float]:
    """Fit t-dist to OOF residuals for a target. Raises RuntimeError if OOF missing."""
    oof_path = OUTPUT_DIR / target / "ensemble_oof.csv"
    if not oof_path.exists():
        raise RuntimeError(
            f"No calibration stored in bundle and no OOF CSV at {oof_path}. "
            f"Cannot fit residual distribution for '{target}'.")
    oof = pd.read_csv(oof_path)
    residuals = oof["y_true"] - oof["pred_ensemble"]
    df, loc, scale = t_dist.fit(residuals, floc=0)
    return float(df), float(scale)


def _synthetic_total_params() -> tuple[float, float, float, float]:
    """
    Derive game-total distribution from h1_total + h2_total OOF residuals.

    Returns (res_df, res_scale, cov_residuals, rho_model_std) where:
      res_df, res_scale: t-dist fitted to synthetic residuals (r1 + r2)
      cov_residuals: Cov(r_H1, r_H2) for variance propagation
      rho_model_std: correlation of per-sample specialist stds between h1/h2
                     (used for combining ensemble disagreement stds)

    Caches result so repeated calls within a run pay no I/O cost.
    Raises RuntimeError if either OOF CSV is missing.
    """
    if hasattr(_synthetic_total_params, "_cache"):
        return _synthetic_total_params._cache

    for name in ("h1_total", "h2_total"):
        p = OUTPUT_DIR / name / "ensemble_oof.csv"
        if not p.exists():
            raise RuntimeError(f"Synthetic total requires {p} — not found.")

    o1 = pd.read_csv(OUTPUT_DIR / "h1_total" / "ensemble_oof.csv")
    o2 = pd.read_csv(OUTPUT_DIR / "h2_total" / "ensemble_oof.csv")
    # normalise column name
    for o in (o1, o2):
        if "pred_ensemble" in o.columns and "y_pred_ensemble" not in o.columns:
            o.rename(columns={"pred_ensemble": "y_pred_ensemble"}, inplace=True)

    r1 = (o1["y_true"] - o1["y_pred_ensemble"]).values
    r2 = (o2["y_true"] - o2["y_pred_ensemble"]).values
    r_synth = r1 + r2
    cov = float(np.cov(r1, r2)[0, 1])

    # Correlation of per-sample model disagreement (specialist stds)
    pred_cols_1 = [c for c in o1.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    pred_cols_2 = [c for c in o2.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    std1 = o1[pred_cols_1].std(axis=1).values
    std2 = o2[pred_cols_2].std(axis=1).values
    rho_std = float(np.corrcoef(std1, std2)[0, 1])

    df_s, _, scale_s = t_dist.fit(r_synth, floc=0)
    result = (float(df_s), float(scale_s), cov, rho_std)
    _synthetic_total_params._cache = result
    return result


def _oof_pred_stats(target: str) -> dict:
    """
    Load OOF prediction-space statistics for a target (cached per process).

    Returns:
      pred_mean, pred_std     — mean/std of ŷ_OOF (prediction space)
      ens_std_median          — median ensemble-disagreement across OOF rows
      heteroscedastic_slope   — OLS slope of |resid| ~ |Z_pred| (pts per Z-unit)
    """
    cache_attr = f"_cache_{target}"
    if hasattr(_oof_pred_stats, cache_attr):
        return getattr(_oof_pred_stats, cache_attr)

    oof_path = OUTPUT_DIR / target / "ensemble_oof.csv"
    if not oof_path.exists():
        result = {}
        setattr(_oof_pred_stats, cache_attr, result)
        return result

    oof = pd.read_csv(oof_path)
    if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
        oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})

    y_hat = oof["y_pred_ensemble"].values
    pred_cols = [c for c in oof.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    ens_std = oof[pred_cols].std(axis=1).values if len(pred_cols) > 1 else np.zeros(len(oof))

    pred_mean = float(y_hat.mean())
    pred_std  = float(y_hat.std())

    result = {
        "pred_mean": pred_mean,
        "pred_std":  pred_std,
        "ens_std_median": float(np.median(ens_std)),
        "ens_std_p75":    float(np.percentile(ens_std, 75)),
        "ens_std_p95":    float(np.percentile(ens_std, 95)),
    }
    setattr(_oof_pred_stats, cache_attr, result)
    return result


def _oof_line_accuracy(target: str, ou_lines: np.ndarray) -> dict[float, float]:
    """Over/under accuracy at each line from OOF predictions.

    For 'total', reconstructs synthetic OOF from h1_total + h2_total.
    Returns {line: accuracy_fraction}.
    """
    if target == "total":
        o1_path = OUTPUT_DIR / "h1_total" / "ensemble_oof.csv"
        o2_path = OUTPUT_DIR / "h2_total" / "ensemble_oof.csv"
        if not (o1_path.exists() and o2_path.exists()):
            return {}
        o1 = pd.read_csv(o1_path)
        o2 = pd.read_csv(o2_path)
        for o in (o1, o2):
            if "pred_ensemble" in o.columns and "y_pred_ensemble" not in o.columns:
                o.rename(columns={"pred_ensemble": "y_pred_ensemble"}, inplace=True)
        y = (o1["y_true"] + o2["y_true"]).values
        yhat = (o1["y_pred_ensemble"] + o2["y_pred_ensemble"]).values
    else:
        oof_path = OUTPUT_DIR / target / "ensemble_oof.csv"
        if not oof_path.exists():
            return {}
        oof = pd.read_csv(oof_path)
        if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
            oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})
        y = oof["y_true"].values
        yhat = oof["y_pred_ensemble"].values
    return {round(float(l), 1): float(np.mean((yhat > l) == (y > l))) for l in ou_lines}


def _pred_context(target: str, pred: float, ens_std: float) -> list[str]:
    """
    Return context lines to append to a regression model's printout:
      - Prediction Z-score (where in model's historical output space is this?)
      - Ensemble std vs historical median (is this an unstable input vector?)
      - Conditional scale adjustment note if heteroscedasticity is meaningful
    """
    stats = _oof_pred_stats(target)
    if not stats:
        return []

    lines = []
    pred_std = stats["pred_std"]
    if pred_std > 0:
        z = (pred - stats["pred_mean"]) / pred_std
        from scipy.stats import norm as _norm
        pct = float(_norm.cdf(z) * 100)
        pct_int = int(round(pct))
        sfx = "th" if 11 <= pct_int % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(pct_int % 10, "th")
        if abs(z) <= 1.0:
            z_label = "CENTER"
        elif abs(z) <= 2.0:
            z_label = "MODERATE EDGE"
        else:
            z_label = "EXTREME — extrapolating"
        lines.append(
            f"  Prediction Z-score: {z:+.2f}  ({pct_int}{sfx} pct of model's OOF output space)  [{z_label}]"
        )

    # Ensemble std context
    ens_med = stats["ens_std_median"]
    ens_p75 = stats["ens_std_p75"]
    ens_p95 = stats["ens_std_p95"]
    if ens_std > ens_p95:
        std_label = f"VERY HIGH — top 5% of historical disagreement (median={ens_med:.2f})"
    elif ens_std > ens_p75:
        std_label = f"HIGH — top 25% of historical disagreement (median={ens_med:.2f})"
    else:
        std_label = f"normal  (historical median={ens_med:.2f}, p95={ens_p95:.2f})"
    lines.append(f"  Ensemble std context: {std_label}")
    return lines


def _get_residual_params(bundle: dict, target: str) -> tuple[float, float]:
    """t-dist params: bundle calibration → OOF fit → error (no guessing)."""
    cal = bundle.get("calibration", {})
    rd = cal.get("residual_dist")
    if rd:
        return rd["df"], rd["scale"]
    # Known calibrated targets from config (retained for public API compatibility)
    if target == "spread":
        return SPREAD_RESID_DF, SPREAD_RESID_SCALE
    if target == "total":
        return TOTAL_RESID_DF, TOTAL_RESID_SCALE
    return _fit_t_from_oof(target)


def _get_std_thresholds(bundle: dict) -> tuple[float, float]:
    cal = bundle.get("calibration", {})
    if "std_thresholds" in cal:
        return tuple(cal["std_thresholds"])
    return WINNER_STD_THRESHOLDS


def _get_confidence_multipliers(bundle: dict) -> dict[str, float]:
    cal = bundle.get("calibration", {})
    if "confidence_multipliers" in cal:
        return cal["confidence_multipliers"]
    return WINNER_CONFIDENCE_MULTIPLIERS


def _get_bias_correction(bundle: dict, delta: float) -> float:
    cal = bundle.get("calibration", {})
    table = cal.get("bias_table")
    if table:
        for entry in table:
            if entry["delta_lo"] <= delta <= entry["delta_hi"]:
                return entry["correction"]
        return 0.0
    return 0.0


def _apply_isotonic(bundle: dict, prob: float) -> float:
    cal = bundle.get("calibration", {})
    calibrator = cal.get("isotonic_calibrator")
    if calibrator is not None:
        return float(calibrator.predict([prob])[0])
    return prob


def _get_bundle_metric(bundle: dict) -> tuple[str, float | None]:
    """Return (metric_name, value) from bundle metadata."""
    cal = bundle.get("calibration", {})
    if "final_metric" in cal:
        return cal.get("metric_name", "metric"), cal["final_metric"]
    if "final_metric" in bundle:
        return bundle.get("metric_name", "metric"), bundle["final_metric"]
    return "metric", None


def _get_combo_method(bundle: dict) -> str:
    return bundle.get("combination_method", "flat_weights")


# ── Ensemble prediction ───────────────────────────────────────────────────────

def _ensemble_preds(bundle: dict, X: pd.DataFrame) -> tuple[float, float, list[float]]:
    """Return (weighted_ensemble_mean, std_across_models, list_of_individual_preds)."""
    models_list = bundle.get("specialists", bundle.get("models", []))
    task = bundle["task"]

    preds = []
    weights = []
    for m in models_list:
        X_sub = X[m["features"]].copy()
        # sf_ features use ±1e6 as a clip-boundary sentinel; replace with NaN
        # so impute_median handles them the same way training did
        X_sub = X_sub.replace([1e6, -1e6], np.nan)
        missing_rate = float(X_sub.isna().sum().sum()) / max(len(m["features"]), 1)
        if m.get("impute_median"):
            X_sub = X_sub.fillna(pd.Series(m["impute_median"]))
        if m.get("needs_scaling"):
            X_sub = (X_sub - pd.Series(m["scale_mean"])) / pd.Series(m["scale_std"])
        if task == "classification":
            p = float(m["model"].predict_proba(X_sub)[:, 1][0])
            p = np.clip(p, 0.01, 0.99)
        else:
            p = float(m["model"].predict(X_sub)[0])
        preds.append(p)
        # Downweight scaled models with missing features (MLPs extrapolate badly)
        w = float(m["weight"])
        if missing_rate > 0.05 and m.get("needs_scaling"):
            w *= max(0.1, 1.0 - missing_rate * 3)
        weights.append(w)

    weights = np.array(weights)
    preds_arr = np.array(preds)

    # Reject outlier models: drop predictions > 3 MADs from the weighted median.
    # Protects against MLP/NN extrapolation when features are partially missing.
    if len(preds) >= 3:
        median = float(np.median(preds_arr))
        mad = float(np.median(np.abs(preds_arr - median)))
        if mad > 0:
            keep = np.abs(preds_arr - median) <= 3 * mad
            if keep.sum() >= 2:
                preds_arr = preds_arr[keep]
                weights = weights[keep]

    weights = weights / weights.sum()
    kept_preds = preds_arr.tolist()

    if bundle.get("combination_method") == "stacking" and bundle.get("meta_model") is not None:
        meta_input = np.array(kept_preds).reshape(1, -1)
        if task == "classification":
            mean = float(bundle["meta_model"].predict_proba(meta_input)[:, 1][0])
        else:
            mean = float(bundle["meta_model"].predict(meta_input)[0])
    else:
        mean = float(np.dot(weights, kept_preds))

    if task == "classification":
        mean = _apply_isotonic(bundle, mean)

    std = float(np.std(kept_preds)) if len(kept_preds) > 1 else 0.0
    return mean, std, kept_preds


# ── Build matchup feature row ─────────────────────────────────────────────────

def build_matchup_row(
    df: pd.DataFrame,
    home_abbr: str,
    away_abbr: str,
    needed_features: list[str],
) -> pd.DataFrame:
    home_as_home = df[df["home_team_abbr"] == home_abbr].sort_values("game_date")
    home_as_away = df[df["away_team_abbr"] == home_abbr].sort_values("game_date")
    away_as_home = df[df["home_team_abbr"] == away_abbr].sort_values("game_date")
    away_as_away = df[df["away_team_abbr"] == away_abbr].sort_values("game_date")

    if home_as_home.empty and home_as_away.empty:
        raise ValueError(f"Team '{home_abbr}' not found. Available: {sorted(df['home_team_abbr'].dropna().unique())}")
    if away_as_home.empty and away_as_away.empty:
        raise ValueError(f"Team '{away_abbr}' not found. Available: {sorted(df['away_team_abbr'].dropna().unique())}")

    h_home_date = home_as_home["game_date"].iloc[-1] if not home_as_home.empty else pd.Timestamp.min
    h_away_date = home_as_away["game_date"].iloc[-1] if not home_as_away.empty else pd.Timestamp.min
    if h_home_date >= h_away_date:
        home_row, home_prefix = home_as_home.iloc[-1], "home_"
    else:
        home_row, home_prefix = home_as_away.iloc[-1], "away_"

    a_home_date = away_as_home["game_date"].iloc[-1] if not away_as_home.empty else pd.Timestamp.min
    a_away_date = away_as_away["game_date"].iloc[-1] if not away_as_away.empty else pd.Timestamp.min
    if a_away_date >= a_home_date:
        away_row, away_prefix = away_as_away.iloc[-1], "away_"
    else:
        away_row, away_prefix = away_as_home.iloc[-1], "home_"

    row_data = {}
    for feat in needed_features:
        if feat.startswith("diff_"):
            suffix = feat[5:]
            if suffix.endswith("_venue"):
                base_stat = suffix[:-6]
                h_col = f"home_{base_stat}_athome"
                a_col = f"away_{base_stat}_onroad"
                h_val = home_row.get(h_col, np.nan) if home_prefix == "home_" else np.nan
                a_val = away_row.get(a_col, np.nan) if away_prefix == "away_" else np.nan
            else:
                h_col = f"{home_prefix}{suffix}"
                a_col = f"{away_prefix}{suffix}"
                h_val = home_row.get(h_col, np.nan)
                a_val = away_row.get(a_col, np.nan)
            row_data[feat] = h_val - a_val if pd.notna(h_val) and pd.notna(a_val) else np.nan
        elif feat.startswith("sum_"):
            suffix = feat[4:]
            if suffix.endswith("_venue"):
                base_stat = suffix[:-6]
                h_col = f"home_{base_stat}_athome"
                a_col = f"away_{base_stat}_onroad"
                h_val = home_row.get(h_col, np.nan) if home_prefix == "home_" else np.nan
                a_val = away_row.get(a_col, np.nan) if away_prefix == "away_" else np.nan
            else:
                h_col = f"{home_prefix}{suffix}"
                a_col = f"{away_prefix}{suffix}"
                h_val = home_row.get(h_col, np.nan)
                a_val = away_row.get(a_col, np.nan)
            row_data[feat] = h_val + a_val if pd.notna(h_val) and pd.notna(a_val) else np.nan
        else:
            val = home_row.get(feat, np.nan)
            if pd.isna(val):
                val = away_row.get(feat, np.nan)
            row_data[feat] = val

    return pd.DataFrame([row_data])


# ── Cover / over probability ──────────────────────────────────────────────────

def cover_prob(threshold: float, mu: float, bundle: dict | None = None, target: str = "spread") -> float:
    """P(actual margin > threshold) using t-dist + bias correction."""
    if bundle:
        df, scale = _get_residual_params(bundle, target)
    else:
        df, scale = SPREAD_RESID_DF, SPREAD_RESID_SCALE
    delta = threshold - mu
    raw = float(1 - t_dist.cdf(delta / scale, df=df))
    correction = _get_bias_correction(bundle, abs(delta)) if bundle else 0.0
    return max(0.0, min(1.0, raw + correction))


def over_prob(line: float, mu: float, bundle: dict | None = None, target: str = "total") -> float:
    """P(actual total > line) using t-dist."""
    if bundle:
        df, scale = _get_residual_params(bundle, target)
    else:
        df, scale = TOTAL_RESID_DF, TOTAL_RESID_SCALE
    return float(1 - t_dist.cdf((line - mu) / scale, df=df))


# ── Display helpers ───────────────────────────────────────────────────────────

def _conf_tier(std: float, bundle: dict | None = None) -> str:
    lo, hi = _get_std_thresholds(bundle) if bundle else WINNER_STD_THRESHOLDS
    if std <= lo:
        return "HIGH"
    elif std <= hi:
        return "MEDIUM"
    return "LOW"


def _ascii_spread_distribution(mu: float, home: str, away: str, df: float, scale: float, width: int = 40) -> str:
    """ASCII bar chart of a spread t-distribution."""
    buckets = [
        (f"{away} +20+",  -99,  -19.5),
        (f"{away} +15",  -19.5, -14.5),
        (f"{away} +10",  -14.5,  -9.5),
        (f"{away}  +5",   -9.5,  -4.5),
        (f"{away}  +1",   -4.5,  -0.5),
        ("  Even  ",      -0.5,   0.5),
        (f"{home}  +1",    0.5,   4.5),
        (f"{home}  +5",    4.5,   9.5),
        (f"{home} +10",    9.5,  14.5),
        (f"{home} +15",   14.5,  19.5),
        (f"{home} +20+",  19.5,   99),
    ]
    probs = []
    for _, lo, hi in buckets:
        p_lo = float(t_dist.cdf((lo - mu) / scale, df=df))
        p_hi = float(t_dist.cdf((hi - mu) / scale, df=df))
        probs.append(p_hi - p_lo)

    max_p = max(probs)
    lines = []
    for (label, _, _), p in zip(buckets, probs):
        bar_len = int(round(p / max_p * width))
        bar = "█" * bar_len
        lines.append(f"  {label}  |{bar:<{width}}  {p*100:4.1f}%")
    return "\n".join(lines)


def _ascii_total_distribution(mu: float, df: float, scale: float, width: int = 40, half: bool = False) -> str:
    """ASCII bar chart of a total t-distribution. Half-game uses tighter buckets."""
    if half:
        buckets = [
            ("< 85",     0,    84.5),
            ("85-89",   84.5,  89.5),
            ("90-94",   89.5,  94.5),
            ("95-99",   94.5,  99.5),
            ("100-104", 99.5, 104.5),
            ("105-109",104.5, 109.5),
            ("110-114",109.5, 114.5),
            ("115+",   114.5, 300),
        ]
    else:
        buckets = [
            ("< 180",   0,    179.5),
            ("180-189", 179.5, 189.5),
            ("190-199", 189.5, 199.5),
            ("200-209", 199.5, 209.5),
            ("210-219", 209.5, 219.5),
            ("220-229", 219.5, 229.5),
            ("230-239", 229.5, 239.5),
            ("240+",    239.5, 400),
        ]
    probs = []
    for _, lo, hi in buckets:
        p_lo = float(t_dist.cdf((lo - mu) / scale, df=df))
        p_hi = float(t_dist.cdf((hi - mu) / scale, df=df))
        probs.append(p_hi - p_lo)

    max_p = max(probs)
    lines = []
    for (label, _, _), p in zip(buckets, probs):
        bar_len = int(round(p / max_p * width))
        bar = "█" * bar_len
        lines.append(f"  {label:>8}  |{bar:<{width}}  {p*100:4.1f}%")
    return "\n".join(lines)


def _print_separator(width: int = 66):
    print("=" * width)


# ── Per-target display blocks ─────────────────────────────────────────────────

def _display_clf_block(
    target: str,
    home: str,
    away: str,
    bundle: dict,
    X: pd.DataFrame,
) -> dict:
    """Display a classification target block. Returns result dict."""
    meta = _TARGET_META[target]
    mean, std, indiv = _ensemble_preds(bundle, X)
    conf = _conf_tier(std, bundle)
    mult = _get_confidence_multipliers(bundle)[conf]
    n_models = len(bundle.get("specialists", bundle.get("models", [])))
    metric_name, metric_val = _get_bundle_metric(bundle)
    combo = _get_combo_method(bundle)

    # Implied spread from winner probability (spread-type peers only)
    spread_peer = meta.get("spread_peer")
    if spread_peer and spread_peer in ("spread", "h1_spread", "h2_spread"):
        # Use fitted params for the spread peer, not the clf bundle
        try:
            spread_pkl = OUTPUT_DIR / spread_peer / "ensemble.pkl"
            if spread_pkl.exists():
                with open(spread_pkl, "rb") as f:
                    spread_bundle_tmp = pickle.load(f)
                sp_df, sp_scale = _get_residual_params(spread_bundle_tmp, spread_peer)
            else:
                sp_df, sp_scale = SPREAD_RESID_DF, SPREAD_RESID_SCALE
        except Exception:
            sp_df, sp_scale = SPREAD_RESID_DF, SPREAD_RESID_SCALE
        implied_spread = float(-sp_scale * t_dist.ppf(1 - mean, df=sp_df))
    else:
        implied_spread = float("nan")

    print(f"\n  {meta['label']}  ({n_models} models, {combo})")
    print(f"  {'─'*62}")
    print(f"  P({home} wins): {mean*100:.1f}%   P({away} wins): {(1-mean)*100:.1f}%")
    print(f"  Ensemble std:   {std:.4f}   Confidence: {conf}  (Kelly mult {mult:.2f}x)")
    print(f"  Model range:    [{min(indiv)*100:.1f}%, {max(indiv)*100:.1f}%]  "
          f"(spread: {(max(indiv)-min(indiv))*100:.1f}pp)")
    if metric_val is not None:
        print(f"  OOF {metric_name}: {metric_val:.4f}")
    if not np.isnan(implied_spread):
        print(f"  Implied spread: {home} by {implied_spread:+.1f} pts")

    return {
        "prob": mean,
        "std": std,
        "conf": conf,
        "implied_spread": implied_spread,
        "indiv": indiv,
    }


def _display_reg_block(
    target: str,
    home: str,
    away: str,
    bundle: dict,
    X: pd.DataFrame,
) -> dict:
    """Display a regression target block. Returns result dict."""
    meta = _TARGET_META[target]
    task_type = meta["task"]  # "reg_spread" or "reg_total"
    is_spread = task_type == "reg_spread"
    is_half = "h1" in target or "h2" in target

    mean, std, indiv = _ensemble_preds(bundle, X)
    res_df, res_scale = _get_residual_params(bundle, target)

    n_models = len(bundle.get("specialists", bundle.get("models", [])))
    metric_name, metric_val = _get_bundle_metric(bundle)
    combo = _get_combo_method(bundle)

    q68 = t_dist.ppf(0.84, df=res_df) * res_scale
    q95 = t_dist.ppf(0.975, df=res_df) * res_scale

    print(f"\n  {meta['label']}  ({n_models} models, {combo})")
    print(f"  {'─'*62}")

    if is_spread:
        win_prob = float(1 - t_dist.cdf((0 - mean) / res_scale, df=res_df))
        print(f"  Predicted margin: {home} by {mean:+.1f} pts")
        print(f"  Ensemble std (model disagreement): {std:.2f} pts")
        print(f"  Model range: [{min(indiv):+.1f}, {max(indiv):+.1f}] pts")
        if metric_val is not None:
            print(f"  OOF {metric_name}: {metric_val:.4f}")
        print(f"  Residual dist: t(df={res_df:.1f}, scale={res_scale:.2f})")
        print()
        print(f"  68% range: [{mean - q68:+.1f}, {mean + q68:+.1f}] pts")
        print(f"  95% range: [{mean - q95:+.1f}, {mean + q95:+.1f}] pts")
        print(f"  Implied P({home} wins): {win_prob*100:.1f}%")
        for ctx_line in _pred_context(target, mean, std):
            print(ctx_line)
        print()
        print(f"  Margin distribution (μ={mean:+.1f}):")
        print(_ascii_spread_distribution(mean, home, away, res_df, res_scale))
        print()

        # Cover table
        step = 1 if is_half else 2
        base = -13.5 if is_half else -19.5
        end  = 14.5  if is_half else  20.5
        thresholds = list(np.arange(base, end + 0.1, step))
        print(f"  {'Threshold':>11}  {'P(cover)':>9}  {'P(no cover)':>12}  {'Zone':>8}")
        print(f"  {'─'*47}")
        for t_val in thresholds:
            delta = abs(t_val - mean)
            corr_p = cover_prob(t_val, mean, bundle, target)
            corr_no = 1 - corr_p
            if delta <= 2:
                zone = "ACCURATE"
            elif delta <= 22:
                zone = "TRADEABLE"
            else:
                zone = "CAUTION"
            team = home if t_val >= 0 else away
            label = f"{team} +{abs(t_val):.1f}"
            print(f"  {label:>11}  {corr_p*100:>8.1f}%  {corr_no*100:>11.1f}%  {zone:>8}")

        return {"mu": mean, "std": std, "win_prob": win_prob, "indiv": indiv, "res_df": res_df, "res_scale": res_scale}

    else:  # reg_total
        print(f"  Predicted total: {mean:.1f} pts")
        print(f"  Ensemble std (model disagreement): {std:.2f} pts")
        print(f"  Model range: [{min(indiv):.1f}, {max(indiv):.1f}] pts")
        if metric_val is not None:
            print(f"  OOF {metric_name}: {metric_val:.4f}")
        print(f"  Residual dist: t(df={res_df:.1f}, scale={res_scale:.2f})")
        print()
        print(f"  68% CI: [{mean - q68:.1f}, {mean + q68:.1f}] pts")
        print(f"  95% CI: [{mean - q95:.1f}, {mean + q95:.1f}] pts")
        for ctx_line in _pred_context(target, mean, std):
            print(ctx_line)
        print()
        print(f"  Total distribution (μ={mean:.1f}):")
        print(_ascii_total_distribution(mean, res_df, res_scale, half=is_half))
        print()

        # Over/under table
        center = round(mean / 5) * 5
        if is_half:
            lo_lim, hi_lim = max(75.5, center - 14.5), min(140.5, center + 15.5)
        else:
            lo_lim, hi_lim = max(180.5, center - 19.5), min(260.5, center + 20.5)
        lines = np.arange(lo_lim, hi_lim, 2.0)
        oof_acc = _oof_line_accuracy(target, lines)
        has_oof = bool(oof_acc)
        if has_oof:
            print(f"  {'Line':>8}  {'P(Over)':>8}  {'P(Under)':>9}  {'Fair Over':>10}  {'Fair Under':>11}  {'OOF Acc':>8}")
            print(f"  {'─'*64}")
        else:
            print(f"  {'Line':>8}  {'P(Over)':>8}  {'P(Under)':>9}  {'Fair Over':>10}  {'Fair Under':>11}")
            print(f"  {'─'*52}")
        for line in lines:
            p_over = over_prob(line, mean, bundle, target)
            p_under = 1 - p_over
            fair_over = f"{p_over*100:.1f}¢" if p_over > 0.01 else "  —"
            fair_under = f"{p_under*100:.1f}¢" if p_under > 0.01 else "  —"
            if has_oof:
                acc = oof_acc.get(round(float(line), 1), float("nan"))
                acc_str = f"{acc*100:.1f}%" if not np.isnan(acc) else "  —"
                print(f"  {line:>8.1f}  {p_over*100:>7.1f}%  {p_under*100:>8.1f}%  {fair_over:>10}  {fair_under:>11}  {acc_str:>8}")
            else:
                print(f"  {line:>8.1f}  {p_over*100:>7.1f}%  {p_under*100:>8.1f}%  {fair_over:>10}  {fair_under:>11}")

        return {"mu": mean, "std": std, "indiv": indiv, "res_df": res_df, "res_scale": res_scale}


# ── Synthetic game total (replaces broken game-total model) ──────────────────

def _display_synthetic_total(
    home: str,
    away: str,
    results: dict[str, dict],
) -> dict | None:
    """
    Synthesise game total from h1_total + h2_total predictions.

    μ_synthetic  = μ_H1 + μ_H2
    σ²_synthetic = σ²_H1 + σ²_H2 + 2·Cov(H1, H2)   [from OOF residuals]
    t-dist parameters fitted to (r_H1 + r_H2) OOF residuals via MLE.

    NOTE: the native game-total model (3 specialists, MAE=14.5) is replaced
    by this synthetic model (OOF MAE≈13.9) which propagates uncertainty correctly
    through the H1+H2 decomposition and passes KS at p=0.63 vs p=0.01 for the
    native model.
    """
    if "h1_total" not in results or "h2_total" not in results:
        return None

    mu_h1 = results["h1_total"]["mu"]
    mu_h2 = results["h2_total"]["mu"]
    mu = mu_h1 + mu_h2

    res_df, res_scale, cov, rho_std = _synthetic_total_params()

    # Per-model std (disagreement) — combine using empirical correlation
    std_h1 = results["h1_total"]["std"]
    std_h2 = results["h2_total"]["std"]
    std_combined = float(np.sqrt(std_h1**2 + std_h2**2 + 2 * rho_std * std_h1 * std_h2))
    q68 = t_dist.ppf(0.84, df=res_df) * res_scale
    q95 = t_dist.ppf(0.975, df=res_df) * res_scale

    print(f"\n  GAME TOTAL  [SYNTHETIC: μ_H1 + μ_H2]")
    print(f"  {'─'*62}")
    print(f"  ⚠  Native game-total model replaced by synthetic (OOF MAE: synthetic=13.88 vs direct=14.50).")
    print(f"     Using h1_total + h2_total with full variance propagation.")
    print(f"  μ = {mu_h1:.1f} + {mu_h2:.1f} = {mu:.1f} pts")
    # σ² values come from OOF empirical variance (scale² × df/(df-2) for t-dist)
    df_h1 = results["h1_total"]["res_df"]
    sc_h1 = results["h1_total"]["res_scale"]
    df_h2 = results["h2_total"]["res_df"]
    sc_h2 = results["h2_total"]["res_scale"]
    var_h1 = sc_h1**2 * df_h1 / (df_h1 - 2) if df_h1 > 2 else sc_h1**2
    var_h2 = sc_h2**2 * df_h2 / (df_h2 - 2) if df_h2 > 2 else sc_h2**2
    print(f"  σ²_synthetic = σ²_H1 + σ²_H2 + 2·Cov(H1,H2)")
    print(f"               = {var_h1:.1f} + {var_h2:.1f} + 2·{cov:.1f}")
    print(f"  Residual dist: t(df={res_df:.1f}, scale={res_scale:.2f})  "
          f"[OOF KS p=0.63 vs native p=0.01]")
    print(f"  Ensemble std (combined, ρ={rho_std:.2f}): {std_combined:.2f} pts")
    print()
    print(f"  68% CI: [{mu - q68:.1f}, {mu + q68:.1f}] pts")
    print(f"  95% CI: [{mu - q95:.1f}, {mu + q95:.1f}] pts")
    # Context from each half-model's prediction Z-score
    for half in ("h1_total", "h2_total"):
        for ctx_line in _pred_context(half, results[half]["mu"], results[half]["std"]):
            print(f"  [{half}] {ctx_line.strip()}")
    print()
    print(f"  Total distribution (μ={mu:.1f}):")
    print(_ascii_total_distribution(mu, res_df, res_scale, half=False))
    print()

    center = round(mu / 5) * 5
    lo_lim = max(180.5, center - 19.5)
    hi_lim = min(260.5, center + 20.5)
    lines = np.arange(lo_lim, hi_lim, 2.0)
    oof_acc = _oof_line_accuracy("total", lines)
    has_oof = bool(oof_acc)
    if has_oof:
        print(f"  {'Line':>8}  {'P(Over)':>8}  {'P(Under)':>9}  {'Fair Over':>10}  {'Fair Under':>11}  {'OOF Acc':>8}")
        print(f"  {'─'*64}")
    else:
        print(f"  {'Line':>8}  {'P(Over)':>8}  {'P(Under)':>9}  {'Fair Over':>10}  {'Fair Under':>11}")
        print(f"  {'─'*52}")
    for line in lines:
        p_over = float(1 - t_dist.cdf((line - mu) / res_scale, df=res_df))
        p_under = 1 - p_over
        fair_over  = f"{p_over*100:.1f}¢"  if p_over  > 0.01 else "  —"
        fair_under = f"{p_under*100:.1f}¢" if p_under > 0.01 else "  —"
        if has_oof:
            acc = oof_acc.get(round(float(line), 1), float("nan"))
            acc_str = f"{acc*100:.1f}%" if not np.isnan(acc) else "  —"
            print(f"  {line:>8.1f}  {p_over*100:>7.1f}%  {p_under*100:>8.1f}%  {fair_over:>10}  {fair_under:>11}  {acc_str:>8}")
        else:
            print(f"  {line:>8.1f}  {p_over*100:>7.1f}%  {p_under*100:>8.1f}%  {fair_over:>10}  {fair_under:>11}")

    return {
        "mu": mu,
        "std": std_combined,
        "indiv": [],
        "res_df": res_df,
        "res_scale": res_scale,
        "synthetic": True,
    }


# ── Cross-model consistency checks ───────────────────────────────────────────

def _cross_model_checks(home: str, away: str, results: dict[str, dict]) -> None:
    W = 66
    any_printed = False

    def _section(title: str):
        nonlocal any_printed
        if not any_printed:
            print(f"\n  {'═'*62}")
            print(f"  CROSS-MODEL CONSISTENCY")
            print(f"  {'═'*62}")
            any_printed = True
        print(f"\n  {title}")
        print(f"  {'─'*62}")

    # ── winner ↔ spread ────────────────────────────────────────────────────
    if "winner" in results and "spread" in results:
        _section("GAME WINNER vs SPREAD")
        w = results["winner"]
        s = results["spread"]
        gap_pp = abs(w["prob"] - s["win_prob"]) * 100
        gap_pts = abs(w["implied_spread"] - s["mu"])
        print(f"  Winner model:  P({home}) = {w['prob']*100:.1f}%  →  implied spread {w['implied_spread']:+.1f} pts")
        print(f"  Spread model:  μ = {s['mu']:+.1f} pts  →  implied P({home}) = {s['win_prob']*100:.1f}%")
        print(f"  Win prob gap:  {gap_pp:.1f}pp    Spread gap: {gap_pts:.1f} pts")
        if gap_pp < 3:
            verdict = "CONSISTENT — high confidence in direction"
        elif gap_pp < 6:
            verdict = "MODERATE disagreement — reduce position size"
        else:
            verdict = "FLAG — models disagree, do not trade"
        print(f"  Verdict: {verdict}")

    # ── home_wins_h1 ↔ h1_spread ─────────────────────────────────────────
    if "home_wins_h1" in results and "h1_spread" in results:
        _section("H1 WINNER vs H1 SPREAD")
        w = results["home_wins_h1"]
        s = results["h1_spread"]
        gap_pp = abs(w["prob"] - s["win_prob"]) * 100
        gap_pts = abs(w.get("implied_spread", float("nan")) - s["mu"])
        print(f"  H1 winner:  P({home}) = {w['prob']*100:.1f}%  →  implied h1_spread {w.get('implied_spread', float('nan')):+.1f} pts")
        print(f"  H1 spread:  μ = {s['mu']:+.1f} pts  →  implied P({home}) H1 = {s['win_prob']*100:.1f}%")
        print(f"  Win prob gap: {gap_pp:.1f}pp    Spread gap: {gap_pts:.1f} pts")
        if gap_pp < 3:
            verdict = "CONSISTENT"
        elif gap_pp < 6:
            verdict = "MODERATE disagreement"
        else:
            verdict = "FLAG"
        print(f"  Verdict: {verdict}")

    # ── home_wins_h2 ↔ h2_spread ─────────────────────────────────────────
    if "home_wins_h2" in results and "h2_spread" in results:
        _section("H2 WINNER vs H2 SPREAD")
        w = results["home_wins_h2"]
        s = results["h2_spread"]
        gap_pp = abs(w["prob"] - s["win_prob"]) * 100
        gap_pts = abs(w.get("implied_spread", float("nan")) - s["mu"])
        print(f"  H2 winner:  P({home}) = {w['prob']*100:.1f}%  →  implied h2_spread {w.get('implied_spread', float('nan')):+.1f} pts")
        print(f"  H2 spread:  μ = {s['mu']:+.1f} pts  →  implied P({home}) H2 = {s['win_prob']*100:.1f}%")
        print(f"  Win prob gap: {gap_pp:.1f}pp    Spread gap: {gap_pts:.1f} pts")
        if gap_pp < 3:
            verdict = "CONSISTENT"
        elif gap_pp < 6:
            verdict = "MODERATE disagreement"
        else:
            verdict = "FLAG"
        print(f"  Verdict: {verdict}")

    # ── spread = h1_spread + h2_spread ────────────────────────────────────
    if "spread" in results and "h1_spread" in results and "h2_spread" in results:
        _section("SPREAD ADDITIVITY ")
        s = results["spread"]["mu"]
        h1 = results["h1_spread"]["mu"]
        h2 = results["h2_spread"]["mu"]
        halves_sum = h1 + h2
        gap = abs(s - halves_sum)
        print(f"  Game spread:   {s:+.1f} pts")
        print(f"  H1 + H2:       {h1:+.1f} + {h2:+.1f} = {halves_sum:+.1f} pts")
        print(f"  Additivity gap: {gap:.1f} pts")
        if gap < 2:
            verdict = "CONSISTENT — halves sum to game"
        elif gap < 4:
            verdict = "MINOR discrepancy — within model noise"
        else:
            verdict = "FLAG — halves do not sum to game spread"
        print(f"  Verdict: {verdict}")

    # ── spread + total → implied team scores ──────────────────────────────
    if "spread" in results and "total" in results:
        _section("TOTAL × SPREAD DECOMPOSITION")
        t_mu = results["total"]["mu"]
        s_mu = results["spread"]["mu"]
        implied_home = (t_mu + s_mu) / 2
        implied_away = (t_mu - s_mu) / 2
        print(f"  Total μ={t_mu:.1f}  |  Spread μ={s_mu:+.1f}")
        print(f"  Implied {home} score: {implied_home:.1f}   Implied {away} score: {implied_away:.1f}")

        t_df = results["total"].get("res_df", TOTAL_RESID_DF)
        t_sc = results["total"].get("res_scale", TOTAL_RESID_SCALE)
        s_df = results["spread"].get("res_df", SPREAD_RESID_DF)
        s_sc = results["spread"].get("res_scale", SPREAD_RESID_SCALE)
        var_total = t_sc**2 * t_df / (t_df - 2) if t_df > 2 else t_sc**2
        var_spread = s_sc**2 * s_df / (s_df - 2) if s_df > 2 else s_sc**2
        se_team = np.sqrt((var_total + var_spread) / 4)
        print(f"  Individual score SE: ±{se_team:.1f} pts  (joint from total+spread uncertainty)")

        expected_higher = home if s_mu > 0 else away
        actual_higher = home if implied_home > implied_away else away
        if expected_higher == actual_higher:
            print(f"  Direction check: consistent — spread & decomposition agree ({expected_higher} leads)")
        else:
            print(f"  Direction check: spread says {expected_higher} but decomposition implies {actual_higher}")

    # ── h1_spread + h1_total → H1 implied scores ─────────────────────────
    if "h1_spread" in results and "h1_total" in results:
        _section("H1 TOTAL × H1 SPREAD DECOMPOSITION")
        t_mu = results["h1_total"]["mu"]
        s_mu = results["h1_spread"]["mu"]
        implied_home = (t_mu + s_mu) / 2
        implied_away = (t_mu - s_mu) / 2
        print(f"  H1 total μ={t_mu:.1f}  |  H1 spread μ={s_mu:+.1f}")
        print(f"  Implied {home} H1 score: {implied_home:.1f}   Implied {away} H1 score: {implied_away:.1f}")

        t_df = results["h1_total"].get("res_df", TOTAL_RESID_DF)
        t_sc = results["h1_total"].get("res_scale", TOTAL_RESID_SCALE)
        s_df = results["h1_spread"].get("res_df", SPREAD_RESID_DF)
        s_sc = results["h1_spread"].get("res_scale", SPREAD_RESID_SCALE)
        var_total = t_sc**2 * t_df / (t_df - 2) if t_df > 2 else t_sc**2
        var_spread = s_sc**2 * s_df / (s_df - 2) if s_df > 2 else s_sc**2
        se_team = np.sqrt((var_total + var_spread) / 4)
        print(f"  Individual H1 score SE: ±{se_team:.1f} pts")

    # ── h2_spread + h2_total → H2 implied scores ─────────────────────────
    if "h2_spread" in results and "h2_total" in results:
        _section("H2 TOTAL × H2 SPREAD DECOMPOSITION")
        t_mu = results["h2_total"]["mu"]
        s_mu = results["h2_spread"]["mu"]
        implied_home = (t_mu + s_mu) / 2
        implied_away = (t_mu - s_mu) / 2
        print(f"  H2 total μ={t_mu:.1f}  |  H2 spread μ={s_mu:+.1f}")
        print(f"  Implied {home} H2 score: {implied_home:.1f}   Implied {away} H2 score: {implied_away:.1f}")

        t_df = results["h2_total"].get("res_df", TOTAL_RESID_DF)
        t_sc = results["h2_total"].get("res_scale", TOTAL_RESID_SCALE)
        s_df = results["h2_spread"].get("res_df", SPREAD_RESID_DF)
        s_sc = results["h2_spread"].get("res_scale", SPREAD_RESID_SCALE)
        var_total = t_sc**2 * t_df / (t_df - 2) if t_df > 2 else t_sc**2
        var_spread = s_sc**2 * s_df / (s_df - 2) if s_df > 2 else s_sc**2
        se_team = np.sqrt((var_total + var_spread) / 4)
        print(f"  Individual H2 score SE: ±{se_team:.1f} pts")


# ── Per-matchup prediction and display ───────────────────────────────────────

def predict_and_print(
    home: str,
    away: str,
    df: pd.DataFrame,
    targets: list[str],
) -> dict[str, dict]:
    W = 66
    _print_separator(W)
    print(f"  {home} (home) vs {away} (away)")
    print(f"  Data through: {df['game_date'].max().strftime('%Y-%m-%d')}")
    _print_separator(W)

    results: dict[str, dict] = {}

    for target in targets:
        if target == "total":
            # Synthetic model: requires h1_total + h2_total already in results
            r = _display_synthetic_total(home, away, results)
            if r is not None:
                results["total"] = r
            else:
                print(f"\n  [TOTAL]  Synthetic model requires h1_total + h2_total — "
                      f"run with --target all or ensure both half models are included.")
            continue

        try:
            bundle = _load_bundle(target)
        except FileNotFoundError:
            print(f"\n  [{target.upper()}]  No trained model found — skipping.")
            continue

        task = _TARGET_META[target]["task"]
        X = build_matchup_row(df, home, away, _get_features(bundle))

        if task == "clf":
            results[target] = _display_clf_block(target, home, away, bundle, X)
        else:
            results[target] = _display_reg_block(target, home, away, bundle, X)

    _cross_model_checks(home, away, results)

    _print_separator(W)
    print()
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def predict_matchups(
    matchups: list[tuple[str, str]],
    target: str = "all",
    verbose: bool = True,
) -> pd.DataFrame:
    if target == "all":
        targets = _TARGET_ORDER
    elif target == "total":
        # synthetic total requires both half models
        targets = ["h1_total", "h2_total", "total"]
    else:
        targets = [target]
    df = pd.read_parquet(GAME_PARQUET)

    rows = []
    for home, away in matchups:
        h, a = home.upper(), away.upper()
        results = predict_and_print(h, a, df, targets)

        row: dict = {"home_team": h, "away_team": a}
        if "spread" in results:
            s_mean = results["spread"]["mu"]
            s_df = results["spread"].get("res_df", SPREAD_RESID_DF)
            s_sc = results["spread"].get("res_scale", SPREAD_RESID_SCALE)
            row["predicted_margin"] = round(float(s_mean), 2)
            spread_bundle = _load_bundle("spread")
            for s in np.arange(-10.5, 11.5, 1.0):
                row[f"cover_{s:+.1f}"] = round(cover_prob(s, s_mean, spread_bundle, "spread"), 3)
        if "total" in results:
            t_mean = results["total"]["mu"]
            t_res_df = results["total"].get("res_df")
            t_res_scale = results["total"].get("res_scale")
            row["predicted_total"] = round(float(t_mean), 2)
            for line in np.arange(190.5, 240.5, 5.0):
                p = float(1 - t_dist.cdf((line - t_mean) / t_res_scale, df=t_res_df))
                row[f"over_{line:.1f}"] = round(p, 3)
        for half_target in ("h1_spread", "h2_spread", "h1_total", "h2_total"):
            if half_target in results:
                key = "predicted_" + half_target
                val = results[half_target].get("mu")
                if val is not None:
                    row[key] = round(float(val), 2)
        rows.append(row)

    return pd.DataFrame(rows)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Predict NBA game outcomes",
        usage="python -m strategy.predict HOME AWAY [HOME AWAY ...]",
    )
    parser.add_argument("teams", nargs="+",
                        help="Team pairs: HOME AWAY [HOME AWAY ...]")
    parser.add_argument("--target", default="all",
                        choices=["all"] + _TARGET_ORDER,
                        help="Which model(s) to run (default: all)")
    args = parser.parse_args()

    if len(args.teams) % 2 != 0:
        parser.error("Teams must be in pairs (home away home away ...)")

    matchups = [(args.teams[i], args.teams[i+1]) for i in range(0, len(args.teams), 2)]
    predict_matchups(matchups, target=args.target)
