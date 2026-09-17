import sqlite3
import os
import json
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# On Render, DATABASE_PATH points at a file on the mounted persistent disk
# (e.g. /var/data/aster.db) so the database survives redeploys and restarts.
# Locally, it falls back to a file alongside the project.
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "aster.db"))
SEED_PATH = os.path.join(BASE_DIR, "seed_data.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reg TEXT NOT NULL UNIQUE,
  depot TEXT NOT NULL,
  category TEXT NOT NULL,
  make TEXT,
  model TEXT,
  value REAL,
  year INTEGER,
  gvw INTEGER,
  cover_start TEXT NOT NULL,
  cover_end TEXT,
  status TEXT NOT NULL DEFAULT 'On cover',
  notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT NOT NULL UNIQUE,
  depot TEXT NOT NULL,
  vehicle_type TEXT,
  loss_date TEXT NOT NULL,
  cause TEXT NOT NULL,
  status TEXT NOT NULL,
  fault TEXT,
  own_damage TEXT,
  paid REAL DEFAULT 0,
  reserve REAL DEFAULT 0,
  incurred REAL DEFAULT 0,
  days_open INTEGER DEFAULT 0,
  policy_year TEXT,
  closed INTEGER DEFAULT 0,
  close_date TEXT,
  driver_age_band TEXT,
  notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS covers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  insurer TEXT,
  policy_number TEXT,
  period_start TEXT,
  period_end TEXT,
  premium REAL,
  status TEXT,
  is_primary INTEGER DEFAULT 0,
  documents TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force_reseed=False):
    fresh = not os.path.exists(DB_PATH)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) c FROM vehicles").fetchone()["c"]
    if fresh or force_reseed or count == 0:
        seed(conn)
    conn.close()


def seed(conn):
    if not os.path.exists(SEED_PATH):
        return
    with open(SEED_PATH) as f:
        data = json.load(f)

    conn.execute("DELETE FROM vehicles")
    conn.execute("DELETE FROM claims")
    conn.execute("DELETE FROM covers")
    conn.execute("DELETE FROM meta")

    for v in data.get("fleet_vehicles", []):
        conn.execute(
            """INSERT OR IGNORE INTO vehicles
               (reg, depot, category, make, model, value, year, gvw, cover_start, cover_end, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                v["reg"], v["depot"], v["type"], v.get("make"), v.get("model", v.get("model")),
                v.get("value"), v.get("year"), v.get("gvw"),
                v["cover_start"], v.get("cover_end"), v.get("status", "On cover"), v.get("notes"),
            ),
        )

    for c in data.get("register", []):
        conn.execute(
            """INSERT OR IGNORE INTO claims
               (ref, depot, vehicle_type, loss_date, cause, status, fault, own_damage,
                paid, reserve, incurred, days_open, policy_year, closed, close_date, driver_age_band)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                c["ref"], c["depot"], c.get("vehicle"), c["loss_date"], c["cause"], c["status"],
                c.get("fault"), c.get("own_damage"), c.get("paid", 0), c.get("reserve", 0),
                c.get("incurred", 0), c.get("days_open", 0), c.get("policy_year"),
                1 if c.get("closed") else 0, c.get("close_date"), c.get("driver_age_band"),
            ),
        )

    for cov in data.get("covers", []):
        conn.execute(
            """INSERT OR IGNORE INTO covers
               (id, name, insurer, policy_number, period_start, period_end, premium, status, is_primary, documents)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                cov["id"], cov["name"], cov.get("insurer"), cov.get("policy_number"),
                cov.get("period_start"), cov.get("period_end"), cov.get("premium"),
                cov.get("status"), 1 if cov.get("primary") else 0,
                json.dumps(cov.get("documents", [])),
            ),
        )

    meta = data.get("meta", {})
    for k, v in meta.items():
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (k, json.dumps(v) if not isinstance(v, str) else v),
        )
    # loss ratio target/history come from the mockup's static analytics block;
    # store as JSON blobs under meta so pages can reuse them until claims volume
    # is enough to compute them from real data alone.
    for key in ("loss_ratio", "kpi"):
        if key in data:
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, json.dumps(data[key])),
            )

    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]
