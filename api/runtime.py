from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sqlite3
from threading import RLock
import time
from typing import Callable

from backup_pool import get_backup_question
import llm_client
from staircase import TOPIC_ORDER

from api.models import HealthResponse, LanguageCode, RuntimeStatus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLLECTIONS = {"en": "chunks_en", "ar": "chunks_ar"}
TRANSIENT_PROVIDER_CODES = {429, 500, 502, 503, 504}
DEFAULT_LIVE_COOLDOWN_SECONDS = 120.0


def _collection_names(root: Path) -> set[str]:
    database = root / "chroma_db" / "chroma.sqlite3"
    if not database.is_file():
        return set()
    connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    try:
        return {str(row[0]) for row in connection.execute("SELECT name FROM collections")}
    finally:
        connection.close()


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
        chroma_dir = self.project_root / "chroma_db"
        chroma_configured = chroma_dir.is_dir() and (chroma_dir / "chroma.sqlite3").is_file()
        try:
            names = _collection_names(self.project_root) if chroma_configured else set()
        except (sqlite3.Error, OSError):
            names = set()
        package_available = importlib.util.find_spec("chromadb") is not None
        return (
            chroma_configured and package_available,
            EXPECTED_COLLECTIONS["en"] in names,
            EXPECTED_COLLECTIONS["ar"] in names,
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
