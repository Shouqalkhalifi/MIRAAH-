import json

from app.pipeline.fingerprint import (
    FingerprintLLM, apply_rules, count_negations, extract_numbers, fingerprint, verify_quote,
)


def test_negations_arabic():
    assert count_negations("لا يجوز الصوم") == 1
    assert count_negations("ولم يصم ولن يصوم") == 2
    assert count_negations("ليس عليه قضاء، بلا عذر") == 2
    assert count_negations("إلا المسافر") == 0  # «إلا» ليست نفياً
    assert count_negations("لِيَ الأمرُ") == 0


def test_hindi_negations_and_numbers():
    assert count_negations("यात्री रोज़ा नहीं रख सकता") == 1  # «नहीं» كلمة واحدة رغم علامات الحركات
    assert count_negations("यात्री रोज़ा रख सकता") == 0
    assert extract_numbers("तीन दिन") == ["3"]
    assert extract_numbers("३ बार") == ["3"]  # أرقام ديفاناغاري
    assert extract_numbers("एक हज़ार") == ["1000"]


def test_negations_english():
    assert count_negations("He did not fast and doesn't need to") == 2
    assert count_negations("There is no blame, never.") == 2
    assert count_negations("He can’t pray") == 1


def test_negations_french():
    assert count_negations("Il ne jeûne pas") == 1
    assert count_negations("Ce n'est jamais permis") == 1
    assert count_negations("sans excuse") == 1


def test_numbers_digits_and_words_cross_language():
    assert extract_numbers("صيام ستة أيام من شوال") == ["6"]
    assert extract_numbers("fasting six days of Shawwal") == ["6"]
    assert extract_numbers("jeûner six jours") == ["6"]
    assert extract_numbers("٣ أيام وثلاث ليال") == ["3", "3"]
    assert extract_numbers("Pay 2.5 percent") == ["2.5"]


def test_numbers_ignore_ambiguous_one():
    assert extract_numbers("no one should") == []
    assert extract_numbers("un homme") == []


def test_verify_quote():
    t = "يُجوزُ لِلمسافرِ أن يفطر"
    assert verify_quote("للمسافر", t) == "للمسافر"  # تطابق بعد إزالة التشكيل
    assert verify_quote("للمريض", t) is None
    assert verify_quote("", t) is None


def raw(**fp):
    return FingerprintLLM.model_validate({"fingerprint": fp, "condition_quotes": ["للمسافر", "مختلق"]})


def test_apply_rules_overrides_model_counts_and_drops_fake_quotes():
    r = raw(conditions=["person is traveling", "if ill"], negations=5, numbers=["99"])
    out = apply_rules(r, "يجوز للمسافر أن يفطر ولا إثم")
    assert out.fp.negations == 1 and out.fp.numbers == []
    assert out.condition_quotes == ["للمسافر", None]


def test_quotes_padded_to_conditions():
    r = FingerprintLLM.model_validate({"fingerprint": {"conditions": ["a", "b"]}, "condition_quotes": []})
    assert apply_rules(r, "x").condition_quotes == [None, None]


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def complete_json(self, prompt, schema, **kw):
        self.calls.append((prompt, kw))
        return schema.model_validate_json(json.dumps(self.reply))


def test_fingerprint_calls_llm_with_passage():
    llm = FakeLLM({"fingerprint": {"certainty": "definite"}})
    out = fingerprint(llm, "Six days.", "en")
    assert out.fp.certainty == "definite" and out.fp.numbers == ["6"]
    assert "Six days." in llm.calls[0][0] and llm.calls[0][1]["purpose"] == "fingerprint"


def test_hasr_construction_is_not_counted_as_negation():
    assert count_negations("كان لا يحدّث إلا على طهارة") == 0
    assert count_negations("ما محمد إلا رسول") == 0
    assert count_negations("He narrated only in a state of purity") == 0
    # نفي حقيقي مع حصر
    assert count_negations("لم يكن يصوم، ولا يحدّث إلا متوضئاً") == 1


def test_find_in_version_requires_verbatim_quote():
    from app.pipeline.fingerprint import find_in_version

    v = "A traveler may break the fast."
    assert find_in_version(FakeLLM({"present": True, "quote": "A traveler"}), "person is traveling",
                           "condition", "يجوز للمسافر", v, "en") == "A traveler"
    # «موجود» بلا اقتباس حقيقي لا يُقبل، حتى لا يُخفى سقوط حقيقي
    assert find_in_version(FakeLLM({"present": True, "quote": "for travelers"}), "x", "condition", "p", v, "en") is None
    assert find_in_version(FakeLLM({"present": False, "quote": None}), "x", "condition", "p", v, "en") is None


def test_hasr_in_english_and_french_not_counted_as_negation():
    # نسخ أمينة لـ «لا يحدّث إلا على طهارة»
    assert count_negations("He would not narrate hadith except in a state of purity") == 0
    assert count_negations("He did not narrate unless he was pure") == 0
    assert count_negations("Il ne racontait que dans un état de pureté") == 0
    # نفي حقيقي يبقى
    assert count_negations("Il ne racontait pas") == 1
    assert count_negations("He did not narrate.") == 1


def test_negation_with_attached_lam_and_until():
    # من حالات الإنذار الكاذب في eval/results.md
    assert count_negations("يُستحب صيام يوم عرفة لغير الحاج") == 1
    assert count_negations("someone who is not on pilgrimage") == 1
    # «لا ... حتى» و "not ... until|unless" قيدٌ يقابل "only when"
    assert count_negations("لا تجب الزكاة في المال حتى يبلغ النصاب") == 0
    assert count_negations("Wealth is not subject to zakat unless it reaches the nisab") == 0
    assert count_negations("Zakat is not due until the nisab is reached") == 0
    assert count_negations("ليتني أصوم") == 0
