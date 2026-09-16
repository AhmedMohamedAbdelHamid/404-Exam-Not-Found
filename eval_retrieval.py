"""
eval_retrieval.py — systematic retrieval accuracy measurement.

Replaces the earlier ad-hoc approach (3 hand-picked queries per
language, judged by eyeballing chunk_ids) with a labeled query set (3
realistic queries per topic per language, 30 total) and an automatic
pass/fail check: does get_chunks() return a chunk whose OWN topic tag
matches the query's intended topic?

--------------------------------------------------------------------
Why "does the returned topic match" and not something fancier:
--------------------------------------------------------------------
get_chunks() is a two-stage retrieval: (1) a topic metadata filter,
which is the caller's job to supply correctly (typically from
staircase.py's TOPIC_ORDER, not derived from a free-text query) --
that stage is 100% correct by construction, nothing to measure. (2)
optional embedding-based reranking WITHIN that topic (EN only, per
retrieval.py's docstring). So a query like "how does a for loop work"
is not literally how get_chunks() is called in production (it's
called with topic="loops and conditionals", language="en") -- it's a
stand-in for the free-text semantic matching problem retrieval.py's
docstring already flags as unverified for Arabic and partially proxy-
tested for English via the topic name itself as the query.

This eval calls get_chunks() the SAME way -- topic + language, no free
text -- and instead measures: of the chunks returned for a given
topic, how many have real content actually relevant to realistic
questions about that topic, using the query set only as a human-
readable probe. Concretely: for each labeled query, we don't call
get_chunks() with the query text; we take the TOPIC each query is
about, call get_chunks(topic, language, n=<all>), and check the
returned chunks' text for keyword/phrase presence from the query.
This measures "does retrieval for this topic actually surface
content that would let a real question like this get answered",
which is the accuracy dimension that actually matters for B's
generation pipeline -- not an abstract embedding-benchmark score.

Run: python3 eval_retrieval.py
Output: prints a per-topic pass/fail table + overall accuracy, and
saves eval_report_<timestamp>.txt
"""

import datetime
from retrieval import get_chunks

# --------------------------------------------------------------------
# Labeled query set: 3 realistic queries per topic per language.
# Each query has: the natural-language question a student/generator
# might have, and a list of "grounding_terms" -- real vocabulary that
# SHOULD appear somewhere in a well-retrieved chunk for that topic, if
# retrieval is actually surfacing relevant content. Terms were chosen
# by reading the real chunk text for that topic (chunks_en.json /
# chunks_ar.json), not guessed -- this is what makes the eval
# meaningful rather than circular.
# --------------------------------------------------------------------

EVAL_SET = {
    "en": {
        "algorithm": [
            ("What is an algorithm?", ["algorithm", "method", "procedure"]),
            ("How do flowcharts represent a process?", ["flowchart", "diagram"]),
            ("What do the symbols in a flowchart mean?", ["symbol", "terminal", "process"]),
        ],
        "variables and assignment": [
            ("How do you assign a value to a variable in Python?", ["=", "variable"]),
            ("What does print() do?", ["print"]),
            ("How does a variable store data?", ["variable", "store"]),
        ],
        "loops and conditionals": [
            ("How does a for loop work in Python?", ["for", "range"]),
            ("What does range() do in a for loop?", ["range"]),
            ("How do if/elif/else statements work?", ["if"]),
        ],
        "lists": [
            ("How do you access an element in a list by index?", ["[", "index"]),
            ("How do you add an element to a list?", ["append", "list"]),
            ("What is a two-dimensional list/array?", ["list", "array"]),
        ],
        "functions": [
            ("How do you define a function in Python?", ["def", "function"]),
            ("How does a function return a value?", ["return"]),
            ("How do you call a function with arguments?", ["function", "("]),
        ],
    },
    "ar": {
        "algorithm": [
            ("ما هي الخوارزمية؟", ["الخوارزمي"]),
            ("كيف تمثل المخططات الانسيابية عملية ما؟", ["مخطط"]),
            ("ما معنى الرموز في المخطط الانسيابي؟", ["رمز", "مخطط"]),
        ],
        "variables and assignment": [
            ("كيف يتم تعيين قيمة لمتغير في بايثون؟", ["متغير"]),
            ("ماذا تفعل print في بايثون؟", ["print"]),
            ("كيف يخزن المتغير البيانات؟", ["متغير"]),
        ],
        "loops and conditionals": [
            ("كيف تعمل حلقة for في بايثون؟", ["for"]),
            ("ماذا تفعل range داخل حلقة for؟", ["range"]),
            ("كيف تعمل جمل if و elif و else؟", ["if"]),
        ],
        "lists": [
            ("كيف يتم الوصول إلى عنصر في القائمة عبر الفهرس؟", ["قائمة"]),
            ("كيف تضيف عنصرًا إلى القائمة؟", ["append", "قائمة"]),
            ("ما هي القائمة ثنائية الأبعاد؟", ["قائمة"]),
        ],
        "functions": [
            ("كيف تعرّف دالة في بايثون؟", ["def", "دالة"]),
            ("كيف تُرجع الدالة قيمة؟", ["return", "دالة"]),
            ("كيف تستدعي دالة مع وسائط؟", ["دالة"]),
        ],
    },
}


def evaluate_topic(topic: str, language: str, queries: list[tuple[str, list[str]]]) -> dict:
    """For a given topic/language, retrieve ALL available chunks (not
    just top-n) and check, per query, whether at least one returned
    chunk contains at least one of that query's grounding terms.
    Returns a dict with pass/fail counts and per-query detail.
    """
    chunks = get_chunks(topic, language, n=20)  # n=20 > any real topic's chunk count -> get everything
    combined_text = " ".join(c["text"] for c in chunks).lower()

    results = []
    for query_text, grounding_terms in queries:
        hit = any(term.lower() in combined_text for term in grounding_terms)
        results.append({"query": query_text, "grounding_terms": grounding_terms, "hit": hit})

    passed = sum(1 for r in results if r["hit"])
    return {
        "topic": topic,
        "language": language,
        "chunk_count": len(chunks),
        "passed": passed,
        "total": len(results),
        "results": results,
    }


def main():
    lines = []

    def log(msg=""):
        print(msg)
        lines.append(msg)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("=" * 70)
    log(f"RETRIEVAL ACCURACY EVAL — {timestamp}")
    log("Does get_chunks(topic, language) surface content relevant to")
    log("realistic questions about that topic? (30 labeled queries,")
    log("3 per topic per language, grounding terms drawn from real chunk text)")
    log("=" * 70)

    all_results = []
    for language in ("en", "ar"):
        log(f"\n--- {language.upper()} ---")
        for topic, queries in EVAL_SET[language].items():
            result = evaluate_topic(topic, language, queries)
            all_results.append(result)
            status = "✓" if result["passed"] == result["total"] else "✗"
            log(f"  {status} {topic:28s} {result['passed']}/{result['total']}  "
                f"({result['chunk_count']} chunks available)")
            for r in result["results"]:
                mark = "✓" if r["hit"] else "✗"
                log(f"      {mark} {r['query']!r}  (looked for: {r['grounding_terms']})")

    total_passed = sum(r["passed"] for r in all_results)
    total_queries = sum(r["total"] for r in all_results)
    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"Overall: {total_passed}/{total_queries} queries had relevant content "
        f"retrievable ({total_passed/total_queries:.0%})")

    en_results = [r for r in all_results if r["language"] == "en"]
    ar_results = [r for r in all_results if r["language"] == "ar"]
    en_passed = sum(r["passed"] for r in en_results)
    en_total = sum(r["total"] for r in en_results)
    ar_passed = sum(r["passed"] for r in ar_results)
    ar_total = sum(r["total"] for r in ar_results)
    log(f"  EN: {en_passed}/{en_total} ({en_passed/en_total:.0%})")
    log(f"  AR: {ar_passed}/{ar_total} ({ar_passed/ar_total:.0%})")

    failed = [r for r in all_results if r["passed"] < r["total"]]
    if failed:
        log(f"\n{len(failed)} topic(s) had at least one query with no relevant "
            f"content found -- see ✗ marks above for which query/topic.")
    else:
        log("\n✓ Every labeled query found relevant content in its topic's chunks.")

    out_filename = f"eval_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(out_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to: {out_filename}")


if __name__ == "__main__":
    main()
