from __future__ import annotations

import logging
import os
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.assessment_service import AssessmentService, ServiceError
from api.demo_service import teacher_demo
from api.models import (
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
)


LOGGER = logging.getLogger("exam_not_found.api")


def _origins() -> list[str]:
    configured = os.getenv("WEB_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def create_app(service: AssessmentService | None = None) -> FastAPI:
    application = FastAPI(
        title="404 Exam Not Found API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.state.assessment_service = service or AssessmentService()
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

    return application


app = create_app()
