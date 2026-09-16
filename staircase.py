"""
staircase.py — B4 deliverable (Day 4, Person B)
"Staircase controller (SQLite state, ±1, min/max)"

Per-student state, persisted in SQLite:
  - current_difficulty (1-5, ±1 per answer, clamped)
  - topic_index (which topic in the curriculum they're on)
  - language (fixed once, per schema.py's LanguageEnum)
  - questions_answered / correct_count (for the misconception dashboard's
    per-student summary, and so record_answer's return value is useful
    to a caller without a second query)

--------------------------------------------------------------------
Topic-selection policy (not specified anywhere in roadmap.md/README.md
-- this is a real design decision, made here, flagged for team review):
--------------------------------------------------------------------
get_next_question(student_id) in B9 needs SOME way to pick a topic --
the roadmap's signature takes only student_id, no topic argument. This
module implements: ONE question per topic, topics visited in curriculum
order (matching the textbook's own chapter structure, Ch.12 sections
12-1 through 12-5), topic advances every time record_answer() is
called (regardless of correct/incorrect).

This gives a 5-question exam (5 topics = 5 questions), which matches
what C's app.py sidebar already says ("Five-question assessment") and
C's dummy_data.py fixture count (5 fixtures) -- strong signal this is
the intended shape, not just a guess. Topic order used:
    algorithm -> variables and assignment -> loops and conditionals ->
    lists -> functions
(source: chunks_en.json / chunks_ar.json topic tags, ordered to match
the textbook's 12-1 through 12-5 section sequence.)

If the team wants a different policy (e.g. student picks topic order,
or a topic can appear more than once), only TOPIC_ORDER and
advance_topic()'s increment logic below need to change -- nothing else
in B3/B5/B6/B9 depends on the specific policy, only on
get_current_topic() returning *some* valid topic string or None.

--------------------------------------------------------------------
Starting difficulty: defaults to 3 (middle of the 1-5 range), matching
common adaptive-testing convention (start at "average", adjust from
there). Not specified in roadmap.md/README.md -- flagged as a default,
not a requirement.
--------------------------------------------------------------------

Run standalone: python3 staircase.py
"""

import sqlite3
from contextlib import contextmanager

from difficulty_scorer import MIN_DIFFICULTY, MAX_DIFFICULTY

DB_PATH = "student_state.db"

STARTING_DIFFICULTY = 3

TOPIC_ORDER = [
    "algorithm",
    "variables and assignment",
    "loops and conditionals",
    "lists",
    "functions",
]


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_state (
            student_id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            current_difficulty INTEGER NOT NULL,
            topic_index INTEGER NOT NULL DEFAULT 0,
            questions_answered INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


class Staircase:
    """One instance wraps one SQLite connection. Safe to construct
    fresh per request (e.g. one per Streamlit session/request) -- state
    lives in the DB file, not in the instance."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn = _connect(db_path)

    @contextmanager
    def _cursor(self):
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        finally:
            cur.close()

    def get_or_create_student(self, student_id: str, language: str = "en") -> dict:
        """Fetch existing state, or create a fresh row with defaults.
        `language` is only used on first creation -- per schema.py,
        language is fixed once per student and never changed here.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM student_state WHERE student_id = ?", (student_id,)
            )
            row = cur.fetchone()
            if row is not None:
                return dict(row)

            cur.execute(
                """
                INSERT INTO student_state
                    (student_id, language, current_difficulty, topic_index,
                     questions_answered, correct_count)
                VALUES (?, ?, ?, 0, 0, 0)
                """,
                (student_id, language, STARTING_DIFFICULTY),
            )
            cur.execute(
                "SELECT * FROM student_state WHERE student_id = ?", (student_id,)
            )
            return dict(cur.fetchone())

    def get_current_topic(self, student_id: str) -> str | None:
        """The topic the student's NEXT question should come from, or
        None if they've completed every topic (exam finished)."""
        state = self.get_or_create_student(student_id)
        idx = state["topic_index"]
        if idx >= len(TOPIC_ORDER):
            return None
        return TOPIC_ORDER[idx]

    def get_current_difficulty(self, student_id: str) -> int:
        return self.get_or_create_student(student_id)["current_difficulty"]

    def get_language(self, student_id: str) -> str:
        return self.get_or_create_student(student_id)["language"]

    def is_exam_complete(self, student_id: str) -> bool:
        return self.get_current_topic(student_id) is None

    def record_answer(self, student_id: str, correct: bool) -> dict:
        """Apply the staircase rule (correct -> +1 capped at MAX_DIFFICULTY;
        wrong -> -1 capped at MIN_DIFFICULTY), advance to the next topic,
        and update the answered/correct counters. Returns the updated
        state dict. Call this once per answer, before the next
        get_next_question() call for this student.
        """
        state = self.get_or_create_student(student_id)

        new_difficulty = state["current_difficulty"] + (1 if correct else -1)
        new_difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_difficulty))

        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE student_state
                SET current_difficulty = ?,
                    topic_index = topic_index + 1,
                    questions_answered = questions_answered + 1,
                    correct_count = correct_count + (?)
                WHERE student_id = ?
                """,
                (new_difficulty, 1 if correct else 0, student_id),
            )
            cur.execute(
                "SELECT * FROM student_state WHERE student_id = ?", (student_id,)
            )
            return dict(cur.fetchone())

    def reset_student(self, student_id: str) -> None:
        """Wipe a student's state entirely -- e.g. for a fresh retake."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM student_state WHERE student_id = ?", (student_id,))

    def close(self) -> None:
        self._conn.close()


if __name__ == "__main__":
    import os

    # Use a throwaway DB file for the demo so repeated runs start clean.
    demo_path = "student_state_demo.db"
    if os.path.exists(demo_path):
        os.remove(demo_path)

    sc = Staircase(db_path=demo_path)

    print("=" * 70)
    print("New student -- defaults")
    print("=" * 70)
    state = sc.get_or_create_student("student_001", language="en")
    print(f"  {state}")
    assert state["current_difficulty"] == STARTING_DIFFICULTY
    assert state["topic_index"] == 0

    print("\n" + "=" * 70)
    print("Full 5-question run: alternating correct/incorrect")
    print("=" * 70)
    answers = [True, True, False, True, False]
    for i, correct in enumerate(answers):
        topic = sc.get_current_topic("student_001")
        difficulty = sc.get_current_difficulty("student_001")
        print(f"  Q{i+1}: topic={topic!r:30s} difficulty={difficulty}  -> "
              f"answering {'correct' if correct else 'wrong'}")
        sc.record_answer("student_001", correct)

    print(f"\n  Exam complete? {sc.is_exam_complete('student_001')}")
    print(f"  Next topic (should be None): {sc.get_current_topic('student_001')}")
    final = sc.get_or_create_student("student_001")
    print(f"  Final state: {final}")
    assert sc.is_exam_complete("student_001")
    assert final["questions_answered"] == 5
    assert final["correct_count"] == 3

    print("\n" + "=" * 70)
    print("Difficulty clamping: all-correct run should cap at MAX_DIFFICULTY")
    print("=" * 70)
    sc.reset_student("student_002")
    sc.get_or_create_student("student_002", language="ar")
    for i in range(5):
        d = sc.get_current_difficulty("student_002")
        sc.record_answer("student_002", correct=True)
        print(f"  after correct answer {i+1}: difficulty was {d}, now "
              f"{sc.get_current_difficulty('student_002') if not sc.is_exam_complete('student_002') else '(exam complete)'}")
    # started at 3, +1 four times before exam completes on the 5th =
    # 3,4,5,5 (capped) -- topic runs out before difficulty would matter more
    final2 = sc.get_or_create_student("student_002")
    print(f"  Final state: {final2}")
    assert final2["current_difficulty"] <= MAX_DIFFICULTY

    print("\n" + "=" * 70)
    print("reset_student() clears state entirely")
    print("=" * 70)
    sc.reset_student("student_001")
    fresh = sc.get_or_create_student("student_001", language="en")
    print(f"  after reset + recreate: {fresh}")
    assert fresh["topic_index"] == 0
    assert fresh["questions_answered"] == 0

    sc.close()
    os.remove(demo_path)
    print("\n✓ All staircase checks passed.")
