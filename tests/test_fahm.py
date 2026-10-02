import json

import pytest
from pydantic import ValidationError

from app.corpus import CorpusItem
from app.models import AlertType as T
from app.pipeline.fahm import term_hits, term_rules, understanding_risks


def test_shipped_terms_have_rules():
    assert {i.id for i in term_rules()} == {"t-islam", "t-tawhid", "t-ibadah", "t-nubuwwah", "t-wahy", "t-shariah",
                                            "t-sunnah", "t-makruh", "t-ijma"}


def test_package_terms_are_attributed_to_the_package():
    from app.corpus import load_corpus
    pkg = [i for i in load_corpus() if i.type == "term" and i.source_name.startswith("الحزمة والبيانات")]
    assert len(pkg) == 10  # نماذج قاموس المصطلحات الأساسية في الحزمة العلمية


def test_tawhid_reduced_to_unity_is_flagged():
    hits = term_hits("أساس الإسلام التوحيد.", "The basis of Islam is unity.")
    assert [h.match_key for h in hits] == ["t-tawhid"]
    assert term_hits("أساس الإسلام التوحيد.", "The basis of Islam is Tawhid, the Oneness of God.") == []


def test_worship_reduced_to_rituals_is_flagged():
    hits = term_hits("العبادة تشمل أعمال القلب.", "Rituals include deeds of the heart.")
    assert [h.match_key for h in hits] == ["t-ibadah"]


def test_makruh_rendered_as_forbidden():
    hits = term_hits("يُكره الكلام أثناء الخطبة.", "Talking during the sermon is forbidden.")
    assert [h.type for h in hits] == [T.term_narrowing]
    h = hits[0]
    assert h.match_key == "t-makruh" and h.ver_quote == "forbidden" and h.evidence[0].ref == "t-makruh"
    assert h.severity.value == "yellow"


def test_makruh_rendered_as_disliked_is_fine():
    assert term_hits("يُكره الكلام أثناء الخطبة.", "Talking during the sermon is disliked.") == []


def test_majority_rendered_as_consensus():
    hits = term_hits("وهذا قول الجمهور.", "This is the consensus of scholars.")
    assert [h.match_key for h in hits] == ["t-ijma"]


def test_avoid_word_already_in_parent_is_not_flagged():
    assert term_hits("It is makruh (يُكره), not forbidden.", "It is disliked, not forbidden.") == []


def test_whole_word_matching():
    # «forbiddenness» ليست «forbidden» كلمةً كاملة
    assert term_hits("يُكره ذلك", "the forbiddenness question") == []


def test_term_rule_requires_both_fields():
    with pytest.raises(ValidationError):
        CorpusItem(id="t", type="term", text_ar="x", source_name="s", license_note="l", trigger_forms=["a"])


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def complete_json(self, prompt, schema, **kw):
        return schema.model_validate_json(json.dumps(self.reply, ensure_ascii=False))


def test_understanding_risks_are_possibilities_tied_to_text():
    src = "يجوز للمسافر أن يفطر في رمضان."
    llm = FakeLLM({"risks": [
        {"risk_ar": "قد يُفهم أن الفطر واجب على المسافر.", "quote": "يجوز للمسافر أن يفطر", "reason_ar": "صيغة الجواز"},
        {"risk_ar": "الفطر أفضل دائماً.", "quote": "للمسافر", "reason_ar": "x"},
        {"risk_ar": "قد يظن القارئ شيئاً", "quote": "نص غير موجود", "reason_ar": "y"},
    ]})
    risks = understanding_risks(llm, src)
    assert len(risks) == 2  # الثالث بلا موضع حقيقي في النص فاستُبعد
    assert all(r.risk_ar.startswith("قد ") for r in risks)
