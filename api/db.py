"""Shared database helper for the Vercel-deployed backend.

Two storage modes, chosen by the DATABASE_URL environment variable:

* Supabase / Postgres -- DATABASE_URL is a real Postgres connection string
  (``postgresql://...``). This is the production mode: Vercel functions are
  stateless and may run as several parallel instances, so state has to live
  in a shared database. Use the Supabase "Session pooler" URI
  (Project Settings -> Database -> Connection string).

* Local SQLite fallback -- DATABASE_URL is missing or is not a Postgres URL.
  State is kept in a SQLite file and the RAG chunks are loaded from the
  chunks_en.json / chunks_ar.json files bundled next to this module. It is
  *not* durable and is *not* shared between processes/function instances,
  so it is for local development only.

  On Vercel this fallback is REFUSED (see StorageNotConfiguredError). Every
  serverless instance has its own private /tmp, so an attempt created on one
  instance simply does not exist on the next one -- which showed up as
  "This assessment attempt was not found" partway through a quiz. Failing
  loudly with a clear message is better than silently losing state. Set
  ALLOW_EPHEMERAL_STORAGE=1 to override (demo use only).

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
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

LOGGER = logging.getLogger("exam_not_found.db")

DATABASE_URL_ENV = "DATABASE_URL"
SQLITE_PATH_ENV = "EXAM_SQLITE_PATH"

_MODULE_DIR = Path(__file__).resolve().parent
_CHUNK_FILES = ("chunks_en.json", "chunks_ar.json")


class StorageNotConfiguredError(RuntimeError):
    """Raised instead of silently falling back to per-instance SQLite on Vercel."""


def _database_url() -> str:
    # Tolerate quotes pasted around the value in a dashboard / .env file.
    return (os.getenv(DATABASE_URL_ENV) or "").strip().strip("\"'").strip()


def _running_on_vercel() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _ephemeral_storage_allowed() -> bool:
    return (os.getenv("ALLOW_EPHEMERAL_STORAGE") or "").strip().lower() in {"1", "true", "yes"}


def database_url_problem() -> str | None:
    """Human-readable reason DATABASE_URL is unusable, or None if it is fine."""
    url = _database_url()
    if not url:
        return "DATABASE_URL is not set."
    if url.startswith(("postgresql://", "postgres://")):
        return None
    if url.startswith(("http://", "https://")):
        return (
            "DATABASE_URL is an https:// project URL (e.g. https://<ref>.supabase.co). "
            "It must be the Postgres connection string from Supabase -> Project Settings "
            "-> Database -> Connection string (URI), starting with postgresql://"
        )
    return "DATABASE_URL must start with postgresql:// (or postgres://)."


def uses_postgres() -> bool:
    """True only when DATABASE_URL is a usable Postgres connection string."""
    problem = database_url_problem()
    if problem is None:
        return True
    if _database_url() and not _warned_invalid_url.is_set():
        _warned_invalid_url.set()
        LOGGER.error(
            "%s %s",
            problem,
            "Refusing to use per-instance SQLite on Vercel."
            if _running_on_vercel() and not _ephemeral_storage_allowed()
            else "Falling back to local SQLite (dev only).",
        )
    return False


_warned_invalid_url = threading.Event()


# --------------------------------------------------------------------------
# Postgres mode
# --------------------------------------------------------------------------

_MIGRATIONS_DIR = _MODULE_DIR / "migrations"
_postgres_lock = threading.Lock()
_postgres_ready = False
_postgres_last_attempt = 0.0
_BOOTSTRAP_RETRY_SECONDS = 30.0
_BOOTSTRAP_ADVISORY_LOCK = 4_040_404


def _raw_postgres_connect() -> Any:
    import psycopg
    from psycopg.rows import dict_row

    # prepare_threshold=None: server-side prepared statements break behind
    # Supabase's transaction pooler (port 6543); disabling them works for both
    # the session and the transaction pooler. Every request here opens short
    # connections, so prepared statements would never pay off anyway.
    return psycopg.connect(
        _database_url(),
        row_factory=dict_row,
        prepare_threshold=None,
        connect_timeout=10,
    )


def _bootstrap_postgres() -> None:
    """Idempotently create tables and load textbook chunks.

    Runs once per function instance. Without it a fresh Supabase project has no
    ``student_state`` / ``attempt_contexts`` / ``chunks`` tables, and an empty
    ``chunks`` table silently disables live question generation (the app then
    serves the small verified fallback pool for every quiz).
    """
    conn = _raw_postgres_connect()
    try:
        with conn.cursor() as cur:
            # Serialise concurrent cold starts so CREATE TABLE IF NOT EXISTS
            # does not race with itself.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_BOOTSTRAP_ADVISORY_LOCK,))
            for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(migration.read_text(encoding="utf-8"))
            cur.execute("SELECT COUNT(*) AS n FROM chunks")
            if cur.fetchone()["n"] == 0:
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
                                list(chunk.get("source_pages") or []),
                            )
                        )
                cur.executemany(
                    "INSERT INTO chunks (chunk_id, topic, language, chunk_type, text, source_pages) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (chunk_id) DO NOTHING",
                    rows,
                )
                LOGGER.info("Seeded %d textbook chunks into Postgres.", len(rows))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_postgres_ready() -> None:
    global _postgres_ready, _postgres_last_attempt
    if _postgres_ready:
        return
    with _postgres_lock:
        if _postgres_ready:
            return
        if time.monotonic() - _postgres_last_attempt < _BOOTSTRAP_RETRY_SECONDS and _postgres_last_attempt:
            return  # a recent bootstrap failed; don't hammer the database on every query
        _postgres_last_attempt = time.monotonic()
        try:
            _bootstrap_postgres()
        except Exception as exc:  # noqa: BLE001 -- never block requests on bootstrap
            LOGGER.error(
                "Postgres bootstrap failed (%s.%s: %s). Run api/migrations/*.sql and "
                "api/seed_chunks.py manually if this persists.",
                type(exc).__module__,
                type(exc).__name__,
                str(exc)[:200],
            )
            return
        _postgres_ready = True


@contextmanager
def _postgres_connection() -> Iterator[Any]:
    _ensure_postgres_ready()
    conn = _raw_postgres_connect()
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
        return
    if _running_on_vercel() and not _ephemeral_storage_allowed():
        raise StorageNotConfiguredError(
            "The server's database is not configured. "
            + (database_url_problem() or "")
            + " Set DATABASE_URL in the Vercel project settings and redeploy."
        )
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


def storage_status() -> dict[str, Any]:
    """Non-secret storage diagnostics for /api/diagnostics."""
    mode = storage_mode()
    status: dict[str, Any] = {
        "mode": mode,
        "durable": mode == "postgres",
        "on_vercel": _running_on_vercel(),
        "config_problem": database_url_problem(),
        "reachable": False,
        "error": None,
        "chunks": {},
    }
    if mode != "postgres" and _running_on_vercel() and not _ephemeral_storage_allowed():
        status["error"] = "StorageNotConfiguredError"
        return status
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT language, COUNT(*) AS n FROM chunks GROUP BY language")
            status["chunks"] = {row["language"]: int(row["n"]) for row in cur.fetchall()}
        status["reachable"] = True
    except Exception as exc:  # noqa: BLE001
        status["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return status
