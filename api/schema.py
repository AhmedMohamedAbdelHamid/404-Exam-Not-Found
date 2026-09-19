"""
Question generation schema — Day 2 contract (Person B)
Shared with A (retrieval/metadata alignment) and C (frontend rendering).

Bilingual scope: the ebook exists as two separate, parallel PDFs
(English and Arabic), matched chapter-for-chapter, with code/syntax
identical across both -- only surrounding explanations differ by
language. A student's language is fixed once (per their track); their
entire exam is generated from ONE corpus only, never mixed. This means
A's retrieval, embedding, and ChromaDB collections must be
language-scoped (e.g. separate collections per language, or a
language metadata filter), not a single merged index.

Freeze note: per roadmap.md, field names/shapes are frozen end of Day 2.
Any change after that needs a group sync.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LanguageEnum(str, Enum):
    """A student's track selects ONE source corpus — English PDF or
    Arabic PDF. These are separate, parallel textbooks (matched
    chapter-for-chapter), not merged. A student never sees chunks or
    questions from the other language."""
    EN = "en"
    AR = "ar"


class ChunkTypeEnum(str, Enum):
    """Mirrors README 3.5 — lets the generator vary question style by
    source content type. MCQ-only for MVP; keep the field so stretch
    goal types (predict-output, order-steps) can slot in later without
    a schema change."""
    CODE_BLOCK = "code_block"
    DEFINITION = "definition"
    ALGORITHM = "algorithm"


class DifficultySubScores(BaseModel):
    """README 3.1 — three self-reported sub-scores + justification each.
    These double as validation input and misconception-tag material."""
    bloom_level: int = Field(..., ge=1, le=5, description="1=Remember, 3=Apply, 5=Evaluate/Create")
    bloom_justification: str

    distractor_quality: int = Field(..., ge=1, le=5, description="1=obviously wrong, 3=plausible shallow error, 5=reflects real misconception")
    distractor_justification: str

    concept_depth: int = Field(..., ge=1, le=5, description="1=single concept/chunk, 3=single concept multi-line, 5=2+ concepts/chunks")
    concept_depth_justification: str

    @property
    def difficulty_score(self) -> int:
        """difficulty_score = round(mean(bloom, distractor, concept_depth))"""
        return round((self.bloom_level + self.distractor_quality + self.concept_depth) / 3)


class QuestionOption(BaseModel):
    text: str
    correct: bool
    # Required on incorrect options per README 3.2; null on the correct one.
    misconception: Optional[str] = Field(
        default=None,
        description="Specific wrong-answer reasoning, e.g. 'off-by-one boundary error'. Required when correct=False."
    )

    @field_validator("misconception")
    @classmethod
    def misconception_required_if_incorrect(cls, v, info):
        # NOTE: cross-field validation on `correct` is easier enforced at
        # the QuestionOut level (Pydantic v2 model_validator) — placeholder
        # here as documentation of intent; see QuestionOut.check_options.
        return v


class QuestionOut(BaseModel):
    """Final structured output from one generation call (one LLM JSON response)."""

    question: str
    topic: str                     # aligns with A's metadata tag (chapter/topic)
    language: LanguageEnum         # which student track / source PDF this question came from
    chunk_type: ChunkTypeEnum = ChunkTypeEnum.DEFINITION
    source_chunk_id: str           # traceability back to A's retrieval — needed for Stage 1 keyword-overlap check (README 3.3)

    options: list[QuestionOption] = Field(..., min_length=4, max_length=4)

    difficulty: DifficultySubScores
    difficulty_score: Optional[int] = None  # populated post-hoc by difficulty scorer, not by the LLM

    # Populated after Stage 1/2 validation (README 3.3) — not set at generation time
    validated: bool = False
    regeneration_count: int = 0

    @field_validator("options")
    @classmethod
    def exactly_one_correct(cls, v: list[QuestionOption]):
        correct_count = sum(1 for opt in v if opt.correct)
        if correct_count != 1:
            raise ValueError(f"Expected exactly 1 correct option, got {correct_count}")
        texts = [opt.text.strip().lower() for opt in v]
        if len(set(texts)) != len(texts):
            raise ValueError("Options must be non-empty and distinct")
        for opt in v:
            if not opt.correct and not opt.misconception:
                raise ValueError(f"Incorrect option missing misconception tag: {opt.text!r}")
        return v


class StudentAnswerLog(BaseModel):
    """What C logs when a student answers — feeds the misconception dashboard."""
    student_id: str
    question_id: str
    selected_option_index: int
    correct: bool
    misconception_tag: Optional[str] = None  # copied from the selected option if wrong
    difficulty_score: int


class NextQuestionRequest(BaseModel):
    """Input to B9: get_next_question(student_id). language is fixed
    per student (set once, e.g. at enrollment/track selection) — not
    re-chosen per question, so A's retrieval only ever searches that
    student's language corpus."""
    student_id: str
    language: LanguageEnum
    current_difficulty: int = Field(..., ge=1, le=5)


if __name__ == "__main__":
    # Quick sanity check that the contract is usable end-to-end.
    example = QuestionOut(
        question="What does this loop print?",
        topic="loops",
        language=LanguageEnum.EN,
        chunk_type=ChunkTypeEnum.CODE_BLOCK,
        source_chunk_id="chunk_042",
        options=[
            QuestionOption(text="0 1 2", correct=True),
            QuestionOption(text="0 1 2 3", correct=False, misconception="off-by-one boundary error"),
            QuestionOption(text="1 2 3", correct=False, misconception="assumes 1-indexed start"),
            QuestionOption(text="(nothing)", correct=False, misconception="assumes loop runs zero times"),
        ],
        difficulty=DifficultySubScores(
            bloom_level=3, bloom_justification="predicts output of new code",
            distractor_quality=4, distractor_justification="distractors reflect real off-by-one/index confusion",
            concept_depth=2, concept_depth_justification="single concept, multi-line trace",
        ),
    )
    example.difficulty_score = example.difficulty.difficulty_score
    print(example.model_dump_json(indent=2))
