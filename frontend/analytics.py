"""Pure analytics helpers for student results and the demo teacher dashboard."""

from collections import Counter, defaultdict


SCORE_BANDS = (
    ("0–20%", 20),
    ("21–40%", 40),
    ("41–60%", 60),
    ("61–80%", 80),
    ("81–100%", 100),
)


def calculate_accuracy(responses):
    """Return correct-answer percentage, or zero for an empty log."""
    if not responses:
        return 0.0
    correct = sum(bool(response.get("correct")) for response in responses)
    return round(correct / len(responses) * 100, 1)


def calculate_average_difficulty(responses):
    """Average numeric difficulty values while safely ignoring absent values."""
    difficulties = [
        response.get("difficulty_score")
        for response in responses
        if isinstance(response.get("difficulty_score"), (int, float))
    ]
    return round(sum(difficulties) / len(difficulties), 1) if difficulties else 0.0


def calculate_score(responses):
    """Return score statistics for a response log, including an empty log."""
    total = len(responses)
    correct = sum(bool(response.get("correct")) for response in responses)
    return {
        "correct": correct,
        "incorrect": total - correct,
        "total": total,
        "accuracy": calculate_accuracy(responses),
        "average_difficulty": calculate_average_difficulty(responses),
    }


def topic_performance(responses):
    """Aggregate attempts, correctness, accuracy, and error rate by topic."""
    topics = defaultdict(lambda: {"attempted": 0, "correct": 0, "incorrect": 0})
    for response in responses:
        topic = response.get("topic") or "Unspecified topic"
        topics[topic]["attempted"] += 1
        if response.get("correct"):
            topics[topic]["correct"] += 1
        else:
            topics[topic]["incorrect"] += 1

    result = {}
    for topic in sorted(topics, key=str.casefold):
        values = topics[topic]
        accuracy = round(values["correct"] / values["attempted"] * 100, 1)
        result[topic] = {
            **values,
            "accuracy": accuracy,
            "error_rate": round(100 - accuracy, 1),
        }
    return result


def misconception_counts(responses):
    """Aggregate misconception occurrences and topics from incorrect answers only."""
    counts = Counter()
    topics = defaultdict(set)
    for response in responses:
        label = response.get("misconception")
        if response.get("correct") or not label:
            continue
        counts[label] += 1
        if response.get("topic"):
            topics[label].add(response["topic"])

    return [
        {
            "label": label,
            "occurrences": count,
            "topics": sorted(topics[label], key=str.casefold),
        }
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    ]


def strongest_topic(performance):
    """Return the highest-accuracy topic, breaking ties alphabetically."""
    if not performance:
        return None
    return min(performance, key=lambda topic: (-performance[topic]["accuracy"], topic.casefold()))


def weakest_topic(performance):
    """Return the lowest-accuracy topic, breaking ties alphabetically."""
    if not performance:
        return None
    return min(performance, key=lambda topic: (performance[topic]["accuracy"], topic.casefold()))


def _option_text(option):
    if option is None:
        return "Unavailable"
    if isinstance(option, dict):
        return str(option.get("text", "Unavailable"))
    return str(getattr(option, "text", option))


def question_review(responses, questions=None):
    """Build compact review rows, optionally resolving text from question fixtures."""
    questions = questions or {}
    rows = []
    for fallback_index, response in enumerate(responses):
        question_id = response.get("question_id")
        question = questions.get(question_id) if hasattr(questions, "get") else None
        options = getattr(question, "options", []) if question is not None else []
        selected_index = response.get("selected_option_index")
        correct_index = response.get("correct_option_index")
        selected_option = (
            options[selected_index]
            if isinstance(selected_index, int) and 0 <= selected_index < len(options)
            else None
        )
        correct_option = (
            options[correct_index]
            if isinstance(correct_index, int) and 0 <= correct_index < len(options)
            else None
        )
        is_correct = bool(response.get("correct"))
        rows.append({
            "question_number": response.get("question_index", fallback_index) + 1,
            "question_id": question_id,
            "question": getattr(question, "question", response.get("question", "Question text unavailable")),
            "topic": response.get("topic") or "Unspecified topic",
            "difficulty": response.get("difficulty_score"),
            "student_answer": response.get("selected_answer") or _option_text(selected_option),
            "correct_answer": response.get("correct_answer") or _option_text(correct_option),
            "correct": is_correct,
            "misconception": None if is_correct else response.get("misconception"),
        })
    return sorted(rows, key=lambda row: row["question_number"])


def _completed_sessions(sessions):
    return [session for session in sessions if session.get("completed")]


def _completed_responses(sessions):
    return [
        response
        for session in _completed_sessions(sessions)
        for response in session.get("responses", [])
    ]


def student_summary(session):
    """Return one teacher-facing summary row for a student session."""
    responses = session.get("responses", [])
    score = calculate_score(responses)
    topics = topic_performance(responses)
    weak_topic = weakest_topic(topics)
    return {
        "student_id": session.get("student_id", "Unknown"),
        "student": session.get("student_name", session.get("student_id", "Unknown")),
        "completed": bool(session.get("completed")),
        "score": f'{score["correct"]} / {score["total"]}',
        "accuracy": score["accuracy"],
        "correct": score["correct"],
        "incorrect": score["incorrect"],
        "main_weak_topic": weak_topic,
        "misconceptions_count": sum(row["occurrences"] for row in misconception_counts(responses)),
    }


def class_topic_performance(sessions):
    """Rank completed-class topic aggregates by error rate, weakest first."""
    topics = topic_performance(_completed_responses(sessions))
    rows = [{"topic": topic, **values} for topic, values in topics.items()]
    return sorted(rows, key=lambda row: (-row["error_rate"], row["topic"].casefold()))


def class_misconceptions(sessions):
    """Aggregate occurrences and unique affected students for completed sessions."""
    completed = _completed_sessions(sessions)
    occurrences = Counter()
    affected_students = defaultdict(set)
    topics = defaultdict(set)
    for session in completed:
        student_id = session.get("student_id", "Unknown")
        for response in session.get("responses", []):
            label = response.get("misconception")
            if response.get("correct") or not label:
                continue
            occurrences[label] += 1
            affected_students[label].add(student_id)
            if response.get("topic"):
                topics[label].add(response["topic"])

    return [
        {
            "label": label,
            "occurrences": count,
            "students_affected": len(affected_students[label]),
            "student_percentage": round(len(affected_students[label]) / len(completed) * 100, 1)
            if completed
            else 0.0,
            "topics": sorted(topics[label], key=str.casefold),
        }
        for label, count in sorted(
            occurrences.items(), key=lambda item: (-item[1], item[0].casefold())
        )
    ]


def score_distribution(sessions):
    """Count completed students in fixed, non-overlapping accuracy bands."""
    distribution = {label: 0 for label, _ in SCORE_BANDS}
    for session in _completed_sessions(sessions):
        accuracy = calculate_accuracy(session.get("responses", []))
        for label, upper in SCORE_BANDS:
            if accuracy <= upper:
                distribution[label] += 1
                break
    return [{"band": label, "students": count} for label, count in distribution.items()]


def difficulty_distribution(sessions):
    """Count completed response difficulty levels, always including levels 1–5."""
    responses = _completed_responses(sessions)
    counts = Counter(
        response.get("difficulty_score")
        for response in responses
        if isinstance(response.get("difficulty_score"), (int, float))
    )
    counted_responses = sum(counts.values())
    levels = sorted(set(range(1, 6)) | set(counts))
    return [
        {
            "difficulty": level,
            "count": counts[level],
            "percentage": round(counts[level] / counted_responses * 100, 1)
            if counted_responses
            else 0.0,
        }
        for level in levels
    ]


def class_summary(sessions):
    """Calculate teacher summary metrics from completed demo sessions."""
    completed = _completed_sessions(sessions)
    scores = [calculate_score(session.get("responses", [])) for session in completed]
    responses = _completed_responses(sessions)
    misconceptions = class_misconceptions(sessions)
    return {
        "students": len(sessions),
        "completed_assessments": len(completed),
        "completion_rate": round(len(completed) / len(sessions) * 100, 1) if sessions else 0.0,
        "average_accuracy": round(sum(score["accuracy"] for score in scores) / len(scores), 1)
        if scores
        else 0.0,
        "average_correct": round(sum(score["correct"] for score in scores) / len(scores), 1)
        if scores
        else 0.0,
        "average_total": round(sum(score["total"] for score in scores) / len(scores), 1)
        if scores
        else 0.0,
        "distinct_misconceptions": len(misconceptions),
        "average_difficulty": calculate_average_difficulty(responses),
        "response_count": len(responses),
        "incorrect_response_count": sum(not response.get("correct") for response in responses),
    }


def teacher_insights(sessions):
    """Create concise, deterministic statements from class aggregates."""
    completed = _completed_sessions(sessions)
    topics = class_topic_performance(sessions)
    misconceptions = class_misconceptions(sessions)
    insights = []
    if topics:
        topic = topics[0]
        insights.append(
            f'{topic["topic"].title()} has the highest class error rate at '
            f'{topic["error_rate"]:g}% ({topic["incorrect"]} of {topic["attempted"]} responses).'
        )
    if misconceptions:
        misconception = misconceptions[0]
        insights.append(
            f'{misconception["label"].capitalize()} is the most common misconception with '
            f'{misconception["occurrences"]} occurrence'
            f'{"s" if misconception["occurrences"] != 1 else ""}, affecting '
            f'{misconception["students_affected"]} of {len(completed)} completed students.'
        )
    at_least_sixty = sum(
        calculate_accuracy(session.get("responses", [])) >= 60 for session in completed
    )
    insights.append(
        f'{at_least_sixty} of {len(completed)} completed students scored at least 60%.'
        if completed
        else "No completed student assessments are available for score insights."
    )
    return insights


def class_analytics(sessions):
    """Return all reusable teacher analytics in one render-friendly payload."""
    summary = class_summary(sessions)
    return {
        **summary,
        "score_distribution": score_distribution(sessions),
        "misconceptions": class_misconceptions(sessions),
        "topics": class_topic_performance(sessions),
        "difficulty": difficulty_distribution(sessions),
        "students_table": [student_summary(session) for session in sessions],
        "insights": teacher_insights(sessions),
    }
