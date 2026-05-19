#!/usr/bin/env python
"""
Standalone EDA: statistical distribution analysis for NBA betting market targets.

Analyzes three target distributions corresponding to market types:
  - Spread  → P(spread > X)  — regression model output
  - Total   → P(total > N)   — regression model output
  - Exact   → P(total = X)   — discrete/multinomial model output

Runs normality tests (Shapiro-Wilk, D'Agostino K², Anderson-Darling),
fits multiple distributions (Normal, Student-t, Laplace, SkewNorm),
and produces diagnostic plots for each.

Usage:
  conda run -n pred python -m feature_pipeline.eda
  conda run -n pred python -m feature_pipeline.eda --season-type Regular
  conda run -n pred python -m feature_pipeline.eda --output-dir /tmp/eda_out
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats
from scipy.stats import (
    anderson,
    laplace,
    norm,
    normaltest,
    poisson,
    shapiro,
    skewnorm,
)
from scipy.stats import t as student_t

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data_curation" / "data"

CONTINUOUS_DISTS: dict[str, stats.rv_continuous] = {
    "Normal":    norm,
    "Student-t": student_t,
    "Laplace":   laplace,
    "SkewNorm":  skewnorm,
}

DIST_COLORS = {
    "Normal":    "#dc2626",
    "Student-t": "#16a34a",
    "Laplace":   "#d97706",
    "SkewNorm":  "#7c3aed",
}


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_game_scores(season_type_filter: str | None = None) -> pd.DataFrame:
    """
    Load traditional box scores and reconstruct game-level rows.

    Returns DataFrame with: game_date, season, season_type,
    home_pts, away_pts, spread, total.
    """
    raw_frames = []
    for stype in ("Regular", "Playoffs"):
        path = DATA_DIR / f"AdvBoxScoresTrad{stype}.parquet"
        if not path.exists():
            print(f"  [warn] Missing {path.name}, skipping")
            continue
        df = pd.read_parquet(path)
        df["_season_type"] = stype
        raw_frames.append(df)

    if not raw_frames:
        raise FileNotFoundError(f"No box score files found in {DATA_DIR}")

    bs = pd.concat(raw_frames, ignore_index=True)
    bs["game_date"] = pd.to_datetime(bs["GAME DATE"])
    bs["pts"] = pd.to_numeric(bs["PTS"], errors="coerce")

    is_home = bs["MATCH UP"].str.upper().str.contains("VS.", regex=False)
    parts = bs["MATCH UP"].str.split(r"\s+(?:VS\.|vs\.|@)\s+", expand=True, regex=True)
    bs["_team"] = parts[0].str.strip()
    bs["_opp"] = parts[1].str.strip()
    bs["_is_home"] = is_home

    home = bs[bs["_is_home"]].copy()
    away = bs[~bs["_is_home"]].copy()

    home["_jk"] = home["game_date"].dt.strftime("%Y-%m-%d") + "|" + home["_team"]
    away["_jk"] = away["game_date"].dt.strftime("%Y-%m-%d") + "|" + away["_opp"]

    games = home[["_jk", "game_date", "_season_type", "pts"]].merge(
        away[["_jk", "pts"]].rename(columns={"pts": "away_pts"}),
        on="_jk",
        how="inner",
    ).rename(columns={"pts": "home_pts", "_season_type": "season_type"})

    # Attach season label from NBAGameIDs
    ids_path = DATA_DIR / "NBAGameIDs.parquet"
    if ids_path.exists():
        gids = pd.read_parquet(ids_path)[["GAME_DATE", "SEASON_FILTER"]].copy()
        gids["GAME_DATE"] = pd.to_datetime(gids["GAME_DATE"])
        gids = gids.drop_duplicates("GAME_DATE")
        games = games.merge(
            gids.rename(columns={"GAME_DATE": "game_date", "SEASON_FILTER": "season"}),
            on="game_date",
            how="left",
        )
    else:
        games["season"] = None

    games["spread"] = games["home_pts"] - games["away_pts"]
    games["total"] = games["home_pts"] + games["away_pts"]
    games = games.dropna(subset=["home_pts", "away_pts"]).reset_index(drop=True)

    if season_type_filter:
        games = games[games["season_type"] == season_type_filter].reset_index(drop=True)

    return games


# ── Fitting Utilities ─────────────────────────────────────────────────────────

def fit_distribution(data: np.ndarray, dist_name: str, dist) -> dict:
    """Fit a distribution and return params, KS p-value, and AIC."""
    params = dist.fit(data)
    ks_stat, ks_p = stats.kstest(data, dist.cdf, args=params)
    ll = float(np.sum(dist.logpdf(data, *params)))
    aic = 2 * len(params) - 2 * ll
    return {
        "name": dist_name,
        "params": params,
        "ks_stat": ks_stat,
        "ks_p": ks_p,
        "aic": aic,
        "ll": ll,
    }


def fit_all(data: np.ndarray) -> dict[str, dict]:
    return {name: fit_distribution(data, name, dist)
            for name, dist in CONTINUOUS_DISTS.items()}


def print_fit_table(fits: dict[str, dict], label: str) -> None:
    rows = []
    for res in fits.values():
        rows.append({
            "Distribution": res["name"],
            "AIC":          f"{res['aic']:.1f}",
            "Log-lik":      f"{res['ll']:.1f}",
            "KS stat":      f"{res['ks_stat']:.4f}",
            "KS p-value":   f"{res['ks_p']:.4f}",
        })
    df = pd.DataFrame(rows)

    best_aic = min(fits, key=lambda k: fits[k]["aic"])
    best_ks  = max(fits, key=lambda k: fits[k]["ks_p"])

    print(f"\n{'─'*64}")
    print(f"  Distribution Fit Comparison: {label}")
    print(f"{'─'*64}")
    print(df.to_string(index=False))
    print(f"  Best AIC: {best_aic}  |  Best KS p-value: {best_ks}")


def run_normality_tests(data: np.ndarray, label: str) -> pd.DataFrame:
    """Shapiro-Wilk, D'Agostino K², Anderson-Darling."""
    rows = []

    sample = data[:5000] if len(data) > 5000 else data
    sw_stat, sw_p = shapiro(sample)
    rows.append({"Test": "Shapiro-Wilk", "Statistic": f"{sw_stat:.5f}",
                 "p-value": f"{sw_p:.4e}", "Reject H₀ (α=0.05)": sw_p < 0.05})

    da_stat, da_p = normaltest(data)
    rows.append({"Test": "D'Agostino K²", "Statistic": f"{da_stat:.5f}",
                 "p-value": f"{da_p:.4e}", "Reject H₀ (α=0.05)": da_p < 0.05})

    ad = anderson(data, dist="norm")
    cv_5pct = ad.critical_values[2]
    rows.append({"Test": "Anderson-Darling", "Statistic": f"{ad.statistic:.5f}",
                 "p-value": f"(crit@5%={cv_5pct:.3f})",
                 "Reject H₀ (α=0.05)": ad.statistic > cv_5pct})

    df = pd.DataFrame(rows)
    print(f"\n{'─'*64}")
    print(f"  Normality Tests: {label}  (H₀ = data is normal)")
    print(f"{'─'*64}")
    print(df.to_string(index=False))
    return df


# ── Plot: Continuous Distribution ─────────────────────────────────────────────

def plot_continuous(
    data: np.ndarray,
    label: str,
    out_path: Path,
    color: str = "#2563eb",
) -> None:
    """
    4-panel diagnostic figure:
      (1) Histogram + fitted PDFs
      (2) Q-Q plot vs Normal
      (3) ECDF vs best-fit and Normal CDFs
      (4) Residuals from Normal fit
    """
    fits = fit_all(data)
    best_name = min(fits, key=lambda k: fits[k]["aic"])

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"Distribution Analysis — {label}", fontsize=13, fontweight="bold")
    gs_layout = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.3)

    x = np.linspace(data.min() - data.std(), data.max() + data.std(), 500)

    # Panel 1: Histogram + PDFs
    ax1 = fig.add_subplot(gs_layout[0, 0])
    ax1.hist(data, bins=60, density=True, color=color, alpha=0.45,
             edgecolor="white", linewidth=0.3, label="Data")
    for name, res in fits.items():
        y = CONTINUOUS_DISTS[name].pdf(x, *res["params"])
        ls = "-" if name == best_name else "--"
        lw = 2.2 if name == best_name else 1.5
        ax1.plot(x, y, ls, color=DIST_COLORS[name], linewidth=lw,
                 label=f"{name}  AIC={res['aic']:.0f}")
    ax1.set_xlabel(label)
    ax1.set_ylabel("Density")
    ax1.set_title("Histogram + Fitted PDFs")
    ax1.legend(fontsize=8)

    # Panel 2: Q-Q vs Normal
    ax2 = fig.add_subplot(gs_layout[0, 1])
    (osm, osr), (slope, intercept, r) = stats.probplot(data, dist="norm")
    ax2.scatter(osm, osr, s=3, alpha=0.35, color=color)
    ref = np.array([osm[0], osm[-1]])
    ax2.plot(ref, slope * ref + intercept, "r-", linewidth=2, label=f"r={r:.4f}")
    ax2.set_xlabel("Theoretical Quantiles (Normal)")
    ax2.set_ylabel("Sample Quantiles")
    ax2.set_title(f"Q-Q Plot vs Normal")
    ax2.legend(fontsize=9)

    # Panel 3: ECDF vs fitted CDFs
    ax3 = fig.add_subplot(gs_layout[1, 0])
    sorted_data = np.sort(data)
    ecdf_y = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
    ax3.step(sorted_data, ecdf_y, color=color, linewidth=1.8, label="ECDF", zorder=3)

    for name, res in fits.items():
        if name not in (best_name, "Normal"):
            continue
        cdf_y = CONTINUOUS_DISTS[name].cdf(sorted_data, *res["params"])
        ls = "--" if name == "Normal" else "-."
        ax3.plot(sorted_data, cdf_y, ls, color=DIST_COLORS[name],
                 linewidth=2, label=f"{name} CDF")
    ax3.set_xlabel(label)
    ax3.set_ylabel("Cumulative Probability")
    ax3.set_title("ECDF vs Fitted CDFs")
    ax3.legend(fontsize=8)

    # Panel 4: Residuals from Normal
    ax4 = fig.add_subplot(gs_layout[1, 1])
    mu, sigma = fits["Normal"]["params"]
    residuals = (data - mu) / sigma
    ax4.hist(residuals, bins=50, density=True, color=color, alpha=0.45,
             edgecolor="white", linewidth=0.3)
    z = np.linspace(-4.5, 4.5, 300)
    ax4.plot(z, norm.pdf(z), "r-", linewidth=2, label="Standard Normal")
    skew_val = stats.skew(residuals)
    kurt_val = stats.kurtosis(residuals)
    ax4.set_xlabel("Standardized Residual")
    ax4.set_ylabel("Density")
    ax4.set_title(f"Residuals from Normal Fit\nskew={skew_val:.3f}, excess kurt={kurt_val:.3f}")
    ax4.legend(fontsize=9)

    # Footer stats
    summary = (
        f"N={len(data):,}   mean={data.mean():.2f}   std={data.std():.2f}   "
        f"skew={stats.skew(data):.3f}   excess_kurt={stats.kurtosis(data):.3f}   "
        f"[{data.min():.0f}, {data.max():.0f}]"
    )
    fig.text(0.5, 0.005, summary, ha="center", fontsize=9,
             bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.7))

    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Plot: Discrete (Exact Total) ──────────────────────────────────────────────

def plot_exact_total(data: np.ndarray, out_path: Path) -> None:
    """
    3-panel discrete distribution figure:
      (1) Empirical PMF + Poisson + Normal PDF overlay
      (2) Empirical CDF vs Poisson CDF vs Normal CDF
      (3) Heatmap of P(total = x) by season_year (if passed)
    """
    data_int = data.astype(int)
    counts = pd.Series(data_int).value_counts().sort_index()
    total_n = len(data_int)
    pmf = counts / total_n

    xmin, xmax = int(data_int.min()), int(data_int.max())
    bins = np.arange(xmin, xmax + 1)

    mu, sigma = data.mean(), data.std()
    lam = mu

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Discrete Distribution Analysis — Exact Total Points",
                 fontsize=13, fontweight="bold")

    # Panel 1: PMF
    ax = axes[0]
    ax.bar(pmf.index, pmf.values, color="#2563eb", alpha=0.55,
           width=0.8, label="Observed PMF")
    pois_pmf = poisson.pmf(bins, lam)
    ax.plot(bins, pois_pmf, "r-o", markersize=2.5, linewidth=1.5,
            label=f"Poisson (λ={lam:.1f})")
    ax.plot(bins, norm.pdf(bins, mu, sigma), "g--", linewidth=2,
            label=f"Normal (μ={mu:.1f}, σ={sigma:.1f})")
    ax.set_xlabel("Total Points")
    ax.set_ylabel("P(Total = x)")
    ax.set_title("Empirical PMF vs Fitted Distributions")
    ax.legend(fontsize=9)

    # Panel 2: CDF
    ax2 = axes[1]
    cum_pmf = pmf.cumsum()
    ax2.step(cum_pmf.index, cum_pmf.values, where="post",
             color="#2563eb", linewidth=2, label="Empirical CDF")
    ax2.plot(bins, poisson.cdf(bins, lam), "r--", linewidth=2,
             label=f"Poisson CDF (λ={lam:.1f})")
    ax2.plot(bins, norm.cdf(bins, mu, sigma), "g:", linewidth=2,
             label="Normal CDF")
    ax2.set_xlabel("Total Points")
    ax2.set_ylabel("P(Total ≤ x)")
    ax2.set_title("Empirical CDF vs Fitted CDFs")
    ax2.legend(fontsize=9)

    # Chi-square tests (cells with expected >= 5)
    chi2_lines = []
    for dist_name, expected in [
        ("Normal",  norm.pdf(counts.index.values.astype(float), mu, sigma) * total_n),
        ("Poisson", poisson.pmf(counts.index.values.astype(int), lam) * total_n),
    ]:
        mask = expected >= 5
        if mask.sum() >= 2:
            # Rescale expected to match observed sum so chi-square is valid
            exp_masked = expected[mask]
            exp_masked = exp_masked * counts.values[mask].sum() / exp_masked.sum()
            stat, p = stats.chisquare(counts.values[mask], f_exp=exp_masked)
            chi2_lines.append(f"χ² vs {dist_name}: stat={stat:.2f}, p={p:.4f} "
                              f"({'reject' if p < 0.05 else 'fail to reject'} H₀)")
        else:
            chi2_lines.append(f"χ² vs {dist_name}: insufficient cells for test")

    summary = (
        f"N={total_n:,}   mean={mu:.2f}   std={sigma:.2f}   "
        f"skew={stats.skew(data):.3f}   excess_kurt={stats.kurtosis(data):.3f}   "
        f"range=[{xmin}, {xmax}]\n"
        + "   ".join(chi2_lines)
    )
    print(f"\n  Chi-square goodness-of-fit:")
    for line in chi2_lines:
        print(f"    {line}")

    fig.text(0.5, -0.03, summary, ha="center", fontsize=8.5,
             bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.7))

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Plot: Seasonal Trend ──────────────────────────────────────────────────────

def plot_seasonal_trends(games: pd.DataFrame, out_path: Path) -> None:
    """Mean/std of spread and total over time, colored by season_type."""
    if "season" not in games.columns or games["season"].isna().all():
        return

    agg = (
        games.groupby(["season", "season_type"])
        .agg(
            spread_mean=("spread", "mean"),
            spread_std=("spread", "std"),
            total_mean=("total", "mean"),
            total_std=("total", "std"),
            n=("total", "count"),
        )
        .reset_index()
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    fig.suptitle("Seasonal Trends: Spread and Total", fontsize=13, fontweight="bold")

    season_order = sorted(agg["season"].unique())
    x = {s: i for i, s in enumerate(season_order)}
    agg["x"] = agg["season"].map(x)

    for stype, color in [("Regular", "#2563eb"), ("Playoffs", "#dc2626")]:
        sub = agg[agg["season_type"] == stype]
        if sub.empty:
            continue
        for ax, col, label in [
            (axes[0], "spread", "Spread"),
            (axes[1], "total",  "Total"),
        ]:
            ax.errorbar(
                sub["x"], sub[f"{col}_mean"], yerr=sub[f"{col}_std"],
                fmt="-o", color=color, markersize=4, linewidth=1.5,
                label=stype, capsize=2, alpha=0.8,
            )

    for ax, label in [(axes[0], "Spread (home − away pts)"),
                      (axes[1], "Total Points")]:
        ax.set_xticks(list(x.values()))
        ax.set_xticklabels(season_order, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel(label)
        ax.set_title(f"{label} by Season")
        ax.legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season-type", choices=["Regular", "Playoffs"],
                        default=None, help="Filter to one season type (default: both)")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parent / "eda_plots",
                        help="Directory for output plots")
    parser.add_argument("--total-range", type=int, nargs=2, default=[160, 280],
                        metavar=("LO", "HI"),
                        help="Range filter for exact-total analysis (default 160 280)")
    args = parser.parse_args()

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading game scores from {DATA_DIR} ...")
    games = load_game_scores(season_type_filter=args.season_type)
    print(f"  {len(games):,} games loaded  "
          f"(Regular: {(games['season_type']=='Regular').sum():,}, "
          f"Playoffs: {(games['season_type']=='Playoffs').sum():,})")

    # ── Spread ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 64)
    print("  SPREAD  (home_pts − away_pts)")
    print("═" * 64)
    spread = games["spread"].dropna().values.astype(float)
    fits_spread = fit_all(spread)
    print_fit_table(fits_spread, "Spread")
    run_normality_tests(spread, "Spread")
    plot_continuous(spread, "Spread (home − away pts)",
                    out_dir / "spread_distribution.png", "#2563eb")

    # ── Total ─────────────────────────────────────────────────────────────────
    print("\n" + "═" * 64)
    print("  TOTAL  (home_pts + away_pts)")
    print("═" * 64)
    total = games["total"].dropna().values.astype(float)
    fits_total = fit_all(total)
    print_fit_table(fits_total, "Total")
    run_normality_tests(total, "Total")
    plot_continuous(total, "Total Points (home + away)",
                    out_dir / "total_distribution.png", "#16a34a")

    # ── Exact Totals (discrete) ───────────────────────────────────────────────
    lo, hi = args.total_range
    print("\n" + "═" * 64)
    print(f"  EXACT TOTALS  (discrete, range [{lo}, {hi}])")
    print("═" * 64)
    exact = total[(total >= lo) & (total <= hi)]
    print(f"  {len(exact):,} games in range  "
          f"({100*len(exact)/len(total):.1f}% of all games)")
    plot_exact_total(exact, out_dir / "exact_total_distribution.png")
    run_normality_tests(exact, "Exact Total (continuous view)")

    # ── Per-season-type breakdown ─────────────────────────────────────────────
    print("\n" + "═" * 64)
    print("  BREAKDOWN BY SEASON TYPE")
    print("═" * 64)
    for stype in ("Regular", "Playoffs"):
        sub = games[games["season_type"] == stype]
        if len(sub) < 50:
            continue
        s = sub["spread"].dropna().values
        t = sub["total"].dropna().values
        print(f"\n  {stype} ({len(sub):,} games)")
        print(f"    Spread  mean={s.mean():.2f}  std={s.std():.2f}  "
              f"skew={stats.skew(s):.3f}  excess_kurt={stats.kurtosis(s):.3f}")
        print(f"    Total   mean={t.mean():.2f}  std={t.std():.2f}  "
              f"skew={stats.skew(t):.3f}  excess_kurt={stats.kurtosis(t):.3f}")

        # Per-type plots when not already filtered
        if args.season_type is None:
            plot_continuous(
                s, f"Spread — {stype}",
                out_dir / f"spread_{stype.lower()}.png",
                "#2563eb" if stype == "Regular" else "#dc2626",
            )
            plot_continuous(
                t, f"Total — {stype}",
                out_dir / f"total_{stype.lower()}.png",
                "#16a34a" if stype == "Regular" else "#d97706",
            )

    # ── Seasonal trends ───────────────────────────────────────────────────────
    print("\n  Generating seasonal trend plot...")
    plot_seasonal_trends(games, out_dir / "seasonal_trends.png")

    # ── Summary recommendation ────────────────────────────────────────────────
    print("\n" + "═" * 64)
    print("  SUMMARY / MODELING RECOMMENDATIONS")
    print("═" * 64)

    best_spread = min(fits_spread, key=lambda k: fits_spread[k]["aic"])
    best_total  = min(fits_total,  key=lambda k: fits_total[k]["aic"])

    _, sw_p_spread = shapiro(spread[:5000] if len(spread) > 5000 else spread)
    _, sw_p_total  = shapiro(total[:5000]  if len(total)  > 5000 else total)

    print(f"\n  Spread:  best-fit = {best_spread}  "
          f"(Shapiro-Wilk p={sw_p_spread:.4e}, {'not normal' if sw_p_spread < 0.05 else 'approx normal'})")
    print(f"  Total:   best-fit = {best_total}  "
          f"(Shapiro-Wilk p={sw_p_total:.4e}, {'not normal' if sw_p_total < 0.05 else 'approx normal'})")
    print(f"\n  Market model guidance:")
    print(f"    Spread/total  → regression → predicted (mean, std) → 1 - cdf(X, mean, std)")
    print(f"    Exact total   → multinomial classifier on 1-pt bins OR")
    print(f"                    normal CDF difference: P(total=X) ≈ norm.cdf(X+0.5) - norm.cdf(X-0.5)")
    print(f"\n  All plots saved to: {out_dir}")
    print("═" * 64)


if __name__ == "__main__":
    main()
