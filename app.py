from html import escape

import streamlit as st

from frontend.analytics import (
    calculate_score,
    class_analytics,
    misconception_counts,
    question_review,
    strongest_topic,
    topic_performance,
    weakest_topic,
)
from frontend.dummy_data import DEMO_CLASS_SESSIONS, QUESTION_FIXTURES
from frontend.ui import apply_styles, bar_chart, chart_panel, heading, metrics, panel


st.set_page_config(page_title="404 — Exam Not Found", page_icon="◈", layout="wide")
apply_styles()


def navigate(view):
    st.session_state.view = view


EXAM_STATE_DEFAULTS = {
    "exam_started": False,
    "current_question_index": 0,
    "selected_answer": None,
    "current_question_submitted": False,
    "answers": [],
    "exam_complete": False,
}


def initialize_exam_state():
    for key, value in EXAM_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, list) else value


def reset_exam():
    for key, value in EXAM_STATE_DEFAULTS.items():
        st.session_state[key] = value.copy() if isinstance(value, list) else value
    for key in list(st.session_state):
        if key.startswith("exam_answer_"):
            del st.session_state[key]


initialize_exam_state()


if "view" not in st.session_state:
    st.session_state.view = "Exam"

with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">404<span>.</span></div>'
        '<strong>Exam Not Found</strong><p>A clearer measure of learning.</p></div>'
        '<div class="eyebrow nav-label">WORKSPACE</div>',
        unsafe_allow_html=True,
    )
    for view in ("Exam", "Results", "Teacher Dashboard"):
        st.button(view, key=f"nav_{view}", use_container_width=True,
                  type="primary" if st.session_state.view == view else "secondary",
                  on_click=navigate, args=(view,))
    st.markdown(
        '<div class="sidebar-note"><span class="live-dot"></span> DEMO WORKSPACE'
        '<p>Five-question assessment.<br>Local schema-compatible fixtures.</p></div>'
        '<div class="sidebar-footer">GENAI FOR EDUCATION<br><span>Student track / 2026</span></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<header class="hero"><div class="eyebrow">404 / EXAM NOT FOUND</div>'
    '<h1>Adaptive assessments.<br><span>Grounded in your textbook.</span></h1>'
    '<p>Designed around how you learn. Built on what you study.</p></header>',
    unsafe_allow_html=True,
)

if st.session_state.view == "Exam":
    question_items = list(QUESTION_FIXTURES.items())
    question_count = len(question_items)

    if not st.session_state.exam_started:
        st.markdown(
            '<section class="start-panel"><div class="eyebrow">YOUR ASSESSMENT</div>'
            '<h2>Python Fundamentals</h2><div class="start-meta">'
            '<span>5 Questions</span><span>English</span></div>'
            '<p>Test your understanding of core Python concepts. Submit each answer to see '
            'feedback before moving to the next question.</p></section>',
            unsafe_allow_html=True,
        )
        if st.button("Start Assessment →", type="primary", use_container_width=True):
            reset_exam()
            st.session_state.exam_started = True
            st.rerun()

    elif st.session_state.exam_complete:
        correct_count = sum(answer["correct"] for answer in st.session_state.answers)
        accuracy = round(correct_count / question_count * 100)
        st.markdown(
            '<section class="completion-panel"><div class="eyebrow">ASSESSMENT COMPLETE</div>'
            '<h2>Assessment Complete</h2>'
            f'<div class="completion-score"><strong>{correct_count}</strong><span> / {question_count}</span></div>'
            f'<p>{accuracy}% accuracy · Your responses have been recorded for this session.</p></section>',
            unsafe_allow_html=True,
        )
        results, restart = st.columns([1.4, 1])
        with results:
            if st.button("View Results", type="primary", use_container_width=True):
                navigate("Results")
                st.rerun()
        with restart:
            if st.button("Restart Assessment", use_container_width=True):
                reset_exam()
                st.session_state.exam_started = True
                st.rerun()

    else:
        question_index = st.session_state.current_question_index
        question_id, question = question_items[question_index]
        progress = (question_index + 1) / question_count
        progress_percent = round(progress * 100)
        header, restart = st.columns([4, 1.25], vertical_alignment="center")
        with header:
            st.markdown(
                '<div class="exam-top"><div><span class="eyebrow">YOUR ASSESSMENT</span>'
                f'<h2>Question <b>{question_index + 1:02d}</b><span class="muted"> / {question_count:02d}</span></h2></div>'
                f'<span class="difficulty"><i></i> Difficulty · {question.difficulty_score}/5</span></div>',
                unsafe_allow_html=True,
            )
        with restart:
            if st.button("Restart Assessment", use_container_width=True):
                reset_exam()
                st.session_state.exam_started = True
                st.rerun()

        st.progress(
            progress,
            text=f"Python Fundamentals · Question {question_index + 1} of {question_count} · {progress_percent}% complete",
        )
        with st.container(border=True, key="question_card"):
            language = "English" if question.language.value == "en" else "Arabic"
            st.markdown(
                '<div class="badges"><span>PYTHON FUNDAMENTALS</span>'
                f'<span>{escape(question.topic.upper())}</span><span>{language.upper()}</span></div>'
                f'<h3 class="question-text">{escape(question.question)}</h3>'
                '<p class="question-hint">Select the one best answer.</p>',
                unsafe_allow_html=True,
            )
            submitted_response = None
            if st.session_state.current_question_submitted:
                submitted_response = next(
                    answer for answer in st.session_state.answers if answer["question_id"] == question_id
                )
            persisted_answer = (
                submitted_response["selected_option_index"]
                if submitted_response is not None
                else st.session_state.selected_answer
            )
            selected_answer = st.radio(
                "Choose one answer",
                range(len(question.options)),
                index=persisted_answer,
                format_func=lambda index: f"**{chr(65 + index)}**　 `{question.options[index].text}`",
                label_visibility="collapsed",
                key=f"exam_answer_{question_id}",
                disabled=st.session_state.current_question_submitted,
            )
            st.session_state.selected_answer = selected_answer

            if st.session_state.current_question_submitted:
                correct_index = submitted_response["correct_option_index"]
                if submitted_response["correct"]:
                    st.markdown('<div class="answer-feedback correct">Correct</div>', unsafe_allow_html=True)
                else:
                    correct_text = escape(question.options[correct_index].text)
                    st.markdown(
                        f'<div class="answer-feedback incorrect"><strong>Incorrect</strong>'
                        f'<span>Correct answer: {chr(65 + correct_index)}. {correct_text}</span></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('<div class="control-divider"></div>', unsafe_allow_html=True)
            status, action = st.columns([2, 1.3], vertical_alignment="center")
            with status:
                st.markdown(
                    f'<div class="control-status">Question {question_index + 1} of {question_count} '
                    f'<span>·</span> {progress_percent}% complete</div>',
                    unsafe_allow_html=True,
                )
            with action:
                if not st.session_state.current_question_submitted:
                    if st.button(
                        "Submit Answer →",
                        type="primary",
                        disabled=selected_answer is None,
                        use_container_width=True,
                    ):
                        correct_index = next(i for i, option in enumerate(question.options) if option.correct)
                        is_correct = selected_answer == correct_index
                        if not any(answer["question_id"] == question_id for answer in st.session_state.answers):
                            st.session_state.answers.append({
                                "question_id": question_id,
                                "question_index": question_index,
                                "topic": question.topic,
                                "selected_option_index": selected_answer,
                                "correct_option_index": correct_index,
                                "correct": is_correct,
                                "misconception": None if is_correct else question.options[selected_answer].misconception,
                                "difficulty_score": question.difficulty_score,
                            })
                        st.session_state.current_question_submitted = True
                        st.rerun()
                elif question_index < question_count - 1:
                    if st.button("Next Question →", type="primary", use_container_width=True):
                        st.session_state.current_question_index += 1
                        st.session_state.selected_answer = None
                        st.session_state.current_question_submitted = False
                        st.rerun()
                elif st.button("Finish Assessment →", type="primary", use_container_width=True):
                    st.session_state.exam_complete = True
                    st.rerun()

elif st.session_state.view == "Results":
    if not st.session_state.exam_complete or not st.session_state.answers:
        result_action = "Continue Assessment" if st.session_state.exam_started else "Start Assessment"
        heading(
            "Assessment Results",
            "Complete the assessment to unlock your session analytics.",
            "CURRENT SESSION",
        )
        st.markdown(
            '<section class="empty-state"><div class="empty-mark">◇</div>'
            '<h3>No completed assessment yet.</h3>'
            '<p>Your score, topic performance, and learning signals will appear here.</p></section>',
            unsafe_allow_html=True,
        )
        if st.button(result_action, type="primary", use_container_width=True):
            navigate("Exam")
            st.rerun()
    else:
        responses = st.session_state.answers
        score = calculate_score(responses)
        topics = topic_performance(responses)
        misconceptions = misconception_counts(responses)
        strongest = strongest_topic(topics)
        weakest = weakest_topic(topics)
        accuracy_text = f'{score["accuracy"]:g}'

        heading(
            "Assessment Complete",
            "Your performance from this completed assessment session.",
            "REAL SESSION DATA",
        )
        st.markdown(
            f'<section class="score-panel"><div class="score-ring" '
            f'style="background:conic-gradient(#FF3040 {score["accuracy"]}%,#292930 0)">'
            f'<div><strong>{accuracy_text}<span>%</span></strong><small>ACCURACY</small></div></div>'
            '<div><div class="eyebrow">YOUR COMPLETED ASSESSMENT</div>'
            f'<div class="score-number">{score["correct"]} <span>/ {score["total"]}</span></div>'
            '<p>Results are calculated from your submitted answers in this session.</p></div>'
            '<span class="sample-pill">Current session</span></section>',
            unsafe_allow_html=True,
        )
        metrics([
            ("Score", f'{score["correct"]} / {score["total"]}', "Correct answers / attempted"),
            ("Accuracy", f'{score["accuracy"]:g}%', "Overall performance"),
            ("Correct", str(score["correct"]), "Submitted answers"),
            ("Incorrect", str(score["incorrect"]), "Submitted answers"),
            ("Average Difficulty", f'{score["average_difficulty"]:g} / 5', "Across answered questions"),
        ])

        topic_content = "".join(
            '<div class="topic-performance-row">'
            f'<div><span>{escape(topic.title())}</span><strong>{values["accuracy"]:g}%</strong></div>'
            f'<small>{values["attempted"]} attempted · {values["correct"]} correct · '
            f'{values["incorrect"]} incorrect · {values["error_rate"]:g}% error rate</small>'
            f'<div class="bar-track"><i style="width:{values["accuracy"]}%"></i></div></div>'
            for topic, values in topics.items()
        )
        if misconceptions:
            misconception_content = "".join(
                '<div class="insight-row">'
                f'<span class="index">{index:02d}</span><div><strong>{escape(item["label"])}</strong>'
                f'<p>{item["occurrences"]} occurrence{"s" if item["occurrences"] != 1 else ""} · '
                f'Topic{"s" if len(item["topics"]) != 1 else ""}: '
                f'{escape(", ".join(topic.title() for topic in item["topics"]) or "Unavailable")}</p></div></div>'
                for index, item in enumerate(misconceptions, start=1)
            )
            misconception_subtitle = "Incorrect selected answers only · most frequent first"
        else:
            misconception_content = (
                '<p class="body-copy">No misconceptions detected in this assessment.</p>'
            )
            misconception_subtitle = "No incorrect-answer learning signals"

        left, right = st.columns([1.25, 1], gap="medium")
        with left:
            panel("Performance by Topic", "Attempted, correct, incorrect, and accuracy", topic_content)
            panel("Misconceptions Detected", misconception_subtitle, misconception_content)
        with right:
            strongest_values = topics[strongest]
            panel(
                "Strongest Topic",
                "HIGHEST ACCURACY · TIES SORTED A–Z",
                f'<div class="topic-title">{escape(strongest.title())}</div>'
                f'<p class="body-copy">{strongest_values["correct"]} correct of '
                f'{strongest_values["attempted"]} attempted.</p>'
                f'<span class="tag">{strongest_values["accuracy"]:g}% accuracy</span>',
            )
            weakest_values = topics[weakest]
            attention_copy = (
                "No errors recorded. This topic is listed by the deterministic accuracy tie-break."
                if weakest_values["incorrect"] == 0
                else f'Review your incorrect responses in this topic first: '
                     f'{weakest_values["incorrect"]} of {weakest_values["attempted"]} '
                     f'were incorrect ({weakest_values["error_rate"]:g}% error rate).'
            )
            panel(
                "Needs Attention",
                "LOWEST ACCURACY · TIES SORTED A–Z",
                f'<div class="topic-title">{escape(weakest.title())}</div>'
                f'<p class="body-copy">{escape(attention_copy)}</p>'
                f'<span class="tag accent">{weakest_values["accuracy"]:g}% accuracy</span>',
            )

        reviews = question_review(responses, QUESTION_FIXTURES)
        st.markdown(
            '<div class="section-heading"><h3>Question Review</h3>'
            '<p>Your submitted answer compared with the correct answer.</p></div>',
            unsafe_allow_html=True,
        )
        for review in reviews:
            status = "Correct" if review["correct"] else "Incorrect"
            difficulty = review["difficulty"] if review["difficulty"] is not None else "Not available"
            with st.expander(
                f'Question {review["question_number"]:02d} · {review["topic"].title()} · {status}'
            ):
                misconception_review = (
                    '<div class="review-cell wide incorrect"><small>Misconception</small>'
                    f'<span>{escape(review["misconception"])}</span></div>'
                    if review["misconception"]
                    else ""
                )
                st.markdown(
                    f'<p class="review-question">{escape(review["question"])}</p>'
                    '<div class="review-grid">'
                    f'<div class="review-cell"><small>Topic</small><span>{escape(review["topic"].title())}</span></div>'
                    f'<div class="review-cell"><small>Difficulty</small><span>{escape(str(difficulty))} / 5</span></div>'
                    f'<div class="review-cell {"correct" if review["correct"] else "incorrect"}">'
                    f'<small>Your answer · {status}</small><span>{escape(review["student_answer"])}</span></div>'
                    f'<div class="review-cell correct"><small>Correct answer</small>'
                    f'<span>{escape(review["correct_answer"])}</span></div>{misconception_review}</div>',
                    unsafe_allow_html=True,
                )

else:
    class_data = class_analytics(DEMO_CLASS_SESSIONS)
    completed_count = class_data["completed_assessments"]

    heading(
        "Teacher Dashboard",
        "A deterministic class analytics preview for teaching decisions.",
        "DEMO CLASS DATA · NOT LIVE",
    )
    metrics([
        ("Students", str(class_data["students"]), "Total fictional class roster"),
        ("Completed Assessments", str(completed_count), "Completed demo assessments"),
        ("Completion Rate", f'{class_data["completion_rate"]:g}%',
         f'{completed_count} of {class_data["students"]} demo students'),
        ("Average Accuracy", f'{class_data["average_accuracy"]:g}%', "Completed demo students only"),
        ("Average Score", f'{class_data["average_correct"]:g} / {class_data["average_total"]:g}',
         "Mean correct / mean attempted"),
        ("Distinct Misconceptions", str(class_data["distinct_misconceptions"]), "Distinct incorrect-answer labels"),
        ("Average Difficulty", f'{class_data["average_difficulty"]:g} / 5',
         "Completed response average"),
    ])

    score_rows = class_data["score_distribution"]
    score_figure = bar_chart(
        [row["band"] for row in score_rows],
        [row["students"] for row in score_rows],
        hover_details=[f'{row["students"]} completed students' for row in score_rows],
    )
    misconception_rows = class_data["misconceptions"][:5]
    misconception_labels = [
        f'{row["label"]} · {row["students_affected"]}/{completed_count} students'
        for row in misconception_rows
    ]
    misconception_figure = bar_chart(
        misconception_labels,
        [row["occurrences"] for row in misconception_rows],
        horizontal=True,
        hover_details=[
            f'{row["occurrences"]} occurrences · {row["students_affected"]} students '
            f'({row["student_percentage"]:g}% of completed)'
            for row in misconception_rows
        ],
    )
    topic_figure = bar_chart(
        [row["topic"].title() for row in class_data["topics"]],
        [row["error_rate"] for row in class_data["topics"]],
        horizontal=True,
        value_suffix="%",
        hover_details=[
            f'{row["incorrect"]} incorrect · {row["correct"]} correct · {row["attempted"]} attempted'
            for row in class_data["topics"]
        ],
    )
    difficulty_figure = bar_chart(
        [f'Difficulty {row["difficulty"]:g}' for row in class_data["difficulty"]],
        [row["percentage"] for row in class_data["difficulty"]],
        value_suffix="%",
        hover_details=[f'{row["count"]} responses' for row in class_data["difficulty"]],
    )

    left, right = st.columns([1.25, 1], gap="medium")
    with left:
        chart_panel(
            "Class Performance",
            f'Completed demo students per accuracy band · n={completed_count} students',
            score_figure,
            "class_performance",
        )
        attempts_per_topic = class_data["topics"][0]["attempted"] if class_data["topics"] else 0
        chart_panel(
            "Weakest Topics",
            f'Incorrect responses ÷ attempts per topic · {attempts_per_topic} attempts each',
            topic_figure,
            "weakest_topics",
        )
    with right:
        chart_panel(
            "Most Common Misconceptions",
            f'Bars show occurrences; labels show unique affected students · '
            f'{class_data["incorrect_response_count"]} incorrect responses total',
            misconception_figure,
            "misconceptions",
        )
        chart_panel(
            "Difficulty Distribution",
            f'Response share by question difficulty · n={class_data["response_count"]} responses',
            difficulty_figure,
            "difficulty",
        )

    insight_content = '<div class="insight-summary">' + "".join(
        f'<div><b>{index:02d}</b><span>{escape(insight)}</span></div>'
        for index, insight in enumerate(class_data["insights"], start=1)
    ) + '</div>'
    panel(
        "Class Insight Summary",
        "Calculated from completed deterministic demo sessions",
        insight_content,
    )

    teacher_rows = [
        {
            "Student": row["student"],
            "Status": "Completed" if row["completed"] else "In progress",
            "Score": row["score"],
            "Accuracy": f'{row["accuracy"]:g}%',
            "Correct": row["correct"],
            "Incorrect": row["incorrect"],
            "Main weak topic": row["main_weak_topic"].title() if row["main_weak_topic"] else "—",
            "Misconceptions": row["misconceptions_count"],
        }
        for row in class_data["students_table"]
    ]
    with st.container(border=True, key="teacher_table"):
        st.markdown(
            '<div class="chart-heading"><h3>Student Performance</h3>'
            '<p>All fictional demo sessions; in-progress scores reflect submitted responses only.</p></div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            teacher_rows,
            hide_index=True,
            width="stretch",
            column_order=(
                "Student", "Status", "Score", "Accuracy", "Correct", "Incorrect",
                "Main weak topic", "Misconceptions",
            ),
        )

st.markdown('<footer class="app-footer"><span>404 / EXAM NOT FOUND</span>'
            '<span>Student results: current session · Teacher dashboard: deterministic demo data.</span></footer>',
            unsafe_allow_html=True)
