from __future__ import annotations

from collections import Counter, defaultdict
import logging
from pathlib import Path
import random
import secrets
import sqlite3
import psycopg
from threading import RLock
from typing import Any, Callable
from uuid import UUID

from backup_pool import get_backup_question
from generation_agent import call_llm as generation_call_llm
from get_next_question import GenerationUnavailable, get_next_question, record_answer
import llm_client
from llm_client import LLMCallError
from schema import QuestionOut
from staircase import DB_PATH, Staircase, TOPIC_ORDER

from analytics_store import (
    AnalyticsConflictError,
    AnalyticsStore,
)
from db import StorageNotConfiguredError
from attempt_store import AttemptContext, AttemptStore, StoredQuestion
from models import (
    AnswerResponse,
    AttemptResponse,
    JourneyPoint,
    LanguageCode,
    MisconceptionResult,
    NextQuestionResponse,
    Progress,
    QuestionDTO,
    QuestionOptionDTO,
    ResultsResponse,
    ReviewResult,
    RuntimeStatus,
    ScoreSummary,
    StartAttemptRequest,
    SubmitAnswerRequest,
    TopicResult,
)
from runtime import PROJECT_ROOT, RuntimeInspector


STATE_FIELDS = ("current_difficulty", "topic_index", "questions_answered", "correct_count")
LOGGER = logging.getLogger("exam_not_found.api.analytics")


class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def _safe_close(staircase: Any) -> None:
    try:
        staircase.close()
    except Exception:
        # A cleanup error must not replace a successful backend operation.
        pass


def _matches(actual: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    return actual is not None and all(actual.get(key) == expected.get(key) for key in STATE_FIELDS)


def _expected_post(pre: dict[str, Any], correct: bool) -> dict[str, Any]:
    expected = dict(pre)
    expected["current_difficulty"] = max(
        1, min(5, pre["current_difficulty"] + (1 if correct else -1))
    )
    expected["topic_index"] = pre["topic_index"] + 1
    expected["questions_answered"] = pre["questions_answered"] + 1
    expected["correct_count"] = pre["correct_count"] + int(correct)
    return expected


class AssessmentService:
    def __init__(
        self,
        *,
        store: AttemptStore | None = None,
        runtime_inspector: RuntimeInspector | None = None,
        staircase_factory: Callable[[str], Any] | None = None,
        sampler_factory: Callable[[], Any] | None = None,
        get_next_fn: Callable[..., QuestionOut | None] = get_next_question,
        record_fn: Callable[..., dict[str, Any]] = record_answer,
        backup_fn: Callable[..., QuestionOut | None] = get_backup_question,
        generation_fn: Callable[..., str] = generation_call_llm,
        critique_fn: Callable[..., str] = llm_client.critique_question_json,
        staircase_db_path: str | None = None,
        randomizer: random.Random | random.SystemRandom | None = None,
        analytics_store: AnalyticsStore | None = None,
    ) -> None:
        self.runtime_inspector = runtime_inspector or RuntimeInspector()
        self.store = store or AttemptStore(runtime_inspector=self.runtime_inspector)
        self.staircase_factory = staircase_factory or (lambda path: Staircase(db_path=path))
        self.sampler_factory = sampler_factory or self._default_sampler_factory
        self.get_next_fn = get_next_fn
        self.record_fn = record_fn
        self.backup_fn = backup_fn
        self.generation_fn = generation_fn
        self.critique_fn = critique_fn
        self.staircase_db_path = staircase_db_path or str((PROJECT_ROOT / DB_PATH).resolve())
        self.randomizer = randomizer or random.SystemRandom()
        self.analytics_store = analytics_store or AnalyticsStore()
        self._analytics_initialized = False
        self._analytics_init_lock = RLock()

    def initialize_analytics(self) -> None:
        """Initialize the shared store without retaining a SQLite connection."""
        if self._analytics_initialized:
            return
        with self._analytics_init_lock:
            if not self._analytics_initialized:
                self.analytics_store.initialize()
                self._analytics_initialized = True

    @staticmethod
    def _log_analytics_failure(operation: str, exc: Exception) -> None:
        LOGGER.error(
            "Analytics %s failed: %s.%s",
            operation,
            type(exc).__module__,
            type(exc).__name__,
        )

    def _require_analytics(self) -> None:
        try:
            self.initialize_analytics()
        except StorageNotConfiguredError as exc:
            LOGGER.error("Storage not configured: %s", exc)
            raise ServiceError(503, "STORAGE_NOT_CONFIGURED", str(exc)) from None
        except Exception as exc:
            self._log_analytics_failure("initialization", exc)
            raise ServiceError(
                503,
                "ANALYTICS_UNAVAILABLE",
                "We couldn't safely start this assessment. Please retry.",
                retryable=True,
            ) from None

    @staticmethod
    def _default_sampler_factory() -> Any:
        from chunk_sampler import ChunkSampler

        return ChunkSampler()

    def _attempt(self, attempt_id: UUID) -> AttemptContext:
        attempt = self.store.get(attempt_id)
        if attempt is None:
            raise ServiceError(404, "ATTEMPT_NOT_FOUND", "This assessment attempt was not found.")
        return attempt

    def _read_state(self, attempt: AttemptContext) -> tuple[dict[str, Any] | None, Exception | None]:
        staircase = None
        state = None
        error = None
        try:
            staircase = self.staircase_factory(attempt.staircase_db_path)
            state = staircase.get_or_create_student(attempt.backend_student_key)
        except Exception as exc:
            error = exc
        finally:
            if staircase is not None:
                _safe_close(staircase)
        return state, error

    @staticmethod
    def _progress(answered: int) -> Progress:
        total = len(TOPIC_ORDER)
        return Progress(
            answered=answered,
            total=total,
            percent=round(answered / total * 100, 1) if total else 0.0,
        )

    def create_attempt(self, request: StartAttemptRequest) -> AttemptResponse:
        # Refuse to create business state when durable analytics is unavailable.
        # This avoids presenting an attempt that was never registered durably.
        self._require_analytics()
        attempt_id = self.store.create_id()
        backend_key = f"{request.student_id}::attempt::{secrets.token_urlsafe(12)}"
        runtime = self.runtime_inspector.for_language(request.language)
        chunk_sampler = None
        live_dependencies_configured = (
            runtime.chroma_configured
            and runtime.collection_available
            and runtime.gemini_configured
        )
        if live_dependencies_configured:
            try:
                chunk_sampler = self.sampler_factory()
            except Exception:
                runtime = runtime.model_copy(
                    update={
                        "pipeline": "degraded",
                        "message": (
                        "Verified fallback is available while live generation is unavailable."
                        if runtime.fallback_available
                        else "Assessment generation is not currently configured."
                        ),
                    }
                )

        staircase = self.staircase_factory(self.staircase_db_path)
        try:
            state = staircase.get_or_create_student(backend_key, language=request.language)
            if state["language"] != request.language:
                raise ServiceError(
                    409,
                    "LANGUAGE_CONFLICT",
                    "This assessment identity belongs to another language track.",
                )
        finally:
            _safe_close(staircase)

        attempt = AttemptContext(
            attempt_id=attempt_id,
            visible_student_id=request.student_id,
            backend_student_key=backend_key,
            language=request.language,
            staircase_db_path=self.staircase_db_path,
            chunk_sampler=chunk_sampler,
            runtime=runtime,
            current_adaptive_difficulty=state["current_difficulty"],
            adaptive_journey=[state["current_difficulty"]],
        )
        try:
            self.analytics_store.create_attempt(
                attempt_id=attempt.attempt_id,
                student_id=attempt.visible_student_id,
                language=attempt.language,
                initial_difficulty=state["current_difficulty"],
                created_at=attempt.created_at,
            )
        except Exception as exc:
            self._log_analytics_failure("attempt creation", exc)
            raise ServiceError(
                503,
                "ANALYTICS_SAVE_FAILED",
                "We couldn't safely save this assessment. Please retry.",
                retryable=True,
            ) from None
        self.store.add(attempt)
        return self._attempt_response(attempt)

    @staticmethod
    def _question_language(question: QuestionOut) -> str:
        return question.language.value if hasattr(question.language, "value") else str(question.language)

    @staticmethod
    def _known_generation_error(exc: Exception) -> bool:
        module_name = type(exc).__module__
        return isinstance(exc, (GenerationUnavailable, LLMCallError, psycopg.Error, sqlite3.Error, OSError, ImportError)) or module_name.startswith(
            ("chromadb.", "google.genai.", "httpx.")
        )

    def _live_on_cooldown(self) -> bool:
        checker = getattr(self.runtime_inspector, "live_generation_on_cooldown", None)
        return bool(checker()) if callable(checker) else False

    def _note_llm_failure(self, exc: LLMCallError) -> None:
        notifier = getattr(self.runtime_inspector, "note_llm_failure", None)
        if callable(notifier):
            notifier(exc)

    def _current_generation_state(
        self, attempt: AttemptContext
    ) -> tuple[dict[str, Any], str | None, int]:
        """Read curriculum state with a connection created and closed in this thread."""
        staircase = None
        try:
            staircase = self.staircase_factory(attempt.staircase_db_path)
            state = staircase.get_or_create_student(attempt.backend_student_key)
            if state["language"] != attempt.language:
                raise ServiceError(
                    409,
                    "LANGUAGE_CONFLICT",
                    "This assessment is locked to a different language track.",
                )
            topic = staircase.get_current_topic(attempt.backend_student_key)
            difficulty = staircase.get_current_difficulty(attempt.backend_student_key)
            return dict(state), topic, difficulty
        except ServiceError:
            raise
        except (psycopg.Error, sqlite3.Error, OSError) as exc:
            raise ServiceError(
                503,
                "GENERATION_UNAVAILABLE",
                "We couldn't prepare the next question right now.",
                retryable=True,
            ) from exc
        finally:
            if staircase is not None:
                _safe_close(staircase)

    def _question_dto(self, stored: StoredQuestion) -> QuestionDTO:
        options = [
            QuestionOptionDTO(
                id=option_id,
                label=chr(65 + display_index),
                text=stored.question.options[original_index].text,
            )
            for display_index, (option_id, original_index) in enumerate(
                zip(stored.option_ids, stored.option_order)
            )
        ]
        return QuestionDTO(
            question_id=stored.question_id,
            question_number=stored.question_number,
            question=stored.question.question,
            topic=stored.question.topic,
            language=self._question_language(stored.question),
            source=stored.source,
            options=options,
        )

    def _mark_attempt_complete(self, attempt: AttemptContext, final_difficulty: int) -> None:
        """Persist backend-proven completion without changing backend truth."""
        attempt.complete = True
        attempt.current_question_id = None
        attempt.current_adaptive_difficulty = final_difficulty
        if attempt.analytics_completion_confirmed:
            return
        try:
            self.analytics_store.mark_attempt_completed(
                attempt.attempt_id,
                final_difficulty,
            )
        except Exception as exc:
            self._log_analytics_failure("attempt completion", exc)
            raise ServiceError(
                503,
                "ANALYTICS_SAVE_FAILED",
                "Your assessment is complete, but its report is still being synchronized. Please retry.",
                retryable=True,
            ) from None
        attempt.analytics_completion_confirmed = True

    def _attempt_response(self, attempt: AttemptContext) -> AttemptResponse:
        current = attempt.questions.get(attempt.current_question_id or "")
        answered = len(attempt.response_logs)
        return AttemptResponse(
            attempt_id=attempt.attempt_id,
            student_id=attempt.visible_student_id,
            language=attempt.language,
            current_adaptive_difficulty=attempt.current_adaptive_difficulty,
            progress=self._progress(answered),
            runtime=attempt.runtime,
            current_question=self._question_dto(current) if current else None,
            current_answer=current.answer_result if current else None,
            answer_state=current.answer_state if current else None,
            can_request_next=(
                current is None
                or (current.answer_state == "saved" and current.analytics_confirmed)
            ),
            complete=attempt.complete,
            created_at=attempt.created_at,
        )

    def get_attempt(self, attempt_id: UUID) -> AttemptResponse:
        attempt = self._attempt(attempt_id)
        with attempt.lock:
            return self._attempt_response(attempt)

    def next_question(self, attempt_id: UUID) -> NextQuestionResponse:
        attempt = self._attempt(attempt_id)
        try:
            return self._next_question_locked(attempt)
        finally:
            # Vercel functions are stateless -- persist whatever this
            # request mutated (questions, difficulty, completion, ...)
            # back to Postgres before returning. See attempt_store.py.
            self.store.save(attempt)

    def _next_question_locked(self, attempt: AttemptContext) -> NextQuestionResponse:
        with attempt.lock:
            current = attempt.questions.get(attempt.current_question_id or "")
            if current is not None and current.answer_state == "open":
                return NextQuestionResponse(
                    status="question",
                    question=self._question_dto(current),
                    current_adaptive_difficulty=attempt.current_adaptive_difficulty,
                    progress=self._progress(len(attempt.response_logs)),
                    complete=False,
                )
            if (
                current is not None
                and current.answer_state == "saved"
                and not current.analytics_confirmed
            ):
                raise ServiceError(
                    503,
                    "ANALYTICS_SAVE_FAILED",
                    "Your answer is saved, but its report is still being synchronized. Retry saving the same answer.",
                    retryable=True,
                )
            if current is not None and current.answer_state != "saved":
                raise ServiceError(
                    409,
                    "ANSWER_REQUIRED",
                    "Save the current answer before requesting another question.",
                )
            if attempt.complete:
                self._mark_attempt_complete(
                    attempt, attempt.current_adaptive_difficulty
                )
                return NextQuestionResponse(
                    status="complete",
                    current_adaptive_difficulty=attempt.current_adaptive_difficulty,
                    progress=self._progress(len(attempt.response_logs)),
                    complete=True,
                )

            attempt.runtime = self.runtime_inspector.for_language(attempt.language)
            state, topic, difficulty = self._current_generation_state(attempt)
            question = None
            source = "live"
            live_completed = False
            live_failed = False
            if topic is None:
                self._mark_attempt_complete(attempt, difficulty)
                return NextQuestionResponse(
                    status="complete",
                    current_adaptive_difficulty=difficulty,
                    progress=self._progress(len(attempt.response_logs)),
                    complete=True,
                )

            live_dependencies_configured = (
                attempt.runtime.chroma_configured
                and attempt.runtime.collection_available
                and attempt.runtime.gemini_configured
                and attempt.chunk_sampler is not None
            )
            live_skip_reason: str | None = None
            if not live_dependencies_configured:
                live_skip_reason = (
                    f"live generation not configured (chunks_present={attempt.runtime.chroma_configured}, "
                    f"language_chunks={attempt.runtime.collection_available}, "
                    f"gemini_key={attempt.runtime.gemini_configured}, "
                    f"sampler={attempt.chunk_sampler is not None})"
                )
            elif self._live_on_cooldown():
                live_skip_reason = "live generation is on cooldown after transient provider errors"
            if live_dependencies_configured and not self._live_on_cooldown():
                staircase = None
                try:
                    staircase = self.staircase_factory(attempt.staircase_db_path)
                    question = self.get_next_fn(
                        student_id=attempt.backend_student_key,
                        chunk_sampler=attempt.chunk_sampler,
                        generation_call_llm_fn=self.generation_fn,
                        critique_call_llm_fn=self.critique_fn,
                        staircase=staircase,
                    )
                    live_completed = question is None
                except (GenerationUnavailable, LLMCallError) as exc:
                    live_failed = True
                    live_skip_reason = f"{type(exc).__name__}: {str(exc)[:300]}"
                    if isinstance(exc, LLMCallError):
                        self._note_llm_failure(exc)
                        attempt.runtime = self.runtime_inspector.for_language(attempt.language)
                except Exception as exc:
                    if not self._known_generation_error(exc):
                        raise
                    live_failed = True
                    live_skip_reason = f"{type(exc).__name__}: {str(exc)[:300]}"
                finally:
                    if staircase is not None:
                        _safe_close(staircase)

            if live_completed:
                self._mark_attempt_complete(attempt, difficulty)
                return NextQuestionResponse(
                    status="complete",
                    current_adaptive_difficulty=difficulty,
                    progress=self._progress(len(attempt.response_logs)),
                    complete=True,
                )

            if question is None:
                source = "fallback"
                # Visible in Vercel -> Logs. Every fallback question means the AI
                # pipeline was NOT used, so say why instead of degrading silently.
                LOGGER.warning(
                    "Serving verified fallback question (topic=%s, language=%s, difficulty=%s): %s",
                    topic,
                    attempt.language,
                    difficulty,
                    live_skip_reason or "unknown reason",
                )
                if live_failed:
                    # Reconcile with the current SQLite truth after the failed live call.
                    state, topic, difficulty = self._current_generation_state(attempt)
                    if topic is None:
                        self._mark_attempt_complete(attempt, difficulty)
                        return NextQuestionResponse(
                            status="complete",
                            current_adaptive_difficulty=difficulty,
                            progress=self._progress(len(attempt.response_logs)),
                            complete=True,
                        )
                if topic is not None and attempt.runtime.fallback_available:
                    try:
                        question = self.backup_fn(topic, attempt.language, difficulty)
                    except (psycopg.Error, sqlite3.Error, OSError):
                        question = None
                if question is None:
                    raise ServiceError(
                        503,
                        "GENERATION_UNAVAILABLE",
                        "We couldn't prepare the next question right now.",
                        retryable=True,
                    ) from None

            if self._question_language(question) != attempt.language:
                raise ServiceError(
                    503,
                    "LANGUAGE_MISMATCH",
                    "The prepared question did not match this assessment language.",
                    retryable=True,
                )

            question_number = len(attempt.question_order) + 1
            question_id = f"q{question_number:03d}"
            option_order = list(range(len(question.options)))
            self.randomizer.shuffle(option_order)
            if len(option_order) > 1 and option_order == list(range(len(question.options))):
                option_order = option_order[1:] + option_order[:1]
            option_ids = tuple(f"opt_{secrets.token_urlsafe(8)}" for _ in option_order)
            stored = StoredQuestion(
                question_id=question_id,
                question_number=question_number,
                question=question,
                source=source,
                requested_difficulty=difficulty,
                state_before=dict(state or {}),
                option_order=tuple(option_order),
                option_ids=option_ids,
                option_to_original=dict(zip(option_ids, option_order)),
            )
            attempt.questions[question_id] = stored
            attempt.question_order.append(question_id)
            attempt.current_question_id = question_id
            attempt.current_adaptive_difficulty = difficulty
            return NextQuestionResponse(
                status="question",
                question=self._question_dto(stored),
                current_adaptive_difficulty=difficulty,
                progress=self._progress(len(attempt.response_logs)),
                complete=False,
            )

    def _prepare_analytics_answer(
        self,
        attempt: AttemptContext,
        stored: StoredQuestion,
        selected_option_id: str,
    ) -> None:
        """Persist immutable submission data before adaptive state is touched.

        ``selected_option_index`` is the zero-based browser/display position in
        the server-frozen option order.  Correctness remains derived from the
        private display-ID-to-original-option mapping.
        """
        original_index = stored.option_to_original[selected_option_id]
        display_index = stored.option_ids.index(selected_option_id)
        selected_option = stored.question.options[original_index]
        correct_option = next(option for option in stored.question.options if option.correct)
        is_correct = bool(selected_option.correct)
        difficulty_score = (
            stored.question.difficulty_score
            or stored.question.difficulty.difficulty_score
            or stored.requested_difficulty
        )
        try:
            self.analytics_store.prepare_answer(
                attempt_id=attempt.attempt_id,
                question_id=stored.question_id,
                question_number=stored.question_number,
                language=attempt.language,
                topic=stored.question.topic,
                question_text=stored.question.question,
                selected_option_index=display_index,
                selected_answer_text=selected_option.text,
                correct_answer_text=correct_option.text,
                correct=is_correct,
                misconception=None if is_correct else selected_option.misconception,
                difficulty_score=difficulty_score,
                requested_difficulty=stored.requested_difficulty,
                adaptive_level_before=stored.state_before["current_difficulty"],
                # The authoritative post-answer level is unknown until the
                # existing reconciliation path proves the backend write.
                adaptive_level_after=None,
                source_reference=stored.question.source_chunk_id,
            )
        except AnalyticsConflictError as exc:
            self._log_analytics_failure("answer preparation conflict", exc)
            raise ServiceError(
                409,
                "ANSWER_SYNC_REQUIRED",
                "Your answer could not be safely synchronized. Please contact the assessment administrator.",
            ) from None
        except Exception as exc:
            self._log_analytics_failure("answer preparation", exc)
            raise ServiceError(
                503,
                "ANALYTICS_SAVE_FAILED",
                "We couldn't safely prepare this answer. Please retry.",
                retryable=True,
            ) from None

    def _confirm_analytics_answer(
        self,
        attempt: AttemptContext,
        stored: StoredQuestion,
        adaptive_level_after: int,
    ) -> None:
        """Confirm analytics only after existing backend reconciliation succeeds."""
        if stored.analytics_confirmed:
            return
        try:
            self.analytics_store.confirm_answer(
                attempt.attempt_id,
                stored.question_id,
                adaptive_level_after=adaptive_level_after,
            )
        except Exception as exc:
            self._log_analytics_failure("answer confirmation", exc)
            raise ServiceError(
                503,
                "ANALYTICS_SAVE_FAILED",
                "Your answer is saved, but its report is still being synchronized. Please retry the same answer.",
                retryable=True,
            ) from None
        stored.analytics_confirmed = True

    def _mark_analytics_answer_failed(
        self,
        attempt: AttemptContext,
        stored: StoredQuestion,
    ) -> None:
        """Best-effort mirror of a definite backend failure.

        Failure here must never replace the existing answer-save error or cause
        the non-idempotent backend update to run again.
        """
        try:
            self.analytics_store.mark_answer_failed(
                attempt.attempt_id,
                stored.question_id,
            )
        except Exception as exc:
            self._log_analytics_failure("answer failure marking", exc)

    def _persist_answer(
        self,
        attempt: AttemptContext,
        stored: StoredQuestion,
        correct: bool,
    ) -> tuple[str, dict[str, Any] | None]:
        pre = stored.state_before
        expected = _expected_post(pre, correct)
        current, current_error = self._read_state(attempt)
        if _matches(current, expected):
            return "saved", current
        if current_error is not None:
            return "definitely_failed", current
        if not _matches(current, pre):
            return "ambiguous", current

        staircase = None
        updated = None
        invoked = False
        try:
            staircase = self.staircase_factory(attempt.staircase_db_path)
            invoked = True
            updated = self.record_fn(
                attempt.backend_student_key,
                correct,
                staircase=staircase,
            )
        except Exception:
            pass
        finally:
            if staircase is not None:
                _safe_close(staircase)

        if _matches(updated, expected):
            return "saved", updated
        if not invoked:
            return "definitely_failed", current

        reconciled, _ = self._read_state(attempt)
        if _matches(reconciled, expected):
            return "saved", reconciled
        if _matches(reconciled, pre):
            return "definitely_failed", reconciled
        return "ambiguous", reconciled

    def _finalize_answer(
        self,
        attempt: AttemptContext,
        stored: StoredQuestion,
        selected_option_id: str,
        state: dict[str, Any],
    ) -> AnswerResponse:
        selected_index = stored.option_to_original[selected_option_id]
        selected_option = stored.question.options[selected_index]
        correct_index = next(
            index for index, option in enumerate(stored.question.options) if option.correct
        )
        correct_option = stored.question.options[correct_index]
        correct_option_id = next(
            option_id
            for option_id, original_index in stored.option_to_original.items()
            if original_index == correct_index
        )
        is_correct = bool(selected_option.correct)
        difficulty_score = (
            stored.question.difficulty_score
            or stored.question.difficulty.difficulty_score
            or stored.requested_difficulty
        )
        log = {
            "question_id": stored.question_id,
            "question_index": stored.question_number - 1,
            "question": stored.question.question,
            "topic": stored.question.topic,
            "language": attempt.language,
            "source_chunk_id": stored.question.source_chunk_id,
            "selected_option_index": selected_index,
            "correct_option_index": correct_index,
            "selected_answer": selected_option.text,
            "correct_answer": correct_option.text,
            "correct": is_correct,
            "misconception": None if is_correct else selected_option.misconception,
            "difficulty_score": difficulty_score,
            "requested_difficulty": stored.requested_difficulty,
            "question_source": stored.source,
            "adaptive_difficulty_before": stored.state_before["current_difficulty"],
            "adaptive_difficulty_after": state["current_difficulty"],
        }
        if not any(row["question_id"] == stored.question_id for row in attempt.response_logs):
            attempt.response_logs.append(log)
        attempt.current_adaptive_difficulty = state["current_difficulty"]
        if not attempt.adaptive_journey or attempt.adaptive_journey[-1] != state["current_difficulty"]:
            attempt.adaptive_journey.append(state["current_difficulty"])
        else:
            # Preserve a step even when difficulty is clamped at a bound.
            attempt.adaptive_journey.append(state["current_difficulty"])
        result = AnswerResponse(
            question_id=stored.question_id,
            selected_option_id=selected_option_id,
            correct_option_id=correct_option_id,
            selected_answer=selected_option.text,
            correct_answer=correct_option.text,
            correct=is_correct,
            misconception=log["misconception"],
            current_adaptive_difficulty=state["current_difficulty"],
            progress=self._progress(len(attempt.response_logs)),
            can_continue=state["topic_index"] < len(TOPIC_ORDER),
        )
        stored.answer_state = "saved"
        stored.answer_result = result
        return result

    def submit_answer(self, attempt_id: UUID, request: SubmitAnswerRequest) -> AnswerResponse:
        attempt = self._attempt(attempt_id)
        try:
            return self._submit_answer_locked(attempt, request)
        finally:
            self.store.save(attempt)

    def _submit_answer_locked(self, attempt: AttemptContext, request: SubmitAnswerRequest) -> AnswerResponse:
        with attempt.lock:
            stored = attempt.questions.get(request.question_id)
            if stored is None or attempt.current_question_id != request.question_id:
                raise ServiceError(409, "QUESTION_NOT_CURRENT", "This question is not open for submission.")
            if request.selected_option_id not in stored.option_to_original:
                raise ServiceError(422, "OPTION_INVALID", "Select one of the available options.")
            if stored.submitted_option_id and stored.submitted_option_id != request.selected_option_id:
                raise ServiceError(
                    409,
                    "ANSWER_CONFLICT",
                    "This question has already been submitted with another option.",
                )
            if stored.answer_state == "saved" and stored.answer_result is not None:
                self._confirm_analytics_answer(
                    attempt,
                    stored,
                    stored.answer_result.current_adaptive_difficulty,
                )
                return stored.answer_result
            if stored.answer_state == "ambiguous":
                raise ServiceError(
                    409,
                    "ANSWER_SYNC_REQUIRED",
                    "Your progress could not be safely synchronized. Please contact the assessment administrator.",
                )
            if stored.answer_state == "saving":
                raise ServiceError(409, "ANSWER_IN_PROGRESS", "This answer is already being saved.")

            stored.submitted_option_id = request.selected_option_id
            # Analytics preparation is deliberately before record_answer(). If
            # it fails, backend adaptive state is left untouched.
            self._prepare_analytics_answer(
                attempt,
                stored,
                request.selected_option_id,
            )
            stored.answer_state = "saving"
            selected_index = stored.option_to_original[request.selected_option_id]
            correct = bool(stored.question.options[selected_index].correct)
            outcome, state = self._persist_answer(attempt, stored, correct)
            stored.answer_state = outcome
            if outcome == "saved" and state is not None:
                result = self._finalize_answer(
                    attempt, stored, request.selected_option_id, state
                )
                # Finalize business state first: an analytics failure must not
                # make record_answer eligible to run again.
                self._confirm_analytics_answer(
                    attempt,
                    stored,
                    state["current_difficulty"],
                )
                return result
            if outcome == "definitely_failed":
                self._mark_analytics_answer_failed(attempt, stored)
                raise ServiceError(
                    503,
                    "ANSWER_SAVE_FAILED",
                    "We couldn't save your progress. Please retry this answer.",
                    retryable=True,
                )
            raise ServiceError(
                409,
                "ANSWER_SYNC_REQUIRED",
                "Your progress could not be safely synchronized. Please contact the assessment administrator.",
            )

    def results(self, attempt_id: UUID) -> ResultsResponse:
        attempt = self._attempt(attempt_id)
        with attempt.lock:
            rows = list(attempt.response_logs)
            if not rows:
                raise ServiceError(409, "RESULTS_NOT_READY", "Submit an answer before viewing results.")
            correct_count = sum(bool(row["correct"]) for row in rows)
            attempted = len(rows)
            topic_data: dict[str, dict[str, int]] = defaultdict(
                lambda: {"attempted": 0, "correct": 0, "incorrect": 0}
            )
            misconception_counts: Counter[str] = Counter()
            misconception_topics: dict[str, set[str]] = defaultdict(set)
            reviews = []
            for row in rows:
                values = topic_data[row["topic"]]
                values["attempted"] += 1
                values["correct" if row["correct"] else "incorrect"] += 1
                if not row["correct"] and row["misconception"]:
                    misconception_counts[row["misconception"]] += 1
                    misconception_topics[row["misconception"]].add(row["topic"])
                reviews.append(
                    ReviewResult(
                        question_id=row["question_id"],
                        question_number=row["question_index"] + 1,
                        question=row["question"],
                        topic=row["topic"],
                        language=row["language"],
                        difficulty=row["difficulty_score"],
                        selected_answer=row["selected_answer"],
                        correct_answer=row["correct_answer"],
                        correct=row["correct"],
                        misconception=row["misconception"] if not row["correct"] else None,
                    )
                )
            topics = [
                TopicResult(
                    topic=topic,
                    attempted=values["attempted"],
                    correct=values["correct"],
                    incorrect=values["incorrect"],
                    accuracy=round(values["correct"] / values["attempted"] * 100, 1),
                )
                for topic, values in sorted(topic_data.items(), key=lambda item: item[0].casefold())
            ]
            strongest = min(topics, key=lambda item: (-item.accuracy, item.topic.casefold())).topic
            weakest = min(topics, key=lambda item: (item.accuracy, item.topic.casefold())).topic
            misconceptions = [
                MisconceptionResult(
                    misconception=label,
                    occurrences=count,
                    topics=sorted(misconception_topics[label], key=str.casefold),
                )
                for label, count in sorted(
                    misconception_counts.items(), key=lambda item: (-item[1], item[0].casefold())
                )
            ]
            average_difficulty = round(
                sum(row["difficulty_score"] for row in rows) / attempted, 1
            )
            return ResultsResponse(
                attempt_id=attempt.attempt_id,
                student_id=attempt.visible_student_id,
                language=attempt.language,
                complete=attempt.complete,
                summary=ScoreSummary(
                    score=correct_count,
                    attempted=attempted,
                    accuracy=round(correct_count / attempted * 100, 1),
                    correct=correct_count,
                    incorrect=attempted - correct_count,
                    final_adaptive_difficulty=attempt.current_adaptive_difficulty,
                    average_question_difficulty=average_difficulty,
                ),
                topics=topics,
                strongest_topic=strongest,
                needs_attention_topic=weakest,
                misconceptions=misconceptions,
                question_review=reviews,
                adaptive_journey=[
                    JourneyPoint(step=index, difficulty=difficulty)
                    for index, difficulty in enumerate(attempt.adaptive_journey)
                ],
            )
