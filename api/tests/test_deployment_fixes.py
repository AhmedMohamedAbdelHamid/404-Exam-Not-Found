"""Regression tests for the two production bugs:

1. "This assessment attempt was not found" partway through a quiz
   (state was stored per serverless instance instead of in shared storage).
2. Every quiz showing the same 5 "verified fallback" questions.

Self-contained: does not need Postgres, Gemini, or network access.

    PYTHONPATH=api python -m pytest api/tests/test_deployment_fixes.py -q
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

# api/ must win over the repo root, which still holds stale copies of several
# modules (backup_pool.py, staircase.py, llm_client.py, ...) from the old app.
API_DIR = Path(__file__).resolve().parents[1]
sys.path[:] = [str(API_DIR)] + [p for p in sys.path if Path(p or ".").resolve() != API_DIR]

from fastapi.testclient import TestClient  # noqa: E402

import backup_pool  # noqa: E402
import db  # noqa: E402
import diagnostics  # noqa: E402
import generation_agent  # noqa: E402
import llm_client  # noqa: E402
import main  # noqa: E402
from assessment_service import AssessmentService  # noqa: E402

TOPICS = ["algorithm", "variables and assignment", "loops and conditionals", "lists", "functions"]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Each test gets its own SQLite file and a clean environment."""
    for name in ("DATABASE_URL", "VERCEL", "VERCEL_ENV", "ALLOW_EPHEMERAL_STORAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EXAM_SQLITE_PATH", str(tmp_path / "shared.sqlite3"))
    monkeypatch.setattr(db, "_sqlite_ready_for", None)
    monkeypatch.setattr(llm_client, "USE_REAL_LLM", False)


# --------------------------------------------------------------------------
# Bug 1: storage
# --------------------------------------------------------------------------

def test_supabase_project_url_is_rejected_with_actionable_message(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "https://abcdefgh.supabase.co")
    assert db.uses_postgres() is False
    problem = db.database_url_problem()
    assert "postgresql://" in problem and "Connection string" in problem


def test_quotes_around_database_url_are_tolerated(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", '"postgresql://u:p@h:5432/db"')
    assert db.uses_postgres() is True


def test_vercel_refuses_per_instance_sqlite(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "https://abcdefgh.supabase.co")
    with pytest.raises(db.StorageNotConfiguredError):
        with db.connection():
            pass


def test_vercel_override_allows_sqlite(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 AS one")
        assert cur.fetchone()["one"] == 1


def test_api_reports_misconfiguration_clearly_instead_of_losing_attempts(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "https://abcdefgh.supabase.co")
    client = TestClient(main.create_app())
    response = client.post("/api/attempts", json={"student_id": "s1", "language": "en"})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "STORAGE_NOT_CONFIGURED"
    assert "DATABASE_URL" in error["message"]


def _play(client, attempt_id, *, pick=0):
    """Answer every question; returns the list of served questions."""
    served = []
    while True:
        response = client.post(f"/api/attempts/{attempt_id}/next")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] == "complete":
            return served
        question = body["question"]
        served.append(question)
        answered = client.post(
            f"/api/attempts/{attempt_id}/answers",
            json={"question_id": question["question_id"], "selected_option_id": question["options"][pick]["id"]},
        )
        assert answered.status_code == 200, answered.text


def test_attempt_survives_being_served_by_different_instances():
    """Each TestClient/app below has its own AssessmentService and therefore its
    own process memory -- exactly like separate Vercel function instances. Only
    the shared database connects them. Before the fix, request 5 was a 404."""
    instances = [TestClient(main.create_app()) for _ in range(3)]
    created = instances[0].post("/api/attempts", json={"student_id": "s1", "language": "en"})
    assert created.status_code == 201
    attempt_id = created.json()["attempt_id"]

    served = 0
    step = 0
    while True:
        client = instances[step % len(instances)]  # a different "instance" every request
        step += 1
        body = client.post(f"/api/attempts/{attempt_id}/next").json()
        if body.get("status") == "complete":
            break
        assert "error" not in body, body
        question = body["question"]
        served += 1
        client = instances[step % len(instances)]
        step += 1
        answer = client.post(
            f"/api/attempts/{attempt_id}/answers",
            json={"question_id": question["question_id"], "selected_option_id": question["options"][0]["id"]},
        )
        assert answer.status_code == 200, answer.text

    assert served == 5
    results = instances[1].get(f"/api/attempts/{attempt_id}/results")
    assert results.status_code == 200
    assert results.json()["summary"]["attempted"] == 5


# --------------------------------------------------------------------------
# Bug 2: identical quizzes
# --------------------------------------------------------------------------

def test_pool_is_larger_and_covers_every_topic_in_both_languages():
    for language in ("en", "ar"):
        for topic in TOPICS:
            assert len(backup_pool._POOL[(topic, language)]) >= 5


def test_fallback_selection_varies_at_a_fixed_difficulty():
    for language in ("en", "ar"):
        for topic in TOPICS:
            for difficulty in (1, 3, 5):
                seen = {
                    backup_pool.get_backup_question(topic, language, difficulty).question
                    for _ in range(200)
                }
                assert len(seen) >= 2, (topic, language, difficulty)


def test_fallback_selection_still_respects_difficulty():
    easy = {backup_pool.get_backup_question("lists", "en", 1).difficulty_score for _ in range(200)}
    hard = {backup_pool.get_backup_question("lists", "en", 5).difficulty_score for _ in range(200)}
    assert max(easy) <= 3 and min(hard) >= 3
    assert sum(easy) / len(easy) < sum(hard) / len(hard)


def test_pool_is_deterministic_when_rng_is_injected():
    import random

    first = backup_pool.get_backup_question("lists", "en", 3, rng=random.Random(7)).question
    second = backup_pool.get_backup_question("lists", "en", 3, rng=random.Random(7)).question
    assert first == second


@pytest.mark.parametrize(
    "key,question",
    [(key, q) for key, qs in backup_pool._POOL.items() for q in qs],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_marked_correct_answer_is_what_python_actually_prints(key, question):
    """Executes every 'what does this code print?' question in the pool."""
    stems = ("What does the following code print?\n", "ماذا تطبع الشيفرة التالية؟\n")
    stem = next((s for s in stems if question.question.startswith(s)), None)
    if stem is None:
        pytest.skip("conceptual question, not code output")
    snippet = question.question[len(stem):]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(snippet, "<pool question>", "exec"), {})
    printed = buffer.getvalue().rstrip("\n")
    correct = [o.text for o in question.options if o.correct]
    assert correct == [printed], f"{key}: python printed {printed!r}, marked correct {correct!r}"


def _stub_generation(messages, chunk, difficulty):
    return generation_agent._generic_stub_llm_response(chunk, difficulty)


def _stub_critique(messages):
    return json.dumps({"exactly_one_correct": True, "supported_by_chunk": True, "reasoning": "ok"})


def test_live_generation_is_used_when_gemini_is_configured(monkeypatch):
    monkeypatch.setattr(llm_client, "USE_REAL_LLM", True)
    client = TestClient(
        main.create_app(AssessmentService(generation_fn=_stub_generation, critique_fn=_stub_critique))
    )
    attempt_id = client.post("/api/attempts", json={"student_id": "s1", "language": "en"}).json()["attempt_id"]
    served = _play(client, attempt_id)
    assert [q["source"] for q in served] == ["live"] * 5


def test_failed_live_generation_falls_back_and_logs_the_reason(monkeypatch, caplog):
    monkeypatch.setattr(llm_client, "USE_REAL_LLM", True)

    def failing_generation(messages, chunk, difficulty):
        raise llm_client.LLMCallError("Gemini API call failed: 403 API key not valid")

    client = TestClient(
        main.create_app(AssessmentService(generation_fn=failing_generation, critique_fn=_stub_critique))
    )
    attempt_id = client.post("/api/attempts", json={"student_id": "s1", "language": "en"}).json()["attempt_id"]
    with caplog.at_level("WARNING", logger="exam_not_found.api.analytics"):
        served = _play(client, attempt_id)
    assert [q["source"] for q in served] == ["fallback"] * 5
    assert any("API key not valid" in record.getMessage() for record in caplog.records)


def test_two_fallback_quizzes_are_not_all_identical():
    client = TestClient(main.create_app())
    quizzes = set()
    for index in range(15):
        attempt_id = client.post(
            "/api/attempts", json={"student_id": f"student-{index}", "language": "en"}
        ).json()["attempt_id"]
        quizzes.add(tuple(q["question"] for q in _play(client, attempt_id)))
    assert len(quizzes) > 1


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

def test_diagnostics_flags_non_durable_storage_and_missing_key():
    report = diagnostics.collect()
    text = " ".join(report["verdict"])
    assert "NOT durable" in text and "GEMINI_API_KEY" in text
    assert "GEMINI_API_KEY" not in json.dumps(report["gemini"]).replace("key_configured", "")  # no secret values


def test_pipeline_probe_passes_with_working_stubs(monkeypatch):
    monkeypatch.setattr(llm_client, "USE_REAL_LLM", True)
    monkeypatch.setattr(generation_agent, "call_llm", _stub_generation)
    monkeypatch.setattr(llm_client, "critique_question_json", _stub_critique)
    result = diagnostics.run_pipeline_probe()
    assert result["ok"] is True
    assert [s["stage"] for s in result["stages"]][-1] == "validation_stage2"


def test_pipeline_probe_reports_provider_http_status(monkeypatch):
    monkeypatch.setattr(llm_client, "USE_REAL_LLM", True)

    class Forbidden(Exception):
        code = 403

    def broken(messages, chunk, difficulty):
        raise llm_client.LLMCallError("Gemini API call failed") from Forbidden("blocked")

    monkeypatch.setattr(generation_agent, "call_llm", broken)
    result = diagnostics.run_pipeline_probe()
    assert result["ok"] is False
    failed = result["stages"][-1]
    assert failed["stage"] == "gemini_generate" and failed["detail"]["http_status"] == 403
