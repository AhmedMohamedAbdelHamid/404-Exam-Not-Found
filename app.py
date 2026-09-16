from html import escape
import random
import re

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
from frontend.dummy_data import DEMO_CLASS_SESSIONS
from frontend.question_provider import (
    LANGUAGE_LABELS,
    create_chunk_sampler,
    curriculum_size,
    default_staircase_db_path,
    fetch_next_question,
    initialize_student,
    inspect_runtime,
    new_attempt_identity,
    read_student_state,
    reconcile_answer_state,
    student_exam_complete,
    submit_answer_once,
)
from frontend.ui import (
    apply_styles,
    bar_chart,
    chart_panel,
    compact_chart_label,
    heading,
    metrics,
    panel,
)


st.set_page_config(page_title="404 — Exam Not Found", page_icon="◈", layout="wide")
apply_styles()


UI_COPY = {
    "en": {
        "your_assessment": "YOUR ASSESSMENT",
        "question": "Question",
        "adaptive_level": "Adaptive level",
        "restart_assessment": "Restart Assessment",
        "select_answer": "Select the one best answer.",
        "choose_answer": "Choose one answer",
        "fallback_question": "FALLBACK QUESTION",
        "correct": "Correct",
        "incorrect": "Incorrect",
        "correct_answer": "Correct answer",
        "learning_signal": "Learning signal",
        "submit_answer": "Submit Answer →",
        "next_question": "Next Question →",
        "finish_assessment": "Finish Assessment →",
        "verified_fallback": "Verified fallback",
        "textbook_grounded": "Textbook grounded",
        "assessment_complete": "Assessment Complete",
        "final_level": "Final adaptive level",
        "completion_summary": "{accuracy}% accuracy{level} · Your responses are ready to review.",
        "view_results": "View Results",
        "start_new_attempt": "Start New Attempt",
        "results_subtitle": "Your performance from this completed assessment session.",
        "real_session": "REAL SESSION DATA",
        "accuracy": "Accuracy",
        "completed_assessment": "YOUR COMPLETED ASSESSMENT",
        "results_calculated": "Results are calculated from your submitted answers in this session.",
        "current_session": "Current session",
        "score": "Score",
        "correct_answers_attempted": "Correct answers / attempted",
        "overall_performance": "Overall performance",
        "submitted_answers": "Submitted answers",
        "average_difficulty": "Average Difficulty",
        "across_answered": "Across answered questions",
        "topic_statistics": "{attempted} attempted · {correct} correct · {incorrect} incorrect · {error_rate}% error rate",
        "occurrence_topics": "{occurrences} occurrence(s) · Topics: {topics}",
        "unavailable": "Unavailable",
        "correct_of_attempted": "{correct} correct of {attempted} attempted.",
        "accuracy_value": "{accuracy}% accuracy",
        "no_errors_tie": "No errors recorded. This topic is listed by the deterministic accuracy tie-break.",
        "review_errors": "Review your incorrect responses in this topic first: {incorrect} of {attempted} were incorrect ({error_rate}% error rate).",
        "performance_by_topic": "Performance by Topic",
        "performance_subtitle": "Attempted, correct, incorrect, and accuracy",
        "strongest_topic": "Strongest Topic",
        "highest_accuracy": "HIGHEST ACCURACY · TIES SORTED A–Z",
        "needs_attention": "Needs Attention",
        "lowest_accuracy": "LOWEST ACCURACY · TIES SORTED A–Z",
        "misconceptions": "Misconceptions Detected",
        "misconception": "Misconception",
        "misconceptions_subtitle": "Incorrect selected answers only · most frequent first",
        "no_misconceptions": "No misconceptions detected in this assessment.",
        "no_misconceptions_subtitle": "No incorrect-answer learning signals",
        "question_review": "Question Review",
        "question_review_subtitle": "Your submitted answer compared with the correct answer.",
        "your_answer": "Your answer",
        "topic": "Topic",
        "difficulty": "Difficulty",
        "not_available": "Not available",
    },
    "ar": {
        "your_assessment": "تقييمك",
        "question": "السؤال",
        "adaptive_level": "المستوى التكيفي",
        "restart_assessment": "إعادة بدء التقييم",
        "select_answer": "اختر الإجابة الصحيحة.",
        "choose_answer": "اختر إجابة واحدة",
        "fallback_question": "سؤال احتياطي",
        "correct": "إجابة صحيحة",
        "incorrect": "إجابة غير صحيحة",
        "correct_answer": "الإجابة الصحيحة",
        "learning_signal": "ملاحظة تعليمية",
        "submit_answer": "إرسال الإجابة",
        "next_question": "السؤال التالي",
        "finish_assessment": "إنهاء التقييم",
        "verified_fallback": "سؤال احتياطي موثوق",
        "textbook_grounded": "مستند إلى الكتاب الدراسي",
        "assessment_complete": "اكتمل التقييم",
        "final_level": "المستوى التكيفي النهائي",
        "completion_summary": "الدقة {accuracy}%{level} · إجاباتك جاهزة للمراجعة.",
        "view_results": "عرض النتائج",
        "start_new_attempt": "بدء محاولة جديدة",
        "results_subtitle": "أداؤك في جلسة التقييم المكتملة.",
        "real_session": "بيانات الجلسة الفعلية",
        "accuracy": "الدقة",
        "completed_assessment": "تقييمك المكتمل",
        "results_calculated": "حُسبت النتائج من إجاباتك المرسلة في هذه الجلسة.",
        "current_session": "الجلسة الحالية",
        "score": "النتيجة",
        "correct_answers_attempted": "الإجابات الصحيحة / المحاولات",
        "overall_performance": "الأداء العام",
        "submitted_answers": "الإجابات المرسلة",
        "average_difficulty": "متوسط الصعوبة",
        "across_answered": "عبر الأسئلة المجابة",
        "topic_statistics": "{attempted} محاولة · {correct} صحيحة · {incorrect} خاطئة · معدل الخطأ {error_rate}%",
        "occurrence_topics": "التكرار: {occurrences} · الموضوعات: {topics}",
        "unavailable": "غير متاح",
        "correct_of_attempted": "{correct} إجابة صحيحة من {attempted} محاولة.",
        "accuracy_value": "الدقة {accuracy}%",
        "no_errors_tie": "لم تُسجل أخطاء. أُدرج هذا الموضوع وفق قاعدة حسم التعادل في الدقة.",
        "review_errors": "راجع إجاباتك الخاطئة في هذا الموضوع أولًا: {incorrect} من {attempted} كانت خاطئة (معدل الخطأ {error_rate}%).",
        "performance_by_topic": "الأداء حسب الموضوع",
        "performance_subtitle": "المحاولات والإجابات الصحيحة والخاطئة والدقة",
        "strongest_topic": "أقوى موضوع",
        "highest_accuracy": "أعلى دقة · يُرتب التعادل أبجديًا",
        "needs_attention": "يحتاج إلى اهتمام",
        "lowest_accuracy": "أقل دقة · يُرتب التعادل أبجديًا",
        "misconceptions": "المفاهيم الخاطئة المكتشفة",
        "misconception": "المفهوم الخاطئ",
        "misconceptions_subtitle": "الإجابات الخاطئة المختارة فقط · الأكثر تكرارًا أولًا",
        "no_misconceptions": "لم تُكتشف مفاهيم خاطئة في هذا التقييم.",
        "no_misconceptions_subtitle": "لا توجد إشارات تعلم من إجابات خاطئة",
        "question_review": "مراجعة الأسئلة",
        "question_review_subtitle": "إجابتك المرسلة مقارنة بالإجابة الصحيحة.",
        "your_answer": "إجابتك",
        "topic": "الموضوع",
        "difficulty": "الصعوبة",
        "not_available": "غير متاح",
    },
}


_LTR_RUN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ \t=+\-*/%<>()\[\]{},.:;'\"\\]*")
_CODE_MARKER = re.compile(
    r"[_=+\-*/%<>()\[\]{}'\"`] | \d | \b(?:print|def|return|for|while|if|else|True|False|None)\b",
    re.VERBOSE,
)


def ui_text(key, language="en", **values):
    """Return student-facing copy without coupling it to analytics logic."""
    language = language if language in UI_COPY else "en"
    return UI_COPY[language][key].format(**values)


def mixed_content_html(value, language="en"):
    """Escape generated content, then isolate LTR runs inside Arabic prose."""
    text = str(value)
    if language != "ar":
        return escape(text)

    output = []
    cursor = 0
    for match in _LTR_RUN.finditer(text):
        output.append(escape(text[cursor:match.start()]))
        fragment = match.group(0)
        css_class = "code-fragment" if _CODE_MARKER.search(fragment) else "ltr-fragment"
        output.append(
            f'<bdi dir="ltr" class="{css_class}">{escape(fragment)}</bdi>'
        )
        cursor = match.end()
    output.append(escape(text[cursor:]))
    return "".join(output)


def mixed_content_markdown(value, language="en"):
    """Use Unicode isolation for mixed-direction text rendered by st.radio."""
    text = str(value)
    if language != "ar":
        return markdown_text(text)

    output = []
    cursor = 0
    for match in _LTR_RUN.finditer(text):
        output.append(markdown_text(text[cursor:match.start()]))
        output.append(f'\u2066{markdown_text(match.group(0))}\u2069')
        cursor = match.end()
    output.append(markdown_text(text[cursor:]))
    return "".join(output)


def misconception_summary(item, language="en"):
    topics = ", ".join(topic.title() for topic in item["topics"]) or ui_text(
        "unavailable", language
    )
    if language == "ar":
        return ui_text(
            "occurrence_topics",
            language,
            occurrences=item["occurrences"],
            topics=topics,
        )
    occurrence_suffix = "s" if item["occurrences"] != 1 else ""
    topic_suffix = "s" if len(item["topics"]) != 1 else ""
    return (
        f'{item["occurrences"]} occurrence{occurrence_suffix} · '
        f'Topic{topic_suffix}: {topics}'
    )


def navigate(view):
    st.session_state.view = view


EXAM_STATE_DEFAULTS = {
    "exam_started": False,
    "current_question_index": 0,
    "current_question_id": None,
    "current_question": None,
    "selected_answer": None,
    "selected_original_index": None,
    "current_question_submitted": False,
    "answers": [],
    "exam_complete": False,
    "option_orders": {},
    "questions": {},
    "question_order": [],
    "question_metadata": {},
    "backend_answer_recorded": {},
    "answer_save_status": {},
    "answer_pre_states": {},
    "answer_reconciliation_checked": {},
    "submission_errors": {},
    "generation_error": None,
    "generation_debug": None,
    "generation_status": "idle",
    "student_id": None,
    "backend_student_id": None,
    "exam_language": None,
    "attempt_id": None,
    "staircase_db_path": None,
    "chunk_sampler": None,
    "runtime_readiness": None,
    "final_backend_state": None,
    "current_adaptive_difficulty": None,
}


def fresh_state_value(value):
    return value.copy() if isinstance(value, (dict, list)) else value


def initialize_exam_state():
    for key, value in EXAM_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = fresh_state_value(value)


def sync_adaptive_difficulty(backend_state):
    """Persist the backend staircase level independently of question scoring."""
    difficulty = backend_state.get("current_difficulty") if backend_state else None
    if isinstance(difficulty, bool) or not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
        raise ValueError("Backend returned an invalid adaptive difficulty.")
    st.session_state.current_adaptive_difficulty = difficulty
    return difficulty


def valid_option_order(order, option_count):
    return isinstance(order, (list, tuple)) and sorted(order) == list(range(option_count))


def shuffled_option_order(option_count):
    """Return a non-identity permutation created only during attempt setup."""
    original_order = list(range(option_count))
    order = original_order.copy()
    random.SystemRandom().shuffle(order)
    if option_count > 1 and order == original_order:
        order = order[1:] + order[:1]
    return tuple(order)


def reset_exam(preserve_draft=True):
    """Clear one frontend attempt without deleting persisted backend rows."""
    previous_orders = dict(st.session_state.get("option_orders", {}))
    if previous_orders:
        st.session_state.last_attempt_option_orders = previous_orders
    previous_student = st.session_state.get("student_id") or st.session_state.get("student_id_input", "")
    previous_language = st.session_state.get("exam_language") or st.session_state.get("language_input", "en")
    for key, value in EXAM_STATE_DEFAULTS.items():
        st.session_state[key] = fresh_state_value(value)
    if preserve_draft:
        st.session_state.student_id_input = previous_student
        st.session_state.language_input = previous_language
    for key in list(st.session_state):
        if key.startswith("exam_answer_"):
            del st.session_state[key]


def option_order_for(question_id, option_count):
    """Read the immutable order created when this assessment attempt started."""
    saved_order = st.session_state.option_orders.get(question_id)
    if not valid_option_order(saved_order, option_count):
        raise RuntimeError("Assessment option order was not initialized correctly.")
    return saved_order


def register_question(delivery):
    """Store one backend question and freeze its display order for this attempt."""
    question_id = delivery.question_id
    if question_id in st.session_state.questions:
        return question_id

    option_order = shuffled_option_order(len(delivery.question.options))
    previous_order = st.session_state.get("last_attempt_option_orders", {}).get(question_id)
    while len(option_order) > 1 and option_order == previous_order:
        option_order = shuffled_option_order(len(delivery.question.options))

    st.session_state.questions[question_id] = delivery.question
    st.session_state.question_order.append(question_id)
    st.session_state.question_metadata[question_id] = {
        "source": delivery.source,
        "requested_difficulty": delivery.requested_difficulty,
        "topic": delivery.topic,
        "language": delivery.language,
        "questions_answered_before": delivery.questions_answered_before,
        "student_state_before": getattr(delivery, "student_state_before", None),
        "fallback_reason": delivery.fallback_reason,
    }
    st.session_state.option_orders[question_id] = option_order
    st.session_state.backend_answer_recorded[question_id] = False
    st.session_state.answer_save_status[question_id] = "not_started"
    st.session_state.current_question_id = question_id
    st.session_state.current_question = delivery.question
    st.session_state.current_question_index = len(st.session_state.question_order) - 1
    st.session_state.current_question_submitted = False
    st.session_state.selected_answer = None
    st.session_state.selected_original_index = None
    return question_id


def answer_progress_saved(question_id):
    return st.session_state.answer_save_status.get(question_id) == "saved"


def fetch_and_store_next_question():
    """Fetch exactly one adaptive question and normalize the resulting UI state."""
    current_question_id = st.session_state.current_question_id
    if (
        current_question_id is not None
        and st.session_state.current_question_submitted
        and not answer_progress_saved(current_question_id)
    ):
        st.session_state.generation_error = (
            "Save your current answer before requesting the next question."
        )
        return False

    language = st.session_state.exam_language
    readiness = inspect_runtime(language)
    st.session_state.runtime_readiness = readiness

    if readiness.live_ready and st.session_state.chunk_sampler is None:
        try:
            st.session_state.chunk_sampler = create_chunk_sampler(readiness)
        except Exception as exc:
            readiness = readiness.with_live_failure(
                f"Chunk sampler initialization: {type(exc).__module__}.{type(exc).__name__}"
            )
            st.session_state.runtime_readiness = readiness

    st.session_state.generation_status = "loading"
    try:
        result = fetch_next_question(
            student_id=st.session_state.backend_student_id,
            language=language,
            staircase_db_path=st.session_state.staircase_db_path,
            chunk_sampler=st.session_state.chunk_sampler,
            readiness=readiness,
            sequence_number=len(st.session_state.question_order) + 1,
        )
    except Exception as exc:
        # This is the UI's final operational boundary. The student receives a
        # safe retry state; the exception type is retained for a debug expander.
        st.session_state.generation_status = "error"
        st.session_state.generation_error = (
            "We could not prepare the next question. Please retry in a moment."
        )
        st.session_state.generation_debug = (
            f"Unexpected provider failure: {type(exc).__module__}.{type(exc).__name__}"
        )
        return False

    if result.status == "question":
        register_question(result.delivery)
        st.session_state.generation_status = "ready"
        st.session_state.generation_error = None
        st.session_state.generation_debug = result.technical_detail
        return True
    if result.status == "complete":
        st.session_state.exam_complete = True
        st.session_state.generation_status = "complete"
        st.session_state.generation_error = None
        st.session_state.final_backend_state = read_student_state(
            staircase_db_path=st.session_state.staircase_db_path,
            student_id=st.session_state.backend_student_id,
        )
        sync_adaptive_difficulty(st.session_state.final_backend_state)
        return True

    st.session_state.generation_status = "error"
    st.session_state.generation_error = result.message
    st.session_state.generation_debug = result.technical_detail
    return False


def start_assessment(student_id, language):
    """Create a fresh, isolated backend attempt and fetch its first question."""
    # The setup form's widget keys already exist in this Streamlit run, so do
    # not assign them here; their submitted values remain available naturally.
    reset_exam(preserve_draft=False)
    visible_id, backend_id = new_attempt_identity(student_id)
    staircase_db_path = default_staircase_db_path()
    state = initialize_student(
        staircase_db_path=staircase_db_path,
        backend_student_id=backend_id,
        language=language,
    )

    st.session_state.student_id = visible_id
    st.session_state.backend_student_id = backend_id
    st.session_state.attempt_id = backend_id.rsplit("::", 1)[-1]
    st.session_state.exam_language = language
    st.session_state.staircase_db_path = staircase_db_path
    st.session_state.exam_started = True
    st.session_state.final_backend_state = state
    sync_adaptive_difficulty(state)

    with st.spinner("Grounding your first question in the textbook…"):
        fetch_and_store_next_question()


def current_response(question_id):
    return next(
        (answer for answer in st.session_state.answers if answer["question_id"] == question_id),
        None,
    )


def append_response_once(response):
    """Keep the C3 frontend log idempotent across save retries and reruns."""
    if current_response(response["question_id"]) is not None:
        return False
    st.session_state.answers.append(response)
    return True


def answer_pre_state(question_id):
    """Freeze the exact state this question was generated against."""
    saved_state = st.session_state.answer_pre_states.get(question_id)
    if saved_state is not None:
        return saved_state

    metadata = st.session_state.question_metadata[question_id]
    pre_state = metadata.get("student_state_before")
    if pre_state is None:
        # Backward-compatible reconstruction for questions already loaded in a
        # Streamlit session before state snapshots were added. Staircase
        # advances topic and question counters together, once per answer.
        answered_before = metadata["questions_answered_before"]
        current_index = st.session_state.question_order.index(question_id)
        pre_state = {
            "current_difficulty": metadata["requested_difficulty"],
            "topic_index": answered_before,
            "questions_answered": answered_before,
            "correct_count": sum(
                1
                for response in st.session_state.answers
                if response["question_index"] < current_index and response["correct"]
            ),
        }
    st.session_state.answer_pre_states[question_id] = dict(pre_state)
    return st.session_state.answer_pre_states[question_id]


def apply_submission_result(question_id, result):
    """Apply one reconciled provider outcome to rerun-safe frontend state."""
    st.session_state.answer_save_status[question_id] = result.status
    st.session_state.answer_reconciliation_checked[question_id] = True
    if result.status == "saved":
        st.session_state.backend_answer_recorded[question_id] = True
        st.session_state.submission_errors.pop(question_id, None)
        st.session_state.generation_error = None
        st.session_state.final_backend_state = result.state
        sync_adaptive_difficulty(result.state)
    else:
        st.session_state.backend_answer_recorded[question_id] = False
        st.session_state.submission_errors[question_id] = {
            "message": result.message,
            "technical_detail": result.technical_detail,
        }
    return result


def reconcile_current_answer(question_id, correct):
    """Read persisted counters only; never repeat the non-idempotent write."""
    result = reconcile_answer_state(
        student_id=st.session_state.backend_student_id,
        correct=correct,
        staircase_db_path=st.session_state.staircase_db_path,
        expected_pre_state=answer_pre_state(question_id),
    )
    st.session_state.answer_reconciliation_checked[question_id] = True
    return apply_submission_result(question_id, result)


def record_current_answer(question_id, correct):
    if st.session_state.answer_save_status.get(question_id) == "saved":
        return None

    st.session_state.answer_save_status[question_id] = "saving"
    try:
        result = submit_answer_once(
            student_id=st.session_state.backend_student_id,
            correct=correct,
            staircase_db_path=st.session_state.staircase_db_path,
            expected_pre_state=answer_pre_state(question_id),
            already_recorded=st.session_state.backend_answer_recorded.get(question_id, False),
        )
    except Exception:
        # Once the provider is invoked, an unexpected exception has an
        # ambiguous write outcome. Never expose a write retry in this state.
        st.session_state.answer_save_status[question_id] = "ambiguous"
        st.session_state.answer_reconciliation_checked[question_id] = False
        st.session_state.backend_answer_recorded[question_id] = False
        raise

    return apply_submission_result(question_id, result)


def markdown_text(value):
    """Escape Markdown metacharacters in untrusted generated option text."""
    text = str(value)
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "#", "+", "-", ".", "!", "|"):
        text = text.replace(character, f"\\{character}")
    return text


initialize_exam_state()

# Preserve the correct level when an existing Streamlit session first reruns
# after this frontend field was introduced.
if (
    st.session_state.current_adaptive_difficulty is None
    and st.session_state.final_backend_state
):
    sync_adaptive_difficulty(st.session_state.final_backend_state)

if "student_id_input" not in st.session_state:
    st.session_state.student_id_input = ""
if "language_input" not in st.session_state:
    st.session_state.language_input = "en"
if "last_attempt_option_orders" not in st.session_state:
    st.session_state.last_attempt_option_orders = {}


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
        '<p>Adaptive question delivery.<br>Verified local fallback.</p></div>'
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
    if not st.session_state.exam_started:
        selected_language = st.session_state.language_input
        readiness = inspect_runtime(selected_language)
        st.markdown(
            '<section class="start-panel"><div class="eyebrow">YOUR ASSESSMENT</div>'
            '<h2>Python Fundamentals</h2>'
            '<p>A focused adaptive assessment grounded in your course textbook. '
            'Your language track stays fixed for the entire attempt.</p></section>',
            unsafe_allow_html=True,
        )

        with st.form("assessment_setup", border=True):
            st.text_input(
                "Student identifier",
                key="student_id_input",
                placeholder="Enter your student ID",
                max_chars=80,
                help="Used only to identify this assessment session.",
            )
            st.radio(
                "Assessment language",
                options=("en", "ar"),
                format_func=lambda code: LANGUAGE_LABELS[code],
                horizontal=True,
                key="language_input",
                help="The selected textbook track cannot change after the assessment starts.",
            )

            # Recompute after the radio widget has populated session state.
            readiness = inspect_runtime(st.session_state.language_input)
            status_class = "ready" if readiness.live_ready else "fallback"
            st.markdown(
                f'<div class="runtime-status {status_class}"><span></span><div>'
                f'<strong>{escape(readiness.mode_label)}</strong>'
                f'<small>{escape(readiness.student_message)}</small></div></div>',
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button(
                "Start Assessment →", type="primary", use_container_width=True
            )

        if not readiness.live_ready:
            with st.expander("Assessment availability", expanded=False):
                st.caption(
                    "Live generation is not currently available. The assessment can "
                    "continue using the verified fallback question set."
                )

        if st.session_state.get("start_error"):
            st.markdown(
                '<div class="operational-card error"><strong>Check your assessment details</strong>'
                f'<span>{escape(st.session_state.start_error)}</span></div>',
                unsafe_allow_html=True,
            )

        if submitted:
            student_id = st.session_state.student_id_input.strip()
            language = st.session_state.language_input
            if not student_id:
                st.session_state.start_error = "Enter a student identifier to begin."
                st.rerun()
            try:
                st.session_state.start_error = None
                start_assessment(student_id, language)
            except ValueError as exc:
                st.session_state.start_error = str(exc)
            except Exception as exc:
                st.session_state.start_error = (
                    "The assessment could not be initialized. Please check the local setup and retry."
                )
                st.session_state.generation_debug = (
                    f"Assessment initialization: {type(exc).__module__}.{type(exc).__name__}"
                )
            st.rerun()

    elif st.session_state.exam_complete:
        exam_language = st.session_state.exam_language or "en"
        completion_direction = "rtl" if exam_language == "ar" else "ltr"
        correct_count = sum(answer["correct"] for answer in st.session_state.answers)
        question_count = len(st.session_state.answers)
        accuracy = round(correct_count / question_count * 100) if question_count else 0
        final_level = (st.session_state.final_backend_state or {}).get("current_difficulty")
        level_copy = (
            f' · {ui_text("final_level", exam_language)} {final_level}/5'
            if final_level is not None else ""
        )
        completion_summary = ui_text(
            "completion_summary",
            exam_language,
            accuracy=accuracy,
            level=level_copy,
        )
        st.markdown(
            f'<section class="completion-panel" dir="{completion_direction}">'
            f'<div class="eyebrow">{escape(ui_text("assessment_complete", exam_language))}</div>'
            f'<h2>{escape(ui_text("assessment_complete", exam_language))}</h2>'
            f'<div class="completion-score"><strong>{correct_count}</strong><span> / {question_count}</span></div>'
            f'<p>{escape(completion_summary)}</p></section>',
            unsafe_allow_html=True,
        )
        results, restart = st.columns([1.4, 1])
        with results:
            if st.button(
                ui_text("view_results", exam_language),
                type="primary",
                use_container_width=True,
            ):
                navigate("Results")
                st.rerun()
        with restart:
            if st.button(ui_text("start_new_attempt", exam_language), use_container_width=True):
                reset_exam(preserve_draft=True)
                st.rerun()

    else:
        question_id = st.session_state.current_question_id
        if question_id is None:
            st.markdown(
                '<section class="operational-card error"><strong>Question unavailable</strong>'
                f'<span>{escape(st.session_state.generation_error or "We could not prepare your first question.")}</span>'
                '<small>Your assessment state is safe. Retry when ready.</small></section>',
                unsafe_allow_html=True,
            )
            if st.button("Retry Question →", type="primary", use_container_width=True):
                with st.spinner("Preparing your question…"):
                    fetch_and_store_next_question()
                st.rerun()
            if st.session_state.generation_debug:
                with st.expander("Developer details", expanded=False):
                    st.code(st.session_state.generation_debug, language=None)
            st.stop()

        # Reconcile an interrupted or legacy save without invoking
        # record_answer again. This safely recovers an answer committed before
        # a frontend cleanup exception.
        if (
            st.session_state.current_question_submitted
            and st.session_state.answer_save_status.get(question_id)
            in {"failed", "saving", "ambiguous"}
            and not st.session_state.answer_reconciliation_checked.get(question_id, False)
        ):
            response = current_response(question_id)
            if response is not None:
                reconcile_current_answer(question_id, response["correct"])
                st.rerun()

        question_index = st.session_state.current_question_index
        question = st.session_state.questions[question_id]
        metadata = st.session_state.question_metadata[question_id]
        option_order = option_order_for(question_id, len(question.options))
        displayed_options = [question.options[original_index] for original_index in option_order]
        question_count = curriculum_size()
        progress = min((question_index + 1) / question_count, 1.0) if question_count else 0.0
        progress_percent = round(progress * 100)
        header, restart = st.columns([4, 1.25], vertical_alignment="center")
        with header:
            difficulty_label = st.session_state.current_adaptive_difficulty
            exam_language = metadata["language"]
            header_direction = "rtl" if exam_language == "ar" else "ltr"
            st.markdown(
                f'<div class="exam-top" dir="{header_direction}"><div>'
                f'<span class="eyebrow">{escape(ui_text("your_assessment", exam_language))}</span>'
                f'<h2>{escape(ui_text("question", exam_language))} '
                f'<b>{question_index + 1:02d}</b><span class="muted"> / {question_count:02d}</span></h2></div>'
                f'<span class="difficulty"><i></i> '
                f'{escape(ui_text("adaptive_level", exam_language))} · {difficulty_label}/5</span></div>',
                unsafe_allow_html=True,
            )
        with restart:
            if st.button(
                ui_text("restart_assessment", exam_language),
                use_container_width=True,
            ):
                reset_exam(preserve_draft=True)
                st.rerun()

        progress_text = (
            f"Python Fundamentals · السؤال {question_index + 1} من {question_count} · "
            f"اكتمل {progress_percent}%"
            if exam_language == "ar"
            else f"Python Fundamentals · Question {question_index + 1} of {question_count} · {progress_percent}% complete"
        )
        st.progress(
            progress,
            text=progress_text,
        )
        with st.container(border=True, key="question_card"):
            language = LANGUAGE_LABELS[metadata["language"]]
            fallback_badge = (
                f'<span class="fallback-pill">{escape(ui_text("fallback_question", exam_language))}</span>'
                if metadata["source"] == "backup" else ""
            )
            direction = "rtl" if metadata["language"] == "ar" else "ltr"
            if direction == "rtl":
                st.markdown(
                    '<style>.st-key-question_card [data-testid="stRadio"] label p {'
                    'direction:rtl;unicode-bidi:plaintext;text-align:right;width:100%;}'
                    '.st-key-question_card [data-testid="stRadio"] label p strong {'
                    'direction:ltr;unicode-bidi:isolate;flex:0 0 auto;}</style>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                '<div class="badges"><span>PYTHON FUNDAMENTALS</span>'
                f'<span>{escape(question.topic.upper())}</span><span>{language.upper()}</span>{fallback_badge}</div>'
                f'<h3 class="question-text mixed-content" dir="{direction}">'
                f'{mixed_content_html(question.question, exam_language)}</h3>'
                f'<p class="question-hint" dir="{direction}">'
                f'{escape(ui_text("select_answer", exam_language))}</p>',
                unsafe_allow_html=True,
            )
            submitted_response = current_response(question_id) if st.session_state.current_question_submitted else None
            persisted_answer = (
                submitted_response.get(
                    "displayed_selected_index",
                    option_order.index(submitted_response["selected_option_index"]),
                )
                if submitted_response is not None
                else (
                    option_order.index(st.session_state.selected_original_index)
                    if st.session_state.selected_original_index is not None
                    else st.session_state.selected_answer
                )
            )
            selected_answer = st.radio(
                ui_text("choose_answer", exam_language),
                range(len(question.options)),
                index=persisted_answer,
                format_func=lambda index: (
                    f"**{chr(65 + index)}**　 "
                    f"{mixed_content_markdown(displayed_options[index].text, exam_language)}"
                ),
                label_visibility="collapsed",
                key=f"exam_answer_{question_id}",
                disabled=st.session_state.current_question_submitted,
            )
            st.session_state.selected_answer = selected_answer
            st.session_state.selected_original_index = (
                option_order[selected_answer] if selected_answer is not None else None
            )

            if st.session_state.current_question_submitted:
                correct_original_index = submitted_response.get(
                    "correct_original_index", submitted_response["correct_option_index"]
                )
                correct_displayed_index = submitted_response.get(
                    "correct_displayed_index", option_order.index(correct_original_index)
                )
                correct_text = mixed_content_html(
                    submitted_response.get(
                        "correct_answer", question.options[correct_original_index].text
                    ),
                    exam_language,
                )
                if submitted_response["correct"]:
                    st.markdown(
                        f'<div class="answer-feedback correct" dir="{direction}">'
                        f'<strong>{escape(ui_text("correct", exam_language))}</strong>'
                        f'<span><bdi dir="ltr">{chr(65 + correct_displayed_index)}.</bdi> '
                        f'{correct_text}</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    misconception = submitted_response.get("misconception")
                    misconception_copy = (
                        f'<small>{escape(ui_text("learning_signal", exam_language))}: '
                        f'{mixed_content_html(misconception, exam_language)}</small>'
                        if misconception else ""
                    )
                    st.markdown(
                        f'<div class="answer-feedback incorrect" dir="{direction}">'
                        f'<strong>{escape(ui_text("incorrect", exam_language))}</strong>'
                        f'<span>{escape(ui_text("correct_answer", exam_language))}: '
                        f'<bdi dir="ltr">{chr(65 + correct_displayed_index)}.</bdi> '
                        f'{correct_text}</span>{misconception_copy}</div>',
                        unsafe_allow_html=True,
                    )

            submission_error = st.session_state.submission_errors.get(question_id)
            if submission_error:
                error_title = (
                    "Progress synchronization required"
                    if st.session_state.answer_save_status.get(question_id) == "ambiguous"
                    else "Progress not saved"
                )
                st.markdown(
                    f'<div class="operational-card error compact"><strong>{error_title}</strong>'
                    f'<span>{escape(submission_error["message"])}</span></div>',
                    unsafe_allow_html=True,
                )
                if submission_error.get("technical_detail"):
                    with st.expander("Developer details", expanded=False):
                        st.code(submission_error["technical_detail"], language=None)

            if st.session_state.generation_error and st.session_state.backend_answer_recorded.get(question_id):
                st.markdown(
                    '<div class="operational-card error compact"><strong>Next question unavailable</strong>'
                    f'<span>{escape(st.session_state.generation_error)}</span></div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="control-divider"></div>', unsafe_allow_html=True)
            status, action = st.columns([2, 1.3], vertical_alignment="center")
            with status:
                source_copy = ui_text(
                    "verified_fallback" if metadata["source"] == "backup" else "textbook_grounded",
                    exam_language,
                )
                st.markdown(
                    (
                        f'<div class="control-status" dir="{direction}">Question '
                        f'{question_index + 1} of {question_count} <span>·</span> '
                        f'{source_copy}</div>'
                    )
                    if exam_language == "en"
                    else
                    f'<div class="control-status" dir="{direction}">'
                    f'{escape(ui_text("question", exam_language))} {question_index + 1} / {question_count} '
                    f'<span>·</span> {source_copy}</div>',
                    unsafe_allow_html=True,
                )
            with action:
                if not st.session_state.current_question_submitted:
                    if st.button(
                        ui_text("submit_answer", exam_language),
                        type="primary",
                        disabled=selected_answer is None,
                        use_container_width=True,
                    ):
                        selected_original_index = st.session_state.selected_original_index
                        selected_option = question.options[selected_original_index]
                        correct_original_index = next(
                            i for i, option in enumerate(question.options) if option.correct
                        )
                        correct_displayed_index = option_order.index(correct_original_index)
                        correct_option = question.options[correct_original_index]
                        is_correct = bool(selected_option.correct)
                        append_response_once({
                            "question_id": question_id,
                            "question_index": question_index,
                            "question": question.question,
                            "topic": question.topic,
                            "language": metadata["language"],
                            "source_chunk_id": question.source_chunk_id,
                            "displayed_selected_index": selected_answer,
                            "selected_original_index": selected_original_index,
                            "selected_option_index": selected_original_index,
                            "correct_original_index": correct_original_index,
                            "correct_option_index": correct_original_index,
                            "correct_displayed_index": correct_displayed_index,
                            "selected_answer": selected_option.text,
                            "selected_answer_text": selected_option.text,
                            "correct_answer": correct_option.text,
                            "correct_answer_text": correct_option.text,
                            "option_order": list(option_order),
                            "correct": is_correct,
                            "misconception": None if is_correct else selected_option.misconception,
                            "difficulty_score": question.difficulty_score,
                            "requested_difficulty": metadata["requested_difficulty"],
                            "question_source": metadata["source"],
                            "fallback_reason": metadata["fallback_reason"],
                        })
                        st.session_state.current_question_submitted = True
                        try:
                            record_current_answer(question_id, is_correct)
                        except Exception as exc:
                            st.session_state.answer_save_status[question_id] = "ambiguous"
                            st.session_state.answer_reconciliation_checked[question_id] = False
                            st.session_state.backend_answer_recorded[question_id] = False
                            st.session_state.submission_errors[question_id] = {
                                "message": (
                                    "We could not safely confirm your adaptive progress. "
                                    "Please ask the assessment administrator to synchronize this attempt."
                                ),
                                "technical_detail": (
                                    f"Unexpected answer update: {type(exc).__module__}.{type(exc).__name__}"
                                ),
                            }
                        st.rerun()
                elif st.session_state.answer_save_status.get(question_id) == "definitely_failed":
                    if st.button("Retry Saving Answer →", type="primary", use_container_width=True):
                        response = current_response(question_id)
                        try:
                            record_current_answer(question_id, response["correct"])
                        except Exception as exc:
                            st.session_state.answer_save_status[question_id] = "ambiguous"
                            st.session_state.answer_reconciliation_checked[question_id] = False
                            st.session_state.backend_answer_recorded[question_id] = False
                            st.session_state.submission_errors[question_id] = {
                                "message": (
                                    "We could not safely confirm your adaptive progress. "
                                    "Please ask the assessment administrator to synchronize this attempt."
                                ),
                                "technical_detail": (
                                    f"Unexpected answer retry: {type(exc).__module__}.{type(exc).__name__}"
                                ),
                            }
                        st.rerun()
                elif answer_progress_saved(question_id):
                    is_final_topic = student_exam_complete(
                        staircase_db_path=st.session_state.staircase_db_path,
                        student_id=st.session_state.backend_student_id,
                    )
                    button_label = ui_text(
                        "finish_assessment" if is_final_topic else "next_question",
                        exam_language,
                    )
                    if not st.session_state.generation_error and st.button(
                        button_label, type="primary", use_container_width=True
                    ):
                        with st.spinner(
                            "Finalizing your assessment…" if is_final_topic
                            else "Preparing your next question…"
                        ):
                            fetch_and_store_next_question()
                        st.rerun()
                else:
                    st.button(
                        "Progress synchronization required",
                        disabled=True,
                        use_container_width=True,
                    )

            if st.session_state.generation_error and st.session_state.backend_answer_recorded.get(question_id):
                if st.button("Retry Next Question", use_container_width=True):
                    with st.spinner("Grounding your next question in the textbook…"):
                        fetch_and_store_next_question()
                    st.rerun()
                if st.session_state.generation_debug:
                    with st.expander("Developer details", expanded=False):
                        st.code(st.session_state.generation_debug, language=None)

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
        results_language = st.session_state.exam_language or responses[0].get("language", "en")
        results_direction = "rtl" if results_language == "ar" else "ltr"
        score = calculate_score(responses)
        topics = topic_performance(responses)
        misconceptions = misconception_counts(responses)
        strongest = strongest_topic(topics)
        weakest = weakest_topic(topics)
        accuracy_text = f'{score["accuracy"]:g}'

        heading(
            ui_text("assessment_complete", results_language),
            ui_text("results_subtitle", results_language),
            ui_text("real_session", results_language),
            direction=results_direction,
        )
        st.markdown(
            f'<section class="score-panel" dir="{results_direction}"><div class="score-ring" '
            f'style="background:conic-gradient(#FF3040 {score["accuracy"]}%,#292930 0)">'
            f'<div><strong>{accuracy_text}<span>%</span></strong>'
            f'<small>{escape(ui_text("accuracy", results_language).upper())}</small></div></div>'
            f'<div><div class="eyebrow">{escape(ui_text("completed_assessment", results_language))}</div>'
            f'<div class="score-number">{score["correct"]} <span>/ {score["total"]}</span></div>'
            f'<p>{escape(ui_text("results_calculated", results_language))}</p></div>'
            f'<span class="sample-pill">{escape(ui_text("current_session", results_language))}</span></section>',
            unsafe_allow_html=True,
        )
        metrics([
            (ui_text("score", results_language), f'{score["correct"]} / {score["total"]}', ui_text("correct_answers_attempted", results_language)),
            (ui_text("accuracy", results_language), f'{score["accuracy"]:g}%', ui_text("overall_performance", results_language)),
            (ui_text("correct", results_language), str(score["correct"]), ui_text("submitted_answers", results_language)),
            (ui_text("incorrect", results_language), str(score["incorrect"]), ui_text("submitted_answers", results_language)),
            (ui_text("average_difficulty", results_language), f'{score["average_difficulty"]:g} / 5', ui_text("across_answered", results_language)),
        ], direction=results_direction)

        topic_content = "".join(
            f'<div class="topic-performance-row" dir="{results_direction}">'
            f'<div><span dir="ltr">{escape(topic.title())}</span><strong>{values["accuracy"]:g}%</strong></div>'
            f'<small>{escape(ui_text("topic_statistics", results_language, attempted=values["attempted"], correct=values["correct"], incorrect=values["incorrect"], error_rate="{:g}".format(values["error_rate"])))}</small>'
            f'<div class="bar-track"><i style="width:{values["accuracy"]}%"></i></div></div>'
            for topic, values in topics.items()
        )
        if misconceptions:
            misconception_content = "".join(
                f'<div class="insight-row" dir="{results_direction}">'
                f'<span class="index">{index:02d}</span><div><strong>'
                f'{mixed_content_html(item["label"], results_language)}</strong>'
                f'<p>{escape(misconception_summary(item, results_language))}</p></div></div>'
                for index, item in enumerate(misconceptions, start=1)
            )
            misconception_subtitle = ui_text("misconceptions_subtitle", results_language)
        else:
            misconception_content = (
                f'<p class="body-copy" dir="{results_direction}">'
                f'{escape(ui_text("no_misconceptions", results_language))}</p>'
            )
            misconception_subtitle = ui_text("no_misconceptions_subtitle", results_language)

        left, right = st.columns([1.25, 1], gap="medium")
        with left:
            panel(ui_text("performance_by_topic", results_language), ui_text("performance_subtitle", results_language), topic_content, direction=results_direction)
            panel(ui_text("misconceptions", results_language), misconception_subtitle, misconception_content, direction=results_direction)
        with right:
            strongest_values = topics[strongest]
            panel(
                ui_text("strongest_topic", results_language),
                ui_text("highest_accuracy", results_language),
                f'<div class="topic-title" dir="ltr">{escape(strongest.title())}</div>'
                f'<p class="body-copy">{escape(ui_text("correct_of_attempted", results_language, correct=strongest_values["correct"], attempted=strongest_values["attempted"]))}</p>'
                f'<span class="tag">{escape(ui_text("accuracy_value", results_language, accuracy="{:g}".format(strongest_values["accuracy"])))}</span>',
                direction=results_direction,
            )
            weakest_values = topics[weakest]
            attention_copy = (
                ui_text("no_errors_tie", results_language)
                if weakest_values["incorrect"] == 0
                else ui_text(
                    "review_errors",
                    results_language,
                    incorrect=weakest_values["incorrect"],
                    attempted=weakest_values["attempted"],
                    error_rate=f'{weakest_values["error_rate"]:g}',
                )
            )
            panel(
                ui_text("needs_attention", results_language),
                ui_text("lowest_accuracy", results_language),
                f'<div class="topic-title" dir="ltr">{escape(weakest.title())}</div>'
                f'<p class="body-copy">{escape(attention_copy)}</p>'
                f'<span class="tag accent">{escape(ui_text("accuracy_value", results_language, accuracy="{:g}".format(weakest_values["accuracy"])))}</span>',
                direction=results_direction,
            )

        reviews = question_review(responses, st.session_state.questions)
        st.markdown(
            f'<div class="section-heading" dir="{results_direction}">'
            f'<h3>{escape(ui_text("question_review", results_language))}</h3>'
            f'<p>{escape(ui_text("question_review_subtitle", results_language))}</p></div>',
            unsafe_allow_html=True,
        )
        for review in reviews:
            status = ui_text("correct" if review["correct"] else "incorrect", results_language)
            review_question = st.session_state.questions.get(review["question_id"])
            review_language = (
                review_question.language.value
                if review_question is not None and hasattr(review_question.language, "value")
                else "en"
            )
            review_direction = "rtl" if review_language == "ar" else "ltr"
            difficulty = (
                f'{review["difficulty"]} / 5'
                if review["difficulty"] is not None
                else ui_text("not_available", results_language)
            )
            review_topic_label = review["topic"].title()
            if results_language == "ar":
                review_topic_label = f'\u2066{review_topic_label}\u2069'
            with st.expander(
                f'{ui_text("question", results_language)} {review["question_number"]:02d} · '
                f'{review_topic_label} · {status}'
            ):
                misconception_review = (
                    f'<div class="review-cell wide incorrect" dir="{review_direction}">'
                    f'<small>{escape(ui_text("misconception", results_language))}</small>'
                    f'<span>{mixed_content_html(review["misconception"], review_language)}</span></div>'
                    if review["misconception"]
                    else ""
                )
                st.markdown(
                    f'<p class="review-question mixed-content" dir="{review_direction}">{mixed_content_html(review["question"], review_language)}</p>'
                    f'<div class="review-grid" dir="{results_direction}">'
                    f'<div class="review-cell"><small>{escape(ui_text("topic", results_language))}</small><span dir="ltr">{escape(review["topic"].title())}</span></div>'
                    f'<div class="review-cell"><small>{escape(ui_text("difficulty", results_language))}</small><span>{escape(difficulty)}</span></div>'
                    f'<div class="review-cell {"correct" if review["correct"] else "incorrect"}">'
                    f'<small>{escape(ui_text("your_answer", results_language))} · {escape(status)}</small>'
                    f'<span dir="{review_direction}">{mixed_content_html(review["student_answer"], review_language)}</span></div>'
                    f'<div class="review-cell correct"><small>{escape(ui_text("correct_answer", results_language))}</small>'
                    f'<span dir="{review_direction}">{mixed_content_html(review["correct_answer"], review_language)}</span></div>{misconception_review}</div>',
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
        f'{compact_chart_label(row["label"])}<br>{row["students_affected"]}/{completed_count} students'
        for row in misconception_rows
    ]
    misconception_figure = bar_chart(
        misconception_labels,
        [row["occurrences"] for row in misconception_rows],
        horizontal=True,
        hover_labels=[row["label"] for row in misconception_rows],
        left_margin=205,
        height=292,
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
