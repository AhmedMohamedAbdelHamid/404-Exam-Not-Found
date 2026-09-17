"""Offline C5 contract tests using injected backend behavior only."""

from __future__ import annotations

import ast
from enum import Enum
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeLanguage(str, Enum):
    EN = "en"
    AR = "ar"


class FakeQuestion:
    def __init__(self, language="en", topic="algorithm", difficulty=3):
        self.question = f"Question about {topic}"
        self.topic = topic
        self.language = FakeLanguage(language)
        self.chunk_type = "definition"
        self.source_chunk_id = f"{language}_{topic.replace(' ', '_')}"
        self.options = [
            SimpleNamespace(text="Correct", correct=True, misconception=None),
            SimpleNamespace(text="Wrong A", correct=False, misconception="error A"),
            SimpleNamespace(text="Wrong B", correct=False, misconception="error B"),
            SimpleNamespace(text="Wrong C", correct=False, misconception="error C"),
        ]
        self.difficulty = SimpleNamespace(
            bloom_level=difficulty,
            bloom_justification="test",
            distractor_quality=difficulty,
            distractor_justification="test",
            concept_depth=difficulty,
            concept_depth_justification="test",
        )
        self.difficulty_score = difficulty
        self.validated = True
        self.regeneration_count = 0


class FakeStaircase:
    topics = ["algorithm", "functions"]
    stores = {}
    instances = []

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.state = self.stores.setdefault(db_path, {})
        self.closed = False
        self.instances.append(self)

    @classmethod
    def reset(cls):
        cls.stores = {}
        cls.instances = []

    def get_or_create_student(self, student_id, language="en"):
        return self.state.setdefault(
            student_id,
            {
                "student_id": student_id,
                "language": language,
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
        )

    def get_current_topic(self, student_id):
        state = self.get_or_create_student(student_id)
        index = state["topic_index"]
        return self.topics[index] if index < len(self.topics) else None

    def get_current_difficulty(self, student_id):
        return self.get_or_create_student(student_id)["current_difficulty"]

    def is_exam_complete(self, student_id):
        return self.get_current_topic(student_id) is None

    def close(self):
        self.closed = True


def install_backend_stubs():
    schema = ModuleType("schema")
    schema.QuestionOut = FakeQuestion
    sys.modules["schema"] = schema

    backup_pool = ModuleType("backup_pool")
    backup_pool.get_backup_question = lambda topic, language, difficulty=3: FakeQuestion(
        language, topic, difficulty
    )
    sys.modules["backup_pool"] = backup_pool

    generation_agent = ModuleType("generation_agent")
    generation_agent.call_llm = lambda messages, chunk, target_difficulty: "{}"
    sys.modules["generation_agent"] = generation_agent

    get_next = ModuleType("get_next_question")

    class GenerationUnavailable(Exception):
        pass

    get_next.GenerationUnavailable = GenerationUnavailable
    get_next.get_next_question = lambda **kwargs: FakeQuestion()
    get_next.record_answer = lambda student_id, correct, staircase=None: {}
    sys.modules["get_next_question"] = get_next

    llm_client = ModuleType("llm_client")

    class LLMCallError(Exception):
        pass

    llm_client.LLMCallError = LLMCallError
    llm_client.USE_REAL_LLM = False
    llm_client.critique_question_json = lambda messages: "{}"
    sys.modules["llm_client"] = llm_client

    staircase = ModuleType("staircase")
    staircase.Staircase = FakeStaircase
    staircase.TOPIC_ORDER = FakeStaircase.topics
    staircase.DB_PATH = "student_state.db"
    sys.modules["staircase"] = staircase
    return GenerationUnavailable


GenerationUnavailable = install_backend_stubs()
from frontend import question_provider as provider
from frontend.analytics import (
    calculate_score,
    misconception_counts,
    question_review,
    topic_performance,
)


class C5ProviderTests(unittest.TestCase):
    def setUp(self):
        FakeStaircase.reset()
        self.db_path = "mock-student-state.db"
        provider.initialize_student(
            staircase_db_path=self.db_path,
            backend_student_id="student::attempt::1",
            language="en",
            staircase_factory=FakeStaircase,
        )
        self.readiness = provider.RuntimeReadiness(True, True, "en")

    def pre_state(self):
        return {
            "current_difficulty": 3,
            "topic_index": 0,
            "questions_answered": 0,
            "correct_count": 0,
        }

    def test_live_question_arrives_with_frontend_id(self):
        calls = []

        def get_next_fn(**kwargs):
            calls.append(kwargs)
            topic = kwargs["staircase"].get_current_topic(kwargs["student_id"])
            return FakeQuestion("en", topic)

        result = provider.fetch_next_question(
            student_id="student::attempt::1",
            language="en",
            staircase_db_path=self.db_path,
            chunk_sampler=object(),
            readiness=self.readiness,
            sequence_number=1,
            get_next_fn=get_next_fn,
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "question")
        self.assertEqual(result.delivery.question_id, "q001")
        self.assertEqual(result.delivery.source, "live")
        self.assertEqual(len(calls), 1)

    def test_answer_is_recorded_exactly_once_and_adapts_before_next_fetch(self):
        calls = []

        def record_fn(student_id, correct, staircase=None):
            calls.append((student_id, correct))
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] = min(5, state["current_difficulty"] + 1)
            state["topic_index"] += 1
            state["questions_answered"] += 1
            state["correct_count"] += 1
            return dict(state)

        first = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state=dict(FakeStaircase.stores[self.db_path]["student::attempt::1"]),
            already_recorded=False,
            record_fn=record_fn,
            staircase_factory=FakeStaircase,
        )
        second = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state={
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
            already_recorded=True,
            record_fn=record_fn,
            staircase_factory=FakeStaircase,
        )
        self.assertTrue(first.success and second.success)
        self.assertEqual(len(calls), 1)
        final_reader = FakeStaircase(self.db_path)
        self.assertEqual(final_reader.get_current_topic("student::attempt::1"), "functions")
        self.assertEqual(final_reader.get_current_difficulty("student::attempt::1"), 4)
        final_reader.close()
        self.assertTrue(all(instance.closed for instance in FakeStaircase.instances))

    def test_post_commit_exception_reconciles_as_saved_and_never_retries(self):
        calls = []
        pre_state = {
            "current_difficulty": 3,
            "topic_index": 2,
            "questions_answered": 2,
            "correct_count": 1,
        }
        FakeStaircase.stores[self.db_path]["student::attempt::1"].update(pre_state)

        def persist_then_raise(student_id, correct, staircase=None):
            calls.append((student_id, correct))
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] = 2
            state["topic_index"] = 3
            state["questions_answered"] = 3
            raise sqlite3.ProgrammingError("simulated exception after commit")

        reconciled = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=False,
            staircase_db_path=self.db_path,
            expected_pre_state=pre_state,
            already_recorded=False,
            record_fn=persist_then_raise,
            staircase_factory=FakeStaircase,
        )
        rerun = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=False,
            staircase_db_path=self.db_path,
            expected_pre_state=pre_state,
            already_recorded=True,
            record_fn=persist_then_raise,
            staircase_factory=FakeStaircase,
        )

        self.assertTrue(reconciled.success and rerun.success)
        self.assertEqual(reconciled.status, "saved")
        self.assertTrue(reconciled.already_recorded)
        self.assertEqual(reconciled.state["current_difficulty"], 2)
        self.assertEqual(len(calls), 1)

    def test_cleanup_exception_cannot_override_confirmed_backend_return(self):
        class CleanupFailingStaircase(FakeStaircase):
            def close(self):
                self.closed = True
                raise sqlite3.ProgrammingError("simulated cleanup failure")

        def record_fn(student_id, correct, staircase=None):
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] = 4
            state["topic_index"] = 1
            state["questions_answered"] = 1
            state["correct_count"] = 1
            return dict(state)

        result = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state=self.pre_state(),
            already_recorded=False,
            record_fn=record_fn,
            staircase_factory=CleanupFailingStaircase,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, "saved")

    def test_unexpected_persisted_state_is_ambiguous_and_blocks_retry(self):
        calls = []

        def mutate_unexpectedly(student_id, correct, staircase=None):
            calls.append((student_id, correct))
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] = 1
            state["topic_index"] = 2
            state["questions_answered"] = 2
            raise sqlite3.ProgrammingError("simulated uncertain write")

        result = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=False,
            staircase_db_path=self.db_path,
            expected_pre_state=self.pre_state(),
            already_recorded=False,
            record_fn=mutate_unexpectedly,
            staircase_factory=FakeStaircase,
        )
        rerun = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=False,
            staircase_db_path=self.db_path,
            expected_pre_state=self.pre_state(),
            already_recorded=False,
            record_fn=mutate_unexpectedly,
            staircase_factory=FakeStaircase,
        )

        self.assertFalse(result.success or rerun.success)
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(rerun.status, "ambiguous")
        self.assertEqual(len(calls), 1)

    def test_completion_is_driven_by_backend_none(self):
        result = provider.fetch_next_question(
            student_id="student::attempt::1",
            language="en",
            staircase_db_path=self.db_path,
            chunk_sampler=object(),
            readiness=self.readiness,
            sequence_number=3,
            get_next_fn=lambda **kwargs: None,
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "complete")

    def test_generation_unavailable_uses_backup(self):
        def unavailable(**kwargs):
            raise GenerationUnavailable("test")

        result = provider.fetch_next_question(
            student_id="student::attempt::1",
            language="en",
            staircase_db_path=self.db_path,
            chunk_sampler=object(),
            readiness=self.readiness,
            sequence_number=1,
            get_next_fn=unavailable,
            backup_fn=lambda topic, language, difficulty: FakeQuestion(language, topic, difficulty),
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "question")
        self.assertEqual(result.delivery.source, "backup")

    def test_failed_live_and_backup_produces_retry_state(self):
        def unavailable(**kwargs):
            raise GenerationUnavailable("test")

        result = provider.fetch_next_question(
            student_id="student::attempt::1",
            language="en",
            staircase_db_path=self.db_path,
            chunk_sampler=object(),
            readiness=self.readiness,
            sequence_number=1,
            get_next_fn=unavailable,
            backup_fn=lambda topic, language, difficulty: None,
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "error")
        self.assertIn("retry", result.message.lower())

    def test_language_mismatch_is_rejected_without_fallback(self):
        backup_calls = []
        result = provider.fetch_next_question(
            student_id="student::attempt::1",
            language="en",
            staircase_db_path=self.db_path,
            chunk_sampler=object(),
            readiness=self.readiness,
            sequence_number=1,
            get_next_fn=lambda **kwargs: FakeQuestion("ar"),
            backup_fn=lambda *args: backup_calls.append(args),
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "error")
        self.assertFalse(backup_calls)

    def test_arabic_fallback_keeps_the_locked_track(self):
        provider.initialize_student(
            staircase_db_path=self.db_path,
            backend_student_id="arabic::attempt::1",
            language="ar",
            staircase_factory=FakeStaircase,
        )
        result = provider.fetch_next_question(
            student_id="arabic::attempt::1",
            language="ar",
            staircase_db_path=self.db_path,
            chunk_sampler=None,
            readiness=provider.RuntimeReadiness(False, True, "ar", ("test",)),
            sequence_number=1,
            backup_fn=lambda topic, language, difficulty: FakeQuestion(language, topic, difficulty),
            staircase_factory=FakeStaircase,
        )
        self.assertEqual(result.status, "question")
        self.assertEqual(result.delivery.language, "ar")
        self.assertEqual(result.delivery.question.language.value, "ar")

    def test_failed_save_retries_once_without_double_update(self):
        calls = []

        def flaky_record(student_id, correct, staircase=None):
            calls.append((student_id, correct))
            if len(calls) == 1:
                raise sqlite3.OperationalError("simulated write interruption")
            state = staircase.get_or_create_student(student_id)
            state["current_difficulty"] += 1
            state["topic_index"] += 1
            state["questions_answered"] += 1
            state["correct_count"] += 1
            return dict(state)

        failed = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state={
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
            already_recorded=False,
            record_fn=flaky_record,
            staircase_factory=FakeStaircase,
        )
        retried = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state={
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
            already_recorded=False,
            record_fn=flaky_record,
            staircase_factory=FakeStaircase,
        )
        rerun = provider.submit_answer_once(
            student_id="student::attempt::1",
            correct=True,
            staircase_db_path=self.db_path,
            expected_pre_state={
                "current_difficulty": 3,
                "topic_index": 0,
                "questions_answered": 0,
                "correct_count": 0,
            },
            already_recorded=True,
            record_fn=flaky_record,
            staircase_factory=FakeStaircase,
        )
        self.assertFalse(failed.success)
        self.assertEqual(failed.status, "definitely_failed")
        self.assertTrue(retried.success and rerun.success)
        self.assertEqual(len(calls), 2)
        persisted = FakeStaircase.stores[self.db_path]["student::attempt::1"]
        self.assertEqual(persisted["questions_answered"], 1)
        self.assertEqual(persisted["correct_count"], 1)

    def test_real_sqlite_requires_thread_local_staircase_instances(self):
        difficulty_stub = ModuleType("difficulty_scorer")
        difficulty_stub.MIN_DIFFICULTY = 1
        difficulty_stub.MAX_DIFFICULTY = 5
        previous = sys.modules.get("difficulty_scorer")
        sys.modules["difficulty_scorer"] = difficulty_stub
        try:
            spec = importlib.util.spec_from_file_location(
                "real_staircase_for_c5_test", ROOT / "staircase.py"
            )
            real_staircase = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(real_staircase)
        finally:
            if previous is None:
                sys.modules.pop("difficulty_scorer", None)
            else:
                sys.modules["difficulty_scorer"] = previous

        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "student_state.db")
            first = real_staircase.Staircase(database)
            first.get_or_create_student("same-key", language="en")

            thread_errors = []

            def reuse_wrong_thread():
                try:
                    first.get_current_difficulty("same-key")
                except Exception as exc:
                    thread_errors.append(exc)

            thread = threading.Thread(target=reuse_wrong_thread)
            thread.start()
            thread.join()
            self.assertEqual(len(thread_errors), 1)
            self.assertIsInstance(thread_errors[0], sqlite3.ProgrammingError)
            self.assertIn("same thread", str(thread_errors[0]).lower())
            first.close()

            writer = real_staircase.Staircase(database)
            writer.record_answer("same-key", True)
            writer.close()
            reader = real_staircase.Staircase(database)
            state = reader.get_or_create_student("same-key")
            reader.close()
            self.assertEqual(state["questions_answered"], 1)
            self.assertEqual(state["current_difficulty"], 4)


class C3C4RegressionTests(unittest.TestCase):
    def test_language_copy_and_mixed_direction_rendering_are_safe(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected_nodes = []
        selected_names = {
            "UI_COPY",
            "_LTR_RUN",
            "_CODE_MARKER",
            "ui_text",
            "mixed_content_html",
            "mixed_content_markdown",
            "markdown_text",
        }
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in selected_names
                for target in node.targets
            ):
                selected_nodes.append(node)
            if isinstance(node, ast.FunctionDef) and node.name in selected_names:
                selected_nodes.append(node)

        namespace = {"re": __import__("re"), "escape": __import__("html").escape}
        exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), "app.py", "exec"), namespace)

        ui_text = namespace["ui_text"]
        mixed_html = namespace["mixed_content_html"]
        mixed_markdown = namespace["mixed_content_markdown"]

        # Existing English copy remains byte-for-byte unchanged.
        self.assertEqual(ui_text("select_answer", "en"), "Select the one best answer.")
        self.assertEqual(ui_text("submit_answer", "en"), "Submit Answer →")
        self.assertEqual(ui_text("question_review", "en"), "Question Review")
        self.assertEqual(ui_text("score", "en"), "Score")
        self.assertEqual(ui_text("performance_by_topic", "en"), "Performance by Topic")

        self.assertEqual(ui_text("select_answer", "ar"), "اختر الإجابة الصحيحة.")
        self.assertEqual(ui_text("submit_answer", "ar"), "إرسال الإجابة")
        self.assertEqual(ui_text("question_review", "ar"), "مراجعة الأسئلة")
        self.assertEqual(ui_text("score", "ar"), "النتيجة")
        self.assertEqual(ui_text("average_difficulty", "ar"), "متوسط الصعوبة")

        original = "ماذا تطبع الشيفرة التالية؟ x = 5\nprint(x) <script>alert(1)</script>"
        rendered = mixed_html(original, "ar")
        self.assertEqual(
            original,
            "ماذا تطبع الشيفرة التالية؟ x = 5\nprint(x) <script>alert(1)</script>",
        )
        self.assertIn('dir="ltr"', rendered)
        self.assertIn('class="code-fragment"', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("\u2066", mixed_markdown(original, "ar"))
        self.assertIn("\u2069", mixed_markdown(original, "ar"))
        self.assertEqual(mixed_html("print(x)", "en"), "print(x)")

    def test_runtime_readiness_wording_is_configuration_accurate(self):
        readiness = provider.RuntimeReadiness(True, True, "en")
        self.assertEqual(readiness.mode_label, "Live pipeline configured")
        self.assertNotIn("quota", readiness.student_message.lower())
        self.assertNotIn("ready", readiness.mode_label.lower())

    def test_adaptive_level_tracks_backend_state_not_question_difficulty(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected_nodes = []
        selected_names = {
            "EXAM_STATE_DEFAULTS",
            "fresh_state_value",
            "initialize_exam_state",
            "sync_adaptive_difficulty",
            "shuffled_option_order",
            "register_question",
            "answer_pre_state",
            "apply_submission_result",
            "record_current_answer",
        }
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in selected_names
                for target in node.targets
            ):
                selected_nodes.append(node)
            if isinstance(node, ast.FunctionDef) and node.name in selected_names:
                selected_nodes.append(node)

        class SessionState(dict):
            __getattr__ = dict.__getitem__
            __setattr__ = dict.__setitem__

        state = SessionState()
        returned_difficulties = iter((4, 3))

        def submit_answer_once(**kwargs):
            difficulty = next(returned_difficulties)
            pre_state = kwargs["expected_pre_state"]
            return SimpleNamespace(
                success=True,
                status="saved",
                state={
                    "current_difficulty": difficulty,
                    "topic_index": pre_state["topic_index"] + 1,
                    "questions_answered": pre_state["questions_answered"] + 1,
                    "correct_count": pre_state["correct_count"] + (1 if kwargs["correct"] else 0),
                },
            )

        namespace = {
            "random": random,
            "st": SimpleNamespace(session_state=state),
            "submit_answer_once": submit_answer_once,
        }
        exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), "app.py", "exec"), namespace)
        namespace["initialize_exam_state"]()

        # Assessment initialization reflects the backend's initial level.
        namespace["sync_adaptive_difficulty"]({"current_difficulty": 3})
        self.assertEqual(state.current_adaptive_difficulty, 3)

        state.backend_student_id = "student::attempt::1"
        state.staircase_db_path = "mock-student-state.db"
        first_delivery = SimpleNamespace(
            question_id="q001", question=FakeQuestion(difficulty=1), source="live",
            requested_difficulty=3, topic="algorithm", language="en",
            questions_answered_before=0, fallback_reason=None,
        )
        namespace["register_question"](first_delivery)
        self.assertEqual(state.current_adaptive_difficulty, 3)

        # A correct answer moves 3 -> 4 and remains stable on rerun.
        namespace["record_current_answer"]("q001", True)
        self.assertEqual(state.current_adaptive_difficulty, 4)
        namespace["initialize_exam_state"]()
        self.assertEqual(state.current_adaptive_difficulty, 4)

        # Neither a new question's score nor fallback delivery changes it.
        fallback_delivery = SimpleNamespace(
            question_id="q002", question=FakeQuestion(topic="functions", difficulty=2),
            source="backup", requested_difficulty=4, topic="functions", language="en",
            questions_answered_before=1, fallback_reason="test",
        )
        namespace["register_question"](fallback_delivery)
        self.assertEqual(state.current_adaptive_difficulty, 4)

        # The next backend answer result is the only source of the new level.
        namespace["record_current_answer"]("q002", False)
        self.assertEqual(state.current_adaptive_difficulty, 3)

        reconciled = SimpleNamespace(
            success=True,
            status="saved",
            state={
                "current_difficulty": 2,
                "topic_index": 3,
                "questions_answered": 3,
                "correct_count": 1,
            },
            message=None,
            technical_detail="answer update: sqlite3.ProgrammingError",
        )
        namespace["apply_submission_result"]("q002", reconciled)
        self.assertEqual(state.answer_save_status["q002"], "saved")
        self.assertTrue(state.backend_answer_recorded["q002"])
        self.assertEqual(state.current_adaptive_difficulty, 2)
        self.assertIn(
            "difficulty_label = st.session_state.current_adaptive_difficulty",
            source,
        )

    def test_option_shuffle_is_valid_and_can_be_frozen(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"valid_option_order", "shuffled_option_order"}
        ]
        namespace = {"random": random}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
        order = namespace["shuffled_option_order"](4)
        stored = {"q001": order}
        self.assertTrue(namespace["valid_option_order"](order, 4))
        self.assertNotEqual(order, (0, 1, 2, 3))
        self.assertIs(stored["q001"], order)
        question = FakeQuestion()
        displayed_incorrect_index = next(
            index for index, original_index in enumerate(order)
            if not question.options[original_index].correct
        )
        original_index = stored["q001"][displayed_incorrect_index]
        self.assertFalse(question.options[original_index].correct)
        self.assertTrue(question.options[original_index].misconception)

    def test_mixed_answer_results_remain_compatible(self):
        questions = {"q001": FakeQuestion(topic="algorithm"), "q002": FakeQuestion(topic="functions")}
        responses = [
            {
                "question_id": "q001", "question_index": 0, "topic": "algorithm",
                "selected_option_index": 0, "correct_option_index": 0,
                "selected_answer": "Correct", "correct_answer": "Correct",
                "correct": True, "misconception": None, "difficulty_score": 3,
            },
            {
                "question_id": "q002", "question_index": 1, "topic": "functions",
                "selected_option_index": 1, "correct_option_index": 0,
                "selected_answer": "Wrong A", "correct_answer": "Correct",
                "correct": False, "misconception": "error A", "difficulty_score": 4,
            },
        ]
        score = calculate_score(responses)
        self.assertEqual(score["correct"], 1)
        self.assertEqual(score["accuracy"], 50.0)
        self.assertEqual(topic_performance(responses)["functions"]["incorrect"], 1)
        self.assertEqual(misconception_counts(responses)[0]["label"], "error A")
        reviews = question_review(responses, questions)
        self.assertEqual(len(reviews), 2)
        self.assertEqual(reviews[1]["question"], "Question about functions")

    def test_restart_defaults_and_teacher_dashboard_remain_present(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected_nodes = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "EXAM_STATE_DEFAULTS"
                for target in node.targets
            ):
                selected_nodes.append(node)
            if isinstance(node, ast.FunctionDef) and node.name in {
                "fresh_state_value", "valid_option_order", "shuffled_option_order",
                "reset_exam", "register_question", "current_response",
                "append_response_once", "answer_progress_saved",
                "fetch_and_store_next_question",
            }:
                selected_nodes.append(node)

        class SessionState(dict):
            __getattr__ = dict.__getitem__
            __setattr__ = dict.__setitem__

        state = SessionState()
        namespace = {"random": random, "st": SimpleNamespace(session_state=state)}
        exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), "app.py", "exec"), namespace)
        for key, value in namespace["EXAM_STATE_DEFAULTS"].items():
            state[key] = namespace["fresh_state_value"](value)
        state["last_attempt_option_orders"] = {}
        delivery = SimpleNamespace(
            question_id="q001", question=FakeQuestion(), source="live",
            requested_difficulty=3, topic="algorithm", language="en",
            questions_answered_before=0, fallback_reason=None,
        )
        namespace["register_question"](delivery)
        self.assertEqual(state.question_order, ["q001"])
        self.assertIn("q001", state.option_orders)
        state.answers.append({"question_id": "q001"})
        state.backend_answer_recorded["q001"] = True
        state.answer_save_status["q001"] = "saved"
        state["exam_answer_q001"] = 2

        duplicate = {"question_id": "q001", "correct": False}
        for save_status in ("saving", "saved", "definitely_failed", "ambiguous"):
            state.answer_save_status["q001"] = save_status
            self.assertFalse(namespace["append_response_once"](duplicate))
        self.assertEqual(len(state.answers), 1)

        for blocked_status in ("not_started", "saving", "definitely_failed", "ambiguous"):
            state.answer_save_status["q001"] = blocked_status
            self.assertFalse(namespace["answer_progress_saved"]("q001"))
        state.answer_save_status["q001"] = "saved"
        self.assertTrue(namespace["answer_progress_saved"]("q001"))

        marker_sampler = object()
        state.chunk_sampler = marker_sampler
        state.current_question_submitted = True
        state.answer_save_status["q001"] = "ambiguous"
        self.assertFalse(namespace["fetch_and_store_next_question"]())
        self.assertIs(state.chunk_sampler, marker_sampler)
        self.assertIn("Save your current answer", state.generation_error)

        namespace["reset_exam"](preserve_draft=False)
        self.assertEqual(state.questions, {})
        self.assertEqual(state.answers, [])
        self.assertEqual(state.option_orders, {})
        self.assertEqual(state.backend_answer_recorded, {})
        self.assertEqual(state.answer_save_status, {})
        self.assertEqual(state.answer_pre_states, {})
        self.assertEqual(state.answer_reconciliation_checked, {})
        self.assertNotIn("exam_answer_q001", state)
        self.assertNotIn("staircase", namespace["EXAM_STATE_DEFAULTS"])
        self.assertIn("staircase_db_path", namespace["EXAM_STATE_DEFAULTS"])
        self.assertIn('class_analytics(DEMO_CLASS_SESSIONS)', source)


if __name__ == "__main__":
    unittest.main()
