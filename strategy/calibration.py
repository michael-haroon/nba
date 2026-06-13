"""
calibration.py
--------------
Auto-calibration pipeline. Computes all distributional parameters from OOF
predictions so nothing is hardcoded. Run after ensemble training completes.

Produces a calibration dict stored in the ensemble pickle bundle:
  - residual_dist: {df, scale} for t-distribution fit to OOF residuals
  - std_thresholds: (p33, p67) of ensemble std across OOF predictions
  - confidence_multipliers: derived from accuracy in each tercile
  - bias_table: binned residual bias for cover probability correction
  - isotonic_calibrator: fitted IsotonicRegression (classification only)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

logger = logging.getLogger(__name__)


def fit_residual_distribution(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Fit Student-t to OOF residuals via MLE (loc forced to 0).
    Returns {df, scale} for use in cover/over probability calculations.
    """
    residuals = y_true - y_pred
    df_fit, loc_fit, scale_fit = t_dist.fit(residuals, floc=0)
    return {"df": float(df_fit), "scale": float(scale_fit)}


def compute_std_thresholds(ensemble_stds: np.ndarray) -> tuple[float, float]:
    """Tercile boundaries of ensemble prediction std."""
    p33 = float(np.percentile(ensemble_stds, 33.33))
    p67 = float(np.percentile(ensemble_stds, 66.67))
    return (p33, p67)


def compute_confidence_multipliers(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ensemble_stds: np.ndarray,
    std_thresholds: tuple[float, float],
) -> dict[str, float]:
    """
    Derive Kelly multipliers from empirical accuracy in each confidence tier.
    The multiplier is proportional to the accuracy gain over baseline (50%).
    HIGH tier gets 1.0, others are scaled relative to HIGH's edge.
    """
    lo, hi = std_thresholds
    correct = ((y_pred >= 0.5) == (y_true == 1)).astype(float)

    high_mask = ensemble_stds <= lo
    med_mask = (ensemble_stds > lo) & (ensemble_stds <= hi)
    low_mask = ensemble_stds > hi

    acc_high = correct[high_mask].mean() if high_mask.sum() > 0 else 0.5
    acc_med = correct[med_mask].mean() if med_mask.sum() > 0 else 0.5
    acc_low = correct[low_mask].mean() if low_mask.sum() > 0 else 0.5

    edge_high = acc_high - 0.5
    if edge_high <= 0:
        return {"HIGH": 1.0, "MEDIUM": 0.75, "LOW": 0.5}

    mult_med = max(0.0, (acc_med - 0.5) / edge_high)
    mult_low = max(0.0, (acc_low - 0.5) / edge_high)

    logger.info(
        "Confidence tiers: HIGH acc=%.3f (1.00x), MED acc=%.3f (%.2fx), LOW acc=%.3f (%.2fx)",
        acc_high, acc_med, mult_med, acc_low, mult_low,
    )

    return {"HIGH": 1.0, "MEDIUM": round(mult_med, 3), "LOW": round(mult_low, 3)}


def compute_bias_table(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    residual_scale: float,
    residual_df: float,
    bin_edges: list[float] | None = None,
) -> list[dict]:
    """
    Compute systematic bias in cover probabilities by delta bin.
    For each bin of |threshold - prediction|, measures (empirical_cover_rate - model_cover_rate).
    """
    if bin_edges is None:
        bin_edges = [0, 2.5, 22.5, 100]

    residuals = y_true - y_pred
    table = []

    for i in range(len(bin_edges) - 1):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (np.abs(y_pred) >= lo) & (np.abs(y_pred) < hi)
        if mask.sum() < 50:
            table.append({"delta_lo": lo, "delta_hi": hi, "correction": 0.0, "n": int(mask.sum())})
            continue

        # For spread: empirical P(home wins) vs model P(home wins) in this delta range
        empirical_rate = (y_true[mask] > 0).mean()
        model_rate = float(
            (1 - t_dist.cdf(-y_pred[mask] / residual_scale, df=residual_df)).mean()
        )
        correction = float(empirical_rate - model_rate)
        table.append({
            "delta_lo": lo, "delta_hi": hi,
            "correction": round(correction, 4),
            "n": int(mask.sum()),
        })

    return table


def fit_isotonic_calibrator(y_true: np.ndarray, y_pred: np.ndarray):
    """Fit isotonic regression for probability calibration (classification only)."""
    from sklearn.isotonic import IsotonicRegression
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(y_pred, y_true)
    return calibrator


def calibrate_bundle(
    bundle: dict,
    oof_preds: np.ndarray,
    oof_labels: np.ndarray,
    oof_stds: np.ndarray | None = None,
) -> dict:
    """
    Attach all calibration artifacts to an ensemble bundle dict.
    Call this after ensemble training, before pickling.

    Args:
        bundle: the ensemble dict (has 'task', 'specialists', etc.)
        oof_preds: combined OOF predictions (weighted ensemble output)
        oof_labels: true labels/values aligned to oof_preds
        oof_stds: per-sample ensemble std (for classification confidence tiers)

    Returns:
        bundle with 'calibration' key added
    """
    task = bundle["task"]
    cal = {}

    if task == "classification":
        cal["isotonic_calibrator"] = fit_isotonic_calibrator(oof_labels, oof_preds)

        if oof_stds is not None:
            thresholds = compute_std_thresholds(oof_stds)
            cal["std_thresholds"] = thresholds
            cal["confidence_multipliers"] = compute_confidence_multipliers(
                oof_labels, oof_preds, oof_stds, thresholds,
            )
        logger.info(
            "Classification calibration: isotonic fitted on %d samples, "
            "std_thresholds=%s",
            len(oof_preds), cal.get("std_thresholds"),
        )

    else:
        residual_dist = fit_residual_distribution(oof_labels, oof_preds)
        cal["residual_dist"] = residual_dist

        bias_table = compute_bias_table(
            oof_labels, oof_preds,
            residual_dist["scale"], residual_dist["df"],
        )
        cal["bias_table"] = bias_table

        if oof_stds is not None:
            cal["std_thresholds"] = compute_std_thresholds(oof_stds)

        logger.info(
            "Regression calibration: t(df=%.2f, scale=%.2f), bias_table=%d bins",
            residual_dist["df"], residual_dist["scale"], len(bias_table),
        )

    bundle["calibration"] = cal
    return bundle


def kalshi_taker_fee(price: float, contracts: int = 1) -> float:
    """
    Kalshi taker fee per contract: ceil(0.07 * C * P * (1-P)).
    Returns fee in dollars for the given number of contracts.
    """
    raw = 0.07 * contracts * price * (1 - price)
    return np.ceil(raw * 100) / 100


def kalshi_maker_fee(price: float, contracts: int = 1) -> float:
    """
    Kalshi maker fee per contract: ceil(0.0175 * C * P * (1-P)).
    Returns fee in dollars.
    """
    raw = 0.0175 * contracts * price * (1 - price)
    return np.ceil(raw * 100) / 100


def min_edge_for_profit(price: float, maker: bool = False) -> float:
    """
    Minimum edge (in probability points) needed to breakeven after Kalshi fees.

    For a YES contract at price P:
      Profit if win: (1 - P) - fee
      Loss if lose: P + fee (you paid P and lose it, plus fee on entry)
      Fee is charged on entry only, not on settlement.
      Net expected profit = edge - fee_per_contract
      Breakeven: edge = fee / (1 - P)

    Fee per contract = 0.07 * P * (1-P) for taker, 0.0175 * P * (1-P) for maker.
    So: min_edge = 0.07 * P * (1-P) / (1-P) = 0.07 * P (taker)
        min_edge = 0.0175 * P (maker)
    """
    if maker:
        return 0.0175 * price * (1 - price)
    return 0.07 * price * (1 - price)


def compute_min_edge_table() -> dict[str, float]:
    """
    Compute minimum edge thresholds at representative prices.
    Returns dict mapping price bucket to minimum edge (as fraction, not %).
    """
    prices = np.arange(0.30, 0.80, 0.05)
    table = {}
    for p in prices:
        table[f"{p:.2f}"] = round(min_edge_for_profit(p), 4)
    return table
