"""تصدير تقرير المقابلة بعد اعتماد المراجع: JSON و HTML قابل للطباعة، للاستخدام الداخلي فقط."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import ui
from app.models import Report
from app.pipeline.locks import LOCK_TYPE_AR

TITLE = "تقرير مقابلة – للاستخدام الداخلي، وليس شهادة اعتماد عامة"
RIYADH = timezone(timedelta(hours=3), "Asia/Riyadh")  # الرياض بلا توقيت صيفي، فلا حاجة إلى tzdata
LANG_AR = {"ar": "العربية", "en": "الإنجليزية", "fr": "الفرنسية", "id": "الإندونيسية", "ur": "الأردية"}
ACTION_AR = {"edit": "طُبّق التصحيح", "reject": "ليس خطأ", "accept": "أُحيل للمختص"}  # accept: خلل في الأصل نفسه
SEVERITY_AR = {"red": "خطير", "yellow": "متوسط", "info": "للعلم"}


def riyadh_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(RIYADH).strftime("%Y-%m-%d %H:%M") + " (بتوقيت الرياض)"


def approved_text(r: Report, label: str, text: str) -> tuple[str, list[str]]:
    """نص الحلقة بعد الصياغات التي اعتمدها المراجع لمواضعها. الأصل لا يُعدَّل أبداً."""
    applied = []
    for a in r.alerts:
        d = r.decisions.get(a.id)
        frag = a.version_span.text
        if a.version_label != label or not d or d.action != "edit" or not d.edited_text or not frag:
            continue
        if frag in text:
            text = text.replace(frag, d.edited_text.strip(), 1)
            applied.append(a.id)
    return text, applied


def build(r: Report, disclaimer: str) -> dict:
    nodes = {n["label"]: n for n in ui.thread(r)}
    chain = [{"label": "source", "name": "الأصل", "lang": r.source.lang, "derived_from": None,
              "medium": None, "medium_ar": "",
              "state": nodes["source"]["state"], "original_text": r.source.text, "approved_text": r.source.text,
              "applied_edits": []}]
    for v in r.versions:
        text, applied = approved_text(r, v.label, v.text)
        chain.append({"label": v.label, "name": v.label, "lang": v.lang, "derived_from": v.derived_from,
                      "medium": v.medium, "medium_ar": ui.MEDIUM_AR.get(v.medium or "", ""),
                      "state": nodes[v.label]["state"], "original_text": v.text, "approved_text": text,
                      "applied_edits": applied})
    alerts = []
    for a in r.alerts:
        d = r.decisions.get(a.id)
        alerts.append({
            "id": a.id, "type": a.type.value, "severity": a.severity.value,
            "severity_ar": SEVERITY_AR[a.severity.value], "headline_ar": ui.headline(a),
            "explanation_ar": a.explanation_ar, "version_label": a.version_label, "introduced_at": a.introduced_at,
            "source_span": a.source_span.text, "version_span": a.version_span.text,
            "decision": None if d is None else {
                "action": d.action, "action_ar": ACTION_AR[d.action], "reason": d.reason,
                "edited_text": d.edited_text,
                "decided_at": riyadh_time(d.decided_at),
            },
        })
    return {
        "title": TITLE,
        "report_id": r.id,
        "report_title": r.title,
        "approved_at": riyadh_time(r.approved_at),
        "source": {"text": r.source.text, "lang": r.source.lang, "source_ref": r.source.source_ref,
                   "content_level": r.source.content_level.value},
        "chain": chain,
        "alerts": alerts,
        "locks": [{"span_text": x["lock"].span_text, "lock_type": x["lock"].lock_type.value,
                   "lock_type_ar": LOCK_TYPE_AR[x["lock"].lock_type.value], "status_ar": x["tag"],
                   "where": x["where"]} for x in ui.lock_rows(r)["rows"]],
        "disclaimer": disclaimer,
    }
