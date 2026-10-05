from app.corpus import CorpusItem, load_corpus
from app.models import AlertType as T
from app.models import Report, Source, Version
from app.pipeline.mizan import NOT_FOUND_AR, Mizan, check_report, containment, find_attributions, verify

M = Mizan(load_corpus())


def test_find_prophetic_attributions_ar_en_fr():
    assert find_attributions("قال رسول الله ﷺ: «إنما الأعمال بالنيات»")[0][:1] == ("prophet",)
    assert find_attributions("قال رسول الله ﷺ: «إنما الأعمال بالنيات»")[0][2] == "إنما الأعمال بالنيات"
    assert find_attributions('The Prophet ﷺ said: "Make things easy."')[0][0] == "prophet"
    assert find_attributions("The Prophet (pbuh) said that religion is sincere counsel.")[0][0] == "prophet"
    assert find_attributions("Le Prophète ﷺ a dit : « Facilitez »")[0][0] == "prophet"
    assert find_attributions("قال الله تعالى: ﴿لا يكلف الله نفسا إلا وسعها﴾")[0][0] == "allah"
    assert find_attributions("يجوز للمسافر أن يفطر.") == []


def test_supported_hadith():
    v = verify("قال رسول الله ﷺ: «إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى»", "source", 0, M)[0]
    assert v.status == "supported" and v.item_id == "h-bukhari-1" and v.score >= 0.8


def test_supported_in_english_translation():
    v = verify('The Prophet ﷺ said: "Make things easy and do not make them difficult."', "en", 0, M)[0]
    assert v.status == "supported" and v.item_id == "h-bukhari-69"


def test_unverified_saying_uses_fixed_phrase_never_fabricated():
    v = verify('The Prophet ﷺ said: "Knowledge in childhood is like engraving on stone."', "post", 0, M)[0]
    assert v.status == "unverified" and v.note_ar == NOT_FOUND_AR and v.item_id is None
    assert "مكذوب" not in v.note_ar


def test_partially_supported():
    v = verify("قال رسول الله ﷺ: «إنما الأعمال بالنيات والقلوب»", "source", 0, M)[0]
    assert v.status == "partially_supported"


def _corpus_with(item):
    return Mizan(load_corpus() + [CorpusItem.model_validate(item)])


def test_conflicting_when_corpus_grade_is_weak():
    m = _corpus_with({"id": "h-test-daif", "type": "hadith", "text_ar": "اطلبوا العلم ولو بالصين", "grade": "daif",
                      "source_name": "اختبار", "license_note": "اختبار"})
    v = verify("قال رسول الله ﷺ: «اطلبوا العلم ولو بالصين»", "source", 0, m)[0]
    assert v.status == "conflicting" and v.item_grade == "daif"


def test_conflicting_when_stated_grade_differs():
    v = verify("قال رسول الله ﷺ: «الدين النصيحة» (حديث ضعيف)", "source", 0, M)[0]
    assert v.status == "conflicting"


def test_unsupported_quran_reference_mismatch():
    v = verify("قال الله تعالى: ﴿وأقيموا الصلاة﴾ (2:185)", "source", 0, M)[0]
    assert v.status == "unsupported" and v.item_id == "q-2-185-yusr"


def test_containment():
    assert containment(["a", "b"], ["a", "b", "c"]) == 1.0
    assert containment([], ["a"]) == 0.0


def test_check_report_alerts_and_propagation():
    r = Report(source=Source(text="ومن الأقوال المأثورة: «العلم في الصغر كالنقش على الحجر»."), versions=[
        Version(label="post", lang="en", text='The Prophet ﷺ said: "Knowledge in childhood is like engraving on stone."'),
        Version(label="post-fr", lang="fr", derived_from="post",
                text="Le Prophète ﷺ a dit : « La science dans l'enfance est comme une gravure sur la pierre. »"),
    ])
    vs, alerts = check_report(r, M)
    assert [v.label for v in vs] == ["post", "post-fr"]
    assert len(alerts) == 1
    a = alerts[0]
    assert a.type == T.unverified_attribution and a.severity.value == "red"
    assert a.introduced_at == "post" and a.propagated_to == ["post-fr"]
    assert NOT_FOUND_AR in a.explanation_ar and a.version_span.text.startswith("The Prophet")


def test_supported_attribution_produces_no_alert():
    r = Report(source=Source(text="قال رسول الله ﷺ: «الدين النصيحة»."),
               versions=[Version(label="en", lang="en", text='The Prophet ﷺ said: "The religion is sincere counsel."')])
    vs, alerts = check_report(r, M)
    assert [v.status for v in vs] == ["supported", "supported"] and alerts == []


def test_quran_brackets_extract_quote():
    v = verify("قال الله تعالى: ﴿لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا﴾", "source", 0, M)[0]
    assert v.quote.startswith("لَا يُكَلِّفُ") and v.status == "supported" and v.item_id == "q-2-286-wus"


# ---------- المدونة الرسمية: المصحف كاملاً من مجمع الملك فهد ----------
def test_official_quran_is_complete_with_imlaei_match_form():
    verses = [i for i in load_corpus() if i.id.endswith("-kfgqpc")]
    assert len(verses) == 6236
    assert all(i.text_match and i.text_en and i.license_note for i in verses)


def test_any_verse_found_by_imlaei_spelling_and_by_translation():
    # الرسم العثماني «ٱلصَّلَوٰةَ» يُطابَق بالإملائي «الصلاة»
    assert verify("قال الله تعالى: «وأقيموا الصلاة وآتوا الزكاة»", "x", 0, M)[0].status == "supported"
    assert verify('Allah says: "There shall be no compulsion in religion"', "x", 0, M)[0].item_id == "q-2-256-kfgqpc"


def test_cited_verse_number_must_hold_the_quote():
    v = verify("قال الله تعالى: ﴿لا إكراه في الدين﴾ (3:10)", "x", 0, M)[0]
    assert v.status == "unsupported" and v.item_id == "q-3-10-kfgqpc" and "2:256" in v.note_ar
    assert verify("قال الله تعالى: ﴿لا إكراه في الدين﴾ (2:256)", "x", 0, M)[0].status == "supported"
