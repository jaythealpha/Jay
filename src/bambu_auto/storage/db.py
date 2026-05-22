from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    state           TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    source_payload  TEXT NOT NULL,
    input_hash      TEXT,
    material        TEXT NOT NULL,
    quality         TEXT NOT NULL,
    target_printer  TEXT,
    meshy_task_id   TEXT,
    model_path      TEXT,
    repaired_path   TEXT,
    gcode_path      TEXT,
    print_job_id    TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(input_hash);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    job_id          TEXT,
    operation       TEXT NOT NULL,
    credits         INTEGER NOT NULL,
    meshy_task_id   TEXT,
    status          TEXT NOT NULL,            -- reserved | committed | refunded
    note            TEXT
);
CREATE INDEX IF NOT EXISTS idx_ledger_ts ON credit_ledger(ts);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON credit_ledger(status);

CREATE TABLE IF NOT EXISTS meshy_cache (
    input_hash      TEXT PRIMARY KEY,
    operation       TEXT NOT NULL,
    meshy_task_id   TEXT NOT NULL,
    model_path      TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_actual_credits (
    job_id          TEXT PRIMARY KEY,
    credits         INTEGER NOT NULL,
    ts              TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)  # autocommit
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()
