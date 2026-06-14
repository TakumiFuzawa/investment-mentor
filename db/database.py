import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

_DEFAULT_DB_PATH = Path("data/mentor.db")

# --------------------------------------------------------------------------
# DDL
# --------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);

CREATE TABLE IF NOT EXISTS learning_progress (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_id     TEXT    NOT NULL UNIQUE,
    status       TEXT    NOT NULL DEFAULT 'not_started'
                     CHECK(status IN ('not_started', 'in_progress', 'completed')),
    quiz_score   INTEGER,
    quiz_total   INTEGER,
    completed_at TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    source     TEXT    CHECK(source IN ('chat', 'manual', NULL)),
    tags       TEXT    DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notes_source ON notes(source);

CREATE TABLE IF NOT EXISTS market_cache (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT    NOT NULL UNIQUE,
    data       TEXT    NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# --------------------------------------------------------------------------
# Connection helpers
# --------------------------------------------------------------------------

def _resolve_path(db_path: Optional[Path]) -> Path:
    return db_path if db_path is not None else _DEFAULT_DB_PATH


def init_db(db_path: Optional[Path] = None) -> None:
    path = _resolve_path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(path)) as conn:
            conn.executescript(_DDL)
        logger.info("Database initialized at {}", path)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: {}", e)
        raise


@contextmanager
def get_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    path = _resolve_path(db_path)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error("Database error: {}", e)
        raise
    finally:
        if conn:
            conn.close()


# --------------------------------------------------------------------------
# market_cache utilities（Phase 2-6でmarket_data.pyと統合予定）
# --------------------------------------------------------------------------

def upsert_market_cache(ticker: str, data: dict, db_path: Optional[Path] = None) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO market_cache (ticker, data, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                data = excluded.data,
                fetched_at = excluded.fetched_at
            """,
            (ticker, payload, now),
        )
    logger.debug("market_cache upserted for {}", ticker)


def get_market_cache(
    ticker: str,
    expire_minutes: int = 30,
    db_path: Optional[Path] = None,
) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT data, fetched_at FROM market_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()

    if row is None:
        return None

    fetched_at = datetime.fromisoformat(str(row["fetched_at"]))
    if datetime.now() - fetched_at > timedelta(minutes=expire_minutes):
        logger.debug("market_cache expired for {}", ticker)
        return None

    return json.loads(row["data"])
