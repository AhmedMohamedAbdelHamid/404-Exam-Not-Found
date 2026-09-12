"""
Generation prompt template — Day 2 deliverable (Person B)
Uses 2-3 manually-pasted sample chunks (stand-ins for A's real retrieval,
which lands Day 4). This is what B3 (Day 4-5) will swap dummy chunks for
real ones from get_chunks(topic, difficulty) — the prompt itself shouldn't
need to change, only the chunk source.
"""

import json
from schema import QuestionOut

# ---------------------------------------------------------------------
# 1. Sample chunks (stand-ins for A's retrieval; replace with real
#    get_chunks() output on Day 4-5 without touching the prompt below)
# ---------------------------------------------------------------------

SAMPLE_CHUNKS = {
    # Pulled verbatim (paraphrased/condensed for token economy, facts
    # preserved) from the real course textbook: ICT_EN__Sec1_Tr1.pdf,
    # Chapter 12 "Programming (Python)", sections 12-2 and 12-3.
    "chunk_12-2_variables": {
        "topic": "variables and assignment",
        "language": "en",
        "chunk_type": "code_block",
        "text": (
            "print(x) displays the string or value inside the parentheses; "
            "strings are wrapped in quotes, numbers are not. A variable is "
            "like a box that stores data. The '=' operator is the "
            "assignment operator: it does NOT mean mathematical equality, "
            "it means 'assign the right side to the left side.'\n\n"
            "Example:\n"
            "city = 'Cairo'\n"
            "print(city)\n"
            "-> Output: Cairo\n\n"
            "A variable must be assigned before it is used -- a program "
            "that calls print(name) BEFORE the line name = 'Mr. Suzuki' "
            "will fail, because the variable doesn't exist yet at that "
            "point. Also, '==' (comparison) is a different operator from "
            "'=' (assignment); writing age == '17 years old' does not "
            "store a value in age, it only compares."
        ),
    },
    "chunk_12-3_for_loop": {
        "topic": "loops",
        "language": "en",
        "chunk_type": "code_block",
        "text": (
            "A for statement repeats a process. Syntax: "
            "for variable in range([range]): [process to repeat], with "
            "the repeated block indented.\n\n"
            "range(end_value): variable goes from 0 up to end_value - 1.\n"
            "range(start, end): variable goes from start up to end - 1.\n"
            "range(start, end, step): variable increases by step, from "
            "start up to end - step.\n\n"
            "Example -- displays integers from 0 to 3:\n"
            "for i in range(0, 4):\n"
            "    print(i)\n"
            "-> Output: 0 1 2 3\n\n"
            "Example -- displays odd numbers from 1 to 5:\n"
            "for i in range(1, 7, 2):\n"
            "    print(i)\n"
            "-> Output: 1 3 5\n\n"
            "Note range(end_value) stops BEFORE reaching end_value -- "
            "range(4) produces 0,1,2,3, not 0,1,2,3,4."
        ),
    },
    "chunk_12-3_if_elif_else": {
        "topic": "conditionals",
        "language": "en",
        "chunk_type": "code_block",
        "text": (
            "Comparison operators: == (equal), != (not equal), < (less "
            "than), > (greater than), <= (less than or equal), >= "
            "(greater than or equal).\n\n"
            "An if/else statement branches on a conditional expression: \n"
            "if [condition]:\n"
            "    [process when true]\n"
            "else:\n"
            "    [process when false]\n\n"
            "An if/elif/else chain checks conditions in order and runs "
            "only the FIRST branch whose condition is true, then skips "
            "the rest -- even if a later condition would also be true.\n\n"
            "Example -- grading program:\n"
            "x = 70\n"
            "if x >= 90:\n"
            "    result = 'Grade is A'\n"
            "elif x >= 50:\n"
            "    result = 'Grade is B'\n"
            "else:\n"
            "    result = 'Grade is C'\n"
            "print(result)\n"
            "-> Output: Grade is B\n"
            "(x=70 fails the first check x>=90, then passes x>=50, so "
            "the elif branch runs and the else branch is skipped, even "
            "though x is also not less than 50.)"
        ),
    },
    # --- Arabic-track chunk (same code/output as the English for-loop
    #     chunk above, verified against ICT_AR__Sec1_Tr1.pdf; the code
    #     itself stays in Latin script in the real textbook -- only the
    #     surrounding prose is Arabic) ---
    "chunk_12-3_for_loop_ar": {
        "topic": "loops",
        "language": "ar",
        "chunk_type": "code_block",
        "text": (
            "جملة for تكرر عملية ما. الصيغة: "
            "for variable in range([range]): [العملية المراد تكرارها], "
            "مع إزاحة السطر المكرر.\n\n"
            "range(end_value): تبدأ القيمة من 0 وتزيد بمقدار 1 حتى end_value - 1.\n"
            "range(start, end): تبدأ القيمة من start وتزيد بمقدار 1 حتى end - 1.\n"
            "range(start, end, step): تزيد القيمة بمقدار step، بدءاً من start حتى end - step.\n\n"
            "مثال -- يعرض الأعداد الصحيحة من 0 إلى 3:\n"
            "for i in range(0, 4):\n"
            "    print(i)\n"
            "-> النتيجة: 0 1 2 3\n\n"
            "مثال -- يعرض أرقاماً فردية من 1 إلى 5:\n"
            "for i in range(1, 7, 2):\n"
            "    print(i)\n"
            "-> النتيجة: 1 3 5\n\n"
            "ملاحظة: range(end_value) تتوقف قبل الوصول إلى end_value -- "
            "range(4) تنتج 0,1,2,3 وليس 0,1,2,3,4."
        ),
    },
}

# ---------------------------------------------------------------------
# 2. Prompt template
# ---------------------------------------------------------------------

SYSTEM_PROMPT = """You are a question-generation engine for an adaptive exam system. \
You generate ONE multiple-choice question grounded strictly in a provided textbook \
chunk. You must not use outside knowledge beyond what the chunk supports.

Rules:
- Output ONLY valid JSON matching the schema below. No markdown fences, no preamble.
- Exactly 4 options, exactly 1 marked correct.
- Every INCORRECT option must carry a "misconception" string describing the specific \
wrong reasoning a student would have to hold to pick it (e.g. "off-by-one boundary \
error", "confuses break with continue"). Do not use generic distractors like "none \
of the above" or unrelated wrong facts -- distractors must reflect real, plausible \
misunderstandings of the chunk's content.
- The correct option's "misconception" field must be null.
- Do not introduce facts, functions, or syntax not present in the chunk.
- Write the question and option text in the SAME language as the chunk's prose. \
Code, syntax keywords, function names, and identifiers (e.g. "for", "range", \
"print", variable names) are NEVER translated, regardless of the chunk's language \
-- copy them exactly as they appear in the chunk.
- Report three difficulty sub-scores (1-5 each) with a one-line justification for each:
  - bloom_level: 1=recall a fact/syntax, 3=apply/predict output in a new example, \
5=evaluate or create (judge the best solution, compare tradeoffs)
  - distractor_quality: 1=distractors are obviously wrong, 3=distractors are \
plausible shallow errors (e.g. off-by-one), 5=distractors reflect deep, realistic \
misconceptions
  - concept_depth: 1=single concept from a single chunk, 3=single concept requiring \
multi-line tracing, 5=2+ concepts or requires connecting multiple chunks

Schema (produce exactly this JSON shape):
{
  "question": "<string, written in the SAME language as the chunk text>",
  "topic": "<string, copy from chunk metadata>",
  "language": "<en | ar, copy from chunk metadata -- must match the chunk's language exactly>",
  "chunk_type": "<code_block | definition | algorithm>",
  "source_chunk_id": "<string, copy from input>",
  "options": [
    {"text": "<string, same language as the question>", "correct": true|false, "misconception": "<string or null>"}
  ],
  "difficulty": {
    "bloom_level": <int 1-5>, "bloom_justification": "<string>",
    "distractor_quality": <int 1-5>, "distractor_justification": "<string>",
    "concept_depth": <int 1-5>, "concept_depth_justification": "<string>"
  }
}
"""

USER_PROMPT_TEMPLATE = """Chunk ID: {chunk_id}
Topic: {topic}
Language: {language}
Chunk type: {chunk_type}

Chunk text:
\"\"\"
{chunk_text}
\"\"\"

Target difficulty band: {target_difficulty} (1=easiest, 5=hardest)

Generate one multiple-choice question from this chunk, at approximately this \
difficulty band, following the system instructions exactly. The question and \
options must be written in {language} (code/syntax stays untranslated)."""


def build_messages(chunk_id: str, target_difficulty: int) -> list[dict]:
    chunk = SAMPLE_CHUNKS[chunk_id]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        chunk_id=chunk_id,
        topic=chunk["topic"],
        language=chunk["language"],
        chunk_type=chunk["chunk_type"],
        chunk_text=chunk["text"],
        target_difficulty=target_difficulty,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------
# 3. Parse + validate LLM output against the Day-2 schema contract
# ---------------------------------------------------------------------

def parse_and_validate(raw_llm_output: str) -> QuestionOut:
    """Strip accidental markdown fences, parse JSON, validate against
    QuestionOut. Raises on Stage-1-style violations (schema.py's
    validators already enforce: exactly one correct option, all options
    distinct/non-empty, misconception present on every wrong option)."""
    cleaned = raw_llm_output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned)
    return QuestionOut(**data)


# ---------------------------------------------------------------------
# 4. Offline test: simulate one "LLM response" by hand and confirm the
#    full pipeline (prompt -> parse -> validate) works end to end.
#    This is what lets B2/B3 build on this today without a live API key.
# ---------------------------------------------------------------------

def _simulated_llm_response_for_for_loop_chunk() -> str:
    """Hand-written stand-in for what the LLM should return, given the
    real for-loop chunk above, at target_difficulty=2. Used to
    sanity-check the parser and schema before wiring a real API call."""
    return json.dumps({
        "question": "What does the following code print?\nfor i in range(1, 7, 2):\n    print(i)",
        "topic": "loops",
        "language": "en",
        "chunk_type": "code_block",
        "source_chunk_id": "chunk_12-3_for_loop",
        "options": [
            {"text": "1 3 5", "correct": True, "misconception": None},
            {"text": "1 3 5 7", "correct": False, "misconception": "off-by-one boundary error: assumes range(start, end, step) includes the end value"},
            {"text": "0 2 4 6", "correct": False, "misconception": "assumes range always starts at 0, ignoring the given start value"},
            {"text": "1 2 3 4 5 6", "correct": False, "misconception": "ignores the step argument and assumes the default increment of 1"},
        ],
        "difficulty": {
            "bloom_level": 2, "bloom_justification": "predicts output of a directly-shown example with a non-default step",
            "distractor_quality": 3, "distractor_justification": "distractors are plausible errors about range's start/end/step exclusivity",
            "concept_depth": 1, "concept_depth_justification": "single concept (three-argument range), single chunk",
        },
    })


def _simulated_llm_response_for_for_loop_chunk_ar() -> str:
    """Hand-written stand-in for the Arabic-track version of the same
    question, given the Arabic chunk above. Code stays untranslated;
    question/option text is in Arabic."""
    return json.dumps({
        "question": "ماذا تطبع الشيفرة التالية؟\nfor i in range(1, 7, 2):\n    print(i)",
        "topic": "loops",
        "language": "ar",
        "chunk_type": "code_block",
        "source_chunk_id": "chunk_12-3_for_loop_ar",
        "options": [
            {"text": "1 3 5", "correct": True, "misconception": None},
            {"text": "1 3 5 7", "correct": False, "misconception": "خطأ حدي (off-by-one): افتراض أن range تشمل قيمة النهاية"},
            {"text": "0 2 4 6", "correct": False, "misconception": "افتراض أن range تبدأ دائماً من 0 متجاهلاً قيمة البداية المحددة"},
            {"text": "1 2 3 4 5 6", "correct": False, "misconception": "تجاهل وسيط الخطوة (step) وافتراض الزيادة الافتراضية 1"},
        ],
        "difficulty": {
            "bloom_level": 2, "bloom_justification": "predicts output of a directly-shown example with a non-default step",
            "distractor_quality": 3, "distractor_justification": "distractors are plausible errors about range's start/end/step exclusivity",
            "concept_depth": 1, "concept_depth_justification": "single concept (three-argument range), single chunk",
        },
    })


if __name__ == "__main__":
    # Show the actual prompt that will be sent (for review/sharing with team)
    messages = build_messages("chunk_12-3_for_loop", target_difficulty=2)
    print("=" * 70)
    print("SYSTEM PROMPT")
    print("=" * 70)
    print(messages[0]["content"])
    print("\n" + "=" * 70)
    print("USER PROMPT (example: real for-loop chunk, target difficulty 2)")
    print("=" * 70)
    print(messages[1]["content"])

    # Prove the parse+validate step works against a realistic response
    print("\n" + "=" * 70)
    print("SIMULATED END-TO-END VALIDATION (English track)")
    print("=" * 70)
    raw = _simulated_llm_response_for_for_loop_chunk()
    question = parse_and_validate(raw)
    question.difficulty_score = question.difficulty.difficulty_score
    print(question.model_dump_json(indent=2))
    print(f"\n✓ Parsed and validated successfully. difficulty_score = {question.difficulty_score}")

    print("\n" + "=" * 70)
    print("SIMULATED END-TO-END VALIDATION (Arabic track)")
    print("=" * 70)
    raw_ar = _simulated_llm_response_for_for_loop_chunk_ar()
    question_ar = parse_and_validate(raw_ar)
    question_ar.difficulty_score = question_ar.difficulty.difficulty_score
    print(question_ar.model_dump_json(indent=2, ensure_ascii=False))
    print(f"\n✓ Parsed and validated successfully. difficulty_score = {question_ar.difficulty_score}")
