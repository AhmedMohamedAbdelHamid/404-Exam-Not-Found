"""Read-only aggregation of durable, real assessment analytics."""

from __future__ import annotations

from collections import Counter, defaultdict

from api.analytics_store import AnalyticsStore, AnswerRecord, AttemptRecord
from api.models import (
    TeacherLiveAttemptRow,
    TeacherLiveDifficultyRow,
    TeacherLiveMisconceptionRow,
    TeacherLiveResponse,
    TeacherLiveScoreBandRow,
    TeacherLiveSummary,
    TeacherLiveTopicRow,
)


SCORE_BANDS = (
    ("0–20%", 20),
    ("21–40%", 40),
    ("41–60%", 60),
    ("61–80%", 80),
    ("81–100%", 100),
)


def _percentage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _newest_attempts(attempts: tuple[AttemptRecord, ...]) -> list[AttemptRecord]:
    # Stable two-pass ordering gives created_at descending, attempt_id ascending
    # for deterministic ties without parsing already-normalized UTC strings.
    ordered = sorted(attempts, key=lambda row: row.attempt_id)
    return sorted(ordered, key=lambda row: row.created_at, reverse=True)


class TeacherService:
    """Build a safe live dashboard from one durable SQLite snapshot."""

    def __init__(self, analytics_store: AnalyticsStore) -> None:
        self.analytics_store = analytics_store

    def live_analytics(self) -> TeacherLiveResponse:
        snapshot = self.analytics_store.read_snapshot()
        attempts = snapshot.attempts
        answers = snapshot.confirmed_answers
        answers_by_attempt: dict[str, list[AnswerRecord]] = defaultdict(list)
        for answer in answers:
            answers_by_attempt[answer.attempt_id].append(answer)

        completed = [attempt for attempt in attempts if attempt.status == "completed"]
        correct_answers = sum(answer.correct for answer in answers)
        confirmed_answers = len(answers)
        incorrect_answers = confirmed_answers - correct_answers
        misconception_count = sum(
            not answer.correct and bool((answer.misconception or "").strip())
            for answer in answers
        )
        completed_scores = [
            sum(answer.correct for answer in answers_by_attempt[attempt.attempt_id])
            for attempt in completed
        ]

        summary = TeacherLiveSummary(
            total_students=len({attempt.student_id for attempt in attempts}),
            total_attempts=len(attempts),
            completed_attempts=len(completed),
            in_progress_attempts=len(attempts) - len(completed),
            completion_rate=_percentage(len(completed), len(attempts)),
            confirmed_answers=confirmed_answers,
            correct_answers=correct_answers,
            incorrect_answers=incorrect_answers,
            overall_accuracy=_percentage(correct_answers, confirmed_answers),
            # Completed attempts with no confirmed answers contribute a score
            # of zero rather than disappearing from the denominator.
            average_score=_average(completed_scores),
            average_difficulty=_average(
                [answer.difficulty_score for answer in answers]
            ),
            misconception_count=misconception_count,
        )

        topic_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"attempted": 0, "correct": 0, "incorrect": 0}
        )
        for answer in answers:
            topic = answer.topic.strip()
            values = topic_counts[topic]
            values["attempted"] += 1
            values["correct" if answer.correct else "incorrect"] += 1
        topics = [
            TeacherLiveTopicRow(
                topic=topic,
                attempted=values["attempted"],
                correct=values["correct"],
                incorrect=values["incorrect"],
                accuracy=_percentage(values["correct"], values["attempted"]),
            )
            for topic, values in topic_counts.items()
        ]
        topics.sort(
            key=lambda row: (
                row.accuracy,
                -row.attempted,
                row.topic.casefold(),
                row.topic,
            )
        )

        misconception_counts: Counter[str] = Counter()
        for answer in answers:
            if answer.correct:
                continue
            misconception = (answer.misconception or "").strip()
            if misconception:
                misconception_counts[misconception] += 1
        misconceptions = [
            TeacherLiveMisconceptionRow(misconception=label, count=count)
            for label, count in sorted(
                misconception_counts.items(),
                key=lambda item: (-item[1], item[0].casefold(), item[0]),
            )
        ]

        difficulty_counts = Counter(answer.difficulty_score for answer in answers)
        difficulty = [
            TeacherLiveDifficultyRow(
                difficulty=level,
                count=difficulty_counts[level],
            )
            for level in range(1, 6)
        ]

        score_counts = {label: 0 for label, _ in SCORE_BANDS}
        for attempt in completed:
            attempt_answers = answers_by_attempt[attempt.attempt_id]
            accuracy = _percentage(
                sum(answer.correct for answer in attempt_answers),
                len(attempt_answers),
            )
            for label, upper_bound in SCORE_BANDS:
                if accuracy <= upper_bound:
                    score_counts[label] += 1
                    break
        score_distribution = [
            TeacherLiveScoreBandRow(band=label, attempts=score_counts[label])
            for label, _ in SCORE_BANDS
        ]

        student_rows = []
        for attempt in _newest_attempts(attempts):
            attempt_answers = answers_by_attempt[attempt.attempt_id]
            correct = sum(answer.correct for answer in attempt_answers)
            answered = len(attempt_answers)
            student_rows.append(
                TeacherLiveAttemptRow(
                    attempt_id=attempt.attempt_id,
                    student_id=attempt.student_id,
                    language=attempt.language,
                    status=attempt.status,
                    answered=answered,
                    correct=correct,
                    incorrect=answered - correct,
                    accuracy=_percentage(correct, answered),
                    initial_difficulty=attempt.initial_difficulty,
                    final_difficulty=attempt.final_difficulty,
                    created_at=attempt.created_at,
                    completed_at=attempt.completed_at,
                )
            )

        return TeacherLiveResponse(
            data_status="available" if attempts else "empty",
            summary=summary,
            topics=topics,
            misconceptions=misconceptions,
            difficulty=difficulty,
            score_distribution=score_distribution,
            students=student_rows,
        )
