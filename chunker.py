"""
chunker.py — Day 2 deliverable (Person A)

Extracts Chapter 12 "Programming (Python)" from both textbook PDFs
(English + Arabic, parallel/matched-chapter, never mixed) into
structured chunks matching B's schema.py contract:

    chunk_id, text, topic, language, chunk_type

Scope decision: only Chapter 12 (12-1 .. 12-5) is in scope for the
generator per prompt_template.py's SAMPLE_CHUNKS (12-2, 12-3). The
books are the full ICT course (202/218 pages); Chapter 12 is the only
pure-Python chapter, at:
    EN: pages 154-173  (0-indexed, PyMuPDF page numbers)
    AR: pages 167-180  (0-indexed)
Chapter 13 ("AI Programming" / HTML+JS+quiz+game project) is explicitly
OUT of scope for this MVP -- it's a different, non-Python unit.

Known issue this script works around (see README section below):
Arabic PDF renders each code *token* as its own text span, and plain
page.get_text() traverses spans in an order that scrambles LTR code
embedded in RTL layout (e.g. "for i in range(0, 4):" extracts as
"for / ]variable / ]in / ]range([...]):" out of order, with a stray
literal "]" glyph artifact prefixing each code token). We fix this by
reconstructing code lines from get_text("dict") span bboxes: group
spans into y-rows, sort each row left-to-right by x, and strip the
leading "]" artifact. Prose (Arabic) lines are left as normal
get_text() output, which extracts cleanly.

Run: python3 chunker.py
Output: chunks_en.json, chunks_ar.json (also merged chunks_all.json)
"""

import json
import re
import pymupdf

# ---------------------------------------------------------------------
# Chapter 12 section map -- confirmed by manual inspection of both PDFs.
# Each section starts on an "Information Study / Point!" page, then is
# followed by "Warm Up" / "Answer the following questions" / "Exercise"
# practice pages until the next section starts.
# ---------------------------------------------------------------------

EN_PDF = "books/ICT_EN__Sec1_Tr1.pdf"
AR_PDF = "books/ICT_AR__Sec1_Tr1.pdf"

EN_SECTIONS = [
    # (section_id, topic, start_page, end_page_exclusive)
    ("12-1", "algorithm", 154, 158),
    ("12-2", "variables and assignment", 158, 162),
    ("12-3", "loops and conditionals", 162, 167),
    ("12-4", "lists", 167, 171),
    ("12-5", "functions", 171, 174),
]

AR_SECTIONS = [
    ("12-1", "algorithm", 167, 171),
    ("12-2", "variables and assignment", 171, 175),
    ("12-3", "loops and conditionals", 175, 181),
    ("12-4", "lists", 181, 185),
    ("12-5", "functions", 185, 189),
]
# All 5 AR boundaries confirmed against real "دراسة المعلومات" (Information
# Study) section-header hits in the source PDF -- page 181 opens with
# list/error-handling content, page 185 opens with function/data-structure
# content, matching the EN chapter structure 1:1.

CHECKS_NEEDED = [
    "chunk_type tagging: VERIFIED (2026-09-15) against all 42 real "
    "chunks, not a sample -- see the accuracy-review comment above "
    "guess_chunk_type() for the full result. Confirmed accurate, no "
    "false positives. One residual note: 'definition' never fires on "
    "this corpus (not a bug -- every page has either algorithm/"
    "flowchart content or real code); re-verify if this chunker is "
    "ever pointed at different source material.",
    "Reconstructed Arabic code (extract_arabic_code_lines): RE-"
    "INVESTIGATED (2026-09-15). What looked like 'noise' on dense "
    "fill-in-the-blank pages (ar_ch12_12-3..12-5) is NOT extraction "
    "corruption -- manually confirmed against source text that code "
    "reconstructs cleanly (e.g. 'a = [1, 4, 9, 16, 25]', 'def "
    "area(base, height):') and the A/B/C/D markers are the textbook's "
    "own legitimate fill-in-the-blank answer choices, not artifacts. "
    "Renamed the retrieval-side metric from noise_score to "
    "exercise_density_score to reflect this (see retrieval.py). "
    "Real, still-open finding: 'lists' and 'functions' topics each "
    "have only 1 low-density (non-exercise-page) AR chunk -- worth "
    "watching if A4's per-student sampling exhausts it under real "
    "classroom load and starts serving dense exercise pages more often.",
    "Only Chapter 12 is chunked. If the generator ever needs Chapter 13 "
    "(AI/HTML/JS/game dev) content, this script does not cover it.",
]


# ---------------------------------------------------------------------
# Arabic code-block reconstruction
# ---------------------------------------------------------------------

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_CODEY_RE = re.compile(r"^[\]\[\(\)\w\s,\.:'\"=+\-*/%<>!]+$")


def _is_codey(text: str) -> bool:
    """A span is treated as 'code' if it has no Arabic characters and
    matches a restrictive charset (letters/digits/punctuation used in
    Python syntax). Prose in English footnotes could false-positive
    here in rare cases; acceptable for MVP, flagged for review."""
    text = text.strip()
    if not text:
        return False
    if _ARABIC_RE.search(text):
        return False
    return bool(_CODEY_RE.match(text))


def extract_arabic_code_lines(page) -> list[str]:
    """Reconstruct LTR code lines from a page that may contain
    scrambled Python code embedded in RTL layout. Returns cleaned code
    lines only (prose is extracted separately via normal get_text()).
    """
    d = page.get_text("dict")
    spans = []
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"])
            x0, y0, x1, y1 = line["bbox"]
            spans.append((y0, x0, text))

    # group into rows by y-proximity (3pt tolerance), sort each row L-to-R
    rows: dict[int, list[tuple[float, str]]] = {}
    for y0, x0, text in spans:
        if not _is_codey(text):
            continue
        key = round(y0 / 3)
        rows.setdefault(key, []).append((x0, text))

    lines = []
    for key in sorted(rows):
        row = sorted(rows[key], key=lambda t: t[0])
        words = [t.lstrip("]").strip() for _, t in row]
        # drop pure line-number artifacts like "01", "02" and stray "Execution result"
        words = [w for w in words if w and not re.fullmatch(r"\d{1,2}", w)]
        joined = " ".join(words).strip()
        if joined and joined.lower() != "execution result":
            lines.append(joined)
    return lines


# ---------------------------------------------------------------------
# chunk_type heuristic tagging (README 3.5 / schema.py ChunkTypeEnum)
# ---------------------------------------------------------------------

_CODE_MARKERS = ("print(", "range(", "for ", "if ", "elif", "else:", "def ", "return", "=")


def guess_chunk_type(text: str) -> str:
    lowered = text.lower()
    if any(m in lowered for m in ("algorithm", "flowchart", "خوارزمية")):
        return "algorithm"
    code_hits = sum(1 for m in _CODE_MARKERS if m in text)
    if code_hits >= 2:
        return "code_block"
    return "definition"


# --------------------------------------------------------------------
# Accuracy review (2026-09-15) -- manually verified against ALL 42
# real chunks (chunks_en.json + chunks_ar.json), not a sample:
#
# Result: 8 chunks tagged "algorithm", 34 tagged "code_block", 0
# tagged "definition". Confirmed both categories are CORRECT (not
# false positives): every "algorithm"-tagged chunk genuinely belongs
# to the algorithm topic (no stray "algorithm" mentions elsewhere
# causing mistagging), and every "code_block"-tagged chunk genuinely
# contains real Python code (print/for/def/etc, not just an
# incidental "=" -- checked the actual marker hits per chunk).
#
# "definition" never fires on this corpus -- NOT a bug. Verified every
# chunk either mentions algorithm/flowchart or has 2+ real code
# markers; there's no page in this specific chapter that's pure
# prose/definition with no code and no algorithm discussion (expected,
# given this is a hands-on Python programming chapter -- concepts are
# taught through worked code examples, not abstract definitions).
# "definition" is reachable code, just never exercised by THIS
# textbook chapter. If this chunker is ever pointed at different
# source material (e.g. a more theory-heavy chapter), re-verify this
# assumption -- don't assume "definition" still won't fire.
# --------------------------------------------------------------------


# ---------------------------------------------------------------------
# Extraction per language
# ---------------------------------------------------------------------

def extract_english_chunks() -> list[dict]:
    """One chunk PER PAGE (not per section) -- section pages run
    4-6 pages and dumping a whole section into one chunk is too coarse
    for retrieval (get_chunks() needs to hand the generator a focused
    passage, not a multi-concept wall of text). Page-level granularity
    roughly matches how the textbook itself is authored: one "Information
    Study" concept page, then one Warm-Up/Answer/Exercise page per
    practice set."""
    doc = pymupdf.open(EN_PDF)
    chunks = []
    for section_id, topic, start, end in EN_SECTIONS:
        for page_idx in range(start, min(end, len(doc))):
            text = doc[page_idx].get_text().strip()
            if not text:
                continue
            chunk_type = guess_chunk_type(text)
            chunks.append({
                "chunk_id": f"en_ch12_{section_id}_p{page_idx}",
                "topic": topic,
                "language": "en",
                "chunk_type": chunk_type,
                "text": text,
                "source_pages": [page_idx, page_idx],
            })
    return chunks


def extract_arabic_chunks() -> list[dict]:
    """Page-level granularity, same rationale as EN. Each page's prose
    is extracted normally; reconstructed (de-scrambled) code lines are
    appended as a clearly-marked block so the generator can ground
    code-block questions in correct token order even on pages where
    inline prose extraction still has scrambled code fragments."""
    doc = pymupdf.open(AR_PDF)
    chunks = []
    for section_id, topic, start, end in AR_SECTIONS:
        for page_idx in range(start, min(end, len(doc))):
            page = doc[page_idx]
            prose_text = page.get_text().strip()
            code_lines = extract_arabic_code_lines(page)
            reconstructed_code = "\n".join(code_lines).strip()

            full_text = prose_text
            if reconstructed_code:
                full_text += (
                    "\n\n--- reconstructed code (verify against source PDF) ---\n"
                    + reconstructed_code
                )
            if not full_text.strip():
                continue

            chunk_type = guess_chunk_type(full_text)
            chunks.append({
                "chunk_id": f"ar_ch12_{section_id}_p{page_idx}",
                "topic": topic,
                "language": "ar",
                "chunk_type": chunk_type,
                "text": full_text,
                "source_pages": [page_idx, page_idx],
            })
    return chunks


def main():
    en_chunks = extract_english_chunks()
    ar_chunks = extract_arabic_chunks()

    with open("chunks_en.json", "w", encoding="utf-8") as f:
        json.dump(en_chunks, f, ensure_ascii=False, indent=2)
    with open("chunks_ar.json", "w", encoding="utf-8") as f:
        json.dump(ar_chunks, f, ensure_ascii=False, indent=2)
    with open("chunks_all.json", "w", encoding="utf-8") as f:
        json.dump(en_chunks + ar_chunks, f, ensure_ascii=False, indent=2)

    print(f"EN chunks: {len(en_chunks)}")
    for c in en_chunks:
        print(f"  {c['chunk_id']:20s} [{c['chunk_type']:10s}] {len(c['text'])} chars  topic={c['topic']}")
    print(f"AR chunks: {len(ar_chunks)}")
    for c in ar_chunks:
        print(f"  {c['chunk_id']:20s} [{c['chunk_type']:10s}] {len(c['text'])} chars  topic={c['topic']}")

    print("\n--- CHECKS NEEDED before Day 3 embedding ---")
    for i, c in enumerate(CHECKS_NEEDED, 1):
        print(f"{i}. {c}")


if __name__ == "__main__":
    main()
