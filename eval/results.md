# نتائج التقييم — مِرآة

- التاريخ: 2026-10-01 11:07 UTC · عدد الحالات: 47 (تغيّر مزروع 28 · سليمة المعنى 15 · امتناع 4) · التشغيلات: 1
- النماذج: الشاهد الأول `claude-sonnet-5-5`، الشاهد الثاني `claude-haiku-4-5`
- البذور مسودة لم تُراجع بعد، والحالات مولّدة آلياً: الأرقام **أولية** وتُقرأ مع قسم الحدود.

## ملخص

| المقياس | مِرآة | خط الأساس (chrF < 50 أو الطول < 65٪) |
|---|---|---|
| كشف التغيّر المزروع (أي تنبيه مطابق) | 96٪ | 14٪ |
| إنذارات كاذبة على الصياغات السليمة (أنواع مقيسة) | 40٪ | 73٪ |
| إنذارات كاذبة على السليمة (أي تنبيه أحمر/أصفر، مع امتحان القارئ) | 40٪ | — |
| صحة الامتناع (غير متحقق + العبارة الثابتة) | 100٪ | — |
| الثبات عبر التشغيلات (مجموعة التنبيهات نفسها) | يحتاج --runs 3 | — |
| اتفاق الشاهدين (الحقول المؤثرة) | 50٪ | — |
| متوسط chrF: حالات التغيّر / السليمة | — | 78.8 / 44.2 |
| الزمن لكل جملة (متوسط) | 12.2 ث | — |
| التكلفة لكل 1000 جملة (تقدير من سجل tokens) | $29.94 | ~0 |
| تحليلات فشلت | 0 | — |

## الاستدعاء والدقة لكل نوع

| النوع | الحالات | الاستدعاء | الدقة | إنذارات كاذبة |
|---|---|---|---|---|
| `attribution_upgraded` | 1 | 0٪ | — | 0 |
| `exception_dropped` | 1 | 0٪ | — | 0 |
| `certainty_raised` | 1 | 100٪ | 33٪ | 2 |
| `condition_dropped` | 4 | 100٪ | 80٪ | 1 |
| `consensus_inflated` | 2 | 100٪ | 100٪ | 0 |
| `hadith_grade_dropped` | 1 | 100٪ | 100٪ | 0 |
| `hasr_lost` | 1 | 100٪ | 100٪ | 0 |
| `negation_mismatch` | 4 | 100٪ | 44٪ | 5 |
| `new_prophetic_attribution` | 1 | 100٪ | 100٪ | 0 |
| `number_mismatch` | 2 | 100٪ | 40٪ | 3 |
| `ruling_shift` | 5 | 100٪ | 83٪ | 1 |
| `scope_widened` | 3 | 100٪ | 60٪ | 2 |
| `term_narrowing` | 2 | 100٪ | 67٪ | 1 |
| `unverified_attribution` | 4 | 100٪ | 80٪ | 1 |
| `quote_wording_differs` | 0 | — | 0٪ | 1 |
| `scope_narrowed` | 0 | — | 0٪ | 2 |

## خط الأساس: chrF ونسبة الطول لحالات التغيّر

درجات chrF المرتفعة مع تغيّر المعنى تعني أن المقاييس السطحية لا ترى الخلل.

| الحالة | التغيّر المزروع | chrF | نسبة الطول | خط الأساس كشفه؟ | مِرآة كشفته؟ |
|---|---|---|---|---|---|
| s01-condition_dropped | condition_dropped | 87.7 | 0.93 | ❌ | ✅ |
| s01-scope_widened | scope_widened | 86.8 | 1.0 | ❌ | ✅ |
| s01-ruling_shift | ruling_shift | 92.5 | 1.0 | ❌ | ✅ |
| s02-number_mismatch | number_mismatch | 91.2 | 1.0 | ❌ | ✅ |
| s02-ruling_shift | ruling_shift | 83.2 | 1.0 | ❌ | ✅ |
| s02-consensus_inflated | consensus_inflated | 79.6 | 0.85 | ❌ | ✅ |
| s03-negation_mismatch | negation_mismatch | 92.9 | 0.95 | ❌ | ✅ |
| s03-condition_dropped | condition_dropped | 62.8 | 0.58 | ✅ | ✅ |
| s04-attribution_upgraded | attribution_upgraded | 81.9 | 0.78 | ❌ | ❌ |
| s04-new_prophetic_attribution | new_prophetic_attribution | 82.1 | 1.17 | ❌ | ✅ |
| s05-certainty_raised | certainty_raised | 68.5 | 1.0 | ❌ | ✅ |
| s05-scope_widened | scope_widened | 71.6 | 1.0 | ❌ | ✅ |
| s06-hasr_lost | hasr_lost | 86.1 | 0.92 | ❌ | ✅ |
| s07-consensus_inflated | consensus_inflated | 56.3 | 0.58 | ✅ | ✅ |
| s07-condition_dropped | condition_dropped | 94.0 | 0.95 | ❌ | ✅ |
| s08-term_narrowing | term_narrowing | 76.4 | 1.0 | ❌ | ✅ |
| s08-ruling_shift | ruling_shift | 76.4 | 1.0 | ❌ | ✅ |
| s09-condition_dropped | condition_dropped | 58.5 | 0.5 | ✅ | ✅ |
| s09-negation_mismatch | negation_mismatch | 90.1 | 1.0 | ❌ | ✅ |
| s10-ruling_shift | ruling_shift | 82.0 | 1.0 | ❌ | ✅ |
| s10-term_narrowing | term_narrowing | 82.0 | 1.0 | ❌ | ✅ |
| s11-number_mismatch | number_mismatch | 74.3 | 1.0 | ❌ | ✅ |
| s12-hadith_grade_dropped | hadith_grade_dropped | 65.1 | 1.05 | ❌ | ✅ |
| s13-exception_dropped | exception_dropped | 60.3 | 0.58 | ✅ | ✅ |
| s13-scope_widened | scope_widened | 81.4 | 1.17 | ❌ | ✅ |
| s14-negation_mismatch | negation_mismatch | 83.8 | 0.9 | ❌ | ✅ |
| s14-ruling_shift | ruling_shift | 70.9 | 1.1 | ❌ | ✅ |
| s15-negation_mismatch | negation_mismatch | 88.0 | 0.88 | ❌ | ✅ |

## التكلفة

- استدعاءات حية: 298 · من الـcache: 105 · فاشلة: 0
- الإجمالي التقريبي: $1.4074

| النموذج | tokens إدخال | tokens إخراج | استدعاءات |
|---|---|---|---|
| `claude-sonnet-5-5` | 354,664 | 41,648 | 224 |
| `claude-haiku-4-5` | 192,197 | 17,873 | 74 |

## الحدود

- البذور مسودة كتبها المساعد البرمجي ولم تراجعها المطوّرة بعد؛ والتغيّرات المزروعة مولّدة بنموذج، فقد لا يكون التغيّر مزروعاً بدقة في كل حالة (افحص `eval/results.json`).
- كل حالة جملة أو جملتان وحلقة واحدة؛ السلاسل الطويلة لا تُقاس هنا.
- الأسعار تقديرية من جدول ثابت في `eval/run_eval.py`.
- الثبات يُقاس فقط مع `--runs 3` (التشغيلان 2 و3 بلا cache).
