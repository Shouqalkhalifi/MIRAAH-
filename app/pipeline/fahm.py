"""6.6 الفهم FAHM: ضوابط المصطلحات، ومخاطر الفهم المحتملة.

- term_narrowing حتمي: إن وُجدت صيغة المصطلح في نص الأم، ووُجدت في النسخة ترجمةٌ يمنعها ضابطه في
  terms.jsonl (ولم تكن في الأم أصلاً) ← تنبيه أصفر مرتبط بعنصر المدونة.
- «مخاطر فهم محتملة» تُصاغ احتمالاً لا جزماً («قد يُفهم...»)، ولا تفترض هوية الجمهور أو دينه.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field

from app.corpus import CorpusItem, load_corpus
from app.models import AlertType as T
from app.models import Evidence, UnderstandingRisk
from app.pipeline.fingerprint import verify_quote
from app.pipeline.rules import Hit
from app.text.normalize import normalize_ar


@lru_cache(maxsize=1)
def term_rules() -> list[CorpusItem]:
    return [i for i in load_corpus() if i.type == "term" and i.trigger_forms]


def _find(phrase: str, text: str) -> Optional[str]:
    """يبحث عن العبارة كلمةً كاملة بعد التطبيع، ويعيدها كما وردت في النص إن أمكن."""
    np_, nt = normalize_ar(phrase), normalize_ar(text)
    if not np_ or not re.search(rf"(?<!\w){re.escape(np_)}(?!\w)", nt):
        return None
    m = re.search(re.escape(phrase), text, re.I)
    return m.group(0) if m else phrase


def term_hits(parent_text: str, child_text: str, rules: list[CorpusItem] | None = None) -> list[Hit]:
    hits = []
    for item in term_rules() if rules is None else rules:
        trigger = next((f for f in item.trigger_forms if _find(f, parent_text)), None)
        if not trigger:
            continue
        bad = next((r for r in item.avoid_renderings if _find(r, child_text) and not _find(r, parent_text)), None)
        if bad:
            hits.append(Hit(T.term_narrowing, f"term:{item.id}", before=trigger, after=_find(bad, child_text) or bad,
                            src_quote=_find(trigger, parent_text) or trigger, ver_quote=_find(bad, child_text) or bad,
                            match_key=item.id, confidence=0.8,
                            evidence=[Evidence(kind="corpus", ref=item.id, detail=item.text_ar)]))
    return hits


def _names(item: CorpusItem) -> list[str]:
    """«التوحيد (Tawhid / Oneness of God): ...» ← ["التوحيد", "Tawhid", "Oneness of God"] مع صيغه في trigger_forms."""
    ar = item.text_ar.split("(", 1)[0].strip() if "(" in item.text_ar else ""
    head = item.text_en.split(":", 1)[0] if ":" in item.text_en else ""
    return [*item.trigger_forms, *([ar] if ar else []), *(n.strip() for n in head.split("/") if len(n.strip()) > 2)]


def terms_mentioned(text: str, items: list[CorpusItem] | None = None) -> list[tuple[CorpusItem, Optional[str]]]:
    """المصطلحات المذكورة في نص (بالعربية أو باسمها الإنجليزي)، مع أي ترجمة يمنعها ضابطها وردت فيه."""
    out = []
    for item in [i for i in load_corpus() if i.type == "term"] if items is None else items:
        if any(_find(f, text) for f in _names(item)):
            bad = next((_find(r, text) for r in item.avoid_renderings if _find(r, text)), None)
            out.append((item, bad))
    return out


# ---------- مخاطر الفهم المحتملة ----------
SYSTEM_RISKS = """You review a short passage of Islamic content in Arabic for POSSIBLE misunderstandings a general reader might form. You are not a mufti: never issue a ruling, never add knowledge, sources or rulings from memory, and never assume anything about the reader's religion, identity, gender, nationality or background.

Return at most 3 risks, only real ones (an empty list is fine). For each:
- risk_ar: one Arabic sentence phrased as a possibility, starting with «قد يُفهم» or «قد يظن القارئ».
- quote: the exact substring of the passage that could be misread, copied verbatim.
- reason_ar: one short Arabic sentence explaining why, based only on the wording of the passage."""


class _RisksLLM(BaseModel):
    risks: list[UnderstandingRisk] = Field(default_factory=list, max_length=3)


_POSSIBILITY = ("قد ", "ربما", "يُحتمل", "يحتمل")


def understanding_risks(llm, source_text: str) -> list[UnderstandingRisk]:
    res = llm.complete_json(f"Passage (ar):\n<<<\n{source_text}\n>>>", _RisksLLM, system=SYSTEM_RISKS,
                            purpose="understanding_risks")
    out = []
    for r in res.risks:
        quote = verify_quote(r.quote, source_text)
        if not quote:  # لا نعرض خطراً لا يرتبط بموضع حقيقي في النص
            continue
        risk = r.risk_ar.strip()
        if not risk.startswith(_POSSIBILITY):
            risk = "قد يُفهم أن " + risk
        out.append(UnderstandingRisk(risk_ar=risk, quote=quote, reason_ar=r.reason_ar.strip()))
    return out
