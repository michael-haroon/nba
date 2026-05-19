import csv
import json
import time
import random
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================================================
# CONFIG
# =========================================================
TARGET_URL = "https://www.espn.com/nba/bpi"
OUT_DIR = Path("./data/output/espn_bpi_wayback")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CDX_URL = "https://web.archive.org/cdx/search/cdx"
MANIFEST_PATH = OUT_DIR / "bpi_manifest.csv"

# =========================================================
# SESSION SETUP
# =========================================================
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (archive-bot/1.0)"})

retries = Retry(
    total=5,
    backoff_factor=1.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"])
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg)

def is_valid_bpi(html):
    """Checks if the snapshot actually contains the BPI table data."""
    t = html.lower()
    # ESPN often serves 'stub' pages that wait for JS. We want the data.
    indicators = ["bpi", "playoff odds", "rank", "team"]
    found = sum(1 for word in indicators if word in t)
    return found >= 3 and "loading..." not in t[:2000]

# =========================================================
# MAIN PIPELINE
# =========================================================
log(f"Fetching CDX index for {TARGET_URL}...")

params = {
    "url": TARGET_URL,
    "matchType": "exact",
    "output": "json",
    "fl": "timestamp,original,digest",
    "filter": "statuscode:200",
    "collapse": "digest" # Only get unique content snapshots
}

r = session.get(CDX_URL, params=params, timeout=60)
if r.status_code != 200:
    raise RuntimeError(f"CDX request failed: {r.status_code}")

rows = r.json()
if len(rows) <= 1:
    log("No snapshots found.")
    exit()

header, *snapshots = rows
log(f"Found {len(snapshots)} unique snapshots. Starting download...")

with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "archive_url", "file_saved"])

    for ts, original, digest in snapshots:
        # Use 'id_' to get the raw content without the Wayback toolbar
        archive_url = f"https://web.archive.org/web/{ts}id_/{original}"
        file_path = OUT_DIR / f"bpi_{ts}.html"

        if file_path.exists():
            continue

        try:
            resp = session.get(archive_url, timeout=30)
            if resp.status_code == 200 and is_valid_bpi(resp.text):
                file_path.write_text(resp.text, encoding="utf-8", errors="ignore")
                writer.writerow([ts, archive_url, file_path.name])
                log(f"Saved: {ts}")
            else:
                log(f"Skipped (invalid content): {ts}")
        except Exception as e:
            log(f"Error downloading {ts}: {e}")

        time.sleep(1.0) # Be kind to Archive.org

log("Curation complete.")