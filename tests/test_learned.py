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


def test_unrelated_answer_asks_to_retry():
    assert check(SRC, "الصلاة واجبة")["verdict"] == "retry"
