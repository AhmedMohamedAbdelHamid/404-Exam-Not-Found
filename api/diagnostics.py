"""Deployment diagnostics for GET /api/diagnostics.

Two attempts to find out "why does my deployed quiz behave like this?" used to
mean reading Vercel logs. This module answers directly from the running
deployment, and never returns secrets (only whether a key is set, plus error
class/message text from the provider).

    /api/diagnostics            storage + configuration (cheap, no LLM call)
    /api/diagnostics?probe=1    additionally dry-runs the real question pipeline
                                once (2 Gemini calls) and reports each stage
"""

from __future__ import annotations

import threading
import time
from typing import Any

import db
import llm_client

_PROBE_MIN_INTERVAL_SECONDS = 30.0
_probe_lock = threading.Lock()
_last_probe_at = 0.0


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def run_pipeline_probe(language: str = "en", topic: str = "lists") -> dict[str, Any]:
    """One real generation -> Stage 1 -> Stage 2 pass, reporting where it stops."""
    from generation_agent import call_llm
    from prompt_template import build_messages_from_chunk
    from retrieval import get_chunks
    from validation_stage1 import run_stage1
    from validation_stage2 import critique_question

    result: dict[str, Any] = {"model": llm_client.GEMINI_MODEL, "stages": []}

    def stage(name: str, ok: bool, detail: Any = None) -> None:
        result["stages"].append({"stage": name, "ok": ok, "detail": detail})

    if not llm_client.USE_REAL_LLM:
        stage("gemini_key", False, "GEMINI_API_KEY is not set in this deployment's environment variables.")
        result["ok"] = False
        return result
    stage("gemini_key", True)

    try:
        chunks = get_chunks(topic, language, n=1)
    except Exception as exc:  # noqa: BLE001
        stage("retrieve_chunk", False, _short(exc))
        result["ok"] = False
        return result
    if not chunks:
        stage("retrieve_chunk", False, f"No chunks for topic={topic!r} language={language!r}. The chunks table is empty.")
        result["ok"] = False
        return result
    chunk = chunks[0]
    stage("retrieve_chunk", True, chunk["chunk_id"])

    started = time.monotonic()
    try:
        raw = call_llm(build_messages_from_chunk(chunk, 3), chunk, 3)
    except Exception as exc:  # noqa: BLE001
        cause = exc.__cause__
        stage(
            "gemini_generate",
            False,
            {"error": _short(exc), "http_status": getattr(cause, "code", None)},
        )
        result["ok"] = False
        return result
    stage("gemini_generate", True, f"{time.monotonic() - started:.1f}s")

    try:
        passed, question, reasons = run_stage1(raw, chunk["text"])
    except Exception as exc:  # noqa: BLE001
        stage("validation_stage1", False, _short(exc))
        result["ok"] = False
        return result
    stage("validation_stage1", bool(passed), None if passed else reasons)
    if not passed:
        result["ok"] = False
        return result

    try:
        passed, reasoning = critique_question(question, chunk["text"], llm_client.critique_question_json)
    except Exception as exc:  # noqa: BLE001
        stage("validation_stage2", False, _short(exc))
        result["ok"] = False
        return result
    stage("validation_stage2", bool(passed), reasoning)
    result["ok"] = bool(passed)
    return result


def collect(probe: bool = False) -> dict[str, Any]:
    global _last_probe_at
    report: dict[str, Any] = {
        "storage": db.storage_status(),
        "gemini": {
            "key_configured": bool(llm_client.USE_REAL_LLM),
            "model": llm_client.GEMINI_MODEL,
        },
    }

    storage = report["storage"]
    verdict: list[str] = []
    if not storage["durable"]:
        verdict.append(
            "Storage is NOT durable: " + (storage["config_problem"] or "DATABASE_URL is not a Postgres URL.")
        )
    elif not storage["reachable"]:
        verdict.append("DATABASE_URL looks valid but the database is unreachable: " + str(storage["error"]))
    elif not storage["chunks"]:
        verdict.append("The chunks table is empty, so live question generation is disabled.")
    if not report["gemini"]["key_configured"]:
        verdict.append("GEMINI_API_KEY is not set, so every question comes from the small fallback pool.")

    if probe:
        with _probe_lock:
            wait = _PROBE_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_probe_at)
            if _last_probe_at and wait > 0:
                report["pipeline_probe"] = {"ok": None, "skipped": f"Rate limited; retry in {wait:.0f}s."}
            else:
                _last_probe_at = time.monotonic()
                report["pipeline_probe"] = run_pipeline_probe()
        probe_result = report["pipeline_probe"]
        if probe_result.get("ok") is False:
            failed = next((s for s in probe_result.get("stages", []) if not s["ok"]), None)
            if failed:
                verdict.append(f"Live pipeline fails at '{failed['stage']}': {failed['detail']}")

    report["verdict"] = verdict or ["OK: durable storage, chunks loaded, Gemini key set."]
    return report
