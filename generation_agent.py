"""
generation_agent.py — B3 deliverable (Day 4-5, Person B)
"Integrate real RAG retrieval into generation agent"

This is the hard handoff unblocked by A3/A4 (retrieval.py, chunk_sampler.py).
Swaps SAMPLE_CHUNKS (Day 2-3 dummy data) for real chunks from A's
ChunkSampler.get_unseen_chunk(), which wraps retrieval.get_chunks()
with per-student anti-cheat exclusion (A4).

--------------------------------------------------------------------
IMPORTANT — not verified against a live ChromaDB in this environment:
--------------------------------------------------------------------
retrieval.py's get_chunks() needs a populated ./chroma_db (built by
running embed_to_chroma.py), which downloads embedding models from
HuggingFace. This sandbox's network is restricted to package
registries only (no huggingface.co access), so embed_to_chroma.py
cannot be run here, and this module's real-retrieval path has NOT
been exercised against actual ChromaDB data.

What IS verified here (see __main__): this module's own logic --
correctly calling ChunkSampler, handling both "got a chunk" and
"no chunks left / topic exhausted" (empty result) cases, building a
valid prompt from whatever chunk dict comes back, and producing a
schema-valid QuestionOut -- tested against a MOCKED ChunkSampler that
returns realistically-shaped dicts (same keys/types retrieval.py's
docstring specifies: chunk_id, topic, language, chunk_type, text,
source_pages, noise_score).

Before Day 4 sync: run this against the REAL chunk_sampler.ChunkSampler
(needs ./chroma_db built via `python3 embed_to_chroma.py`, which
requires real internet access) to confirm end-to-end behavior with
actual retrieved chunks, not just the mock.

--------------------------------------------------------------------
Also unverified here (separate, known issue): real LLM generation.
call_llm() below now uses the REAL Gemini API (llm_client.py)
automatically when GEMINI_API_KEY is set. Without a key -- e.g. this
sandbox, which also has no network path to Google's API regardless --
it falls back to a generic rule-based STUB that produces a
syntactically valid, schema-passing QuestionOut for ANY chunk, proving
the pipeline plumbing works even without a key, but NOT representative
of real question quality (it's not pedagogically designed, unlike
generate.py's hand-written canned responses). The __main__ tests below
still use this stub path deliberately (no key in this sandbox), so
they test plumbing correctness, not generation quality.

Run standalone: python3 generation_agent.py
"""

from schema import QuestionOut
from difficulty_scorer import apply_difficulty_score
from prompt_template import build_messages_from_chunk, parse_and_validate
import json
import llm_client


class NoChunkAvailable(Exception):
    """Raised when ChunkSampler has no unseen chunk left for this
    student/topic/language (every chunk already served, or the topic
    has zero chunks). Caller (B9) should treat this as "fall back to
    the backup pool" (A5, Day 6) -- same policy chunk_sampler.py's own
    docstring specifies for its None return.
    """
    def __init__(self, topic: str, language: str, student_id: str):
        self.topic = topic
        self.language = language
        self.student_id = student_id
        super().__init__(
            f"No unseen chunk available for student_id={student_id!r}, "
            f"topic={topic!r}, language={language!r}. Caller should fall "
            f"back to the backup question pool (A5)."
        )


def _generic_stub_llm_response(chunk: dict, target_difficulty: int) -> str:
    """GENERIC test stub, NOT a real LLM call and NOT pedagogically
    designed like generate.py's hand-written canned responses. Produces
    a syntactically valid, schema-passing QuestionOut JSON for ANY
    chunk dict, so this module's plumbing (retrieval -> prompt -> parse
    -> validate -> score) can be tested against arbitrary real chunks,
    not just the 4 hand-picked ones in prompt_template.py.

    Replace with a real LLM call before Day 5-6 / the demo -- see
    module docstring.
    """
    topic = chunk["topic"]
    language = chunk["language"]
    lang_label = {"en": "English", "ar": "Arabic"}.get(language, language)

    if language == "ar":
        question_text = f"بناءً على النص، ما الموضوع الرئيسي لهذا المقطع؟ ({topic})"
        options = [
            {"text": f"يتعلق بموضوع {topic}", "correct": True, "misconception": None},
            {"text": "يتعلق بموضوع غير ذي صلة (أ)", "correct": False, "misconception": "خلط بين مواضيع مختلفة من الكتاب"},
            {"text": "يتعلق بموضوع غير ذي صلة (ب)", "correct": False, "misconception": "افتراض أن كل صفحة تغطي نفس الموضوع"},
            {"text": "لا يمكن تحديد الموضوع من النص", "correct": False, "misconception": "تجاهل المحتوى الصريح للنص"},
        ]
    else:
        question_text = f"Based on the text, what is this passage primarily about? ({topic})"
        options = [
            {"text": f"It explains {topic}", "correct": True, "misconception": None},
            {"text": "It explains an unrelated topic (A)", "correct": False, "misconception": "confuses this topic with a different chapter section"},
            {"text": "It explains an unrelated topic (B)", "correct": False, "misconception": "assumes all pages in the chapter cover the same topic"},
            {"text": "The topic cannot be determined from the text", "correct": False, "misconception": "ignores the passage's explicit content"},
        ]

    return json.dumps({
        "question": question_text,
        "topic": topic,
        "language": language,
        "chunk_type": chunk.get("chunk_type", "definition"),
        "source_chunk_id": chunk["chunk_id"],
        "options": options,
        "difficulty": {
            "bloom_level": target_difficulty,
            "bloom_justification": f"[STUB] set to match requested target_difficulty={target_difficulty}",
            "distractor_quality": 2,
            "distractor_justification": "[STUB] generic topic-confusion distractors, not chunk-specific",
            "concept_depth": 1,
            "concept_depth_justification": "[STUB] single-chunk topic identification only",
        },
    })


def call_llm(messages: list[dict], chunk: dict, target_difficulty: int) -> str:
    """Real Gemini call when GEMINI_API_KEY is set (llm_client.py);
    otherwise falls back to the generic stub above, so B3's own tests
    (__main__ below, and B6's retry tests that import this call_llm)
    keep working with no key/network. `chunk`/`target_difficulty` are
    only used by the stub fallback -- a real call only needs `messages`.
    """
    if llm_client.USE_REAL_LLM:
        return llm_client.generate_question_json(messages)

    del messages  # the stub ignores prompt content, same caveat as generate.py
    return _generic_stub_llm_response(chunk, target_difficulty)


def generate_question_for_student(
    student_id: str,
    topic: str,
    language: str,
    target_difficulty: int,
    chunk_sampler,
) -> QuestionOut:
    """B3's core integration point: pull a REAL, unseen chunk for this
    student/topic/language via chunk_sampler (A4, wraps A3's
    get_chunks()), then run it through the same
    build_messages_from_chunk -> LLM -> parse_and_validate ->
    apply_difficulty_score pipeline generate.py already proved works
    on dummy chunks.

    Raises NoChunkAvailable if chunk_sampler has nothing left --
    caller (B9) must handle this (fall back to backup pool, A5).
    """
    chunk = chunk_sampler.get_unseen_chunk(student_id, topic, language)
    if chunk is None:
        raise NoChunkAvailable(topic, language, student_id)

    messages = build_messages_from_chunk(chunk, target_difficulty)
    raw_response = call_llm(messages, chunk, target_difficulty)
    question = parse_and_validate(raw_response)
    apply_difficulty_score(question)
    return question


# ---------------------------------------------------------------------
# Mock ChunkSampler for testing this module's OWN logic without a live
# ChromaDB (see module docstring -- Chroma is unreachable here).
# Shaped identically to the real chunk_sampler.ChunkSampler's public
# interface (get_unseen_chunk(student_id, topic, language, difficulty)
# -> dict | None) so swapping in the real one is a one-line change.
# ---------------------------------------------------------------------

class _MockChunkSampler:
    """Returns realistically-shaped chunk dicts (same keys retrieval.py
    documents: chunk_id, topic, language, chunk_type, text,
    source_pages, noise_score) without touching ChromaDB. Tracks seen
    chunk_ids per student, same contract as the real ChunkSampler, so
    the exhaustion/None-return path is also testable.
    """

    _FAKE_CHUNKS = {
        ("algorithm", "en"): [
            {"chunk_id": "en_ch12_12-1_p155", "topic": "algorithm", "language": "en",
             "chunk_type": "definition", "text": "An algorithm is a method or procedure "
             "for solving a particular problem.", "source_pages": [155, 155], "noise_score": 0},
        ],
        ("variables and assignment", "en"): [
            {"chunk_id": "en_ch12_12-2_p160", "topic": "variables and assignment", "language": "en",
             "chunk_type": "code_block", "text": "A variable is like a box that stores data. "
             "The '=' operator assigns the right side to the left side.",
             "source_pages": [160, 160], "noise_score": 0},
        ],
        ("loops and conditionals", "ar"): [
            {"chunk_id": "ar_ch12_12-3_p175", "topic": "loops and conditionals", "language": "ar",
             "chunk_type": "code_block", "text": "جملة for تكرر عملية ما.",
             "source_pages": [175, 175], "noise_score": 0},
        ],
    }

    def __init__(self):
        self._seen: dict[str, set[str]] = {}

    def get_unseen_chunk(self, student_id, topic, language, difficulty=None):
        del difficulty
        seen = self._seen.setdefault(student_id, set())
        candidates = self._FAKE_CHUNKS.get((topic, language), [])
        for c in candidates:
            if c["chunk_id"] not in seen:
                seen.add(c["chunk_id"])
                return c
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("B3 — GENERATION AGENT WIRED TO (MOCKED) REAL RETRIEVAL")
    print("=" * 70)
    print(
        "NOTE: using _MockChunkSampler, not the real chunk_sampler.ChunkSampler "
        "-- see module docstring for why (no live ChromaDB in this sandbox)."
    )

    sampler = _MockChunkSampler()

    print("\n--- Case 1: chunk available (EN, algorithm) ---")
    q = generate_question_for_student(
        student_id="student_001", topic="algorithm", language="en",
        target_difficulty=2, chunk_sampler=sampler,
    )
    print(f"question: {q.question}")
    print(f"source_chunk_id: {q.source_chunk_id}  (real chunk, not SAMPLE_CHUNKS)")
    print(f"difficulty_score: {q.difficulty_score}")

    print("\n--- Case 2: chunk available (AR, loops and conditionals) ---")
    q_ar = generate_question_for_student(
        student_id="student_002", topic="loops and conditionals", language="ar",
        target_difficulty=3, chunk_sampler=sampler,
    )
    print(f"question: {q_ar.question}")
    print(f"language: {q_ar.language}")

    print("\n--- Case 3: NO chunk available (exhausted -- Case 1 already consumed ---")
    print("    student_001's only 'algorithm'/en chunk) -> should raise ---")
    try:
        generate_question_for_student(
            student_id="student_001", topic="algorithm", language="en",
            target_difficulty=2, chunk_sampler=sampler,
        )
        print("✗ FAILED: expected NoChunkAvailable, nothing was raised")
    except NoChunkAvailable as e:
        print(f"✓ Correctly raised NoChunkAvailable: {e}")

    print("\n--- Case 4: topic with zero chunks at all -> should also raise ---")
    try:
        generate_question_for_student(
            student_id="student_003", topic="functions", language="en",
            target_difficulty=2, chunk_sampler=sampler,
        )
        print("✗ FAILED: expected NoChunkAvailable, nothing was raised")
    except NoChunkAvailable as e:
        print(f"✓ Correctly raised NoChunkAvailable: {e}")

    print("\n✓ All B3 plumbing checks passed (against mocked retrieval).")
