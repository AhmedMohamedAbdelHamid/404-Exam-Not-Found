"""
verify_integration.py — Person A's Day 3 integration verification.

Runs the real end-to-end pipeline (staircase -> chunk_sampler/retrieval
-> generation_agent -> validation_stage2 -> get_next_question) against
the REAL ChromaDB (not B's _MockChunkSampler), for both EN and AR, and
writes a timestamped report to disk so results can be shared with the
team without re-running anything.

Prerequisites (same as any other script in this repo):
  - ./chroma_db must exist and be populated (run embed_to_chroma.py
    first if it doesn't).
  - Run from the project root (same directory as schema.py etc).

Run: python3 verify_integration.py
Output: verification_report_<timestamp>.txt (also prints to console)
"""

import os
import sys
import io
import datetime

from staircase import Staircase
from chunk_sampler import ChunkSampler
from generation_agent import call_llm as generation_stub_call_llm
from validation_stage2 import _always_pass_critique
from get_next_question import get_next_question, record_answer, GenerationUnavailable


class Tee:
    """Writes to both the real stdout and an in-memory buffer, so we
    can print live progress AND save everything to a file afterward."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def run_exam(student_id: str, language: str, answers_pattern: list[bool], sc: Staircase, sampler: ChunkSampler):
    sc.get_or_create_student(student_id, language=language)
    results = []
    question_num = 0
    while True:
        try:
            q = get_next_question(
                student_id=student_id,
                chunk_sampler=sampler,
                generation_call_llm_fn=generation_stub_call_llm,
                critique_call_llm_fn=_always_pass_critique,
                staircase=sc,
            )
        except GenerationUnavailable as e:
            print(f"  Q{question_num + 1}: FAILED -- GenerationUnavailable")
            print(f"      {e}")
            results.append({"status": "failed", "error": str(e)})
            correct = answers_pattern[question_num] if question_num < len(answers_pattern) else True
            record_answer(student_id, correct, staircase=sc)
            question_num += 1
            if question_num >= len(answers_pattern):
                break
            continue

        if q is None:
            print(f"  Exam complete after {question_num} questions.")
            break

        correct = answers_pattern[question_num]
        print(f"  Q{question_num + 1}: topic={q.topic!r:28s} chunk={q.source_chunk_id:22s} "
              f"difficulty_score={q.difficulty_score}  -> {'correct' if correct else 'wrong'}")
        results.append({"status": "ok", "chunk_id": q.source_chunk_id, "topic": q.topic})
        record_answer(student_id, correct, staircase=sc)
        question_num += 1

    return results


def main():
    buffer = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = Tee(real_stdout, buffer)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 70)
    print(f"A's INTEGRATION VERIFICATION REPORT — {timestamp}")
    print("Real ChunkSampler + real ChromaDB wired into B's full pipeline")
    print("(staircase -> retrieval/chunk_sampler -> generation_agent ->")
    print(" validation_stage2 -> get_next_question), not B's mock.")
    print("=" * 70)

    if not os.path.exists("./chroma_db"):
        print("\n✗ ./chroma_db not found. Run embed_to_chroma.py first.")
        sys.stdout = real_stdout
        return

    all_ok = True

    print("\n--- ENGLISH: 3 full exams, different students ---")
    db_path = "verify_en.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    sc = Staircase(db_path=db_path)
    sampler = ChunkSampler()
    en_summary = []
    for i in range(3):
        student_id = f"verify_en_{i}"
        print(f"\nStudent {student_id}:")
        results = run_exam(student_id, "en", [True, True, False, True, False], sc, sampler)
        ok_count = sum(1 for r in results if r["status"] == "ok")
        en_summary.append((student_id, ok_count, len(results)))
        if ok_count != len(results):
            all_ok = False
    sc.close()
    os.remove(db_path)

    print("\n--- ARABIC: 1 full exam ---")
    db_path = "verify_ar.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    sc = Staircase(db_path=db_path)
    sampler = ChunkSampler()
    print("\nStudent verify_ar_0:")
    ar_results = run_exam("verify_ar_0", "ar", [True, False, True, True, False], sc, sampler)
    ar_ok_count = sum(1 for r in ar_results if r["status"] == "ok")
    if ar_ok_count != len(ar_results):
        all_ok = False
    sc.close()
    os.remove(db_path)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for student_id, ok_count, total in en_summary:
        status = "✓ PASS" if ok_count == total else "✗ FAIL"
        print(f"  EN {student_id}: {ok_count}/{total} questions generated  [{status}]")
    ar_status = "✓ PASS" if ar_ok_count == len(ar_results) else "✗ FAIL"
    print(f"  AR verify_ar_0: {ar_ok_count}/{len(ar_results)} questions generated  [{ar_status}]")

    print()
    if all_ok:
        print("✓ ALL TRACKS PASSED — real retrieval fully verified end-to-end.")
    else:
        print("✗ AT LEAST ONE TRACK FAILED — see failures above for details.")
        print("  Known issue as of this script's writing: the AR track fails")
        print("  Stage 1 keyword-overlap validation because generation_agent.py's")
        print("  fallback stub embeds the raw English topic string into Arabic")
        print("  question text. This is a generation-stub bug, not a retrieval")
        print("  bug -- confirmed by inspecting the raw chunk text (on-topic,")
        print("  clean Arabic) vs the raw stub output (English word injected).")
        print("  Fix belongs in generation_agent.py, or resolves automatically")
        print("  once a real GEMINI_API_KEY is set (llm_client.py bypasses the")
        print("  stub entirely).")

    sys.stdout = real_stdout

    out_filename = f"verification_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(out_filename, "w", encoding="utf-8") as f:
        f.write(buffer.getvalue())
    print(f"\nReport saved to: {out_filename}")


if __name__ == "__main__":
    main()
