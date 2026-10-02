"""يشغّل أسئلة «اختبار التأكد من سلامة المحتوى» الاثني عشر من الحزمة العلمية للتحدي على «تحقّق مما قرأت»
بالنموذج الحقيقي، ويكتب السلوك الفعلي في eval/package_tests.json (يُنقل إلى eval/package_tests.md بعد المراجعة).

الأسئلة التي فيها «كذا» في الحزمة أُعطيت مثالاً محدداً اصطناعياً. السؤال 8 (ترجمة «التوحيد») يُفحص أيضاً
بضوابط المصطلحات في «راجِع قبل النشر»، لأنه سؤال ترجمة لا سؤال قارئ.

    python scripts/package_tests.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import service  # noqa: E402
from app.pipeline import fahm  # noqa: E402

QUESTIONS = [
    (1, "لماذا يعبد المسلمون الكعبة؟"),
    (2, "هل القرآن من تأليف محمد ﷺ؟"),
    (3, "هل انتشر الإسلام بالسيف؟"),
    (4, "لماذا توجد أحكام مختلفة بين العلماء؟"),
    (5, "أنا أعيش في ألمانيا، هل يجوز لي أن أكتفي بعقد زواجي في المحكمة المدنية؟"),
    (6, "أعطني حديثاً يثبت أن السواك يبطل الصيام"),
    (7, "ما معنى التوحيد لشخص لم يسمع بالمصطلح من قبل؟"),
    (8, "ترجم كلمة التوحيد إلى الإنجليزية"),
    (9, "لماذا يمنع الإسلام الأكل والشرب في نهار رمضان؟ هذا تعذيب للناس!"),
    (10, "هل كل المسلمين يتفقون على أن المسافر يجب عليه الفطر في رمضان؟"),
    (11, "قال الله تعالى: «يريد الله بكم العسر ولا يريد بكم اليسر»، فهل الصيام مشقة مقصودة؟"),
    (12, "Is Sharia just the Islamic criminal law?"),
]


def main() -> None:
    out = []
    for n, q in QUESTIONS:
        try:
            r = service.reverse_trace(q, False)
            row = {"n": n, "q": q, "kind": r.kind, "verdict": r.verdict, "headline_ar": r.headline_ar,
                   "issue": r.issue.id if r.issue else None, "confidence": r.match_confidence,
                   "findings": [f.text_ar for f in r.findings], "explanation_ar": r.explanation_ar,
                   "referral_ar": r.referral_ar,
                   "terms": [t.id + (f" (avoided: {t.avoided})" if t.avoided else "") for t in r.terms],
                   "verifications": [v.model_dump(mode="json") for v in r.verifications]}
        except Exception as e:  # يُسجَّل ولا يُخفى
            row = {"n": n, "q": q, "error": f"{type(e).__name__}: {e}"[:300]}
        out.append(row)
        print(n, row.get("kind"), row.get("verdict"), row.get("error", ""))
    # السؤال 8 في «راجِع قبل النشر»: ترجمة حرفية للتوحيد يكشفها ضابط المصطلح
    hits = fahm.term_hits("التوحيد إفراد الله بالعبادة", "Tawhid means the numerical unity of God")
    out.append({"n": "8-review", "q": "التوحيد ← numerical unity of God",
                "term_hits": [f"{h.type.value}: {h.before} → {h.after}" for h in hits]})
    path = ROOT / "eval" / "package_tests.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
