"""Schema-compatible question fixtures for the frontend assessment."""

from schema import DifficultySubScores, LanguageEnum, QuestionOption, QuestionOut


QUESTION_FIXTURES: dict[str, QuestionOut] = {
    "q001": QuestionOut(
        question="Which operator assigns a value to a variable in Python?",
        topic="variables and assignment",
        language=LanguageEnum.EN,
        source_chunk_id="dummy_variables_001",
        options=[
            QuestionOption(text="=", correct=True),
            QuestionOption(
                text="==",
                correct=False,
                misconception="confuses equality comparison with assignment",
            ),
            QuestionOption(
                text="!=",
                correct=False,
                misconception="confuses inequality comparison with assignment",
            ),
            QuestionOption(
                text="+",
                correct=False,
                misconception="confuses addition with assignment",
            ),
        ],
        difficulty=DifficultySubScores(
            bloom_level=1,
            bloom_justification="Recalls the assignment operator.",
            distractor_quality=1,
            distractor_justification="Alternatives are other familiar operators.",
            concept_depth=1,
            concept_depth_justification="Tests a single concept: assignment.",
        ),
        difficulty_score=1,
    ),
    "q002": QuestionOut(
        question="Which expression checks whether x is equal to 10?",
        topic="comparison operators",
        language=LanguageEnum.EN,
        source_chunk_id="dummy_comparisons_001",
        options=[
            QuestionOption(text="x = 10", correct=False, misconception="uses assignment instead of equality comparison"),
            QuestionOption(text="x == 10", correct=True),
            QuestionOption(text="x != 10", correct=False, misconception="uses inequality instead of equality comparison"),
            QuestionOption(text="x >= 10", correct=False, misconception="checks a range rather than exact equality"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=2, bloom_justification="Distinguishes equality from related operators.",
            distractor_quality=2, distractor_justification="Distractors reflect common operator confusion.",
            concept_depth=2, concept_depth_justification="Tests interpretation of one comparison expression.",
        ),
        difficulty_score=2,
    ),
    "q003": QuestionOut(
        question="Which keyword adds an alternative branch to an if statement in Python?",
        topic="conditionals",
        language=LanguageEnum.EN,
        source_chunk_id="dummy_conditionals_001",
        options=[
            QuestionOption(text="then", correct=False, misconception="imports conditional syntax from another language"),
            QuestionOption(text="case", correct=False, misconception="confuses an if branch with pattern matching"),
            QuestionOption(text="else", correct=True),
            QuestionOption(text="otherwise", correct=False, misconception="uses plain-language wording instead of Python syntax"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=2, bloom_justification="Recognizes the syntax used to form a conditional branch.",
            distractor_quality=2, distractor_justification="Alternatives resemble syntax from other languages or pseudocode.",
            concept_depth=2, concept_depth_justification="Tests one structural element of a conditional.",
        ),
        difficulty_score=2,
    ),
    "q004": QuestionOut(
        question="What values are produced by range(1, 4) in a Python for loop?",
        topic="loops",
        language=LanguageEnum.EN,
        source_chunk_id="dummy_loops_001",
        options=[
            QuestionOption(text="0, 1, 2, 3", correct=False, misconception="assumes range starts at zero despite the explicit start value"),
            QuestionOption(text="1, 2, 3, 4", correct=False, misconception="treats the range stop value as inclusive"),
            QuestionOption(text="1, 2, 3", correct=True),
            QuestionOption(text="0, 1, 2, 3, 4", correct=False, misconception="ignores both the explicit start and exclusive stop boundary"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=3, bloom_justification="Applies range boundary rules to predict iteration values.",
            distractor_quality=4, distractor_justification="Distractors represent realistic start and stop boundary errors.",
            concept_depth=3, concept_depth_justification="Combines explicit start and exclusive stop behavior.",
        ),
        difficulty_score=3,
    ),
    "q005": QuestionOut(
        question="What does a Python function return when it reaches no return statement?",
        topic="functions",
        language=LanguageEnum.EN,
        source_chunk_id="dummy_functions_001",
        options=[
            QuestionOption(text="0", correct=False, misconception="assumes functions default to a numeric zero"),
            QuestionOption(text="An empty string", correct=False, misconception="assumes functions default to an empty text value"),
            QuestionOption(text="None", correct=True),
            QuestionOption(text="The function name", correct=False, misconception="confuses the function object with its return value"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=3, bloom_justification="Applies knowledge of implicit return behavior.",
            distractor_quality=3, distractor_justification="Alternatives reflect plausible default-value assumptions.",
            concept_depth=3, concept_depth_justification="Connects control flow completion with the resulting value.",
        ),
        difficulty_score=3,
    ),
}

# Retained for compatibility with code importing the original sample fixture.
DUMMY_QUESTION = QUESTION_FIXTURES["q001"]


def _demo_responses(selected_options):
    """Build a deterministic response log with the same shape as the C2 log."""
    responses = []
    for question_index, ((question_id, question), selected_index) in enumerate(
        zip(QUESTION_FIXTURES.items(), selected_options)
    ):
        correct_index = next(index for index, option in enumerate(question.options) if option.correct)
        is_correct = selected_index == correct_index
        responses.append({
            "question_id": question_id,
            "question_index": question_index,
            "topic": question.topic,
            "selected_option_index": selected_index,
            "correct_option_index": correct_index,
            "correct": is_correct,
            "misconception": None if is_correct else question.options[selected_index].misconception,
            "difficulty_score": question.difficulty_score,
        })
    return responses


# Frontend-only demo class data. These fixed patterns deliberately include varied
# performance and two incomplete sessions; they are not production or live records.
_DEMO_SESSION_PATTERNS = (
    ("demo-01", "Amina Hassan", True, (0, 1, 2, 2, 2)),
    ("demo-02", "Omar Khalil", True, (0, 0, 2, 1, 2)),
    ("demo-03", "Layla Nasser", True, (1, 0, 2, 1, 0)),
    ("demo-04", "Youssef Adel", True, (0, 1, 0, 1, 3)),
    ("demo-05", "Nour Samir", True, (0, 1, 2, 2, 0)),
    ("demo-06", "Mariam Tarek", True, (2, 0, 1, 1, 2)),
    ("demo-07", "Karim Fawzy", True, (0, 1, 2, 0, 2)),
    ("demo-08", "Salma Emad", True, (3, 3, 2, 1, 1)),
    ("demo-09", "Ziad Mostafa", False, (0, 0)),
    ("demo-10", "Farah Hany", False, (1, 1, 2)),
)

DEMO_CLASS_SESSIONS = [
    {
        "student_id": student_id,
        "student_name": student_name,
        "completed": completed,
        "responses": _demo_responses(selected_options),
    }
    for student_id, student_name, completed, selected_options in _DEMO_SESSION_PATTERNS
]
