# SOURCES — المصادر والمكتبات وتراخيصها

## المكتبات البرمجية

| المكتبة | الاستخدام | الترخيص |
|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | الخادم والواجهة البرمجية | MIT |
| [Uvicorn](https://github.com/encode/uvicorn) | خادم ASGI | BSD-3-Clause |
| [Pydantic](https://github.com/pydantic/pydantic) | التحقق من البيانات | MIT |
| [SQLModel](https://github.com/fastapi/sqlmodel) | SQLite (التقارير، cache، سجل الاستدعاءات) | MIT |
| [Jinja2](https://github.com/pallets/jinja) | قوالب HTML | BSD-3-Clause |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | قراءة `.env` | BSD-3-Clause |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | استدعاء نماذج Claude | MIT |
| [httpx](https://github.com/encode/httpx) | عميل HTTP (الاختبارات) | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest) | الاختبارات | MIT |
| [rank-bm25](https://github.com/dorianbrown/rank_bm25) | الاسترجاع BM25 في الميزان | Apache-2.0 |
| [NumPy](https://github.com/numpy/numpy) (تبعية rank-bm25) | حساب الدرجات | BSD-3-Clause |
| [qrcode](https://github.com/lincolnloop/python-qrcode) | رمز QR في صفحة الختم (SVG) | BSD-3-Clause |
| [sacrebleu](https://github.com/mjpost/sacrebleu) | chrF لخط الأساس في التقييم | Apache-2.0 |
| [python-multipart](https://github.com/Kludex/python-multipart) | استقبال نموذج «قابِل ما قرأت» | Apache-2.0 |
| [Alpine.js](https://alpinejs.dev) (CDN) | تفاعل الواجهة | MIT |
| [Readex Pro](https://fonts.google.com/specimen/Readex+Pro) (Google Fonts) | خط الواجهة | SIL Open Font License 1.1 |
| [Amiri](https://fonts.google.com/specimen/Amiri) (Google Fonts) | النص العربي الأصلي وحده (نسخي) | SIL Open Font License 1.1 |
| [Literata](https://fonts.google.com/specimen/Literata) (Google Fonts) | النصوص اللاتينية | SIL Open Font License 1.1 |

## الخدمات والبنية

| العنصر | الاستخدام | الترخيص / الشروط |
|---|---|---|
| Anthropic API: `claude-sonnet-5-5` (الشاهد الأول) و `claude-haiku-4-5` (الشاهد الثاني) | المحاذاة، وبصمة المعنى، والتحقق الموجّه، والصياغات الآمنة، وامتحان القارئ، ومخاطر الفهم | شروط استخدام Anthropic التجارية. أسماء النماذج في `.env` |
| صورة Docker `python:3.11-slim` | تشغيل التطبيق | PSF License (Python) وتراخيص حزم Debian |
| [ruff](https://github.com/astral-sh/ruff) (أداة فحص أثناء التطوير، ليست في المتطلبات) | فحص الكود غير المستخدم | MIT |

## بيانات المدونة (`data/corpus/`)

> المرحلة 0: العناصر الحالية **أمثلة للشكل فقط** (3 لكل نوع) وتحتاج مراجعة. تُستبدل بعناصر موثّقة من الحزمة العلمية.

| النوع | المصدر | الترخيص / الملاحظة |
|---|---|---|
| quran | النص القرآني، والترجمة Sahih International عبر quran.com | النص القرآني ملك عام، والترجمة لأغراض غير تجارية مع الإسناد |
| hadith | صحيح البخاري، وصحيح مسلم (روابط sunnah.com) | المتون ملك عام، والترجمات الإنجليزية من عمل المشروع |
| term | أمثلة اصطناعية | تُستبدل بضوابط من قاموس الحزمة العلمية والجمهرة |

## بيانات التقييم (`data/eval/`)
- `seeds.jsonl`: 15 بذرة **مسودة** كتبها المساعد البرمجي، تراجعها المطوّرة من مصادر الحزمة قبل اعتماد النتائج.
- `cases.jsonl`: حالات مولّدة آلياً من البذور بنموذج Claude (تغيّرات مزروعة وصياغات سليمة)، وأربع حالات امتناع
  لأقوال تُنسب إلى النبي ﷺ وليست في المدونة المحلية.

## مكتبة «قابِل ما قرأت» (`data/library/issues.jsonl`)
- **المصدر**: الشيخ عبد العزيز بن باز، كتاب «أسئلة مهمة تتعلق بالصيام»، ملف PDF من موقعه الرسمي:
  https://binbaz.org.sa/books/pdf/215 (قدّمته المطوّرة مصدراً موثوقاً). الاستخدام: اقتباسات قصيرة حرفية لغرض المراجعة
  مع الإحالة إلى الصفحة؛ الحقوق لأصحابها، ولا يُعاد نشر الكتاب.
- 9 مسائل (`BZ01`–`BZ09`). كل `text_ar` مقتطف حرفي من نص الملف، وتحقّق برنامج البناء آلياً من وجوده فيه وسجّل رقم
  الصفحة في الرابط (`#page=N`). لا آيات ولا أحاديث، لأن نصها في النسخة الممسوحة مشوّه بالتعرف الضوئي ولا يُصلح من الذاكرة.
- الملف ممسوح ضوئياً: بعض المقتطفات فيها أخطاء تعرّف أُبقيت كما هي (مثل «سبعأ» و«الصاثم» و«مطلقإ»).
- لا ترجمة إنجليزية معتمدة في المصدر، فـ`translation_en` فارغة ولم تُخترع. الحقول الإنجليزية في `position`
  (الشروط والنطاق) وصف داخلي للمقارنة الحتمية، وليست ترجمة.
- كل المسائل `reviewed: false` حتى تراجعها المطوّرة على صفحات الكتاب.
- **المصدر الثاني**: «مسائل الحج والعمرة من مجموع الفتاوى» للشيخ ابن باز، تلخيص عبد الرحمن الهرفي، من الموقع الرسمي:
  https://binbaz.org.sa/books/pdf/610 (قدّمته المطوّرة، وتطابق حجمه مع ملف الموقع: 766,400 بايت). 12 مسألة (`HJ01`–`HJ12`).
  طبقة النص في هذا الملف تالفة الترتيب (مثل «احلج» بدل «الحج»)، فنُقلت المقتطفات من صورة الصفحة، ثم تحقّق برنامج
  آلياً من كل مقتطف مقابل طبقة النص بمقارنة تتسامح مع تبديل الحروف (تطابق 93–100٪، وكل فرق راجع إلى تقطّع كلمة في
  طبقة النص). لا آيات ولا أحاديث. الكتاب تلخيص لفتاوى الشيخ، لا نص الفتاوى نفسها؛ وأرقام صفحات «مجموع الفتاوى» في
  `source_note` إن احتجتِ إلى الرجوع للأصل.
- المسألتان الوهميتان `I01` و`I02` نُقلتا إلى `tests/fixtures/placeholder_issues.jsonl` للاختبارات فقط.

## الأصول البصرية
- أيقونة الموقع (`app/static/favicon.*`): من عمل المشروع، تُولَّد بـ `scripts/make_favicon.py` بألوان الهوية.
- الواجهة («المقابلة»): CSS من عمل المشروع في `app/static/app.css` برموز متغيرات CSS، بلا مكتبة تنسيق ولا صور خارجية.

## البيانات الاصطناعية
كل الأمثلة في `app/mock.py` و `data/examples/` اصطناعية، ولا تحتوي على محادثات حقيقية ولا بيانات شخصية.
