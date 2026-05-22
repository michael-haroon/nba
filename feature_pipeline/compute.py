"""
Compute configuration for the feature pipeline. CPU-only.
"""

from __future__ import annotations

import os


def get_n_jobs() -> int:
    return os.cpu_count() or 1


def get_parallel_split(n_outer: int) -> tuple[int, int]:
    """
    Split CPU budget between outer and inner parallelism.
    Returns (n_outer_jobs, n_inner_jobs) such that their product ≈ total CPUs.
    """
    n_cpu = get_n_jobs()
    n_outer_jobs = min(n_outer, n_cpu)
    n_inner_jobs = max(1, n_cpu // n_outer_jobs)
    return n_outer_jobs, n_inner_jobs


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
