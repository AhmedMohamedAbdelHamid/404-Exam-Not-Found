"""
difficulty_scorer.py — B2 deliverable (Day 3, Person B)

Computes the final difficulty_score from an LLM's three self-reported
sub-scores (README 3.1: bloom_level, distractor_quality, concept_depth).

difficulty_score = round(mean(bloom_level, distractor_quality, concept_depth))

The math itself already lives as a property on schema.DifficultySubScores
(kept there so any code holding a DifficultySubScores instance can get the
score without importing this module). This module exists as the
explicit, testable "scorer" the roadmap calls for, and is the single
place B4 (staircase controller) and B9 (final API) should import from --
if the scoring formula ever changes (e.g. weighted average instead of
plain mean), it changes here once.
"""

from schema import DifficultySubScores, QuestionOut

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


def score_difficulty(sub_scores: DifficultySubScores) -> int:
    """Compute the final 1-5 difficulty_score from three sub-scores.

    difficulty_score = round(mean(bloom_level, distractor_quality, concept_depth))

    Uses Python's round() (banker's rounding: 2.5 -> 2, 3.5 -> 4) since
    that's what schema.py's property already does -- keeping this
    function and that property numerically identical matters, since
    some call sites use one and some the other.
    """
    mean = (
        sub_scores.bloom_level
        + sub_scores.distractor_quality
        + sub_scores.concept_depth
    ) / 3
    score = round(mean)
    # Defensive clamp: sub-scores are each already validated 1-5 by
    # schema.py's Field(ge=1, le=5), so this should be unreachable, but
    # cheap insurance against a future schema change loosening that bound.
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, score))


def apply_difficulty_score(question: QuestionOut) -> QuestionOut:
    """Populate question.difficulty_score in place from question.difficulty,
    and return the same object (for chaining in a pipeline). This is the
    one call site B3's generation agent and B9's final API should use --
    every QuestionOut that leaves the pipeline should have gone through
    this before reaching the staircase controller or a student.
    """
    question.difficulty_score = score_difficulty(question.difficulty)
    return question


if __name__ == "__main__":
    # Sanity checks across the rounding boundary (banker's rounding),
    # since this is the one place a rounding bug would silently mis-tier
    # every question in the exam.
    test_cases = [
        (1, 1, 1, 1),   # min
        (5, 5, 5, 5),   # max
        (3, 3, 3, 3),   # exact integer mean
        (2, 3, 4, 3),   # mean 3.0 exactly
        (1, 2, 3, 2),   # mean 2.0 exactly
        (2, 2, 3, 2),   # mean 2.333 -> rounds down
        (2, 3, 3, 3),   # mean 2.667 -> rounds up
        (1, 1, 2, 1),   # mean 1.333 -> rounds down
        (1, 2, 2, 2),   # mean 1.667(ish, actually 5/3=1.667) -> rounds up
    ]
    print("Rounding sanity checks (bloom, distractor, concept -> expected score):")
    all_passed = True
    for bloom, distractor, concept, expected in test_cases:
        sub = DifficultySubScores(
            bloom_level=bloom, bloom_justification="test",
            distractor_quality=distractor, distractor_justification="test",
            concept_depth=concept, concept_depth_justification="test",
        )
        got = score_difficulty(sub)
        status = "OK" if got == expected else "MISMATCH"
        if got != expected:
            all_passed = False
        print(f"  ({bloom},{distractor},{concept}) -> {got} (expected {expected}) [{status}]")

    # Also confirm this function agrees with schema.py's own property
    # (they must never drift apart -- different call sites use each).
    print("\nCross-check against schema.DifficultySubScores.difficulty_score property:")
    for bloom, distractor, concept, _ in test_cases:
        sub = DifficultySubScores(
            bloom_level=bloom, bloom_justification="test",
            distractor_quality=distractor, distractor_justification="test",
            concept_depth=concept, concept_depth_justification="test",
        )
        fn_result = score_difficulty(sub)
        prop_result = sub.difficulty_score
        match = "OK" if fn_result == prop_result else "DRIFT DETECTED"
        if fn_result != prop_result:
            all_passed = False
        print(f"  score_difficulty()={fn_result} vs .difficulty_score={prop_result} [{match}]")

    print(f"\n{'✓ All checks passed.' if all_passed else '✗ SOME CHECKS FAILED — see above.'}")
