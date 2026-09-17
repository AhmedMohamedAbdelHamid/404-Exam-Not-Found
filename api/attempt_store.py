from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from schema import QuestionOut

from api.models import AnswerResponse, AnswerState, LanguageCode, QuestionSource, RuntimeStatus


@dataclass
class StoredQuestion:
    question_id: str
    question_number: int
    question: QuestionOut
    source: QuestionSource
    requested_difficulty: int
    state_before: dict[str, Any]
    option_order: tuple[int, ...]
    option_ids: tuple[str, ...]
    option_to_original: dict[str, int]
    answer_state: AnswerState = "open"
    submitted_option_id: str | None = None
    answer_result: AnswerResponse | None = None
    analytics_confirmed: bool = False


@dataclass
class AttemptContext:
    attempt_id: UUID
    visible_student_id: str
    backend_student_key: str
    language: LanguageCode
    staircase_db_path: str
    chunk_sampler: Any
    runtime: RuntimeStatus
    current_adaptive_difficulty: int
    questions: dict[str, StoredQuestion] = field(default_factory=dict)
    question_order: list[str] = field(default_factory=list)
    current_question_id: str | None = None
    response_logs: list[dict[str, Any]] = field(default_factory=list)
    adaptive_journey: list[int] = field(default_factory=list)
    complete: bool = False
    analytics_completion_confirmed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: RLock = field(default_factory=RLock, repr=False)


class AttemptStore:
    """Process-local attempt state. SQLite remains the adaptive source of truth."""

    def __init__(self) -> None:
        self._attempts: dict[UUID, AttemptContext] = {}
        self._lock = RLock()

    def add(self, attempt: AttemptContext) -> AttemptContext:
        with self._lock:
            self._attempts[attempt.attempt_id] = attempt
        return attempt

    def get(self, attempt_id: UUID) -> AttemptContext | None:
        with self._lock:
            return self._attempts.get(attempt_id)

    def create_id(self) -> UUID:
        return uuid4()
