from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
import logging
import os
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from assessment_service import AssessmentService, ServiceError
from demo_service import teacher_demo
from models import (
    AnswerResponse,
    AttemptResponse,
    ErrorDetail,
    ErrorEnvelope,
    HealthResponse,
    NextQuestionResponse,
    ResultsResponse,
    StartAttemptRequest,
    SubmitAnswerRequest,
    TeacherDemoResponse,
    TeacherLiveResponse,
)
from teacher_service import TeacherService


LOGGER = logging.getLogger("exam_not_found.api")


def _origins() -> list[str]:
    configured = os.getenv("WEB_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _require_teacher_authorization(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    configured_token = os.getenv("TEACHER_DASHBOARD_TOKEN")
    if not configured_token:
        raise ServiceError(
            503,
            "TEACHER_AUTH_NOT_CONFIGURED",
            "Live teacher analytics is not configured.",
        )

    parts = authorization.split() if authorization else []
    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not parts[1]
        or not hmac.compare_digest(parts[1], configured_token)
    ):
        raise ServiceError(
            401,
            "TEACHER_AUTH_REQUIRED",
            "Teacher authorization is required.",
        )


def create_app(
    service: AssessmentService | None = None,
    *,
    teacher_service: TeacherService | None = None,
) -> FastAPI:
    assessment_service = service or AssessmentService()
    live_teacher_service = teacher_service or TeacherService(
        assessment_service.analytics_store
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # AnalyticsStore retains only path/configuration; initialization opens
        # and closes its own SQLite connection.
        assessment_service.initialize_analytics()
        yield

    application = FastAPI(
        title="404 Exam Not Found API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.assessment_service = assessment_service
    application.state.teacher_service = live_teacher_service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        payload = ErrorEnvelope(
            error=ErrorDetail(code=exc.code, message=exc.message, retryable=exc.retryable)
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        del exc
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Check the submitted assessment details and try again.",
                retryable=False,
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        LOGGER.error("Unhandled API error: %s.%s", type(exc).__module__, type(exc).__name__)
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="Something went wrong. Please try again.",
                retryable=True,
            )
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    def current_service(request: Request) -> AssessmentService:
        return request.app.state.assessment_service

    @application.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        return current_service(request).runtime_inspector.health()

    @application.post("/api/attempts", response_model=AttemptResponse, status_code=201)
    def start_attempt(payload: StartAttemptRequest, request: Request) -> AttemptResponse:
        return current_service(request).create_attempt(payload)

    @application.get("/api/attempts/{attempt_id}", response_model=AttemptResponse)
    def get_attempt(attempt_id: UUID, request: Request) -> AttemptResponse:
        return current_service(request).get_attempt(attempt_id)

    @application.post("/api/attempts/{attempt_id}/next", response_model=NextQuestionResponse)
    def next_question(attempt_id: UUID, request: Request) -> NextQuestionResponse:
        return current_service(request).next_question(attempt_id)

    @application.post("/api/attempts/{attempt_id}/answers", response_model=AnswerResponse)
    def submit_answer(
        attempt_id: UUID,
        payload: SubmitAnswerRequest,
        request: Request,
    ) -> AnswerResponse:
        return current_service(request).submit_answer(attempt_id, payload)

    @application.get("/api/attempts/{attempt_id}/results", response_model=ResultsResponse)
    def results(attempt_id: UUID, request: Request) -> ResultsResponse:
        return current_service(request).results(attempt_id)

    @application.get("/api/demo/teacher", response_model=TeacherDemoResponse)
    def demo_teacher() -> TeacherDemoResponse:
        return teacher_demo()

    @application.get(
        "/api/teacher/live",
        response_model=TeacherLiveResponse,
        dependencies=[Depends(_require_teacher_authorization)],
    )
    def live_teacher(request: Request) -> TeacherLiveResponse:
        try:
            return request.app.state.teacher_service.live_analytics()
        except Exception as exc:
            LOGGER.error(
                "Live teacher analytics failed: %s.%s",
                type(exc).__module__,
                type(exc).__name__,
            )
            raise ServiceError(
                503,
                "TEACHER_ANALYTICS_UNAVAILABLE",
                "Live teacher analytics is temporarily unavailable.",
                retryable=True,
            ) from None

    return application


app = create_app()
