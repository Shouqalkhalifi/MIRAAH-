from app.models import AlertType as T
from app.models import Lock, MeaningFingerprint, Report, Source
from app.pipeline.chain import analyze_chain
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.locks import check_lock, lock_in_text, suggest_locks
from tests.test_chain import THREE_LINKS, by_type, fake_align, fake_fp

SRC = "يجوز للمسافر أن يفطر في رمضان. ويجب عليه قضاء ما أفطره من أيام."


def test_suggest_from_fingerprint_quotes_and_fixed_cues():
    def fp(sentence):
        if "للمسافر" in sentence:
            return Fingerprinted(fp=MeaningFingerprint(conditions=["person is traveling"]),
                                 condition_quotes=["للمسافر"])
        return Fingerprinted(fp=MeaningFingerprint())

    text = "رُوي أن صيام ستة أيام قد يُستحب للمسافر، ولا يجب. وهذا حديث ضعيف."
    locks = {l.span_text: l.lock_type.value for l in suggest_locks(text, fp)}
    assert locks["للمسافر"] == "condition"
    assert locks["رُوي"] == "attribution"
    assert locks["قد"] == "certainty"
    assert locks["ستة"] == "number"
    assert locks["ولا"] == "negation"
    assert locks["ضعيف"] == "grade"
    assert all(lock_in_text(s, text) for s in locks)


def test_suggest_term_lock():
    locks = {l.span_text: l.lock_type.value for l in suggest_locks("يُكره الكلام أثناء الخطبة.")}
    assert locks.get("يُكره") == "term"


def test_number_and_negation_locks_checked_by_rules():
    assert check_lock(Lock(span_text="ستة", lock_type="number"), "", "fast six days", "en", None)
    assert not check_lock(Lock(span_text="ستة", lock_type="number"), "", "fast seven days", "en", None)
    assert check_lock(Lock(span_text="لا", lock_type="negation"), "", "it is not obligatory", "en", None)
    assert not check_lock(Lock(span_text="لا", lock_type="negation"), "", "it is obligatory", "en", None)


def test_other_locks_use_presence_with_quote():
    lock = Lock(span_text="للمسافر", lock_type="condition")
    assert check_lock(lock, SRC, "A traveler may...", "en", lambda *a: "A traveler")
    assert not check_lock(lock, SRC, "Muslims may...", "en", lambda *a: None)
    assert not check_lock(lock, SRC, "", "en", lambda *a: "x")  # جملة محذوفة
    assert check_lock(lock, SRC, "يجوز للمسافر الفطر", "ar", None)  # النسخة العربية تحوي المقطع نفسه


def test_lock_violated_through_chain_with_introduced_at():
    report = Report(source=Source(text=SRC), versions=THREE_LINKS,
                    locks=[Lock(span_text="للمسافر", lock_type="condition")])

    def lock_fn(lock, src_ctx, vtext, lang):
        return "kept" if any(w in vtext.lower() for w in ("travel", "voyag")) else None

    a = by_type(analyze_chain(report, fake_align, fake_fp, lock_fn=lock_fn))[T.lock_violated]
    assert a.severity.value == "red" and a.introduced_at == "en-summary" and a.propagated_to == ["fr-translation"]
    assert a.source_span.text == "للمسافر" and "للمسافر" in a.explanation_ar and "شرط" in a.explanation_ar
