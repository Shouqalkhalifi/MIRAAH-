import pytest
from pydantic import ValidationError

from app.models import Alert, AlertType, MeaningFingerprint, Report, Severity, Source, Span, Version


def src():
    return Source(text="نص", content_level="A")


def test_fingerprint_defaults_and_json_roundtrip():
    fp = MeaningFingerprint.model_validate({
        "attribution": {"to": "prophet", "form": "tamrid"},
        "conditions": ["for travelers"], "certainty": "probable",
        "hadith_mentions": [{"snippet": "...", "grade_stated": "daif"}],
    })
    assert fp.ruling == "none" and fp.negations == 0
    assert MeaningFingerprint.model_validate_json(fp.model_dump_json()) == fp


def test_fingerprint_rejects_unknown_enum():
    with pytest.raises(ValidationError):
        MeaningFingerprint.model_validate({"certainty": "very_sure"})


def test_chain_must_reference_earlier_link():
    Report(source=src(), versions=[
        Version(label="en", lang="en", text="t"),
        Version(label="sum", lang="en", text="t", derived_from="en")])
    with pytest.raises(ValidationError):
        Report(source=src(), versions=[Version(label="sum", lang="en", text="t", derived_from="en")])


def test_max_four_versions():
    vs = [Version(label=f"v{i}", lang="en", text="t") for i in range(5)]
    with pytest.raises(ValidationError):
        Report(source=src(), versions=vs)


def test_duplicate_label_rejected():
    with pytest.raises(ValidationError):
        Report(source=src(), versions=[Version(label="v", lang="en", text="t"),
                                       Version(label="v", lang="en", text="t")])


def test_alert_must_be_traceable():
    with pytest.raises(ValidationError):
        Alert(type=AlertType.condition_dropped, severity=Severity.red, version_label="v", explanation_ar="x")
    a = Alert(type=AlertType.condition_dropped, severity=Severity.red, version_label="v",
              explanation_ar="x", source_span=Span(text="للمسافر"))
    assert len(a.id) == 12
