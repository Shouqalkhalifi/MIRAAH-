import json

import pytest

from app.models import Alert, AlertType, Report, Severity, Source, Span, Version
from app.pipeline.revise import RevisionError, revise, self_check
from tests.test_chain import fake_fp

SRC = "يجوز للمسافر أن يفطر في رمضان."
REPORT = Report(source=Source(text=SRC), versions=[
    Version(label="sum", lang="en", text="Muslims may break the fast in Ramadan.")])


def alert(**kw):
    base = dict(type=AlertType.condition_dropped, severity=Severity.red, version_label="sum",
                explanation_ar="سقط الشرط «للمسافر»", source_span=Span(text="للمسافر"),
                source_context=SRC, version_context="Muslims may break the fast in Ramadan.")
    return Alert(**{**base, **kw})


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def complete_json(self, prompt, schema, **kw):
        self.prompts.append(prompt)
        return schema.model_validate_json(json.dumps(self.reply))


def test_three_styles_and_unsafe_one_excluded():
    llm = FakeLLM({"precise": "A traveler may break the fast in Ramadan.",
                   "balanced": "Travelers may break their Ramadan fast.",
                   "clear": "Anyone may skip fasting in Ramadan."})
    out = revise(llm, REPORT, alert(), fake_fp)
    assert [r.style for r in out] == ["precise", "balanced", "clear"]
    assert [r.passed for r in out] == [True, True, False]
    assert any("للمسافر" in p for p in out[2].problems)
    assert "Target language: en" in llm.prompts[0] and SRC in llm.prompts[0]


def test_never_revises_the_source():
    with pytest.raises(RevisionError, match="لا تعدّل النص المصدر"):
        revise(FakeLLM({}), REPORT, alert(version_label="source"), fake_fp)


def test_info_alerts_not_revised():
    with pytest.raises(RevisionError):
        revise(FakeLLM({}), REPORT, alert(severity=Severity.info), fake_fp)


def test_candidate_adding_prophetic_attribution_is_rejected():
    problems = self_check('The Prophet ﷺ said: "A traveler may break the fast."', "en", SRC, "ar", fake_fp)
    assert any("النبي" in p for p in problems)


def test_candidate_breaking_term_rule_is_rejected():
    problems = self_check("Talking during the sermon is forbidden.", "en", "يُكره الكلام أثناء الخطبة.", "ar",
                          lambda t, l: fake_fp("x", l))
    assert any("المصطلح" in p for p in problems)
