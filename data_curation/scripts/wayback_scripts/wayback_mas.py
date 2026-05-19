import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================================================
# CONFIG
# =========================================================

DOMAIN = "masseyratings.com/*"

OUT = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data/output/massey_wayback2")
OUT.mkdir(parents=True, exist_ok=True)

CDX = "https://web.archive.org/cdx/search/cdx"

CACHE_DIR = OUT / "cdx_cache"
CACHE_DIR.mkdir(exist_ok=True)

MANIFEST = OUT / "manifest.csv"

# =========================================================
# SESSION
# =========================================================

session = requests.Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (archive-miner/2.0)"}
)

retry = Retry(
    total=5,
    backoff_factor=1.2,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
)

session.mount("https://", HTTPAdapter(max_retries=retry))
session.mount("http://", HTTPAdapter(max_retries=retry))


# =========================================================
# LOGGING
# =========================================================

def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg, flush=True)


# =========================================================
# CDX FETCH (ROBUST)
# =========================================================

def fetch_cdx(domain):
    params = {
        "url": domain,
        "matchType": "prefix",
        "output": "json",
        "fl": "timestamp,original,statuscode,digest,mimetype",
        "collapse": "digest",
        "limit": 5000
    }

    rows = []
    resume = None

    while True:
        if resume:
            params["resumeKey"] = resume

        log(f"[CDX] requesting page (resume={bool(resume)})")

        try:
            r = session.get(CDX, params=params, timeout=(10, 60))
        except Exception as e:
            log(f"[CDX ERROR] {e}")
            time.sleep(5)
            continue

        if r.status_code == 503:
            log("[CDX] 503 backoff")
            time.sleep(5)
            continue

        data = r.json()

        if not isinstance(data, list) or len(data) <= 1:
            break

        rows.extend(data[1:])

        meta = data[0] if isinstance(data[0], dict) else {}
        resume = meta.get("resumeKey")

        if not resume:
            break

        time.sleep(0.3)

    log(f"[CDX COMPLETE] rows={len(rows)}")
    return rows


# =========================================================
# URL CLUSTERING (CRITICAL FIX)
# =========================================================

def cluster_urls(rows):
    clusters = defaultdict(list)

    for r in rows:
        if len(r) < 2:
            continue

        ts, original = r[0], r[1]

        path = original.split("masseyratings.com")[-1]

        # normalize structure
        if "rate" in path:
            key = "rate_family"
        elif "nba" in path:
            key = "nba_family"
        else:
            key = "other"

        clusters[key].append((ts, original, r))

    return clusters


# =========================================================
# CONTENT VALIDATION (AFTER CLUSTERING)
# =========================================================

def is_valid_ratings(html):
    t = html.lower()

    bad = ["please wait", "loading", "javascript required"]
    if any(b in t for b in bad):
        return False

    good = ["rating", "offense", "defense", "massey"]

    return sum(g in t for g in good) >= 2


# =========================================================
# DOWNLOAD SNAPSHOTS
# =========================================================

def fetch_snapshot(ts, url):
    return f"https://web.archive.org/web/{ts}id_/{url}"


def download(url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.text


# =========================================================
# MAIN PIPELINE
# =========================================================

log("STARTING FULL DOMAIN MINING")

rows = fetch_cdx(DOMAIN)

clusters = cluster_urls(rows)

log(f"CLUSTERS FOUND: {list(clusters.keys())}")

captures = []

for cluster_name, items in clusters.items():

    log(f"[CLUSTER] {cluster_name} size={len(items)}")

    for ts, original, raw in items:

        archive_url = fetch_snapshot(ts, original)

        try:
            html = download(archive_url)
        except Exception:
            continue

        if not is_valid_ratings(html):
            continue

        sha = hashlib.sha256(html.encode("utf-8", "ignore")).hexdigest()

        captures.append({
            "ts": ts,
            "url": original,
            "cluster": cluster_name,
            "sha": sha,
        })

        time.sleep(0.2)


# =========================================================
# SAVE OUTPUT
# =========================================================

captures.sort(key=lambda x: x["ts"])

with MANIFEST.open("w", newline="") as f:
    w = csv.writer(f)

    w.writerow(["timestamp", "url", "cluster", "sha256"])

    for c in captures:
        w.writerow([c["ts"], c["url"], c["cluster"], c["sha"]])

log(f"DONE: {len(captures)} valid snapshots saved")