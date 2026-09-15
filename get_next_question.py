"""
get_next_question.py — B9 deliverable (Day 6 EOD, Person B)
"Final API: get_next_question(student_id)" -- depends on B4
(staircase controller) and B6 (validation + retry). This is the hard
handoff C is waiting on (C5: wire real exam flow to B9; C6: wire real
misconception logging).

--------------------------------------------------------------------
What this ties together (nothing new is implemented here -- this file
is orchestration only, over already-tested pieces):
--------------------------------------------------------------------
  staircase.Staircase        (B4) -- current topic, difficulty, language
  generation_agent           (B3) -- real chunk retrieval via ChunkSampler
  validation_stage2          (B5+B6) -- generate + Stage1 + Stage2 + retry
  A5's backup pool           -- NOT implemented here (Day 6, A+B shared
                                 task per roadmap.md's Full Task List --
                                 A5 depends on A4, "Help B/A generate the
                                 backup question pool"). Both
                                 NoChunkAvailable and
                                 ValidationFailedAfterRetries are the
                                 signal this API's caller (or a wrapper
                                 around this API) should use the backup
                                 pool once it exists -- see
                                 get_next_question()'s docstring.

--------------------------------------------------------------------
Still unverified end-to-end against REAL infrastructure (see B3/B6's
own module docstrings for the itemized reasons -- not repeated here):
  - No live ChromaDB in this sandbox (chunk_sampler/retrieval untested
    against real embeddings).
  - No live LLM API in this sandbox (generation + critique are stand-in
    stubs).
Both are the same call-site-only swap noted in generation_agent.py and
validation_stage2.py -- this file doesn't add new integration risk on
top of what those two already flag.

--------------------------------------------------------------------
Exam-completion handling:
--------------------------------------------------------------------
get_next_question() returns None (not an exception) when the student
has finished all 5 topics (staircase.is_exam_complete() is True) --
this is a normal end state, not a failure, so it's a plain return
value, not an exception.

Run standalone: python3 get_next_question.py
"""

from schema import QuestionOut
from staircase import Staircase
from generation_agent import NoChunkAvailable
from validation_stage2 import generate_validated_question, ValidationFailedAfterRetries
import llm_client


class GenerationUnavailable(Exception):
    """Unified failure signal for B9's caller: either B3 had no chunk
    left (NoChunkAvailable) or B5/B6 validation never passed
    (ValidationFailedAfterRetries). Wraps whichever actually occurred
    so callers only need to catch ONE exception type and fall back to
    the backup pool (A5), rather than knowing about B3/B6's internals.
    The original exception is available as `.__cause__`.
    """
    pass


def get_next_question(
    student_id: str,
    chunk_sampler,
    generation_call_llm_fn,
    critique_call_llm_fn,
    staircase: Staircase | None = None,
) -> QuestionOut | None:
    """The final API. Returns the next validated question for this
    student, or None if they've completed all topics (exam finished).

    Raises GenerationUnavailable if generation/validation could not
    produce a usable question for the student's current topic (no
    chunk left, or validation failed after retries) -- caller should
    fall back to the backup pool (A5) for this topic/difficulty, not
    crash or show an error to the student mid-exam.

    `staircase` can be injected (e.g. a test instance with its own
    throwaway DB file); defaults to a fresh Staircase() using the
    module-level DB_PATH if not given, so most real call sites don't
    need to construct one manually.
    """
    sc = staircase if staircase is not None else Staircase()

    if sc.is_exam_complete(student_id):
        return None

    topic = sc.get_current_topic(student_id)
    language = sc.get_language(student_id)
    difficulty = sc.get_current_difficulty(student_id)

    try:
        question = generate_validated_question(
            student_id=student_id,
            topic=topic,
            language=language,
            target_difficulty=difficulty,
            chunk_sampler=chunk_sampler,
            generation_call_llm_fn=generation_call_llm_fn,
            critique_call_llm_fn=critique_call_llm_fn,
        )
    except (NoChunkAvailable, ValidationFailedAfterRetries) as e:
        raise GenerationUnavailable(
            f"Could not produce a question for student_id={student_id!r}, "
            f"topic={topic!r}, language={language!r}, difficulty={difficulty}. "
            f"Fall back to the backup question pool (A5) for this "
            f"topic/difficulty. Underlying cause: {e}"
        ) from e

    return question


def record_answer(student_id: str, correct: bool, staircase: Staircase | None = None) -> dict:
    """Companion to get_next_question() -- the caller (eventually C,
    Day 7 C5) must call this after the student answers, BEFORE calling
    get_next_question() again, so the staircase (B4) advances
    difficulty and topic correctly. Thin pass-through to
    staircase.Staircase.record_answer(); exists here so B9's public
    surface is self-contained (a caller only needs to import from this
    one file for the whole question<->answer loop) rather than needing
    to know about staircase.py directly.
    """
    sc = staircase if staircase is not None else Staircase()
    return sc.record_answer(student_id, correct)


def real_call_llm_for_generation_agent(messages: list[dict], chunk: dict, target_difficulty: int) -> str:
    """Adapter matching generation_agent.call_llm's 3-arg signature,
    for passing llm_client's real generation function into
    get_next_question() as generation_call_llm_fn. Use this (or just
    generation_agent.call_llm directly, which already checks
    llm_client.USE_REAL_LLM internally) once GEMINI_API_KEY is set.
    """
    del chunk, target_difficulty  # llm_client only needs messages
    return llm_client.generate_question_json(messages)


if __name__ == "__main__":
    import os
    from generation_agent import _MockChunkSampler, call_llm as generation_stub_call_llm
    from validation_stage2 import _always_pass_critique
    import llm_client

    demo_db = "student_state_b9_demo.db"
    if os.path.exists(demo_db):
        os.remove(demo_db)

    print("=" * 70)
    print("B9 — FINAL API: get_next_question(student_id)")
    print("=" * 70)
    print(f"llm_client.USE_REAL_LLM = {llm_client.USE_REAL_LLM} "
          f"(GEMINI_API_KEY {'is' if llm_client.USE_REAL_LLM else 'is NOT'} set)")
    print(
        "NOTE: chunk_sampler is still MOCKED regardless (no live ChromaDB "
        "in this sandbox -- see generation_agent.py's docstring). If a real "
        "key IS set, generation_call_llm_fn below will make REAL Gemini "
        "calls even though retrieval is mocked -- generation_agent.call_llm() "
        "and validation_stage2's critique wiring both check "
        "llm_client.USE_REAL_LLM automatically, so no code change was needed "
        "here to pick up a real key.\n"
    )

    # Real production wiring, once ./chroma_db exists (A's embed_to_chroma.py
    # has been run) and GEMINI_API_KEY is set:
    #
    #   from chunk_sampler import ChunkSampler
    #   real_sampler = ChunkSampler()
    #   q = get_next_question(
    #       student_id=student_id,
    #       chunk_sampler=real_sampler,
    #       generation_call_llm_fn=real_call_llm_for_generation_agent,
    #       critique_call_llm_fn=llm_client.critique_question_json,
    #   )
    #
    # generation_call_llm_fn / critique_call_llm_fn below use the same
    # stub-with-automatic-real-fallback pattern as every other file in
    # this pipeline, so this demo works identically with or without a key.
    critique_fn = llm_client.critique_question_json if llm_client.USE_REAL_LLM else _always_pass_critique

    sc = Staircase(db_path=demo_db)
    sc.get_or_create_student("demo_student", language="en")

    print("--- Full simulated exam run (5 topics, alternating correct/wrong) ---")
    # _MockChunkSampler only has fake chunks for 3 of the 5 real topics
    # (algorithm/en, variables and assignment/en, loops and
    # conditionals/ar) -- this run is EN, so "lists" and "functions"
    # have NO fake chunk available, which deliberately exercises the
    # GenerationUnavailable fallback path mid-exam, not just at the end.
    sampler = _MockChunkSampler()
    answers_pattern = [True, True, False, True, False]

    question_num = 0
    while True:
        try:
            q = get_next_question(
                student_id="demo_student",
                chunk_sampler=sampler,
                generation_call_llm_fn=generation_stub_call_llm,
                critique_call_llm_fn=critique_fn,
                staircase=sc,
            )
        except GenerationUnavailable as e:
            print(f"  Q{question_num + 1}: GenerationUnavailable -- would fall back to "
                  f"backup pool here.\n      ({e})")
            # Simulate the exam continuing via a backup-pool question by
            # still recording an answer and advancing state, since A5
            # doesn't exist yet to actually supply one.
            correct = answers_pattern[question_num]
            record_answer("demo_student", correct, staircase=sc)
            question_num += 1
            if question_num >= 5:
                break
            continue

        if q is None:
            print(f"  Exam complete after {question_num} questions.")
            break

        correct = answers_pattern[question_num]
        print(f"  Q{question_num + 1}: topic={q.topic!r:28s} difficulty_score={q.difficulty_score}  "
              f"validated={q.validated}  -> answering {'correct' if correct else 'wrong'}")
        record_answer("demo_student", correct, staircase=sc)
        question_num += 1

    final_state = sc.get_or_create_student("demo_student")
    print(f"\nFinal state: {final_state}")
    assert final_state["questions_answered"] == 5

    print("\n--- Confirm exam-complete returns None, not an exception ---")
    result = get_next_question(
        student_id="demo_student", chunk_sampler=sampler,
        generation_call_llm_fn=generation_stub_call_llm,
        critique_call_llm_fn=critique_fn, staircase=sc,
    )
    print(f"  get_next_question() after exam complete -> {result}")
    assert result is None

    sc.close()
    os.remove(demo_db)
    print("\n✓ All B9 orchestration checks passed.")
