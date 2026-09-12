from html import escape

import streamlit as st

from frontend.dummy_data import DUMMY_QUESTION
from frontend.ui import apply_styles, bars, heading, metrics, panel


st.set_page_config(page_title="404 — Exam Not Found", page_icon="◈", layout="wide")
apply_styles()


def navigate(view):
    st.session_state.view = view


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
        '<p>One sample question.<br>A preview of what comes next.</p></div>'
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
    question = DUMMY_QUESTION
    st.markdown(
        '<div class="exam-top"><div><span class="eyebrow">YOUR ASSESSMENT</span>'
        '<h2>Question <b>01</b><span class="muted"> / 10</span></h2></div>'
        f'<span class="difficulty"><i></i> Difficulty · {question.difficulty_score}/5</span></div>',
        unsafe_allow_html=True,
    )
    st.progress(0.1, text="Sample assessment · Question 1 of 10 · 10% complete")
    with st.container(border=True, key="question_card"):
        language = "English" if question.language.value == "en" else "Arabic"
        st.markdown(
            '<div class="badges"><span>PYTHON FUNDAMENTALS</span>'
            f'<span>{escape(question.topic.upper())}</span><span>{language.upper()}</span></div>'
            f'<h3 class="question-text">{escape(question.question)}</h3>'
            '<p class="question-hint">Select the one best answer.</p>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Choose one answer", range(len(question.options)), index=None,
            format_func=lambda index: f"**{chr(65 + index)}**　 `{question.options[index].text}`",
            label_visibility="collapsed", key="sample_answer",
        )
        st.markdown('<div class="control-divider"></div>', unsafe_allow_html=True)
        previous, status, submit = st.columns([1, 2, 1.3], vertical_alignment="center")
        with previous:
            st.button("Previous", disabled=True, use_container_width=True)
        with status:
            st.markdown('<div class="control-status">Question 1 of 10 <span>·</span> 10% complete</div>',
                        unsafe_allow_html=True)
        with submit:
            st.button("Submit Answer →", type="primary", disabled=True, use_container_width=True)
    st.caption("Demo preview · Selection is available. Submission and progression are not enabled yet.")

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
