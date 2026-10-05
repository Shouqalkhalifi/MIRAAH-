"""«قابِل ما قرأت» على المسألتين التجريبيتين الوهميتين فقط (I01 غير خلافية، I02 خلافية)."""
import json
import re

from app.config import ROOT
from app.library import load_library
from app.pipeline import reverse as rv
from app.pipeline.fingerprint import SYSTEM_FP, SYSTEM_PRESENCE

# المسألتان الوهميتان نُقلتا من المكتبة المشحونة إلى ملف اختبار ثابت
PLACEHOLDERS = ROOT / "tests" / "fixtures" / "placeholder_issues.jsonl"
ISSUES = load_library(PLACEHOLDERS)


class FakeLLM:
    """يحاكي النموذج: يصنّف، ويطابق المسألة، ويستخرج البصمة بكلمات بسيطة، ويشرح."""

    def __init__(self, explanation="المصدر يذكر «نص تجريبي (أ)» بشرط.", diff=None, confidence=0.9):
        self.explanation, self.diff, self.confidence = explanation, diff, confidence
        self.calls = []

    def complete_json(self, prompt, schema, system="", **kw):
        self.calls.append(kw.get("purpose"))
        return schema.model_validate_json(json.dumps(self.reply(system, prompt), ensure_ascii=False))

    def reply(self, system, prompt):
        """الرد حسب التعليمات (يُستعمل أيضاً مزوّداً وهمياً خلف طبقة LLM الحقيقية)."""
        text = prompt.split("<<<\n", 1)[-1].rsplit("\n>>>", 1)[0].lower()
        if system.startswith(SYSTEM_PRESENCE[:60]):
            reply = {"present": False, "quote": None}
        elif system.startswith(rv.SYSTEM_CLASSIFY[:60]):
            kind = "question" if text.strip().endswith("?") else ("out_of_scope" if "weather" in text else "claim")
            reply = {"kind": kind}
        elif system.startswith(rv.SYSTEM_MATCH[:60]):
            ids = re.findall(r"^- (I\d+):", prompt, re.M)
            reply = {"issue_id": ids[0] if ids else None, "confidence": self.confidence}
        elif system.startswith(SYSTEM_FP[:60]):
            ruling = next((r for w, r in [("obligatory", "obligatory"), ("forbidden", "forbidden"),
                                          ("recommended", "recommended"), ("permissible", "permissible")] if w in text), "none")
            fp = {"ruling": ruling,
                  "conditions": ["if the tester is ready"] if "ready" in text else [],
                  "exceptions": ["during maintenance"] if "maintenance" in text else [],
                  "consensus_claim": "ijma" if ("all scholars agree" in text or "consensus" in text) else "none",
                  "scope": {"quantifier": "all" if "everyone" in text else "unspecified"}}
            reply = {"fingerprint": fp}
        elif system.startswith(rv.SYSTEM_EXPLAIN[:60]):
            reply = {"explanation_ar": self.explanation, "diff_quote": self.diff}
        else:
            raise AssertionError(f"unexpected system prompt: {system[:40]}")
        return reply


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
    assert [f.mark for f in r.findings] == ["سقط", "سقط", "تغيّر"]


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


def test_keywords_match_any_apostrophe_in_transliteration():
    from app.library import default_library
    for spelling in ["I'tikaf", "I\u2019tikaf", "I\u2018tikaf", "I\u02bftikaf", "Itikaf"]:
        ids = [i.id for i, _ in rv.candidates(f"The statement I read says that {spelling} is obligatory for women.",
                                              default_library())]
        assert "BZ09" in ids, spelling


def test_detect_lang():
    assert rv.detect_lang("الزوربلات واجبة") == "ar" and rv.detect_lang("zorblat is obligatory") == "en"


# ---------- أسئلة الحزمة العلمية: فحوص المدونة تعمل وإن لم تكن المسألة في المكتبة ----------
def test_misquoted_verse_shows_the_text_from_the_corpus():
    # سؤال الحزمة 11: آية منقولة بخطأ (ترتيب اليسر والعسر مقلوب)
    r = run("قال الله تعالى: «يريد الله بكم العسر ولا يريد بكم اليسر»، فما معناها؟")
    assert r.verdict == "no_reference" and r.headline_ar == rv.NOTES_ONLY_AR
    v = r.verifications[0]
    assert v.attributed_to == "allah" and v.status == "partially_supported" and v.item_id == "q-2-185-yusr"
    assert "يُسْرَ وَلَا يُرِيدُ بِكُمُ الْعُسْرَ" in v.item_text


def test_correct_verse_is_supported():
    r = run("قال الله تعالى: «يريد الله بكم اليسر ولا يريد بكم العسر»، فما معناها؟")
    assert r.verifications[0].status == "supported"


def test_package_term_rule_is_shown_with_the_avoided_rendering():
    # سؤال الحزمة 12: مصطلح بلغة غير عربية مختزل في ترجمة يمنعها القاموس
    r = run("Is Sharia just the Islamic criminal law?")
    t = next(t for t in r.terms if t.id == "t-shariah")
    assert t.avoided == "criminal law" and "نماذج لقاموس المصطلحات" in t.source_name
    # سؤال الحزمة 8 يُصنَّف خارج النطاق، والضابط يظهر مع ذلك
    r = run("Translate tawhid into English for the weather column")
    assert r.verdict == "out_of_scope" and [t.id for t in r.terms] == ["t-tawhid"]
    assert r.headline_ar == rv.NOTES_ONLY_AR


def test_passing_mention_of_a_term_shows_no_rule():
    assert rv.term_notes("هل انتشر الإسلام بالسيف؟") == []
    assert [t.id for t in rv.term_notes("ما معنى التوحيد لشخص لم يسمع به؟")] == ["t-tawhid"]


def test_no_notes_keeps_plain_no_reference():
    r = run("The moon-cheese rule is obligatory.")
    assert r.terms == [] and r.verifications == [] and r.headline_ar == rv.NO_REFERENCE_AR


def test_cueless_hadith_or_verse_is_found_in_the_corpus_with_its_source():
    r = run("إنما الأعمال بالنيات وإنما لكل امرئ ما نوى")
    [v] = r.verifications
    assert v.status == "supported" and v.attributed_to == "prophet" and v.cue == "" and v.source_url
    assert r.headline_ar == rv.NOTES_ONLY_AR
    [v] = run("يريد الله بكم اليسر ولا يريد بكم العسر").verifications
    assert v.attributed_to == "allah" and v.item_id.startswith("q-2-185")


def test_ordinary_sentence_is_not_matched_to_a_text_and_coverage_is_explained():
    r = run("The moon-cheese rule is obligatory.")
    assert r.verifications == [] and "مسألة" in r.coverage_ar and "آية" in r.coverage_ar
    from app.pipeline.mizan import find_quote
    assert find_quote("الزكاة واجبة في الذهب إذا بلغ النصاب", "x", 0) == []


def test_quoted_hadith_inside_a_post_is_found():
    from app.pipeline.mizan import find_quote
    [v] = find_quote("قرأت منشوراً يقول: «لا ضرر ولا ضرار» فهل هو حديث؟", "x", 0)
    assert v.attributed_to == "prophet" and v.quote == "لا ضرر ولا ضرار" and v.item_grade in ("sahih", "hasan")
