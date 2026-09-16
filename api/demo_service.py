from __future__ import annotations

from frontend.analytics import class_analytics
from frontend.dummy_data import DEMO_CLASS_SESSIONS

from api.models import TeacherDemoResponse


def teacher_demo() -> TeacherDemoResponse:
    analytics = class_analytics(DEMO_CLASS_SESSIONS)
    summary_keys = (
        "students",
        "completed_assessments",
        "completion_rate",
        "average_accuracy",
        "average_correct",
        "average_total",
        "distinct_misconceptions",
        "average_difficulty",
        "response_count",
        "incorrect_response_count",
    )
    return TeacherDemoResponse(
        label="DEMO CLASS DATA · NOT LIVE",
        summary={key: analytics[key] for key in summary_keys},
        score_distribution=analytics["score_distribution"],
        misconceptions=analytics["misconceptions"],
        topics=analytics["topics"],
        difficulty=analytics["difficulty"],
        students=analytics["students_table"],
        insights=analytics["insights"],
    )
