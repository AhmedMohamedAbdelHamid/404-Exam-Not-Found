from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


LanguageCode = Literal["en", "ar"]
QuestionSource = Literal["live", "fallback"]
AnswerState = Literal["open", "saving", "saved", "definitely_failed", "ambiguous"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class RuntimeStatus(BaseModel):
    pipeline: Literal["configured", "degraded"]
    chroma_configured: bool
    collection_available: bool
    gemini_configured: bool
    fallback_available: bool
    message: str


class HealthResponse(BaseModel):
    api_available: bool = True
    chroma_configured: bool
    english_collection_available: bool
    arabic_collection_available: bool
    gemini_configured: bool
    fallback_available: bool
    status: Literal["configured", "degraded", "fallback_available"]


class StartAttemptRequest(StrictModel):
    student_id: str = Field(min_length=1, max_length=80)
    language: LanguageCode

    @field_validator("student_id")
    @classmethod
    def normalize_student_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Student identifier is required.")
        return normalized


class Progress(BaseModel):
    answered: int
    total: int
    percent: float


class QuestionOptionDTO(BaseModel):
    id: str
    label: str
    text: str


class QuestionDTO(BaseModel):
    question_id: str
    question_number: int
    question: str
    topic: str
    language: LanguageCode
    source: QuestionSource
    options: list[QuestionOptionDTO]


class AttemptResponse(BaseModel):
    attempt_id: UUID
    student_id: str
    language: LanguageCode
    current_adaptive_difficulty: int = Field(ge=1, le=5)
    progress: Progress
    runtime: RuntimeStatus
    current_question: QuestionDTO | None = None
    current_answer: "AnswerResponse | None" = None
    answer_state: AnswerState | None = None
    can_request_next: bool
    complete: bool
    created_at: datetime


class NextQuestionResponse(BaseModel):
    status: Literal["question", "complete"]
    question: QuestionDTO | None = None
    current_adaptive_difficulty: int = Field(ge=1, le=5)
    progress: Progress
    complete: bool


class SubmitAnswerRequest(StrictModel):
    question_id: str = Field(min_length=1, max_length=40)
    selected_option_id: str = Field(min_length=1, max_length=80)


class AnswerResponse(BaseModel):
    question_id: str
    selected_option_id: str
    correct_option_id: str
    selected_answer: str
    correct_answer: str
    correct: bool
    misconception: str | None = None
    current_adaptive_difficulty: int = Field(ge=1, le=5)
    progress: Progress
    can_continue: bool
    answer_state: Literal["saved"] = "saved"


class ScoreSummary(BaseModel):
    score: int
    attempted: int
    accuracy: float
    correct: int
    incorrect: int
    final_adaptive_difficulty: int = Field(ge=1, le=5)
    average_question_difficulty: float


class TopicResult(BaseModel):
    topic: str
    attempted: int
    correct: int
    incorrect: int
    accuracy: float


class MisconceptionResult(BaseModel):
    misconception: str
    occurrences: int
    topics: list[str]


class ReviewResult(BaseModel):
    question_id: str
    question_number: int
    question: str
    topic: str
    language: LanguageCode
    difficulty: int
    selected_answer: str
    correct_answer: str
    correct: bool
    misconception: str | None = None


class JourneyPoint(BaseModel):
    step: int
    difficulty: int = Field(ge=1, le=5)


class ResultsResponse(BaseModel):
    attempt_id: UUID
    student_id: str
    language: LanguageCode
    complete: bool
    summary: ScoreSummary
    topics: list[TopicResult]
    strongest_topic: str | None
    needs_attention_topic: str | None
    misconceptions: list[MisconceptionResult]
    question_review: list[ReviewResult]
    adaptive_journey: list[JourneyPoint]


class TeacherDemoResponse(BaseModel):
    label: Literal["DEMO CLASS DATA · NOT LIVE"]
    summary: dict[str, Any]
    score_distribution: list[dict[str, Any]]
    misconceptions: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    difficulty: list[dict[str, Any]]
    students: list[dict[str, Any]]
    insights: list[str]


AttemptResponse.model_rebuild()
