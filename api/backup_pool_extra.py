"""Additional hand-authored backup questions (3 per topic, in EN and AR).

Why this exists: the original pool had exactly 2 questions per topic/language,
chosen only by difficulty, so whenever live generation was unavailable every
student -- and every retake -- got the identical 5 questions.

Each entry below is authored once with an English and an Arabic rendering and
registered through backup_pool._add(), so the same import-time schema
validation applies (exactly one correct option, misconception on every wrong
option, four options). Every "What does the following code print?" question is
additionally executed by tests/test_backup_pool.py, which asserts that the
option marked correct is exactly what Python prints -- so none of these rely on
a human having traced the code correctly.

Grounding: each question points at a real chunk_id whose page covers the
concept (checked against chunks_en.json / chunks_ar.json).
"""

from __future__ import annotations

from typing import Callable

_STEM_EN = "What does the following code print?\n"
_STEM_AR = "ماذا تطبع الشيفرة التالية؟\n"

# Option tuple: (text_en, text_ar, is_correct, misconception_en, misconception_ar)
# Outputs of code are language-neutral, so text_ar may be None (= same as text_en).


def _opts(rows):
    en, ar = [], []
    for text_en, text_ar, correct, mis_en, mis_ar in rows:
        en.append((text_en, correct, None if correct else mis_en))
        ar.append((text_ar or text_en, correct, None if correct else (mis_ar or mis_en)))
    return en, ar


def register(add: Callable[..., None]) -> None:
    def both(
        *,
        topic: str,
        chunk_en: str,
        chunk_ar: str,
        stem_en: str,
        stem_ar: str,
        options,
        bloom: int,
        distractor: int,
        concept: int,
        just_en: tuple[str, str, str],
        just_ar: tuple[str, str, str],
    ) -> None:
        en_opts, ar_opts = _opts(options)
        add(
            topic=topic, language="en", chunk_id=chunk_en, question=stem_en, options=en_opts,
            bloom=bloom, distractor=distractor, concept=concept,
            bloom_just=just_en[0], distractor_just=just_en[1], concept_just=just_en[2],
        )
        add(
            topic=topic, language="ar", chunk_id=chunk_ar, question=stem_ar, options=ar_opts,
            bloom=bloom, distractor=distractor, concept=concept,
            bloom_just=just_ar[0], distractor_just=just_ar[1], concept_just=just_ar[2],
        )

    def code(topic, chunk_en, chunk_ar, snippet, options, bloom, distractor, concept, just_en, just_ar):
        both(
            topic=topic, chunk_en=chunk_en, chunk_ar=chunk_ar,
            stem_en=_STEM_EN + snippet, stem_ar=_STEM_AR + snippet,
            options=options, bloom=bloom, distractor=distractor, concept=concept,
            just_en=just_en, just_ar=just_ar,
        )

    # ================================================================
    # ALGORITHM
    # ================================================================

    both(
        topic="algorithm", chunk_en="en_ch12_12-1_p157", chunk_ar="ar_ch12_12-1_p170",
        stem_en="Which type of diagram is best suited to showing parallel process flows?",
        stem_ar="أي نوع من المخططات هو الأنسب لتمثيل تدفق العمليات المتوازية؟",
        options=[
            ("An activity diagram", "مخطط النشاط", True, None, None),
            ("A flowchart", "مخطط انسيابي", False,
             "confuses the flowchart, which suits a single process flow, with the activity diagram used for parallel flows",
             "خلط بين المخطط الانسيابي المناسب لتدفق عملية واحدة ومخطط النشاط المناسب للعمليات المتوازية"),
            ("Source code", "الشيفرة المصدرية", False,
             "confuses a visual diagram of an algorithm with the text of a program",
             "خلط بين مخطط مرئي لخوارزمية ونص البرنامج"),
            ("A machine-language listing", "قائمة بلغة الآلة", False,
             "confuses a diagram of an algorithm with the 0s-and-1s form a computer executes",
             "خلط بين مخطط يمثل خوارزمية والصيغة المكوّنة من الأصفار والواحدات التي ينفذها الحاسوب"),
        ],
        bloom=2, distractor=3, concept=2,
        just_en=("recalls which diagram suits parallel flows and separates it from a similar one",
                 "the flowchart distractor is the realistic near-miss: same family, different use",
                 "two related diagram types must be told apart"),
        just_ar=("استرجاع نوع المخطط المناسب للتدفق المتوازي والتمييز بينه وبين مخطط مشابه",
                 "مشتت المخطط الانسيابي هو الخطأ القريب الواقعي: نفس العائلة باستخدام مختلف",
                 "يجب التمييز بين نوعين متقاربين من المخططات"),
    )

    both(
        topic="algorithm", chunk_en="en_ch12_12-1_p155", chunk_ar="ar_ch12_12-1_p169",
        stem_en=("A flowchart for pedestrians reads: \"Proceed if the signal is green; otherwise, stop.\" "
                 "What kind of control structure does this describe?"),
        stem_ar=("يقول مخطط انسيابي للمشاة: \"تابع السير إذا كانت الإشارة خضراء، وإلا فتوقف\". "
                 "ما نوع هيكل التحكم الذي يصفه هذا المخطط؟"),
        options=[
            ("A branching (conditional) structure", "هيكل متفرع (شرطي)", True, None, None),
            ("A repetition (loop) structure", "هيكل تكراري (حلقة)", False,
             "confuses a one-time decision with repeated execution of a step",
             "خلط بين قرار يُتخذ مرة واحدة وتكرار تنفيذ خطوة ما"),
            ("A data input/output step", "خطوة إدخال/إخراج بيانات", False,
             "confuses making a decision with reading or displaying data",
             "خلط بين اتخاذ قرار وقراءة البيانات أو عرضها"),
            ("A terminal step that ends the algorithm", "خطوة طرفية تنهي الخوارزمية", False,
             "confuses a decision with the start/end symbol",
             "خلط بين القرار ورمز البداية/النهاية"),
        ],
        bloom=3, distractor=3, concept=2,
        just_en=("applies the idea of branching to a described real-world rule",
                 "distractors are the other flowchart step types students really mix up",
                 "single concept, recognised from a scenario rather than a definition"),
        just_ar=("تطبيق فكرة التفرع على قاعدة واقعية موصوفة",
                 "المشتتات هي أنواع خطوات المخطط الأخرى التي يخلط الطلاب بينها فعلاً",
                 "مفهوم واحد يُتعرَّف عليه من سيناريو وليس من تعريف"),
    )

    both(
        topic="algorithm", chunk_en="en_ch12_12-1_p156", chunk_ar="ar_ch12_12-1_p169",
        stem_en="Which sequence correctly describes how a problem ends up being solved by a computer?",
        stem_ar="أي تسلسل يصف بشكل صحيح كيف تُحَل مشكلة ما بواسطة الحاسوب؟",
        options=[
            ("Design an algorithm, write a program in a programming language, translate it into machine language, then the computer executes it",
             "تصميم خوارزمية، ثم كتابة برنامج بلغة برمجة، ثم ترجمته إلى لغة الآلة، ثم ينفذه الحاسوب",
             True, None, None),
            ("Write machine language, design an algorithm, write a program in a programming language, then the computer executes it",
             "كتابة لغة الآلة، ثم تصميم خوارزمية، ثم كتابة برنامج بلغة برمجة، ثم ينفذه الحاسوب",
             False,
             "reverses the order: machine language is the final translated form, not the first thing written",
             "عكس للترتيب: لغة الآلة هي الصيغة النهائية المترجمة وليست أول ما يُكتب"),
            ("Write a program in a programming language, design an algorithm, translate it into machine language, then the computer executes it",
             "كتابة برنامج بلغة برمجة، ثم تصميم خوارزمية، ثم ترجمته إلى لغة الآلة، ثم ينفذه الحاسوب",
             False,
             "believes a program can be written before the method (algorithm) it implements has been designed",
             "الاعتقاد بأن البرنامج يمكن كتابته قبل تصميم الطريقة (الخوارزمية) التي ينفذها"),
            ("Design an algorithm, translate it into machine language, write a program in a programming language, then the computer executes it",
             "تصميم خوارزمية، ثم ترجمتها إلى لغة الآلة، ثم كتابة برنامج بلغة برمجة، ثم ينفذه الحاسوب",
             False,
             "swaps the programming and translation steps; translation is applied to the finished program",
             "تبديل خطوتي البرمجة والترجمة؛ فالترجمة تُطبَّق على البرنامج المكتمل"),
        ],
        bloom=4, distractor=4, concept=4,
        just_en=("requires ordering four related stages, not recalling one term",
                 "each distractor is a plausible reordering of the same four stages",
                 "connects algorithm, programming language and machine language in one chain"),
        just_ar=("يتطلب ترتيب أربع مراحل مترابطة وليس استرجاع مصطلح واحد",
                 "كل مشتت هو إعادة ترتيب معقولة للمراحل الأربع نفسها",
                 "يربط الخوارزمية ولغة البرمجة ولغة الآلة في سلسلة واحدة"),
    )

    # ================================================================
    # VARIABLES AND ASSIGNMENT
    # ================================================================

    code(
        "variables and assignment", "en_ch12_12-2_p159", "ar_ch12_12-2_p172",
        "a = 6\nprint(a * 5)",
        [
            ("30", None, True, None, None),
            ("11", None, False, "confuses * (multiplication) with + (addition)",
             "خلط بين * (الضرب) و + (الجمع)"),
            ("65", None, False, "treats * as joining the two numbers side by side instead of multiplying them",
             "التعامل مع * كأنها تضع الرقمين جنبًا إلى جنب بدل ضربهما"),
            ("a * 5", None, False, "assumes print() shows the expression as text rather than its computed value",
             "افتراض أن print() تعرض التعبير كنص بدل قيمته المحسوبة"),
        ],
        2, 2, 1,
        ("applies * to a stored value in a short worked example",
         "distractors are shallow operator/print misunderstandings",
         "single concept: arithmetic on a variable"),
        ("تطبيق * على قيمة مخزنة في مثال قصير",
         "المشتتات سوء فهم سطحي للمعاملات وprint",
         "مفهوم واحد: العمليات الحسابية على متغير"),
    )

    code(
        "variables and assignment", "en_ch12_12-2_p160", "ar_ch12_12-2_p173",
        "a = 7\nprint(a // 2)\nprint(a % 2)",
        [
            ("3\n1", None, True, None, None),
            ("3.5\n1", None, False, "treats // as ordinary division instead of floor division",
             "التعامل مع // كقسمة عادية بدل القسمة الصحيحة"),
            ("4\n1", None, False, "assumes // rounds up or to nearest instead of discarding the remainder",
             "افتراض أن // تقرّب للأعلى أو لأقرب عدد بدل إهمال الباقي"),
            ("1\n3", None, False, "swaps the roles of // (quotient) and % (remainder)",
             "تبديل دوري // (خارج القسمة) و % (الباقي)"),
        ],
        3, 3, 3,
        ("must evaluate two different integer operators on the same value",
         "each distractor is a real operator mix-up",
         "combines floor division and remainder"),
        ("يجب تقييم معاملين صحيحين مختلفين على القيمة نفسها",
         "كل مشتت هو خلط حقيقي بين المعاملات",
         "يجمع بين القسمة الصحيحة والباقي"),
    )

    code(
        "variables and assignment", "en_ch12_12-2_p158", "ar_ch12_12-2_p171",
        "x = 4\ny = x\nx = x + 10\nprint(y)",
        [
            ("4", None, True, None, None),
            ("14", None, False, "assumes y stays linked to x and follows it when x changes, instead of keeping the value copied at assignment",
             "افتراض أن y تبقى مرتبطة بـ x وتتبعها عند تغيّرها بدل الاحتفاظ بالقيمة المنسوخة وقت الإسناد"),
            ("10", None, False, "confuses the amount added to x with the value stored in y",
             "خلط بين المقدار المضاف إلى x والقيمة المخزنة في y"),
            ("18", None, False, "adds the old and new values of x together",
             "جمع القيمة القديمة والجديدة لـ x معًا"),
        ],
        4, 4, 3,
        ("requires tracing three assignments and knowing which value y captured",
         "the 'y follows x' distractor is a very common real misconception",
         "tests that assignment copies a value rather than linking variables"),
        ("يتطلب تتبع ثلاث جمل إسناد ومعرفة أي قيمة التقطتها y",
         "مشتت 'y تتبع x' مفهوم خاطئ شائع فعليًا",
         "يختبر أن الإسناد ينسخ قيمة ولا يربط بين المتغيرات"),
    )

    # ================================================================
    # LOOPS AND CONDITIONALS
    # ================================================================

    code(
        "loops and conditionals", "en_ch12_12-3_p164", "ar_ch12_12-3_p178",
        "total = 0\nfor i in range(1, 4):\n    total = total + i\nprint(total)",
        [
            ("6", None, True, None, None),
            ("10", None, False, "off-by-one: assumes range(1, 4) includes 4",
             "خطأ إزاحة بواحد: افتراض أن range(1, 4) تشمل 4"),
            ("3", None, False, "assumes only the last value of i is reported rather than the accumulated total",
             "افتراض أن القيمة الأخيرة لـ i فقط هي التي تُطبع وليس المجموع المتراكم"),
            ("0", None, False, "assumes total is never updated inside the loop",
             "افتراض أن total لا يتم تحديثها داخل الحلقة"),
        ],
        2, 3, 2,
        ("traces a short accumulator loop",
         "the 10 distractor is the classic range() off-by-one",
         "range() bounds plus accumulation"),
        ("تتبع حلقة تجميع قصيرة",
         "مشتت 10 هو خطأ الإزاحة بواحد الكلاسيكي مع range()",
         "حدود range() مع التجميع"),
    )

    code(
        "loops and conditionals", "en_ch12_12-3_p163", "ar_ch12_12-3_p177",
        "x = 50\nif x >= 50:\n    print('A')\nif x >= 30:\n    print('B')\nelse:\n    print('C')",
        [
            ("A\nB", None, True, None, None),
            ("A", None, False, "treats two separate if statements as one chain where only the first true branch runs",
             "التعامل مع جملتي if منفصلتين كسلسلة واحدة لا ينفذ منها إلا أول فرع صحيح"),
            ("A\nB\nC", None, False, "assumes the else branch always runs in addition to the if branches",
             "افتراض أن فرع else ينفذ دائمًا إضافةً إلى فروع if"),
            ("A\nC", None, False, "attaches the else to the first if instead of the second",
             "ربط else بأول if بدل الثاني"),
        ],
        3, 4, 3,
        ("traces two independent conditionals and an else",
         "distractors reflect common if/else scoping mistakes",
         "separate if statements versus an if/elif chain"),
        ("تتبع شرطين مستقلين مع else",
         "المشتتات تعكس أخطاء شائعة في نطاق if/else",
         "جمل if المنفصلة مقابل سلسلة if/elif"),
    )

    code(
        "loops and conditionals", "en_ch12_12-3_p166", "ar_ch12_12-3_p180",
        "count = 0\nfor i in range(5):\n    if i % 2 == 0:\n        count = count + 1\nprint(count)",
        [
            ("3", None, True, None, None),
            ("2", None, False, "counts odd values or assumes i starts at 1",
             "عدّ القيم الفردية أو افتراض أن i تبدأ من 1"),
            ("5", None, False, "ignores the if and counts every iteration",
             "تجاهل if وعدّ كل تكرار"),
            ("6", None, False, "sums the even values of i instead of counting them",
             "جمع القيم الزوجية لـ i بدل عدّها"),
        ],
        4, 4, 3,
        ("combines a loop, a modulo test and a counter in one trace",
         "each distractor is a distinct, realistic tracing error",
         "loop plus conditional plus remainder"),
        ("يجمع حلقة واختبار باقي القسمة وعدّادًا في تتبع واحد",
         "كل مشتت خطأ تتبع مختلف وواقعي",
         "حلقة مع شرط مع باقي القسمة"),
    )

    # ================================================================
    # LISTS
    # ================================================================

    code(
        "lists", "en_ch12_12-4_p168", "ar_ch12_12-4_p182",
        "a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]\nprint(a[2][1])",
        [
            ("8", None, True, None, None),
            ("6", None, False, "swaps row and column: reads a[1][2] instead of a[2][1]",
             "تبديل الصف والعمود: قراءة a[1][2] بدل a[2][1]"),
            ("4", None, False, "counts rows and columns from 1 instead of 0",
             "عدّ الصفوف والأعمدة من 1 بدل 0"),
            ("5", None, False, "counts only the row index from 1, treating a[2] as the second row",
             "عدّ فهرس الصف فقط من 1 واعتبار a[2] الصف الثاني"),
        ],
        2, 3, 2,
        ("reads one element of a two-dimensional list",
         "distractors are the three classic 2D-indexing slips",
         "row/column indexing from zero"),
        ("قراءة عنصر واحد من قائمة ثنائية الأبعاد",
         "المشتتات هي الأخطاء الثلاثة الكلاسيكية في فهرسة القوائم الثنائية",
         "فهرسة الصف/العمود من الصفر"),
    )

    code(
        "lists", "en_ch12_12-4_p169", "ar_ch12_12-4_p183",
        "a = [2, 4, 6]\ns = 0\nfor i in range(0, 3, 1):\n    s = s + a[i]\nprint(s)",
        [
            ("12", None, True, None, None),
            ("3", None, False, "adds the indices 0 + 1 + 2 rather than the list elements",
             "جمع الفهارس 0 + 1 + 2 بدل عناصر القائمة"),
            ("6", None, False, "off-by-one: assumes range(0, 3) skips the last index",
             "خطأ إزاحة بواحد: افتراض أن range(0, 3) تتخطى آخر فهرس"),
            ("10", None, False, "assumes the loop starts at index 1 and skips the first element",
             "افتراض أن الحلقة تبدأ من الفهرس 1 وتتخطى العنصر الأول"),
        ],
        3, 3, 3,
        ("traces a loop that reads list elements by index",
         "distractors are index-versus-element and off-by-one errors",
         "combines range(), indexing and accumulation"),
        ("تتبع حلقة تقرأ عناصر القائمة بالفهرس",
         "المشتتات أخطاء الفهرس مقابل العنصر والإزاحة بواحد",
         "يجمع بين range() والفهرسة والتجميع"),
    )

    code(
        "lists", "en_ch12_12-4_p168", "ar_ch12_12-4_p182",
        "a = [34, 52, 11, 40, 17]\nsmallest = a[0]\nfor i in range(1, 5, 1):\n    if a[i] < smallest:\n        smallest = a[i]\nprint(smallest)",
        [
            ("11", None, True, None, None),
            ("17", None, False, "assumes the last element is the minimum",
             "افتراض أن العنصر الأخير هو الأصغر"),
            ("34", None, False, "assumes the starting value is never replaced, so the running minimum never updates",
             "افتراض أن القيمة الابتدائية لا تُستبدل أبدًا فلا يتحدث الحد الأدنى"),
            ("52", None, False, "confuses finding the minimum with finding the maximum by reading < as >",
             "خلط بين إيجاد الحد الأدنى وإيجاد الحد الأقصى بقراءة < على أنها >"),
        ],
        4, 3, 4,
        ("traces the running-minimum pattern across a whole list",
         "distractors are the standard minimum-search errors",
         "requires understanding update-if-smaller over a loop"),
        ("تتبع نمط الحد الأدنى المتحرك عبر قائمة كاملة",
         "المشتتات هي أخطاء البحث عن الحد الأدنى المعتادة",
         "يتطلب فهم التحديث إذا كانت القيمة أصغر ضمن حلقة"),
    )

    # ================================================================
    # FUNCTIONS
    # ================================================================

    code(
        "functions", "en_ch12_12-5_p172", "ar_ch12_12-5_p186",
        "def circle(r):\n    S = r * r * 3.14\n    return S\na = circle(5)\nprint(a)",
        [
            ("78.5", None, True, None, None),
            ("25", None, False, "forgets to multiply by 3.14",
             "نسيان الضرب في 3.14"),
            ("15.7", None, False, "uses r instead of r * r (5 * 3.14)",
             "استخدام r بدل r * r (أي 5 * 3.14)"),
            ("S", None, False, "assumes print() shows the variable name rather than the value that was returned",
             "افتراض أن print() تعرض اسم المتغير بدل القيمة المُرجعة"),
        ],
        2, 3, 2,
        ("follows a single call to a small function",
         "distractors are formula-transcription slips",
         "argument passing and return value"),
        ("متابعة استدعاء واحد لدالة صغيرة",
         "المشتتات أخطاء في نقل الصيغة",
         "تمرير الوسيطة والقيمة المُرجعة"),
    )

    code(
        "functions", "en_ch12_12-5_p173", "ar_ch12_12-5_p187",
        "def area(base, height):\n    S = base * height / 2\n    return S\na = area(10, 5)\nb = area(6, 7)\nprint(a)\nprint(b)",
        [
            ("25.0\n21.0", None, True, None, None),
            ("50\n42", None, False, "forgets the / 2 in the triangle-area formula",
             "نسيان القسمة على 2 في صيغة مساحة المثلث"),
            ("25.0\n25.0", None, False, "assumes the second call reuses the first call's result",
             "افتراض أن الاستدعاء الثاني يعيد استخدام نتيجة الأول"),
            ("An error, because area() is called twice", "خطأ، لأن area() تُستدعى مرتين", False,
             "assumes a function can only be called once",
             "افتراض أن الدالة لا يمكن استدعاؤها إلا مرة واحدة"),
        ],
        3, 3, 3,
        ("traces two calls with different arguments",
         "the reuse-previous-result distractor is a genuine misconception",
         "multiple arguments, return value, and float division"),
        ("تتبع استدعاءين بوسائط مختلفة",
         "مشتت إعادة استخدام النتيجة السابقة مفهوم خاطئ حقيقي",
         "وسائط متعددة وقيمة مُرجعة وقسمة عشرية"),
    )

    code(
        "functions", "en_ch12_12-5_p172", "ar_ch12_12-5_p186",
        "def add(a, b):\n    total = a + b\n\nresult = add(2, 3)\nprint(result)",
        [
            ("None", None, True, None, None),
            ("5", None, False, "assumes a function automatically returns the last value it computed, without a return statement",
             "افتراض أن الدالة تُرجع تلقائيًا آخر قيمة حسبتها دون جملة return"),
            ("0", None, False, "assumes a function without return gives back 0",
             "افتراض أن الدالة بلا return تُرجع 0"),
            ("An error, because total is not defined outside add()", "خطأ، لأن total غير معرّفة خارج add()", False,
             "assumes the program breaks because of total's scope, though the code never uses total outside the function",
             "افتراض أن البرنامج يفشل بسبب نطاق total رغم أن الشيفرة لا تستخدمها خارج الدالة"),
        ],
        4, 4, 4,
        ("predicts behaviour when the return statement is missing",
         "the 'returns the last value' distractor is a very common misconception",
         "distinguishes computing a value inside a function from returning it"),
        ("التنبؤ بالسلوك عند غياب جملة return",
         "مشتت 'تُرجع آخر قيمة' مفهوم خاطئ شائع جدًا",
         "التمييز بين حساب قيمة داخل الدالة وإرجاعها"),
    )
