"""
trading/models.py
-----------------
Multi-model prediction engine. Loads all available ensembles and converts
point predictions to binary probabilities for each Kalshi threshold market.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENSEMBLES_DIR = PROJECT_ROOT / "strategy" / "output" / "nba"

# Maps our model target name → Kalshi series prefix
# NOTE: "total" is excluded — game total is derived synthetically as h1_total + h2_total
# h2_total has no direct Kalshi market but is loaded as a support model for the synthetic total
MODEL_TO_SERIES = {
    "winner": "KXNBAGAME",
    "spread": "KXNBASPREAD",
    "h1_spread": "KXNBA1HSPREAD",
    "h1_total": "KXNBA1HTOTAL",
    "h2_total": "KXNBA2HTOTAL",   # support model: needed for synthetic game total
    "home_wins_h1": "KXNBA1HWINNER",
}


class EmpiricalResiduals:
    """
    Semi-parametric survival function from OOF residuals.

    Uses empirical CDF in the body of the distribution (where we have ≥ 30 samples
    on each side of delta), and falls back to the fitted t-distribution in the tails.
    This avoids distributional assumptions in the center while remaining smooth at extremes.
    """

    def __init__(self, residuals: np.ndarray, t_df: float, t_scale: float):
        self.residuals = np.sort(residuals)
        self.n = len(self.residuals)
        self.t_df = t_df
        self.t_scale = t_scale
        # Use empirical only where we have ≥ 30 observations on each tail
        tail_n = min(30, max(1, self.n // 20))
        self.lo = float(self.residuals[tail_n - 1])
        self.hi = float(self.residuals[-(tail_n)])

    def survival(self, delta: float) -> float:
        """P(residual > delta)"""
        if delta <= self.lo or delta >= self.hi:
            return float(1 - stats.t.cdf(delta / self.t_scale, self.t_df))
        count_above = self.n - int(np.searchsorted(self.residuals, delta, side="right"))
        return float(count_above / self.n)


def _load_empirical_residuals(target: str) -> EmpiricalResiduals | None:
    """Load OOF residuals for a target and build EmpiricalResiduals. Returns None if unavailable."""
    oof_path = ENSEMBLES_DIR / target / "ensemble_oof.csv"
    if not oof_path.exists():
        return None
    try:
        oof = pd.read_csv(oof_path)
        if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
            oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})
        residuals = (oof["y_true"] - oof["y_pred_ensemble"]).values
        rd = {}
        # Try to get t-dist params from bundle calibration; fall back to MLE fit
        try:
            from scipy.stats import t as t_dist
            df, _, scale = t_dist.fit(residuals, floc=0)
        except Exception:
            df, scale = 30.0, float(residuals.std())
        return EmpiricalResiduals(residuals, float(df), float(scale))
    except Exception as e:
        logger.warning(f"Could not load OOF residuals for {target}: {e}")
        return None


def load_all_models() -> dict[str, dict]:
    """Load all available ensemble.pkl files. Returns {target_name: bundle}."""
    bundles = {}
    for target in MODEL_TO_SERIES:
        pkl_path = ENSEMBLES_DIR / target / "ensemble.pkl"
        if pkl_path.exists():
            with open(pkl_path, "rb") as f:
                bundles[target] = pickle.load(f)
            logger.info(f"Loaded {target} ({bundles[target]['task']}, "
                        f"{len(bundles[target]['specialists'])} specialists)")
            # Attach empirical residuals for regression models
            if bundles[target].get("task") == "regression":
                empr = _load_empirical_residuals(target)
                if empr is not None:
                    bundles[target]["calibration"]["empirical_residuals"] = empr
                    logger.info(f"  {target}: empirical residuals loaded (n={empr.n}, "
                                f"empirical body [{empr.lo:.1f}, {empr.hi:.1f}])")
    return bundles


def predict_regression(bundle: dict, X: pd.DataFrame) -> dict:
    """Predict point value for regression models. Returns {value, std}."""
    specialists = bundle["specialists"]
    weights = np.array(bundle["weights"])

    preds = []
    for s in specialists:
        X_sub = X[s["features"]].copy()
        if s.get("impute_median"):
            X_sub = X_sub.fillna(pd.Series(s["impute_median"]))
        if s.get("needs_scaling"):
            X_sub = (X_sub - pd.Series(s["scale_mean"])) / pd.Series(s["scale_std"])
        try:
            p = float(s["model"].predict(X_sub)[0])
        except Exception:
            p = 0.0
        preds.append(p)

    preds_arr = np.array(preds)

    # Reject outlier models (>3 MADs from median)
    if len(preds) >= 3:
        median = float(np.median(preds_arr))
        mad = float(np.median(np.abs(preds_arr - median)))
        if mad > 0:
            keep = np.abs(preds_arr - median) <= 3 * mad
            if keep.sum() >= 2:
                preds_arr = preds_arr[keep]
                weights = weights[keep]

    weights = weights / weights.sum()
    value = float(np.dot(preds_arr, weights))
    std = float(np.std(preds_arr))
    return {"value": value, "std": std}


def predict_classification(bundle: dict, X: pd.DataFrame) -> dict:
    """Predict probability for classification models. Returns {prob, std}."""
    specialists = bundle["specialists"]
    weights = np.array(bundle["weights"])

    preds = []
    for s in specialists:
        X_sub = X[s["features"]].copy()
        if s.get("impute_median"):
            X_sub = X_sub.fillna(pd.Series(s["impute_median"]))
        if s.get("needs_scaling"):
            X_sub = (X_sub - pd.Series(s["scale_mean"])) / pd.Series(s["scale_std"])
        try:
            p = float(s["model"].predict_proba(X_sub)[:, 1][0])
        except Exception:
            p = 0.5
        preds.append(p)

    preds_arr = np.array(preds)

    # Reject outlier models (>3 MADs from median)
    if len(preds) >= 3:
        median = float(np.median(preds_arr))
        mad = float(np.median(np.abs(preds_arr - median)))
        if mad > 0:
            keep = np.abs(preds_arr - median) <= 3 * mad
            if keep.sum() >= 2:
                preds_arr = preds_arr[keep]
                weights = weights[keep]

    weights = weights / weights.sum()
    prob = float(np.dot(preds_arr, weights))
    std = float(np.std(preds_arr))
    return {"prob": prob, "std": std}


def threshold_probability(predicted_value: float, threshold: float,
                          calibration: dict, direction: str = "above") -> float:
    """
    Convert a regression prediction to P(outcome > threshold) or P(outcome < threshold).

    Uses empirical OOF residual CDF in the body of the distribution (where we have
    sufficient data) and falls back to the fitted t-distribution in the tails.
    direction: "above" for spread/total over, "below" for total under.
    """
    delta = threshold - predicted_value

    empr: EmpiricalResiduals | None = calibration.get("empirical_residuals")
    if empr is not None:
        p_above = empr.survival(delta)
    else:
        rd = calibration.get("residual_dist", {})
        df = rd.get("df", 30)
        scale = rd.get("scale", 10)
        p_above = float(1 - stats.t.cdf(delta / scale, df))

    return p_above if direction == "above" else (1.0 - p_above)


def parse_spread_ticker(ticker: str) -> dict | None:
    """
    Parse spread ticker like KXNBASPREAD-26JUN08SASNYK-SAS5 or NYK3.
    Returns {game_key, team, threshold, direction}.
    direction: team wins by threshold+ means home_spread > threshold (if team=home)
               or home_spread < -threshold (if team=away)
    """
    import re
    parts = ticker.split("-")
    if len(parts) != 3:
        return None

    game_key = parts[1]  # 26JUN08SASNYK
    market_part = parts[2]  # e.g. SAS5, NYK12, SAS17

    m = re.match(r"([A-Z]{2,3})(\d+\.?\d*)", market_part)
    if not m:
        return None

    team = m.group(1)
    threshold = float(m.group(2))
    return {"game_key": game_key, "team": team, "threshold": threshold}


def parse_total_ticker(ticker: str) -> dict | None:
    """
    Parse total ticker like KXNBATOTAL-26JUN08SASNYK-219.
    Returns {game_key, threshold}.
    YES = total >= threshold.
    """
    parts = ticker.split("-")
    if len(parts) != 3:
        return None
    game_key = parts[1]
    try:
        threshold = float(parts[2])
    except ValueError:
        return None
    return {"game_key": game_key, "threshold": threshold}


def parse_h1_spread_ticker(ticker: str) -> dict | None:
    """Same format as spread but for first half."""
    return parse_spread_ticker(ticker)


def parse_h1_total_ticker(ticker: str) -> dict | None:
    """Same format as total but for first half."""
    return parse_total_ticker(ticker)
