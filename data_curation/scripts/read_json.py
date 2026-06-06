import os
import glob
import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = "/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/logs"
os.makedirs(LOG_DIR, exist_ok=True)

run_id  = time.strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"crude_ingest_{run_id}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(),          # also print to terminal
    ]
)
log = logging.getLogger("ingest")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = "/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data"
PBP_DIR = os.path.join(BASE, "raw_payloads/pbp")
SUM_DIR = os.path.join(BASE, "raw_payloads/summary")

OUTPUTS = {
    "pbp":       os.path.join(BASE, "CRUDEPlayByPlay.parquet"),
    "summary":   os.path.join(BASE, "CRUDESummary.parquet"),
    "officials": os.path.join(BASE, "CRUDESummaryOfficials.parquet"),
    "broadcast": os.path.join(BASE, "CRUDESummaryBroadcasters.parquet"),
    "players":   os.path.join(BASE, "CRUDESummaryPlayers.parquet"),
    "last_five": os.path.join(BASE, "CRUDESummaryLastFive.parquet"),
}

BROADCASTER_TYPES = [
    "nationalBroadcasters", "nationalRadioBroadcasters", "nationalOttBroadcasters",
    "homeTvBroadcasters",   "homeRadioBroadcasters",     "homeOttBroadcasters",
    "awayTvBroadcasters",   "awayRadioBroadcasters",     "awayOttBroadcasters",
]

IO_WORKERS  = 6
FLUSH_EVERY = 200

# ── JSON ──────────────────────────────────────────────────────────────────────
def load_json(path):
    with open(path, "rb") as f:
        raw = f.read()
    data = orjson.loads(raw)
    return orjson.loads(data) if isinstance(data, str) else data

# ── Flatten ───────────────────────────────────────────────────────────────────
def flatten_dict(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_dict(v, key))
        elif not isinstance(v, list):
            out[key] = v
    return out

# ── Parquet sink ──────────────────────────────────────────────────────────────
class ParquetSink:
    def __init__(self, path):
        self.path        = path
        self.writer      = None
        self.buf         = []
        self.count       = 0
        self.flush_count = 0
        self.flush_time  = 0.0

    def add(self, rows):
        self.buf.extend(rows)
        if len(self.buf) >= FLUSH_EVERY:
            self._flush()

    def _flush(self):
        if not self.buf:
            return
        t0    = time.perf_counter()
        table = pa.Table.from_pylist(self.buf)

        if self.writer is None:
            self.writer = pq.ParquetWriter(
                self.path, table.schema, compression="snappy")
        elif table.schema != self.writer.schema:
            merged = pa.unify_schemas([self.writer.schema, table.schema])
            # null-fill table for any columns in the target schema it's missing
            for field in merged:
                if table.schema.get_field_index(field.name) == -1:
                    table = table.append_column(
                        field, pa.array([None] * len(table), type=field.type))
            if merged != self.writer.schema:
                log.warning(f"    [{os.path.basename(self.path)}] schema expanded to "
                            f"{len(merged)} cols (new: {set(merged.names) - set(self.writer.schema.names)})")
                self.writer.close()
                self.writer = pq.ParquetWriter(self.path, merged, compression="snappy")
            table = table.select(self.writer.schema.names).cast(self.writer.schema)

        self.writer.write_table(table)
        elapsed           = time.perf_counter() - t0
        self.flush_time  += elapsed
        self.flush_count += 1
        self.count       += len(self.buf)
        log.debug(f"    [{os.path.basename(self.path)}] flush #{self.flush_count}: "
                f"{len(self.buf)} rows in {elapsed*1000:.1f}ms  "
                f"(total {self.count:,} rows, {self.flush_time:.2f}s in writes)")
        self.buf.clear()

    def close(self):
        self._flush()
        if self.writer:
            self.writer.close()
        mb = os.path.getsize(self.path) / 1e6 if os.path.exists(self.path) else 0
        log.info(f"  CLOSED {os.path.basename(self.path)}: "
                 f"{self.count:,} rows  {mb:.1f} MB  "
                 f"({self.flush_count} flushes, {self.flush_time:.2f}s in parquet writes)")

# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_pbp(path):
    data = load_json(path)
    game = data["game"]
    gid  = game["gameId"]
    vid  = game.get("videoAvailable")
    return {"pbp": [{"gameId": gid, "videoAvailable_game": vid, **a}
                    for a in game.get("actions", [])]}

def parse_summary(path):
    data = load_json(path)
    bss  = data["boxScoreSummary"]
    gid  = bss["gameId"]

    skip = {"officials","broadcasters","homeTeam","awayTeam",
            "lastFiveMeetings","pregameCharts","postgameCharts"}
    flat = {"gameId": gid}
    for k, v in bss.items():
        if k in skip:
            continue
        flat.update(flatten_dict({k: v}) if isinstance(v, dict) else {k: v})

    for chart in ("pregameCharts", "postgameCharts"):
        for side in ("homeTeam", "awayTeam"):
            flat.update(flatten_dict(
                bss.get(chart, {}).get(side, {}), f"{chart}.{side}"))

    for side in ("homeTeam", "awayTeam"):
        team = bss.get(side, {})
        for k, v in team.items():
            if k in ("players","periods","inactives","statistics"):
                continue
            flat[f"{side}.{k}"] = v
        for p in team.get("periods", []):
            n = p.get("period")
            flat[f"{side}.period_{n}_score"] = p.get("score")
            flat[f"{side}.period_{n}_type"]  = p.get("periodType")

    officials = [{"gameId": gid, **o} for o in bss.get("officials", [])]

    broadcasts = []
    for btype in BROADCASTER_TYPES:
        for b in bss.get("broadcasters", {}).get(btype, []):
            broadcasts.append({"gameId": gid, "broadcast_type": btype, **b})

    players = []
    for side in ("homeTeam", "awayTeam"):
        team = bss.get(side, {})
        meta = {"gameId": gid, "side": side,
                "teamId": team.get("teamId"), "teamTricode": team.get("teamTricode")}
        for p in team.get("players", []):
            players.append({**meta, "inactive": False, **p})
        for p in team.get("inactives", []):
            players.append({**meta, "inactive": True, **p})

    last_five = []
    for m in bss.get("lastFiveMeetings", {}).get("meetings", []):
        row = {"gameId": gid}
        for k, v in m.items():
            if k in ("homeTeam", "awayTeam"):
                for sk, sv in v.items():
                    row[f"{k}.{sk}"] = sv
            else:
                row[k] = v
        last_five.append(row)

    return {"summary": [flat], "officials": officials,
            "broadcast": broadcasts, "players": players,
            "last_five": last_five}

# ── Pipeline ──────────────────────────────────────────────────────────────────
def run_pipeline(label, files, parser, output_keys):
    log.info(f"[{label}] starting — {len(files):,} files, {IO_WORKERS} workers, "
             f"flush_every={FLUSH_EVERY}")
    sinks   = {k: ParquetSink(OUTPUTS[k]) for k in output_keys}
    skipped = []
    done    = 0
    total   = len(files)
    t_start = time.perf_counter()
    t_last  = t_start

    with ThreadPoolExecutor(max_workers=IO_WORKERS) as ex:
        window_size = IO_WORKERS + 2
        it          = iter(files)
        futures     = {}

        for path in list(it)[:window_size]:
            futures[ex.submit(parser, path)] = path
        remaining = iter(files[window_size:])

        while futures:
            done_future = next(as_completed(futures))
            path        = futures.pop(done_future)

            try:
                result = done_future.result()
                for key, rows in result.items():
                    if rows:
                        sinks[key].add(rows)
            except Exception as e:
                skipped.append((os.path.basename(path), str(e)))
                log.warning(f"  [{label}] SKIP {os.path.basename(path)}: {e}")

            done += 1

            # progress every 1000 files
            if done % 1000 == 0:
                now      = time.perf_counter()
                chunk_s  = now - t_last
                total_s  = now - t_start
                rate     = 1000 / chunk_s
                eta      = (total - done) / rate
                t_last   = now
                log.info(f"  [{label}] {done:,}/{total:,}  "
                         f"rate={rate:.0f} files/s  "
                         f"elapsed={total_s:.1f}s  eta={eta:.1f}s")

            try:
                nxt = next(remaining)
                futures[ex.submit(parser, nxt)] = nxt
            except StopIteration:
                pass

    for s in sinks.values():
        s.close()

    elapsed = time.perf_counter() - t_start
    log.info(f"[{label}] finished in {elapsed:.1f}s  "
             f"skipped={len(skipped)}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info(f"=== crude ingest start  run_id={run_id} ===")
    log.info(f"log → {log_path}")
    t0 = time.perf_counter()

    # pbp_files = [f for f in glob.glob(os.path.join(PBP_DIR, "*.json"))
    #              if os.path.getsize(f) > 0]
    sum_files = [f for f in glob.glob(os.path.join(SUM_DIR, "*.json"))
                 if os.path.getsize(f) > 0]

    # log.info(f"PBP files: {len(pbp_files):,}  |  Summary files: {len(sum_files):,}")

    # run_pipeline("pbp",     pbp_files, parse_pbp,     ["pbp"])
    run_pipeline("summary", sum_files, parse_summary,
                 ["summary", "officials", "broadcast", "players", "last_five"])

    log.info(f"=== all done in {time.perf_counter() - t0:.1f}s ===")