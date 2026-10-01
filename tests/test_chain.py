"""اختبار السلسلة بمحاذاة وبصمة وهميتين (بلا نموذج)."""
from app.models import AlertType as T
from app.models import MeaningFingerprint, Report, Source, Version
from app.pipeline.align import Unit
from app.pipeline.chain import analyze_chain
from app.pipeline.fingerprint import Fingerprinted

SOURCE = "يجوز للمسافر أن يفطر في رمضان. ويجب عليه قضاء ما أفطره من أيام."
TRANS = "A traveler may break the fast in Ramadan. He must make up the days he missed."
SUMMARY = "Muslims may break the fast in Ramadan."
FRENCH = "Les musulmans peuvent rompre le jeûne pendant le Ramadan."


def fake_align(parent, child, pl, cl):
    if len(parent) == len(child):
        return [Unit((i,), (i,)) for i in range(len(child))]
    return [Unit((0,), (0,))] + [Unit((i,), ()) for i in range(1, len(parent))]


def fake_fp(text, lang):
    t = text.lower()
    if any(k in t for k in ("مسافر", "travel", "voyag")):
        fp = {"conditions": ["person is traveling"], "ruling": "permissible",
              "scope": {"quantifier": "specific", "restricted_to": "travelers"}}
        return Fingerprinted(fp=MeaningFingerprint.model_validate(fp),
                             condition_quotes=["للمسافر" if "للمسافر" in text else None])
    if any(k in t for k in ("قضاء", "make up", "rattrap")):
        return Fingerprinted(fp=MeaningFingerprint(ruling="obligatory"))
    return Fingerprinted(fp=MeaningFingerprint.model_validate(
        {"ruling": "permissible", "scope": {"quantifier": "all"}}))


def chain_report(versions):
    return Report(source=Source(text=SOURCE, content_level="B"), versions=versions)


THREE_LINKS = [
    Version(label="en-translation", lang="en", text=TRANS),
    Version(label="en-summary", lang="en", text=SUMMARY, derived_from="en-translation"),
    Version(label="fr-translation", lang="fr", text=FRENCH, derived_from="en-summary"),
]


def by_type(alerts):
    return {a.type: a for a in alerts}


def test_condition_drop_detected_at_second_link_and_propagates():
    alerts = analyze_chain(chain_report(THREE_LINKS), fake_align, fake_fp)
    a = by_type(alerts)
    cd = a[T.condition_dropped]
    assert cd.introduced_at == "en-summary" and cd.version_label == "en-summary"
    assert cd.propagated_to == ["fr-translation"]
    assert cd.source_span.text == "للمسافر" and cd.source_sentence_indices == [0]
    assert cd.confidence == 0.85  # ظهر أيضاً في المقارنة المحلية مع الأم
    assert a[T.sentence_dropped].introduced_at == "en-summary"
    assert a[T.scope_widened].introduced_at == "en-summary"
    assert a[T.length_drop].introduced_at == "en-summary"
    # الترجمة الأولى سليمة: لا تنبيه دخل فيها
    assert all(x.introduced_at != "en-translation" for x in alerts)
    # الأحمر أولاً
    assert alerts[0].severity.value == "red"


def test_faithful_chain_has_no_alerts():
    alerts = analyze_chain(chain_report(THREE_LINKS[:1]), fake_align, fake_fp)
    assert alerts == []


def test_branching_versions_each_compared_to_source():
    vs = [Version(label="en", lang="en", text=TRANS),
          Version(label="summary-direct", lang="en", text=SUMMARY)]
    a = by_type(analyze_chain(chain_report(vs), fake_align, fake_fp))
    assert a[T.condition_dropped].introduced_at == "summary-direct"
    assert a[T.condition_dropped].propagated_to == []


def test_four_links_defect_in_last():
    vs = [Version(label="v1", lang="en", text=TRANS),
          Version(label="v2", lang="en", text=TRANS, derived_from="v1"),
          Version(label="v3", lang="en", text=TRANS, derived_from="v2"),
          Version(label="v4", lang="en", text=SUMMARY, derived_from="v3")]
    a = by_type(analyze_chain(chain_report(vs), fake_align, fake_fp))
    assert a[T.condition_dropped].introduced_at == "v4"


def test_progress_reports_all_stages_in_order():
    seen = []
    analyze_chain(chain_report(THREE_LINKS), fake_align, fake_fp, progress=seen.append)
    assert seen == ["segment", "align", "fingerprint", "compare", "chain"]


def test_each_unit_text_fingerprinted_once():
    calls = []

    def counting_fp(text, lang):
        calls.append((text, lang))
        return fake_fp(text, lang)

    analyze_chain(chain_report(THREE_LINKS), fake_align, counting_fp)
    assert len(calls) == len(set(calls))
