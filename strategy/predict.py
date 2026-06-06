"""
predict.py
----------
Predict the next game(s) using the ensemble pkls and the latest team stats
from game_features.parquet.

Runs winner, spread, and total models by default. Cross-checks across all
three models: winner ↔ spread ↔ total. Shows distributions, ensemble
confidence, bias-corrected fair prices, and implied team scores.

Usage:
    python -m strategy.predict SAS NYK
    python -m strategy.predict SAS NYK --target winner
    python -m strategy.predict SAS NYK --target spread
    python -m strategy.predict SAS NYK --target total
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


# ── Fallback bias correction (used only when bundle lacks calibration) ────────
_BIAS_TABLE_FALLBACK = [
    (0,  2,  0.000),
    (3,  22, -0.013),
    (23, 99, +0.003),
]


def _get_residual_params(bundle: dict) -> tuple[float, float]:
    """Get t-dist params from bundle calibration, fall back to config constants."""
    cal = bundle.get("calibration", {})
    rd = cal.get("residual_dist")
    if rd:
        return rd["df"], rd["scale"]
    target = bundle.get("target", "spread")
    if target == "total":
        return TOTAL_RESID_DF, TOTAL_RESID_SCALE
    return SPREAD_RESID_DF, SPREAD_RESID_SCALE


def _get_std_thresholds(bundle: dict) -> tuple[float, float]:
    """Get std thresholds from bundle calibration, fall back to config."""
    cal = bundle.get("calibration", {})
    if "std_thresholds" in cal:
        return tuple(cal["std_thresholds"])
    return WINNER_STD_THRESHOLDS


def _get_confidence_multipliers(bundle: dict) -> dict[str, float]:
    """Get confidence multipliers from bundle, fall back to config."""
    cal = bundle.get("calibration", {})
    if "confidence_multipliers" in cal:
        return cal["confidence_multipliers"]
    return WINNER_CONFIDENCE_MULTIPLIERS


def _get_bias_correction(bundle: dict, delta: float) -> float:
    """Get bias correction from bundle calibration, fall back to hardcoded."""
    cal = bundle.get("calibration", {})
    table = cal.get("bias_table")
    if table:
        for entry in table:
            if entry["delta_lo"] <= delta <= entry["delta_hi"]:
                return entry["correction"]
        return 0.0
    for lo, hi, corr in _BIAS_TABLE_FALLBACK:
        if lo <= delta <= hi:
            return corr
    return 0.0


def _apply_isotonic(bundle: dict, prob: float) -> float:
    """Apply isotonic calibration if available in bundle."""
    cal = bundle.get("calibration", {})
    calibrator = cal.get("isotonic_calibrator")
    if calibrator is not None:
        return float(calibrator.predict([prob])[0])
    return prob


# ── Ensemble helpers ──────────────────────────────────────────────────────────

def _ensemble_preds(bundle: dict, X: pd.DataFrame) -> tuple[float, float, list[float]]:
    """Return (weighted_ensemble_mean, std_across_models, list_of_individual_preds)."""
    # Support both old format ("models") and new specialist format ("specialists")
    models_list = bundle.get("specialists", bundle.get("models", []))
    task = bundle["task"]

    preds = []
    weights = []
    for m in models_list:
        X_sub = X[m["features"]].copy()
        if m.get("impute_median"):
            X_sub = X_sub.fillna(pd.Series(m["impute_median"]))
        if m.get("needs_scaling"):
            X_sub = (X_sub - pd.Series(m["scale_mean"])) / pd.Series(m["scale_std"])
        if task == "classification":
            p = float(m["model"].predict_proba(X_sub)[:, 1][0])
        else:
            p = float(m["model"].predict(X_sub)[0])
        preds.append(p)
        weights.append(float(m["weight"]))

    weights = np.array(weights)
    weights = weights / weights.sum()

    # If stacking meta-model is present, use it instead of flat weights
    if bundle.get("combination_method") == "stacking" and bundle.get("meta_model") is not None:
        meta_input = np.array(preds).reshape(1, -1)
        if task == "classification":
            mean = float(bundle["meta_model"].predict_proba(meta_input)[:, 1][0])
        else:
            mean = float(bundle["meta_model"].predict(meta_input)[0])
    else:
        mean = float(np.dot(weights, preds))

    # Apply isotonic calibration if available (classification only)
    if task == "classification":
        mean = _apply_isotonic(bundle, mean)

    std = float(np.std(preds)) if len(preds) > 1 else 0.0
    return mean, std, preds


def _load_bundle(target: str) -> dict:
    # Try new specialist format first, fall back to legacy
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
            # Game-level feature (log5, sf_*, crowd_*, sellout_flag, etc.): pull directly
            val = home_row.get(feat, np.nan)
            if pd.isna(val):
                val = away_row.get(feat, np.nan)
            row_data[feat] = val

    return pd.DataFrame([row_data])


# ── Cover probability (t-dist + bias correction) ──────────────────────────────

def cover_prob(threshold: float, mu: float, bundle: dict | None = None) -> float:
    """P(actual margin > threshold) using t-dist + bias correction."""
    if bundle:
        df, scale = _get_residual_params(bundle)
    else:
        df, scale = SPREAD_RESID_DF, SPREAD_RESID_SCALE
    delta = threshold - mu
    raw = float(1 - t_dist.cdf(delta / scale, df=df))
    correction = _get_bias_correction(bundle, abs(delta)) if bundle else 0.0
    return max(0.0, min(1.0, raw + correction))


def over_prob(line: float, mu: float, bundle: dict | None = None) -> float:
    """P(actual total > line) using t-dist."""
    if bundle:
        df, scale = _get_residual_params(bundle)
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


def _ascii_distribution(mu: float, home: str, away: str, width: int = 40) -> str:
    """ASCII bar chart of the spread t-distribution."""
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
        p_lo = float(t_dist.cdf((lo - mu) / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))
        p_hi = float(t_dist.cdf((hi - mu) / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))
        probs.append(p_hi - p_lo)

    max_p = max(probs)
    lines = []
    for (label, _, _), p in zip(buckets, probs):
        bar_len = int(round(p / max_p * width))
        bar = "█" * bar_len
        lines.append(f"  {label}  |{bar:<{width}}  {p*100:4.1f}%")
    return "\n".join(lines)


def _ascii_total_distribution(mu: float, width: int = 40) -> str:
    """ASCII bar chart of the total t-distribution."""
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
        p_lo = float(t_dist.cdf((lo - mu) / TOTAL_RESID_SCALE, df=TOTAL_RESID_DF))
        p_hi = float(t_dist.cdf((hi - mu) / TOTAL_RESID_SCALE, df=TOTAL_RESID_DF))
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


# ── Per-matchup prediction and display ───────────────────────────────────────

def predict_and_print(
    home: str,
    away: str,
    df: pd.DataFrame,
    targets: list[str],
) -> None:
    W = 66
    _print_separator(W)
    print(f"  {home} (home) vs {away} (away)")
    print(f"  Data through: {df['game_date'].max().strftime('%Y-%m-%d')}")
    _print_separator(W)

    winner_result = None
    spread_result = None
    total_result = None

    # ── Winner model ──────────────────────────────────────────────────────────
    if "winner" in targets:
        bundle = _load_bundle("winner")
        X = build_matchup_row(df, home, away, _get_features(bundle))
        mean, std, indiv = _ensemble_preds(bundle, X)
        conf = _conf_tier(std)
        mult = WINNER_CONFIDENCE_MULTIPLIERS[conf]

        # Spread cross-check: invert t-CDF to find mu where P(spread>0|mu)=win_prob
        # 1 - t.cdf((0-mu)/scale, df) = win_prob  →  mu = -scale * t.ppf(1-win_prob, df)
        implied_spread = -SPREAD_RESID_SCALE * t_dist.ppf(1 - mean, df=SPREAD_RESID_DF)

        winner_result = {"prob": mean, "std": std, "conf": conf, "implied_spread": implied_spread, "indiv": indiv}

        print(f"\n  WINNER MODEL  ({len(bundle.get('specialists', bundle.get('models', [])))} models)")
        print(f"  {'─'*62}")
        print(f"  P({home} wins): {mean*100:.1f}%   P({away} wins): {(1-mean)*100:.1f}%")
        print(f"  Ensemble std:  {std:.4f}   Confidence: {conf}  (Kelly mult {mult:.2f}x)")
        print(f"  Model range:   [{min(indiv)*100:.1f}%, {max(indiv)*100:.1f}%]  "
              f"(spread: {(max(indiv)-min(indiv))*100:.1f}pp)")
        print(f"  Implied spread: {home} by {implied_spread:+.1f} pts  "
              f"(from t.ppf⁻¹, df={SPREAD_RESID_DF}, scale={SPREAD_RESID_SCALE})")

    # ── Spread model ──────────────────────────────────────────────────────────
    if "spread" in targets:
        bundle = _load_bundle("spread")
        X = build_matchup_row(df, home, away, _get_features(bundle))
        mean, std, indiv = _ensemble_preds(bundle, X)

        # Winner cross-check: P(spread > 0)
        win_from_spread = float(1 - t_dist.cdf((0 - mean) / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))

        spread_result = {"mu": mean, "std": std, "win_prob": win_from_spread, "indiv": indiv}

        print(f"\n  SPREAD MODEL  ({len(bundle.get('specialists', bundle.get('models', [])))} models)")
        print(f"  {'─'*62}")
        print(f"  Predicted margin: {home} by {mean:+.1f} pts")
        print(f"  Ensemble std (model disagreement): {std:.2f} pts")
        print(f"  Model range: [{min(indiv):+.1f}, {max(indiv):+.1f}] pts")
        print(f"  Residual distribution: t(df={SPREAD_RESID_DF:.1f}, scale={SPREAD_RESID_SCALE})")
        print()
        q68 = t_dist.ppf(0.84, df=SPREAD_RESID_DF) * SPREAD_RESID_SCALE
        q95 = t_dist.ppf(0.975, df=SPREAD_RESID_DF) * SPREAD_RESID_SCALE
        print(f"  68% range: [{mean - q68:+.1f}, {mean + q68:+.1f}] pts  (t-dist, not ±1σ)")
        print(f"  95% range: [{mean - q95:+.1f}, {mean + q95:+.1f}] pts  (wider than normal due to fat tails)")
        print(f"  Implied P({home} wins): {win_from_spread*100:.1f}%")
        print()

        # ASCII distribution
        print(f"  Margin distribution (μ={mean:+.1f}, t-dist):")
        print(_ascii_distribution(mean, home, away))
        print()

        # Cover table — tradeable zone (delta 3–22) highlighted
        thresholds = list(range(-20, 22, 2))  # -20, -18, ..., +20 (step 2 to keep it compact)
        print(f"  {'Threshold':>10}  {'Raw P(YES)':>10}  {'Corrected YES':>13}  {'Corrected NO':>12}  {'Zone':>8}")
        print(f"  {'─'*58}")
        for t_val in thresholds:
            delta = abs(t_val - mean)
            raw_p = cover_prob(t_val, mean) - _bias_correction(delta)  # raw before correction
            corr_p = cover_prob(t_val, mean)
            corr_no = 1 - corr_p

            # Zone label
            if delta <= 2:
                zone = "ACCURATE"
            elif delta <= 22:
                zone = "TRADEABLE"
            else:
                zone = "CAUTION"

            team = home if t_val >= 0 else away
            sign = abs(t_val)
            label = f"{team} +{sign:.0f}"
            print(f"  {label:>10}  {raw_p*100:>9.1f}%  {corr_p*100:>12.1f}%  {corr_no*100:>11.1f}%  {zone:>8}")

    # ── Total model ──────────────────────────────────────────────────────────
    if "total" in targets:
        bundle = _load_bundle("total")
        X = build_matchup_row(df, home, away, _get_features(bundle))
        mean, std, indiv = _ensemble_preds(bundle, X)

        total_result = {"mu": mean, "std": std, "indiv": indiv}

        q68 = t_dist.ppf(0.84, df=TOTAL_RESID_DF) * TOTAL_RESID_SCALE
        q95 = t_dist.ppf(0.975, df=TOTAL_RESID_DF) * TOTAL_RESID_SCALE

        print(f"\n  TOTAL MODEL  ({len(bundle.get('specialists', bundle.get('models', [])))} models)")
        print(f"  {'─'*62}")
        print(f"  Predicted total: {mean:.1f} pts")
        print(f"  Ensemble std (model disagreement): {std:.2f} pts")
        print(f"  Model range: [{min(indiv):.1f}, {max(indiv):.1f}] pts")
        print(f"  Residual distribution: t(df={TOTAL_RESID_DF:.1f}, scale={TOTAL_RESID_SCALE})")
        print()
        print(f"  68% CI: [{mean - q68:.1f}, {mean + q68:.1f}] pts")
        print(f"  95% CI: [{mean - q95:.1f}, {mean + q95:.1f}] pts")
        print()

        # ASCII distribution
        print(f"  Total distribution (μ={mean:.1f}, t-dist):")
        print(_ascii_total_distribution(mean))
        print()

        # Over/under table for common lines
        lines = np.arange(
            max(180.5, round(mean / 5) * 5 - 19.5),
            min(260.5, round(mean / 5) * 5 + 20.5),
            2.0,
        )
        print(f"  {'Line':>8}  {'P(Over)':>8}  {'P(Under)':>9}  {'Fair Over':>10}  {'Fair Under':>11}")
        print(f"  {'─'*52}")
        for line in lines:
            p_over = over_prob(line, mean)
            p_under = 1 - p_over
            # Fair price = 1/implied_odds (no vig)
            fair_over = f"{p_over*100:.1f}¢" if p_over > 0.01 else "  —"
            fair_under = f"{p_under*100:.1f}¢" if p_under > 0.01 else "  —"
            print(f"  {line:>8.1f}  {p_over*100:>7.1f}%  {p_under*100:>8.1f}%  {fair_over:>10}  {fair_under:>11}")

    # ── Cross-model agreement ─────────────────────────────────────────────────
    if winner_result and spread_result:
        print(f"\n  CROSS-MODEL CHECK")
        print(f"  {'─'*62}")
        w_prob  = winner_result["prob"]
        w_impl  = winner_result["implied_spread"]
        s_prob  = spread_result["win_prob"]
        s_mu    = spread_result["mu"]
        gap_pp  = abs(w_prob - s_prob) * 100
        gap_pts = abs(w_impl - s_mu)

        print(f"  Winner model:  P({home}) = {w_prob*100:.1f}%  →  implied spread {w_impl:+.1f} pts")
        print(f"  Spread model:  μ = {s_mu:+.1f} pts  →  implied P({home}) = {s_prob*100:.1f}%")
        print(f"  Win prob gap:  {gap_pp:.1f}pp    Spread gap: {gap_pts:.1f} pts")

        if gap_pp < 3:
            verdict = "CONSISTENT — high confidence in direction"
        elif gap_pp < 6:
            verdict = "MODERATE disagreement — reduce position size"
        else:
            verdict = "FLAG — models disagree, do not trade"
        print(f"  Verdict: {verdict}")

    # ── Total × Spread cross-check ───────────────────────────────────────────
    if total_result and spread_result:
        print(f"\n  TOTAL × SPREAD DECOMPOSITION")
        print(f"  {'─'*62}")
        t_mu = total_result["mu"]
        s_mu = spread_result["mu"]
        implied_home = (t_mu + s_mu) / 2
        implied_away = (t_mu - s_mu) / 2
        print(f"  Total μ={t_mu:.1f}  |  Spread μ={s_mu:+.1f}")
        print(f"  Implied {home} score: {implied_home:.1f}   Implied {away} score: {implied_away:.1f}")

        # Joint CI: propagate uncertainty from both models
        # Var(home) = (Var(total) + Var(spread)) / 4  (independent since corr≈0)
        var_total = TOTAL_RESID_SCALE**2 * TOTAL_RESID_DF / (TOTAL_RESID_DF - 2)
        var_spread = SPREAD_RESID_SCALE**2 * SPREAD_RESID_DF / (SPREAD_RESID_DF - 2)
        se_team = np.sqrt((var_total + var_spread) / 4)
        print(f"  Individual score SE: ±{se_team:.1f} pts  (joint from total+spread uncertainty)")

        # Sanity: does the total model's over-50% line align with spread direction?
        if s_mu > 0:
            expected_higher = home
        else:
            expected_higher = away
        if implied_home > implied_away:
            actual_higher = home
        else:
            actual_higher = away

        if expected_higher == actual_higher:
            print(f"  Direction check: ✓ Spread & decomposition agree ({expected_higher} leads)")
        else:
            print(f"  Direction check: ✗ Spread says {expected_higher} but decomposition implies {actual_higher}")

    # ── Total × Winner cross-check ───────────────────────────────────────────
    if total_result and winner_result:
        print(f"\n  TOTAL × WINNER CROSS-CHECK")
        print(f"  {'─'*62}")
        t_mu = total_result["mu"]
        w_impl_spread = winner_result["implied_spread"]
        implied_home_w = (t_mu + w_impl_spread) / 2
        implied_away_w = (t_mu - w_impl_spread) / 2
        print(f"  Using winner-implied spread ({w_impl_spread:+.1f}) + total ({t_mu:.1f}):")
        print(f"  Implied {home} score: {implied_home_w:.1f}   Implied {away} score: {implied_away_w:.1f}")

        # Compare total model ensemble std to confidence
        t_std = total_result["std"]
        if t_std < 3.0:
            t_conf = "HIGH"
        elif t_std < 6.0:
            t_conf = "MEDIUM"
        else:
            t_conf = "LOW"
        print(f"  Total model confidence: {t_conf} (ensemble std={t_std:.2f})")

    _print_separator(W)
    print()


# ── Public API (kept for trade_signals.py compatibility) ─────────────────────

def predict_matchups(
    matchups: list[tuple[str, str]],
    target: str = "all",
    verbose: bool = True,
) -> pd.DataFrame:
    targets = ["winner", "spread", "total"] if target == "all" else [target]
    df = pd.read_parquet(GAME_PARQUET)

    for home, away in matchups:
        predict_and_print(home.upper(), away.upper(), df, targets)

    # Return predictions for backward compatibility + total
    spread_bundle = _load_bundle("spread")
    total_bundle = _load_bundle("total") if "total" in targets or target == "all" else None
    rows = []
    for home, away in matchups:
        h, a = home.upper(), away.upper()
        X_s = build_matchup_row(df, h, a, _get_features(spread_bundle))
        s_mean, _, _ = _ensemble_preds(spread_bundle, X_s)
        row = {"home_team": h, "away_team": a, "predicted_margin": round(float(s_mean), 2)}
        for s in np.arange(-10.5, 11.5, 1.0):
            row[f"cover_{s:+.1f}"] = round(cover_prob(s, s_mean), 3)
        if total_bundle:
            X_t = build_matchup_row(df, h, a, _get_features(total_bundle))
            t_mean, _, _ = _ensemble_preds(total_bundle, X_t)
            row["predicted_total"] = round(float(t_mean), 2)
            for line in np.arange(190.5, 240.5, 5.0):
                row[f"over_{line:.1f}"] = round(over_prob(line, t_mean), 3)
        rows.append(row)
    return pd.DataFrame(rows)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Predict NBA game outcomes (winner + spread)",
        usage="python -m strategy.predict HOME AWAY [HOME AWAY ...]",
    )
    parser.add_argument("teams", nargs="+",
                        help="Team pairs: HOME AWAY [HOME AWAY ...]")
    parser.add_argument("--target", default="all",
                        choices=["all", "winner", "spread", "total"],
                        help="Which model(s) to run (default: all)")
    args = parser.parse_args()

    if len(args.teams) % 2 != 0:
        parser.error("Teams must be in pairs (home away home away ...)")

    matchups = [(args.teams[i], args.teams[i+1]) for i in range(0, len(args.teams), 2)]
    predict_matchups(matchups, target=args.target)
