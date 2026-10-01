"""6.4 السلسلة: تحديد الحلقة التي دخل فيها الخلل.

- كل حلقة تُقارن **بالأصل** (بتركيب المحاذاة على طول السلسلة): هذا يحدد الثوابت المكسورة.
- `introduced_at` = أول حلقة في المسار من الأصل ظهر فيها الخلل نفسه. الحلقات اللاحقة التي ورثته
  تُسجَّل في `propagated_to` بدل تكرار التنبيه.
- وتُقارن الحلقة **بأمها** مباشرة: إن لم يظهر الخلل في هذه المقارنة تنخفض الثقة.

الدوال الخارجية (المحاذاة والبصمة) تُمرَّر حقناً، فيمكن اختبار السلسلة بلا نموذج.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from app.models import Alert, Evidence, Report, Span
from app.models import AlertType as T
from app.pipeline.align import Unit, build_units, compose, units_to_links
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.rules import Hit, compare_unit, explain, length_drop, phrases_match
from app.pipeline.segment import split_sentences

STAGES: list[tuple[str, str]] = [
    ("segment", "تقسيم الجمل"),
    ("align", "محاذاة كل نسخة بحلقتها الأم"),
    ("fingerprint", "استخراج بصمة المعنى"),
    ("compare", "مقارنة البصمات وتطبيق القواعد"),
    ("chain", "تحديد الحلقة التي دخل فيها الخلل"),
]

AlignFn = Callable[[list[str], list[str], str, str], list[Unit]]
FingerprintFn = Callable[[str, str], Fingerprinted]
# (العبارة، النوع، نص الأم، نص النسخة، لغة النسخة) ← اقتباس من النسخة إن وُجدت فيها، وإلا None
PresenceFn = Callable[[str, str, str, str, str], Optional[str]]
_PRESENCE_TYPES = {T.condition_dropped: "condition", T.exception_dropped: "exception"}

_SEV_ORDER = {"red": 0, "yellow": 1, "info": 2}


@dataclass
class _Found:
    hit: Hit
    unit: Unit  # وحدة المقارنة مع الأصل: parent = جمل الأصل، child = جمل هذه الحلقة


def _join(sents: list[str], idx: tuple[int, ...]) -> str:
    return " ".join(sents[i] for i in idx)


def _same(a: _Found, b: _Found) -> bool:
    if a.hit.type != b.hit.type:
        return False
    if a.unit.parent or b.unit.parent:
        if not set(a.unit.parent) & set(b.unit.parent):
            return False
    if a.hit.match_key or b.hit.match_key:
        return a.hit.match_key == b.hit.match_key or phrases_match(a.hit.match_key, b.hit.match_key)
    return True


def _hit_in(hit: Hit, hits: list[Hit]) -> bool:
    return any(h.type == hit.type and (not hit.match_key or h.match_key == hit.match_key
                                       or phrases_match(h.match_key, hit.match_key)) for h in hits)


def analyze_chain(report: Report, align_fn: AlignFn, fp_fn: FingerprintFn,
                  progress: Callable[[str], None] = lambda s: None, max_workers: int = 4,
                  presence_fn: Optional[PresenceFn] = None) -> list[Alert]:
    src = report.source
    langs = {"source": src.lang, **{v.label: v.lang for v in report.versions}}
    texts = {"source": src.text, **{v.label: v.text for v in report.versions}}
    parent_of = {v.label: v.derived_from for v in report.versions}
    order = [v.label for v in report.versions]

    def path(label: str) -> list[str]:  # من أول حلقة بعد الأصل حتى الحلقة نفسها
        out = []
        while label != "source":
            out.append(label)
            label = parent_of[label]
        return out[::-1]

    # 1) التقسيم
    progress("segment")
    sents = {k: [s.text for s in split_sentences(t)] for k, t in texts.items()}
    n_src = len(sents["source"])

    # 2) المحاذاة المحلية (كل حلقة بأمها) ثم تركيبها حتى الأصل
    progress("align")
    with ThreadPoolExecutor(max_workers) as ex:
        futures = {lb: ex.submit(align_fn, sents[parent_of[lb]], sents[lb], langs[parent_of[lb]], langs[lb])
                   for lb in order}
        local_units = {lb: f.result() for lb, f in futures.items()}
    to_source: dict[str, dict[int, set[int]]] = {"source": {i: {i} for i in range(n_src)}}
    cum_units: dict[str, list[Unit]] = {}
    for lb in order:
        to_source[lb] = compose(units_to_links(local_units[lb]), to_source[parent_of[lb]])
        cum_units[lb] = build_units(to_source[lb], n_src, len(sents[lb]))

    # 3) البصمات: كل نص وحدة مرة واحدة (والـcache في llm يمنع التكرار بين التشغيلات)
    progress("fingerprint")
    needed: set[tuple[str, str]] = set()
    for lb in order:
        for u in cum_units[lb]:
            if u.parent:
                needed.add((_join(sents["source"], u.parent), src.lang))
            if u.child:
                needed.add((_join(sents[lb], u.child), langs[lb]))
        if parent_of[lb] != "source":
            pl = parent_of[lb]
            for u in local_units[lb]:
                if u.parent:
                    needed.add((_join(sents[pl], u.parent), langs[pl]))
                if u.child:
                    needed.add((_join(sents[lb], u.child), langs[lb]))
    keys = sorted(needed)
    with ThreadPoolExecutor(max_workers) as ex:
        fps = dict(zip(keys, ex.map(lambda k: fp_fn(*k), keys)))

    def fp(label: str, idx: tuple[int, ...]) -> Optional[Fingerprinted]:
        return fps[(_join(sents[label], idx), langs[label])] if idx else None

    # 4) المقارنة: مع الأصل (تراكمية) ومع الأم (محلية)
    progress("compare")
    def unit_hits(pl: str, lb: str, u: Unit) -> list[Hit]:
        hits = compare_unit(fp(pl, u.parent), fp(lb, u.child))
        if presence_fn is None or not u.child:
            return hits
        # الشرط/الاستثناء «الساقط» قد يكون استخراجاً غير متسق بين اللغتين: تحقق موجّه قبل التنبيه
        kept = []
        for h in hits:
            if h.type in _PRESENCE_TYPES and presence_fn(
                    h.match_key, _PRESENCE_TYPES[h.type], _join(sents[pl], u.parent), _join(sents[lb], u.child), langs[lb]):
                continue
            kept.append(h)
        return kept

    cum: dict[str, list[_Found]] = {}
    local: dict[str, list[Hit]] = {}
    for lb in order:
        cum[lb] = [_Found(h, u) for u in cum_units[lb] for h in unit_hits("source", lb, u)]
        pl = parent_of[lb]
        if pl == "source":
            local[lb] = [f.hit for f in cum[lb]]
        else:
            local[lb] = [h for u in local_units[lb] for h in unit_hits(pl, lb, u)]

    # 5) السلسلة: أول حلقة ظهر فيها الخلل
    progress("chain")
    records: list[tuple[str, _Found, Alert]] = []
    for lb in order:
        ancestors = path(lb)[:-1]
        for f in cum[lb]:
            prev = next((r for r in records if r[0] in ancestors and _same(r[1], f)), None)
            if prev:
                if lb not in prev[2].propagated_to:
                    prev[2].propagated_to.append(lb)
                continue
            confirmed = _hit_in(f.hit, local[lb])
            records.append((lb, f, _make_alert(report, f, lb, sents, confirmed)))
        lh = length_drop(texts[parent_of[lb]], texts[lb], langs[parent_of[lb]], langs[lb])
        if lh:
            records.append((lb, _Found(lh, Unit((), ())), _make_alert(report, _Found(lh, Unit((), ())), lb, sents, True)))

    alerts = [r[2] for r in records]
    alerts.sort(key=lambda a: (_SEV_ORDER[a.severity.value], a.source_sentence_indices[:1] or [10**6]))
    return alerts


def _make_alert(report: Report, f: _Found, label: str, sents: dict[str, list[str]], confirmed: bool) -> Alert:
    h, u = f.hit, f.unit
    exp, why = explain(h)
    src_text = h.src_quote or _join(sents["source"], u.parent)
    ver_text = h.ver_quote or _join(sents[label], u.child)
    evidence = [Evidence(kind="fingerprint", ref=h.field, detail=f"{h.before or '—'} → {h.after or '—'}")]
    if u.parent:
        evidence.append(Evidence(kind="text_span", ref=f"source:{','.join(map(str, u.parent))}",
                                 detail=_join(sents["source"], u.parent)))
    if h.type == T.length_drop:
        evidence = [Evidence(kind="text_span", ref=f"{label}:all", detail=f"أقصر بنحو {h.before}٪ من أمّها")]
        ver_text = report_version_text(report, label)
    conf = h.confidence if confirmed else round(h.confidence * 0.8, 2)
    if not confirmed:
        evidence.append(Evidence(kind="fingerprint", ref="local_check",
                                 detail="لم يظهر هذا الخلل عند مقارنة الحلقة بأمها مباشرة، فالثقة أقل"))
    return Alert(
        type=h.type, severity=h.severity, content_level=report.source.content_level,
        source_span=Span(text=src_text, sentence_index=u.parent[0] if u.parent else None),
        version_span=Span(text=ver_text, sentence_index=u.child[0] if u.child else None),
        version_label=label, introduced_at=label, explanation_ar=exp, why_it_matters_ar=why,
        evidence=evidence, confidence=conf, source_sentence_indices=list(u.parent),
    )


def report_version_text(report: Report, label: str) -> str:
    return next(v.text for v in report.versions if v.label == label)
