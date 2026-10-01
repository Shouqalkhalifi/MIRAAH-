"""حفظ التقارير في SQLite (التقرير كاملاً JSON في جدول reports)."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.db import get_engine
from app.models import Report, ReportRow


def save_report(report: Report) -> None:
    with Session(get_engine()) as s:
        s.merge(ReportRow(id=report.id, created_at=report.created_at, status=report.status.value,
                          data=report.model_dump_json()))
        s.commit()


def load_report(report_id: str) -> Optional[Report]:
    with Session(get_engine()) as s:
        row = s.get(ReportRow, report_id)
    return Report.model_validate_json(row.data) if row else None
