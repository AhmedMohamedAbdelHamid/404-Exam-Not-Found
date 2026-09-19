"""Shared Postgres connection helper for the Vercel-deployed backend.

Local development and the legacy Streamlit app keep using the original
SQLite-backed modules (still in the repo root of the main branch) --
this module is only imported by the Postgres-backed replacements used
here in web/api/, because on Vercel each request can land on a
different, stateless function instance: state can no longer live in a
local SQLite file, it has to live in a real database.

Points DATABASE_URL at your Supabase project's connection string
(Project Settings -> Database -> Connection string -> URI, "Session"
pooler mode recommended for serverless).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

DATABASE_URL_ENV = "DATABASE_URL"


def _connection_string() -> str:
    url = os.getenv(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{DATABASE_URL_ENV} is not set. Set it to the Supabase project's "
            "Postgres connection string."
        )
    return url


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """One connection, one transaction: commits on success, rolls back
    and re-raises on any exception. Mirrors the original SQLite
    modules' _write()/_read() context managers so callers don't change.
    """
    conn = psycopg.connect(_connection_string(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
