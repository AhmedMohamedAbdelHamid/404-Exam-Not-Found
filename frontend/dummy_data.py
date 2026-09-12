"""Schema-compatible sample data for the frontend shell."""

from schema import DifficultySubScores, LanguageEnum, QuestionOption, QuestionOut


DUMMY_QUESTION = QuestionOut(
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
)
