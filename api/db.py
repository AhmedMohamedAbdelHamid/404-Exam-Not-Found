"""Shared database helper for the Vercel-deployed backend.

Two storage modes, chosen by the DATABASE_URL environment variable:

* Supabase / Postgres -- DATABASE_URL is a real Postgres connection string
  (``postgresql://...``). This is the production mode: Vercel functions are
  stateless and may run as several parallel instances, so state has to live
  in a shared database. Use the Supabase "Session pooler" URI
  (Project Settings -> Database -> Connection string).

* Local SQLite fallback -- DATABASE_URL is missing or is not a Postgres URL.
  State is kept in a SQLite file (default: the OS temp dir, which is the
  only writable place on Vercel) and the RAG chunks are loaded from the
  chunks_en.json / chunks_ar.json files bundled next to this module. This
  lets the app run on Vercel before Supabase is wired up. It is *not*
  durable and is not shared between function instances -- each warm
  instance has its own copy -- so treat it as a demo/dev mode only.

Callers use the same interface in both modes:

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT ... WHERE x = %s", (value,))
        row = cur.fetchone()      # dict-like rows

and `json_param()` / `json_value()` for jsonb columns.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

LOGGER = logging.getLogger("exam_not_found.db")

DATABASE_URL_ENV = "DATABASE_URL"
SQLITE_PATH_ENV = "EXAM_SQLITE_PATH"

_MODULE_DIR = Path(__file__).resolve().parent
_CHUNK_FILES = ("chunks_en.json", "chunks_ar.json")


def _database_url() -> str:
    return (os.getenv(DATABASE_URL_ENV) or "").strip()


def uses_postgres() -> bool:
    """True only when DATABASE_URL is a usable Postgres connection string."""
    url = _database_url()
    if not url:
        return False
    if url.startswith(("postgresql://", "postgres://")):
        return True
    if not _warned_invalid_url.is_set():
        _warned_invalid_url.set()
        LOGGER.warning(
            "DATABASE_URL is set but is not a postgresql:// connection string "
            "(a Supabase project URL such as https://<ref>.supabase.co will not "
            "work). Falling back to the local SQLite store. Use the Session "
            "pooler URI from Supabase -> Project Settings -> Database."
        )
    return False


_warned_invalid_url = threading.Event()


# --------------------------------------------------------------------------
# Postgres mode
# --------------------------------------------------------------------------

@contextmanager
def _postgres_connection() -> Iterator[Any]:
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(_database_url(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------
# SQLite fallback mode
# --------------------------------------------------------------------------

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    initial_difficulty INTEGER NOT NULL CHECK (initial_difficulty BETWEEN 1 AND 5),
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
    created_at TEXT NOT NULL,
    completed_at TEXT NULL,
    final_difficulty INTEGER NULL CHECK (final_difficulty BETWEEN 1 AND 5),
    CHECK (
        (status = 'in_progress' AND completed_at IS NULL AND final_difficulty IS NULL)
        OR
        (status = 'completed' AND completed_at IS NOT NULL AND final_difficulty IS NOT NULL)
    )
);
CREATE TABLE IF NOT EXISTS answers (
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id) ON DELETE RESTRICT,
    question_id TEXT NOT NULL,
    question_number INTEGER NOT NULL CHECK (question_number >= 1),
    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    topic TEXT NOT NULL,
    question_text TEXT NOT NULL,
    selected_option_index INTEGER NOT NULL CHECK (selected_option_index >= 0),
    selected_answer_text TEXT NOT NULL,
    correct_answer_text TEXT NOT NULL,
    correct BOOLEAN NOT NULL,
    misconception TEXT NULL,
    difficulty_score INTEGER NOT NULL CHECK (difficulty_score BETWEEN 1 AND 5),
    requested_difficulty INTEGER NOT NULL CHECK (requested_difficulty BETWEEN 1 AND 5),
    adaptive_level_before INTEGER NOT NULL CHECK (adaptive_level_before BETWEEN 1 AND 5),
    adaptive_level_after INTEGER NULL CHECK (adaptive_level_after BETWEEN 1 AND 5),
    source_reference TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed')),
    created_at TEXT NOT NULL,
    confirmed_at TEXT NULL,
    PRIMARY KEY (attempt_id, question_id),
    CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND adaptive_level_after IS NOT NULL)
        OR
        (status IN ('pending', 'failed') AND confirmed_at IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_attempts_created ON attempts(created_at, attempt_id);
CREATE INDEX IF NOT EXISTS idx_answers_status_order
    ON answers(status, attempt_id, question_number, question_id);
CREATE TABLE IF NOT EXISTS student_state (
    student_id TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    current_difficulty INTEGER NOT NULL,
    topic_index INTEGER NOT NULL DEFAULT 0,
    questions_answered INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attempt_contexts (
    attempt_id TEXT PRIMARY KEY,
    context TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    language TEXT NOT NULL,
    chunk_type TEXT,
    text TEXT NOT NULL,
    source_pages TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_topic_language ON chunks(topic, language);
"""

_sqlite_lock = threading.Lock()
_sqlite_ready_for: str | None = None


def _sqlite_path() -> str:
    configured = os.getenv(SQLITE_PATH_ENV)
    if configured:
        return configured
    return str(Path(tempfile.gettempdir()) / "exam_not_found.sqlite3")


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {column[0]: value for column, value in zip(cursor.description, row)}


_PLACEHOLDER_RE = re.compile(r"%s")
_NOW_RE = re.compile(r"\bnow\(\)", re.IGNORECASE)


def _translate(sql: str) -> str:
    """Postgres-flavoured SQL used by the stores -> SQLite."""
    return _NOW_RE.sub("CURRENT_TIMESTAMP", _PLACEHOLDER_RE.sub("?", sql))


class _SqliteCursor:
    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw
        self._cursor = raw.cursor()

    def __enter__(self) -> "_SqliteCursor":
        return self

    def __exit__(self, *exc: object) -> None:
        self._cursor.close()

    def execute(self, sql: str, params: Any = None) -> "_SqliteCursor":
        statement = _translate(sql)
        if params is None and statement.count(";") > 1:
            # Multi-statement DDL script (AnalyticsStore.initialize()).
            self._raw.executescript(statement)
        else:
            self._cursor.execute(statement, tuple(params) if params else ())
        return self

    def fetchone(self) -> dict[str, Any] | None:
        return self._cursor.fetchone()

    def fetchall(self) -> list[dict[str, Any]]:
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount


class _SqliteConnection:
    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    def cursor(self) -> _SqliteCursor:
        return _SqliteCursor(self._raw)


def _seed_chunks(raw: sqlite3.Connection) -> None:
    if raw.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]:
        return
    rows = []
    for name in _CHUNK_FILES:
        path = _MODULE_DIR / name
        if not path.exists():
            LOGGER.warning("Chunk file %s not found; live generation disabled.", name)
            continue
        for chunk in json.loads(path.read_text(encoding="utf-8")):
            rows.append(
                (
                    chunk["chunk_id"],
                    chunk["topic"],
                    chunk["language"],
                    chunk.get("chunk_type"),
                    chunk["text"],
                    json.dumps(chunk.get("source_pages") or []),
                )
            )
    raw.executemany(
        "INSERT OR IGNORE INTO chunks "
        "(chunk_id, topic, language, chunk_type, text, source_pages) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    raw.commit()


def _ensure_sqlite_ready(path: str) -> None:
    global _sqlite_ready_for
    if _sqlite_ready_for == path:
        return
    with _sqlite_lock:
        if _sqlite_ready_for == path:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, timeout=30)
        try:
            raw.executescript(_SQLITE_SCHEMA)
            raw.commit()
            _seed_chunks(raw)
        finally:
            raw.close()
        _sqlite_ready_for = path


@contextmanager
def _sqlite_connection() -> Iterator[_SqliteConnection]:
    path = _sqlite_path()
    _ensure_sqlite_ready(path)
    raw = sqlite3.connect(path, timeout=30)
    raw.row_factory = _dict_factory
    raw.execute("PRAGMA foreign_keys = ON")
    try:
        yield _SqliteConnection(raw)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


# --------------------------------------------------------------------------
# Public interface
# --------------------------------------------------------------------------

@contextmanager
def connection() -> Iterator[Any]:
    """One connection, one transaction: commits on success, rolls back and
    re-raises on any exception."""
    if uses_postgres():
        with _postgres_connection() as conn:
            yield conn
    else:
        with _sqlite_connection() as conn:
            yield conn


def json_param(payload: Any) -> Any:
    """Wrap a Python value for binding to a jsonb (Postgres) / TEXT (SQLite) column."""
    if uses_postgres():
        from psycopg.types.json import Json

        return Json(payload)
    return json.dumps(payload)


def json_value(value: Any) -> Any:
    """Inverse of json_param() for values read back from the column."""
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return value


def storage_mode() -> str:
    return "postgres" if uses_postgres() else "sqlite"
