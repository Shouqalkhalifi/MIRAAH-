import json

from app.models import AlertType as T
from app.models import ExamQuestion, ReaderExam, Report, Source, Version
from app.pipeline.reader_exam import NOT_STATED, SYSTEM_QUESTIONS, answer, divergence_alerts, make_questions, run_exam

SRC = "يجوز للمسافر أن يفطر في رمضان."
Q = {"questions": [
    {"question_ar": "لمن تجوز الرخصة؟", "options": ["للمسافر", "لكل المسلمين", NOT_STATED]},
    {"question_ar": "ما نوع الحكم؟", "options": ["جائز", "واجب"]},
    {"question_ar": "سؤال بخيار واحد", "options": ["فقط"]},
]}


class RouterLLM:
    """يولّد الأسئلة، ويجيب حسب النص: من يرى «Muslims» يختار «لكل المسلمين»."""

    def __init__(self):
        self.prompts = []

    def complete_json(self, prompt, schema, system="", **kw):
        self.prompts.append((system, prompt))
        if system == SYSTEM_QUESTIONS:
            return schema.model_validate_json(json.dumps(Q, ensure_ascii=False))
        everyone = "muslims" in prompt.lower() or "musulmans" in prompt.lower()
        return schema.model_validate({"answers": [1 if everyone else 0, 0]})


def test_questions_get_not_stated_option_and_invalid_dropped():
    qs = make_questions(RouterLLM(), SRC)
    assert [q.id for q in qs] == ["q1", "q2"]
    assert qs[0].options == ["للمسافر", "لكل المسلمين", NOT_STATED]  # لا تكرار لخيار «لا يذكر»
    assert qs[1].options[-1] == NOT_STATED


def test_each_reader_sees_only_its_text():
    llm = RouterLLM()
    qs = make_questions(llm, SRC)
    answer(llm, "Muslims may break the fast.", "en", qs)
    last = llm.prompts[-1][1]
    assert "Muslims may break the fast." in last and SRC not in last


def test_out_of_range_answers_ignored():
    class Bad:
        def complete_json(self, prompt, schema, **kw):
            return schema.model_validate({"answers": [9]})

    qs = [ExamQuestion(id="q1", question_ar="سؤال؟", options=["أ", "ب", NOT_STATED])]
    assert answer(Bad(), "x", "en", qs + qs) == [None, None]


def test_divergence_detected_with_introduced_at_and_propagation():
    report = Report(source=Source(text=SRC), versions=[
        Version(label="en", lang="en", text="A traveler may break the fast in Ramadan."),
        Version(label="sum", lang="en", derived_from="en", text="Muslims may break the fast in Ramadan."),
        Version(label="fr", lang="fr", derived_from="sum", text="Les musulmans peuvent rompre le jeûne."),
    ])
    exam, alerts = run_exam(RouterLLM(), report)
    assert exam.answers["source"] == [0, 0] and exam.answers["en"] == [0, 0]
    assert len(alerts) == 1
    a = alerts[0]
    assert a.type == T.reader_divergence and a.introduced_at == "sum" and a.propagated_to == ["fr"]
    assert "القارئ العربي يفهم أن: «للمسافر»" in a.explanation_ar and "«لكل المسلمين»" in a.explanation_ar
    assert a.evidence[0].kind == "reader_exam"


def test_no_alert_when_answers_match():
    report = Report(source=Source(text=SRC), versions=[Version(label="en", lang="en", text="x")])
    exam = ReaderExam(questions=[ExamQuestion(id="q1", question_ar="سؤال؟", options=["أ", "ب"])],
                      answers={"source": [0], "en": [0]})
    assert divergence_alerts(report, exam) == []
