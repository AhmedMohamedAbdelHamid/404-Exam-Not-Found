"""
staircase.py — Postgres-backed replacement for the original SQLite
version (student_state.db). Public interface, method names, argument
shapes, and returned dict keys are all unchanged, so get_next_question.py
and assessment_service.py needed no edits: `from staircase import
Staircase` and every call site works exactly as before. See db.py for
why: Vercel functions are stateless and a local SQLite file can't be
shared across instances.

Topic order / starting-difficulty / staircase rule are unchanged from
the original -- see the SQLite version (repo root, main branch) for the
full design rationale.
"""

from __future__ import annotations

from typing import Any

from db import connection
from difficulty_scorer import MIN_DIFFICULTY, MAX_DIFFICULTY

STARTING_DIFFICULTY = 3

# Kept only so `from staircase import DB_PATH` (assessment_service.py)
# keeps working -- no longer an actual file path, since state lives in
# Postgres now. AttemptContext.staircase_db_path is likewise vestigial.
DB_PATH = "student_state.db"

TOPIC_ORDER = [
    "algorithm",
    "variables and assignment",
    "loops and conditionals",
    "lists",
    "functions",
]


class Staircase:
    """One instance per call site, same as before. `db_path` is accepted
    and ignored: it existed to isolate SQLite files per attempt, but
    Postgres already isolates state by student_id, so call sites that
    pass `Staircase(db_path=attempt.staircase_db_path)` keep working
    unchanged.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path  # unused; kept for call-site compatibility

    def get_or_create_student(self, student_id: str, language: str = "en") -> dict[str, Any]:
        """Fetch existing state, or create a fresh row with defaults.
        `language` is only used on first creation -- language is fixed
        once per student and never changed here.
        """
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM student_state WHERE student_id = %s", (student_id,))
            row = cur.fetchone()
            if row is not None:
                return dict(row)

            cur.execute(
                """
                INSERT INTO student_state
                    (student_id, language, current_difficulty, topic_index,
                     questions_answered, correct_count)
                VALUES (%s, %s, %s, 0, 0, 0)
                ON CONFLICT (student_id) DO NOTHING
                """,
                (student_id, language, STARTING_DIFFICULTY),
            )
            cur.execute("SELECT * FROM student_state WHERE student_id = %s", (student_id,))
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

    def record_answer(self, student_id: str, correct: bool) -> dict[str, Any]:
        """Apply the staircase rule (correct -> +1 capped at MAX_DIFFICULTY;
        wrong -> -1 capped at MIN_DIFFICULTY), advance to the next topic,
        and update the answered/correct counters. Returns the updated
        state dict.
        """
        state = self.get_or_create_student(student_id)

        new_difficulty = state["current_difficulty"] + (1 if correct else -1)
        new_difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_difficulty))

        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE student_state
                SET current_difficulty = %s,
                    topic_index = topic_index + 1,
                    questions_answered = questions_answered + 1,
                    correct_count = correct_count + (%s)
                WHERE student_id = %s
                """,
                (new_difficulty, 1 if correct else 0, student_id),
            )
            cur.execute("SELECT * FROM student_state WHERE student_id = %s", (student_id,))
            return dict(cur.fetchone())

    def reset_student(self, student_id: str) -> None:
        """Wipe a student's state entirely -- e.g. for a fresh retake."""
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM student_state WHERE student_id = %s", (student_id,))

    def close(self) -> None:
        pass  # no persistent connection is held between calls
