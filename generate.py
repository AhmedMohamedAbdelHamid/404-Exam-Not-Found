"""
generate.py — B2 deliverable (Day 3, Person B)
"Generation working end-to-end on dummy chunks."

Ties together: prompt_template.build_messages() -> LLM call ->
prompt_template.parse_and_validate() -> difficulty_scorer.apply_difficulty_score()
-> a fully populated, schema-valid QuestionOut.

call_llm() now uses the REAL Gemini API (llm_client.py) automatically
when GEMINI_API_KEY is set (see llm_client.USE_REAL_LLM). Without a
key -- e.g. this sandbox, which also has no network path to Google's
API regardless -- it falls back to the same hand-written canned
responses this file has used since Day 3, so local/offline testing
still works unchanged.

Run standalone: python3 generate.py
"""

from schema import QuestionOut
from difficulty_scorer import apply_difficulty_score
from prompt_template import (
    SAMPLE_CHUNKS,
    build_messages,
    parse_and_validate,
    _simulated_llm_response_for_for_loop_chunk,
    _simulated_llm_response_for_for_loop_chunk_ar,
    _simulated_llm_response_for_variables_chunk,
    _simulated_llm_response_for_if_elif_chunk,
)
import llm_client

# ---------------------------------------------------------------------
# LLM call. Real signature: (messages: list[dict]) -> str.
# Uses llm_client.py's real Gemini call when GEMINI_API_KEY is set;
# otherwise falls back to canned responses below (offline/no-key path).
# ---------------------------------------------------------------------

# All 4 SAMPLE_CHUNKS in prompt_template.py now have a canned response,
# so the full dummy-chunk set generates end-to-end, not just a subset.
_CANNED_RESPONSES = {
    "en_ch12_12-2_p160": _simulated_llm_response_for_variables_chunk,
    "en_ch12_12-3_p162": _simulated_llm_response_for_for_loop_chunk,
    "en_ch12_12-3_p163": _simulated_llm_response_for_if_elif_chunk,
    "ar_ch12_12-3_p175": _simulated_llm_response_for_for_loop_chunk_ar,
}


def call_llm(messages: list[dict], chunk_id: str) -> str:
    """Real LLM call when GEMINI_API_KEY is set (llm_client.py);
    otherwise falls back to a canned response keyed by chunk_id, so
    this file's own dummy-chunk demo keeps working with no key/network
    (as in this sandbox). `chunk_id` is only used by the fallback path
    -- a real call only needs `messages`.
    """
    if llm_client.USE_REAL_LLM:
        return llm_client.generate_question_json(messages)

    del messages  # the canned response ignores prompt content entirely
    if chunk_id not in _CANNED_RESPONSES:
        raise NotImplementedError(
            f"No canned LLM response for chunk_id={chunk_id!r} yet. "
            f"Available: {list(_CANNED_RESPONSES.keys())}"
        )
    return _CANNED_RESPONSES[chunk_id]()


# ---------------------------------------------------------------------
# The actual pipeline: chunk_id -> fully scored, validated QuestionOut
# ---------------------------------------------------------------------

def generate_question(chunk_id: str, target_difficulty: int) -> QuestionOut:
    """Full pipeline for one question: build prompt -> call LLM ->
    parse + validate against schema -> compute difficulty_score.

    This is what B3 wires real retrieval into (chunk_id will come from
    A's get_chunks() instead of SAMPLE_CHUNKS), and what B5/B6's
    validation stages wrap with retry logic on Day 5-6. Today (Day 3)
    it proves the chain works at all, on dummy chunks.
    """
    messages = build_messages(chunk_id, target_difficulty)
    raw_response = call_llm(messages, chunk_id)
    question = parse_and_validate(raw_response)
    apply_difficulty_score(question)
    return question


if __name__ == "__main__":
    print("=" * 70)
    print("B2 — END-TO-END GENERATION ON DUMMY CHUNKS")
    print("=" * 70)

    test_cases = [
        ("en_ch12_12-2_p160", 1),
        ("en_ch12_12-3_p162", 2),
        ("en_ch12_12-3_p163", 3),
        ("ar_ch12_12-3_p175", 2),
    ]

    results = []
    for chunk_id, target_difficulty in test_cases:
        print(f"\n--- chunk_id={chunk_id!r}, target_difficulty={target_difficulty} ---")
        question = generate_question(chunk_id, target_difficulty)
        results.append(question)
        print(f"question:         {question.question!r}")
        print(f"topic:            {question.topic}")
        print(f"language:         {question.language}")
        print(f"options:          {len(question.options)} (exactly 1 correct, "
              f"validated by schema)")
        print(f"difficulty_score: {question.difficulty_score}  "
              f"(from sub-scores {question.difficulty.bloom_level}/"
              f"{question.difficulty.distractor_quality}/"
              f"{question.difficulty.concept_depth})")

    print("\n" + "=" * 70)
    print(f"✓ {len(results)}/{len(test_cases)} chunks generated, parsed, "
          f"validated, and scored successfully.")
    print("=" * 70)
