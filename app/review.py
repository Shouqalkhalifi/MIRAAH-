"""6.12 قرار المراجع: قبول/رفض/تعديل بسبب إلزامي، وسجل تدقيق، والنشر المقفل حتى حسم كل تنبيه أحمر."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db import get_engine
from app.models import AuditEntry, Decision, Report, ReportStatus
from app.store import load_report, save_report


class ReviewError(ValueError):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _audit(report_id: str, event: str, alert_id: str = "", payload: dict | None = None) -> None:
    with Session(get_engine()) as s:
        s.add(AuditEntry(report_id=report_id, event=event, alert_id=alert_id,
                         payload=json.dumps(payload or {}, ensure_ascii=False, default=str)))
        s.commit()


def audit_log(report_id: str) -> list[AuditEntry]:
    with Session(get_engine()) as s:
        return list(s.exec(select(AuditEntry).where(AuditEntry.report_id == report_id).order_by(AuditEntry.id)))


def _load(report_id: str) -> Report:
    r = load_report(report_id)
    if r is None:
        raise ReviewError("التقرير غير موجود", 404)
    return r


def blockers(r: Report) -> list[str]:
    """أسباب منع النشر (قائمة فارغة = جاهز)."""
    out = []
    if r.status != ReportStatus.analyzed:
        out.append("التقرير ليس في حالة «حُلِّل»")
    if r.referral:
        out.append("مستوى المحتوى D: يُحال إلى مختص")
    pending = [a.id for a in r.alerts if a.severity.value == "red" and a.id not in r.decisions]
    if pending:
        out.append(f"لم تُحسم {len(pending)} من التنبيهات الحمراء")
    return out


def decide(report_id: str, decision: Decision) -> Report:
    r = _load(report_id)
    if r.status == ReportStatus.published:
        raise ReviewError("التقرير منشور؛ القرارات مقفلة")
    if r.status != ReportStatus.analyzed:
        raise ReviewError("لا يمكن اتخاذ قرار قبل اكتمال التحليل")
    if not any(a.id == decision.alert_id for a in r.alerts):
        raise ReviewError("التنبيه غير موجود في هذا التقرير", 404)
    r.decisions[decision.alert_id] = decision
    save_report(r)
    _audit(r.id, "decision", decision.alert_id, decision.model_dump(mode="json"))
    return r


def publish(report_id: str, reviewer_role: str) -> Report:
    r = _load(report_id)
    if r.status == ReportStatus.published:
        return r
    problems = blockers(r)
    if problems:
        raise ReviewError("؛ ".join(problems))
    r.status, r.published_at, r.reviewer_role = ReportStatus.published, datetime.now(timezone.utc), reviewer_role
    save_report(r)
    _audit(r.id, "publish", payload={"reviewer_role": reviewer_role, "decisions": len(r.decisions)})
    return r
