"""
parse_sag_html.py

Parses Sagarin NBA rating HTML snapshots (from Wayback Machine scrapes) into a
clean parquet/CSV.

Core output per row: sag_rank, team, sag_rating, as_of_date, home_advantage.

Three sub-component columns (comp1/comp2/comp3) capture whatever rating
components the page shows in that era — their labels vary (PREDICTOR,
GOLDEN_MEAN, PURE_ELO, DIMIN_CURVE, RECENT, ELO_SCORE) but the core columns
are always correct regardless of era.

Usage:
    python parse_sag_html.py                         # default paths
    python parse_sag_html.py --html-dir /path/to/html --out /path/to/out.parquet
    python parse_sag_html.py --csv                   # emit CSV instead of parquet
    python parse_sag_html.py --workers 8             # parallel workers (default: cpu count)
"""

import argparse
import re
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# 3-column sub-metric format (all eras with three pipe-separated components):
#   <rank>  <Team>  =  <rating>  W  L  schedl(rank)  v10W v10L | v16W v16L | c1 c1r | c2 c2r | c3 c3r
_3COL = re.compile(
    r"^\s{0,4}(\d{1,2})\s{2,}(.+?)\s{2,}=[  ]+([\d.]+)\s+"
    r"(\d+)\s+(\d+)\s+"
    r"([\d.]+)\(\s*(\d+)\)\s+"
    r"(\d+)\s+(\d+)\s+\|\s+"
    r"(\d+)\s+(\d+)\s+\|"
    r"\s+([\d.]+)\s+(\d+)\s*"
    r"\|\s*([\d.]+)\s+(\d+)\s*"
    r"\|\s*([\d.]+)\s+(\d+)",
    re.MULTILINE,
)

# 2-column sub-metric format (pre-~2013, ELO_SCORE | PREDICTOR only):
_2COL = re.compile(
    r"^\s{0,4}(\d{1,2})\s{2,}(.+?)\s{2,}=[  ]+([\d.]+)\s+"
    r"(\d+)\s+(\d+)\s+"
    r"([\d.]+)\(\s*(\d+)\)\s+"
    r"(\d+)\s+(\d+)\s+\|\s+"
    r"(\d+)\s+(\d+)\s+\|"
    r"\s+([\d.]+)\s+(\d+)\s*"
    r"\|\s*([\d.]+)\s+(\d+)",
    re.MULTILINE,
)

_DATE_LINE = re.compile(
    r"(?:Final\s+)?NBA\s+\d{4}-\d{4}\s+(?:ratings?\s+through\s+(?:results?|games?)\s+of|through\s+games?\s+of)\s+"
    r"(\d{4}\s+[A-Za-z]+\s+\d{1,2})",
    re.IGNORECASE,
)


_HOME_ADV = re.compile(r"HOME ADVANTAGE=\[\s*([\d.]+)\s*\]")

# Snapshot type detection
_FINAL_LINE = re.compile(r"Final\s+NBA\s+\d{4}-\d{4}", re.IGNORECASE)
_STARTING_LINE = re.compile(r"NBA\s+\d{4}-\d{4}\s+Starting\s+Ratings", re.IGNORECASE)

# Column-header keywords used to label comp1/comp2/comp3.
# We scan each keyword's position in the header to assign labels in order.
_COMP_KEYWORDS = [
    ("PREDICTOR",   "predictor"),
    ("GOLDEN_MEAN", "golden_mean"),
    ("PURE_POINTS", "golden_mean"),   # alias
    ("RECENT",      "recent"),
    ("PURE_ELO",    "pure_elo"),
    ("ELO_SCORE",   "elo_score"),
    ("DIMIN",       "dimin_curve"),
]


def _comp_labels(header_text: str) -> tuple[str, str, str]:
    """
    Return (label1, label2, label3) for the three sub-metric columns based on
    what keywords appear in the header line, in left-to-right order.
    Falls back to generic names if fewer than 3 are found.
    """
    t = header_text.upper()
    found = []
    for keyword, label in _COMP_KEYWORDS:
        pos = t.find(keyword)
        if pos != -1:
            found.append((pos, label))
    found.sort()
    labels = [label for _, label in found]
    # pad to 3 with generic names
    while len(labels) < 3:
        labels.append(f"comp{len(labels) + 1}")
    return labels[0], labels[1], labels[2]


# ---------------------------------------------------------------------------
# Per-file parser
# ---------------------------------------------------------------------------

def parse_sagarin_file(html_path: Path) -> list[dict]:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    page = soup.find("article", {"data-page": "sagarin"})
    if page is None:
        # Some early 2013-14 files need lxml
        soup = BeautifulSoup(html, "lxml")
        page = soup.find("article", {"data-page": "sagarin"})
    if not page:
        log.warning("%s: no sagarin article element found", html_path.name)
        return []

    as_of_date = None
    home_adv = None
    snapshot_type = "regular"
    rows: dict[int, dict] = {}  # sag_rank -> row; first occurrence wins

    for pre in page.find_all("pre"):
        for br in pre.find_all("br"):
            br.replace_with("\n")
        text = pre.get_text().replace(" ", " ").replace("&nbsp", " ")

        if snapshot_type == "regular":
            if _FINAL_LINE.search(text):
                snapshot_type = "final"
            elif _STARTING_LINE.search(text):
                snapshot_type = "starting"

        if as_of_date is None:
            m = _DATE_LINE.search(text)
            if m:
                raw = re.sub(r"\s+", " ", m.group(1)).strip()
                try:
                    as_of_date = pd.to_datetime(raw, format="%Y %B %d").date()
                except Exception:
                    pass

        if home_adv is None:
            m = _HOME_ADV.search(text)
            if m:
                home_adv = float(m.group(1))

        l1, l2, l3 = _comp_labels(text)

        # 3-component rows
        for m in _3COL.finditer(text):
            rank = int(m.group(1))
            if rank in rows:
                continue
            rows[rank] = {
                "sag_rank":      rank,
                "team":          m.group(2).strip(),
                "sag_rating":    float(m.group(3)),
                "wins":          int(m.group(4)),
                "losses":        int(m.group(5)),
                "schedl":        float(m.group(6)),
                "schedl_rank":   int(m.group(7)),
                l1:              float(m.group(12)),
                f"{l1}_rank":    int(m.group(13)),
                l2:              float(m.group(14)),
                f"{l2}_rank":    int(m.group(15)),
                l3:              float(m.group(16)),
                f"{l3}_rank":    int(m.group(17)),
            }

        # 2-component rows (only if nothing matched yet)
        if not rows:
            for m in _2COL.finditer(text):
                rank = int(m.group(1))
                if rank in rows:
                    continue
                rows[rank] = {
                    "sag_rank":    rank,
                    "team":        m.group(2).strip(),
                    "sag_rating":  float(m.group(3)),
                    "wins":        int(m.group(4)),
                    "losses":      int(m.group(5)),
                    "schedl":      float(m.group(6)),
                    "schedl_rank": int(m.group(7)),
                    l1:            float(m.group(12)),
                    f"{l1}_rank":  int(m.group(13)),
                    l2:            float(m.group(14)),
                    f"{l2}_rank":  int(m.group(15)),
                }

    if not rows:
        log.warning("%s: no team rows parsed", html_path.name)
        return []

    result = []
    for rank in sorted(rows):
        row = rows[rank]
        row["as_of_date"] = as_of_date
        row["snapshot_type"] = snapshot_type
        row["home_advantage"] = home_adv
        row["source_file"] = html_path.name
        result.append(row)

    return result


def _safe_parse(html_path: Path) -> tuple[list[dict], str | None]:
    """Wrapper for parallel use — returns (rows, error_str_or_None)."""
    try:
        return parse_sagarin_file(html_path), None
    except Exception as e:
        return [], str(e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Parse Sagarin NBA HTML snapshots")
    parser.add_argument(
        "--html-dir",
        default="../data/unscraped_sites/usatoday_sag/html/",
    )
    parser.add_argument(
        "--out",
        default="../data/sag_ratings_parsed.parquet",
    )
    parser.add_argument("--csv", action="store_true")
    parser.add_argument(
        "--workers",
        type=int,
        default=cpu_count(),
        help="Parallel worker processes (default: cpu count)",
    )
    args = parser.parse_args()

    html_dir = Path(args.html_dir)
    if not html_dir.is_dir():
        log.error("html-dir does not exist: %s", html_dir.resolve())
        return

    html_files = sorted(html_dir.glob("*.html"))
    log.info("Found %d HTML files in %s", len(html_files), html_dir)

    all_rows = []
    failed = 0

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_safe_parse, f): f for f in html_files}
        for future in as_completed(futures):
            rows, err = future.result()
            if err:
                log.warning("Error parsing %s: %s", futures[future].name, err)
                failed += 1
            else:
                all_rows.extend(rows)

    if not all_rows:
        log.error("No rows parsed — check html-dir path")
        return

    df = pd.DataFrame(all_rows)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    df = df.sort_values(["as_of_date", "sag_rank"]).reset_index(drop=True)

    out_path = Path(args.out)
    if args.csv and out_path.suffix == ".parquet":
        out_path = out_path.with_suffix(".csv")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".csv" or args.csv:
        df.to_csv(out_path, index=False)
    else:
        df.to_parquet(out_path, index=False)

    log.info(
        "Wrote %d rows (%d snapshots, %d files failed) → %s",
        len(df),
        df["as_of_date"].nunique(),
        failed,
        out_path.resolve(),
    )

    print("\nColumn dtypes:")
    print(df.dtypes.to_string())
    print("\nSample (first 5 rows):")
    print(df[["sag_rank", "team", "sag_rating", "as_of_date"]].head().to_string(index=False))
    print(f"\nDate range: {df['as_of_date'].min().date()} → {df['as_of_date'].max().date()}")
    print(f"Unique teams: {df['team'].nunique()}")
    print(f"Unique snapshots: {df['as_of_date'].nunique()}")


if __name__ == "__main__":
    main()
