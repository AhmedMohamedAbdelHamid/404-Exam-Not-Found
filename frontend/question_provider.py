"""Thin C5 adapter between Streamlit and the team question backend.

This module owns orchestration and error normalization only. It does not
duplicate generation, retrieval, validation, staircase, or backup-pool logic.
All functions are intentionally usable with injected callables so the frontend
flow can be tested without ChromaDB or Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import importlib.util
from pathlib import Path
import sqlite3
import uuid

from backup_pool import get_backup_question
from generation_agent import call_llm as generation_call_llm
from get_next_question import (
    GenerationUnavailable,
    get_next_question,
    record_answer,
)
import llm_client
from schema import QuestionOut
from staircase import DB_PATH, Staircase, TOPIC_ORDER


LANGUAGE_LABELS = {"en": "English", "ar": "Arabic"}
EXPECTED_COLLECTIONS = {"en": "chunks_en", "ar": "chunks_ar"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LanguageConflictError(ValueError):
    """Raised when an existing backend identity belongs to another track."""


class LanguageMismatchError(RuntimeError):
    """Raised when the backend returns content from the wrong corpus."""


@dataclass(frozen=True)
class RuntimeReadiness:
    live_ready: bool
    backup_ready: bool
    language: str
    missing: tuple[str, ...] = ()
    technical_detail: str | None = None

    @property
    def mode_label(self) -> str:
        return "Live pipeline configured" if self.live_ready else "Resilient assessment ready"

    @property
    def student_message(self) -> str:
        if self.live_ready:
            return (
                "Textbook-grounded generation is configured, with verified fallback "
                "available if needed."
            )
        if self.backup_ready:
            return "Verified textbook questions are available while live generation is offline."
        return "Assessment content is not available yet. Check the runtime configuration and retry."

    def with_live_failure(self, detail: str) -> "RuntimeReadiness":
        return replace(
            self,
            live_ready=False,
            missing=tuple(dict.fromkeys((*self.missing, "live pipeline unavailable"))),
            technical_detail=detail,
        )


@dataclass(frozen=True)
class QuestionDelivery:
    question_id: str
    question: QuestionOut
    source: str
    requested_difficulty: int
    topic: str
    language: str
    questions_answered_before: int
    student_state_before: dict | None = None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class FetchResult:
    status: str
    delivery: QuestionDelivery | None = None
    message: str | None = None
    technical_detail: str | None = None


@dataclass(frozen=True)
class SubmissionResult:
    success: bool
    status: str
    state: dict | None = None
    already_recorded: bool = False
    message: str | None = None
    technical_detail: str | None = None


def _collection_names_from_sqlite(database_file: Path) -> set[str]:
    """Read Chroma collection names without creating or mutating its store."""
    uri = f"file:{database_file.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute("SELECT name FROM collections").fetchall()
        return {str(row[0]) for row in rows}
    finally:
        connection.close()


def inspect_runtime(language: str, project_root: Path | None = None) -> RuntimeReadiness:
    """Check whether live generation can run, without exposing credentials."""
    if language not in LANGUAGE_LABELS:
        raise ValueError(f"Unsupported language code: {language!r}")

    root = project_root or PROJECT_ROOT
    missing: list[str] = []
    technical_detail = None
    chroma_path = root / "chroma_db"
    chroma_database = chroma_path / "chroma.sqlite3"

    if not chroma_path.is_dir() or not chroma_database.is_file():
        missing.append("ChromaDB index")
    else:
        try:
            collection_names = _collection_names_from_sqlite(chroma_database)
            expected = EXPECTED_COLLECTIONS[language]
            if expected not in collection_names:
                missing.append(f"{expected} collection")
        except (sqlite3.Error, OSError) as exc:
            missing.append("readable ChromaDB index")
            technical_detail = f"{type(exc).__name__}: collection metadata could not be read"

    if importlib.util.find_spec("chromadb") is None:
        missing.append("ChromaDB package")

    # USE_REAL_LLM is computed only after llm_client loads an optional .env.
    if not llm_client.USE_REAL_LLM:
        missing.append("Gemini configuration")
    else:
        try:
            genai_available = importlib.util.find_spec("google.genai") is not None
        except ModuleNotFoundError:
            genai_available = False
        if not genai_available:
            missing.append("Google GenAI package")

    backup_ready = all(
        get_backup_question(topic, language, difficulty=3) is not None
        for topic in TOPIC_ORDER
    )
    return RuntimeReadiness(
        live_ready=not missing,
        backup_ready=backup_ready,
        language=language,
        missing=tuple(missing),
        technical_detail=technical_detail,
    )


def default_staircase_db_path() -> str:
    """Return one stable absolute DB path that is safe to persist in session state."""
    return str((PROJECT_ROOT / DB_PATH).resolve())


def create_staircase(db_path: str) -> Staircase:
    """Create a connection-bearing Staircase for the current execution only."""
    return Staircase(db_path=db_path)


def create_chunk_sampler(readiness: RuntimeReadiness):
    """Import retrieval only when its local Chroma resources are ready."""
    if not readiness.live_ready:
        return None
    from chunk_sampler import ChunkSampler

    return ChunkSampler()


def new_attempt_identity(student_id: str) -> tuple[str, str]:
    """Return a stable visible ID and a fresh backend key for one attempt."""
    visible_id = student_id.strip()
    if not visible_id:
        raise ValueError("Student identifier is required.")
    if len(visible_id) > 80:
        raise ValueError("Student identifier must be 80 characters or fewer.")
    attempt_token = uuid.uuid4().hex[:12]
    return visible_id, f"{visible_id}::attempt::{attempt_token}"


def initialize_student(
    *,
    staircase_db_path: str,
    backend_student_id: str,
    language: str,
    staircase_factory=create_staircase,
) -> dict:
    """Explicitly initialize language with a fresh, current-thread connection."""
    if language not in LANGUAGE_LABELS:
        raise ValueError(f"Unsupported language code: {language!r}")
    staircase = staircase_factory(staircase_db_path)
    try:
        state = staircase.get_or_create_student(backend_student_id, language=language)
        if state["language"] != language:
            raise LanguageConflictError(
                "This assessment identity already belongs to a different language track."
            )
        return state
    finally:
        staircase.close()


def read_student_state(
    *,
    staircase_db_path: str,
    student_id: str,
    staircase_factory=create_staircase,
) -> dict:
    """Read adaptive state without retaining a SQLite connection between reruns."""
    staircase = staircase_factory(staircase_db_path)
    try:
        return staircase.get_or_create_student(student_id)
    finally:
        staircase.close()


def student_exam_complete(
    *,
    staircase_db_path: str,
    student_id: str,
    staircase_factory=create_staircase,
) -> bool:
    """Check completion on a fresh connection in the current execution thread."""
    staircase = staircase_factory(staircase_db_path)
    try:
        return staircase.is_exam_complete(student_id)
    finally:
        staircase.close()


def question_id_for(sequence_number: int) -> str:
    if sequence_number < 1:
        raise ValueError("Question sequence numbers start at 1.")
    return f"q{sequence_number:03d}"


def curriculum_size() -> int:
    return len(TOPIC_ORDER)


def _question_language(question: QuestionOut) -> str:
    return question.language.value if hasattr(question.language, "value") else str(question.language)


def _validate_question_language(question: QuestionOut, expected_language: str) -> None:
    actual_language = _question_language(question)
    if actual_language != expected_language:
        raise LanguageMismatchError(
            f"Expected {expected_language!r} question, received {actual_language!r}."
        )


def _is_known_operational_error(exc: Exception) -> bool:
    module_name = type(exc).__module__
    return isinstance(
        exc,
        (llm_client.LLMCallError, sqlite3.Error, OSError, ImportError),
    ) or module_name.startswith(("chromadb.", "google.genai.", "httpx."))


def _safe_detail(exc: Exception, context: str) -> str:
    """Keep diagnostics useful without retaining exception text or secrets."""
    return f"{context}: {type(exc).__module__}.{type(exc).__name__}"


def fetch_next_question(
    *,
    student_id: str,
    language: str,
    staircase_db_path: str,
    chunk_sampler,
    readiness: RuntimeReadiness,
    sequence_number: int,
    get_next_fn=get_next_question,
    generation_fn=generation_call_llm,
    critique_fn=llm_client.critique_question_json,
    backup_fn=get_backup_question,
    staircase_factory=create_staircase,
) -> FetchResult:
    """Return one question using a Staircase created and closed in this call."""
    staircase = staircase_factory(staircase_db_path)
    try:
        state = staircase.get_or_create_student(student_id)
        if state["language"] != language:
            return FetchResult(
                status="error",
                message="This assessment is locked to a different language track.",
                technical_detail="Backend student language did not match the active attempt.",
            )

        topic = staircase.get_current_topic(student_id)
        if topic is None:
            return FetchResult(status="complete")

        difficulty = staircase.get_current_difficulty(student_id)
        questions_answered_before = state["questions_answered"]
        fallback_reason = None

        if readiness.live_ready:
            if chunk_sampler is None:
                fallback_reason = "Live retrieval could not be initialized."
                live_detail = "Live runtime was ready, but no ChunkSampler instance was available."
            else:
                try:
                    question = get_next_fn(
                        student_id=student_id,
                        chunk_sampler=chunk_sampler,
                        generation_call_llm_fn=generation_fn,
                        critique_call_llm_fn=critique_fn,
                        staircase=staircase,
                    )
                    if question is None:
                        return FetchResult(status="complete")
                    _validate_question_language(question, language)
                    return FetchResult(
                        status="question",
                        delivery=QuestionDelivery(
                            question_id=question_id_for(sequence_number),
                            question=question,
                            source="live",
                            requested_difficulty=difficulty,
                            topic=topic,
                            language=language,
                            questions_answered_before=questions_answered_before,
                            student_state_before=dict(state),
                        ),
                    )
                except LanguageMismatchError as exc:
                    return FetchResult(
                        status="error",
                        message="The question track did not match this assessment. Please retry.",
                        technical_detail=_safe_detail(exc, "language validation"),
                    )
                except GenerationUnavailable as exc:
                    fallback_reason = "Live generation could not produce a validated question."
                    live_detail = _safe_detail(exc, "generation unavailable")
                except Exception as exc:
                    if not _is_known_operational_error(exc):
                        raise
                    fallback_reason = "The live question service is temporarily unavailable."
                    live_detail = _safe_detail(exc, "live pipeline")
        else:
            fallback_reason = "Live generation is not configured for this runtime."
            live_detail = readiness.technical_detail or ", ".join(readiness.missing)

        if readiness.backup_ready:
            try:
                question = backup_fn(topic, language, difficulty)
            except Exception as exc:
                if not _is_known_operational_error(exc):
                    raise
                question = None
                backup_detail = _safe_detail(exc, "backup pool")
            else:
                backup_detail = None

            if question is not None:
                try:
                    _validate_question_language(question, language)
                except LanguageMismatchError as exc:
                    return FetchResult(
                        status="error",
                        message="The available question did not match this assessment track.",
                        technical_detail=_safe_detail(exc, "backup language validation"),
                    )
                return FetchResult(
                    status="question",
                    delivery=QuestionDelivery(
                        question_id=question_id_for(sequence_number),
                        question=question,
                        source="backup",
                        requested_difficulty=difficulty,
                        topic=topic,
                        language=language,
                        questions_answered_before=questions_answered_before,
                        student_state_before=dict(state),
                        fallback_reason=fallback_reason,
                    ),
                    technical_detail=live_detail,
                )

        detail_parts = [part for part in (live_detail, locals().get("backup_detail")) if part]
        return FetchResult(
            status="error",
            message="A question is not available right now. Please retry in a moment.",
            technical_detail=" | ".join(detail_parts) or "No live or backup question was available.",
        )
    finally:
        staircase.close()


_ANSWER_STATE_FIELDS = (
    "current_difficulty",
    "topic_index",
    "questions_answered",
    "correct_count",
)


def expected_answer_state(pre_state: dict, correct: bool) -> dict:
    """Return the exact staircase counters expected after one answer."""
    expected = dict(pre_state)
    delta = 1 if correct else -1
    expected["current_difficulty"] = max(
        1,
        min(5, pre_state["current_difficulty"] + delta),
    )
    expected["topic_index"] = pre_state["topic_index"] + 1
    expected["questions_answered"] = pre_state["questions_answered"] + 1
    expected["correct_count"] = pre_state["correct_count"] + (1 if correct else 0)
    return expected


def _state_matches(actual: dict | None, expected: dict) -> bool:
    return actual is not None and all(
        actual.get(field) == expected.get(field) for field in _ANSWER_STATE_FIELDS
    )


def _read_state_for_reconciliation(
    *,
    staircase_db_path: str,
    student_id: str,
    staircase_factory,
) -> tuple[dict | None, Exception | None]:
    """Read through a fresh connection without letting cleanup hide the result."""
    staircase = None
    state = None
    error = None
    try:
        staircase = staircase_factory(staircase_db_path)
        state = staircase.get_or_create_student(student_id)
    except Exception as exc:
        error = exc
    finally:
        if staircase is not None:
            try:
                staircase.close()
            except Exception as exc:
                if error is None and state is None:
                    error = exc
    return state, error


def reconcile_answer_state(
    *,
    student_id: str,
    correct: bool,
    staircase_db_path: str,
    expected_pre_state: dict,
    staircase_factory=create_staircase,
    technical_detail: str | None = None,
) -> SubmissionResult:
    """Classify persisted state as saved, safely retryable, or ambiguous."""
    expected_post_state = expected_answer_state(expected_pre_state, correct)
    persisted_state, read_error = _read_state_for_reconciliation(
        staircase_db_path=staircase_db_path,
        student_id=student_id,
        staircase_factory=staircase_factory,
    )
    if _state_matches(persisted_state, expected_post_state):
        return SubmissionResult(
            success=True,
            status="saved",
            state=persisted_state,
            already_recorded=True,
            technical_detail=technical_detail,
        )
    if _state_matches(persisted_state, expected_pre_state):
        return SubmissionResult(
            success=False,
            status="definitely_failed",
            state=persisted_state,
            message="We could not save your adaptive progress. Your answer is safe; please retry.",
            technical_detail=technical_detail,
        )

    detail = technical_detail
    if read_error is not None:
        read_detail = _safe_detail(read_error, "answer reconciliation")
        detail = " | ".join(part for part in (detail, read_detail) if part)
    return SubmissionResult(
        success=False,
        status="ambiguous",
        state=persisted_state,
        message=(
            "We could not safely confirm your adaptive progress. "
            "Please ask the assessment administrator to synchronize this attempt."
        ),
        technical_detail=detail or "Persisted answer state matched neither expected state.",
    )


def submit_answer_once(
    *,
    student_id: str,
    correct: bool,
    staircase_db_path: str,
    expected_pre_state: dict,
    already_recorded: bool,
    record_fn=record_answer,
    staircase_factory=create_staircase,
) -> SubmissionResult:
    """Record once and reconcile every outcome after the write is invoked."""
    expected_post_state = expected_answer_state(expected_pre_state, correct)
    current_state, current_error = _read_state_for_reconciliation(
        staircase_db_path=staircase_db_path,
        student_id=student_id,
        staircase_factory=staircase_factory,
    )
    if _state_matches(current_state, expected_post_state):
        return SubmissionResult(
            success=True,
            status="saved",
            state=current_state,
            already_recorded=True,
        )
    if current_error is not None:
        return SubmissionResult(
            success=False,
            status="definitely_failed",
            state=current_state,
            message="We could not read your adaptive progress. Please retry saving your answer.",
            technical_detail=_safe_detail(current_error, "answer preflight"),
        )
    if already_recorded or not _state_matches(current_state, expected_pre_state):
        return SubmissionResult(
            success=False,
            status="ambiguous",
            state=current_state,
            message=(
                "We could not safely confirm your adaptive progress. "
                "Please ask the assessment administrator to synchronize this attempt."
            ),
            technical_detail="Answer preflight state matched neither the expected pre-state nor post-state.",
        )

    staircase = None
    updated_state = None
    operation_error = None
    try:
        staircase = staircase_factory(staircase_db_path)
        try:
            updated_state = record_fn(student_id, correct, staircase=staircase)
        except Exception as exc:
            operation_error = exc
    except Exception as exc:
        operation_error = exc
    finally:
        if staircase is not None:
            try:
                staircase.close()
            except Exception as exc:
                if operation_error is None:
                    operation_error = exc

    # A normal backend return that contains the exact post-state is definitive;
    # a cleanup error must never overwrite this confirmed successful result.
    if _state_matches(updated_state, expected_post_state):
        return SubmissionResult(success=True, status="saved", state=updated_state)

    detail = (
        _safe_detail(operation_error, "answer update")
        if operation_error is not None
        else "record_answer returned an unexpected state."
    )
    return reconcile_answer_state(
        student_id=student_id,
        correct=correct,
        staircase_db_path=staircase_db_path,
        expected_pre_state=expected_pre_state,
        staircase_factory=staircase_factory,
        technical_detail=detail,
    )
