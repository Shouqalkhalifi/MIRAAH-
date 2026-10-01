"""تشغيل التحليل: من الطلب إلى تقرير محفوظ."""
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field, model_validator

from app.llm import get_llm
from app.models import Lock, Report, ReportStatus, Source, Version, validate_chain
from app.pipeline.align import align
from app.pipeline import mizan
from app.pipeline.chain import STAGES as CHAIN_STAGES
from app.pipeline.chain import analyze_chain
from app.pipeline.fingerprint import find_in_version, fingerprint
from app.pipeline.segment import split_sentences
from app.store import load_report, save_report

# مراحل التحليل كما تظهر في شريط التقدم
STAGES: list[tuple[str, str]] = CHAIN_STAGES + [
    ("mizan", "الميزان: البحث عن النصوص المنسوبة في المدونة"),
]

# يُستبدل في الاختبارات بنموذج وهمي
llm_factory: Callable = get_llm


class AnalyzeRequest(BaseModel):
    title: str = ""
    source: Source
    versions: list[Version] = Field(min_length=1, max_length=4)
    locks: list[Lock] = Field(default_factory=list)

    @model_validator(mode="after")
    def _chain(self) -> "AnalyzeRequest":
        validate_chain(self.versions)
        return self


def create_report(req: AnalyzeRequest) -> Report:
    report = Report(title=req.title, source=req.source, versions=req.versions, locks=req.locks,
                    status=ReportStatus.analyzing, stage="queued",
                    source_sentence_count=len(split_sentences(req.source.text)))
    save_report(report)
    return report


def run_analysis(report_id: str) -> Report:
    report = load_report(report_id)
    if report is None:
        raise KeyError(report_id)

    def progress(stage: str) -> None:
        report.stage = stage
        save_report(report)

    try:
        llm = llm_factory()
        report.alerts = analyze_chain(
            report,
            align_fn=lambda p, c, pl, cl: align(llm, p, c, pl, cl),
            fp_fn=lambda text, lang: fingerprint(llm, text, lang),
            presence_fn=lambda item, kind, ptext, vtext, vlang: find_in_version(llm, item, kind, ptext, vtext, vlang),
            progress=progress,
        )
        progress("mizan")
        report.verifications, mizan_alerts = mizan.check_report(report)
        report.alerts += mizan_alerts
        report.status, report.stage, report.error = ReportStatus.analyzed, "done", ""
    except Exception as e:  # يظهر الخطأ للمستخدم في شاشة التحليل بدل تقرير ناقص
        report.status, report.error = ReportStatus.failed, f"{type(e).__name__}: {e}"[:500]
    save_report(report)
    return report
