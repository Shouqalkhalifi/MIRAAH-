"""بيانات العرض: الوحدات الثلاث (الميزان / الأثر / الفهم) وعنوان عربي لكل نوع تنبيه."""
from __future__ import annotations

from app.models import AlertType as T

MODULES = {
    "mizan": {"ar": "الميزان", "en": "MIZAN", "sub_ar": "دليل وإسناد", "sub_en": "Evidence & Attribution",
              "desc": "يبحث عن كل نص منسوب إلى الله أو رسوله ﷺ في مدونة محلية موثّقة، وما لا يجده يُحال إلى المراجع ولا يُحكم عليه."},
    "athar": {"ar": "الأثر", "en": "ATHAR", "sub_ar": "سلسلة المعنى", "sub_en": "Meaning Lineage",
              "desc": "يتتبّع ثوابت المعنى من الأصل عبر الترجمات والملخصات، ويحدد الحلقة التي دخل فيها الخلل."},
    "fahm": {"ar": "الفهم", "en": "FAHM", "sub_ar": "فهم سياقي وثقافي", "sub_en": "Contextual & Cultural Understanding",
             "desc": "يفحص ضوابط المصطلحات، ويمتحن ما يفهمه قارئ النسخة مقارنة بقارئ الأصل."},
}

# النوع ← (الوحدة، العنوان العربي)
ALERT_META: dict[str, tuple[str, str]] = {
    # الميزان: النسبة والدليل
    T.unverified_attribution: ("mizan", "نسبة غير متحقق منها"),
    T.source_conflict: ("mizan", "تعارض مع المصدر"),
    T.quote_wording_differs: ("mizan", "اختلاف لفظ النص المنسوب"),
    T.new_prophetic_attribution: ("mizan", "نسبة جديدة إلى النبي ﷺ"),
    T.attribution_upgraded: ("mizan", "جزم بعد تمريض"),
    T.hadith_grade_dropped: ("mizan", "حذف درجة الحديث"),
    T.consensus_inflated: ("mizan", "تضخيم دعوى الإجماع"),
    # الأثر: ثوابت المعنى عبر السلسلة
    T.condition_dropped: ("athar", "سقوط شرط"),
    T.exception_dropped: ("athar", "سقوط استثناء"),
    T.certainty_raised: ("athar", "ارتفاع درجة اليقين"),
    T.ruling_shift: ("athar", "تغيّر نوع الحكم"),
    T.scope_widened: ("athar", "اتساع النطاق"),
    T.scope_narrowed: ("athar", "تضييق النطاق"),
    T.hasr_lost: ("athar", "سقوط الحصر"),
    T.negation_mismatch: ("athar", "اختلاف النفي"),
    T.number_mismatch: ("athar", "اختلاف الأرقام"),
    T.sentence_dropped: ("athar", "جملة بلا مقابل"),
    T.length_drop: ("athar", "اختصار شديد"),
    T.lock_violated: ("athar", "كسر قفل معنى"),
    T.witness_disagreement: ("athar", "مختلف فيه بين الشاهدين"),
    # الفهم
    T.term_narrowing: ("fahm", "مخالفة ضابط مصطلح"),
    T.reader_divergence: ("fahm", "اختلاف فهم القارئ"),
}
ALERT_META = {k.value: v for k, v in ALERT_META.items()}

# سطر إنجليزي قصير لكل نوع (كما في التصميم: "Meaning: Constraint Loss")
ALERT_EN = {
    "unverified_attribution": "Evidence: Not Verified", "source_conflict": "Evidence: Source Conflict",
    "quote_wording_differs": "Evidence: Wording Differs", "new_prophetic_attribution": "Evidence: New Attribution",
    "attribution_upgraded": "Evidence: Attribution Upgraded", "hadith_grade_dropped": "Evidence: Grade Dropped",
    "consensus_inflated": "Evidence: Consensus Inflated", "condition_dropped": "Meaning: Constraint Loss",
    "exception_dropped": "Meaning: Exception Loss", "certainty_raised": "Meaning: Certainty Raised",
    "ruling_shift": "Meaning: Ruling Shift", "scope_widened": "Meaning: Scope Widened",
    "scope_narrowed": "Meaning: Scope Narrowed", "hasr_lost": "Meaning: Restriction Lost",
    "negation_mismatch": "Meaning: Negation Mismatch", "number_mismatch": "Meaning: Number Mismatch",
    "sentence_dropped": "Meaning: Sentence Dropped", "length_drop": "Style: Heavy Shortening",
    "lock_violated": "Meaning: Lock Broken", "witness_disagreement": "Witnesses Disagree",
    "term_narrowing": "Context: Term Misuse", "reader_divergence": "Context: Reader Divergence",
}


def meta(alert_type: str) -> tuple[str, str, str]:
    """(الوحدة، العنوان العربي، السطر الإنجليزي)"""
    mod, ar = ALERT_META.get(alert_type, ("athar", alert_type))
    return mod, ar, ALERT_EN.get(alert_type, alert_type)
