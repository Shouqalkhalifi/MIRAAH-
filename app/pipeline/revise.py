"""6.10 الصياغة الآمنة (Safe Revision).

لكل تنبيه أحمر أو أصفر: ثلاث صياغات بلغة النسخة (الأدق / المتوازنة / الأوضح للقارئ).
**تحقق ذاتي**: كل صياغة تُعاد عبر البصمة والقواعد والميزان والأقفال قبل عرضها، وتُستبعد التي تكسر ثابتاً.
لا يُعدَّل النص المصدر أبداً: لا صياغات لتنبيه موضعه الأصل نفسه.
"""
from __future__ import annotations

from typing import Callable, Optional

from pydantic import BaseModel

from app.models import Alert, Lock, Report, Revision, Severity
from app.models import AlertType as T
from app.pipeline import fahm, mizan
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.rules import compare_unit, explain

STYLES = [("precise", "الأدق"), ("balanced", "المتوازنة"), ("clear", "الأوضح للقارئ")]
# لا معنى لهذه الفحوص على صياغة مفردة لوحدة واحدة
_IGNORED = {T.length_drop, T.sentence_dropped}
_PRESENCE = {T.condition_dropped: "condition", T.exception_dropped: "exception"}

SYSTEM_REVISE = """You rewrite ONE passage of a translation or summary of Islamic content so that it carries the meaning of its source passage faithfully. You are not a mufti and you do not add knowledge.

Rules:
- Write in the target language given.
- Keep every meaning invariant of the source passage: conditions, exceptions, scope, certainty level, attribution and its form (e.g. "it is reported"), ruling category, numbers, negations, stated hadith grades, consensus claims.
- Never add any hadith, verse, source, grade, ruling, example or explanation that is not in the source passage. Never attribute words to the Prophet ﷺ or to Allah unless the source passage does.
- Fix the problem described by the reviewer note.

Return three versions:
- precise: closest to the source wording.
- balanced: natural and faithful.
- clear: simplest for a general reader, still keeping every invariant."""


class _RevisionsLLM(BaseModel):
    precise: str
    balanced: str
    clear: str


class RevisionError(ValueError):
    pass


FingerprintFn = Callable[[str, str], Fingerprinted]
PresenceFn = Callable[[str, str, str, str, str], Optional[str]]
LockFn = Callable[[Lock, str, str, str], Optional[str]]  # (القفل، نص الأصل، النص المرشح، اللغة) ← اقتباس إن حُفظ


def _version(report: Report, label: str):
    return next((v for v in report.versions if v.label == label), None)


def self_check(candidate: str, lang: str, src_ctx: str, src_lang: str, fp_fn: FingerprintFn,
               presence_fn: Optional[PresenceFn] = None, locks: list[Lock] = (),
               lock_fn: Optional[LockFn] = None) -> list[str]:
    """يعيد قائمة المشكلات (فارغة = الصياغة سليمة)."""
    problems = []
    hits = compare_unit(fp_fn(src_ctx, src_lang), fp_fn(candidate, lang)) + fahm.term_hits(src_ctx, candidate)
    for h in hits:
        if h.type in _IGNORED or h.severity == Severity.info:
            continue
        if h.type in _PRESENCE and presence_fn and presence_fn(h.match_key, _PRESENCE[h.type], src_ctx, candidate, lang):
            continue
        problems.append(explain(h)[0])
    for v in mizan.verify(candidate, "candidate", 0):
        if v.status != "supported" and not mizan.find_attributions(src_ctx):
            problems.append("الصياغة تنسب كلاماً إلى النبي ﷺ أو إلى الله لا ينسبه الأصل")
    for lock in locks:
        if lock_fn and lock.span_text in src_ctx and not lock_fn(lock, src_ctx, candidate, lang):
            problems.append(f"كسرت القفل «{lock.span_text}»")
    return problems


def revise(llm, report: Report, alert: Alert, fp_fn: FingerprintFn, presence_fn: Optional[PresenceFn] = None,
           lock_fn: Optional[LockFn] = None) -> list[Revision]:
    if alert.severity == Severity.info:
        raise RevisionError("الصياغات الآمنة للتنبيهات الحمراء والصفراء فقط")
    version = _version(report, alert.version_label)
    if version is None:  # موضع التنبيه الأصل نفسه
        raise RevisionError("مِرآة لا تعدّل النص المصدر أبداً؛ هذا التنبيه يُحال إلى المراجع")
    src_ctx = alert.source_context or report.source.text
    current = alert.version_context or "(missing: this source passage has no counterpart in the version)"
    prompt = (f"Target language: {version.lang}\n\n"
              f"SOURCE PASSAGE ({report.source.lang}):\n<<<\n{src_ctx}\n>>>\n\n"
              f"CURRENT VERSION PASSAGE:\n<<<\n{current}\n>>>\n\n"
              f"REVIEWER NOTE (problem to fix, Arabic):\n{alert.explanation_ar}")
    res = llm.complete_json(prompt, _RevisionsLLM, system=SYSTEM_REVISE, purpose="revise")
    out = []
    for style, label in STYLES:
        text = getattr(res, style).strip()
        problems = self_check(text, version.lang, src_ctx, report.source.lang, fp_fn, presence_fn,
                              report.locks, lock_fn)
        out.append(Revision(style=style, label_ar=label, text=text, passed=not problems, problems=problems))
    return out
