"""6.7 امتحان القارئ.

1. من الأصل: 3–5 أسئلة مغلقة عن المعنى (هل الحكم مشروط؟ ما الشرط؟ من القائل؟ ما درجة الثبوت؟ هل يشمل الجميع؟).
2. استدعاء يرى الأصل فقط يجيب، واستدعاء منفصل لكل نسخة يرى النسخة فقط يجيب.
3. اختلاف الإجابة ← reader_divergence: «القارئ العربي يفهم أن... بينما قارئ النسخة يفهم أن...».
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models import Alert, AlertType, Evidence, ExamQuestion, ReaderExam, Report, Severity, Span

NOT_STATED = "النص لا يذكر ذلك"

SYSTEM_QUESTIONS = """You write a short closed-question "reader exam" about the MEANING of an Arabic passage of Islamic content. The questions will later be answered by readers who see only a translation or summary, to detect where meaning changed.

Write 3 to 5 questions in Arabic, each answerable from the passage alone, focused on meaning-critical points that exist in this passage, for example: is the ruling conditional and on what; who the statement is attributed to and in what form (asserted or reported with «رُوي/قيل»); how certain it is; whether it applies to everyone or a specific group; what the ruling category is; any number or exception.
Each question has 2 to 4 short, mutually exclusive Arabic options; exactly one is correct according to the passage. Do not add an option meaning "not stated" (it is added automatically). Do not ask about anything the passage does not address. Never add knowledge from outside the passage."""

SYSTEM_ANSWER = """You are a careful reader. Answer each multiple-choice question using ONLY the text you are given, as an ordinary reader would understand it. Do not use outside knowledge about Islam or about the original source. If the text does not say, choose the option «النص لا يذكر ذلك».
Return the 0-based index of the chosen option for every question, in order."""


class _RawQuestion(BaseModel):
    question_ar: str
    options: list[str] = Field(default_factory=list)


class _QuestionsLLM(BaseModel):
    questions: list[_RawQuestion] = Field(default_factory=list)


class _AnswersLLM(BaseModel):
    answers: list[int]


def _render(questions: list[ExamQuestion]) -> str:
    lines = []
    for i, q in enumerate(questions):
        lines.append(f"Q{i + 1}. {q.question_ar}")
        lines += [f"  [{j}] {o}" for j, o in enumerate(q.options)]
    return "\n".join(lines)


def make_questions(llm, source_text: str) -> list[ExamQuestion]:
    res = llm.complete_json(f"Passage (ar):\n<<<\n{source_text}\n>>>", _QuestionsLLM, system=SYSTEM_QUESTIONS,
                            purpose="reader_exam_questions")
    out = []
    for i, q in enumerate(res.questions[:5]):
        opts = [o.strip() for o in q.options if o.strip() and o.strip() != NOT_STATED][:4]
        if len(opts) >= 2 and len(q.question_ar.strip()) >= 3:
            out.append(ExamQuestion(id=f"q{i + 1}", question_ar=q.question_ar.strip(), options=opts + [NOT_STATED]))
    return out


def answer(llm, text: str, lang: str, questions: list[ExamQuestion]) -> list[Optional[int]]:
    prompt = f"TEXT ({lang}):\n<<<\n{text}\n>>>\n\nQUESTIONS:\n{_render(questions)}"
    res = llm.complete_json(prompt, _AnswersLLM, system=SYSTEM_ANSWER, purpose="reader_exam_answer")
    out: list[Optional[int]] = []
    for i, q in enumerate(questions):
        a = res.answers[i] if i < len(res.answers) else None
        out.append(a if a is not None and 0 <= a < len(q.options) else None)
    return out


def run_exam(llm, report: Report) -> tuple[ReaderExam, list[Alert]]:
    questions = make_questions(llm, report.source.text)
    exam = ReaderExam(questions=questions)
    if not questions:
        return exam, []
    exam.answers["source"] = answer(llm, report.source.text, report.source.lang, questions)
    for v in report.versions:
        exam.answers[v.label] = answer(llm, v.text, v.lang, questions)
    return exam, divergence_alerts(report, exam)


def divergence_alerts(report: Report, exam: ReaderExam) -> list[Alert]:
    parent_of = {v.label: v.derived_from for v in report.versions}

    def ancestors(label: str) -> list[str]:
        out = []
        while parent_of.get(label, "source") != "source":
            label = parent_of[label]
            out.append(label)
        return out

    src = exam.answers.get("source", [])
    records: dict[tuple[str, str], Alert] = {}  # (label, question id) ← التنبيه
    alerts = []
    for v in report.versions:
        ans = exam.answers.get(v.label, [])
        for i, q in enumerate(exam.questions):
            s_ans = src[i] if i < len(src) else None
            v_ans = ans[i] if i < len(ans) else None
            if s_ans is None or v_ans is None or s_ans == v_ans:
                continue
            prev = next((records[(a, q.id)] for a in ancestors(v.label) if (a, q.id) in records), None)
            if prev:
                prev.propagated_to.append(v.label)
                continue
            s_txt, v_txt = q.options[s_ans], q.options[v_ans]
            alert = Alert(
                type=AlertType.reader_divergence, severity=Severity.yellow,
                content_level=report.source.content_level, version_label=v.label, introduced_at=v.label,
                explanation_ar=f"{q.question_ar} — القارئ العربي يفهم أن: «{s_txt}»، بينما قارئ {v.label} يفهم أن: «{v_txt}».",
                why_it_matters_ar="سأل امتحان القارئ عن معنى الأصل؛ فأجاب من قرأ الأصل وحده جواباً، ومن قرأ النسخة وحدها جواباً آخر. هذا يعني أن النسخة توصل فهماً مختلفاً.",
                evidence=[Evidence(kind="reader_exam", ref=q.id, detail=f"{q.question_ar} | الأصل: {s_txt} | {v.label}: {v_txt}")],
                confidence=0.7, source_span=Span(), version_span=Span(),
                source_context=report.source.text, version_context=v.text,
            )
            records[(v.label, q.id)] = alert
            alerts.append(alert)
    return alerts
