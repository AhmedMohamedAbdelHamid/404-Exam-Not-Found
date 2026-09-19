"""
retrieval.py — get_chunks(topic, language, difficulty) -- Postgres-backed
replacement for the original local-Chroma version (repo root, main
branch). Same public contract: same function signature, same return
shape (chunk_id, topic, language, chunk_type, text, source_pages,
exercise_density_score), same "topic is a hard metadata filter, not
fuzzy matching" retrieval strategy. difficulty is still accepted and
still unused -- see the original module's docstring for why (it's a
property of the generated question, not of any chunk).

One intentional simplification versus the original: its EN-only branch
re-ranked topic-filtered candidates by embedding the topic name and
querying Chroma for the closest matches. That branch's own comment
calls it "a light-touch improvement, not load-bearing -- if it ever
misbehaves, falling back to random.sample is safe since the topic
filter already guarantees correctness." This version always takes that
safe path (sort by exercise_density_score, shuffle within the lowest-
density tier) for every language, so no embedding model is needed at
request time. chunks.embedding in Supabase (pgvector) is still
populated at index-build time and is there if that re-rank is ever
worth reinstating via match_chunks().
"""

from __future__ import annotations

import random
import re

from db import connection

_ISOLATED_LETTER_RE = re.compile(r"(?m)^[A-D]\s*$")


def _exercise_density_score(text: str) -> int:
    """Counts isolated A/B/C/D fill-in-the-blank markers -- a proxy for
    'this chunk is a dense multi-problem exercise page' rather than a
    single focused explanation/example. Higher = more sub-problems
    crammed into one chunk, not lower quality."""
    return len(_ISOLATED_LETTER_RE.findall(text))


def get_chunks(
    topic: str,
    language: str,
    difficulty: int | None = None,
    n: int = 1,
    exclude_chunk_ids: list[str] | None = None,
) -> list[dict]:
    """Retrieve up to `n` chunks for a given topic + language.

    Args:
        topic: exact topic string, e.g. "loops and conditionals" -- a
            metadata equality filter, not fuzzy matching.
        language: "en" or "ar".
        difficulty: accepted for call-site convenience but NOT used to
            filter chunks (difficulty is a property of the generated
            question, not any chunk).
        n: how many chunks to return.
        exclude_chunk_ids: chunk_ids to skip, so two questions for the
            same student on the same topic don't reuse the same chunk.

    Returns:
        List of dicts: {chunk_id, topic, language, chunk_type, text,
        source_pages, exercise_density_score}. Empty list if topic/
        language has no chunks (caller should fall back to the backup
        pool, not crash).
    """
    del difficulty  # intentionally unused -- see module docstring

    if language not in ("en", "ar"):
        raise ValueError(f"language must be 'en' or 'ar', got {language!r}")

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, topic, language, chunk_type, text, source_pages
            FROM chunks
            WHERE topic = %s AND language = %s
            """,
            (topic, language),
        )
        rows = cur.fetchall()

    candidates = []
    for row in rows:
        if exclude_chunk_ids and row["chunk_id"] in exclude_chunk_ids:
            continue
        candidates.append({
            "chunk_id": row["chunk_id"],
            "topic": row["topic"],
            "language": row["language"],
            "chunk_type": row["chunk_type"],
            "text": row["text"],
            "source_pages": list(row["source_pages"]) if row["source_pages"] else [],
            "exercise_density_score": _exercise_density_score(row["text"]),
        })

    if not candidates:
        return []

    # Prefer lower exercise-density chunks when there's a choice -- a
    # focused explanation/example page makes a better single-question
    # grounding source than a dense multi-problem exercise page.
    candidates.sort(key=lambda c: c["exercise_density_score"])
    min_density = candidates[0]["exercise_density_score"]
    low_density_tier = [c for c in candidates if c["exercise_density_score"] == min_density]
    random.shuffle(low_density_tier)
    remaining = [c for c in candidates if c["exercise_density_score"] != min_density]
    return (low_density_tier + remaining)[:n]
