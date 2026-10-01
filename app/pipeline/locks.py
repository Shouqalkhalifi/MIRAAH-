"""6.9 أقفال المعنى.

- المستخدم يحدد مقاطع في الأصل ويختار نوع القفل، أو يضغط «اقترح أقفالاً» فتُقترح من البصمة (الشروط
  والاستثناءات) ومن صيغ ثابتة في النص (اليقين، والنسبة، والدرجات، والنفي، والأرقام، والمصطلحات).
- أي نسخة لا تحفظ معنى القفل ← lock_violated أحمر.
- الأرقام والنفي تُفحص بالقواعد؛ وبقية الأنواع بالتحقق الموجّه مع اقتباس حرفي من النسخة.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from app.models import Lock, LockType
from app.pipeline.fahm import term_rules
from app.pipeline.fingerprint import count_negations, extract_numbers, verify_quote
from app.pipeline.segment import split_sentences
from app.text.normalize import normalize_ar

LOCK_TYPE_AR = {"condition": "شرط", "certainty": "يقين", "exception": "استثناء", "attribution": "نسبة",
                "grade": "درجة", "term": "مصطلح", "negation": "نفي", "number": "رقم"}

# صيغ ثابتة (بعد التطبيع) تُقترح أقفالاً
_CUES: dict[LockType, set[str]] = {
    LockType.certainty: {"قد", "ربما", "يحتمل", "الارجح", "الاظهر", "لعل", "يغلب"},
    LockType.attribution: {"روي", "يروي", "قيل", "يذكر", "يحكي", "ذكر"},
    LockType.grade: {"صحيح", "حسن", "ضعيف", "موضوع", "ضعفه", "صححه"},
    LockType.negation: {"لا", "لم", "لن", "ليس", "ليست"},
}
_PROPHET = re.compile(r"(قال|عن|ان)\s+(رسول\s+الله|النبي)")
_WORD = re.compile(r"\S+")
_PUNCT = "«»\"'“”،,.؛;:!?؟()[]﴿﴾"


def _norm_token(tok: str) -> str:
    return normalize_ar(tok.strip(_PUNCT))


def lock_in_text(span: str, text: str) -> bool:
    return bool(span.strip()) and normalize_ar(span) in normalize_ar(text)


def suggest_locks(source_text: str, fingerprint_fn: Callable[[str], object] | None = None) -> list[Lock]:
    """أقفال مقترحة من الأصل. fingerprint_fn(sentence) ← Fingerprinted (اختياري، لاقتراح الشروط والاستثناءات)."""
    out: dict[str, Lock] = {}

    def add(span: str, kind: LockType):
        span = span.strip(_PUNCT + " ")
        if span and lock_in_text(span, source_text) and span not in out:
            out[span] = Lock(span_text=span, lock_type=kind, origin="auto")

    for seg in split_sentences(source_text):
        if fingerprint_fn:
            fp = fingerprint_fn(seg.text)
            for q in fp.condition_quotes:
                if q:
                    add(q, LockType.condition)
            for q in fp.exception_quotes:
                if q:
                    add(q, LockType.exception)
        for tok in _WORD.findall(seg.text):
            n = _norm_token(tok)
            for kind, cues in _CUES.items():
                if n in cues or (len(n) > 2 and n[0] in "وف" and n[1:] in cues):
                    add(tok, kind)
            if extract_numbers(tok):
                add(tok, LockType.number)
        m = _PROPHET.search(normalize_ar(seg.text))
        if m:
            words = seg.text.split()
            add(" ".join(words[: len(m.group(0).split())]) if normalize_ar(seg.text).startswith(m.group(0))
                else m.group(0), LockType.attribution)
        for item in term_rules():
            for form in item.trigger_forms:
                if lock_in_text(form, seg.text):
                    add(form, LockType.term)
    return list(out.values())


PresenceFn = Callable[[str, str, str, str, str], Optional[str]]


def check_lock(lock: Lock, source_ctx: str, version_text: str, version_lang: str,
               presence_fn: Optional[PresenceFn]) -> Optional[str]:
    """يعيد دليلاً (اقتباساً أو وصفاً) إن حُفظ معنى القفل في النسخة، وإلا None."""
    if not version_text.strip():
        return None
    if lock.lock_type == LockType.number:
        need = extract_numbers(lock.span_text)
        have = extract_numbers(version_text)
        return "، ".join(need) if need and all(have.count(n) >= need.count(n) for n in set(need)) else None
    if lock.lock_type == LockType.negation:
        return "النفي محفوظ" if count_negations(version_text) >= max(1, count_negations(lock.span_text)) else None
    direct = verify_quote(lock.span_text, version_text)  # النسخة بالعربية وفيها المقطع نفسه
    if direct:
        return direct
    if presence_fn is None:
        return None
    return presence_fn(lock.span_text, f"{lock.lock_type.value} (meaning lock)", source_ctx, version_text, version_lang)
