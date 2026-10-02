"""نماذج البيانات (CLAUDE.md القسمان 5 و6).

Pydantic للتحقق، وجدول SQLModel واحد يخزّن التقرير كاملاً بصيغة JSON.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- التعدادات ----------
class ContentLevel(str, Enum):
    A = "A"  # أعلى حساسية: نصوص منسوبة إلى الله ورسوله ﷺ
    B = "B"
    C = "C"
    D = "D"  # خارج النطاق ← إحالة


class LockType(str, Enum):
    condition = "condition"
    certainty = "certainty"
    exception = "exception"
    attribution = "attribution"
    grade = "grade"
    term = "term"
    negation = "negation"
    number = "number"


class Severity(str, Enum):
    red = "red"
    yellow = "yellow"
    info = "info"


class AlertType(str, Enum):
    condition_dropped = "condition_dropped"
    exception_dropped = "exception_dropped"
    certainty_raised = "certainty_raised"
    attribution_upgraded = "attribution_upgraded"
    new_prophetic_attribution = "new_prophetic_attribution"
    ruling_shift = "ruling_shift"
    scope_widened = "scope_widened"
    scope_narrowed = "scope_narrowed"
    hasr_lost = "hasr_lost"
    consensus_inflated = "consensus_inflated"
    disagreement_collapsed = "disagreement_collapsed"
    attribution_generalized = "attribution_generalized"
    hadith_grade_dropped = "hadith_grade_dropped"
    negation_mismatch = "negation_mismatch"
    number_mismatch = "number_mismatch"
    term_narrowing = "term_narrowing"
    length_drop = "length_drop"
    sentence_dropped = "sentence_dropped"
    lock_violated = "lock_violated"
    # الميزان (6.5)
    unverified_attribution = "unverified_attribution"  # لم يُعثر عليه في المدونة
    source_conflict = "source_conflict"  # وُجد لكن درجته ضعيفة/مخالفة، أو الآية المرقّمة لا تطابق
    quote_wording_differs = "quote_wording_differs"  # تطابق جزئي مع النص المعتمد
    # من المراحل اللاحقة
    reader_divergence = "reader_divergence"
    witness_disagreement = "witness_disagreement"


class ReportStatus(str, Enum):
    draft = "draft"
    analyzing = "analyzing"
    failed = "failed"
    analyzed = "analyzed"
    in_review = "in_review"
    approved = "approved"  # اعتمده المراجع وصُدِّر تقريره الداخلي


# ---------- المدخلات ----------
class Source(BaseModel):
    text: str = Field(min_length=1)
    lang: str = "ar"
    source_ref: str = ""
    content_level: ContentLevel = ContentLevel.B


class Version(BaseModel):
    label: str = Field(min_length=1)
    lang: str
    text: str = Field(min_length=1)
    derived_from: str = "source"  # "source" أو label نسخة سابقة


class Lock(BaseModel):
    span_text: str = Field(min_length=1)
    lock_type: LockType
    origin: Literal["user", "auto"] = "user"


# ---------- بصمة المعنى (6.2) ----------
class Attribution(BaseModel):
    to: Literal["allah", "prophet", "companion", "scholar", "religion", "author", "none"] = "none"
    form: Literal["assertive", "tamrid", "none"] = "none"


class Scope(BaseModel):
    quantifier: Literal["all", "some", "specific", "unspecified"] = "unspecified"
    restricted_to: Optional[str] = None


class HadithMention(BaseModel):
    snippet: str
    grade_stated: Literal["sahih", "hasan", "daif", "none"] = "none"


class MeaningFingerprint(BaseModel):
    attribution: Attribution = Field(default_factory=Attribution)
    claim: str = ""
    ruling: Literal["obligatory", "recommended", "permissible", "disliked", "forbidden", "none"] = "none"
    scope: Scope = Field(default_factory=Scope)
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    certainty: Literal["definite", "probable", "possible", "unstated"] = "unstated"
    restriction_hasr: bool = False
    negations: int = 0
    numbers: list[str] = Field(default_factory=list)
    quran_refs: list[str] = Field(default_factory=list)
    hadith_mentions: list[HadithMention] = Field(default_factory=list)
    consensus_claim: Literal["none", "some_scholars", "majority", "ijma"] = "none"
    disagreement_stated: bool = False  # «اختلف العلماء»، «في المسألة خلاف»
    key_terms: list[str] = Field(default_factory=list)


# ---------- التنبيه (6.3) ----------
class Span(BaseModel):
    text: str = ""
    start: Optional[int] = None  # موضع الحرف في النص (للتتبع والتظليل)
    end: Optional[int] = None
    sentence_index: Optional[int] = None


class Evidence(BaseModel):
    kind: Literal["text_span", "corpus", "fingerprint", "lock", "reader_exam"]
    ref: str = ""  # id عنصر المدونة أو اسم الحقل
    detail: str = ""


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: AlertType
    severity: Severity
    content_level: ContentLevel = ContentLevel.B
    source_span: Span = Field(default_factory=Span)
    version_span: Span = Field(default_factory=Span)
    version_label: str
    introduced_at: str = ""  # label أول حلقة انكسر فيها الثابت
    explanation_ar: str
    why_it_matters_ar: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    witnesses_agree: Optional[bool] = None
    # امتدادات: كل جمل الأصل المعنية، والحلقات اللاحقة التي ورثت الخلل
    source_sentence_indices: list[int] = Field(default_factory=list)
    propagated_to: list[str] = Field(default_factory=list)
    tier: int = 4  # طبقة الخطورة (6.11): 0 نسبة إلى الله ورسوله ﷺ ... 4 أسلوب
    # سياق الوحدة كاملاً (جمل الأصل وجمل النسخة) لاقتراح الصياغة الآمنة
    source_context: str = ""
    version_context: str = ""

    @model_validator(mode="after")
    def _traceable(self) -> "Alert":
        # القاعدة 6: كل تنبيه قابل للتتبع إلى موضع في النص أو عنصر في المدونة
        if not (self.source_span.text or self.version_span.text or self.evidence):
            raise ValueError("التنبيه يجب أن يرتبط بموضع في النص أو بدليل")
        return self


# ---------- الفهم (6.6) ----------
class UnderstandingRisk(BaseModel):
    risk_ar: str  # صياغة احتمالية: «قد يُفهم...»
    quote: str  # مقطع حرفي من الأصل
    reason_ar: str = ""


# ---------- الميزان (6.5) ----------
SupportStatus = Literal["supported", "partially_supported", "unsupported", "conflicting", "unverified"]


class Verification(BaseModel):
    label: str  # "source" أو label النسخة
    sentence_index: int
    attributed_to: Literal["prophet", "allah"]
    cue: str
    quote: str  # النص المنسوب كما ورد
    status: SupportStatus
    score: float = 0.0
    item_id: Optional[str] = None
    item_text: str = ""
    item_grade: Optional[str] = None
    source_name: str = ""
    source_url: str = ""
    note_ar: str = ""


# ---------- الشاهدان (6.8) ----------
class WitnessStats(BaseModel):
    enabled: bool = False  # False = شاهد واحد فقط
    model_a: str = ""
    model_b: str = ""
    agreement: Optional[float] = None  # نسبة اتفاق الحقول المؤثرة
    compared: int = 0  # عدد نصوص الوحدات المقارنة


# ---------- امتحان القارئ (6.7) ----------
class ExamQuestion(BaseModel):
    id: str = ""
    question_ar: str = Field(min_length=3)
    options: list[str] = Field(min_length=2, max_length=6)


class ReaderExam(BaseModel):
    questions: list[ExamQuestion] = Field(default_factory=list)
    answers: dict[str, list[Optional[int]]] = Field(default_factory=dict)  # label ← رقم الخيار لكل سؤال
    # إعادة الامتحان على نص الحلقة بعد التصحيحات المعتمدة؛ النص محفوظ ليُعرف إن تغيّرت التصحيحات بعدها
    corrected: dict[str, list[Optional[int]]] = Field(default_factory=dict)
    corrected_text: dict[str, str] = Field(default_factory=dict)


# ---------- الصياغة الآمنة (6.10) ----------
class Revision(BaseModel):
    style: Literal["precise", "balanced", "clear"]
    label_ar: str
    text: str
    passed: bool  # اجتازت التحقق الذاتي (البصمة + القواعد + الميزان + الأقفال)
    problems: list[str] = Field(default_factory=list)


# ---------- قرار المراجع (6.12) ----------
class Decision(BaseModel):
    """قرار بلا صفة ولا اسم. «edit» = طبّق التصحيح، «reject» = ليس خطأ (بسبب إلزامي).
    «accept» = أحِله للمختص (بسبب)، ويظهر فقط حين يكون الخلل في الأصل نفسه، لأن الأصل لا يُعدَّل."""
    alert_id: str
    action: Literal["edit", "reject", "accept"]
    reason: str = Field(default="", max_length=1000)
    edited_text: Optional[str] = Field(default=None, max_length=5000)
    decided_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _check(self) -> "Decision":
        self.reason = self.reason.strip()
        if self.action == "edit":
            if not (self.edited_text and self.edited_text.strip()):
                raise ValueError("التصحيح يحتاج الصياغة المعتمدة")
        elif len(self.reason) < 3:
            raise ValueError("اكتب سبباً قصيراً")
        if self.reason and self.edited_text and " ".join(self.reason.split()) == " ".join(self.edited_text.split()):
            raise ValueError("اكتب سبب القرار، لا الصياغة نفسها")
        return self


class AuditEntry(SQLModel, table=True):
    """سجل تدقيق إضافي فقط: كل قرار ونشر يُسجَّل ولا يُحذف."""
    __tablename__ = "audit_log"
    id: Optional[int] = SQLField(default=None, primary_key=True)
    report_id: str = SQLField(index=True)
    ts: datetime = SQLField(default_factory=_now)
    event: str  # decision | approve
    alert_id: str = ""
    payload: str = "{}"


# ---------- التقرير ----------
def validate_chain(versions: list["Version"]) -> None:
    """كل حلقة تُشتق من الأصل أو من حلقة قبلها، والتسميات فريدة."""
    seen = {"source"}
    for v in versions:
        if v.label in seen:
            raise ValueError(f"تسمية مكررة أو محجوزة: {v.label}")
        if v.derived_from not in seen:
            raise ValueError(f"الحلقة الأم '{v.derived_from}' غير معرّفة قبل '{v.label}'")
        seen.add(v.label)


class Report(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = Field(default_factory=_now)
    title: str = ""
    source: Source
    versions: list[Version] = Field(default_factory=list, max_length=4)
    locks: list[Lock] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    status: ReportStatus = ReportStatus.draft
    stage: str = ""  # مرحلة التحليل الحالية (لشريط التقدم)
    error: str = ""
    source_sentence_count: int = 0
    verifications: list[Verification] = Field(default_factory=list)
    understanding_risks: list[UnderstandingRisk] = Field(default_factory=list)
    referral: bool = False  # مستوى D: خارج النطاق ← إحالة
    decisions: dict[str, Decision] = Field(default_factory=dict)  # alert_id ← آخر قرار
    revisions: dict[str, list[Revision]] = Field(default_factory=dict)  # alert_id ← الصياغات المقترحة
    reader_exam: Optional[ReaderExam] = None
    witnesses: WitnessStats = Field(default_factory=WitnessStats)
    warnings: list[str] = Field(default_factory=list)  # مراحل اختيارية تعذّرت (لا تُفشل التقرير)
    approved_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_published(cls, data):
        """تقارير محفوظة قبل إزالة الختم: «published» صارت «approved»."""
        if isinstance(data, dict) and data.get("status") == "published":
            data = {**data, "status": "approved", "approved_at": data.get("published_at")}
        return data

    @model_validator(mode="after")
    def _chain_valid(self) -> "Report":
        validate_chain(self.versions)
        return self


class ReportRow(SQLModel, table=True):
    __tablename__ = "reports"
    id: str = SQLField(primary_key=True)
    created_at: datetime = SQLField(default_factory=_now)
    status: str = ReportStatus.draft.value
    data: str  # Report.model_dump_json()


class ReverseRow(SQLModel, table=True):
    """نتيجة «قابِل ما قرأت» لا تُحفظ إلا إذا اختار المستخدم حفظها."""
    __tablename__ = "reverse_saved"
    id: str = SQLField(primary_key=True)
    created_at: datetime = SQLField(default_factory=_now)
    data: str  # ReverseResult.model_dump_json()
