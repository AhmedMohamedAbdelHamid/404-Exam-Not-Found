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
- BOTH languages: within the topic-filtered candidates, chunks are
  additionally sorted by `exercise_density_score` (count of isolated
  A/B/C/D fill-in-the-blank markers -- confirmed by direct inspection
  to indicate dense multi-problem exercise pages, NOT extraction
  corruption; both genres extract faithfully). Lower-density chunks
  (score 0, typically the "Information Study" concept/example page)
  are preferred over dense exercise pages when both exist for a topic,
  since a focused page makes a better single-question grounding source.
  This is exposed on the returned dict as `exercise_density_score` too,
  so B can filter/inspect it directly rather than trust it blindly.
  See retrieval.py's inline comment above _exercise_density_score for
  the full investigation (this was originally called "noise_score";
  renamed after confirming it does not measure a defect).

Run standalone for a demo: python3 retrieval.py
"""

import json
import re
import random
import chromadb

CHROMA_PATH = "./chroma_db"

_client = chromadb.PersistentClient(path=CHROMA_PATH)

# --------------------------------------------------------------------
# exercise_density_score -- renamed from an earlier "noise_score"
# (2026-09-15 accuracy review, see roadmap discussion). Investigated
# whether this was extraction corruption to FIX, not just deprioritize
# -- it isn't. Manually inspected the highest-scoring chunks (13-17,
# the worst in the corpus) directly against source text: code blocks
# reconstruct cleanly (e.g. "a = [1, 4, 9, 16, 25]", "def area(base,
# height):"), and the isolated A/B/C/D lines are the textbook's OWN
# fill-in-the-blank answer markers (multi-part "Try It Yourself"
# exercises with an answer key on the same page), not extraction
# artifacts. So this metric does NOT measure extraction quality --
# it measures exercise density, a real content-genre difference, not
# a defect. Renamed to stop implying "noise = broken" when it means
# "this page is a dense multi-problem exercise with a shared preamble
# and answer key, which makes a poor single grounding chunk for one
# generated question, even though the text itself is faithfully
# extracted."
#
# Considered and rejected: splitting these pages into one sub-chunk
# per fill-in-the-blank problem (the numbered "(1)/(2)/(3)" markers
# ARE a real boundary). Rejected because the marker's exact formatting
# isn't consistent enough across pages (spacing/character variants
# confirmed on inspection) to split reliably without risking silently
# cutting a problem's shared preamble or answer key away from its
# blanks -- worse than today's state, where the whole page is at least
# intact and honestly deprioritized. Revisit only with real time
# budget for testing, not as a rushed fix.
_ISOLATED_LETTER_RE = re.compile(r"(?m)^[A-D]\s*$")


def _exercise_density_score(text: str) -> int:
    """Counts isolated A/B/C/D fill-in-the-blank markers -- a proxy for
    'this chunk is a dense multi-problem exercise page' rather than a
    single focused explanation/example. Higher = more sub-problems
    crammed into one chunk, not lower quality. See module-level note
    above for what this does and doesn't mean."""
    return len(_ISOLATED_LETTER_RE.findall(text))


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
        source_pages, exercise_density_score}. Empty list if topic/language has
        no chunks (call site should treat this as "fall back to
        backup pool", not crash).
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
            "exercise_density_score": _exercise_density_score(doc),
        })

    if not candidates:
        return []

    # Prefer lower exercise-density chunks when there's a choice --
    # a focused explanation/example page makes a better single-question
    # grounding source than a dense multi-problem exercise page (see
    # _exercise_density_score's docstring -- this is NOT a quality/
    # corruption signal, both kinds of page extract faithfully).
    # Stable sort so this doesn't fight the language-specific
    # ranking/shuffle below, it just biases which candidates are "in
    # the running" for the top n.
    candidates.sort(key=lambda c: c["exercise_density_score"])

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
    # own; no unproven semantic re-rank. Still respect the density sort
    # above -- shuffle only among the lowest-density tier (score equal
    # to the minimum present) so we don't randomly hand back a dense
    # multi-problem exercise chunk when a focused one was available for
    # this topic.
    min_density = candidates[0]["exercise_density_score"]
    low_density_tier = [c for c in candidates if c["exercise_density_score"] == min_density]
    random.shuffle(low_density_tier)
    remaining = [c for c in candidates if c["exercise_density_score"] != min_density]
    return (low_density_tier + remaining)[:n]


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
            print(f"  {c['chunk_id']:25s} [{c['chunk_type']:10s}] exercise_density={c['exercise_density_score']}  {preview}...")
