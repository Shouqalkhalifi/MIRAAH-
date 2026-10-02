"""«قابِل ما قرأت» على المسألتين التجريبيتين الوهميتين فقط (I01 غير خلافية، I02 خلافية)."""
import json
import re

from app.library import load_library
from app.pipeline import reverse as rv
from app.pipeline.fingerprint import SYSTEM_FP

ISSUES = load_library()


class FakeLLM:
    """يحاكي النموذج: يصنّف، ويطابق المسألة، ويستخرج البصمة بكلمات بسيطة، ويشرح."""

    def __init__(self, explanation="المصدر يذكر «نص تجريبي (أ)» بشرط.", diff=None, confidence=0.9):
        self.explanation, self.diff, self.confidence = explanation, diff, confidence
        self.calls = []

    def complete_json(self, prompt, schema, system="", **kw):
        self.calls.append(kw.get("purpose"))
        text = prompt.split("<<<\n", 1)[-1].rsplit("\n>>>", 1)[0].lower()
        if system == rv.SYSTEM_CLASSIFY:
            kind = "question" if text.strip().endswith("?") else ("out_of_scope" if "weather" in text else "claim")
            reply = {"kind": kind}
        elif system == rv.SYSTEM_MATCH:
            ids = re.findall(r"^- (I\d+):", prompt, re.M)
            reply = {"issue_id": ids[0] if ids else None, "confidence": self.confidence}
        elif system == SYSTEM_FP:
            ruling = next((r for w, r in [("obligatory", "obligatory"), ("forbidden", "forbidden"),
                                          ("recommended", "recommended"), ("permissible", "permissible")] if w in text), "none")
            fp = {"ruling": ruling,
                  "conditions": ["if the tester is ready"] if "ready" in text else [],
                  "exceptions": ["during maintenance"] if "maintenance" in text else [],
                  "consensus_claim": "ijma" if ("all scholars agree" in text or "consensus" in text) else "none",
                  "scope": {"quantifier": "all" if "everyone" in text else "unspecified"}}
            reply = {"fingerprint": fp}
        elif system == rv.SYSTEM_EXPLAIN:
            reply = {"explanation_ar": self.explanation, "diff_quote": self.diff}
        else:
            raise AssertionError(f"unexpected system prompt: {system[:40]}")
        return schema.model_validate_json(json.dumps(reply, ensure_ascii=False))


def run(text, **kw):
    return rv.run_reverse(FakeLLM(**kw), text, ISSUES)


# ---------- الأحكام الخمسة ----------
def test_matches_source():
    r = run("Zorblat is obligatory if the tester is ready, except during maintenance.")
    assert r.verdict == "matches" and r.headline_ar == "مطابق للمصدر" and r.issue.id == "I01"


def test_partially_matches_with_missing_parts():
    r = run("Zorblat is obligatory for everyone.")
    assert r.verdict == "partial"
    assert r.headline_ar == "مطابق جزئياً: ينقص شرط واستثناء، اتسع النطاق"
    assert [f.mark for f in r.findings] == ["لحق", "لحق", "تغيّر"]


def test_contradicts_source():
    r = run("Zorblat is forbidden.")
    assert r.verdict == "contradicts" and r.headline_ar == "متعارض مع المصدر: المصدر يذكر الحكم واجباً"
    assert r.tone == "rubric"


def test_khilafi_issue():
    r = run("Quaffle is recommended.")
    assert r.verdict == "khilafi" and r.issue.id == "I02"
    assert r.referral_ar == rv.KHILAF_REFERRAL_AR


def test_no_reference_outside_library():
    r = run("The moon-cheese rule is obligatory.")
    assert r.verdict == "no_reference" and r.headline_ar == rv.NO_REFERENCE_AR and r.issue is None


def test_low_confidence_match_is_no_reference():
    r = run("Zorblat is obligatory.", confidence=0.3)
    assert r.verdict == "no_reference"


# ---------- القواعد الإلزامية ----------
def test_adopting_an_opinion_in_khilaf_is_never_contradicts():
    for claim in ["Quaffle is permissible.", "Quaffle is forbidden.", "Quaffle is obligatory."]:
        assert run(claim).verdict == "khilafi", claim


def test_consensus_claim_on_khilaf_issue_flagged_as_addition():
    r = run("All scholars agree that quaffle is obligatory.")
    assert r.verdict == "khilafi"
    assert r.findings[0].mark == "زيادة" and rv.OVERCLAIM_AR in r.findings[0].text_ar


def test_question_shows_sources_only_without_model_ruling():
    llm = FakeLLM()
    r = rv.run_reverse(llm, "Is zorblat obligatory?", ISSUES)
    assert r.verdict == "sources_only" and r.issue.id == "I01"
    assert r.explanation_ar is None and r.fingerprint is None and r.findings == []
    assert "reverse_explain" not in llm.calls and "fingerprint" not in llm.calls


def test_personal_fatwa_request_gets_fixed_referral_without_analysis():
    llm = FakeLLM()
    r = rv.run_reverse(llm, "I live in X, can I skip zorblat at work?", ISSUES)
    assert r.verdict == "referral" and r.headline_ar == rv.PERSONAL_AR and r.issue is None
    assert llm.calls == []  # لا استدعاء نموذج أصلاً


def test_out_of_scope():
    r = run("What will the weather be tomorrow")
    assert r.verdict == "out_of_scope" and r.headline_ar == rv.OUT_OF_SCOPE_AR


def test_hostile_input_handled_calmly_with_same_logic():
    r = run("You idiots, zorblat is FORBIDDEN and your useless app is garbage!!")
    assert r.verdict == "contradicts"
    out = (r.headline_ar + " ".join(f.text_ar for f in r.findings) + (r.explanation_ar or "")).lower()
    assert "idiot" not in out and "garbage" not in out


# ---------- الشرح ----------
def test_explanation_with_quote_from_library_is_kept():
    r = run("Zorblat is forbidden.", explanation="المصدر يذكر «نص تجريبي (أ)» ولا يذكر التحريم.", diff="forbidden")
    assert r.explanation_ar and not r.explanation_removed
    assert r.diff_quote == "forbidden"


def test_explanation_quoting_outside_the_library_is_removed():
    r = run("Zorblat is forbidden.", explanation="قال العلماء «هذا قول مختلق ليس في المكتبة».")
    assert r.explanation_ar is None and r.explanation_removed is True
    assert r.verdict == "contradicts"  # يُعرض الحكم وحده


def test_diff_quote_must_be_verbatim_in_reader_text():
    r = run("Zorblat is forbidden.", diff="something the reader never wrote")
    assert r.diff_quote is None


def test_detect_lang():
    assert rv.detect_lang("الزوربلات واجبة") == "ar" and rv.detect_lang("zorblat is obligatory") == "en"
