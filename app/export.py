"""تصدير تقرير المراجعة: JSON و HTML قابل للطباعة و PDF، للمراجعة قبل النشر لا شهادة اعتماد."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import ui
from app.models import Report
from app.pipeline.locks import LOCK_TYPE_AR

TITLE = "تقرير مراجعة مِرآة – للمراجعة قبل النشر، وليس شهادة اعتماد"
NOTICE_AR = ("هذا التقرير نتيجة فحص آلي مساعد يراجعه الإنسان قبل النشر، والقرار الأخير للمراجع البشري. "
             "ليس شهادة اعتماد، ولا يُصدر حكماً شرعياً.")
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


def report_ref(r: Report) -> str:
    """رقم تقرير مقروء: تاريخ الإنشاء بتوقيت الرياض ثم أربعة أرقام مشتقة من المعرّف (20261003-4821)."""
    created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
    try:
        n = int(r.id[:8], 16)
    except ValueError:
        n = sum(map(ord, r.id))
    return f"{created.astimezone(RIYADH):%Y%m%d}-{n % 10000:04d}"


def _verdict(r: Report) -> dict:
    """الإشارة الضوئية نفسها التي في صفحة التقرير: rubric لا تنشر · saffron يحتاج نظرة · verified جاهز."""
    if r.referral:
        return {"tone": "rubric", "text": "خارج نطاق مِرآة (المستوى D): يُحال إلى مختص قبل النشر"}
    s = ui.status_line(r)
    if s["tone"] == "verified":
        return {"tone": "verified", "text": "لم تجد مِرآة ما يمنع النشر، والقرار الأخير للمراجع"}
    return s


def build(r: Report, disclaimer: str) -> dict:
    nodes = {n["label"]: n for n in ui.thread(r)}
    names = ui.version_names(r)
    chain = [{"label": "source", "name": "الأصل", "lang": r.source.lang, "derived_from": None, "derived_from_name": "",
              "medium": None, "medium_ar": "",
              "state": nodes["source"]["state"], "original_text": r.source.text, "approved_text": r.source.text,
              "applied_edits": []}]
    for v in r.versions:
        text, applied = approved_text(r, v.label, v.text)
        chain.append({"label": v.label, "name": names[v.label], "lang": v.lang, "derived_from": v.derived_from,
                      "derived_from_name": names.get(v.derived_from or "source", "الأصل"),
                      "medium": v.medium, "medium_ar": ui.MEDIUM_AR.get(v.medium or "", ""),
                      "state": nodes[v.label]["state"], "original_text": v.text, "approved_text": text,
                      "applied_edits": applied})
    alerts = []
    for a in r.alerts:
        d = r.decisions.get(a.id)
        alerts.append({
            "id": a.id, "type": a.type.value, "severity": a.severity.value,
            "severity_ar": SEVERITY_AR[a.severity.value], "headline_ar": ui.headline(a),
            "explanation_ar": ui.name_text(r, a.explanation_ar, a), "version_label": a.version_label,
            "introduced_at": a.introduced_at, "version_name": names.get(a.version_label, a.version_label),
            "introduced_name": names.get(a.introduced_at, a.introduced_at),
            "source_span": a.source_span.text, "version_span": a.version_span.text,
            "why_it_matters_ar": ui.name_text(r, a.why_it_matters_ar, a),
            "suggestions": [{"label_ar": s.label_ar, "text": s.text}
                            for s in r.revisions.get(a.id, []) if s.passed],
            "decision": None if d is None else {
                "action": d.action, "action_ar": ACTION_AR[d.action], "reason": d.reason,
                "edited_text": d.edited_text,
                "decided_at": riyadh_time(d.decided_at),
            },
        })
    return {
        "title": TITLE,
        "report_id": r.id,
        "report_ref": report_ref(r),
        "report_title": r.title,
        "approved_at": riyadh_time(r.approved_at),
        "exported_at": riyadh_time(datetime.now(timezone.utc)),
        "notice_ar": NOTICE_AR,
        "verdict": _verdict(r),
        "source": {"text": r.source.text, "lang": r.source.lang, "source_ref": r.source.source_ref,
                   "content_level": r.source.content_level.value},
        "chain": chain,
        "alerts": alerts,
        "locks": [{"span_text": x["lock"].span_text, "lock_type": x["lock"].lock_type.value,
                   "lock_type_ar": LOCK_TYPE_AR[x["lock"].lock_type.value], "status_ar": x["tag"],
                   "where": [{**w, "name": names.get(w["label"], w["label"])} for w in x["where"]]}
                  for x in ui.lock_rows(r)["rows"]],
        "disclaimer": disclaimer,
    }
