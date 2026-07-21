"""SQLite storage for run results and batch fingerprints."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from solm.config import DATA_DIR

DB_PATH = DATA_DIR / "state.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    date TEXT NOT NULL,
    ts TEXT NOT NULL,
    model TEXT NOT NULL,
    task TEXT NOT NULL,
    trial INTEGER NOT NULL,
    status TEXT NOT NULL,           -- ok | error | timeout | infra
    score REAL NOT NULL,
    duration_s REAL,
    turns INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    laziness_flags INTEGER DEFAULT 0,
    laziness_notes TEXT DEFAULT '',
    checks_json TEXT DEFAULT '{}',
    workspace TEXT DEFAULT '',
    error TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_runs_date_model ON runs(date, model);
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    ts TEXT NOT NULL,
    fingerprint_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS gut_log (
    date TEXT PRIMARY KEY,
    label TEXT NOT NULL,            -- fine | off
    ts TEXT NOT NULL
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_run(conn: sqlite3.Connection, row: dict) -> None:
    cols = ",".join(row.keys())
    ph = ",".join("?" for _ in row)
    with conn:
        conn.execute(f"INSERT INTO runs ({cols}) VALUES ({ph})", list(row.values()))


def insert_batch(conn: sqlite3.Connection, batch_id: str, date: str, ts: str, fingerprint_json: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO batches (batch_id, date, ts, fingerprint_json) VALUES (?,?,?,?)",
            (batch_id, date, ts, fingerprint_json),
        )


def fetch_runs(conn: sqlite3.Connection, date: str | None = None) -> list[dict]:
    if date:
        cur = conn.execute("SELECT * FROM runs WHERE date = ? ORDER BY id", (date,))
    else:
        cur = conn.execute("SELECT * FROM runs ORDER BY id")
    return [dict(r) for r in cur.fetchall()]


def fetch_batches(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM batches ORDER BY ts")
    return [dict(r) for r in cur.fetchall()]


def fetch_dates(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT date FROM runs ORDER BY date")
    return [r["date"] for r in cur.fetchall()]


def latest_date(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute("SELECT MAX(date) AS d FROM runs")
    row = cur.fetchone()
    return row["d"] if row and row["d"] else None


def set_gut(conn: sqlite3.Connection, date: str, label: str, ts: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO gut_log (date, label, ts) VALUES (?,?,?)",
            (date, label, ts),
        )


def fetch_gut(conn: sqlite3.Connection) -> dict[str, str]:
    cur = conn.execute("SELECT date, label FROM gut_log ORDER BY date")
    return {r["date"]: r["label"] for r in cur.fetchall()}
