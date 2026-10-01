# نتائج التقييم — مِرآة

- التاريخ: 2026-10-01 11:58 UTC · الحالات: 47 (تغيّر مزروع 28 · سليمة المعنى 15 · امتناع 4) · التشغيلات: 3
- النماذج: الشاهد الأول `claude-sonnet-5-5`، الشاهد الثاني `claude-haiku-4-5`
- البذور **مسودة لم تراجعها المطوّرة بعد**، والحالات مولّدة آلياً: الأرقام أولية وتُقرأ مع قسم الحدود.
- الأرقام بصيغة «المتوسط (الأدنى–الأعلى)» عبر التشغيلات؛ والحالات المتأثرة بأعطال مستبعدة ومذكورة أدناه.

## ملخص

| المقياس | مِرآة | خط الأساس (chrF < 50 أو الطول < 65٪) |
|---|---|---|
| كشف التغيّر المزروع (أي تنبيه مطابق) | 96٪ | 14٪ |
| إنذارات كاذبة على الصياغات السليمة (الأنواع المقيسة) | 44٪ (40٪–47٪) | 73٪ |
| إنذارات كاذبة على السليمة (أي تنبيه أحمر/أصفر، مع امتحان القارئ) | 47٪ (40٪–53٪) | — |
| صحة الامتناع («غير متحقق» + العبارة الثابتة) | 100٪ | — |
| الثبات: الحالة تعطي مجموعة التنبيهات نفسها في كل التشغيلات | 77٪ | — |
| اتفاق الشاهدين (الحقول المؤثرة) | 47٪ | — |
| متوسط chrF: حالات التغيّر / السليمة | — | 78.8 / 44.2 |
| الزمن لكل جملة (متوسط التشغيلات بلا cache) | 18.5 ث | — |
| التكلفة لكل 1000 جملة (سجل tokens للتشغيلات بلا cache) | $40 | ~0 |

## الاستدعاء والدقة لكل نوع (مجمّعة عبر التشغيلات الصالحة)

| النوع | المرات | الاستدعاء | الدقة | إنذارات كاذبة |
|---|---|---|---|---|
| `attribution_upgraded` | 3 | 0٪ | — | 0 |
| `exception_dropped` | 3 | 0٪ | — | 0 |
| `scope_widened` | 9 | 78٪ | 64٪ | 4 |
| `certainty_raised` | 3 | 100٪ | 33٪ | 6 |
| `condition_dropped` | 12 | 100٪ | 75٪ | 4 |
| `consensus_inflated` | 6 | 100٪ | 100٪ | 0 |
| `hadith_grade_dropped` | 3 | 100٪ | 100٪ | 0 |
| `hasr_lost` | 3 | 100٪ | 100٪ | 0 |
| `negation_mismatch` | 12 | 100٪ | 44٪ | 15 |
| `new_prophetic_attribution` | 3 | 100٪ | 100٪ | 0 |
| `number_mismatch` | 6 | 100٪ | 40٪ | 9 |
| `ruling_shift` | 15 | 100٪ | 71٪ | 6 |
| `term_narrowing` | 6 | 100٪ | 67٪ | 3 |
| `unverified_attribution` | 8 | 100٪ | 73٪ | 3 |
| `quote_wording_differs` | 0 | — | 0٪ | 3 |
| `scope_narrowed` | 0 | — | 0٪ | 5 |

«المرات» = مرات ظهور التغيّر المزروع عبر التشغيلات (الحالة × التشغيل). الأنواع ذات المرات القليلة لا يُعتمد عليها إحصائياً.

## خط الأساس مقابل مِرآة لكل حالة تغيّر

درجات chrF المرتفعة مع تغيّر المعنى تعني أن المقاييس السطحية لا ترى الخلل.

| الحالة | التغيّر المزروع | chrF | نسبة الطول | خط الأساس كشفه؟ | مِرآة كشفته (في كم تشغيل) |
|---|---|---|---|---|---|
| s01-condition_dropped | condition_dropped | 87.7 | 0.93 | ❌ | 3/3 |
| s01-scope_widened | scope_widened | 86.8 | 1.0 | ❌ | 3/3 |
| s01-ruling_shift | ruling_shift | 92.5 | 1.0 | ❌ | 3/3 |
| s02-number_mismatch | number_mismatch | 91.2 | 1.0 | ❌ | 3/3 |
| s02-ruling_shift | ruling_shift | 83.2 | 1.0 | ❌ | 3/3 |
| s02-consensus_inflated | consensus_inflated | 79.6 | 0.85 | ❌ | 3/3 |
| s03-negation_mismatch | negation_mismatch | 92.9 | 0.95 | ❌ | 3/3 |
| s03-condition_dropped | condition_dropped | 62.8 | 0.58 | ✅ | 3/3 |
| s04-attribution_upgraded | attribution_upgraded | 81.9 | 0.78 | ❌ | 0/3 |
| s04-new_prophetic_attribution | new_prophetic_attribution | 82.1 | 1.17 | ❌ | 3/3 |
| s05-certainty_raised | certainty_raised | 68.5 | 1.0 | ❌ | 3/3 |
| s05-scope_widened | scope_widened | 71.6 | 1.0 | ❌ | 3/3 |
| s06-hasr_lost | hasr_lost | 86.1 | 0.92 | ❌ | 3/3 |
| s07-consensus_inflated | consensus_inflated | 56.3 | 0.58 | ✅ | 3/3 |
| s07-condition_dropped | condition_dropped | 94.0 | 0.95 | ❌ | 3/3 |
| s08-term_narrowing | term_narrowing | 76.4 | 1.0 | ❌ | 3/3 |
| s08-ruling_shift | ruling_shift | 76.4 | 1.0 | ❌ | 3/3 |
| s09-condition_dropped | condition_dropped | 58.5 | 0.5 | ✅ | 3/3 |
| s09-negation_mismatch | negation_mismatch | 90.1 | 1.0 | ❌ | 3/3 |
| s10-ruling_shift | ruling_shift | 82.0 | 1.0 | ❌ | 3/3 |
| s10-term_narrowing | term_narrowing | 82.0 | 1.0 | ❌ | 3/3 |
| s11-number_mismatch | number_mismatch | 74.3 | 1.0 | ❌ | 3/3 |
| s12-hadith_grade_dropped | hadith_grade_dropped | 65.1 | 1.05 | ❌ | 3/3 |
| s13-exception_dropped | exception_dropped | 60.3 | 0.58 | ✅ | 3/3 |
| s13-scope_widened | scope_widened | 81.4 | 1.17 | ❌ | 3/3 |
| s14-negation_mismatch | negation_mismatch | 83.8 | 0.9 | ❌ | 3/3 |
| s14-ruling_shift | ruling_shift | 70.9 | 1.1 | ❌ | 3/3 |
| s15-negation_mismatch | negation_mismatch | 88.0 | 0.88 | ❌ | 3/3 |

## التكلفة

- استدعاءات حية: 810 · من الـcache: 396 · فاشلة: 5
- الإجمالي التقريبي لهذا التقييم: $3.783

| النموذج | tokens إدخال | tokens إخراج | استدعاءات |
|---|---|---|---|
| `claude-sonnet-5-5` | 931,296 | 120,780 | 623 |
| `claude-haiku-4-5` | 486,019 | 45,312 | 187 |

## حالات مستبعدة من القياس

| التشغيل | الحالة | الحالة النهائية | السبب |
|---|---|---|---|
| 3 | a01 | analyzed | تعذّر امتحان القارئ: BadRequestError |
| 3 | a02 | failed | BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, 'request_id': 'req_011CfbVFMgrdnZgqn7tQPFTP'} |
| 3 | a03 | analyzed | تعذّر امتحان القارئ: BadRequestError |
| 3 | a04 | analyzed | تعذّر مخاطر الفهم: BadRequestError؛ تعذّر امتحان القارئ: BadRequestError |

أخطاء المزوّد المسجّلة أثناء التقييم:

- `Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anth`

## الحدود

- البذور مسودة كتبها المساعد البرمجي ولم تراجعها المطوّرة بعد؛ والتغيّرات المزروعة مولّدة بنموذج، فقد لا يكون التغيّر مزروعاً بدقة في كل حالة (`eval/results.json` فيه النصوص والتنبؤات كاملة).
- 47 حالة فقط، وبعض الأنواع ظهرت مرة واحدة لكل تشغيل: الاستدعاء والدقة لهذه الأنواع غير مستقرين إحصائياً.
- كل حالة جملة أو جملتان وحلقة واحدة (عربي ← إنجليزي)؛ السلاسل الطويلة واللغات الأخرى لا تُقاس هنا.
- الصياغات «السليمة» مولّدة بنموذج أيضاً؛ وبعض «الإنذارات الكاذبة» قد تكون فروقاً دقيقة حقيقية تحتاج حكماً بشرياً.
- التشغيل الأول أُعيد من cache تقييم أولي سابق؛ الزمن والتكلفة محسوبان من التشغيلات بلا cache فقط.
- الأسعار تقديرية من جدول ثابت في `eval/run_eval.py`.
