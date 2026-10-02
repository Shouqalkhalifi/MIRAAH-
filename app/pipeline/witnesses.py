"""6.8 مبدأ الشاهدين.

تُستخرج البصمة بنموذجين مستقلين (WITNESS_A_MODEL و WITNESS_B_MODEL):
- اتفاق ← يمضي التنبيه (witnesses_agree=true).
- اختلاف في حقل مؤثر ← witnesses_agree=false وتنخفض الثقة؛ وما يراه الشاهد الثاني وحده يصبح تنبيهاً أصفر
  «مختلف فيه — يحتاج نظرة بشرية».
- إن لم يتوفر الشاهد الثاني يعمل بشاهد واحد ويُظهر ذلك في التقرير.
- نسبة الاتفاق (على الحقول المؤثرة لكل نص وحدة) تُعرض مقياساً للثقة.
"""
from __future__ import annotations

from app.models import MeaningFingerprint
from app.models import AlertType as T
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.rules import Hit, phrases_match

# أنواع التنبيه المشتقة من البصمة (التي يمكن أن يختلف فيها الشاهدان)
FP_DERIVED = {
    T.condition_dropped, T.exception_dropped, T.certainty_raised, T.attribution_upgraded,
    T.new_prophetic_attribution, T.ruling_shift, T.scope_widened, T.scope_narrowed, T.hasr_lost,
    T.consensus_inflated, T.hadith_grade_dropped,
}

# ما يراه الشاهد الثاني وحده يصبح تنبيهاً فقط في هذه الأنواع. النطاق (scope) مستبعد: في التشغيل الفعلي اختلف
# الشاهدان في قراءة «عليه» (محدد/غير محدد) على ترجمة أمينة، فهو حقل لين يُحتسب في نسبة الاتفاق فقط.
B_ONLY_ALERT_TYPES = FP_DERIVED - {T.scope_widened, T.scope_narrowed}

TYPE_AR = {
    T.condition_dropped: "سقوط شرط", T.exception_dropped: "سقوط استثناء", T.certainty_raised: "رفع اليقين",
    T.attribution_upgraded: "جزم بعد تمريض", T.new_prophetic_attribution: "نسبة جديدة إلى النبي ﷺ",
    T.ruling_shift: "تغيّر الحكم", T.scope_widened: "اتساع النطاق", T.scope_narrowed: "تضييق النطاق",
    T.hasr_lost: "سقوط الحصر", T.consensus_inflated: "تضخيم دعوى الإجماع", T.hadith_grade_dropped: "حذف درجة الحديث",
    T.disagreement_collapsed: "انهيار الخلاف إلى قطع", T.attribution_generalized: "تعميم النسبة إلى الإسلام",
}


def impactful(fp: MeaningFingerprint) -> tuple:
    """الحقول المؤثرة التي يُقاس عليها اتفاق الشاهدين."""
    return (fp.attribution.to, fp.attribution.form, fp.ruling, fp.certainty, fp.restriction_hasr,
            fp.consensus_claim, fp.scope.quantifier, len(fp.conditions) > 0, len(fp.exceptions) > 0,
            tuple(sorted(h.grade_stated for h in fp.hadith_mentions)))


def agreement(pairs: list[tuple[Fingerprinted, Fingerprinted]]) -> float | None:
    if not pairs:
        return None
    return round(sum(impactful(a.fp) == impactful(b.fp) for a, b in pairs) / len(pairs), 3)


def same_hit(a: Hit, b: Hit) -> bool:
    return a.type == b.type and (not a.match_key or not b.match_key or a.match_key == b.match_key
                                 or phrases_match(a.match_key, b.match_key))


def reconcile(hits_a: list[Hit], hits_b: list[Hit]) -> tuple[dict[int, bool], list[Hit]]:
    """يعيد: (رقم تنبيه الشاهد الأول ← هل وافقه الثاني)، وتنبيهات «مختلف فيه» لما رآه الثاني وحده."""
    agree = {}
    for i, h in enumerate(hits_a):
        if h.type in FP_DERIVED:
            agree[i] = any(same_hit(h, b) for b in hits_b)
    only_b = []
    for b in hits_b:
        if b.type in B_ONLY_ALERT_TYPES and not any(same_hit(b, h) for h in hits_a):
            only_b.append(Hit(T.witness_disagreement, f"witness_b:{b.field}", before=TYPE_AR[b.type],
                              after="", src_quote=b.src_quote, match_key=f"wb-{b.type.value}-{b.match_key}",
                              confidence=0.5))
    return agree, only_b
