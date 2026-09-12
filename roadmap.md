# Roadmap — Adaptive RAG-Based Exam Generator
### GenAI for Education Hackathon 2026 (EUI) — 9-Day Build Plan

**Roles**
- **A** — RAG pipeline (chunking, embedding, vector DB, retrieval)
- **B** — Generation + difficulty logic (prompt template, staircase controller, validation, backup pool)
- **C** — Frontend + analytics (Streamlit exam flow, misconception report, teacher dashboard)

**Note on the ebook:** the two uploaded PDFs (`ICT_EN__Sec1_Tr1.pdf`, `ICT_AR__Sec1_Tr1.pdf`) are a 202-page "Programming and Artificial Intelligence" textbook for First Year Secondary — this looks like your candidate source book for RAG. Roadmap below assumes **A uses the English version as primary source**, so the "decide which ebook" open item is basically resolved — just confirm as a team on Day 1.

---

## Critical path (read this first)

```
Ebook confirmed (Day 1)
   -> A: chunk + embed textbook (Day 2-3)
        -> A: retrieval function ready (Day 4)  ---> B WAITS ON THIS
             -> B: real RAG-grounded generation + validation (Day 4-6)
                  -> B: final question API ready (Day 6)  ---> C WAITS ON THIS
                       -> C: full integration (Day 7)
                            -> Integration testing, all 3 (Day 8)
                                 -> Demo (Day 9)
```

There are exactly **two hard handoffs** in this project. Everything else can run in parallel with dummy/mock data:

1. **Day 4 — A → B:** B cannot do *real* RAG-grounded generation until A's retrieval function exists. Until then B works with sample/pasted chunks.
2. **Day 6 — B → C:** C cannot do *real* end-to-end wiring until B's final `get_next_question()` API exists. Until then C builds every screen against dummy data.

If A or B slips, the person downstream slips 1:1 — flag delays immediately, don't sit on them.

---

## Day-by-day

| Day | Person A (RAG) | Person B (Generation) | Person C (Frontend) |
|---|---|---|---|
| **1** | Confirm ebook w/ team; skim it, mark chapters & code-heavy sections | Confirm ebook; draft prompt template using 2–3 manually-pasted sample chunks | Confirm ebook; wireframe page flow (exam → results → teacher dashboard) |
| **2** | Build chunking script (PyMuPDF, by section, code blocks kept intact) | **Finalize JSON schema/Pydantic contract, share with A & C by EOD** | Build static Streamlit UI shell (no real data) |
| **3** | Set up ChromaDB, embed all chunks, tag metadata (chapter/topic/rough difficulty) | Build difficulty scorer (sub-scores → mean → round); generation working end-to-end on dummy chunks | Build exam-taking flow logic against hardcoded dummy questions |
| **4** | **Expose `get_chunks(topic, difficulty)` retrieval function — deliver by midday** | *(AM: staircase controller/SQLite while waiting)* **PM: integrate real retrieval from A** | Build misconception report + teacher dashboard chart (Plotly/Altair), still on dummy data |
| **5** | Add per-student chunk sampling (anti-cheat layer 1); tune retrieval with B | Finish real RAG integration; build Validation Stage 1 (rule-based checks) | Polish UI; add/confirm option-order randomization |
| **6** | Help B/A generate the backup question pool (~15–20 vetted Qs/topic/difficulty) | Build Validation Stage 2 (LLM self-critique + retry ≤2); **expose final `get_next_question(student_id)` API by EOD** | *(waiting on B's API — keep refining dashboard visuals meanwhile)* |
| **7** | Support integration; fix retrieval/chunking issues found in real questions | Support integration; fix generation/validation bugs C finds | **Wire real exam flow + real misconception logging to dashboard** (depends on Day 6 API) |
| **8** | **All three: integration testing.** Run 3–5 full simulated student sessions, verify backup pool triggers on generation failure, feature freeze — bugs only | | |
| **9** | **All three: demo prep.** Rehearse pitch together (hook → live demo → dashboard flip → close), final polish. *Fallback demo clip: recorded by whoever's free — doesn't need all three.* | | |

---

## Full task list (with dependencies)

| ID | Owner | Task | Deadline | Depends on | Who's waiting |
|---|---|---|---|---|---|
| K1 | All | Confirm ebook + agree JSON schema fields at a high level | Day 1 | — | Everyone |
| A1 | A | Chunking script (section/concept-based, code blocks intact) | Day 2 | K1 | A2 |
| B1 | B | Finalize Pydantic schema, share with team | Day 2 | K1 | A4, C1–C4 field shapes |
| C1 | C | Static Streamlit UI shell | Day 2 | K1 | — |
| A2 | A | Embed chunks + ChromaDB + metadata tagging | Day 3 | A1 | A3 |
| B2 | B | Difficulty scorer + dummy-chunk generation working E2E | Day 3 | B1 | B4 |
| C2 | C | Exam-taking flow on dummy questions | Day 3 | C1, B1 (schema) | — |
| **A3** | **A** | **Retrieval function `get_chunks(topic, difficulty)`** | **Day 4 (midday)** | A2 | **B3** |
| B3 | B | Integrate real RAG retrieval into generation agent | Day 4–5 | A3 | B5 |
| B4 | B | Staircase controller (SQLite state, ±1, min/max) | Day 4 | B2 | B9 |
| C3 | C | Misconception report + teacher dashboard (dummy data) | Day 4 | C2 | — |
| A4 | A | Per-student chunk sampling (anti-cheat layer 1) | Day 5 | A3 | — |
| B5 | B | Validation Stage 1 (rule-based checks) | Day 5 | B3 | B6 |
| C4 | C | Option-order randomization; UI polish | Day 5 | C3 | — |
| B6 | B | Validation Stage 2 (LLM self-critique, retry ≤2) | Day 6 | B5 | B9 |
| **B9** | **B** | **Final API: `get_next_question(student_id)`** | **Day 6 (EOD)** | B4, B6 | **C5, C6** |
| A5 | A | Help generate backup question pool | Day 6 | A4 | C6 (fallback safety) |
| C5 | C | Wire real exam flow to B9 | Day 7 | B9 | C6 |
| C6 | C | Wire real misconception logging → dashboard | Day 7 | B9, A5 | Demo |
| — | All | Integration testing, bug bash, feature freeze | Day 8 | C5, C6 | Demo |
| — | All | Pitch rehearsal + fallback demo recording | Day 9 | Day 8 | — |

---

## Checkpoints

- **End of Day 2:** schema is frozen — nobody changes field names/shapes after this without a group sync.
- **End of Day 4:** if A hasn't delivered the retrieval function, B starts Day 5 still blocked — this is the point to escalate/pair up.
- **End of Day 6:** if B hasn't delivered the final API, C loses a full wiring day — same escalation rule.
- **End of Day 8:** feature freeze is real — nothing new goes in, only fixes, so the demo isn't at risk.
