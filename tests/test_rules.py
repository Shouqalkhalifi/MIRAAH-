"""اختبار لكل قاعدة من جدول 6.3 ببصمات مصنوعة يدوياً."""
import pytest

from app.models import AlertType as T
from app.models import MeaningFingerprint, Severity
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.rules import (
    TEMPLATES, compare_unit, explain, length_drop, phrases_match,
)


def F(cq=None, eq=None, **kw) -> Fingerprinted:
    fp = MeaningFingerprint.model_validate(kw)
    return Fingerprinted(fp=fp, condition_quotes=cq or [None] * len(fp.conditions),
                         exception_quotes=eq or [None] * len(fp.exceptions))


def types(p, c):
    return [h.type for h in compare_unit(p, c)]


def test_identical_fingerprints_no_alerts():
    fp = dict(conditions=["person is traveling"], ruling="permissible", certainty="definite",
              scope={"quantifier": "specific", "restricted_to": "travelers"}, negations=1, numbers=["6"])
    assert types(F(**fp), F(**fp)) == []


# --- condition_dropped ---
def test_condition_dropped_with_verified_quote():
    hits = compare_unit(F(conditions=["person is traveling"], cq=["للمسافر"]), F())
    assert [h.type for h in hits] == [T.condition_dropped]
    assert hits[0].src_quote == "للمسافر" and hits[0].severity == Severity.red


def test_condition_kept_when_paraphrased():
    assert types(F(conditions=["person is traveling"]), F(conditions=["the traveller"])) == []


def test_condition_kept_when_expressed_as_scope():
    child = F(scope={"quantifier": "specific", "restricted_to": "travelers"})
    assert types(F(conditions=["person is traveling"], scope=child.fp.scope.model_dump()), child) == []


# --- exception_dropped ---
def test_exception_dropped():
    assert types(F(exceptions=["unless ill"]), F()) == [T.exception_dropped]
    assert types(F(exceptions=["unless ill"]), F(exceptions=["except when sick or ill"])) == []


# --- certainty_raised ---
@pytest.mark.parametrize("before", ["possible", "probable"])
def test_certainty_raised(before):
    assert types(F(certainty=before), F(certainty="definite")) == [T.certainty_raised]


def test_certainty_lowered_is_not_raised():
    assert types(F(certainty="definite"), F(certainty="possible")) == []


# --- attribution_upgraded ---
def test_attribution_upgraded():
    p = F(attribution={"to": "scholar", "form": "tamrid"})
    c = F(attribution={"to": "scholar", "form": "assertive"})
    assert types(p, c) == [T.attribution_upgraded]


# --- new_prophetic_attribution ---
def test_new_prophetic_attribution():
    p = F(attribution={"to": "scholar", "form": "assertive"})
    c = F(attribution={"to": "prophet", "form": "assertive"})
    assert types(p, c) == [T.new_prophetic_attribution]
    assert types(c, c) == []


def test_added_sentence_with_prophetic_attribution():
    assert types(None, F(attribution={"to": "prophet", "form": "assertive"})) == [T.new_prophetic_attribution]
    assert types(None, F(attribution={"to": "author", "form": "none"})) == []


# --- ruling_shift ---
def test_ruling_shift():
    assert types(F(ruling="disliked"), F(ruling="forbidden")) == [T.ruling_shift]
    assert types(F(ruling="permissible"), F(ruling="none")) == []  # غياب الحكم في الابن ليس تحوّلاً


# --- scope ---
def test_scope_widened():
    p = F(scope={"quantifier": "specific", "restricted_to": "travelers"})
    assert types(p, F(scope={"quantifier": "all"})) == [T.scope_widened]


def test_scope_narrowed():
    assert types(F(scope={"quantifier": "all"}), F(scope={"quantifier": "some"})) == [T.scope_narrowed]


def test_scope_restriction_lost_with_unspecified_quantifier():
    p = F(scope={"quantifier": "unspecified", "restricted_to": "women"})
    assert types(p, F(scope={"quantifier": "unspecified"})) == [T.scope_widened]


# --- hasr_lost ---
def test_hasr_lost():
    assert types(F(restriction_hasr=True), F(restriction_hasr=False)) == [T.hasr_lost]
    assert types(F(restriction_hasr=False), F(restriction_hasr=True)) == []


# --- consensus_inflated ---
@pytest.mark.parametrize("after", ["majority", "ijma"])
def test_consensus_inflated(after):
    assert types(F(consensus_claim="some_scholars"), F(consensus_claim=after)) == [T.consensus_inflated]


def test_consensus_deflated_not_flagged():
    assert types(F(consensus_claim="ijma"), F(consensus_claim="majority")) == []


# --- disagreement_collapsed (الحزمة العلمية: لا يُعرض الخلافي بصيغة القطع) ---
def test_disagreement_collapsed_into_a_definite_ruling():
    hits = compare_unit(F(disagreement_stated=True, certainty="unstated"),
                        F(certainty="unstated"))
    assert [h.type for h in hits] == [T.disagreement_collapsed] and hits[0].severity == Severity.red


def test_disagreement_kept_is_fine():
    assert types(F(disagreement_stated=True), F(disagreement_stated=True)) == []


# --- attribution_generalized ---
@pytest.mark.parametrize("before", ["scholar", "companion", "author"])
def test_opinion_attributed_to_islam_itself(before):
    assert types(F(attribution={"to": before}), F(attribution={"to": "religion"})) == [T.attribution_generalized]


def test_religion_to_religion_not_flagged():
    assert types(F(attribution={"to": "religion"}), F(attribution={"to": "religion"})) == []


# --- hadith_grade_dropped ---
def test_hadith_grade_dropped():
    p = F(hadith_mentions=[{"snippet": "x", "grade_stated": "daif"}])
    c = F(hadith_mentions=[{"snippet": "x", "grade_stated": "none"}])
    assert types(p, c) == [T.hadith_grade_dropped]
    assert types(p, p) == []


# --- negation_mismatch / number_mismatch ---
def test_negation_mismatch():
    hits = compare_unit(F(negations=1), F(negations=0))
    assert [h.type for h in hits] == [T.negation_mismatch] and hits[0].confidence < 0.85


def test_number_mismatch():
    assert types(F(numbers=["6"]), F(numbers=["7"])) == [T.number_mismatch]
    assert types(F(numbers=["6", "3"]), F(numbers=["3", "6"])) == []


# --- length_drop ---
def test_length_drop_same_language():
    h = length_drop("one two three four five six seven eight nine ten", "one two three", "en", "en")
    assert h.type == T.length_drop and h.severity == Severity.info and h.before == "70"
    assert length_drop("a b c d", "a b c", "en", "en") is None


def test_length_drop_skipped_across_languages():
    assert length_drop("كلمة " * 20, "word", "ar", "en") is None


# --- sentence_dropped ---
def test_sentence_dropped():
    assert types(F(), None) == [T.sentence_dropped]


# --- عام ---
def test_phrase_matching():
    assert phrases_match("person is traveling", "traveller")
    assert phrases_match("if able", "when he is able")
    assert not phrases_match("person is traveling", "person is ill")


def test_every_rule_type_has_template_and_explains():
    for t in TEMPLATES:
        assert TEMPLATES[t][1]
    hits = compare_unit(F(certainty="possible", ruling="disliked"), F(certainty="definite", ruling="forbidden"))
    exp = dict((h.type, explain(h)[0]) for h in hits)
    assert "محتمل" in exp[T.certainty_raised] and "جازم" in exp[T.certainty_raised]
    assert "مكروه" in exp[T.ruling_shift] and "محرّم" in exp[T.ruling_shift]
