"""
validation_stage2.py — B6 deliverable (Day 6, Person B)
"Validation Stage 2 (LLM self-critique, retry <=2)" per README 3.3:
  - "Is exactly one option unambiguously correct per the source?"
  - "Is the correct answer directly supported by the chunk, not
     outside knowledge?"
  If either check fails: regenerate (max 2 retries), then fall back to
  the backup pool (A5) -- never let a live demo hit a generation
  failure with no fallback.

--------------------------------------------------------------------
Same LLM-availability caveat as generate.py / generation_agent.py:
--------------------------------------------------------------------
No live LLM is reachable from this sandbox. critique_question()'s
call_llm_fn parameter has the real signature a live critique call
needs ((messages) -> str), and CANNED_CRITIQUE_STUB below is a stand-in
used only for testing this module's own retry-orchestration logic
(does the loop actually retry, cap at max_retries, and propagate the
right failure -- not "does a real LLM correctly judge correctness").
Swap the stub for a real call before Day 6 sync / demo.

--------------------------------------------------------------------
Retry design decision (README says "regenerate", doesn't specify
whether a retry re-pulls a new chunk or reuses the same one):
--------------------------------------------------------------------
This module reuses the SAME retrieved chunk across all retry attempts
for one question slot, and only regenerates the LLM call. Rationale:
if the chunk were bad, chunk_sampler wouldn't have anything better to
offer anyway (same topic/language, next call just burns through the
student's anti-cheat "seen" budget for no benefit); the actual failure
being retried is almost always a generation-quality problem (bad
distractor, ungrounded claim), not a chunk problem. If the team wants
"regenerate" to mean "try a different chunk too," that's a one-line
change (move the chunk_sampler call inside the retry loop) -- flagged
here as a decision made, not hidden.

Run standalone: python3 validation_stage2.py
"""

import json

from schema import QuestionOut
from difficulty_scorer import apply_difficulty_score
from prompt_template import build_messages_from_chunk, parse_and_validate
from validation_stage1 import run_stage1
from generation_agent import NoChunkAvailable

MAX_RETRIES = 2  # per README 3.3: "regenerate (max 2 retries)"


class ValidationFailedAfterRetries(Exception):
    """Raised when a question fails Stage 1 or Stage 2 on every
    attempt (1 initial + MAX_RETRIES retries). Caller (B9) should
    treat this exactly like NoChunkAvailable: fall back to the backup
    question pool (A5) -- never surface a generation failure to a
    live student with no fallback (README 3.3's explicit demo-safety
    requirement).
    """
    def __init__(self, topic: str, language: str, attempts: int, last_reasons: list[str]):
        self.topic = topic
        self.language = language
        self.attempts = attempts
        self.last_reasons = last_reasons
        super().__init__(
            f"Question generation for topic={topic!r} language={language!r} "
            f"failed validation after {attempts} attempts. Caller should fall "
            f"back to the backup question pool (A5). Last failure reasons: "
            f"{last_reasons}"
        )


CRITIQUE_PROMPT_TEMPLATE = """You are reviewing a generated multiple-choice question for \
correctness against its source material. Answer ONLY with JSON, no other text.

Source chunk:
\"\"\"
{chunk_text}
\"\"\"

Generated question: {question}
Options:
{options_block}
Marked correct answer: {correct_answer}

Answer these two questions:
1. Is exactly one option unambiguously correct according to the source chunk above \
(not just structurally -- is it actually, factually the one right answer)?
2. Is the correct answer directly supported by the chunk's content, without relying \
on outside knowledge not present in the chunk?

Respond with exactly this JSON shape:
{{"exactly_one_correct": true|false, "supported_by_chunk": true|false, "reasoning": "<one sentence>"}}"""


def build_critique_messages(question: QuestionOut, chunk_text: str) -> list[dict]:
    options_block = "\n".join(
        f"  - {opt.text}" + (" [marked correct]" if opt.correct else "")
        for opt in question.options
    )
    correct_answer = next(opt.text for opt in question.options if opt.correct)
    prompt = CRITIQUE_PROMPT_TEMPLATE.format(
        chunk_text=chunk_text,
        question=question.question,
        options_block=options_block,
        correct_answer=correct_answer,
    )
    return [{"role": "user", "content": prompt}]


def critique_question(question: QuestionOut, chunk_text: str, call_llm_fn) -> tuple[bool, str]:
    """Runs the Stage 2 self-critique. call_llm_fn's real signature is
    (messages: list[dict]) -> str (a raw LLM call) -- same shape as
    generate.py/generation_agent.py's call_llm stand-ins, so swapping
    in a real API call is a one-line change at the call site, not here.
    Returns (passed, reasoning).
    """
    messages = build_critique_messages(question, chunk_text)
    raw = call_llm_fn(messages)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        return False, f"Critique response was not valid JSON: {e}"

    exactly_one = result.get("exactly_one_correct", False)
    supported = result.get("supported_by_chunk", False)
    reasoning = result.get("reasoning", "(no reasoning given)")

    passed = bool(exactly_one) and bool(supported)
    return passed, reasoning


def generate_validated_question(
    student_id: str,
    topic: str,
    language: str,
    target_difficulty: int,
    chunk_sampler,
    generation_call_llm_fn,
    critique_call_llm_fn,
    max_retries: int = MAX_RETRIES,
) -> QuestionOut:
    """The full B3+B5+B6 pipeline for one question slot: pull one real
    chunk (B3, via chunk_sampler), generate + validate against Stage 1
    (B5) and Stage 2 (B6), retrying generation up to max_retries times
    against the SAME chunk if either stage fails, and raising
    ValidationFailedAfterRetries if it never passes both.

    Raises NoChunkAvailable (propagated from B3) if chunk_sampler has
    nothing left for this topic/language/student -- same fallback
    policy as a validation failure: caller should use the backup pool.

    generation_call_llm_fn / critique_call_llm_fn are injected so this
    function has no hard dependency on any particular stand-in or real
    LLM client -- generate.py/generation_agent.py's call_llm and this
    module's critique_question expect the real signature
    (messages: list[dict]) -> str.
    """
    chunk = chunk_sampler.get_unseen_chunk(student_id, topic, language)
    if chunk is None:
        raise NoChunkAvailable(topic, language, student_id)

    last_reasons: list[str] = []
    attempts = 0

    for attempt_num in range(max_retries + 1):  # 1 initial + max_retries retries
        attempts += 1
        messages = build_messages_from_chunk(chunk, target_difficulty)
        raw_response = generation_call_llm_fn(messages, chunk, target_difficulty)

        stage1_passed, question, stage1_reasons = run_stage1(raw_response, chunk["text"])
        if not stage1_passed:
            last_reasons = [f"attempt {attempt_num + 1}: Stage 1 failed"] + stage1_reasons
            continue

        stage2_passed, stage2_reasoning = critique_question(question, chunk["text"], critique_call_llm_fn)
        if not stage2_passed:
            last_reasons = [f"attempt {attempt_num + 1}: Stage 2 failed -- {stage2_reasoning}"]
            continue

        # Both stages passed.
        question.validated = True
        question.regeneration_count = attempt_num
        apply_difficulty_score(question)
        return question

    raise ValidationFailedAfterRetries(topic, language, attempts, last_reasons)


# ---------------------------------------------------------------------
# Test stand-ins (NOT real LLM calls -- see module docstring)
# ---------------------------------------------------------------------

def _always_pass_critique(messages: list[dict]) -> str:
    del messages
    return json.dumps({
        "exactly_one_correct": True,
        "supported_by_chunk": True,
        "reasoning": "[STUB] canned pass response for testing.",
    })


def _always_fail_critique(messages: list[dict]) -> str:
    del messages
    return json.dumps({
        "exactly_one_correct": False,
        "supported_by_chunk": False,
        "reasoning": "[STUB] canned fail response for testing retry exhaustion.",
    })


class _FlakyCritique:
    """Fails the first N calls, then passes -- used to prove the retry
    loop actually re-invokes generation+critique and succeeds once the
    'LLM' gets it right, rather than just fast-pathing on attempt 1."""
    def __init__(self, fail_count: int):
        self.fail_count = fail_count
        self.calls = 0

    def __call__(self, messages: list[dict]) -> str:
        self.calls += 1
        if self.calls <= self.fail_count:
            return _always_fail_critique(messages)
        return _always_pass_critique(messages)


if __name__ == "__main__":
    from generation_agent import _MockChunkSampler, call_llm as generation_stub_call_llm

    print("=" * 70)
    print("B6 — VALIDATION STAGE 2 + RETRY ORCHESTRATION")
    print("=" * 70)
    print("NOTE: using stub critique/generation LLM calls, not a real API --")
    print("see module docstring for why. This proves the RETRY LOGIC works,")
    print("not that a real LLM's judgment is correct.\n")

    print("--- Case 1: critique passes on first attempt (regeneration_count should be 0) ---")
    sampler = _MockChunkSampler()
    q = generate_validated_question(
        student_id="student_A", topic="algorithm", language="en",
        target_difficulty=2, chunk_sampler=sampler,
        generation_call_llm_fn=generation_stub_call_llm,
        critique_call_llm_fn=_always_pass_critique,
    )
    print(f"  validated={q.validated}, regeneration_count={q.regeneration_count}")
    assert q.validated and q.regeneration_count == 0

    print("\n--- Case 2: critique fails twice, then passes on the 3rd (final) attempt ---")
    print("    (proves retry loop actually retries, not just checks once)")
    sampler2 = _MockChunkSampler()
    flaky = _FlakyCritique(fail_count=2)
    q2 = generate_validated_question(
        student_id="student_B", topic="variables and assignment", language="en",
        target_difficulty=1, chunk_sampler=sampler2,
        generation_call_llm_fn=generation_stub_call_llm,
        critique_call_llm_fn=flaky,
    )
    print(f"  validated={q2.validated}, regeneration_count={q2.regeneration_count}, "
          f"critique was called {flaky.calls} times")
    assert q2.validated and q2.regeneration_count == 2
    assert flaky.calls == 3

    print("\n--- Case 3: critique ALWAYS fails -> exhausts all retries -> raises ---")
    sampler3 = _MockChunkSampler()
    try:
        generate_validated_question(
            student_id="student_C", topic="loops and conditionals", language="ar",
            target_difficulty=3, chunk_sampler=sampler3,
            generation_call_llm_fn=generation_stub_call_llm,
            critique_call_llm_fn=_always_fail_critique,
        )
        print("  ✗ FAILED: expected ValidationFailedAfterRetries, nothing was raised")
    except ValidationFailedAfterRetries as e:
        print(f"  ✓ Correctly raised after {e.attempts} attempts (1 initial + {MAX_RETRIES} retries)")
        print(f"    Last reasons: {e.last_reasons}")
        assert e.attempts == MAX_RETRIES + 1

    print("\n--- Case 4: no chunk available at all -> NoChunkAvailable propagates from B3 ---")
    sampler4 = _MockChunkSampler()
    try:
        generate_validated_question(
            student_id="student_D", topic="functions", language="en",
            target_difficulty=2, chunk_sampler=sampler4,
            generation_call_llm_fn=generation_stub_call_llm,
            critique_call_llm_fn=_always_pass_critique,
        )
        print("  ✗ FAILED: expected NoChunkAvailable, nothing was raised")
    except NoChunkAvailable as e:
        print(f"  ✓ Correctly raised NoChunkAvailable (B3's exception propagated through B6): {e}")

    print("\n✓ All B6 validation-stage-2 + retry-orchestration checks passed.")
