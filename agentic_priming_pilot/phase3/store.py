"""SQLite store for the Phase 3 pilot: script versions, pre-call baseline
scores, and real-world call outcomes.

Deliberately boring and file-backed — this data is the case study, so it
should survive a laptop reboot and be trivially inspectable with `sqlite3`.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path("pilot.db")

CONTEXTS = ("phone", "in_person")

# wrong_number and disconnected exist so Phase 2's verification can be scored
# against reality: without them there is no way to tell a number that was
# simply not picked up from one that was never the shop's line.
OUTCOMES = (
    "booked",
    "no_answer",
    "declined",
    "hung_up",
    "wrong_number",
    "disconnected",
)

# Outcomes proving the number did reach the intended business.
OUTCOMES_REACHED_BUSINESS = ("booked", "declined", "hung_up")

# Outcomes proving the number was bad. no_answer is deliberately in neither
# bucket — it is genuinely ambiguous evidence about the number itself.
OUTCOMES_BAD_NUMBER = ("wrong_number", "disconnected")

SCHEMA = """
CREATE TABLE IF NOT EXISTS script_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    context     TEXT NOT NULL CHECK (context IN ('phone', 'in_person')),
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (name, context)
);

CREATE TABLE IF NOT EXISTS baselines (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    script_version_id INTEGER NOT NULL REFERENCES script_versions(id),
    scored_at         TEXT NOT NULL,
    total_score       REAL NOT NULL,
    gate_flags        TEXT NOT NULL,
    humanity_check    INTEGER NOT NULL,
    scorer_backend    TEXT NOT NULL,
    scorer_version    TEXT,
    raw               TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    script_version_id INTEGER NOT NULL REFERENCES script_versions(id),
    business_name     TEXT NOT NULL,
    phone             TEXT,
    channel           TEXT NOT NULL CHECK (channel IN ('phone', 'walk_in')),
    outcome           TEXT NOT NULL,
    contacted_at      TEXT NOT NULL,
    notes             TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate_outcome_check(conn)
    return conn


def _migrate_outcome_check(conn) -> None:
    """Early versions pinned the outcome vocabulary in a CHECK constraint, so
    a database created then rejects wrong_number/disconnected. Rebuild the
    table without the constraint, preserving rows; validation now lives in
    record_attempt() alone."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='attempts'"
    ).fetchone()
    if not row or "CHECK (outcome IN" not in (row["sql"] or ""):
        return

    conn.executescript(
        """
        PRAGMA foreign_keys=off;
        BEGIN;
        CREATE TABLE attempts_new (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            script_version_id INTEGER NOT NULL REFERENCES script_versions(id),
            business_name     TEXT NOT NULL,
            phone             TEXT,
            channel           TEXT NOT NULL
                              CHECK (channel IN ('phone', 'walk_in')),
            outcome           TEXT NOT NULL,
            contacted_at      TEXT NOT NULL,
            notes             TEXT
        );
        INSERT INTO attempts_new SELECT * FROM attempts;
        DROP TABLE attempts;
        ALTER TABLE attempts_new RENAME TO attempts;
        COMMIT;
        PRAGMA foreign_keys=on;
        """
    )


def add_script(conn, name: str, context: str, body: str) -> int:
    if context not in CONTEXTS:
        raise ValueError(f"context must be one of {CONTEXTS}")
    cur = conn.execute(
        "INSERT INTO script_versions (name, context, body, created_at) "
        "VALUES (?, ?, ?, ?)",
        (name, context, body, now()),
    )
    conn.commit()
    return cur.lastrowid


def get_script(conn, script_id: int):
    row = conn.execute(
        "SELECT * FROM script_versions WHERE id = ?", (script_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"No script version with id {script_id}")
    return row


def list_scripts(conn):
    return conn.execute(
        "SELECT * FROM script_versions ORDER BY context, name"
    ).fetchall()


def record_baseline(conn, script_version_id: int, result) -> int:
    """Store a scoring result. `result` is a scorer.ScoreResult."""
    cur = conn.execute(
        "INSERT INTO baselines (script_version_id, scored_at, total_score, "
        "gate_flags, humanity_check, scorer_backend, scorer_version, raw) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            script_version_id,
            now(),
            result.total_score,
            json.dumps(result.gate_flags, sort_keys=True),
            1 if result.humanity_check else 0,
            result.backend,
            result.scorer_version,
            json.dumps(result.raw, sort_keys=True) if result.raw else None,
        ),
    )
    conn.commit()
    return cur.lastrowid


def latest_baseline(conn, script_version_id: int):
    return conn.execute(
        "SELECT * FROM baselines WHERE script_version_id = ? "
        "ORDER BY scored_at DESC, id DESC LIMIT 1",
        (script_version_id,),
    ).fetchone()


def record_attempt(
    conn,
    script_version_id: int,
    business_name: str,
    phone: str,
    channel: str,
    outcome: str,
    notes: str = "",
) -> int:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    cur = conn.execute(
        "INSERT INTO attempts (script_version_id, business_name, phone, "
        "channel, outcome, contacted_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            script_version_id,
            business_name,
            phone,
            channel,
            outcome,
            now(),
            notes,
        ),
    )
    conn.commit()
    return cur.lastrowid


def attempts_for(conn, script_version_id: int):
    return conn.execute(
        "SELECT * FROM attempts WHERE script_version_id = ? ORDER BY contacted_at",
        (script_version_id,),
    ).fetchall()
