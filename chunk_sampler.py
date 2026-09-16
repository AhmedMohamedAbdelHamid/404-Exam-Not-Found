"""
chunk_sampler.py — A4 deliverable (roadmap deadline: Day 5; started
Day 3 since A2/A3 landed early).

"Per-student chunk sampling (anti-cheat layer 1)" -- roadmap.md's own
description. The concrete problem this solves: without this, two
students on the same topic/language/difficulty would very likely get
the SAME source chunk from get_chunks() (topics have only ~4-6 chunks
each), so if they compare notes/screens, their questions could be
suspiciously similar or identical. This also stops ONE student from
seeing the same chunk twice across their own exam if they revisit a
topic (e.g. after answering wrong and getting bumped back down by B4's
staircase controller).

--------------------------------------------------------------------
Design note -- why this is a standalone in-memory tracker, not SQLite:
--------------------------------------------------------------------
B4 (staircase controller, SQLite-backed student state) is a Day-4
task and doesn't exist in the repo yet. Rather than guess B's schema
or bolt a second, possibly-conflicting SQLite table onto the project
today, this module owns its OWN minimal state (student_id -> set of
seen chunk_ids) behind a small interface. It works standalone today
(proven in the __main__ demo below) and is trivially backed by a real
table later -- swap ChunkSampler's storage for SQLite reads/writes
without changing its public methods, once B4 exists and the team
decides whether chunk-history lives in B's DB or a separate one.

--------------------------------------------------------------------
What this does NOT solve (be honest about scope):
--------------------------------------------------------------------
This prevents SAME-STUDENT chunk reuse (a student won't see the same
chunk twice across their own exam). It does NOT, by itself, guarantee
two DIFFERENT students get different chunks on the same topic -- with
only 1-4 low-exercise-density chunks per topic (see exercise_density_score filtering in
retrieval.py) and a class-sized cohort, students WILL end up sharing
source chunks, especially once everyone's seen the same 3. If two
students who happen to share a chunk also happen to get similar
target_difficulty from B4's staircase controller, their generated
questions could look suspiciously alike. Verified empirically in the
__main__ demo below: two students queried back-to-back on the same
topic get the SAME top chunk today, because nothing here randomizes
or diversifies ACROSS students, only within one student's own history.

If real cross-student anti-cheat (not just same-student non-repetition)
is actually required for the demo/rubric, options to raise with the
team, not decided unilaterally here:
  1. Round-robin/hash-based chunk assignment across concurrent
     students on the same topic (needs a shared, not per-instance,
     seen-set -- see persistence note above).
  2. Accept the current scope (same-student only) as "anti-cheat
     layer 1" literally, per roadmap.md's own phrase, and treat full
     cross-student diversity as a stretch goal given only 3-6 usable
     chunks per topic in the source material.
This module implements option 2 today. Flag to B/C if option 1 is
actually needed before Day 5.

Run standalone: python3 chunk_sampler.py
"""

from retrieval import get_chunks


class ChunkSampler:
    """Tracks which chunk_ids each student has already been served,
    per topic+language, and asks get_chunks() to exclude them on the
    next request. One instance is meant to live for the duration of
    the exam session (or be re-hydrated from real persistence once B4
    exists)."""

    def __init__(self):
        # student_id -> set of chunk_ids already served (any topic)
        self._seen: dict[str, set[str]] = {}

    def get_unseen_chunk(
        self, student_id: str, topic: str, language: str, difficulty: int | None = None
    ) -> dict | None:
        """Return one chunk for this topic/language that this student
        has not been served before, and record it as seen. Returns
        None if every chunk for this topic/language has already been
        shown to this student -- the caller (B's generation agent)
        should treat that as "fall back to the backup pool" (A5),
        same as get_chunks() returning [] for an unknown topic.
        """
        already_seen = self._seen.setdefault(student_id, set())

        # Ask for a few candidates, not just one -- if the top pick
        # happens to already be seen, we can fall through to the next
        # without a second round-trip. get_chunks() already sorts by
        # exercise_density_score, so candidates arrive best-first.
        candidates = get_chunks(
            topic, language, difficulty=difficulty, n=6,
            exclude_chunk_ids=list(already_seen),
        )

        if not candidates:
            return None

        chosen = candidates[0]
        already_seen.add(chosen["chunk_id"])
        return chosen

    def reset_student(self, student_id: str) -> None:
        """Clear a student's seen-chunk history -- e.g. for a fresh
        exam attempt/retake."""
        self._seen.pop(student_id, None)

    def seen_count(self, student_id: str) -> int:
        return len(self._seen.get(student_id, set()))


if __name__ == "__main__":
    sampler = ChunkSampler()

    print("=" * 70)
    print("Same student, same topic, called repeatedly -- should never repeat")
    print("=" * 70)
    for i in range(5):
        chunk = sampler.get_unseen_chunk("student_A", "loops and conditionals", "ar")
        if chunk:
            print(f"  call {i+1}: {chunk['chunk_id']} (exercise_density={chunk['exercise_density_score']})")
        else:
            print(f"  call {i+1}: None -- all chunks for this topic exhausted for student_A")

    print(f"\nstudent_A has now seen {sampler.seen_count('student_A')} chunks for this topic")

    print("\n" + "=" * 70)
    print("Two different students, same topic, SAME sampler instance --")
    print("this is the anti-cheat case that matters: does A give a")
    print("different chunk to a second student on the same topic?")
    print("=" * 70)
    c1 = sampler.get_unseen_chunk("student_B", "functions", "en")
    c2 = sampler.get_unseen_chunk("student_C", "functions", "en")
    print(f"  student_B got: {c1['chunk_id'] if c1 else None}")
    print(f"  student_C got: {c2['chunk_id'] if c2 else None}")
    print("  (NOT necessarily different -- see CRITICAL DEPLOYMENT NOTE")
    print("  in the module docstring: exclusion is per-student only by")
    print("  design here, cross-student variety is NOT this module's job)")

    print("\n" + "=" * 70)
    print("reset_student() clears history")
    print("=" * 70)
    sampler.reset_student("student_A")
    print(f"  student_A seen count after reset: {sampler.seen_count('student_A')}")
