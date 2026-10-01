"""6.3 مقارنة بصمة الأم ببصمة الابن، وفحوص حتمية ← تنبيهات.

كل القواعد دوال حتمية بلا نموذج. الشروح العربية قوالب ثابتة لكل نوع (لا يكتبها النموذج).
term_narrowing و lock_violated في المرحلة 2.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.models import AlertType as T
from app.models import Evidence, MeaningFingerprint, Severity
from app.pipeline.fingerprint import Fingerprinted
from app.text.normalize import tokens

DEFAULT_SEVERITY: dict[T, Severity] = {
    T.condition_dropped: Severity.red,
    T.exception_dropped: Severity.red,
    T.certainty_raised: Severity.red,
    T.attribution_upgraded: Severity.red,
    T.new_prophetic_attribution: Severity.red,
    T.ruling_shift: Severity.red,
    T.scope_widened: Severity.yellow,
    T.scope_narrowed: Severity.yellow,
    T.hasr_lost: Severity.yellow,
    T.consensus_inflated: Severity.red,
    T.hadith_grade_dropped: Severity.red,
    T.negation_mismatch: Severity.red,
    T.number_mismatch: Severity.red,
    T.term_narrowing: Severity.yellow,
    T.length_drop: Severity.info,
    T.sentence_dropped: Severity.yellow,
    T.lock_violated: Severity.red,
}

LENGTH_DROP_RATIO = 0.65  # الابن أقصر بأكثر من 35٪


@dataclass
class Hit:
    type: T
    field: str  # حقل البصمة (للدليل)
    before: str  # القيمة في الأم (للعرض)
    after: str  # القيمة في الابن
    src_quote: str = ""  # اقتباس حرفي من الأم إن وُجد
    ver_quote: str = ""
    match_key: str = ""  # لمطابقة الخلل نفسه عبر حلقات السلسلة
    confidence: float = 0.85
    evidence: list[Evidence] = field(default_factory=list)  # دليل إضافي (مثل عنصر المدونة)

    @property
    def severity(self) -> Severity:
        return DEFAULT_SEVERITY[self.type]


# ---------- مطابقة العبارات الإنجليزية (الشروط والاستثناءات) ----------
_STOP = {"a", "an", "the", "is", "are", "was", "be", "being", "of", "to", "in", "on", "for", "if", "and", "or",
         "person", "people", "someone", "one", "has", "have", "who", "with", "by", "it", "that", "this", "their",
         "his", "her", "they", "he", "she", "state", "when", "while", "must", "may", "should"}
_SUFFIXES = ("ification", "ation", "ness", "ity", "ing", "ers", "er", "ed", "es", "ly", "s")


def _stem(w: str) -> str:
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if len(w) > 3 and w[-1] == w[-2]:  # travell → travel
        w = w[:-1]
    return w


def content_tokens(phrase: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]+", phrase.lower()) if w not in _STOP}


def phrases_match(a: str, b: str) -> bool:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return a.strip().lower() == b.strip().lower()
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


def _kept(item: str, child: MeaningFingerprint, pool: list[str]) -> bool:
    if any(phrases_match(item, x) for x in pool):
        return True
    # القيد قد يُعبَّر عنه في الابن نطاقاً لا شرطاً ("for travelers")
    return bool(child.scope.restricted_to) and phrases_match(item, child.scope.restricted_to)


# ---------- القواعد ----------
_CERTAINTY_RANK = {"possible": 1, "probable": 2, "definite": 3}
_SCOPE_RANK = {"specific": 0, "some": 1, "all": 2}
_CONSENSUS_RANK = {"none": 0, "some_scholars": 1, "majority": 2, "ijma": 3}


def _dropped(kind: T, field: str, p: Fingerprinted, c: MeaningFingerprint) -> list[Hit]:
    items = getattr(p.fp, field)
    quotes = p.condition_quotes if field == "conditions" else p.exception_quotes
    pool = getattr(c, field)
    out = []
    for i, item in enumerate(items):
        if not _kept(item, c, pool):
            q = quotes[i] if i < len(quotes) and quotes[i] else ""
            out.append(Hit(kind, field, before=q or item, after="", src_quote=q, match_key=item))
    return out


def _scope_label(fp: MeaningFingerprint) -> str:
    return fp.scope.restricted_to or fp.scope.quantifier


def compare_unit(p: Optional[Fingerprinted], c: Optional[Fingerprinted]) -> list[Hit]:
    """يقارن وحدة محاذاة واحدة. p=None: جملة مضافة، c=None: جملة محذوفة."""
    if p is None and c is None:
        return []
    if c is None:
        return [Hit(T.sentence_dropped, "alignment", before="", after="", confidence=0.9)]
    cf = c.fp
    if p is None:  # جملة مضافة: الخطر الأكبر نسبة كلام جديد إلى النبي ﷺ
        if cf.attribution.to == "prophet":
            return [Hit(T.new_prophetic_attribution, "attribution.to", before="none", after="prophet")]
        return []

    pf = p.fp
    hits: list[Hit] = []
    hits += _dropped(T.condition_dropped, "conditions", p, cf)
    hits += _dropped(T.exception_dropped, "exceptions", p, cf)

    if pf.certainty in ("possible", "probable") and cf.certainty == "definite":
        hits.append(Hit(T.certainty_raised, "certainty", pf.certainty, cf.certainty))

    if pf.attribution.form == "tamrid" and cf.attribution.form == "assertive":
        hits.append(Hit(T.attribution_upgraded, "attribution.form", "tamrid", "assertive"))

    if cf.attribution.to == "prophet" and pf.attribution.to != "prophet":
        hits.append(Hit(T.new_prophetic_attribution, "attribution.to", pf.attribution.to, "prophet"))

    if cf.ruling != pf.ruling and cf.ruling != "none":
        hits.append(Hit(T.ruling_shift, "ruling", pf.ruling, cf.ruling))

    ps, cs = pf.scope, cf.scope
    if ps.quantifier in _SCOPE_RANK and cs.quantifier in _SCOPE_RANK and ps.quantifier != cs.quantifier:
        kind = T.scope_widened if _SCOPE_RANK[cs.quantifier] > _SCOPE_RANK[ps.quantifier] else T.scope_narrowed
        hits.append(Hit(kind, "scope", _scope_label(pf), _scope_label(cf)))
    elif ps.restricted_to and not cs.restricted_to and cs.quantifier != "specific":
        hits.append(Hit(T.scope_widened, "scope.restricted_to", ps.restricted_to, cs.quantifier))
    elif cs.restricted_to and not ps.restricted_to and ps.quantifier != "specific":
        hits.append(Hit(T.scope_narrowed, "scope.restricted_to", ps.quantifier, cs.restricted_to))

    if pf.restriction_hasr and not cf.restriction_hasr:
        hits.append(Hit(T.hasr_lost, "restriction_hasr", "true", "false"))

    pr, cr = _CONSENSUS_RANK[pf.consensus_claim], _CONSENSUS_RANK[cf.consensus_claim]
    if pr >= 1 and cr > pr:
        hits.append(Hit(T.consensus_inflated, "consensus_claim", pf.consensus_claim, cf.consensus_claim))

    p_grades = {h.grade_stated for h in pf.hadith_mentions} - {"none"}
    c_grades = {h.grade_stated for h in cf.hadith_mentions} - {"none"}
    for g in sorted(p_grades - c_grades):
        hits.append(Hit(T.hadith_grade_dropped, "hadith_mentions.grade_stated", g, "", match_key=g))

    if pf.negations != cf.negations:  # محسوبة بالقواعد؛ الصياغة قد تغيّرها فالثقة أقل
        hits.append(Hit(T.negation_mismatch, "negations", str(pf.negations), str(cf.negations), confidence=0.6))

    if sorted(pf.numbers) != sorted(cf.numbers):
        hits.append(Hit(T.number_mismatch, "numbers", "، ".join(pf.numbers) or "لا شيء",
                        "، ".join(cf.numbers) or "لا شيء", confidence=0.9))
    return hits


def length_drop(parent_text: str, child_text: str, parent_lang: str, child_lang: str) -> Optional[Hit]:
    """يُطبَّق على النص كاملاً، وعند اتحاد اللغة فقط (عدد الكلمات لا يُقارن بين لغتين)."""
    if parent_lang != child_lang:
        return None
    pn, cn = len(tokens(parent_text)), len(tokens(child_text))
    if pn == 0 or cn / pn >= LENGTH_DROP_RATIO:
        return None
    pct = round((1 - cn / pn) * 100)
    return Hit(T.length_drop, "length", before=str(pct), after="", confidence=1.0)


# ---------- الشروح (قوالب ثابتة) ----------
_AR = {
    "definite": "جازم", "probable": "راجح", "possible": "محتمل", "unstated": "غير مصرَّح",
    "obligatory": "واجب", "recommended": "مستحب", "permissible": "مباح", "disliked": "مكروه",
    "forbidden": "محرّم", "none": "لا شيء", "all": "عام للجميع", "some": "بعض الناس", "specific": "فئة محددة",
    "unspecified": "غير محدد", "some_scholars": "بعض العلماء", "majority": "الجمهور", "ijma": "الإجماع",
    "prophet": "النبي ﷺ", "allah": "الله تعالى", "companion": "صحابي", "scholar": "عالم أو قول مأثور",
    "author": "كلام الكاتب", "sahih": "صحيح", "hasan": "حسن", "daif": "ضعيف",
}

TEMPLATES: dict[T, tuple[str, str]] = {
    T.condition_dropped: ("سقط الشرط «{before}» ولم يعد له مقابل في النسخة.",
                          "الحكم في الأصل مقيّد بشرط. حين يسقط الشرط يظن القارئ أن الحكم عام لكل أحد وفي كل حال."),
    T.exception_dropped: ("سقط الاستثناء «{before}».",
                          "الاستثناء يُخرج حالات من الحكم. حذفه يجعل الحكم يشمل من استثناهم الأصل."),
    T.certainty_raised: ("ارتفعت درجة اليقين من «{before}» إلى «{after}».",
                         "الأصل يعرض القول احتمالاً أو ترجيحاً. تقديمه جازماً يوهم القارئ أنه مقطوع به."),
    T.attribution_upgraded: ("تحوّلت صيغة النسبة من التمريض («رُوي» أو «قيل») إلى الجزم.",
                             "«رُوي» و«قيل» تدلان على عدم الجزم بثبوت الخبر. تحويلهما إلى «قال» أو «ثبت» ينسب الخبر جزماً بلا دليل."),
    T.new_prophetic_attribution: ("النسخة تنسب هذا الكلام إلى النبي ﷺ، والنص الأم لا ينسبه إليه (النسبة فيه: {before}).",
                                  "نسبة كلام إلى النبي ﷺ أمر خطير. هذه النسبة غير موجودة في النص الأم، فيجب التحقق منها قبل النشر."),
    T.ruling_shift: ("تغيّر نوع الحكم من «{before}» إلى «{after}».",
                     "نوع الحكم (واجب، مستحب، مباح، مكروه، محرّم) هو جوهر المعنى. تغييره يغيّر ما يفعله القارئ."),
    T.scope_widened: ("اتسع النطاق من «{before}» إلى «{after}».",
                      "الحكم في الأصل خاص بفئة أو حال. تعميمه يجعله يشمل من لم يقصدهم الأصل."),
    T.scope_narrowed: ("ضاق النطاق من «{before}» إلى «{after}».",
                       "الحكم في الأصل أعم. تخصيصه يُخرج منه من يشملهم الأصل."),
    T.hasr_lost: ("سقطت أداة الحصر (مثل «إنما» أو «لا… إلا»).",
                  "أداة الحصر تقصر الحكم على أمر واحد. سقوطها يفتح الباب لغيره."),
    T.consensus_inflated: ("ارتفعت دعوى الاتفاق من «{before}» إلى «{after}».",
                           "القول بأن المسألة إجماع أو قول الجمهور يختلف عن كونها قول بعض العلماء. المبالغة فيه تُخفي خلافاً معتبراً."),
    T.hadith_grade_dropped: ("حُذفت درجة الحديث المذكورة في الأم («{before}»).",
                             "درجة الحديث تبيّن مدى ثبوته. حذفها قد يجعل القارئ يظن الضعيف صحيحاً."),
    T.negation_mismatch: ("عدد أدوات النفي {before} في الأم و{after} في النسخة (عدٌّ آلي بالقواعد).",
                          "سقوط النفي أو زيادته قد يقلب المعنى إلى ضده. قد تكون الصياغة مختلفة فقط، فراجعها."),
    T.number_mismatch: ("الأرقام في الأم: {before}، وفي النسخة: {after}.",
                        "الأرقام (عدد الأيام، المقادير، الركعات) جزء من الحكم. أي اختلاف فيها يغيّر ما يُطلب من القارئ."),
    T.term_narrowing: ("تُرجم المصطلح «{before}» بلفظ «{after}»، وهذا يخالف ضابط استخدامه في المدونة.",
                       "للمصطلح الشرعي حدود. ترجمته بلفظ أشد أو أوسع أو أضيق يغيّر الحكم في ذهن القارئ."),
    T.length_drop: ("النسخة أقصر من أمّها بنحو {before}٪.",
                    "الاختصار الشديد مظنّة سقوط قيود أو تفاصيل مهمة. راجع ما حُذف."),
    T.sentence_dropped: ("هذه الجملة من الأصل ليس لها مقابل في النسخة.",
                         "قد تحمل الجملة المحذوفة حكماً أو قيداً يحتاجه القارئ."),
}


def explain(hit: Hit) -> tuple[str, str]:
    exp, why = TEMPLATES[hit.type]
    return exp.format(before=_AR.get(hit.before, hit.before), after=_AR.get(hit.after, hit.after)), why
