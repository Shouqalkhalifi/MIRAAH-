"""بيانات وهمية ثابتة لواجهات المرحلة 0 فقط (اصطناعية بالكامل). تُستبدل بالتحليل الفعلي في المرحلة 1."""
from __future__ import annotations

import hashlib

from app.models import (
    Alert, AlertType, ContentLevel, Evidence, Report, ReportStatus, Severity, Source, Span, Version,
)

SOURCE_TEXT = "يجوز للمسافر أن يفطر في رمضان. ويجب عليه قضاء ما أفطره من أيام."

DEMO_REPORT = Report(
    id="demo",
    title="مثال: رخصة الفطر للمسافر",
    source=Source(text=SOURCE_TEXT, lang="ar", source_ref="مثال اصطناعي", content_level=ContentLevel.B),
    versions=[
        Version(label="en-translation", lang="en", derived_from="source",
                text="A traveler may break the fast in Ramadan. He must make up the days he missed."),
        Version(label="en-summary", lang="en", derived_from="en-translation",
                text="Muslims may break the fast in Ramadan."),
        Version(label="fr-translation", lang="fr", derived_from="en-summary",
                text="Les musulmans peuvent rompre le jeûne pendant le Ramadan."),
    ],
    alerts=[
        Alert(id="a1", type=AlertType.condition_dropped, severity=Severity.red,
              version_label="en-summary", introduced_at="en-summary",
              source_span=Span(text="للمسافر", sentence_index=0),
              version_span=Span(text="Muslims may break the fast", sentence_index=0),
              explanation_ar="سقط شرط «السفر»؛ فصارت الرخصة تبدو عامة لكل المسلمين.",
              why_it_matters_ar="الرخصة في الأصل خاصة بالمسافر. حين يسقط الشرط قد يفهم القارئ أن الفطر في رمضان جائز لأي أحد.",
              evidence=[Evidence(kind="text_span", ref="source:0", detail="«للمسافر» في الجملة الأولى من الأصل")],
              confidence=0.95),
        Alert(id="a2", type=AlertType.scope_widened, severity=Severity.yellow,
              version_label="en-summary", introduced_at="en-summary",
              source_span=Span(text="للمسافر", sentence_index=0),
              version_span=Span(text="Muslims", sentence_index=0),
              explanation_ar="اتسع النطاق من «المسافر» إلى «المسلمين» عموماً.",
              why_it_matters_ar="تحويل حكم خاص بفئة إلى حكم عام يغيّر المعنى حتى لو بدت الجملة قريبة.",
              evidence=[Evidence(kind="fingerprint", ref="scope.restricted_to", detail="traveler ← null")],
              confidence=0.9),
        Alert(id="a3", type=AlertType.sentence_dropped, severity=Severity.yellow,
              version_label="en-summary", introduced_at="en-summary",
              source_span=Span(text="ويجب عليه قضاء ما أفطره من أيام.", sentence_index=1),
              explanation_ar="جملة وجوب القضاء ليس لها مقابل في الملخص.",
              why_it_matters_ar="بدونها قد يُفهم أن الفطر لا يترتب عليه شيء.",
              evidence=[Evidence(kind="text_span", ref="source:1")],
              confidence=1.0),
    ],
    status=ReportStatus.analyzed,
)

REVISIONS = {
    "a1": [
        ("الأدق", "A traveler may break the fast in Ramadan and must make up the missed days."),
        ("المتوازنة", "Travelers may break their Ramadan fast, then make up those days later."),
        ("الأوضح للقارئ", "If you are traveling, you may skip fasting in Ramadan, but you must fast the missed days later."),
    ]
}


def chain_labels(report: Report) -> list[str]:
    return ["source"] + [v.label for v in report.versions]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
