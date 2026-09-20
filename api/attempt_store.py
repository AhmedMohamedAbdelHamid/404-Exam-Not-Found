from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from schema import QuestionOut

from models import AnswerResponse, AnswerState, LanguageCode, QuestionSource, RuntimeStatus
from chunk_sampler import ChunkSampler
from runtime import RuntimeInspector
from db import connection, json_param, json_value


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


def _jsonable(value: Any) -> Any:
    """Recursively convert an AttemptContext (and everything it contains)
    into plain JSON-safe values, for storage in attempt_contexts.context
    (jsonb). Mirror of _context_from_dict below -- keep both in sync.
    """
    if isinstance(value, BaseModel):
        return {"__pydantic__": type(value).__name__, "data": value.model_dump(mode="json")}
    if isinstance(value, ChunkSampler):
        return {"__chunk_sampler__": True, "data": value.to_dict()}
    if isinstance(value, (StoredQuestion, AttemptContext)):
        return {
            f.name: _jsonable(getattr(value, f.name))
            for f in fields(value)
            if f.name not in ("lock", "runtime")  # not persisted: see note below
        }
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


_PYDANTIC_MODELS: dict[str, type[BaseModel]] = {
    "QuestionOut": QuestionOut,
    "AnswerResponse": AnswerResponse,
}


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        if "__pydantic__" in value:
            model = _PYDANTIC_MODELS[value["__pydantic__"]]
            return model.model_validate(value["data"])
        if "__chunk_sampler__" in value:
            return ChunkSampler.from_dict(value["data"])
        return {k: _from_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_jsonable(v) for v in value]
    return value


def _question_from_dict(data: dict) -> StoredQuestion:
    restored = {k: _from_jsonable(v) for k, v in data.items()}
    restored["option_order"] = tuple(restored["option_order"])
    restored["option_ids"] = tuple(restored["option_ids"])
    return StoredQuestion(**restored)


def _context_from_dict(data: dict, *, runtime: RuntimeStatus) -> AttemptContext:
    restored = {k: _from_jsonable(v) for k, v in data.items() if k not in ("lock", "runtime")}
    restored["attempt_id"] = UUID(restored["attempt_id"])
    restored["created_at"] = datetime.fromisoformat(restored["created_at"])
    restored["questions"] = {
        qid: _question_from_dict(q) for qid, q in restored.get("questions", {}).items()
    }
    return AttemptContext(runtime=runtime, **restored)


class AttemptStore:
    """Postgres-backed (Supabase attempt_contexts: attempt_id text primary
    key, context jsonb, updated_at). Vercel functions are stateless and
    can run as several parallel instances, so an in-memory dict (the
    original implementation) can't be shared across requests for the
    same attempt -- every add()/save() upserts the full context as one
    JSONB blob; every get() reads it back and reconstructs the same
    dataclasses assessment_service.py already works with in memory.

    `runtime` is deliberately NOT persisted: assessment_service.py
    already treats it as refreshable (re-set via
    runtime_inspector.for_language() at several points), so get()
    recomputes a fresh one instead of trusting a stale snapshot.
    `lock` is dropped too -- meaningless across instances/processes;
    concurrent access to the *same* attempt_id is not expected within
    one exam session, so no replacement locking is added here.
    """

    def __init__(self, runtime_inspector: RuntimeInspector | None = None) -> None:
        self._runtime_inspector = runtime_inspector or RuntimeInspector()

    def add(self, attempt: AttemptContext) -> AttemptContext:
        self.save(attempt)
        return attempt

    def save(self, attempt: AttemptContext) -> None:
        payload = _jsonable(attempt)
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO attempt_contexts (attempt_id, context, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (attempt_id) DO UPDATE SET
                    context = EXCLUDED.context, updated_at = now()
                """,
                (str(attempt.attempt_id), json_param(payload)),
            )

    def get(self, attempt_id: UUID) -> AttemptContext | None:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT context FROM attempt_contexts WHERE attempt_id = %s",
                (str(attempt_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        context = json_value(row["context"])
        runtime = self._runtime_inspector.for_language(context["language"])
        return _context_from_dict(context, runtime=runtime)

    def create_id(self) -> UUID:
        return uuid4()

