"""
feature_routing.py
------------------
Read feature_report.csv from the importance pipeline and generate per-model-family
feature lists. Each feature is classified by its pass/fail pattern across the 4
importance methods (MDI, SFI, PCA-MDA, Residual-MDA) and routed to the model
families best suited to exploit its signal structure.

Usage:
    from strategy.feature_routing import route_features
    groups = route_features("winner")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from strategy.config import FEATURES_ROOT

logger = logging.getLogger(__name__)


FEATURE_GROUPS = {
    "accepted": "All 4 methods pass — universal signal, used by all models",
    "complementary": "MDI+PCA+RESID pass, SFI fails — interaction features for trees",
    "linear_only": "PCA+RESID pass, MDI+SFI fail — linear-combination signal only",
    "absorbed": "MDI+SFI+PCA pass, RESID fails — substitutes for diversity",
    "redundant": "MDI+PCA only — signal captured by accepted set",
    "noise": "PCA only — riding dominant eigenvectors",
    "rejected": "0 methods pass — no signal",
}


def _classify_feature(row: pd.Series) -> str:
    """Classify a single feature by its method pass/fail pattern."""
    mdi = bool(row["mdi_passes"])
    sfi = bool(row["sfi_passes"])
    pca = bool(row["pca_mda_passes"])
    resid = bool(row["resid_mda_passes"])

    if row["tier"] == "ACCEPTED":
        return "accepted"
    if row["tier"] == "REJECTED":
        return "rejected"

    if mdi and not sfi and pca and resid:
        return "complementary"
    if not mdi and not sfi and pca and resid:
        return "linear_only"
    if mdi and sfi and pca and not resid:
        return "absorbed"
    if mdi and not sfi and pca and not resid:
        return "redundant"
    if not mdi and not sfi and pca and not resid:
        return "noise"

    # Remaining edge cases: classify conservatively
    if resid and pca:
        return "complementary" if mdi else "linear_only"
    if sfi:
        return "absorbed"
    return "redundant"


def route_features(target: str) -> dict[str, list[str]]:
    """
    Read feature_report.csv for the given target and classify features into
    model-family-appropriate groups.

    Returns dict with keys matching output file suffixes:
        'trees'     → ACCEPTED + COMPLEMENTARY
        'linear'    → ACCEPTED + LINEAR_ONLY
        'diversity' → ACCEPTED + ABSORBED
        'full'      → ACCEPTED + COMPLEMENTARY + LINEAR_ONLY
    """
    report_path = FEATURES_ROOT / target / "filtered" / "feature_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(
            f"No feature_report.csv for target '{target}'. "
            f"Run: python -m feature_pipeline.analysis.run --target target_{target} "
            f"--output-dir output/features/{target}"
        )

    df = pd.read_csv(report_path)
    df["group"] = df.apply(_classify_feature, axis=1)

    groups = {}
    for group_name in FEATURE_GROUPS:
        groups[group_name] = df[df["group"] == group_name]["feature"].tolist()

    accepted = groups["accepted"]
    complementary = groups["complementary"]
    linear_only = groups["linear_only"]
    absorbed = groups["absorbed"]

    # Linear list: use logistic_validation.csv if already run, else fall back to accepted
    validated_linear_path = FEATURES_ROOT / target / "filtered" / "feature_list_linear.txt"
    if validated_linear_path.exists():
        from strategy.config import load_feature_list
        linear_features = load_feature_list(validated_linear_path)
        logger.info("  Linear features from logistic validation: %d", len(linear_features))
    else:
        linear_features = accepted
        logger.info("  Linear features: falling back to %d accepted (run logistic_validation first)", len(accepted))

    feature_lists = {
        "trees": accepted + complementary,
        "linear": linear_features,
        "diversity": accepted + absorbed,
        "full": accepted + complementary,
    }

    logger.info(
        "Feature routing for '%s': accepted=%d, complementary=%d, "
        "linear_only=%d, absorbed=%d, redundant=%d, noise=%d, rejected=%d",
        target,
        len(accepted), len(complementary), len(linear_only), len(absorbed),
        len(groups["redundant"]), len(groups["noise"]), len(groups["rejected"]),
    )

    return feature_lists


def write_feature_lists(target: str, feature_lists: dict[str, list[str]]) -> dict[str, Path]:
    """Write per-group feature lists to output/features/{target}/filtered/."""
    filtered_dir = FEATURES_ROOT / target / "filtered"
    filtered_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    for group, features in feature_lists.items():
        path = filtered_dir / f"feature_list_{group}.txt"
        path.write_text("\n".join(features) + "\n")
        paths[group] = path
        logger.info("  Wrote %s (%d features)", path.name, len(features))

    return paths


def write_routing_report(target: str, feature_lists: dict[str, list[str]]) -> Path:
    """Write routing_report.json with counts and feature assignments."""
    report_path = FEATURES_ROOT / target / "filtered" / "routing_report.json"

    report = {
        "target": target,
        "group_counts": {k: len(v) for k, v in feature_lists.items()},
        "groups": feature_lists,
    }

    report_path.write_text(json.dumps(report, indent=2))
    logger.info("  Wrote routing_report.json")
    return report_path


def run_routing(target: str) -> dict[str, list[str]]:
    """Full routing: classify → write lists → write report. Returns feature_lists."""
    logger.info("Feature routing for target: %s", target)
    feature_lists = route_features(target)
    write_feature_lists(target, feature_lists)
    write_routing_report(target, feature_lists)
    return feature_lists


# ─────────────────────────────────────────────────────────────────────────────
#  Per-family feature set routing (granular, evidence-based)
# ─────────────────────────────────────────────────────────────────────────────

# Model family groupings — NBA model names
_GBDT = {"lgbm", "xgb", "catboost"}
_RF_ET = {"rf", "extratrees"}
_WEAK_TREE = {"hgb", "adaboost"}
_LINEAR = {"logreg", "ridge", "lda", "sgd", "elasticnet"}
_FRAGILE = {"knn", "gnb", "qda"}
_NEURAL = {"mlp"}


def get_feature_set(family: str, filter_report: pd.DataFrame) -> list[str]:
    """Return the feature list appropriate for this model family.

    Uses the granular pass/fail patterns from filter_report to determine
    which features each model can responsibly consume.

    Routing logic:
      GBDT/RF_ET:   accepted + complementary + standalone (absorbed)
                    (handles interactions, redundancy is cheap)
      WEAK_TREE:    accepted + standalone (absorbed)
                    (sensitive to noise, needs reasonably clean signal)
      NEURAL:       accepted + standalone (absorbed)
                    (moderate robustness, benefits from more features)
      LINEAR:       accepted + standalone + linear_only
                    (needs orthogonal features, PCA-MDA identifies these)
      FRAGILE:      accepted only
                    (curse of dimensionality, only proven features)

    Parameters
    ----------
    family : str
        Model family name (NBA naming: lgbm, xgb, catboost, rf, extratrees,
        hgb, adaboost, logreg, ridge, lda, sgd, elasticnet, knn, gnb, qda, mlp).
    filter_report : pd.DataFrame
        Output of filter_features() with a 'feature' column or feature as index,
        and boolean pass columns (mdi_passes, sfi_passes, pca_mda_passes, resid_mda_passes).
    """
    if "feature" in filter_report.columns:
        df = filter_report.set_index("feature")
    else:
        df = filter_report

    df["_group"] = df.apply(_classify_feature, axis=1)

    accepted = df.index[df["_group"] == "accepted"].tolist()
    complementary = df.index[df["_group"] == "complementary"].tolist()
    absorbed = df.index[df["_group"] == "absorbed"].tolist()
    linear_only = df.index[df["_group"] == "linear_only"].tolist()

    df.drop(columns=["_group"], inplace=True)

    if family in _GBDT | _RF_ET:
        return sorted(accepted + complementary + absorbed)
    elif family in _WEAK_TREE | _NEURAL:
        return sorted(accepted + absorbed)
    elif family in _LINEAR:
        return sorted(accepted + absorbed + linear_only)
    elif family in _FRAGILE:
        return sorted(accepted)
    # Unknown family → conservative
    logger.warning(f"Unknown family {family!r} — using accepted features only")
    return sorted(accepted)
