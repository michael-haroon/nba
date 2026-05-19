import csv
import json
import random
import time
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TARGET = "http://www.usatoday.com/sports/nba/sagarin/"
OUT = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data_curation/data/unscraped_sites/usatoday_sag")
OUT.mkdir(parents=True, exist_ok=True)

INDEX_FILE = OUT / "index.csv"
CDX = "https://web.archive.org/cdx/search/cdx"
CACHE = OUT / "cdx.json"

# --- Setup Session ---
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; archive-bot/1.0)"})
retry = Retry(total=8, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))
session.mount("https://", HTTPAdapter(max_retries=retry))

# --- Load CDX Data ---
if CACHE.exists():
    rows = json.loads(CACHE.read_text(encoding="utf-8"))
else:
    params = {"url": TARGET, "matchType": "exact", "output": "json", 
              "fl": "timestamp,original,mimetype,statuscode,digest", 
              "filter": "statuscode:200", "collapse": "digest"}
    r = session.get(CDX, params=params, timeout=60)
    r.raise_for_status()
    rows = r.json()
    CACHE.write_text(json.dumps(rows), encoding="utf-8")

header, *captures = rows

# --- Auto-Resume Logic ---
last_ts = None
if INDEX_FILE.exists():
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        lines = list(csv.reader(f))
        if len(lines) > 1:
            last_ts = lines[-1][0] # Get timestamp from last row

# --- Processing ---
# Use 'a' to append if file exists, otherwise 'w' to start fresh
mode = 'a' if INDEX_FILE.exists() else 'w'
with open(INDEX_FILE, mode, newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if mode == 'w':
        w.writerow(["timestamp", "original", "mimetype", "statuscode", "digest", "archive_url", "saved_file"])

    skipping = True if last_ts else False
    
    for ts, original, mimetype, statuscode, digest in captures:
        # Resume logic: skip until we find the next record after last_ts
        if skipping:
            if ts == last_ts:
                skipping = False
            continue

        archive_url = f"https://web.archive.org/web/{ts}id_/{original}"
        file_path = OUT / f"{ts}.html"

        if not file_path.exists():
            print(f"Downloading {ts}...")
            for attempt in range(8):
                try:
                    rr = session.get(archive_url, timeout=60)
                    if rr.status_code == 200:
                        file_path.write_text(rr.text, encoding="utf-8", errors="ignore")
                        break
                    elif rr.status_code in (429, 500, 502, 503, 504):
                        time.sleep(min(60, (2 ** attempt) + random.random()))
                    else:
                        break
                except Exception as e:
                    print(f"Attempt {attempt} failed: {e}")
                    time.sleep(5)

        w.writerow([ts, original, mimetype, statuscode, digest, archive_url, str(file_path)])
        f.flush() # Force write to disk so we don't lose progress on crash
        time.sleep(0.5)