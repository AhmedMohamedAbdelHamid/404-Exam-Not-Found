from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.analytics_store import AnalyticsStore
from api.assessment_service import AssessmentService
from api.attempt_store import AttemptStore
from api.main import create_app
from api.teacher_service import TeacherService


CREATED = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
TEST_TOKEN = "phase3-test-token"


@pytest.fixture
def store(tmp_path: Path) -> AnalyticsStore:
    analytics = AnalyticsStore(tmp_path / "teacher-analytics.db")
    analytics.initialize()
    return analytics


def create_attempt(
    store: AnalyticsStore,
    attempt_id: str,
    student_id: str,
    language: str,
    created_offset: int,
    *,
    completed: bool = False,
    final_difficulty: int = 3,
) -> None:
    created_at = CREATED + timedelta(minutes=created_offset)
    store.create_attempt(
        attempt_id=attempt_id,
        student_id=student_id,
        language=language,
        initial_difficulty=3,
        created_at=created_at,
    )
    if completed:
        store.mark_attempt_completed(
            attempt_id,
            final_difficulty,
            completed_at=created_at + timedelta(minutes=5),
        )


def add_answer(
    store: AnalyticsStore,
    attempt_id: str,
    question_id: str,
    question_number: int,
    *,
    language: str = "en",
    topic: str = "algorithm",
    correct: bool = True,
    misconception: str | None = None,
    difficulty: int = 3,
    status: str = "confirmed",
) -> None:
    store.prepare_answer(
        attempt_id=attempt_id,
        question_id=question_id,
        question_number=question_number,
        language=language,
        topic=topic,
        question_text=f"HIDDEN_QUESTION_{attempt_id}_{question_id}",
        selected_option_index=1,
        selected_answer_text=f"HIDDEN_SELECTED_{attempt_id}_{question_id}",
        correct_answer_text=f"HIDDEN_CORRECT_{attempt_id}_{question_id}",
        correct=correct,
        misconception=misconception,
        difficulty_score=difficulty,
        requested_difficulty=3,
        adaptive_level_before=3,
        adaptive_level_after=None,
        source_reference=f"chunk-{attempt_id}-{question_id}",
        created_at=CREATED + timedelta(minutes=question_number),
    )
    if status == "confirmed":
        store.confirm_answer(
            attempt_id,
            question_id,
            adaptive_level_after=4 if correct else 2,
            confirmed_at=CREATED + timedelta(minutes=question_number, seconds=30),
        )
    elif status == "failed":
        store.mark_answer_failed(attempt_id, question_id)


def seed_live_data(store: AnalyticsStore) -> None:
    create_attempt(store, "attempt-old", "shared-student", "en", 0)
    add_answer(store, "attempt-old", "q001", 1, topic="variables", correct=True, difficulty=3)
    add_answer(
        store,
        "attempt-old",
        "q002",
        2,
        topic="loops",
        correct=False,
        misconception="Boundary mistake",
        difficulty=4,
    )
    store.mark_attempt_completed(
        "attempt-old", 4, completed_at=CREATED + timedelta(minutes=5)
    )

    create_attempt(store, "attempt-progress", "student-beta", "en", 10)
    add_answer(store, "attempt-progress", "q001", 1, topic="algorithm", correct=True, difficulty=5)
    add_answer(store, "attempt-progress", "q002", 2, topic="lists", status="pending")
    add_answer(store, "attempt-progress", "q003", 3, topic="functions", status="failed")

    create_attempt(store, "attempt-new", "shared-student", "ar", 20)
    add_answer(
        store,
        "attempt-new",
        "q001",
        1,
        language="ar",
        topic="المتغيرات",
        correct=False,
        misconception="خطأ في الحدود",
        difficulty=2,
    )
    add_answer(
        store,
        "attempt-new",
        "q002",
        2,
        language="ar",
        topic="loops",
        correct=False,
        misconception="Boundary mistake",
        difficulty=2,
    )
    store.mark_attempt_completed(
        "attempt-new", 2, completed_at=CREATED + timedelta(minutes=25)
    )


def test_empty_database_returns_explicit_live_empty_payload(store: AnalyticsStore):
    report = TeacherService(store).live_analytics()
    assert report.data_source == "live"
    assert report.data_status == "empty"
    assert report.summary.model_dump() == {
        "total_students": 0,
        "total_attempts": 0,
        "completed_attempts": 0,
        "in_progress_attempts": 0,
        "completion_rate": 0.0,
        "confirmed_answers": 0,
        "correct_answers": 0,
        "incorrect_answers": 0,
        "overall_accuracy": 0.0,
        "average_score": 0.0,
        "average_difficulty": 0.0,
        "misconception_count": 0,
    }
    assert report.topics == report.misconceptions == report.score_distribution[:0] == []
    assert [(row.difficulty, row.count) for row in report.difficulty] == [
        (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)
    ]
    assert all(row.attempts == 0 for row in report.score_distribution)


def test_live_summary_uses_confirmed_rows_and_distinct_students(store: AnalyticsStore):
    seed_live_data(store)
    summary = TeacherService(store).live_analytics().summary
    assert summary.total_students == 2
    assert summary.total_attempts == 3
    assert summary.completed_attempts == 2
    assert summary.in_progress_attempts == 1
    assert summary.completion_rate == 66.7
    assert summary.confirmed_answers == 5
    assert summary.correct_answers == 2
    assert summary.incorrect_answers == 3
    assert summary.overall_accuracy == 40.0
    assert summary.average_score == 0.5
    assert summary.average_difficulty == 3.2
    assert summary.misconception_count == 3


def test_pending_and_failed_answers_never_contribute(store: AnalyticsStore):
    create_attempt(store, "attempt", "student", "en", 0)
    add_answer(store, "attempt", "pending", 1, status="pending")
    add_answer(store, "attempt", "failed", 2, status="failed", correct=False, misconception="Ignored")
    report = TeacherService(store).live_analytics()
    assert report.summary.confirmed_answers == 0
    assert report.topics == []
    assert report.misconceptions == []
    assert report.students[0].answered == 0


def test_topic_values_and_weak_order_are_deterministic(store: AnalyticsStore):
    seed_live_data(store)
    topics = TeacherService(store).live_analytics().topics
    assert [row.topic for row in topics] == [
        "loops",
        "المتغيرات",
        "algorithm",
        "variables",
    ]
    loops = topics[0]
    assert (loops.attempted, loops.correct, loops.incorrect, loops.accuracy) == (2, 0, 2, 0.0)
    assert topics[2].accuracy == topics[3].accuracy == 100.0


def test_topic_alphabetical_tie_break_is_case_stable(store: AnalyticsStore):
    create_attempt(store, "attempt", "student", "en", 0)
    add_answer(store, "attempt", "q1", 1, topic="beta", correct=False, misconception="m")
    add_answer(store, "attempt", "q2", 2, topic="Alpha", correct=False, misconception="m")
    topics = TeacherService(store).live_analytics().topics
    assert [row.topic for row in topics] == ["Alpha", "beta"]


def test_misconceptions_include_only_confirmed_incorrect_selected_signals(store: AnalyticsStore):
    seed_live_data(store)
    create_attempt(store, "extra", "student-extra", "en", 30)
    add_answer(store, "extra", "q1", 1, correct=True, misconception="Never count this")
    add_answer(store, "extra", "q2", 2, correct=False, misconception="   ")
    rows = TeacherService(store).live_analytics().misconceptions
    assert [(row.misconception, row.count) for row in rows] == [
        ("Boundary mistake", 2),
        ("خطأ في الحدود", 1),
    ]


def test_difficulty_and_completed_score_distributions_are_complete(store: AnalyticsStore):
    seed_live_data(store)
    report = TeacherService(store).live_analytics()
    assert [(row.difficulty, row.count) for row in report.difficulty] == [
        (1, 0), (2, 2), (3, 1), (4, 1), (5, 1)
    ]
    assert [(row.band, row.attempts) for row in report.score_distribution] == [
        ("0–20%", 1),
        ("21–40%", 0),
        ("41–60%", 1),
        ("61–80%", 0),
        ("81–100%", 0),
    ]


def test_completed_attempt_with_zero_answers_counts_as_zero_score(store: AnalyticsStore):
    create_attempt(store, "empty-complete", "student-a", "en", 0, completed=True)
    create_attempt(store, "perfect", "student-b", "en", 1)
    add_answer(store, "perfect", "q1", 1, correct=True)
    store.mark_attempt_completed("perfect", 4, completed_at=CREATED + timedelta(minutes=6))
    report = TeacherService(store).live_analytics()
    assert report.summary.average_score == 0.5
    assert report.score_distribution[0].attempts == 1
    assert report.score_distribution[-1].attempts == 1


def test_attempt_rows_keep_retries_separate_and_newest_first(store: AnalyticsStore):
    seed_live_data(store)
    rows = TeacherService(store).live_analytics().students
    assert [str(row.attempt_id) for row in rows] == [
        "attempt-new",
        "attempt-progress",
        "attempt-old",
    ]
    assert rows[0].student_id == rows[2].student_id == "shared-student"
    assert rows[0].language == "ar"
    assert rows[0].status == "completed"
    assert rows[1].status == "in_progress"


def test_service_survives_store_recreation_and_keeps_unicode(store: AnalyticsStore):
    seed_live_data(store)
    reopened = AnalyticsStore(store.db_path)
    reopened.initialize()
    report = TeacherService(reopened).live_analytics()
    assert report.summary.total_attempts == 3
    assert any(row.topic == "المتغيرات" for row in report.topics)
    assert any(row.misconception == "خطأ في الحدود" for row in report.misconceptions)


def endpoint_client(store: AnalyticsStore) -> TestClient:
    assessment = AssessmentService(
        store=AttemptStore(),
        analytics_store=store,
    )
    return TestClient(
        create_app(assessment, teacher_service=TeacherService(store)),
        raise_server_exceptions=False,
    )


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer", "Bearer wrong-token", "Bearer a b"],
)
def test_live_endpoint_rejects_missing_malformed_and_wrong_auth(
    store: AnalyticsStore,
    monkeypatch,
    authorization: str | None,
):
    monkeypatch.setenv("TEACHER_DASHBOARD_TOKEN", TEST_TOKEN)
    headers = {"Authorization": authorization} if authorization else {}
    response = endpoint_client(store).get("/api/teacher/live", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TEACHER_AUTH_REQUIRED"
    assert TEST_TOKEN not in response.text


def test_live_endpoint_fails_closed_without_server_token(store: AnalyticsStore, monkeypatch):
    monkeypatch.delenv("TEACHER_DASHBOARD_TOKEN", raising=False)
    response = endpoint_client(store).get(
        "/api/teacher/live",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TEACHER_AUTH_NOT_CONFIGURED"
    assert TEST_TOKEN not in response.text


def test_authorized_empty_endpoint_is_live_and_read_only(store: AnalyticsStore, monkeypatch):
    monkeypatch.setenv("TEACHER_DASHBOARD_TOKEN", TEST_TOKEN)
    before = store.read_snapshot()
    response = endpoint_client(store).get(
        "/api/teacher/live",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    after = store.read_snapshot()
    assert response.status_code == 200
    assert response.json()["data_source"] == "live"
    assert response.json()["data_status"] == "empty"
    assert before == after
    assert TEST_TOKEN not in response.text


def test_authorized_endpoint_uses_durable_rows_without_active_attempts(
    store: AnalyticsStore,
    monkeypatch,
):
    seed_live_data(store)
    reopened = AnalyticsStore(store.db_path)
    reopened.initialize()
    monkeypatch.setenv("TEACHER_DASHBOARD_TOKEN", TEST_TOKEN)
    client = endpoint_client(reopened)
    response = client.get(
        "/api/teacher/live",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["summary"]["total_attempts"] == 3
    assert payload["summary"]["confirmed_answers"] == 5
    assert "HIDDEN_QUESTION" not in serialized
    assert "HIDDEN_SELECTED" not in serialized
    assert "HIDDEN_CORRECT" not in serialized
    assert "backend_student_key" not in serialized
    assert TEST_TOKEN not in serialized


def test_demo_endpoint_remains_independent_of_empty_live_data(store: AnalyticsStore, monkeypatch):
    monkeypatch.setenv("TEACHER_DASHBOARD_TOKEN", TEST_TOKEN)
    client = endpoint_client(store)
    live = client.get(
        "/api/teacher/live",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    demo = client.get("/api/demo/teacher")
    assert live.status_code == demo.status_code == 200
    assert live.json()["data_source"] == "live"
    assert live.json()["data_status"] == "empty"
    assert demo.json()["label"] == "DEMO CLASS DATA · NOT LIVE"
    assert demo.json()["summary"]["students"] == 10
