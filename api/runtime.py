from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
import time
from typing import Callable

from backup_pool import get_backup_question
import llm_client
from staircase import TOPIC_ORDER

from models import HealthResponse, LanguageCode, RuntimeStatus
from db import connection


PROJECT_ROOT = Path(__file__).resolve().parent
EXPECTED_LANGUAGES = {"en", "ar"}
TRANSIENT_PROVIDER_CODES = {429, 500, 502, 503, 504}
DEFAULT_LIVE_COOLDOWN_SECONDS = 120.0


def _chunk_languages() -> set[str]:
    """Which languages currently have rows in Supabase's chunks table --
    the Postgres-backed replacement for the original's local Chroma
    collection check (see retrieval.py). Field names below (chroma_configured
    etc.) are kept as-is for API/frontend compatibility even though the
    backing store changed.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT DISTINCT language FROM chunks")
            return {row["language"] for row in cur.fetchall()}
    except Exception:
        return set()


class RuntimeInspector:
    def __init__(
        self,
        project_root: Path | None = None,
        *,
        cooldown_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self._clock = clock
        self._cooldown_seconds = (
            self._configured_cooldown_seconds()
            if cooldown_seconds is None
            else max(0.0, cooldown_seconds)
        )
        self._live_degraded_until = 0.0
        self._cooldown_lock = RLock()

    @staticmethod
    def _configured_cooldown_seconds() -> float:
        raw = os.getenv("LIVE_GENERATION_COOLDOWN_SECONDS", str(DEFAULT_LIVE_COOLDOWN_SECONDS))
        try:
            return max(0.0, float(raw))
        except ValueError:
            return DEFAULT_LIVE_COOLDOWN_SECONDS

    def live_generation_on_cooldown(self) -> bool:
        with self._cooldown_lock:
            return self._clock() < self._live_degraded_until

    def note_llm_failure(self, error: Exception) -> bool:
        """Start a temporary cooldown only for structured transient provider errors."""
        cause = error.__cause__
        status_code = getattr(cause, "code", None) if cause is not None else None
        if status_code not in TRANSIENT_PROVIDER_CODES or self._cooldown_seconds <= 0:
            return False
        with self._cooldown_lock:
            self._live_degraded_until = max(
                self._live_degraded_until,
                self._clock() + self._cooldown_seconds,
            )
        return True

    def collection_status(self) -> tuple[bool, bool, bool]:
        try:
            names = _chunk_languages()
        except Exception:
            names = set()
        database_configured = True  # Postgres, or the bundled SQLite fallback
        return (
            database_configured and bool(names),
            "en" in names,
            "ar" in names,
        )

    @staticmethod
    def fallback_available(language: LanguageCode | None = None) -> bool:
        languages = (language,) if language else ("en", "ar")
        return all(
            get_backup_question(topic, candidate, difficulty=3) is not None
            for candidate in languages
            for topic in TOPIC_ORDER
        )

    def for_language(self, language: LanguageCode) -> RuntimeStatus:
        chroma_configured, english, arabic = self.collection_status()
        collection_available = english if language == "en" else arabic
        gemini_configured = bool(llm_client.USE_REAL_LLM)
        fallback_available = self.fallback_available(language)
        dependencies_configured = chroma_configured and collection_available and gemini_configured
        live_configured = dependencies_configured and not self.live_generation_on_cooldown()
        return RuntimeStatus(
            pipeline="configured" if live_configured else "degraded",
            chroma_configured=chroma_configured,
            collection_available=collection_available,
            gemini_configured=gemini_configured,
            fallback_available=fallback_available,
            message=(
                "AI pipeline configured with verified fallback."
                if live_configured
                else "Verified fallback is active while live generation recovers."
                if dependencies_configured and fallback_available
                else "Verified fallback is available while live generation is unavailable."
                if fallback_available
                else "Assessment generation is not currently configured."
            ),
        )

    def health(self) -> HealthResponse:
        chroma_configured, english, arabic = self.collection_status()
        fallback_available = self.fallback_available()
        gemini_configured = bool(llm_client.USE_REAL_LLM)
        fully_configured = chroma_configured and english and arabic and gemini_configured
        on_cooldown = self.live_generation_on_cooldown()
        status = (
            "configured"
            if fully_configured and not on_cooldown
            else "degraded"
            if fully_configured and on_cooldown
            else "fallback_available"
            if fallback_available
            else "degraded"
        )
        return HealthResponse(
            chroma_configured=chroma_configured,
            english_collection_available=english,
            arabic_collection_available=arabic,
            gemini_configured=gemini_configured,
            fallback_available=fallback_available,
            status=status,
        )
