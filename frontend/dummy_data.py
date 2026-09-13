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
