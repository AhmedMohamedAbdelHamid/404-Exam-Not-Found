from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import random
import sqlite3
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.assessment_service import AssessmentService
from api.attempt_store import AttemptStore
from api.main import create_app
from api.models import HealthResponse, RuntimeStatus
from api.runtime import RuntimeInspector
from get_next_question import GenerationUnavailable
from llm_client import LLMCallError
from schema import DifficultySubScores, LanguageEnum, QuestionOption, QuestionOut


TOPICS = [
    "algorithm",
    "variables and assignment",
    "loops and conditionals",
    "lists",
    "functions",
]


def question(language="en", topic="algorithm", difficulty=3):
    return QuestionOut(
        question=f"Question about {topic}",
        topic=topic,
        language=LanguageEnum(language),
        source_chunk_id=f"{language}_{topic}",
        options=[
            QuestionOption(text="Correct", correct=True),
            QuestionOption(text="Wrong A", correct=False, misconception="error A"),
            QuestionOption(text="Wrong B", correct=False, misconception="error B"),
            QuestionOption(text="Wrong C", correct=False, misconception="error C"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=difficulty,
            bloom_justification="test",
            distractor_quality=difficulty,
            distractor_justification="test",
            concept_depth=difficulty,
            concept_depth_justification="test",
        ),
        difficulty_score=difficulty,
        validated=True,
    )


class FakeStaircase:
    stores = {}
    instances = []

    def __init__(self, db_path):
        self.db_path = db_path
        self.store = self.stores.setdefault(db_path, {})
        self.closed = False
        self.instances.append(self)

    @classmethod
    def reset(cls):
        cls.stores = {}
        cls.instances = []

    def get_or_create_student(self, student_id, language="en"):
        return self.store.setdefault(
            student_id,
            {
                "student_id": student_id,
                "language": language,
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
        )

    def get_current_topic(self, student_id):
        state = self.get_or_create_student(student_id)
        return TOPICS[state["topic_index"]] if state["topic_index"] < len(TOPICS) else None

    def get_current_difficulty(self, student_id):
        return self.get_or_create_student(student_id)["current_difficulty"]

    def close(self):
        self.closed = True


class FakeRuntime:
    def __init__(self, configured=True, fallback=True):
        self.configured = configured
        self.fallback = fallback
        self.cooldown = False

    def live_generation_on_cooldown(self):
        return self.cooldown

    def note_llm_failure(self, error):
        cause = error.__cause__
        if getattr(cause, "code", None) in {429, 500, 502, 503, 504}:
            self.cooldown = True
            return True
        return False

    def for_language(self, language):
        return RuntimeStatus(
            pipeline="configured" if self.configured and not self.cooldown else "degraded",
            chroma_configured=self.configured,
            collection_available=self.configured,
            gemini_configured=self.configured,
            fallback_available=self.fallback,
            message="AI pipeline configured with verified fallback.",
        )

    def health(self):
        return HealthResponse(
            chroma_configured=self.configured,
            english_collection_available=self.configured,
            arabic_collection_available=self.configured,
            gemini_configured=self.configured,
            fallback_available=self.fallback,
            status="configured" if self.configured else "fallback_available",
        )


class Harness:
    def __init__(self, tmp_path, *, configured=True, get_next_fn=None, record_fn=None, backup_fn=None):
        FakeStaircase.reset()
        self.record_calls = 0
        self.sampler = object()
        self.sampler_calls = []

        def default_get_next(**kwargs):
            self.sampler_calls.append(kwargs["chunk_sampler"])
            staircase = kwargs["staircase"]
            student_id = kwargs["student_id"]
            topic = staircase.get_current_topic(student_id)
            language = staircase.get_or_create_student(student_id)["language"]
            return question(language, topic, staircase.get_current_difficulty(student_id))

        def default_record(student_id, correct, staircase=None):
            self.record_calls += 1
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] = max(
                1, min(5, state["current_difficulty"] + (1 if correct else -1))
            )
            state["topic_index"] += 1
            state["questions_answered"] += 1
            state["correct_count"] += int(correct)
            return dict(state)

        self.service = AssessmentService(
            store=AttemptStore(),
            runtime_inspector=FakeRuntime(configured=configured),
            staircase_factory=FakeStaircase,
            sampler_factory=lambda: self.sampler,
            get_next_fn=get_next_fn or default_get_next,
            record_fn=record_fn or default_record,
            backup_fn=backup_fn or (lambda topic, language, difficulty: question(language, topic, difficulty)),
            staircase_db_path=str(tmp_path / "state.db"),
            randomizer=random.Random(7),
        )
        self.client = TestClient(create_app(self.service), raise_server_exceptions=False)

    def start(self, language="en", student="qa_student"):
        response = self.client.post(
            "/api/attempts", json={"student_id": student, "language": language}
        )
        assert response.status_code == 201
        return response.json()

    def next(self, attempt_id):
        return self.client.post(f"/api/attempts/{attempt_id}/next")

    def option(self, attempt_id, *, correct):
        attempt = self.service.store.get(UUID(attempt_id))
        stored = attempt.questions[attempt.current_question_id]
        return next(
            option_id
            for option_id, original_index in stored.option_to_original.items()
            if bool(stored.question.options[original_index].correct) is correct
        )


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def test_start_english_attempt_and_trim_identifier(harness):
    started = harness.start(student="  qa_student  ")
    assert started["student_id"] == "qa_student"
    assert started["language"] == "en"
    assert started["current_adaptive_difficulty"] == 3


def test_start_arabic_explicitly_initializes_language(harness):
    started = harness.start("ar")
    attempt = harness.service.store.get(UUID(started["attempt_id"]))
    state = FakeStaircase.stores[attempt.staircase_db_path][attempt.backend_student_key]
    assert state["language"] == "ar"


def test_blank_student_validation_is_safe(harness):
    response = harness.client.post("/api/attempts", json={"student_id": "   ", "language": "en"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "traceback" not in response.text.lower()


def test_attempt_uses_private_unique_backend_keys(harness):
    first = harness.start()
    second = harness.start()
    first_context = harness.service.store.get(UUID(first["attempt_id"]))
    second_context = harness.service.store.get(UUID(second["attempt_id"]))
    assert first_context.backend_student_key != second_context.backend_student_key
    assert "backend_student_key" not in first


def test_same_chunk_sampler_is_reused_for_attempt(harness):
    started = harness.start()
    first = harness.next(started["attempt_id"]).json()["question"]
    selected = harness.option(started["attempt_id"], correct=True)
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": first["question_id"], "selected_option_id": selected},
    )
    harness.next(started["attempt_id"])
    assert harness.sampler_calls == [harness.sampler, harness.sampler]


def test_staircase_is_fresh_and_closed_per_operation(harness):
    started = harness.start()
    harness.next(started["attempt_id"])
    selected = harness.option(started["attempt_id"], correct=True)
    question_id = harness.service.store.get(UUID(started["attempt_id"])).current_question_id
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": question_id, "selected_option_id": selected},
    )
    assert len({id(instance) for instance in FakeStaircase.instances}) == len(FakeStaircase.instances)
    assert all(instance.closed for instance in FakeStaircase.instances)


def test_question_dto_never_exposes_answer_key(harness):
    started = harness.start()
    dto = harness.next(started["attempt_id"]).json()["question"]
    serialized = str(dto).lower()
    assert all(set(option) == {"id", "label", "text"} for option in dto["options"])
    assert "misconception" not in serialized
    assert "correct_option" not in serialized
    assert "source_chunk_id" not in serialized


def test_server_option_permutation_is_stable_across_reload(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    reloaded = harness.client.get(
        f'/api/attempts/{started["attempt_id"]}'
    ).json()["current_question"]
    assert delivered["options"] == reloaded["options"]


def test_repeated_next_before_answer_returns_same_question_without_regeneration(harness):
    started = harness.start()
    first = harness.next(started["attempt_id"])
    second = harness.next(started["attempt_id"])
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert len(harness.sampler_calls) == 1


def test_correct_answer_updates_adaptive_level(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    answer = harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": delivered["question_id"], "selected_option_id": option_id},
    )
    assert answer.status_code == 200
    assert answer.json()["correct"] is True
    assert answer.json()["current_adaptive_difficulty"] == 4


def test_incorrect_answer_returns_misconception_and_decrements(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=False)
    answer = harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": delivered["question_id"], "selected_option_id": option_id},
    )
    assert answer.json()["correct"] is False
    assert answer.json()["misconception"]
    assert answer.json()["current_adaptive_difficulty"] == 2


def test_identical_duplicate_is_http_idempotent(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    payload = {"question_id": delivered["question_id"], "selected_option_id": option_id}
    first = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    second = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    assert first.json() == second.json()
    assert harness.record_calls == 1


def test_concurrent_duplicate_is_recorded_once(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    payload = {"question_id": delivered["question_id"], "selected_option_id": option_id}
    url = f'/api/attempts/{started["attempt_id"]}/answers'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: harness.client.post(url, json=payload), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert harness.record_calls == 1


def test_different_duplicate_returns_conflict(harness):
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    correct_id = harness.option(started["attempt_id"], correct=True)
    wrong_id = harness.option(started["attempt_id"], correct=False)
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": delivered["question_id"], "selected_option_id": correct_id},
    )
    conflict = harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": delivered["question_id"], "selected_option_id": wrong_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ANSWER_CONFLICT"


def test_post_write_exception_reconciles_without_retry(tmp_path):
    calls = []

    def persist_then_raise(student_id, correct, staircase=None):
        calls.append(1)
        state = staircase.get_or_create_student(student_id)
        state.update(current_difficulty=4, topic_index=1, questions_answered=1, correct_count=1)
        raise sqlite3.ProgrammingError("post-commit cleanup")

    harness = Harness(tmp_path, record_fn=persist_then_raise)
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    payload = {"question_id": delivered["question_id"], "selected_option_id": option_id}
    first = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    second = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    assert first.status_code == second.status_code == 200
    assert len(calls) == 1


def test_definite_failure_allows_safe_retry(tmp_path):
    calls = []

    def fail_before_write(*args, **kwargs):
        calls.append("failed")
        raise sqlite3.OperationalError("before mutation")

    harness = Harness(tmp_path, record_fn=fail_before_write)
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    payload = {"question_id": delivered["question_id"], "selected_option_id": option_id}
    failed = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    assert failed.status_code == 503
    assert failed.json()["error"]["retryable"] is True

    def succeeds(student_id, correct, staircase=None):
        calls.append("saved")
        state = staircase.get_or_create_student(student_id)
        state.update(current_difficulty=4, topic_index=1, questions_answered=1, correct_count=1)
        return dict(state)

    harness.service.record_fn = succeeds
    retried = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    assert retried.status_code == 200
    assert calls == ["failed", "saved"]


def test_ambiguous_state_blocks_unsafe_retry(tmp_path):
    calls = []

    def uncertain_write(student_id, correct, staircase=None):
        calls.append(1)
        state = staircase.get_or_create_student(student_id)
        state.update(current_difficulty=5, topic_index=2, questions_answered=2, correct_count=1)
        raise sqlite3.ProgrammingError("uncertain")

    harness = Harness(tmp_path, record_fn=uncertain_write)
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    option_id = harness.option(started["attempt_id"], correct=True)
    payload = {"question_id": delivered["question_id"], "selected_option_id": option_id}
    first = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    second = harness.client.post(f'/api/attempts/{started["attempt_id"]}/answers', json=payload)
    assert first.status_code == second.status_code == 409
    assert first.json()["error"]["code"] == "ANSWER_SYNC_REQUIRED"
    assert len(calls) == 1


def test_generation_unavailable_uses_fallback(tmp_path):
    def unavailable(**kwargs):
        raise GenerationUnavailable("simulated")

    harness = Harness(tmp_path, get_next_fn=unavailable)
    started = harness.start()
    delivered = harness.next(started["attempt_id"]).json()["question"]
    assert delivered["source"] == "fallback"


def test_llm_call_error_uses_sanitized_fallback_without_mutating_staircase(tmp_path):
    class QuotaError(Exception):
        code = 429

    calls = []

    def quota_exhausted(**kwargs):
        calls.append(1)
        raise LLMCallError("private provider detail") from QuotaError("quota")

    harness = Harness(tmp_path, get_next_fn=quota_exhausted)
    started = harness.start()
    attempt = harness.service.store.get(UUID(started["attempt_id"]))
    before = dict(FakeStaircase.stores[attempt.staircase_db_path][attempt.backend_student_key])

    response = harness.next(started["attempt_id"])
    assert response.status_code == 200
    delivered = response.json()["question"]
    assert delivered["source"] == "fallback"
    assert all(set(option) == {"id", "label", "text"} for option in delivered["options"])
    assert set(delivered) == {
        "question_id", "question_number", "question", "topic", "language", "source", "options"
    }
    assert "misconception" not in response.text.lower()
    after = FakeStaircase.stores[attempt.staircase_db_path][attempt.backend_student_key]
    assert after == before
    assert len(calls) == 1


def test_llm_failure_and_unavailable_backup_returns_safe_503(tmp_path):
    def unavailable(**kwargs):
        raise LLMCallError("private quota detail")

    harness = Harness(tmp_path, get_next_fn=unavailable, backup_fn=lambda *args: None)
    started = harness.start()
    response = harness.next(started["attempt_id"])
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "GENERATION_UNAVAILABLE",
            "message": "We couldn't prepare the next question right now.",
            "retryable": True,
        }
    }
    assert "quota" not in response.text.lower()


def test_concurrent_duplicate_next_generates_once_and_preserves_options(tmp_path):
    calls = []

    def generated(**kwargs):
        calls.append(1)
        staircase = kwargs["staircase"]
        student_id = kwargs["student_id"]
        state = staircase.get_or_create_student(student_id)
        return question(state["language"], staircase.get_current_topic(student_id), 3)

    harness = Harness(tmp_path, get_next_fn=generated)
    started = harness.start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: harness.next(started["attempt_id"]), range(2))
        )
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert responses[0].json()["question"]["options"] == responses[1].json()["question"]["options"]
    assert len(calls) == 1


def test_transient_llm_failure_activates_cooldown_and_skips_next_live_call(tmp_path):
    class ProviderUnavailable(Exception):
        code = 503

    calls = []

    def unavailable(**kwargs):
        calls.append(1)
        raise LLMCallError("provider unavailable") from ProviderUnavailable()

    harness = Harness(tmp_path, get_next_fn=unavailable)
    started = harness.start()
    first = harness.next(started["attempt_id"]).json()["question"]
    selected = harness.option(started["attempt_id"], correct=True)
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": first["question_id"], "selected_option_id": selected},
    )
    second = harness.next(started["attempt_id"])
    assert second.status_code == 200
    assert second.json()["question"]["source"] == "fallback"
    assert len(calls) == 1


def test_live_provider_cooldown_expires_automatically(tmp_path):
    class ProviderUnavailable(Exception):
        code = 429

    now = [100.0]
    runtime = RuntimeInspector(
        project_root=tmp_path,
        cooldown_seconds=30,
        clock=lambda: now[0],
    )
    failure = LLMCallError("provider failure")
    failure.__cause__ = ProviderUnavailable()
    assert runtime.note_llm_failure(failure) is True
    assert runtime.live_generation_on_cooldown() is True
    now[0] = 130.0
    assert runtime.live_generation_on_cooldown() is False


def test_backend_none_marks_attempt_complete(tmp_path):
    harness = Harness(tmp_path, get_next_fn=lambda **kwargs: None)
    started = harness.start()
    completed = harness.next(started["attempt_id"])
    assert completed.status_code == 200
    assert completed.json()["status"] == "complete"
    assert completed.json()["complete"] is True


def test_results_calculation_and_misconceptions(harness):
    started = harness.start()
    first = harness.next(started["attempt_id"]).json()["question"]
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": first["question_id"], "selected_option_id": harness.option(started["attempt_id"], correct=True)},
    )
    second = harness.next(started["attempt_id"]).json()["question"]
    harness.client.post(
        f'/api/attempts/{started["attempt_id"]}/answers',
        json={"question_id": second["question_id"], "selected_option_id": harness.option(started["attempt_id"], correct=False)},
    )
    results = harness.client.get(
        f'/api/attempts/{started["attempt_id"]}/results'
    ).json()
    assert results["summary"]["score"] == 1
    assert results["summary"]["attempted"] == 2
    assert results["summary"]["accuracy"] == 50.0
    assert len(results["misconceptions"]) == 1
    assert results["misconceptions"][0]["occurrences"] == 1
    assert results["question_review"][0]["misconception"] is None
    assert len(results["adaptive_journey"]) == 3


def test_teacher_demo_is_honestly_labeled(harness):
    response = harness.client.get("/api/demo/teacher")
    assert response.status_code == 200
    assert response.json()["label"] == "DEMO CLASS DATA · NOT LIVE"
    assert response.json()["summary"]["students"] == 10


def test_health_is_safe_and_contains_no_secret(harness, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "never-return-this-secret")
    response = harness.client.get("/api/health")
    assert response.status_code == 200
    assert "never-return-this-secret" not in response.text
    assert "gemini_configured" in response.json()


def test_unknown_attempt_and_internal_error_do_not_leak_tracebacks(tmp_path):
    harness = Harness(tmp_path, get_next_fn=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("private detail")))
    unknown = harness.client.get(f"/api/attempts/{uuid4()}")
    assert unknown.status_code == 404
    assert "traceback" not in unknown.text.lower()

    started = harness.start()
    failed = harness.next(started["attempt_id"])
    assert failed.status_code == 500
    assert "private detail" not in failed.text
    assert "traceback" not in failed.text.lower()
