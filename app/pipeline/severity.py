"""6.11 ترتيب الخطورة.

الترتيب: ما يُنسب إلى الله ورسوله ﷺ ← الأحكام ← الشروط والاستثناءات واليقين ← المصطلحات ← الأسلوب.
مستوى المحتوى يرفع الخطورة: A (أعلى حساسية) يرفع الأصفر إلى أحمر في الطبقات 0–2، و D خارج النطاق ← إحالة.
"""
from __future__ import annotations

from app.models import Alert, ContentLevel, Evidence, Severity
from app.models import AlertType as T

TIER_LABELS_AR = {
    0: "نسبة إلى الله ورسوله ﷺ",
    1: "الأحكام",
    2: "الشروط والاستثناءات واليقين",
    3: "المصطلحات",
    4: "الأسلوب",
}

TIERS: dict[T, int] = {
    # 0) ما يُنسب إلى الله ورسوله ﷺ
    T.new_prophetic_attribution: 0, T.attribution_upgraded: 0, T.unverified_attribution: 0,
    T.source_conflict: 0, T.quote_wording_differs: 0, T.hadith_grade_dropped: 0,
    # 1) الأحكام
    T.ruling_shift: 1, T.madhhab_unverified: 1, T.consensus_inflated: 1, T.disagreement_collapsed: 1, T.attribution_generalized: 1, T.negation_mismatch: 1, T.number_mismatch: 1,
    # 2) الشروط والاستثناءات واليقين
    T.condition_dropped: 2, T.exception_dropped: 2, T.certainty_raised: 2, T.scope_widened: 2,
    T.scope_narrowed: 2, T.hasr_lost: 2, T.lock_violated: 2, T.reader_divergence: 2, T.sentence_dropped: 2,
    # 3) المصطلحات وما يحتاج نظرة بشرية
    T.term_narrowing: 3, T.witness_disagreement: 3,
    # 4) الأسلوب
    T.length_drop: 4,
}

_SEV_RANK = {Severity.red: 0, Severity.yellow: 1, Severity.info: 2}


def tier(alert: Alert) -> int:
    return TIERS.get(alert.type, 4)


def apply_severity(alerts: list[Alert], level: ContentLevel) -> list[Alert]:
    """يعدّل الخطورة حسب مستوى المحتوى ويرتّب: الخطورة ← الطبقة ← موضع الجملة. لا يحذف شيئاً."""
    for a in alerts:
        a.tier = tier(a)
        if level == ContentLevel.A and a.severity == Severity.yellow and a.tier <= 2:
            a.severity = Severity.red
            a.evidence.append(Evidence(kind="fingerprint", ref="content_level",
                                       detail="رُفعت الخطورة لأن مستوى المحتوى A (نصوص منسوبة إلى الله ورسوله ﷺ)"))
    return sorted(alerts, key=lambda a: (_SEV_RANK[a.severity], a.tier,
                                         a.source_sentence_indices[:1] or [10**6], a.version_label))


def needs_referral(level: ContentLevel) -> bool:
    """مستوى D خارج نطاق الأداة: يُحال إلى مختص ولا يُعدّ التقرير صالحاً للنشر بمفرده."""
    return level == ContentLevel.D
