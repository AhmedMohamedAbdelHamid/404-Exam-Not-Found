"""
backup_pool.py — A5 deliverable (roadmap deadline: Day 6, "Help
generate the backup question pool"). Shared A+B task per roadmap.md's
Full Task List; built here on the A side since it's the natural
consumer of get_next_question.py's existing GenerationUnavailable
exception, which had no fallback implementation before this file.

--------------------------------------------------------------------
What this is, and what it isn't:
--------------------------------------------------------------------
This is a small (2 per topic per language = 20 total), HAND-AUTHORED,
hand-vetted set of QuestionOut-shaped questions -- not LLM-generated,
not auto-validated. The roadmap calls for "~15-20 vetted Qs/topic/
difficulty"; this delivers 2 per topic (one easier, one harder) across
all 5 topics x 2 languages, prioritizing genuine correctness and
grounding over raw count, since a bad backup question is worse than
none (it's the safety net -- it has no Stage 1/2 validation to catch
mistakes, unlike generated questions). If more volume is wanted before
the demo, extending the TOPIC/language cells below is straightforward
(same schema, same pattern) -- flagged as a real "more would help"
item, not a completeness claim.

Each question is grounded in a REAL chunk_id from chunks_en.json /
chunks_ar.json (source_chunk_id is set genuinely, not a placeholder),
and was checked by hand against that chunk's actual text before being
written -- not copied from generation_agent.py's stub logic.

--------------------------------------------------------------------
Integration point (the part that was genuinely missing before this):
--------------------------------------------------------------------
get_next_question.py raises GenerationUnavailable and its own
docstring says the caller should "fall back to the backup question
pool (A5) for this topic/difficulty" -- but nothing implementing that
fallback existed anywhere in the repo. get_backup_question() below is
that function. Suggested call-site wiring (not made here, since it's
B/C's call which layer -- get_next_question.py itself vs. its caller
-- should own the try/except):

    from get_next_question import get_next_question, GenerationUnavailable
    from backup_pool import get_backup_question

    try:
        q = get_next_question(student_id, chunk_sampler, gen_fn, critique_fn)
    except GenerationUnavailable:
        q = get_backup_question(topic, language, difficulty)
        # q.validated stays True but is hand-vetted, not LLM-validated --
        # caller/dashboard may want to distinguish this from a real
        # validated question if that matters for the misconception
        # report (C6). source_chunk_id is real and traceable either way.

Difficulty here means "pick the easier or harder pre-written question
for this topic", not free selection of a 1-5 score -- with only 2
backups per topic, difficulty >= 3 maps to the harder one and
everything below maps to the easier one. See _select_by_difficulty's
docstring for the exact cutoff and why.

Run standalone: python3 backup_pool.py
"""

from schema import QuestionOut, QuestionOption, DifficultySubScores, LanguageEnum, ChunkTypeEnum

# --------------------------------------------------------------------
# The pool itself: {(topic, language): [easier_question, harder_question]}
# Each entry is a QuestionOut built directly (not parsed from JSON) so
# schema validation (exactly-one-correct, misconception-required,
# 4 options) runs at import time -- a malformed backup question fails
# LOUDLY on import, not silently at exam time when a student needs it.
# --------------------------------------------------------------------

_POOL: dict[tuple[str, str], list[QuestionOut]] = {}


def _add(topic: str, language: str, chunk_id: str,
         question: str, options: list[tuple[str, bool, str | None]],
         bloom: int, distractor: int, concept: int,
         bloom_just: str, distractor_just: str, concept_just: str) -> None:
    """Build, validate (via QuestionOut's own validators), and register
    one backup question. Questions are appended in [easy, hard] order
    per (topic, language) -- see module docstring for why this pool
    uses two tiers, not five."""
    q = QuestionOut(
        question=question,
        topic=topic,
        language=LanguageEnum(language),
        chunk_type=ChunkTypeEnum.CODE_BLOCK,
        source_chunk_id=chunk_id,
        options=[QuestionOption(text=t, correct=c, misconception=m) for t, c, m in options],
        difficulty=DifficultySubScores(
            bloom_level=bloom, bloom_justification=bloom_just,
            distractor_quality=distractor, distractor_justification=distractor_just,
            concept_depth=concept, concept_depth_justification=concept_just,
        ),
        validated=True,  # hand-vetted by a human -- see module docstring
    )
    q.difficulty_score = q.difficulty.difficulty_score
    key = (topic, language)
    _POOL.setdefault(key, [])
    _POOL[key].append(q)


# ============================================================
# ALGORITHM
# ============================================================

_add(
    topic="algorithm", language="en",
    chunk_id="en_ch12_12-1_p154",
    question="What is the best definition of an algorithm?",
    options=[
        ("A method or procedure for solving a particular problem", True, None),
        ("A programming language used to write code", False, "confuses algorithm (the abstract method) with a programming language (a tool for expressing it)"),
        ("A diagram that shows the flow of a process", False, "confuses the algorithm itself with a flowchart, which is one way of representing an algorithm visually"),
        ("A list of variables used in a program", False, "confuses algorithm with unrelated programming terminology"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="direct recall of the textbook's own definition",
    distractor_just="distractors are plausible related-but-wrong programming terms, not deep misconceptions",
    concept_just="single concept, single chunk",
)

_add(
    topic="algorithm", language="en",
    chunk_id="en_ch12_12-1_p154",
    question=(
        "A flowchart symbol shows a diamond shape at one step, with two "
        "arrows leaving it labeled 'Yes' and 'No'. What does this diamond "
        "represent in the algorithm?"
    ),
    options=[
        ("A conditional branch, where the flow splits based on whether a condition is true or false", True, None),
        ("The start or end point of the algorithm", False, "confuses the conditional-branch symbol with the terminal (start/end) symbol"),
        ("A step that repeats a process multiple times", False, "confuses branching (one-time decision) with looping (repeated execution) -- both control flow, but different symbols and different behavior"),
        ("A step where data is displayed to the user", False, "confuses the conditional-branch symbol with the display/output symbol"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="applies knowledge of flowchart symbol meanings to interpret a described (not shown verbatim) diamond-with-two-labeled-arrows structure",
    distractor_just="distractors reflect real confusion between distinct flowchart symbols with different visual/functional roles",
    concept_just="requires connecting the visual shape, the Yes/No branching, and the general concept of conditional logic",
)

_add(
    topic="algorithm", language="ar",
    chunk_id="ar_ch12_12-1_p167",
    question="ما هو التعريف الأدق لمصطلح 'الخوارزمية'؟",
    options=[
        ("طريقة أو إجراء لحل مشكلة معينة", True, None),
        ("لغة برمجة تُستخدم لكتابة الكود", False, "خلط بين الخوارزمية (الطريقة المجردة) ولغة البرمجة (أداة للتعبير عنها)"),
        ("مخطط يوضح تدفق عملية ما", False, "خلط بين الخوارزمية نفسها والمخطط الانسيابي، وهو أحد طرق تمثيلها بصريًا فقط"),
        ("قائمة بالمتغيرات المستخدمة في البرنامج", False, "خلط بين الخوارزمية ومصطلحات برمجية غير ذات صلة"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="استرجاع مباشر لتعريف الكتاب نفسه",
    distractor_just="المشتتات مصطلحات برمجية قريبة لكن خاطئة، وليست مفاهيم خاطئة عميقة",
    concept_just="مفهوم واحد، مقطع نصي واحد",
)

_add(
    topic="algorithm", language="ar",
    chunk_id="ar_ch12_12-1_p167",
    question=(
        "يظهر أحد رموز المخطط الانسيابي على شكل معين (Diamond)، وله سهمان "
        "خارجان مكتوب عليهما 'نعم' و 'لا'. ماذا يمثل هذا الشكل في الخوارزمية؟"
    ),
    options=[
        ("تفرع شرطي، حيث ينقسم مسار التنفيذ بناءً على تحقق شرط ما من عدمه", True, None),
        ("نقطة بداية أو نهاية الخوارزمية", False, "خلط بين رمز التفرع الشرطي ورمز البداية/النهاية"),
        ("خطوة تُكرر عملية ما عدة مرات", False, "خلط بين التفرع (قرار لمرة واحدة) والتكرار (تنفيذ متكرر) رغم أنهما رمزان مختلفان بسلوك مختلف"),
        ("خطوة يتم فيها عرض بيانات للمستخدم", False, "خلط بين رمز التفرع الشرطي ورمز العرض/الإخراج"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="تطبيق المعرفة بمعاني رموز المخطط الانسيابي لتفسير شكل ماسي موصوف (وليس معروضًا حرفيًا) بسهمين مكتوب عليهما نعم/لا",
    distractor_just="المشتتات تعكس خلطًا حقيقيًا بين رموز مخطط انسيابي مختلفة بأدوار بصرية ووظيفية مختلفة",
    concept_just="يتطلب الربط بين الشكل البصري، التفرع بنعم/لا، والمفهوم العام للمنطق الشرطي",
)

# ============================================================
# VARIABLES AND ASSIGNMENT
# ============================================================

_add(
    topic="variables and assignment", language="en",
    chunk_id="en_ch12_12-2_p158",
    question="What does the following code print?\ncity = 'Cairo'\nprint(city)",
    options=[
        ("Cairo", True, None),
        ("city", False, "confuses the variable name with the value it stores"),
        ("'Cairo'", False, "assumes print() displays the quotes literally, not just the string content"),
        ("An error, because city is not defined", False, "ignores that the assignment on the line above already ran, so city IS defined by the time print() executes"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="recalls what print() and '=' do in a directly-shown example",
    distractor_just="distractors are mostly shallow misunderstandings of syntax, not deep misconceptions",
    concept_just="single concept (assignment then print), single chunk",
)

_add(
    topic="variables and assignment", language="en",
    chunk_id="en_ch12_12-2_p158",
    question="What does the following code print?\nx = 5\nx = x + 3\nprint(x)",
    options=[
        ("8", True, None),
        ("5", False, "assumes the second assignment doesn't take effect, treating x as if it keeps its first value"),
        ("An error, because you can't assign x to itself", False, "confuses '=' (assignment, which evaluates the right side first) with mathematical equality, where x = x + 3 would be a contradiction"),
        ("x + 3", False, "assumes print() shows the unevaluated expression rather than the computed value stored in x"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="requires tracing how a variable's value changes across two sequential assignment statements, not just reading one line",
    distractor_just="the 'x = x + 3 is impossible' distractor reflects a very common real misconception (treating '=' as mathematical equality instead of assignment)",
    concept_just="requires understanding that assignment evaluates right-to-left and that reassigning updates the stored value",
)

_add(
    topic="variables and assignment", language="ar",
    chunk_id="ar_ch12_12-2_p171",
    question="ماذا تطبع الشيفرة التالية؟\ncity = 'Cairo'\nprint(city)",
    options=[
        ("Cairo", True, None),
        ("city", False, "خلط بين اسم المتغير والقيمة المخزنة فيه"),
        ("'Cairo'", False, "افتراض أن print() تعرض علامات الاقتباس حرفيًا وليس محتوى النص فقط"),
        ("خطأ، لأن المتغير city غير معرّف", False, "تجاهل أن سطر الإسناد السابق قد نُفذ بالفعل، لذا فإن city معرّف فعليًا عند تنفيذ print()"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="استرجاع مباشر لوظيفة print() و '=' في مثال معروض مباشرة",
    distractor_just="المشتتات في معظمها سوء فهم سطحي للصياغة وليست مفاهيم خاطئة عميقة",
    concept_just="مفهوم واحد (الإسناد ثم الطباعة)، مقطع نصي واحد",
)

_add(
    topic="variables and assignment", language="ar",
    chunk_id="ar_ch12_12-2_p171",
    question="ماذا تطبع الشيفرة التالية؟\nx = 5\nx = x + 3\nprint(x)",
    options=[
        ("8", True, None),
        ("5", False, "افتراض أن الإسناد الثاني لا ينفذ فعليًا، والتعامل مع x وكأنها تحتفظ بقيمتها الأولى"),
        ("خطأ، لأنه لا يمكن إسناد x إلى نفسها", False, "خلط بين '=' (الإسناد، الذي يُقيّم الطرف الأيمن أولاً) والمساواة الرياضية، حيث تكون x = x + 3 تناقضًا"),
        ("x + 3", False, "افتراض أن print() تعرض التعبير غير المُقيّم بدلاً من القيمة المحسوبة المخزنة في x"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="يتطلب تتبع كيفية تغيّر قيمة المتغير عبر جملتي إسناد متتاليتين، وليس مجرد قراءة سطر واحد",
    distractor_just="المشتت 'x = x + 3 مستحيلة' يعكس مفهومًا خاطئًا شائعًا فعليًا (التعامل مع '=' كمساواة رياضية بدلاً من إسناد)",
    concept_just="يتطلب فهم أن الإسناد يُقيّم من اليمين إلى اليسار وأن إعادة الإسناد تُحدّث القيمة المخزنة",
)

# ============================================================
# LOOPS AND CONDITIONALS
# ============================================================

_add(
    topic="loops and conditionals", language="en",
    chunk_id="en_ch12_12-3_p162",
    question="What does the following code print?\nfor i in range(3):\n    print(i)",
    options=[
        ("0\n1\n2", True, None),
        ("1\n2\n3", False, "assumes range() is 1-indexed, when it actually starts from 0 by default"),
        ("0\n1\n2\n3", False, "off-by-one error: assumes range(3) includes 3, when range(end) stops BEFORE the end value"),
        ("3", False, "assumes the loop only prints the final value of i, not each value during every iteration"),
    ],
    bloom=2, distractor=4, concept=1,
    bloom_just="requires tracing a simple loop's execution, one level above pure recall",
    distractor_just="both off-by-one distractors reflect the single most common real error with range()",
    concept_just="single concept (range() start/stop behavior), single chunk",
)

_add(
    topic="loops and conditionals", language="en",
    chunk_id="en_ch12_12-3_p163",
    question=(
        "What does the following code print?\n"
        "x = 70\n"
        "if x >= 90:\n"
        "    result = 'Grade is A'\n"
        "elif x >= 50:\n"
        "    result = 'Grade is B'\n"
        "else:\n"
        "    result = 'Grade is C'\n"
        "print(result)"
    ),
    options=[
        ("Grade is B", True, None),
        ("Grade is C", False, "assumes elif is only checked if the if condition AND some other condition both fail, rather than running as soon as its own condition is true"),
        ("Grade is A", False, "assumes the condition closest to the variable's actual value wins, rather than evaluating top-to-bottom and stopping at the first true branch"),
        ("Grade is B and Grade is C", False, "assumes elif/else are independent checks like separate if statements, rather than a single chain where only one branch executes"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="applies the if/elif/else rule to predict output for a new input value, not just the exact worked example",
    distractor_just="distractors reflect the real, common misconception that elif/else behave like independent if statements",
    concept_just="single concept (elif short-circuiting) but requires tracing multiple branches",
)

_add(
    topic="loops and conditionals", language="ar",
    chunk_id="ar_ch12_12-3_p175",
    question="ماذا تطبع الشيفرة التالية؟\nfor i in range(3):\n    print(i)",
    options=[
        ("0\n1\n2", True, None),
        ("1\n2\n3", False, "افتراض أن range() تبدأ من 1، بينما هي تبدأ من 0 افتراضيًا"),
        ("0\n1\n2\n3", False, "خطأ إزاحة بواحد: افتراض أن range(3) تشمل 3، بينما range(النهاية) تتوقف قبل قيمة النهاية"),
        ("3", False, "افتراض أن الحلقة تطبع القيمة الأخيرة لـ i فقط، وليس كل قيمة في كل تكرار"),
    ],
    bloom=2, distractor=4, concept=1,
    bloom_just="يتطلب تتبع تنفيذ حلقة بسيطة، أعلى بدرجة واحدة من الاسترجاع المباشر",
    distractor_just="كلا مشتتي خطأ الإزاحة بواحد يعكسان الخطأ الأكثر شيوعًا فعليًا مع range()",
    concept_just="مفهوم واحد (سلوك بداية/نهاية range())، مقطع نصي واحد",
)

_add(
    topic="loops and conditionals", language="ar",
    chunk_id="ar_ch12_12-3_p176",
    question=(
        "ماذا تطبع الشيفرة التالية؟\n"
        "x = 70\n"
        "if x >= 90:\n"
        "    result = 'Grade is A'\n"
        "elif x >= 50:\n"
        "    result = 'Grade is B'\n"
        "else:\n"
        "    result = 'Grade is C'\n"
        "print(result)"
    ),
    options=[
        ("Grade is B", True, None),
        ("Grade is C", False, "افتراض أن elif يُفحص فقط إذا فشل شرط if وشرط آخر معًا، بدلاً من أن ينفذ فور تحقق شرطه الخاص"),
        ("Grade is A", False, "افتراض أن الشرط الأقرب للقيمة الفعلية للمتغير هو الذي يفوز، بدلاً من التقييم من الأعلى للأسفل والتوقف عند أول شرط صحيح"),
        ("Grade is B و Grade is C", False, "افتراض أن elif/else هي فحوصات مستقلة مثل جمل if منفصلة، بدلاً من سلسلة واحدة ينفذ منها فرع واحد فقط"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="تطبيق قاعدة if/elif/else للتنبؤ بالمخرج لقيمة إدخال جديدة، وليس المثال المحلول نفسه فقط",
    distractor_just="المشتتات تعكس مفهومًا خاطئًا شائعًا وحقيقيًا بأن elif/else تتصرف كجمل if مستقلة",
    concept_just="مفهوم واحد (القصر الدائري لـ elif) لكنه يتطلب تتبع عدة فروع",
)

# ============================================================
# LISTS
# ============================================================

_add(
    topic="lists", language="en",
    chunk_id="en_ch12_12-4_p167",
    question="What does the following code print?\na = [10, 20, 30]\nprint(a[1])",
    options=[
        ("20", True, None),
        ("10", False, "assumes list indices start at 1, when Python lists are 0-indexed"),
        ("30", False, "assumes a[1] refers to the 'first' element counted from the end, or miscounts the index"),
        ("[10, 20, 30]", False, "assumes a[1] prints the whole list rather than a single indexed element"),
    ],
    bloom=1, distractor=3, concept=1,
    bloom_just="direct recall of 0-indexing applied to a simple example",
    distractor_just="the 1-indexing distractor reflects a very common real error for anyone coming from 1-indexed languages/math notation",
    concept_just="single concept (list indexing), single chunk",
)

_add(
    topic="lists", language="en",
    chunk_id="en_ch12_12-4_p167",
    question=(
        "What does the following code print?\n"
        "a = [1, 2, 3]\n"
        "a.append(4)\n"
        "print(a[3])"
    ),
    options=[
        ("4", True, None),
        ("3", False, "assumes append() adds the new element at the position matching its VALUE rather than at the end of the list, or miscounts the resulting index"),
        ("An error, because index 3 is out of range", False, "assumes the list is still length 3 after append(), ignoring that append() grows the list by one element"),
        ("[1, 2, 3, 4]", False, "assumes a[3] prints the whole list rather than the single element at index 3"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="requires tracing how append() changes the list's length and contents before evaluating an index into the NEW list",
    distractor_just="the 'index out of range' distractor is a very real error for students who don't track that append() changes the valid index range",
    concept_just="combines two concepts (append() behavior + indexing) rather than either alone",
)

_add(
    topic="lists", language="ar",
    chunk_id="ar_ch12_12-4_p181",
    question="ماذا تطبع الشيفرة التالية؟\na = [10, 20, 30]\nprint(a[1])",
    options=[
        ("20", True, None),
        ("10", False, "افتراض أن فهرسة القوائم تبدأ من 1، بينما قوائم بايثون تبدأ فهرستها من 0"),
        ("30", False, "افتراض أن a[1] تشير إلى العنصر 'الأول' معدودًا من النهاية، أو خطأ في عد الفهرس"),
        ("[10, 20, 30]", False, "افتراض أن a[1] تطبع القائمة بأكملها وليس عنصرًا واحدًا مفهرسًا"),
    ],
    bloom=1, distractor=3, concept=1,
    bloom_just="استرجاع مباشر لمفهوم الفهرسة من الصفر مطبقًا على مثال بسيط",
    distractor_just="مشتت الفهرسة من 1 يعكس خطأً شائعًا فعليًا لدى القادمين من لغات/رياضيات تبدأ فهرستها من 1",
    concept_just="مفهوم واحد (فهرسة القوائم)، مقطع نصي واحد",
)

_add(
    topic="lists", language="ar",
    chunk_id="ar_ch12_12-4_p181",
    question=(
        "ماذا تطبع الشيفرة التالية؟\n"
        "a = [1, 2, 3]\n"
        "a.append(4)\n"
        "print(a[3])"
    ),
    options=[
        ("4", True, None),
        ("3", False, "افتراض أن append() تضيف العنصر الجديد في موضع يطابق قيمته وليس في نهاية القائمة، أو خطأ في عد الفهرس الناتج"),
        ("خطأ، لأن الفهرس 3 خارج النطاق", False, "افتراض أن طول القائمة لا يزال 3 بعد append()، متجاهلاً أن append() تزيد طول القائمة بعنصر واحد"),
        ("[1, 2, 3, 4]", False, "افتراض أن a[3] تطبع القائمة بأكملها وليس العنصر الواحد عند الفهرس 3"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="يتطلب تتبع كيف تغيّر append() طول القائمة ومحتواها قبل تقييم فهرس في القائمة الجديدة",
    distractor_just="مشتت 'الفهرس خارج النطاق' خطأ حقيقي فعلاً لمن لا يتتبع أن append() تغيّر نطاق الفهرسة الصالح",
    concept_just="يجمع بين مفهومين (سلوك append() + الفهرسة) بدلاً من أحدهما فقط",
)

# ============================================================
# FUNCTIONS
# ============================================================

_add(
    topic="functions", language="en",
    chunk_id="en_ch12_12-5_p171",
    question=(
        "What does the following code print?\n"
        "def greet():\n"
        "    return 'Hello'\n"
        "print(greet())"
    ),
    options=[
        ("Hello", True, None),
        ("greet()", False, "assumes print() shows the function call as text rather than calling it and printing its return value"),
        ("Nothing is printed", False, "assumes defining a function with return doesn't produce an output unless print() is used INSIDE the function"),
        ("An error, because greet() has no arguments", False, "assumes all functions must take arguments, when a function can legitimately take zero"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="direct recall of how return + print(function_call()) work together",
    distractor_just="distractors are plausible surface confusions about function calls, not deep misconceptions",
    concept_just="single concept (define, call, return), single chunk",
)

_add(
    topic="functions", language="en",
    chunk_id="en_ch12_12-5_p171",
    question=(
        "What does the following code print?\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "result = add(3, 4)\n"
        "result = add(result, 2)\n"
        "print(result)"
    ),
    options=[
        ("9", True, None),
        ("7", False, "stops tracing after the first call to add(), ignoring that result is reassigned by the second call"),
        ("An error, because result is used before it's fully defined", False, "assumes result can't be passed into a function call that also reassigns result, when the right side is fully evaluated before the assignment happens"),
        ("3427", False, "assumes + concatenates the arguments as text/digits rather than performing numeric addition"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="requires tracing a function called twice, where the second call's argument depends on the first call's result",
    distractor_just="the 'error, used before defined' distractor reflects a real misunderstanding of assignment evaluation order",
    concept_just="combines function calls, return values, and variable reassignment across two lines",
)

_add(
    topic="functions", language="ar",
    chunk_id="ar_ch12_12-5_p185",
    question=(
        "ماذا تطبع الشيفرة التالية؟\n"
        "def greet():\n"
        "    return 'Hello'\n"
        "print(greet())"
    ),
    options=[
        ("Hello", True, None),
        ("greet()", False, "افتراض أن print() تعرض استدعاء الدالة كنص بدلاً من استدعائها وطباعة القيمة المُرجعة"),
        ("لا شيء يُطبع", False, "افتراض أن تعريف دالة تستخدم return لا ينتج عنه أي مخرج إلا إذا استُخدمت print() داخل الدالة"),
        ("خطأ، لأن greet() لا تأخذ وسائط", False, "افتراض أن جميع الدوال يجب أن تأخذ وسائط، بينما يمكن لدالة ألا تأخذ أي وسيط"),
    ],
    bloom=1, distractor=2, concept=1,
    bloom_just="استرجاع مباشر لكيفية عمل return و print(استدعاء_الدالة()) معًا",
    distractor_just="المشتتات هي حالات لبس سطحية معقولة حول استدعاء الدوال، وليست مفاهيم خاطئة عميقة",
    concept_just="مفهوم واحد (تعريف، استدعاء، إرجاع)، مقطع نصي واحد",
)

_add(
    topic="functions", language="ar",
    chunk_id="ar_ch12_12-5_p185",
    question=(
        "ماذا تطبع الشيفرة التالية؟\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "result = add(3, 4)\n"
        "result = add(result, 2)\n"
        "print(result)"
    ),
    options=[
        ("9", True, None),
        ("7", False, "توقف عن التتبع بعد أول استدعاء لـ add()، متجاهلاً أن result يُعاد إسنادها بالاستدعاء الثاني"),
        ("خطأ، لأن result تُستخدم قبل تعريفها بالكامل", False, "افتراض أن result لا يمكن تمريرها إلى استدعاء دالة يعيد إسنادها أيضًا، بينما يُقيَّم الطرف الأيمن بالكامل قبل حدوث الإسناد"),
        ("3427", False, "افتراض أن + تُلحق الوسيطتين كنص/أرقام بدلاً من إجراء جمع عددي"),
    ],
    bloom=3, distractor=4, concept=2,
    bloom_just="يتطلب تتبع دالة تُستدعى مرتين، حيث تعتمد وسيطة الاستدعاء الثاني على نتيجة الاستدعاء الأول",
    distractor_just="مشتت 'خطأ، تُستخدم قبل تعريفها' يعكس سوء فهم حقيقي لترتيب تقييم الإسناد",
    concept_just="يجمع بين استدعاء الدوال، القيم المُرجعة، وإعادة إسناد المتغير عبر سطرين",
)


# --------------------------------------------------------------------
# Public retrieval function -- this is what get_next_question.py's
# GenerationUnavailable handler (once wired up) should call.
# --------------------------------------------------------------------

def _select_by_difficulty(candidates: list[QuestionOut], difficulty: int) -> QuestionOut:
    """With only 2 pre-written tiers per topic (easy/hard), map the
    requested 1-5 difficulty onto one of them: difficulty >= 3 gets
    the harder question, difficulty < 3 gets the easier one. Crude,
    but honest about the pool's real size -- a student's exam won't
    get a mismatched-difficulty backup question silently, it gets the
    closer of the two available, on a documented, simple rule.
    Candidates are stored [easy, hard] by _add()'s append order.
    """
    if len(candidates) == 1:
        return candidates[0]
    easy, hard = candidates[0], candidates[1]
    return hard if difficulty >= 3 else easy


def get_backup_question(topic: str, language: str, difficulty: int = 3) -> QuestionOut | None:
    """Retrieve one backup question for this topic/language, or None
    if the pool has nothing for this (topic, language) pair -- caller
    should treat None as a genuine "nothing we can do" case (e.g. skip
    the topic, or show a graceful error) since there's no further
    fallback below this.

    Each call returns a fresh copy (Pydantic's .model_copy()) so
    callers can freely mutate the result (e.g. shuffle option order
    for anti-cheat) without affecting the shared pool for other
    students.
    """
    candidates = _POOL.get((topic, language))
    if not candidates:
        return None
    chosen = _select_by_difficulty(candidates, difficulty)
    return chosen.model_copy(deep=True)


def pool_coverage() -> dict[str, int]:
    """How many backup questions exist per (topic, language) --
    useful for a quick completeness check without printing every
    question. Real, current counts: 2 per topic per language (20
    total) -- see module docstring for why this is smaller than the
    roadmap's 15-20/topic target, and how to extend it."""
    return {f"{topic} ({language})": len(qs) for (topic, language), qs in _POOL.items()}


if __name__ == "__main__":
    print("=" * 70)
    print("A5 — BACKUP QUESTION POOL")
    print("=" * 70)

    coverage = pool_coverage()
    print(f"\nPool coverage ({sum(coverage.values())} total questions):")
    for key, count in coverage.items():
        print(f"  {key:40s} {count}")

    print("\n" + "=" * 70)
    print("Retrieval checks: every (topic, language) x difficulty tier")
    print("=" * 70)
    topics = ["algorithm", "variables and assignment", "loops and conditionals", "lists", "functions"]
    for language in ("en", "ar"):
        for topic in topics:
            for difficulty in (1, 4):
                q = get_backup_question(topic, language, difficulty)
                assert q is not None, f"MISSING: {topic}/{language}/{difficulty}"
                assert q.validated is True
                preview = q.question.split("\n")[0][:50]
                print(f"  {topic:26s} {language} diff={difficulty} -> {preview}...")

    print("\n" + "=" * 70)
    print("Edge case: topic/language with no backup questions -> None, not a crash")
    print("=" * 70)
    result = get_backup_question("nonexistent topic", "en")
    print(f"  get_backup_question('nonexistent topic', 'en') -> {result}")
    assert result is None

    print("\n" + "=" * 70)
    print("Schema validity: every question already passed QuestionOut's")
    print("own validators at import time (exactly-one-correct,")
    print("misconception-required, 4 distinct options) -- if this script")
    print("ran at all, that's already proven. Double-checking explicitly:")
    print("=" * 70)
    total = 0
    for (topic, language), qs in _POOL.items():
        for q in qs:
            total += 1
            correct_count = sum(1 for o in q.options if o.correct)
            assert correct_count == 1
            assert len(q.options) == 4
            assert q.source_chunk_id.startswith(f"{language}_ch12_")
    print(f"  ✓ All {total} questions independently re-verified.")

    print("\n✓ All A5 backup pool checks passed.")
