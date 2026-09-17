"""Durable, API-owned assessment analytics persistence.

This module deliberately has no dependency on the assessment service or the
generation backend.  Each operation opens and closes its own SQLite connection
so no connection crosses FastAPI worker threads.  Write operations use
``BEGIN IMMEDIATE`` to make read/compare/write idempotency decisions atomic.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Iterator, Literal
from uuid import UUID


AttemptStatus = Literal["in_progress", "completed"]
AnswerStatus = Literal["pending", "confirmed", "failed"]

DEFAULT_ANALYTICS_DB_PATH = Path(__file__).resolve().parents[1] / "assessment_analytics.db"
ANALYTICS_DB_PATH_ENV = "ASSESSMENT_ANALYTICS_DB_PATH"
DEFAULT_BUSY_TIMEOUT_MS = 5_000


class AnalyticsStoreError(Exception):
    """Base class for analytics persistence domain errors."""


class AnalyticsConflictError(AnalyticsStoreError):
    """The requested write conflicts with an existing immutable record."""


class AnalyticsNotFoundError(AnalyticsStoreError):
    """The requested attempt or answer does not exist."""


class AnalyticsValidationError(AnalyticsStoreError):
    """The caller supplied data outside the durable analytics contract."""


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    student_id: str
    language: str
    initial_difficulty: int
    status: AttemptStatus
    created_at: str
    completed_at: str | None
    final_difficulty: int | None


@dataclass(frozen=True)
class AnswerRecord:
    attempt_id: str
    question_id: str
    question_number: int
    language: str
    topic: str
    question_text: str
    selected_option_index: int
    selected_answer_text: str
    correct_answer_text: str
    correct: bool
    misconception: str | None
    difficulty_score: int
    requested_difficulty: int
    adaptive_level_before: int
    adaptive_level_after: int | None
    source_reference: str
    status: AnswerStatus
    created_at: str
    confirmed_at: str | None


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """One consistent read transaction for teacher-facing aggregation."""

    attempts: tuple[AttemptRecord, ...]
    confirmed_answers: tuple[AnswerRecord, ...]


def _configured_path() -> Path:
    configured = os.getenv(ANALYTICS_DB_PATH_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_ANALYTICS_DB_PATH


def _identifier(value: str | UUID, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise AnalyticsValidationError(f"{field} must not be blank.")
    return normalized


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalyticsValidationError(f"{field} must not be blank.")
    return value


def _language(value: str) -> str:
    if value not in ("en", "ar"):
        raise AnalyticsValidationError("language must be 'en' or 'ar'.")
    return value


def _difficulty(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise AnalyticsValidationError(f"{field} must be an integer from 1 to 5.")
    return value


def _utc_iso(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise AnalyticsValidationError("timestamps must be timezone-aware.")
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _attempt_from_row(row: sqlite3.Row) -> AttemptRecord:
    return AttemptRecord(
        attempt_id=row["attempt_id"],
        student_id=row["student_id"],
        language=row["language"],
        initial_difficulty=row["initial_difficulty"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        final_difficulty=row["final_difficulty"],
    )


def _answer_from_row(row: sqlite3.Row) -> AnswerRecord:
    return AnswerRecord(
        attempt_id=row["attempt_id"],
        question_id=row["question_id"],
        question_number=row["question_number"],
        language=row["language"],
        topic=row["topic"],
        question_text=row["question_text"],
        selected_option_index=row["selected_option_index"],
        selected_answer_text=row["selected_answer_text"],
        correct_answer_text=row["correct_answer_text"],
        correct=bool(row["correct"]),
        misconception=row["misconception"],
        difficulty_score=row["difficulty_score"],
        requested_difficulty=row["requested_difficulty"],
        adaptive_level_before=row["adaptive_level_before"],
        adaptive_level_after=row["adaptive_level_after"],
        source_reference=row["source_reference"],
        status=row["status"],
        created_at=row["created_at"],
        confirmed_at=row["confirmed_at"],
    )


class AnalyticsStore:
    """Small durable store for assessment attempts and submitted answers."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self.db_path = Path(db_path).expanduser() if db_path is not None else _configured_path()
        if busy_timeout_ms < 0:
            raise AnalyticsValidationError("busy_timeout_ms must not be negative.")
        self.busy_timeout_ms = busy_timeout_ms

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=self.busy_timeout_ms / 1_000,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms:d}")
        return connection

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the v1 schema; safe to call repeatedly and concurrently."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
                    initial_difficulty INTEGER NOT NULL CHECK (initial_difficulty BETWEEN 1 AND 5),
                    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
                    created_at TEXT NOT NULL,
                    completed_at TEXT NULL,
                    final_difficulty INTEGER NULL CHECK (final_difficulty BETWEEN 1 AND 5),
                    CHECK (
                        (status = 'in_progress' AND completed_at IS NULL AND final_difficulty IS NULL)
                        OR
                        (status = 'completed' AND completed_at IS NOT NULL AND final_difficulty IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS answers (
                    attempt_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    question_number INTEGER NOT NULL CHECK (question_number >= 1),
                    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
                    topic TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    selected_option_index INTEGER NOT NULL CHECK (selected_option_index >= 0),
                    selected_answer_text TEXT NOT NULL,
                    correct_answer_text TEXT NOT NULL,
                    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
                    misconception TEXT NULL,
                    difficulty_score INTEGER NOT NULL CHECK (difficulty_score BETWEEN 1 AND 5),
                    requested_difficulty INTEGER NOT NULL CHECK (requested_difficulty BETWEEN 1 AND 5),
                    adaptive_level_before INTEGER NOT NULL CHECK (adaptive_level_before BETWEEN 1 AND 5),
                    adaptive_level_after INTEGER NULL CHECK (adaptive_level_after BETWEEN 1 AND 5),
                    source_reference TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed')),
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT NULL,
                    PRIMARY KEY (attempt_id, question_id),
                    FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id) ON DELETE RESTRICT,
                    CHECK (
                        (status = 'confirmed' AND confirmed_at IS NOT NULL AND adaptive_level_after IS NOT NULL)
                        OR
                        (status IN ('pending', 'failed') AND confirmed_at IS NULL)
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_attempts_created
                    ON attempts(created_at, attempt_id);
                CREATE INDEX IF NOT EXISTS idx_answers_status_order
                    ON answers(status, attempt_id, question_number, question_id);
                PRAGMA user_version = 1;
                """
            )
            connection.commit()
        finally:
            connection.close()

    def create_attempt(
        self,
        *,
        attempt_id: str | UUID,
        student_id: str,
        language: str,
        initial_difficulty: int,
        created_at: datetime | None = None,
    ) -> AttemptRecord:
        normalized_id = _identifier(attempt_id, "attempt_id")
        normalized_student = _text(student_id, "student_id").strip()
        normalized_language = _language(language)
        normalized_difficulty = _difficulty(initial_difficulty, "initial_difficulty")
        requested_created_at = _utc_iso(created_at) if created_at is not None else None

        with self._write() as connection:
            existing = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (normalized_id,)
            ).fetchone()
            if existing is not None:
                record = _attempt_from_row(existing)
                matches = (
                    record.student_id == normalized_student
                    and record.language == normalized_language
                    and record.initial_difficulty == normalized_difficulty
                    and (requested_created_at is None or record.created_at == requested_created_at)
                )
                if not matches:
                    raise AnalyticsConflictError(
                        f"Attempt {normalized_id!r} already exists with another identity."
                    )
                return record

            timestamp = requested_created_at or _utc_iso()
            connection.execute(
                """
                INSERT INTO attempts (
                    attempt_id, student_id, language, initial_difficulty,
                    status, created_at, completed_at, final_difficulty
                ) VALUES (?, ?, ?, ?, 'in_progress', ?, NULL, NULL)
                """,
                (
                    normalized_id,
                    normalized_student,
                    normalized_language,
                    normalized_difficulty,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (normalized_id,)
            ).fetchone()
            return _attempt_from_row(row)

    def get_attempt(self, attempt_id: str | UUID) -> AttemptRecord | None:
        normalized_id = _identifier(attempt_id, "attempt_id")
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (normalized_id,)
            ).fetchone()
        return _attempt_from_row(row) if row is not None else None

    def mark_attempt_completed(
        self,
        attempt_id: str | UUID,
        final_difficulty: int,
        *,
        completed_at: datetime | None = None,
    ) -> AttemptRecord:
        normalized_id = _identifier(attempt_id, "attempt_id")
        normalized_difficulty = _difficulty(final_difficulty, "final_difficulty")
        requested_completed_at = _utc_iso(completed_at) if completed_at is not None else None

        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (normalized_id,)
            ).fetchone()
            if row is None:
                raise AnalyticsNotFoundError(f"Attempt {normalized_id!r} was not found.")
            existing = _attempt_from_row(row)
            if existing.status == "completed":
                matches = (
                    existing.final_difficulty == normalized_difficulty
                    and (
                        requested_completed_at is None
                        or existing.completed_at == requested_completed_at
                    )
                )
                if not matches:
                    raise AnalyticsConflictError(
                        f"Attempt {normalized_id!r} is already completed with other values."
                    )
                return existing

            timestamp = requested_completed_at or _utc_iso()
            connection.execute(
                """
                UPDATE attempts
                SET status = 'completed', completed_at = ?, final_difficulty = ?
                WHERE attempt_id = ?
                """,
                (timestamp, normalized_difficulty, normalized_id),
            )
            updated = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (normalized_id,)
            ).fetchone()
            return _attempt_from_row(updated)

    def prepare_answer(
        self,
        *,
        attempt_id: str | UUID,
        question_id: str,
        question_number: int,
        language: str,
        topic: str,
        question_text: str,
        selected_option_index: int,
        selected_answer_text: str,
        correct_answer_text: str,
        correct: bool,
        misconception: str | None,
        difficulty_score: int,
        requested_difficulty: int,
        adaptive_level_before: int,
        adaptive_level_after: int | None,
        source_reference: str,
        created_at: datetime | None = None,
    ) -> AnswerRecord:
        """Create a pending answer without ever replacing its payload.

        An exact retry is a read-equivalent operation.  An exact retry of a
        failed row returns it to ``pending`` while preserving its original
        creation timestamp; callers must explicitly confirm it again.
        """
        values = self._validated_answer_values(
            attempt_id=attempt_id,
            question_id=question_id,
            question_number=question_number,
            language=language,
            topic=topic,
            question_text=question_text,
            selected_option_index=selected_option_index,
            selected_answer_text=selected_answer_text,
            correct_answer_text=correct_answer_text,
            correct=correct,
            misconception=misconception,
            difficulty_score=difficulty_score,
            requested_difficulty=requested_difficulty,
            adaptive_level_before=adaptive_level_before,
            adaptive_level_after=adaptive_level_after,
            source_reference=source_reference,
        )
        requested_created_at = _utc_iso(created_at) if created_at is not None else None

        with self._write() as connection:
            attempt = connection.execute(
                "SELECT language FROM attempts WHERE attempt_id = ?", (values["attempt_id"],)
            ).fetchone()
            if attempt is None:
                raise AnalyticsNotFoundError(
                    f"Attempt {values['attempt_id']!r} was not found."
                )
            if attempt["language"] != values["language"]:
                raise AnalyticsConflictError("Answer language does not match its attempt.")

            existing_row = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (values["attempt_id"], values["question_id"]),
            ).fetchone()
            if existing_row is not None:
                existing = _answer_from_row(existing_row)
                if not self._answer_payload_matches(existing, values, requested_created_at):
                    raise AnalyticsConflictError(
                        "This question already has a different prepared answer."
                    )
                if existing.status == "failed":
                    connection.execute(
                        """
                        UPDATE answers
                        SET status = 'pending', confirmed_at = NULL
                        WHERE attempt_id = ? AND question_id = ?
                        """,
                        (values["attempt_id"], values["question_id"]),
                    )
                    refreshed = connection.execute(
                        "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                        (values["attempt_id"], values["question_id"]),
                    ).fetchone()
                    return _answer_from_row(refreshed)
                return existing

            timestamp = requested_created_at or _utc_iso()
            connection.execute(
                """
                INSERT INTO answers (
                    attempt_id, question_id, question_number, language, topic,
                    question_text, selected_option_index, selected_answer_text,
                    correct_answer_text, correct, misconception, difficulty_score,
                    requested_difficulty, adaptive_level_before, adaptive_level_after,
                    source_reference, status, created_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL)
                """,
                (
                    values["attempt_id"], values["question_id"], values["question_number"],
                    values["language"], values["topic"], values["question_text"],
                    values["selected_option_index"], values["selected_answer_text"],
                    values["correct_answer_text"], int(values["correct"]),
                    values["misconception"], values["difficulty_score"],
                    values["requested_difficulty"], values["adaptive_level_before"],
                    values["adaptive_level_after"], values["source_reference"], timestamp,
                ),
            )
            inserted = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (values["attempt_id"], values["question_id"]),
            ).fetchone()
            return _answer_from_row(inserted)

    @staticmethod
    def _validated_answer_values(**values: object) -> dict[str, object]:
        question_number = values["question_number"]
        selected_option_index = values["selected_option_index"]
        correct = values["correct"]
        misconception = values["misconception"]
        if isinstance(question_number, bool) or not isinstance(question_number, int) or question_number < 1:
            raise AnalyticsValidationError("question_number must be a positive integer.")
        if (
            isinstance(selected_option_index, bool)
            or not isinstance(selected_option_index, int)
            or selected_option_index < 0
        ):
            raise AnalyticsValidationError("selected_option_index must be a non-negative integer.")
        if not isinstance(correct, bool):
            raise AnalyticsValidationError("correct must be a boolean.")
        if misconception is not None and not isinstance(misconception, str):
            raise AnalyticsValidationError("misconception must be text or null.")
        return {
            "attempt_id": _identifier(values["attempt_id"], "attempt_id"),
            "question_id": _identifier(values["question_id"], "question_id"),
            "question_number": question_number,
            "language": _language(values["language"]),
            "topic": _text(values["topic"], "topic"),
            "question_text": _text(values["question_text"], "question_text"),
            "selected_option_index": selected_option_index,
            "selected_answer_text": _text(values["selected_answer_text"], "selected_answer_text"),
            "correct_answer_text": _text(values["correct_answer_text"], "correct_answer_text"),
            "correct": correct,
            "misconception": misconception,
            "difficulty_score": _difficulty(values["difficulty_score"], "difficulty_score"),
            "requested_difficulty": _difficulty(
                values["requested_difficulty"], "requested_difficulty"
            ),
            "adaptive_level_before": _difficulty(
                values["adaptive_level_before"], "adaptive_level_before"
            ),
            "adaptive_level_after": (
                _difficulty(values["adaptive_level_after"], "adaptive_level_after")
                if values["adaptive_level_after"] is not None
                else None
            ),
            "source_reference": _text(values["source_reference"], "source_reference"),
        }

    @staticmethod
    def _answer_payload_matches(
        existing: AnswerRecord,
        values: dict[str, object],
        requested_created_at: str | None,
    ) -> bool:
        immutable_fields = (
            "question_number",
            "language",
            "topic",
            "question_text",
            "selected_option_index",
            "selected_answer_text",
            "correct_answer_text",
            "correct",
            "misconception",
            "difficulty_score",
            "requested_difficulty",
            "adaptive_level_before",
            "adaptive_level_after",
            "source_reference",
        )
        return all(getattr(existing, field) == values[field] for field in immutable_fields) and (
            requested_created_at is None or existing.created_at == requested_created_at
        )

    def get_answer(
        self, attempt_id: str | UUID, question_id: str
    ) -> AnswerRecord | None:
        normalized_attempt = _identifier(attempt_id, "attempt_id")
        normalized_question = _identifier(question_id, "question_id")
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (normalized_attempt, normalized_question),
            ).fetchone()
        return _answer_from_row(row) if row is not None else None

    def confirm_answer(
        self,
        attempt_id: str | UUID,
        question_id: str,
        *,
        adaptive_level_after: int | None = None,
        confirmed_at: datetime | None = None,
    ) -> AnswerRecord:
        """Confirm a prepared answer once; identical repeats return the row."""
        normalized_attempt = _identifier(attempt_id, "attempt_id")
        normalized_question = _identifier(question_id, "question_id")
        normalized_after = (
            _difficulty(adaptive_level_after, "adaptive_level_after")
            if adaptive_level_after is not None
            else None
        )
        requested_confirmed_at = _utc_iso(confirmed_at) if confirmed_at is not None else None
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (normalized_attempt, normalized_question),
            ).fetchone()
            if row is None:
                raise AnalyticsNotFoundError("Prepared answer was not found.")
            existing = _answer_from_row(row)
            if existing.status == "confirmed":
                if (
                    (requested_confirmed_at is not None and existing.confirmed_at != requested_confirmed_at)
                    or (normalized_after is not None and existing.adaptive_level_after != normalized_after)
                ):
                    raise AnalyticsConflictError(
                        "Answer is already confirmed with other values."
                    )
                return existing
            if existing.status == "failed":
                raise AnalyticsConflictError(
                    "A failed answer must be prepared again before confirmation."
                )

            if (
                existing.adaptive_level_after is not None
                and normalized_after is not None
                and existing.adaptive_level_after != normalized_after
            ):
                raise AnalyticsConflictError(
                    "Prepared answer has another post-answer adaptive level."
                )

            authoritative_after = normalized_after or existing.adaptive_level_after
            if authoritative_after is None:
                raise AnalyticsValidationError(
                    "adaptive_level_after is required when confirming this answer."
                )
            timestamp = requested_confirmed_at or _utc_iso()
            connection.execute(
                """
                UPDATE answers
                SET status = 'confirmed', confirmed_at = ?, adaptive_level_after = ?
                WHERE attempt_id = ? AND question_id = ? AND status = 'pending'
                """,
                (timestamp, authoritative_after, normalized_attempt, normalized_question),
            )
            updated = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (normalized_attempt, normalized_question),
            ).fetchone()
            return _answer_from_row(updated)

    def mark_answer_failed(
        self, attempt_id: str | UUID, question_id: str
    ) -> AnswerRecord:
        """Move a pending answer to failed without downgrading confirmation."""
        normalized_attempt = _identifier(attempt_id, "attempt_id")
        normalized_question = _identifier(question_id, "question_id")
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (normalized_attempt, normalized_question),
            ).fetchone()
            if row is None:
                raise AnalyticsNotFoundError("Prepared answer was not found.")
            existing = _answer_from_row(row)
            if existing.status == "confirmed":
                raise AnalyticsConflictError("A confirmed answer cannot become failed.")
            if existing.status == "failed":
                return existing
            connection.execute(
                """
                UPDATE answers SET status = 'failed', confirmed_at = NULL
                WHERE attempt_id = ? AND question_id = ? AND status = 'pending'
                """,
                (normalized_attempt, normalized_question),
            )
            updated = connection.execute(
                "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
                (normalized_attempt, normalized_question),
            ).fetchone()
            return _answer_from_row(updated)

    def list_attempts(self, *, status: AttemptStatus | None = None) -> list[AttemptRecord]:
        if status is not None and status not in ("in_progress", "completed"):
            raise AnalyticsValidationError("Unknown attempt status.")
        sql = "SELECT * FROM attempts"
        parameters: tuple[str, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            parameters = (status,)
        sql += " ORDER BY created_at, attempt_id"
        with self._read() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_attempt_from_row(row) for row in rows]

    def list_confirmed_answers(
        self, *, attempt_id: str | UUID | None = None
    ) -> list[AnswerRecord]:
        sql = "SELECT * FROM answers WHERE status = 'confirmed'"
        parameters: tuple[str, ...] = ()
        if attempt_id is not None:
            sql += " AND attempt_id = ?"
            parameters = (_identifier(attempt_id, "attempt_id"),)
        sql += " ORDER BY attempt_id, question_number, question_id"
        with self._read() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_answer_from_row(row) for row in rows]

    def read_snapshot(self) -> AnalyticsSnapshot:
        """Read attempts and confirmed answers from one SQLite snapshot.

        The explicit read transaction ensures a concurrent answer confirmation
        cannot appear in the answer set without its corresponding attempt view.
        Pending and failed answers are excluded at the SQL boundary.
        """
        with self._read() as connection:
            connection.execute("BEGIN")
            attempt_rows = connection.execute(
                "SELECT * FROM attempts ORDER BY created_at, attempt_id"
            ).fetchall()
            answer_rows = connection.execute(
                """
                SELECT * FROM answers
                WHERE status = 'confirmed'
                ORDER BY attempt_id, question_number, question_id
                """
            ).fetchall()
            connection.commit()
        return AnalyticsSnapshot(
            attempts=tuple(_attempt_from_row(row) for row in attempt_rows),
            confirmed_answers=tuple(_answer_from_row(row) for row in answer_rows),
        )
