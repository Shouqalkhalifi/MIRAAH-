"""«ماذا تعلّمت اليوم؟»: يقابل ما كتبه القارئ بكلمات الأصل بالقواعد وحدها، بلا نموذج ولا حفظ للنص.

مقابلة ألفاظ لا حكم على الفهم: تكشف ما نقص من كلمات الأصل المؤثرة، وتنبّه إلى نفيٍ ليس في الأصل.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from app.text.normalize import strip_diacritics, tokens

_STOP = {
    "في", "من", "على", "عن", "الي", "ان", "او", "ام", "ما", "هو", "هي", "هم", "ذلك", "هذا", "هذه", "التي", "الذي",
    "ثم", "قد", "مع", "عليه", "عليها", "عليهم", "له", "لها", "لهم", "به", "بها", "اذا", "انه", "انها", "كان", "كانت",
    "يكون", "اي", "حتي", "عند", "بعد", "قبل", "كما", "لان", "اما", "وهو", "وهي", "منه", "منها", "فيه", "فيها",
    "الا",
}
_NEGATIONS = {"لا", "ليس", "ليست", "لم", "لن", "غير", "ولا", "فلا", "ولم", "ولن", "وليس"}
_EXCEPT = {"الا", "سوي"}  # «لا… إلا» استثناء يثبت الحكم للمستثنى، فليس نفياً يقلب المعنى
_EXCEPT_REACH = 8
_PREFIXES = ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ل")
_SUFFIXES = ("هما", "هم", "ها", "ه", "ات")


def _stem(t: str) -> str:
    for p in _PREFIXES:
        if t.startswith(p) and len(t) - len(p) >= 3:
            t = t[len(p):]
            break
    for s in _SUFFIXES:
        if t.endswith(s) and len(t) - len(s) >= 3:
            return t[: -len(s)]
    return t


def _skeleton(t: str) -> str:
    """حروف الكلمة الأصلية تقريباً: بلا حرف المضارعة ولا حروف المدّ، فتلتقي «إفطار» و«يفطر» و«أفطره»."""
    if len(t) >= 4 and t[0] in "يتنا":
        t = t[1:]
    return "".join(c for c in t if c not in "اويىء")


def _close(a: str, b: str) -> bool:
    if a == b or (min(len(a), len(b)) >= 3 and SequenceMatcher(None, a, b).ratio() >= 0.75):
        return True
    sa, sb = _skeleton(a), _skeleton(b)
    return min(len(a), len(b)) >= 3 and len(sa) >= 2 and sa == sb


def _negations(text: str) -> int:
    toks = tokens(text)
    return sum(1 for i, t in enumerate(toks)
               if t in _NEGATIONS and not _EXCEPT.intersection(toks[i + 1:i + 1 + _EXCEPT_REACH]))


def check(source: str, answer: str) -> dict:
    """verdict: great (≥70٪ من كلمات الأصل المؤثرة) | close (≥40٪) | retry؛ ومعها الناقص من ألفاظ الأصل."""
    words: dict[str, str] = {}  # الجذع ← اللفظ كما في الأصل (بلا تشكيل)
    for raw in source.split():
        t = tokens(raw)
        if not t or t[0] in _STOP or t[0] in _NEGATIONS or len(t[0]) < 2:
            continue
        words.setdefault(_stem(t[0]), strip_diacritics(raw).strip(".,،؛:!?«»()"))
    got = [_stem(t) for t in tokens(answer) if t not in _STOP]
    matched = [s for s in words if any(_close(s, g) for g in got)]
    missing = [words[s] for s in words if s not in matched]
    score = len(matched) / len(words) if words else 0.0
    neg_added = _negations(answer) > _negations(source)
    neg_lost = _negations(answer) < _negations(source)
    verdict = "retry" if neg_added or neg_lost else ("great" if score >= 0.7 else "close" if score >= 0.4 else "retry")
    note = ("في عبارتك نفيٌ ليس في الأصل، فانقلب المعنى." if neg_added
            else "الأصل فيه نفيٌ سقط من عبارتك، فانقلب المعنى." if neg_lost else "")
    return {"verdict": verdict, "score": round(score, 2), "missing": missing[:6], "note": note}
