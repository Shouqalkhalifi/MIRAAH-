"""تقسيم الجمل بالقواعد للعربية والإنجليزية والهندية (الدَّنْدا «।»).

يعيد كل جملة مع موضعها (start, end) في النص الأصلي حتى تبقى التنبيهات قابلة للتتبع.
ملاحظة: لا نقسم عند «؛» و«،» لأنها كثيراً ما تفصل الحكم عن شرطه داخل الجملة الواحدة.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

TERMINATORS = ".!?؟۔।॥"
CLOSERS = "\"'»”’)]﴿﴾}"

_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "st", "no", "vol",
    "p", "pp", "ch", "cf", "al", "ibid", "approx", "ca", "fig", "ed", "eds", "trans",
}


class Segment(BaseModel):
    index: int
    text: str
    start: int
    end: int


def _is_abbreviation(text: str, dot: int) -> bool:
    m = re.search(r"([A-Za-z][A-Za-z.]*)$", text[:dot])
    if not m:
        return False
    word = m.group(1).lower().rstrip(".")
    if word in _ABBREVIATIONS:
        return True
    return len(word) == 1 and text[dot - 1].isupper()  # أحرف أولى للأسماء: "A. Smith"


def _is_boundary(text: str, i: int) -> bool:
    ch = text[i]
    if ch not in TERMINATORS:
        return False
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if ch == ".":
        prev = text[i - 1] if i > 0 else ""
        if prev.isdigit() and nxt.isdigit():  # 3.5
            return False
        if nxt == "." or prev == ".":  # ...
            return nxt != "." and _followed_by_break(text, i)
        if _is_abbreviation(text, i):
            return False
    if nxt and nxt in TERMINATORS:  # ?! أو ؟!
        return False
    return _followed_by_break(text, i)


def _followed_by_break(text: str, i: int) -> bool:
    j = i + 1
    while j < len(text) and text[j] in CLOSERS:
        j += 1
    return j >= len(text) or text[j].isspace()


def split_sentences(text: str) -> list[Segment]:
    segments: list[Segment] = []
    start = 0
    n = len(text)

    def emit(s: int, e: int) -> None:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            segments.append(Segment(index=len(segments), text=text[s:e], start=s, end=e))

    i = 0
    while i < n:
        if text[i] == "\n":
            emit(start, i)
            start = i + 1
        elif _is_boundary(text, i):
            j = i + 1
            while j < n and text[j] in CLOSERS:
                j += 1
            emit(start, j)
            start = j
            i = j
            continue
        i += 1
    emit(start, n)
    return segments
