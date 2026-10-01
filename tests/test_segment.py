from app.pipeline.segment import split_sentences


def texts(t):
    return [s.text for s in split_sentences(t)]


def test_arabic_basic():
    assert texts("يجوز للمسافر أن يفطر. ويجب عليه القضاء.") == ["يجوز للمسافر أن يفطر.", "ويجب عليه القضاء."]


def test_arabic_question_mark():
    assert texts("هل يجوز الفطر؟ نعم للمسافر.") == ["هل يجوز الفطر؟", "نعم للمسافر."]


def test_arabic_semicolon_and_comma_do_not_split():
    t = "يجوز الفطر للمسافر؛ لأن السفر مظنة المشقة، والله أعلم."
    assert texts(t) == [t]


def test_english_basic():
    assert texts("A traveler may break the fast. He must make it up!") == [
        "A traveler may break the fast.", "He must make it up!"]


def test_english_abbreviations():
    assert texts("See e.g. the Sahih of al-Bukhari, Vol. 1. It is reliable.") == [
        "See e.g. the Sahih of al-Bukhari, Vol. 1.", "It is reliable."]


def test_decimal_numbers():
    assert texts("Pay 2.5 percent. That is zakat.") == ["Pay 2.5 percent.", "That is zakat."]


def test_initials():
    assert texts("Narrated by A. Smith in the book. Done.") == ["Narrated by A. Smith in the book.", "Done."]


def test_closing_quotes_stay_with_sentence():
    assert texts('He said: "Make things easy." Then he left.') == [
        'He said: "Make things easy."', "Then he left."]
    assert texts("قال: «يسروا ولا تعسروا.» ثم مضى.") == ["قال: «يسروا ولا تعسروا.»", "ثم مضى."]


def test_ellipsis_and_interrobang():
    assert texts("Wait... Really?! Yes.") == ["Wait...", "Really?!", "Yes."]


def test_newlines_split():
    assert texts("السطر الأول\nالسطر الثاني") == ["السطر الأول", "السطر الثاني"]


def test_offsets_are_traceable():
    t = "  الجملة الأولى. الجملة الثانية؟  "
    segs = split_sentences(t)
    for s in segs:
        assert t[s.start:s.end] == s.text
    assert [s.index for s in segs] == [0, 1]


def test_empty():
    assert split_sentences("") == []
    assert split_sentences("   \n  ") == []


def test_no_terminator():
    assert texts("نص بلا علامة ترقيم") == ["نص بلا علامة ترقيم"]
