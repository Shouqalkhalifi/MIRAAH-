"""6.5 الميزان MIZAN: الاسترجاع من المدونة المحلية، ودرجات الدعم، وكاشف النسبة المختلقة.

- المدونة المحلية فقط (data/corpus). لا يولّد النموذج نصاً ولا مرجعاً أبداً: الميزان كله حتمي.
- كل «قال رسول الله ﷺ» وما في معناها يُبحث عن نصها في المدونة. إن لم يتجاوز التطابق العتبة فهي `unverified`
  مع العبارة الثابتة: «لم نعثر على هذا النص في المصادر المعتمدة المتاحة لمِرآة». لا يُقال «حديث مكذوب» أبداً.

درجات الدعم:
- supported: النص موجود في المدونة (تطابق ≥ 0.8) ودرجته مقبولة (صحيح/حسن أو قرآن).
- partially_supported: تطابق جزئي (0.5–0.8): الصياغة تختلف عن النص المعتمد.
- conflicting: وُجد النص لكن درجته في المدونة ضعيف/موضوع، أو الدرجة المذكورة في النص تخالف درجته في المدونة.
- unsupported: النص يحيل إلى آية برقمها (مثل 2:185) والآية موجودة في المدونة لكن النص المقتبس لا يطابقها.
- unverified: لم يُعثر عليه في المدونة ← امتناع وإحالة للمراجع.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from app.corpus import CorpusItem, load_corpus
from app.models import Alert, AlertType, Evidence, Report, Severity, Span, Verification
from app.pipeline.segment import split_sentences
from app.text.normalize import normalize_ar, tokens

NOT_FOUND_AR = "لم نعثر على هذا النص في المصادر المعتمدة المتاحة لمِرآة"

SUPPORTED_AT = 0.8
PARTIAL_AT = 0.5

# صيغ النسبة بعد التطبيع (ة←ه، ى←ي، أ←ا، ﷺ ← «صلي الله عليه وسلم» ثم تُحذف)
_PROPHET_CUES = [
    r"قال رسول الله", r"قال النبي", r"يقول النبي", r"يقول رسول الله", r"عن النبي", r"عن رسول الله",
    r"ان النبي", r"ان رسول الله", r"قول النبي", r"قول رسول الله", r"قال عليه الصلاه والسلام",
    r"the prophet(?: muhammad)? (?:has )?said", r"the messenger of allah (?:has )?said", r"the prophet says",
    r"prophet muhammad said", r"it was narrated that the prophet", r"le prophete a dit", r"le prophète a dit",
    r"le messager d'allah a dit",
]
_ALLAH_CUES = [r"قال الله تعالي", r"قال الله", r"قال تعالي", r"يقول الله تعالي", r"يقول الله", r"يقول تعالي",
               r"allah (?:says|said)", r"allah the exalted says", r"allah dit", r"allah a dit"]
_HONORIFICS = re.compile(r"صلي الله عليه وسلم|\(\s*(?:saw|pbuh|s\.a\.w\.?)\s*\)|\bpbuh\b|عليه السلام", re.I)
_QUOTED = re.compile(r"[«\"“﴿﴾](.+?)[»\"”﴿﴾]")
_QURAN_REF = re.compile(r"\b(\d{1,3})\s*:\s*(\d{1,3})\b")
_GRADE_WORDS = {"sahih": ["صحيح", "sahih", "authentic"], "hasan": ["حسن", "hasan"],
                "daif": ["ضعيف", "daif", "da'if", "weak", "faible"], "mawdu": ["موضوع", "fabricated", "mawdu"]}


class SearchHit(BaseModel):
    item: CorpusItem
    bm25: float
    containment: float


class Mizan:
    def __init__(self, items: list[CorpusItem]):
        self.items = items
        self._docs = [tokens(i.text_ar) + tokens(i.text_en) for i in items]
        self._bm25 = BM25Okapi(self._docs) if items else None

    def search(self, query: str, types: tuple[str, ...] = ("quran", "hadith"), k: int = 3) -> list[SearchHit]:
        q = tokens(query)
        if not q or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(q)
        hits = []
        for i, item in enumerate(self.items):
            if item.type not in types:
                continue
            cont = max(containment(q, tokens(item.text_ar)), containment(q, tokens(item.text_en)))
            if scores[i] > 0 or cont > 0:
                hits.append(SearchHit(item=item, bm25=float(scores[i]), containment=cont))
        hits.sort(key=lambda h: (h.containment, h.bm25), reverse=True)
        return hits[:k]


def containment(query: list[str], doc: list[str]) -> float:
    """نسبة كلمات النص المنسوب الموجودة في عنصر المدونة (تتحمل الاقتباس الجزئي من نص أطول)."""
    if not query or not doc:
        return 0.0
    d = set(doc)
    return sum(1 for t in query if t in d) / len(query)


def in_order(quote: str, item: CorpusItem) -> bool:
    """كلمات الاقتباس الموجودة في النص المعتمد تأتي فيه بالترتيب نفسه (تُتجاهل الكلمات الزائدة)."""
    q = tokens(quote)
    for doc in (tokens(item.text_ar), tokens(item.text_en)):
        common = [t for t in q if t in set(doc)]
        if not common:
            continue
        pos, ok = 0, True
        for t in common:
            try:
                pos = doc.index(t, pos) + 1
            except ValueError:
                ok = False
                break
        if ok:
            return True
    return False


@lru_cache(maxsize=1)
def default_mizan() -> Mizan:
    return Mizan(load_corpus())


def _stated_grade(text: str) -> Optional[str]:
    t = normalize_ar(text)
    for g, words in _GRADE_WORDS.items():
        if any(re.search(rf"\b{re.escape(normalize_ar(w))}\b", t) for w in words):
            return g
    return None


def find_attributions(text: str) -> list[tuple[str, str, str]]:
    """يعيد [(to, cue, quote)] لكل نسبة صريحة إلى النبي ﷺ أو إلى الله في الجملة.

    quote = ما بين علامات الاقتباس في النص الأصلي إن وُجد، وإلا ما بعد صيغة النسبة (مطبَّعاً).
    """
    norm = re.sub(r"\s+", " ", _HONORIFICS.sub(" ", normalize_ar(text)))
    quoted = _QUOTED.search(text)
    out = []
    for to, cues in (("prophet", _PROPHET_CUES), ("allah", _ALLAH_CUES)):
        for cue in cues:
            m = re.search(cue, norm)
            if m:
                quote = quoted.group(1) if quoted else norm[m.end():]
                out.append((to, m.group(0), quote.strip(" :،,.-—")))
                break
    return out


def verify(text: str, label: str, sentence_index: int, mizan: Mizan | None = None) -> list[Verification]:
    mizan = mizan or default_mizan()
    out = []
    for to, cue, quote in find_attributions(text):
        types = ("hadith",) if to == "prophet" else ("quran",)
        hits = mizan.search(quote or text, types=types)
        best = hits[0] if hits else None
        v = Verification(label=label, sentence_index=sentence_index, attributed_to=to, cue=cue, quote=quote,
                         status="unverified", note_ar=NOT_FOUND_AR)
        if best and best.containment >= PARTIAL_AT:
            it = best.item
            v.score, v.item_id, v.item_text, v.item_grade = round(best.containment, 2), it.id, it.text_ar, it.grade
            v.source_name, v.source_url = it.source_name, it.source_url
            stated = _stated_grade(text)
            if it.grade in ("daif", "mawdu") or (stated and it.grade and stated != it.grade):
                v.status, v.note_ar = "conflicting", f"وُجد النص في المدونة ودرجته فيها: {it.grade}"
            elif best.containment >= SUPPORTED_AT and in_order(quote or text, it):
                v.status, v.note_ar = "supported", "النص موجود في المدونة المحلية"
            elif best.containment >= SUPPORTED_AT:  # الألفاظ نفسها بترتيب آخر قد تقلب المعنى (اليسر ↔ العسر)
                v.status, v.note_ar = "partially_supported", "الألفاظ موجودة لكن ترتيبها يختلف عن النص المعتمد"
            else:
                v.status, v.note_ar = "partially_supported", "تطابق جزئي: الصياغة تختلف عن النص المعتمد"
        elif to == "allah":
            ref = _QURAN_REF.search(text)
            ref_item = next((i for i in mizan.items if ref and i.id.startswith(f"q-{ref.group(1)}-{ref.group(2)}-")), None)
            if ref_item:
                v.status, v.item_id, v.item_text = "unsupported", ref_item.id, ref_item.text_ar
                v.source_name, v.source_url = ref_item.source_name, ref_item.source_url
                v.note_ar = "الآية المشار إليها برقمها لا تطابق النص المقتبس"
        out.append(v)
    return out


# ---------- من نتائج الميزان إلى تنبيهات ----------
_STATUS_ALERT = {
    "unverified": (AlertType.unverified_attribution, Severity.red),
    "conflicting": (AlertType.source_conflict, Severity.red),
    "unsupported": (AlertType.source_conflict, Severity.red),
    "partially_supported": (AlertType.quote_wording_differs, Severity.yellow),
}
_TO_AR = {"prophet": "النبي ﷺ", "allah": "الله تعالى"}
_GRADE_AR = {"sahih": "صحيح", "hasan": "حسن", "daif": "ضعيف", "mawdu": "موضوع"}


def _texts(v: Verification) -> tuple[str, str]:
    to = _TO_AR[v.attributed_to]
    if v.status == "unverified":
        return (f"{NOT_FOUND_AR}: «{v.quote}» (منسوب إلى {to}). يُحال إلى المراجع.",
                f"نسبة الكلام إلى {to} تحتاج مصدراً معتمداً. مِرآة لا تحكم على النص، لكنها لم تجده في مدونتها، فيلزم التحقق البشري قبل النشر.")
    if v.status == "conflicting":
        return (f"وُجد هذا النص في المدونة ({v.source_name})، ودرجته فيها «{_GRADE_AR.get(v.item_grade or '', v.item_grade)}»، "
                "وهي لا توافق طريقة عرضه هنا.",
                "عرض حديث ضعيف أو مختلف في درجته كأنه ثابت يضلّل القارئ. اذكر الدرجة أو راجع النص.")
    if v.status == "unsupported":
        return ("الآية المشار إليها برقمها لا تطابق النص المقتبس.",
                "الإحالة إلى آية بنص لا يطابقها تنسب إلى القرآن ما ليس فيه بلفظه. راجع الاقتباس أو الرقم.")
    return (f"الصياغة تختلف جزئياً عن النص المعتمد في المدونة ({v.source_name}).",
            "حين يُنسب الكلام إلى النبي ﷺ أو إلى الله تُراعى ألفاظه. اختلاف الصياغة قد يكون ترجمة مقبولة، فراجعه.")


def check_report(report: Report, mizan: Mizan | None = None) -> tuple[list[Verification], list[Alert]]:
    """يفحص الأصل وكل نسخة، ويعيد كل نتائج الميزان والتنبيهات (مع وراثة الخلل عبر السلسلة)."""
    mizan = mizan or default_mizan()
    texts = {"source": report.source.text, **{v.label: v.text for v in report.versions}}
    parent_of = {v.label: v.derived_from for v in report.versions}
    order = ["source"] + [v.label for v in report.versions]

    def ancestors(label: str) -> list[str]:
        out = []
        while label != "source":
            label = parent_of[label]
            out.append(label)
        return out

    verifications: list[Verification] = []
    records: list[tuple[Verification, Alert]] = []
    for label in order:
        for seg in split_sentences(texts[label]):
            for v in verify(seg.text, label, seg.index, mizan):
                verifications.append(v)
                if v.status == "supported":
                    continue
                anc = ancestors(label)
                prev = next((a for pv, a in records if pv.label in anc and pv.attributed_to == v.attributed_to
                             and pv.status == v.status), None)
                if prev:
                    if label not in prev.propagated_to:
                        prev.propagated_to.append(label)
                    continue
                kind, sev = _STATUS_ALERT[v.status]
                exp, why = _texts(v)
                evidence = [Evidence(kind="corpus", ref=v.item_id or "—",
                                     detail=(f"{v.source_name} {v.source_url}".strip() if v.item_id
                                             else "بحث BM25 في المدونة المحلية بلا نتيجة فوق العتبة"))]
                span = Span(text=seg.text, start=seg.start, end=seg.end, sentence_index=seg.index)
                records.append((v, Alert(
                    type=kind, severity=sev, content_level=report.source.content_level,
                    source_span=span if label == "source" else Span(),
                    version_span=span if label != "source" else Span(),
                    version_label=label, introduced_at=label, explanation_ar=exp, why_it_matters_ar=why,
                    evidence=evidence, confidence=0.9 if v.status == "unverified" else round(max(v.score, 0.5), 2),
                    source_sentence_indices=[seg.index] if label == "source" else [],
                    source_context=seg.text if label == "source" else "",
                    version_context=seg.text if label != "source" else "",
                )))
    return verifications, [a for _, a in records]
