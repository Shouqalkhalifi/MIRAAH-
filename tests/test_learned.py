"""«ماذا تعلّمت اليوم؟»: مقابلة عبارة القارئ بألفاظ الأصل بالقواعد."""
from app.pipeline.learned import check

SRC = "يجوز للمسافر أن يفطر في رمضان. ويجب عليه قضاء ما أفطره من أيام."


def test_faithful_answer_is_great_despite_typos():
    r = check(SRC, "يجوز للمسافر ان يفطر في رمضان ويجيب عليه قضاء ما افطره في رمضان")
    assert r["verdict"] == "great" and r["missing"] == ["أيام"]


def test_dropped_condition_is_listed_as_missing():
    r = check(SRC, "يجوز للمسلم ان يفطر في رمضان")
    assert r["verdict"] == "close" and "للمسافر" in r["missing"] and "قضاء" in r["missing"]


def test_added_negation_flips_the_verdict():
    r = check(SRC, "لا يجوز للمسافر أن يفطر في رمضان ويجب عليه قضاء ما أفطره من أيام")
    assert r["verdict"] == "retry" and "نفي" in r["note"]


def test_exception_after_negation_is_not_a_flip():
    r = check(SRC, "لا يجوز افطار في رمضان الا اذا سافرت")
    assert r["verdict"] == "close" and not r["note"]
    assert "يفطر" not in r["missing"] and "قضاء" in r["missing"]
    full = check(SRC, "لا يجوز الإفطار في رمضان إلا للمسافر، ويجب عليه قضاء الأيام التي أفطرها")
    assert full["verdict"] == "great" and not full["note"]
    own = check(SRC, "لا يجوز افطار في رمضان الا اذا سافرت واقضي التي افطرته في السفر")
    assert own["verdict"] == "great" and "قضاء" not in own["missing"]


EN = "A traveler may break the fast in Ramadan. He must make up the days he missed."


def test_english_answer_against_english_reference():
    assert check(EN, "A traveler may break the fast in Ramadan. He must make up the days he missed.")["verdict"] == "great"
    r = check(EN, "Travelers can break their fast in Ramadan")
    assert r["verdict"] == "close" and "make" in r["missing"]
    assert check(EN, "A traveler can't break the fast in Ramadan, he must make up the days")["verdict"] == "retry"


def test_unrelated_answer_asks_to_retry():
    assert check(SRC, "الصلاة واجبة")["verdict"] == "retry"
