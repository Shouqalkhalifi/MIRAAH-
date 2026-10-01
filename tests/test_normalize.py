from app.text.normalize import normalize_ar, strip_diacritics, tokens


def test_strip_diacritics():
    assert strip_diacritics("إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ") == "إنما الأعمال بالنيات"


def test_tatweel_removed():
    assert normalize_ar("الصـــلاة") == "الصلاه"


def test_hamza_forms_unified():
    assert normalize_ar("أحمد إسلام آمن ٱلله") == "احمد اسلام امن الله"
    assert normalize_ar("مؤمن رئيس") == "مومن رييس"


def test_taa_marbuta_and_alef_maqsura():
    assert normalize_ar("صلاة على مستشفى") == "صلاه علي مستشفي"


def test_arabic_digits():
    assert normalize_ar("٣ أيام و۴ ليال") == "3 ايام و4 ليال"


def test_presentation_forms():
    # أشكال العرض (مثل اسم مجلد المشروع) تتحول إلى الحروف الأساسية
    assert normalize_ar("ﻣِﺮآة") == "مراه"


def test_whitespace_and_case():
    assert normalize_ar("  The   Prophet\n said ") == "the prophet said"


def test_same_meaning_different_spelling_match():
    assert normalize_ar("يُرِيدُ اللَّهُ بِكُمُ الْيُسْرَ") == normalize_ar("يريد الله بكم اليسر")


def test_tokens():
    assert tokens("قالَ: «الدِّينُ النَّصِيحَةُ»") == ["قال", "الدين", "النصيحه"]
