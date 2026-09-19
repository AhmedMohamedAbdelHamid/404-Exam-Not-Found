"""
seed_chunks.py — one-time (or re-run-safe) loader: chunks_en.json /
chunks_ar.json -> Supabase's `chunks` table.

Replaces the original embed_to_chroma.py, which built a local Chroma
index. retrieval.py's get_chunks() only ever filters by (topic,
language) at request time (see its module docstring), so this loader
does not compute embeddings -- chunks.embedding is left NULL. It's a
nullable pgvector column already in the schema, so it's there to
backfill later if a semantic re-rank is ever worth adding back via the
existing match_chunks() function.

Usage:
    DATABASE_URL="postgresql://...supabase connection string..." \\
        python3 seed_chunks.py
"""

from __future__ import annotations

import json
from pathlib import Path

from db import connection

CHUNK_FILES = ["chunks_en.json", "chunks_ar.json"]


def _load_chunks() -> list[dict]:
    chunks: list[dict] = []
    for filename in CHUNK_FILES:
        path = Path(__file__).resolve().parent / filename
        with open(path, encoding="utf-8") as f:
            chunks.extend(json.load(f))
    return chunks


def seed() -> None:
    chunks = _load_chunks()
    with connection() as conn, conn.cursor() as cur:
        for chunk in chunks:
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, topic, language, chunk_type, text, source_pages)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    topic = EXCLUDED.topic,
                    language = EXCLUDED.language,
                    chunk_type = EXCLUDED.chunk_type,
                    text = EXCLUDED.text,
                    source_pages = EXCLUDED.source_pages
                """,
                (
                    chunk["chunk_id"],
                    chunk["topic"],
                    chunk["language"],
                    chunk["chunk_type"],
                    chunk["text"],
                    chunk["source_pages"],
                ),
            )
    print(f"Seeded {len(chunks)} chunks into Supabase.")


if __name__ == "__main__":
    seed()
