"""
Compute configuration for the feature pipeline. CPU-only.

BLAS/LAPACK thread env vars are set below BEFORE numpy is imported anywhere.
Import this module early (before numpy) to ensure threads are configured.
"""

from __future__ import annotations

import os

_N_CPUS = os.cpu_count() or 1
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(_N_CPUS))
os.environ.setdefault("OMP_NUM_THREADS", str(_N_CPUS))
os.environ.setdefault("MKL_NUM_THREADS", str(_N_CPUS))
os.environ.setdefault("NUMEXPR_MAX_THREADS", str(_N_CPUS))


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


def blas_limit(n_threads: int = 1):
    """Limit BLAS threads during joblib parallel sections to prevent oversubscription."""
    from threadpoolctl import threadpool_limits
    return threadpool_limits(limits=n_threads, user_api="blas")


def blas_full():
    """Expand BLAS threads to all available cores for single-process linear algebra."""
    from threadpoolctl import threadpool_limits
    return threadpool_limits(limits=_N_CPUS, user_api="blas")
