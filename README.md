# Adaptive RAG-Based Exam Generator

**Hackathon:** GenAI for Education Hackathon 2026 (EUI) — Student Track
**Theme fit:** Assessment Revolution
**Team size:** 3

---

## 1. The idea

An AI system that generates exam questions grounded in the actual course
textbook (via RAG), where each question's difficulty adapts in real time
based on whether the student answered the previous question correctly —
within a fixed min/max difficulty range.

Because every student's question sequence depends on their own answers,
no two students see the same exam, which makes the exam effectively
uncheatable while staying curriculum-accurate.

**Core inputs:**
1. The programming ebook the students already use (ingested into RAG)
2. The student's running performance (correct/incorrect) driving a
   difficulty staircase

**Planned extra features:**
- Per-student "which topics/misconceptions is this student struggling
  with" report
- Class-wide ranking of hardest topics, for teachers
- (Roadmap, not MVP) personalized remediation content, parent reports

---

## 2. Why this is a strong idea (rating: 7.5/10)

**Strengths:**
- Solves a real problem (exam integrity + one-size-fits-all difficulty),
  not a generic "AI does X" wrapper
- RAG grounding directly addresses the biggest weakness of naive AI quiz
  generators: hallucinated/off-syllabus questions
- Teacher-analytics layer turns this from "cool demo" into "a school
  would actually use this"
- Fully buildable by 3 people in ~9 days with tools the team already
  knows (Streamlit, Python)

**Risks / why not higher:**
- Adaptive testing itself isn't novel (Duolingo, GRE CAT already do
  this) — the differentiator is the *combination* of RAG-grounding +
  anti-cheat framing + class-wide misconception analytics, not
  adaptivity alone. Lead the pitch with the combination.
- MCQ-only caps how flashy the generated questions feel, but it's the
  right tradeoff for auto-gradability and low demo risk — don't
  second-guess this under time pressure.

---

## 3. Key design decisions

### 3.1 Difficulty — operationally defined (not "just ask the AI")

Each question gets a difficulty score 1–5, computed as the average of
three sub-scores the LLM self-reports at generation time:

| Sub-score | 1 (easy) | 3 (medium) | 5 (hard) |
|---|---|---|---|
| **Bloom's level** | Remember (recall fact/syntax) | Apply (predict output / new context) | Evaluate/Create (judge best solution) |
| **Distractor quality** | Obviously wrong options | Plausible shallow errors (off-by-one) | Options reflect real common misconceptions |
| **Concept depth** | Single concept, single chunk | Single concept, multi-line tracing | 2+ concepts, 2+ retrieved chunks |

`difficulty_score = round(mean(bloom_level, distractor_quality, concept_depth))`

The model must output all three sub-scores + a one-line justification
each — this doubles as validation input (3.3) and the misconception tag
(3.2), for free.

**Staircase logic:** correct → difficulty += 1 (capped at max); wrong →
difficulty −= 1 (capped at min). Per-student state tracked in SQLite.

### 3.2 Misconception signal — specific, not chapter-level

Every wrong option carries a `misconception` tag, not just the question
carrying a `topic` tag:

```json
{
  "question": "...",
  "topic": "loops",
  "options": [
    {"text": "...", "correct": true},
    {"text": "...", "correct": false, "misconception": "off-by-one boundary error"},
    {"text": "...", "correct": false, "misconception": "confuses break with continue"},
    {"text": "...", "correct": false, "misconception": "assumes loop runs zero times"}
  ]
}
```

When a student picks a wrong option, log the specific misconception
string. The teacher dashboard can then say **"38% of the class has the
off-by-one boundary misconception"** instead of just "38% struggle with
loops" — far more actionable, and a strong demo moment.

### 3.3 Validation / regeneration guardrail

Two stages before a question reaches a student:

**Stage 1 — rule-based (cheap):**
- Exactly one option marked `correct: true`
- All 4 options non-empty and distinct
- Keyword overlap check: question concepts appear in the retrieved chunk

**Stage 2 — LLM self-critique (one extra call, only if Stage 1 passes):**
- "Is exactly one option unambiguously correct per the source?"
- "Is the correct answer directly supported by the chunk, not outside
  knowledge?"

If either check fails: regenerate (max 2 retries), then fall back to a
pre-vetted backup question for that topic/difficulty. **The backup pool
is demo insurance — never let a live demo hit a generation failure with
no fallback.**

### 3.4 Cheat-resistance — explicit mechanism

Three layers, stated plainly in the pitch:

1. **Per-student chunk sampling** — for a given topic/difficulty,
   question is generated from a randomly selected chunk among several
   covering that concept
2. **Option order randomization** — shuffled per student per question
3. **Difficulty path divergence** — difficulty adapts to each student's
   own answers, so two students rarely see the same question sequence
   even starting from the same point

**Pitch line:** *"There is no fixed answer key — the question sequence
is a function of each student's own performance, so sharing answers
between students is structurally meaningless."*

### 3.5 Additional question types (stretch goal)

Keep MCQ as the guaranteed default. Optionally vary format by chunk
content type — stays auto-gradable, no LLM-grader risk:

| Chunk type | Question type | Still auto-gradable? |
|---|---|---|
| Code block | "Predict the output" (options = candidate outputs) | Yes |
| Definition/concept | Standard concept MCQ | Yes |
| Multi-step (algorithm) | "Order the steps" | Yes |
| Code snippet (stretch only) | Fill-in-the-blank, single missing token, exact match | Yes |

Avoid free-text/code-writing grading — introduces an LLM-as-grader
dependency right before the demo, too risky for the timeline.

---

## 4. Architecture

```
Programming ebook
      |
      v
Chunking (by section/concept, code blocks kept intact)
      |
      v
Vector DB (RAG) — embeddings + metadata (chapter, topic, difficulty)
      |
      v
Question generator agent  <-- retrieves chunk(s) for target difficulty
      |
      v
Difficulty scorer (self-reported sub-scores, see 3.1)
      |
      v
Validation / regeneration guardrail (see 3.3)
      |
      v
Staircase controller (adjusts next difficulty, enforces min/max)
      |
      +--> Student exam (unique per student, randomized options)
      |
      +--> Teacher analytics (misconception ranking, weak topics)
```

---

## 5. Tech stack

| Layer | Tool | Why |
|---|---|---|
| Frontend / demo | **Streamlit** | Team already knows it; fastest path to a working interactive demo |
| LLM | **Gemini Flash or GPT-4o-mini** | Cheap/fast enough for live generation, strong structured-output following |
| Embeddings | **`text-embedding-3-small`** (OpenAI) or **`all-MiniLM-L6-v2`** (free, local) | MiniLM = zero API cost; OpenAI = slightly better quality if budget allows |
| Vector store | **ChromaDB** | Local/embedded, zero setup, plenty for one ebook — no need for Pinecone/Weaviate |
| PDF/ebook parsing | **PyMuPDF (fitz)** | Handles code blocks/formatting better than naive text extraction |
| Difficulty/state tracking | **SQLite** | Per-student difficulty state, question history, answer logs |
| Structured output | **Pydantic + LLM JSON mode/function calling** | Enforces the MCQ schema so malformed outputs don't break the live demo |
| Analytics visualization | **Streamlit + Plotly/Altair** | Bar chart of "hardest topics/misconceptions across the class" — the key demo moment |

---

## 6. Suggested build split (3 people, ~9 days)

- **Person A — RAG pipeline:** chunking, embedding, metadata tagging
  (chapter, topic, rough difficulty)
- **Person B — Generation + difficulty logic:** prompt template,
  staircase controller, validation guardrail, backup question pool
- **Person C — Frontend + analytics:** exam-taking flow in Streamlit,
  per-student misconception report, class-wide weak-topic dashboard

## 7. What to cut from the MVP

- Parent notifications — roadmap slide only, do not build
- Full personalized remediation — if time remains, a cheap version is
  just surfacing the retrieved chunks tied to each wrong answer
  ("re-read this section")

## 8. Pitch structure

1. **Hook (15 sec):** "Every question is grounded in the actual
   textbook, and every exam is mathematically unique per student — so
   it's ungameable, and it shows teachers exactly where the whole class
   is struggling."
2. **Live demo:** take the exam live, show difficulty adapting question
   to question
3. **Flip to teacher dashboard:** show the misconception ranking across
   the class — this is the moment that sells the project
4. **Close:** state the no-fixed-answer-key mechanism explicitly (3.4)
   to preempt the "how is this actually cheat-resistant" question

## 9. Open next steps

- [ ] Draft the exact generation prompt template (produces full JSON:
      question, options, misconception tags, difficulty sub-scores, in
      one call)
- [ ] Design the Streamlit page flow (exam-taking → results → dashboard)
- [ ] Decide which programming ebook to use for the demo and pre-chunk it
- [ ] Build the backup question pool per topic/difficulty (demo insurance)
