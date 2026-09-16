"""
validation_stage1.py — B5 deliverable (Day 5, Person B)
"Validation Stage 1 (rule-based checks)" per README 3.3:
  - Exactly one option marked correct: true
  - All 4 options non-empty and distinct
  - Keyword overlap check: question concepts appear in the retrieved chunk

--------------------------------------------------------------------
Where each check actually lives:
--------------------------------------------------------------------
The first two checks are ALREADY enforced by schema.py's
QuestionOut.exactly_one_correct field_validator, which runs at parse
time inside prompt_template.parse_and_validate() -- a QuestionOut
object cannot exist in memory without having already passed them
(Pydantic raises ValueError during construction otherwise). So this
module's real, new contribution is the keyword-overlap check, plus a
single entry point (run_stage1) that safely handles BOTH a malformed
raw LLM response (schema/parse failure) and a well-formed-but-
ungrounded one (keyword overlap failure) with one consistent
(passed, reasons) result -- this is what B6's retry loop and B9 call,
they don't call parse_and_validate directly.

--------------------------------------------------------------------
Keyword overlap check -- design notes (a heuristic, not semantic NLP,
matching README 3.3's own framing of Stage 1 as "cheap"):
--------------------------------------------------------------------
Extracts "significant words" from the question text + the correct
option's text (the part that most needs to be grounded), lowercases,
strips a small English stopword list and short tokens, then checks
what fraction of those tokens appear verbatim in the source chunk
text. Code-like tokens (identifiers, keywords such as "range",
"print", "elif") are treated as strong signal and never stopworded.

Language handling: this only applies English stopwording. For Arabic
questions, no stopword filtering is applied (every token >= 3 chars is
checked) -- filtering Arabic function words correctly needs a vetted
Arabic stopword list this project doesn't have yet; skipping the
filter is the safer default (a slightly stricter check) rather than
guessing at Arabic stopwords and filtering wrong. Flagged here as a
known gap, not fixed silently.

Threshold: passes if >= MIN_OVERLAP_RATIO of extracted keywords are
found in the chunk, OR at least one exact code-identifier match is
found (code overlap is a strong grounding signal on its own even if
prose overlap is low, e.g. a question built almost entirely around a
literal code snippet).

Run standalone: python3 validation_stage1.py
"""

import re
from schema import QuestionOut
from prompt_template import parse_and_validate

MIN_OVERLAP_RATIO = 0.3
MIN_TOKEN_LENGTH = 3

# Small, generic English stopword list -- deliberately not exhaustive.
# Purpose is only to stop trivially common words (what/does/the/this)
# from diluting the overlap ratio, not to do real linguistic filtering.
#
# IMPORTANT: this list deliberately EXCLUDES words that double as
# Python keywords (for, in, is, and, or, as, not, with, from, if,
# else, elif, while, import, return, ...) even though they're also
# common English function words -- stopwording them would strip out
# exactly the code vocabulary this check most needs to catch on a
# programming-content course. Caught via the Case 1 test below, which
# originally extracted only 1 keyword ("range") because "for" was
# being silently stopworded out of a for-loop question.
_EN_STOPWORDS = {
    "the", "a", "an", "was", "were", "does", "do", "did",
    "what", "which", "who", "how", "why", "when", "where", "this",
    "that", "these", "those", "but", "of", "to",
    "on", "at", "by", "it", "its",
    "be", "been", "being", "has", "have", "had", "will", "would",
    "can", "could", "should", "following", "code", "output", "print",
}
# NOTE: "print" is deliberately NOT in the exclusion for code-token
# matching below -- it's stopworded only for the PROSE overlap ratio,
# since "print" is common English but also a real Python keyword.
# The code-token check (regex below) still counts it independently.

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_CODE_TOKEN_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _extract_keywords(question: QuestionOut) -> list[str]:
    correct_option_text = next(
        (opt.text for opt in question.options if opt.correct), ""
    )
    combined = f"{question.question} {correct_option_text}"
    tokens = _tokenize(combined)

    if question.language.value == "en":
        tokens = [t for t in tokens if t not in _EN_STOPWORDS]

    tokens = [t for t in tokens if len(t) >= MIN_TOKEN_LENGTH]
    return tokens


def _extract_code_identifiers(text: str) -> set[str]:
    """Pulls out things that look like code identifiers/keywords
    (alphanumeric+underscore runs of 3+ chars) from question text --
    used as a strong independent grounding signal."""
    return {
        m.group(0).split("(")[0].strip()
        for m in _CODE_TOKEN_RE.finditer(text)
        if len(m.group(0).split("(")[0].strip()) >= MIN_TOKEN_LENGTH
    }


def check_keyword_overlap(question: QuestionOut, chunk_text: str) -> tuple[bool, str]:
    """Returns (passed, reason). See module docstring for the heuristic."""
    keywords = _extract_keywords(question)
    if not keywords:
        # Degenerate case (e.g. question is only symbols/numbers) --
        # can't meaningfully fail this on emptiness, so treat as pass
        # with a note, rather than blocking on a check that has
        # nothing to check.
        return True, "No extractable keywords to check (question too short/symbolic) -- treated as pass."

    chunk_lower = chunk_text.lower()
    found = [k for k in keywords if k in chunk_lower]
    ratio = len(found) / len(keywords)

    code_identifiers = _extract_code_identifiers(question.question)
    code_overlap = code_identifiers & _extract_code_identifiers(chunk_text)

    if ratio >= MIN_OVERLAP_RATIO:
        return True, f"Keyword overlap {ratio:.0%} ({len(found)}/{len(keywords)}) >= {MIN_OVERLAP_RATIO:.0%} threshold."
    if code_overlap:
        return True, f"Prose overlap {ratio:.0%} below threshold, but code identifier(s) {code_overlap} matched chunk -- treated as grounded."
    return False, (
        f"Keyword overlap only {ratio:.0%} ({len(found)}/{len(keywords)}: {found}) "
        f"< {MIN_OVERLAP_RATIO:.0%} threshold, and no code identifiers matched. "
        f"Question may not be grounded in the retrieved chunk (possible hallucination)."
    )


def run_stage1(raw_llm_response: str, chunk_text: str) -> tuple[bool, QuestionOut | None, list[str]]:
    """Single entry point B6/B9 should call. Handles BOTH failure modes:
      1. Malformed/schema-invalid JSON (parse_and_validate raises) --
         caught here, returned as a stage1 failure, not an exception.
      2. Well-formed but ungrounded question (keyword overlap fails).

    Returns (passed, question_or_None, reasons). `question` is None
    only on failure mode 1 (nothing valid to return); on failure mode
    2, the (invalid-per-Stage-1) QuestionOut is still returned so the
    caller can inspect it (e.g. for logging) even though passed=False.
    """
    reasons = []
    try:
        question = parse_and_validate(raw_llm_response)
    except Exception as e:
        return False, None, [f"Schema/parse validation failed: {e}"]

    # exactly-one-correct + distinct/non-empty are already guaranteed
    # by the successful parse above (schema.py's field_validator) --
    # noted here explicitly so it's clear these aren't silently skipped,
    # just already enforced earlier in the pipeline.
    reasons.append("Exactly-one-correct-option check: passed (enforced by schema parse).")
    reasons.append("Distinct/non-empty options check: passed (enforced by schema parse).")

    overlap_passed, overlap_reason = check_keyword_overlap(question, chunk_text)
    reasons.append(f"Keyword overlap check: {'passed' if overlap_passed else 'FAILED'} -- {overlap_reason}")

    return overlap_passed, question, reasons


if __name__ == "__main__":
    print("=" * 70)
    print("B5 — VALIDATION STAGE 1 (rule-based checks)")
    print("=" * 70)

    real_chunk_text = (
        "A for statement repeats a process. Syntax: "
        "for variable in range([range]): [process to repeat]. "
        "range(start, end, step): variable increases by step, from "
        "start up to end - step. Example -- displays odd numbers from "
        "1 to 5: for i in range(1, 7, 2): print(i) -> Output: 1 3 5"
    )

    print("\n--- Case 1: well-grounded question (from prompt_template.py's own canned response) ---")
    from prompt_template import _simulated_llm_response_for_for_loop_chunk
    passed, q, reasons = run_stage1(_simulated_llm_response_for_for_loop_chunk(), real_chunk_text)
    print(f"passed={passed}")
    for r in reasons:
        print(f"  - {r}")
    assert passed, "Expected well-grounded question to pass stage 1"

    print("\n--- Case 2: hallucinated question (talks about something NOT in the chunk) ---")
    import json
    hallucinated = json.dumps({
        "question": "What is the boiling point of water at sea level in Celsius?",
        "topic": "loops and conditionals",
        "language": "en",
        "chunk_type": "code_block",
        "source_chunk_id": "en_ch12_12-3_p162",
        "options": [
            {"text": "100", "correct": True, "misconception": None},
            {"text": "90", "correct": False, "misconception": "confuses with a different reference point"},
            {"text": "0", "correct": False, "misconception": "confuses with freezing point"},
            {"text": "212", "correct": False, "misconception": "uses Fahrenheit instead of Celsius"},
        ],
        "difficulty": {
            "bloom_level": 1, "bloom_justification": "recall",
            "distractor_quality": 2, "distractor_justification": "plausible unit confusion",
            "concept_depth": 1, "concept_depth_justification": "single fact",
        },
    })
    passed2, q2, reasons2 = run_stage1(hallucinated, real_chunk_text)
    print(f"passed={passed2}")
    for r in reasons2:
        print(f"  - {r}")
    assert not passed2, "Expected hallucinated (off-topic) question to FAIL stage 1"

    print("\n--- Case 3: malformed JSON (missing required field) -> should fail cleanly, not crash ---")
    malformed = json.dumps({"question": "incomplete", "topic": "loops and conditionals"})
    passed3, q3, reasons3 = run_stage1(malformed, real_chunk_text)
    print(f"passed={passed3}, question_returned={q3}")
    for r in reasons3:
        print(f"  - {r}")
    assert not passed3 and q3 is None, "Expected malformed JSON to fail with question=None"

    print("\n--- Case 4: Arabic well-grounded question (no stopword filtering applied) ---")
    from prompt_template import _simulated_llm_response_for_for_loop_chunk_ar
    ar_chunk_text = (
        "جملة for تكرر عملية ما. الصيغة: for variable in range([range]): "
        "مثال -- يعرض أرقاماً فردية من 1 إلى 5: for i in range(1, 7, 2): "
        "print(i) -> النتيجة: 1 3 5"
    )
    passed4, q4, reasons4 = run_stage1(_simulated_llm_response_for_for_loop_chunk_ar(), ar_chunk_text)
    print(f"passed={passed4}")
    for r in reasons4:
        print(f"  - {r}")
    assert passed4, "Expected well-grounded Arabic question to pass stage 1"

    print("\n✓ All B5 stage-1 validation checks passed.")
