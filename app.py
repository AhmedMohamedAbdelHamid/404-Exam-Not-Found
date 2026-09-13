from html import escape

import streamlit as st

from frontend.dummy_data import QUESTION_FIXTURES
from frontend.ui import apply_styles, bars, heading, metrics, panel


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
    heading("Assessment Complete", "A clearer picture of your progress, and where to go next.", "SAMPLE RESULTS")
    st.markdown(
        '<section class="score-panel"><div class="score-ring"><div><strong>80<span>%</span></strong>'
        '<small>ACCURACY</small></div></div><div><div class="eyebrow">A STRONG FOUNDATION</div>'
        '<div class="score-number">8 <span>/ 10</span></div>'
        '<p>Keep building on what you know.<br>Your next focus: comparison operators.</p></div>'
        '<span class="sample-pill">Illustrative results</span></section>',
        unsafe_allow_html=True,
    )
    metrics([("Score", "8 / 10", "Correct answers"), ("Accuracy", "80%", "Overall performance"),
             ("Current Level", "3 / 5", "Sample difficulty level"), ("Questions", "10", "In this example")])
    left, right = st.columns([1.25, 1], gap="medium")
    with left:
        panel("Performance Overview", "Sample accuracy by topic", bars([
            ("Variables", 100), ("Loops", 80), ("Comparisons", 60)], unit="%"))
        panel("Misconceptions Detected", "Two example learning signals",
              '<div class="insight-row"><span class="index">01</span><div><strong>Assignment vs. equality</strong>'
              '<p>Distinguishing = from ==</p></div></div>'
              '<div class="insight-row"><span class="index">02</span><div><strong>Loop boundaries</strong>'
              '<p>Remembering that range excludes its endpoint</p></div></div>')
    with right:
        panel("Strongest Topic", "BUILD ON THIS", '<div class="topic-title">Variables & assignment</div>'
              '<p class="body-copy">A solid understanding of how values are stored and assigned.</p>'
              '<span class="tag">100% · Sample accuracy</span>')
        panel("Needs Attention", "YOUR NEXT FOCUS", '<div class="topic-title">Comparison operators</div>'
              '<p class="body-copy">Review how equality and inequality checks differ from assignment.</p>'
              '<span class="tag accent">Suggested review</span>')

else:
    heading("Teacher Dashboard", "A class-wide perspective. A more focused next lesson.", "SAMPLE CLASS DATA")
    metrics([("Students", "32", "In the sample class"), ("Average Score", "7.6 / 10", "Sample class average"),
             ("Completion Rate", "88%", "28 of 32 students"), ("Misconceptions", "6", "Distinct sample patterns")])
    left, right = st.columns([1.25, 1], gap="medium")
    with left:
        panel("Class Performance", "Illustrative student distribution by score",
              '<div class="chart-columns" role="img" aria-label="Sample score distribution: '
              '0–2: 1 student; 3–4: 2; 5–6: 5; 7–8: 12; 9–10: 8.">'
              + "".join(f'<div class="chart-column"><span>{count}</span>'
                        f'<i style="height:{count * 9}px"></i><small>{label}</small></div>'
                        for label, count in [("0–2", 1), ("3–4", 2), ("5–6", 5), ("7–8", 12), ("9–10", 8)])
              + '</div><div class="chart-foot">SCORE BAND <span>28 completed assessments</span></div>')
        panel("Weakest Topics", "Sample incorrect-answer rate",
              bars([("Comparison operators", 42), ("Loop boundaries", 35), ("Functions", 24)], unit="%"))
    with right:
        panel("Most Common Misconceptions", "Illustrative number of students affected",
              bars([("Assignment vs. equality", 12), ("Off-by-one boundaries", 9), ("Return vs. print", 6)], maximum=16))
        panel("Difficulty Distribution", "Sample questions by difficulty level",
              bars([("Level 1 · Recall", 15), ("Level 2 · Understand", 25), ("Level 3 · Apply", 35),
                    ("Level 4 · Analyze", 20), ("Level 5 · Evaluate", 5)], unit="%"))

st.markdown('<footer class="app-footer"><span>404 / EXAM NOT FOUND</span>'
            '<span>Demo workspace · All result and dashboard figures are illustrative.</span></footer>',
            unsafe_allow_html=True)
