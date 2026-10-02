"""تشغيل التحليل: من الطلب إلى تقرير محفوظ."""
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field, model_validator

from app.llm import get_llm
from app.models import Lock, Report, ReportStatus, Source, Version, WitnessStats, validate_chain
from app.pipeline.align import align
from app.pipeline import fahm, mizan, reader_exam, severity
from app.pipeline.chain import STAGES as CHAIN_STAGES
from app.pipeline.chain import analyze_chain
from app.pipeline.fingerprint import find_in_version, fingerprint
from app.pipeline.segment import split_sentences
from app.store import load_report, save_report

# مراحل التحليل كما تظهر في شريط التقدم
STAGES: list[tuple[str, str]] = CHAIN_STAGES + [
    ("mizan", "الميزان: البحث عن النصوص المنسوبة في المدونة"),
    ("fahm", "الفهم: مخاطر الفهم المحتملة"),
    ("reader_exam", "امتحان القارئ: هل يفهم قارئ النسخة ما يفهمه قارئ الأصل؟"),
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
        from app.pipeline.locks import lock_in_text

        missing = [lk.span_text for lk in self.locks if not lock_in_text(lk.span_text, self.source.text)]
        if missing:
            raise ValueError(f"مقطع القفل غير موجود في الأصل: {missing[0]}")
        return self


def create_report(req: AnalyzeRequest) -> Report:
    report = Report(title=req.title, source=req.source, versions=req.versions, locks=req.locks,
                    status=ReportStatus.analyzing, stage="queued",
                    source_sentence_count=len(split_sentences(req.source.text)))
    save_report(report)
    return report


# أخطاء المزوّد المعروفة ← رسالة عربية مفهومة للمراجع (مع الإبقاء على التفاصيل التقنية بعدها)
_PROVIDER_ERRORS = [
    ("credit balance is too low", "نفد رصيد خدمة النموذج اللغوي (Anthropic). أعد شحن الرصيد ثم أعد التحليل؛ "
                                  "التقارير التي سبق تحليلها ما زالت متاحة."),
    ("authentication", "مفتاح ANTHROPIC_API_KEY غير صحيح أو منتهٍ. راجع ملف .env أو إعدادات الأسرار في المنصة."),
    ("invalid x-api-key", "مفتاح ANTHROPIC_API_KEY غير صحيح أو منتهٍ. راجع ملف .env أو إعدادات الأسرار في المنصة."),
    ("rate_limit", "خدمة النموذج اللغوي تتلقى طلبات كثيرة الآن. أعد المحاولة بعد دقيقة."),
    ("overloaded", "خدمة النموذج اللغوي مشغولة الآن. أعد المحاولة بعد قليل."),
    ("connection", "تعذّر الاتصال بخدمة النموذج اللغوي. تحقق من الاتصال بالإنترنت ثم أعد المحاولة."),
    ("timed out", "انتهت مهلة الاتصال بخدمة النموذج اللغوي. أعد المحاولة."),
    ("ANTHROPIC_API_KEY غير موجود", "لم يُضبط مفتاح ANTHROPIC_API_KEY. أضفه إلى ملف .env أو إعدادات الأسرار في المنصة."),
]


def friendly_error(e: Exception) -> str:
    technical = f"{type(e).__name__}: {e}"
    low = technical.lower()
    message = next((msg for key, msg in _PROVIDER_ERRORS if key.lower() in low), "حدث خطأ غير متوقع أثناء التحليل.")
    return f"{message}\n— التفاصيل التقنية: {technical}"[:700]


def _optional(report: Report, name: str, fn, default):
    """المراحل المساعدة (الفهم، امتحان القارئ) لا تُفشل التقرير: يُسجَّل التعذّر ظاهراً في التقرير."""
    try:
        return fn()
    except Exception as e:
        report.warnings.append(f"تعذّر {name}: {type(e).__name__}")
        return default


def run_analysis(report_id: str) -> Report:
    report = load_report(report_id)
    if report is None:
        raise KeyError(report_id)

    def progress(stage: str) -> None:
        report.stage = stage
        save_report(report)

    try:
        llm = llm_factory()
        model_a, model_b = llm.models.get("witness_a") or llm.models.get("main"), llm.models.get("witness_b")
        two = bool(model_b) and model_b != model_a
        stats: dict = {}
        report.alerts = analyze_chain(
            report,
            align_fn=lambda p, c, pl, cl: align(llm, p, c, pl, cl),
            fp_fn=lambda text, lang: fingerprint(llm, text, lang, role="witness_a"),
            witness_fp_fn=(lambda text, lang: fingerprint(llm, text, lang, role="witness_b")) if two else None,
            stats=stats,
            presence_fn=lambda item, kind, ptext, vtext, vlang: find_in_version(llm, item, kind, ptext, vtext, vlang),
            extra_rules=fahm.term_hits,
            lock_fn=lock_checker(llm),
            progress=progress,
        )
        report.witnesses = WitnessStats(enabled=two, model_a=model_a or "", model_b=model_b if two else "",
                                        agreement=stats.get("agreement"), compared=stats.get("compared", 0))
        progress("mizan")
        report.verifications, mizan_alerts = mizan.check_report(report)
        report.alerts += mizan_alerts
        progress("fahm")
        report.understanding_risks = _optional(report, "مخاطر الفهم", lambda: fahm.understanding_risks(llm, report.source.text), [])
        progress("reader_exam")
        exam = _optional(report, "امتحان القارئ", lambda: reader_exam.run_exam(llm, report), None)
        if exam:
            report.reader_exam, exam_alerts = exam
            report.alerts += exam_alerts
        report.alerts = severity.apply_severity(report.alerts, report.source.content_level)
        report.referral = severity.needs_referral(report.source.content_level)
        report.status, report.stage, report.error = ReportStatus.analyzed, "done", ""
    except Exception as e:  # يظهر الخطأ للمستخدم في شاشة التحليل بدل تقرير ناقص
        report.status, report.error = ReportStatus.failed, friendly_error(e)
    save_report(report)
    return report


def reexam_corrected(report_id: str) -> Report:
    """يعيد امتحان القارئ على كل حلقة طُبّق فيها تصحيح، بالأسئلة نفسها، ليُرى هل عاد الفهم إلى فهم الأصل."""
    from app.export import approved_text

    report = load_report(report_id)
    if report is None:
        raise KeyError(report_id)
    exam = report.reader_exam
    if not exam or not exam.questions:
        return report
    llm = None
    for v in report.versions:
        text, applied = approved_text(report, v.label, v.text)
        if not applied:
            exam.corrected.pop(v.label, None)
            exam.corrected_text.pop(v.label, None)
            continue
        if exam.corrected_text.get(v.label) == text:
            continue
        llm = llm or llm_factory()
        exam.corrected[v.label] = reader_exam.answer(llm, text, v.lang, exam.questions)
        exam.corrected_text[v.label] = text
    save_report(report)
    return report


def revise_alert(report_id: str, alert_id: str) -> list:
    """ثلاث صياغات آمنة لتنبيه، بعد التحقق الذاتي. تُحفظ في التقرير ولا تُولَّد مرتين."""
    from app.pipeline.revise import revise

    report = load_report(report_id)
    if report is None:
        raise KeyError(report_id)
    alert = next((a for a in report.alerts if a.id == alert_id), None)
    if alert is None:
        raise KeyError(alert_id)
    if alert_id in report.revisions:
        return report.revisions[alert_id]
    llm = llm_factory()
    revisions = revise(
        llm, report, alert,
        fp_fn=lambda text, lang: fingerprint(llm, text, lang),
        presence_fn=lambda item, kind, ptext, vtext, vlang: find_in_version(llm, item, kind, ptext, vtext, vlang),
        lock_fn=lock_checker(llm),
    )
    report.revisions[alert_id] = revisions
    save_report(report)
    return revisions


def suggest_locks(text: str, lang: str = "ar") -> list:
    from app.pipeline.locks import suggest_locks as _suggest

    llm = llm_factory()
    return _suggest(text, lambda sentence: fingerprint(llm, sentence, lang))


def lock_checker(llm):
    from app.pipeline.locks import check_lock

    def fn(lock, src_ctx, version_text, version_lang):
        return check_lock(lock, src_ctx, version_text, version_lang,
                          lambda item, kind, p, v, lang: find_in_version(llm, item, kind, p, v, lang))
    return fn


# ---------- «قابِل ما قرأت» ----------
def reverse_trace(text: str, save: bool = False):
    """يقابل ما كتبه المستخدم بمصادر المكتبة. لا يُحفظ نصه (ولا يدخل cache النموذج) إلا إذا اختار الحفظ."""
    import uuid

    from sqlmodel import Session

    from app.db import get_engine
    from app.models import ReverseRow
    from app.pipeline.reverse import run_reverse

    llm = llm_factory()
    llm.cache_enabled = False  # الخصوصية: نص المستخدم لا يُخزَّن في cache الاستجابات
    result = run_reverse(llm, text, presence_fn=lambda item, kind, p, v, lang: find_in_version(llm, item, kind, p, v, lang))
    if save:
        result.id = uuid.uuid4().hex[:12]
        with Session(get_engine()) as s:
            s.add(ReverseRow(id=result.id, data=result.model_dump_json()))
            s.commit()
    return result


def load_reverse(rid: str):
    from sqlmodel import Session

    from app.db import get_engine
    from app.models import ReverseRow
    from app.pipeline.reverse import ReverseResult

    with Session(get_engine()) as s:
        row = s.get(ReverseRow, rid)
    return ReverseResult.model_validate_json(row.data) if row else None
