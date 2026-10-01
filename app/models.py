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
    hadith_grade_dropped = "hadith_grade_dropped"
    negation_mismatch = "negation_mismatch"
    number_mismatch = "number_mismatch"
    term_narrowing = "term_narrowing"
    length_drop = "length_drop"
    sentence_dropped = "sentence_dropped"
    lock_violated = "lock_violated"
    # من المراحل اللاحقة
    unverified_attribution = "unverified_attribution"
    reader_divergence = "reader_divergence"
    witness_disagreement = "witness_disagreement"


class ReportStatus(str, Enum):
    draft = "draft"
    analyzing = "analyzing"
    failed = "failed"
    analyzed = "analyzed"
    in_review = "in_review"
    published = "published"


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
    to: Literal["allah", "prophet", "companion", "scholar", "author", "none"] = "none"
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

    @model_validator(mode="after")
    def _traceable(self) -> "Alert":
        # القاعدة 6: كل تنبيه قابل للتتبع إلى موضع في النص أو عنصر في المدونة
        if not (self.source_span.text or self.version_span.text or self.evidence):
            raise ValueError("التنبيه يجب أن يرتبط بموضع في النص أو بدليل")
        return self


# ---------- التقرير ----------
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

    @model_validator(mode="after")
    def _chain_valid(self) -> "Report":
        seen = {"source"}
        for v in self.versions:
            if v.label in seen:
                raise ValueError(f"تسمية مكررة أو محجوزة: {v.label}")
            if v.derived_from not in seen:
                raise ValueError(f"الحلقة الأم '{v.derived_from}' غير معرّفة قبل '{v.label}'")
            seen.add(v.label)
        return self


class ReportRow(SQLModel, table=True):
    __tablename__ = "reports"
    id: str = SQLField(primary_key=True)
    created_at: datetime = SQLField(default_factory=_now)
    status: str = ReportStatus.draft.value
    data: str  # Report.model_dump_json()
