from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from api.analytics_store import (
    ANALYTICS_DB_PATH_ENV,
    AnalyticsConflictError,
    AnalyticsNotFoundError,
    AnalyticsStore,
)


CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
CONFIRMED = CREATED + timedelta(minutes=1)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    return tmp_path / "analytics.db"


@pytest.fixture
def store(database: Path) -> AnalyticsStore:
    result = AnalyticsStore(database)
    result.initialize()
    return result


def create_attempt(
    store: AnalyticsStore,
    attempt_id: str = "attempt-1",
    *,
    student_id: str = "student-1",
    language: str = "en",
    created_at: datetime = CREATED,
):
    return store.create_attempt(
        attempt_id=attempt_id,
        student_id=student_id,
        language=language,
        initial_difficulty=3,
        created_at=created_at,
    )


def answer_payload(
    attempt_id: str = "attempt-1",
    question_id: str = "q001",
    *,
    question_number: int = 1,
    language: str = "en",
    selected_option_index: int = 2,
    correct: bool = False,
    misconception: str | None = "Confuses assignment with equality.",
):
    return {
        "attempt_id": attempt_id,
        "question_id": question_id,
        "question_number": question_number,
        "language": language,
        "topic": "variables and assignment",
        "question_text": "What value is printed?",
        "selected_option_index": selected_option_index,
        "selected_answer_text": "5",
        "correct_answer_text": "8",
        "correct": correct,
        "misconception": misconception,
        "difficulty_score": 3,
        "requested_difficulty": 3,
        "adaptive_level_before": 3,
        "adaptive_level_after": 2 if not correct else 4,
        "source_reference": "en_chunk_001",
        "created_at": CREATED,
    }


def test_schema_initializes_with_required_tables_and_pragmas(database: Path):
    store = AnalyticsStore(database, busy_timeout_ms=2_500)
    store.initialize()
    connection = sqlite3.connect(database)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"attempts", "answers"} <= tables
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()


def test_repeated_initialization_is_safe(database: Path):
    first = AnalyticsStore(database)
    first.initialize()
    second = AnalyticsStore(database)
    second.initialize()
    assert second.list_attempts() == []


def test_environment_path_override_is_honored(tmp_path: Path, monkeypatch):
    configured = tmp_path / "configured" / "analytics.db"
    monkeypatch.setenv(ANALYTICS_DB_PATH_ENV, str(configured))
    store = AnalyticsStore()
    store.initialize()
    assert store.db_path == configured
    assert configured.is_file()


def test_attempt_creation_persists_and_uses_utc(store: AnalyticsStore):
    record = create_attempt(store)
    assert store.get_attempt("attempt-1") == record
    assert record.created_at == "2026-01-02T03:04:05.000000Z"
    assert record.status == "in_progress"


def test_identical_duplicate_attempt_is_idempotent(store: AnalyticsStore):
    first = create_attempt(store)
    second = create_attempt(store)
    assert second == first
    assert len(store.list_attempts()) == 1


def test_duplicate_attempt_without_repeating_timestamp_is_idempotent(store: AnalyticsStore):
    first = create_attempt(store)
    second = store.create_attempt(
        attempt_id="attempt-1",
        student_id="student-1",
        language="en",
        initial_difficulty=3,
    )
    assert second == first


@pytest.mark.parametrize("change", ["student", "language", "difficulty", "created_at"])
def test_conflicting_attempt_identity_is_rejected(store: AnalyticsStore, change: str):
    create_attempt(store)
    values = {
        "attempt_id": "attempt-1",
        "student_id": "other" if change == "student" else "student-1",
        "language": "ar" if change == "language" else "en",
        "initial_difficulty": 4 if change == "difficulty" else 3,
        "created_at": CREATED + timedelta(seconds=1) if change == "created_at" else CREATED,
    }
    with pytest.raises(AnalyticsConflictError):
        store.create_attempt(**values)


@pytest.mark.parametrize("language", ["en", "ar"])
def test_supported_languages_persist(store: AnalyticsStore, language: str):
    record = create_attempt(store, f"attempt-{language}", language=language)
    assert record.language == language


def test_repeated_visible_student_id_is_allowed_across_attempts(store: AnalyticsStore):
    create_attempt(store, "attempt-a", student_id="same-student")
    create_attempt(
        store,
        "attempt-b",
        student_id="same-student",
        created_at=CREATED + timedelta(seconds=1),
    )
    assert [row.student_id for row in store.list_attempts()] == ["same-student", "same-student"]


def test_pending_answer_persists_and_round_trips_boolean(store: AnalyticsStore):
    create_attempt(store)
    pending = store.prepare_answer(**answer_payload())
    assert pending.status == "pending"
    assert pending.correct is False
    assert store.get_answer("attempt-1", "q001") == pending


def test_pending_to_confirmed_transition_and_duplicate_confirm(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    first = store.confirm_answer("attempt-1", "q001", confirmed_at=CONFIRMED)
    second = store.confirm_answer("attempt-1", "q001", confirmed_at=CONFIRMED)
    assert first == second
    assert first.status == "confirmed"
    assert first.confirmed_at == "2026-01-02T03:05:05.000000Z"
    assert len(store.list_confirmed_answers()) == 1


def test_authoritative_after_level_can_be_supplied_only_at_confirmation(store: AnalyticsStore):
    create_attempt(store)
    payload = answer_payload()
    payload["adaptive_level_after"] = None
    pending = store.prepare_answer(**payload)
    assert pending.adaptive_level_after is None
    confirmed = store.confirm_answer(
        "attempt-1",
        "q001",
        adaptive_level_after=2,
        confirmed_at=CONFIRMED,
    )
    assert confirmed.adaptive_level_after == 2


def test_confirmed_answer_survives_store_recreation(database: Path):
    first = AnalyticsStore(database)
    first.initialize()
    create_attempt(first)
    first.prepare_answer(**answer_payload())
    expected = first.confirm_answer("attempt-1", "q001", confirmed_at=CONFIRMED)
    reopened = AnalyticsStore(database)
    reopened.initialize()
    assert reopened.get_answer("attempt-1", "q001") == expected


def test_identical_duplicate_prepare_is_idempotent(store: AnalyticsStore):
    create_attempt(store)
    first = store.prepare_answer(**answer_payload())
    second = store.prepare_answer(**answer_payload())
    assert second == first


def test_different_option_or_payload_is_rejected(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    changed_option = answer_payload(selected_option_index=1)
    changed_option["selected_answer_text"] = "8"
    with pytest.raises(AnalyticsConflictError):
        store.prepare_answer(**changed_option)


def test_confirmed_answer_cannot_be_overwritten_or_failed(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    confirmed = store.confirm_answer("attempt-1", "q001")
    assert store.prepare_answer(**answer_payload()) == confirmed
    with pytest.raises(AnalyticsConflictError):
        store.mark_answer_failed("attempt-1", "q001")


def test_failed_answer_can_be_prepared_again_but_is_not_analytic(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    failed = store.mark_answer_failed("attempt-1", "q001")
    assert failed.status == "failed"
    assert store.list_confirmed_answers() == []
    retried = store.prepare_answer(**answer_payload())
    assert retried.status == "pending"
    assert retried.created_at == failed.created_at


def test_pending_answer_is_excluded_from_confirmed_reads(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    assert store.list_confirmed_answers() == []


def test_consistent_snapshot_contains_only_confirmed_answers(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload(question_id="confirmed"))
    store.confirm_answer("attempt-1", "confirmed")
    store.prepare_answer(**answer_payload(question_id="pending", question_number=2))
    store.prepare_answer(**answer_payload(question_id="failed", question_number=3))
    store.mark_answer_failed("attempt-1", "failed")
    snapshot = store.read_snapshot()
    assert [row.attempt_id for row in snapshot.attempts] == ["attempt-1"]
    assert [row.question_id for row in snapshot.confirmed_answers] == ["confirmed"]


@pytest.mark.parametrize(
    ("correct", "misconception", "expected_after"),
    [(False, "Off-by-one error", 2), (True, None, 4)],
)
def test_answer_learning_and_adaptive_fields_persist(
    store: AnalyticsStore,
    correct: bool,
    misconception: str | None,
    expected_after: int,
):
    create_attempt(store)
    record = store.prepare_answer(
        **answer_payload(correct=correct, misconception=misconception)
    )
    assert record.misconception == misconception
    assert record.adaptive_level_before == 3
    assert record.adaptive_level_after == expected_after
    assert record.source_reference == "en_chunk_001"


def test_question_uniqueness_is_scoped_to_attempt(store: AnalyticsStore):
    create_attempt(store, "attempt-1")
    create_attempt(store, "attempt-2", created_at=CREATED + timedelta(seconds=1))
    first = store.prepare_answer(**answer_payload("attempt-1", "q001"))
    second = store.prepare_answer(**answer_payload("attempt-2", "q001"))
    assert first.question_id == second.question_id
    assert first.attempt_id != second.attempt_id


def test_foreign_key_is_enforced_as_domain_not_found(store: AnalyticsStore):
    with pytest.raises(AnalyticsNotFoundError):
        store.prepare_answer(**answer_payload("missing-attempt"))


def test_sqlite_foreign_keys_are_enabled_per_connection(store: AnalyticsStore):
    with store._read() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_database_rejects_orphan_answer_rows(store: AnalyticsStore):
    with pytest.raises(sqlite3.IntegrityError), store._write() as connection:
        connection.execute(
            """
            INSERT INTO answers (
                attempt_id, question_id, question_number, language, topic,
                question_text, selected_option_index, selected_answer_text,
                correct_answer_text, correct, misconception, difficulty_score,
                requested_difficulty, adaptive_level_before, adaptive_level_after,
                source_reference, status, created_at, confirmed_at
            ) VALUES (
                'missing', 'q001', 1, 'en', 'algorithm', 'Question?', 0,
                'A', 'B', 0, 'Signal', 3, 3, 3, 2, 'chunk', 'pending',
                '2026-01-02T03:04:05.000000Z', NULL
            )
            """
        )


def test_completion_state_and_final_difficulty_are_idempotent(store: AnalyticsStore):
    create_attempt(store)
    completed_at = CREATED + timedelta(minutes=10)
    first = store.mark_attempt_completed(
        "attempt-1", 4, completed_at=completed_at
    )
    second = store.mark_attempt_completed(
        "attempt-1", 4, completed_at=completed_at
    )
    assert first == second
    assert first.status == "completed"
    assert first.final_difficulty == 4
    assert first.completed_at == "2026-01-02T03:14:05.000000Z"


def test_conflicting_completion_is_rejected(store: AnalyticsStore):
    create_attempt(store)
    store.mark_attempt_completed("attempt-1", 4)
    with pytest.raises(AnalyticsConflictError):
        store.mark_attempt_completed("attempt-1", 5)


def test_empty_database_reads_cleanly(store: AnalyticsStore):
    assert store.list_attempts() == []
    assert store.list_confirmed_answers() == []
    assert store.get_attempt("missing") is None
    assert store.get_answer("missing", "q001") is None


def test_attempt_and_answer_ordering_is_deterministic(store: AnalyticsStore):
    create_attempt(store, "attempt-b", created_at=CREATED + timedelta(seconds=2))
    create_attempt(store, "attempt-a", created_at=CREATED + timedelta(seconds=1))
    for question_id, number in (("q010", 2), ("q002", 1), ("q001", 1)):
        payload = answer_payload(
            "attempt-a", question_id, question_number=number
        )
        store.prepare_answer(**payload)
        store.confirm_answer("attempt-a", question_id)
    assert [row.attempt_id for row in store.list_attempts()] == ["attempt-a", "attempt-b"]
    assert [row.question_id for row in store.list_confirmed_answers(attempt_id="attempt-a")] == [
        "q001",
        "q002",
        "q010",
    ]


def test_concurrent_duplicate_prepare_creates_one_row(store: AnalyticsStore):
    create_attempt(store)
    payload = answer_payload()
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(lambda _: store.prepare_answer(**payload), range(12)))
    assert all(record == records[0] for record in records)
    assert store.get_answer("attempt-1", "q001") is not None
    with store._read() as connection:
        count = connection.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    assert count == 1


def test_concurrent_confirm_is_idempotent(store: AnalyticsStore):
    create_attempt(store)
    store.prepare_answer(**answer_payload())
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(
            pool.map(
                lambda _: store.confirm_answer(
                    "attempt-1", "q001", confirmed_at=CONFIRMED
                ),
                range(8),
            )
        )
    assert all(record == records[0] for record in records)
    assert len(store.list_confirmed_answers()) == 1


def test_tests_use_only_temporary_database(database: Path):
    assert database.parent != Path.cwd()
    assert database.name == "analytics.db"
