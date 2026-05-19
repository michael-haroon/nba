"""
Compute configuration for the feature pipeline. CPU-only.
"""

from __future__ import annotations

import os


def get_n_jobs() -> int:
    return os.cpu_count() or 1


def get_n_random_combos() -> int:
    return int(os.environ.get("N_RANDOM_COMBOS", "50"))


def get_rf_params() -> dict:
    return {
        "n_estimators": 500,
        "max_depth": None,
        "min_samples_leaf": 5,
        "n_jobs": -1,
        "random_state": 42,
    }
