"""
trading/sizing.py
-----------------
Position sizing that accounts for:
1. Model confidence (ensemble std) — OOF-derived accuracy per std decile
2. Per-cluster inventory caps (prevent correlated concentration)

Accuracy multipliers are derived empirically from OOF data via
load_accuracy_profile(). For regression targets, weight = overall_MAE /
decile_MAE (lower MAE → higher weight). For classification, weight =
(overall_acc - 0.5) / (decile_acc - 0.5). Deciles with n < 100 are capped
at 1.0 (insufficient data).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from strategy.config import KELLY_FRACTION, WINNER_CONFIDENCE_MULTIPLIERS
from trading.config import MAX_CONTRACTS_PER_MARKET

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENSEMBLES_DIR = PROJECT_ROOT / "strategy" / "output" / "nba"

# Accuracy profile cache: {target: np.ndarray of shape (10,)} — one weight per std decile
_ACCURACY_PROFILES: dict[str, np.ndarray] = {}
# Decile boundaries cache: {target: np.ndarray of shape (11,)} — bin edges
_STD_DECILE_EDGES: dict[str, np.ndarray] = {}

# Maximum net inventory per cluster (prevents correlated concentration)
CLUSTER_MAX_CONTRACTS = {
    "direction": 15,   # winner + near-spread (threshold 1-3)
    "magnitude": 10,   # deeper spread (threshold 4+)
    "total": 10,       # total markets
    "h1": 10,          # all first-half markets
}


def load_accuracy_profile(target: str, oof_path: str | Path | None = None) -> np.ndarray:
    """
    Compute per-std-decile accuracy multiplier from OOF data. Cached after first call.

    For regression: weight[d] = overall_MAE / decile_MAE  (higher = more accurate decile)
    For classification: weight[d] = (overall_acc - 0.5) / (decile_acc - 0.5)

    Deciles with n < 100 are capped at 1.0 (not enough data to trust).
    Returns array of shape (10,) with weights for deciles D1..D10.
    """
    if target in _ACCURACY_PROFILES:
        return _ACCURACY_PROFILES[target]

    if oof_path is None:
        oof_path = ENSEMBLES_DIR / target / "ensemble_oof.csv"
    oof_path = Path(oof_path)

    if not oof_path.exists():
        logger.warning(f"No OOF for {target} — using flat accuracy profile")
        _ACCURACY_PROFILES[target] = np.ones(10)
        _STD_DECILE_EDGES[target] = np.zeros(11)
        return _ACCURACY_PROFILES[target]

    oof = pd.read_csv(oof_path)
    if "pred_ensemble" in oof.columns and "y_pred_ensemble" not in oof.columns:
        oof = oof.rename(columns={"pred_ensemble": "y_pred_ensemble"})
    pred_cols = [c for c in oof.columns if c.startswith("pred_") and c != "y_pred_ensemble"]
    oof["model_std"] = oof[pred_cols].std(axis=1) if len(pred_cols) > 1 else 0.0

    # Classify task from ensemble_config if available
    import json
    cfg_path = ENSEMBLES_DIR / target / "ensemble_config.json"
    task = "regression"
    if cfg_path.exists():
        with open(cfg_path) as f:
            task = json.load(f).get("task", "regression")

    # Decile boundaries (stored for lookup at signal time)
    edges = np.percentile(oof["model_std"], np.linspace(0, 100, 11))
    _STD_DECILE_EDGES[target] = edges

    weights = np.ones(10)
    if task == "classification":
        overall_acc = float((oof["y_pred_ensemble"].round() == oof["y_true"]).mean())
        overall_skill = max(overall_acc - 0.5, 1e-6)
        for d in range(10):
            lo, hi = edges[d], edges[d + 1]
            mask = (oof["model_std"] >= lo) & (oof["model_std"] < hi if d < 9 else oof["model_std"] <= hi)
            n = mask.sum()
            if n < 100:
                weights[d] = 1.0  # insufficient data — don't adjust
            else:
                dec_acc = float((oof.loc[mask, "y_pred_ensemble"].round() == oof.loc[mask, "y_true"]).mean())
                dec_skill = max(dec_acc - 0.5, 1e-6)
                weights[d] = np.clip(dec_skill / overall_skill, 0.2, 2.0)
    else:
        overall_mae = float((oof["y_true"] - oof["y_pred_ensemble"]).abs().mean())
        for d in range(10):
            lo, hi = edges[d], edges[d + 1]
            mask = (oof["model_std"] >= lo) & (oof["model_std"] < hi if d < 9 else oof["model_std"] <= hi)
            n = mask.sum()
            if n < 100:
                weights[d] = 1.0
            else:
                dec_mae = float((oof.loc[mask, "y_true"] - oof.loc[mask, "y_pred_ensemble"]).abs().mean())
                weights[d] = np.clip(overall_mae / max(dec_mae, 1e-6), 0.2, 2.0)

    _ACCURACY_PROFILES[target] = weights
    logger.info(f"[{target}] accuracy profile: {np.round(weights, 3)}")
    return weights


def get_accuracy_multiplier(market_type: str, model_std: float) -> float:
    """Look up per-std-decile accuracy multiplier for a signal."""
    profile = _ACCURACY_PROFILES.get(market_type)
    edges = _STD_DECILE_EDGES.get(market_type)
    if profile is None or edges is None or edges.max() == 0:
        return 1.0
    d = int(np.searchsorted(edges[1:-1], model_std, side="right"))  # 0..9
    return float(profile[d])


def preload_accuracy_profiles() -> None:
    """Load accuracy profiles for all targets that have OOF CSVs. Call once at startup."""
    targets = ["winner", "home_wins_h1", "spread", "h1_spread", "h1_total", "h2_total", "total"]
    for t in targets:
        load_accuracy_profile(t)


def classify_cluster(market_type: str, threshold: float = 0) -> str:
    """Assign a signal to its correlation cluster."""
    if market_type in ("winner",):
        return "direction"
    if market_type == "spread" and abs(threshold) <= 3:
        return "direction"
    if market_type == "spread":
        return "magnitude"
    if market_type in ("total",):
        return "total"
    if market_type.startswith("h1"):
        return "h1"
    return "direction"


@dataclass
class SizedSignal:
    ticker: str
    market_type: str
    side: str
    contracts: int
    model_prob: float
    market_price: float
    edge: float
    cluster: str
    weight_breakdown: dict  # for logging/transparency


def size_signals(
    signals: list,
    bankroll: float,
    existing_inventory: dict[str, int] | None = None,
    enforce_caps: bool = True,
) -> list[SizedSignal]:
    """
    Size all signals accounting for:
    - Edge magnitude (Kelly)
    - OOF-empirical accuracy multiplier (per std-decile, per target)
    - Cluster inventory caps (only when enforce_caps=True)

    Args:
        signals: list of Signal dataclass instances from scanner
        bankroll: total dollars available
        existing_inventory: {cluster_name: current_net_contracts}
        enforce_caps: if False, skip cluster caps (for resting orders / leverage)

    Returns sorted by priority (highest composite weight first).
    """
    if existing_inventory is None:
        existing_inventory = {}

    cluster_used = {k: existing_inventory.get(k, 0) for k in CLUSTER_MAX_CONTRACTS}

    scored = []
    for sig in signals:
        if sig.edge <= 0 or sig.market_price <= 0 or sig.market_price >= 1:
            continue
        kelly_raw = sig.edge / (1.0 - sig.market_price)

        # OOF-empirical: how accurate is this model at this ensemble std level?
        accuracy_mult = get_accuracy_multiplier(sig.market_type, sig.model_std)

        threshold = _extract_threshold(sig)
        composite = kelly_raw * KELLY_FRACTION * accuracy_mult

        bet_dollars = min(composite * bankroll, bankroll * 0.03)
        contracts_raw = bet_dollars / sig.market_price if sig.market_price > 0 else 0

        cluster = classify_cluster(sig.market_type, threshold)

        scored.append({
            "signal": sig,
            "contracts_raw": contracts_raw,
            "composite": composite,
            "cluster": cluster,
            "threshold": threshold,
            "weights": {
                "kelly_raw": kelly_raw,
                "accuracy_mult": accuracy_mult,
                "composite": composite,
            },
        })

    scored.sort(key=lambda x: -x["composite"])

    sized = []
    for s in scored:
        sig = s["signal"]
        cluster = s["cluster"]

        if enforce_caps:
            max_cluster = CLUSTER_MAX_CONTRACTS.get(cluster, 10)
            remaining = max_cluster - cluster_used.get(cluster, 0)
            if remaining <= 0:
                continue
            contracts = int(min(s["contracts_raw"], remaining, MAX_CONTRACTS_PER_MARKET))
        else:
            contracts = int(min(s["contracts_raw"], MAX_CONTRACTS_PER_MARKET))

        contracts = max(1, contracts)
        cluster_used[cluster] = cluster_used.get(cluster, 0) + contracts

        sized.append(SizedSignal(
            ticker=sig.ticker,
            market_type=sig.market_type,
            side=sig.side,
            contracts=contracts,
            model_prob=sig.model_prob,
            market_price=sig.market_price,
            edge=sig.edge,
            cluster=cluster,
            weight_breakdown=s["weights"],
        ))

    return sized


def _extract_threshold(sig) -> float:
    """
    Extract threshold in the prediction's coordinate space.

    For spread: prediction is home_spread. Ticker like "...-SAS9" means
    "away wins by 9" = home_spread of -9. Ticker like "...-NYK9" means
    "home wins by 9" = home_spread of +9. We use the game_key (2nd part
    of ticker) to determine home team (last 3 chars).

    For total: threshold is the line (e.g., 103, 219).
    """
    import re
    ticker = sig.ticker
    if sig.market_type in ("spread", "h1_spread"):
        parts = ticker.split("-")
        if len(parts) != 3:
            return 0
        game_key = parts[1]  # e.g. "26JUN08SASNYK"
        market_part = parts[2]  # e.g. "SAS9" or "NYK12"
        m = re.match(r"([A-Z]{2,3})(\d+\.?\d*)", market_part)
        if not m:
            return 0
        team = m.group(1)
        points = float(m.group(2))
        # Home team is last 2-3 chars of game_key
        home = re.search(r"[A-Z]{2,3}$", game_key).group()
        if team == home:
            return points  # home wins by X = home_spread of +X
        else:
            return -points  # away wins by X = home_spread of -X
    elif sig.market_type in ("total", "h1_total"):
        parts = ticker.split("-")
        try:
            return float(parts[-1])
        except ValueError:
            return 0
    return 0
