"""
retrieval.py — get_chunks(topic, language, difficulty) — A3 deliverable
(roadmap deadline: Day 4 midday; started Day 3 since embedding/A2 landed
early). This is the hard handoff B is waiting on (see roadmap.md
"Critical path").

--------------------------------------------------------------------
Contract, and why it differs slightly from the roadmap's literal
"get_chunks(topic, difficulty)" signature:
--------------------------------------------------------------------
Per schema.py (B's frozen Day-2 contract) and prompt_template.py's
USER_PROMPT_TEMPLATE, `target_difficulty` is passed straight into the
GENERATION PROMPT as an instruction ("Target difficulty band: {N}") --
it is NOT a property of any chunk, and no chunk is tagged with a
difficulty level. difficulty_score is computed by B, post-generation,
from three LLM self-reported sub-scores about the *question*
(schema.py's DifficultySubScores) -- the same chunk can ground an easy
or hard question depending on how the prompt shapes it.

So get_chunks() here retrieves by (topic, language) -- matching what a
chunk actually IS -- and does not filter on difficulty. `difficulty`
is accepted as a parameter anyway so B's call site can pass it through
untouched into build_messages() without restructuring their code, but
it has no effect on which chunk comes back. This is called out loudly
below and should be confirmed with B today, not assumed.

--------------------------------------------------------------------
KNOWN TOPIC-STRING MISMATCH -- confirm with B before they integrate:
--------------------------------------------------------------------
prompt_template.py's SAMPLE_CHUNKS uses "loops" and "conditionals" as
TWO separate topics. This chunker tags Chapter 12 section 12-3 (which
covers both in the textbook) as ONE combined topic:
"loops and conditionals". Real topic strings produced by A:
    algorithm | variables and assignment | loops and conditionals |
    lists | functions
If B's staircase controller / difficulty scorer expects "loops" and
"conditionals" as independently selectable topics, one of us needs to
either split the chunk-tagging or merge B's topic list. Flag this
explicitly in today's sync -- don't let it surface as a silent bug on
Day 4-5 integration.

--------------------------------------------------------------------
Retrieval strategy per language (see embed_to_chroma.py docstring for
the measurements behind this):
--------------------------------------------------------------------
- EN: embedding-based semantic search is reliable (verified clean
  topic separation on sanity queries) -- but we still filter by the
  `topic` metadata tag FIRST, since topic is a hard, correct label
  (from real section boundaries) and the student/generator always
  wants a specific topic, not "whatever's semantically closest."
  Embedding similarity is then used only to rank/diversify WITHIN
  that topic (matters once there's more than one chunk per topic per
  page -- right now it's ~4 pages/topic).
- AR: metadata topic filter ONLY, no embedding step. The multilingual
  embedder (paraphrase-multilingual-MiniLM-L12-v2) stopped collapsing
  to one chunk but is still not reliably topic-accurate on its own
  (verified: a "for loop" query didn't rank a loops/12-3 chunk in the
  top 3). Since the topic filter alone is 100% reliable and already
  narrows to ~4-6 chunks, semantic re-ranking on top of that adds risk
  without proven benefit for Arabic today. Can revisit if a stronger
  multilingual model is swapped in later.

Run standalone for a demo: python3 retrieval.py
"""

import json
import random
import chromadb

CHROMA_PATH = "./chroma_db"

_client = chromadb.PersistentClient(path=CHROMA_PATH)


def _collection_name(language: str) -> str:
    if language not in ("en", "ar"):
        raise ValueError(f"language must be 'en' or 'ar', got {language!r}")
    return f"chunks_{language}"


def get_chunks(
    topic: str,
    language: str,
    difficulty: int | None = None,
    n: int = 1,
    exclude_chunk_ids: list[str] | None = None,
) -> list[dict]:
    """Retrieve up to `n` chunks for a given topic + language, shaped
    exactly like prompt_template.py's SAMPLE_CHUNKS entries (plus
    chunk_id/source_pages for traceability -- schema.py's
    source_chunk_id field needs this).

    Args:
        topic: exact topic string, e.g. "loops and conditionals".
            Must match A's tagging exactly (see mismatch note above)
            -- this is a metadata equality filter, not fuzzy matching.
        language: "en" or "ar". Selects which ChromaDB collection is
            queried -- collections are never mixed (schema.py's
            language-scoping requirement).
        difficulty: accepted for call-site convenience (so B can pass
            NextQuestionRequest.current_difficulty straight through)
            but NOT used to filter chunks -- see module docstring.
            Unused today; kept as an explicit parameter rather than
            silently dropped so it's obvious this is intentional, not
            a bug.
        n: how many chunks to return. >1 lets B pick among a few
            candidates (e.g. for backup pool generation, A5) rather
            than always getting the single top match.
        exclude_chunk_ids: chunk_ids to skip -- for A4 (per-student
            chunk sampling / anti-cheat), so two questions for the
            same student on the same topic don't reuse the identical
            chunk. Optional, defaults to no exclusion.

    Returns:
        List of dicts: {chunk_id, topic, language, chunk_type, text,
        source_pages}. Empty list if topic/language has no chunks
        (call site should treat this as "fall back to backup pool",
        not crash).
    """
    del difficulty  # intentionally unused -- see docstring

    collection = _client.get_collection(_collection_name(language))

    where_filter = {"topic": topic}
    # Chroma's get() (metadata-filter-only, no embedding query) is the
    # right call here for AR (topic filter only) and is ALSO what we
    # use for EN as the first pass, per the "topic first" strategy
    # above -- embedding search is layered on top only for EN below.
    results = collection.get(where=where_filter)

    ids = results["ids"]
    documents = results["documents"]
    metadatas = results["metadatas"]

    candidates = []
    for cid, doc, meta in zip(ids, documents, metadatas):
        if exclude_chunk_ids and cid in exclude_chunk_ids:
            continue
        candidates.append({
            "chunk_id": cid,
            "topic": meta["topic"],
            "language": meta["language"],
            "chunk_type": meta["chunk_type"],
            "text": doc,
            "source_pages": json.loads(meta["source_pages"]),
        })

    if not candidates:
        return []

    if language == "en" and len(candidates) > n:
        # EN only: re-rank the topic-filtered candidates by embedding
        # similarity to the topic name itself, as a proxy for "most
        # representative / clearest explanation" chunk in this topic.
        # This is a light-touch improvement, not load-bearing -- if it
        # ever misbehaves, falling back to random.sample is safe since
        # the topic filter already guarantees correctness.
        query_result = collection.query(
            query_texts=[topic],
            n_results=min(n, len(candidates)),
            where=where_filter,
        )
        ranked_ids = query_result["ids"][0]
        by_id = {c["chunk_id"]: c for c in candidates}
        ranked = [by_id[i] for i in ranked_ids if i in by_id]
        # top up with any remaining candidates if the ranked query
        # returned fewer than n (can happen with exclude filtering)
        remaining = [c for c in candidates if c["chunk_id"] not in ranked_ids]
        return (ranked + remaining)[:n]

    # AR (and EN fallback): topic filter is already reliable on its
    # own; just sample without an unproven semantic re-rank.
    random.shuffle(candidates)
    return candidates[:n]


if __name__ == "__main__":
    demo_calls = [
        ("loops and conditionals", "en", 2),
        ("loops and conditionals", "ar", 2),
        ("functions", "en", 4),
        ("variables and assignment", "ar", 1),
        ("not a real topic", "en", 3),  # should return [] cleanly
    ]
    for topic, language, difficulty in demo_calls:
        print(f"\nget_chunks(topic={topic!r}, language={language!r}, difficulty={difficulty})")
        chunks = get_chunks(topic, language, difficulty=difficulty, n=2)
        if not chunks:
            print("  -> [] (no chunks for this topic/language -- caller should use backup pool)")
        for c in chunks:
            preview = c["text"][:80].replace("\n", " ")
            print(f"  {c['chunk_id']:25s} [{c['chunk_type']:10s}] {preview}...")
