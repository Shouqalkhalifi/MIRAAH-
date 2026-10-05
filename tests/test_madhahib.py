"""المذاهب الأربعة مراجعَ لا أحكاماً: نسبة قول إلى مذهب لا نملك نصه ← «لم نتحقق منها» مع كتب المذهب."""
from app import madhahib
from app.models import AlertType as T
from app.models import Report, Source, Version
from app.pipeline.mizan import check_report, verify_madhhab


def test_four_schools_with_books_from_dorar_list():
    ms = madhahib.madhahib()
    assert [m["id"] for m in ms] == ["hanafi", "maliki", "shafii", "hanbali"]
    assert all(len(m["books"]) >= 4 and all(b["dorar_no"] and b["title"] and b["author"] for b in m["books"]) for m in ms)
    assert madhahib.load()["source"]["refs_url"] == "https://dorar.net/refs/feqhia"


def test_detects_school_attribution_ar_en_without_false_malik():
    assert [m for m, _ in madhahib.find("وعند الحنفية يجب الوتر")] == ["hanafi"]
    assert [m for m, _ in madhahib.find("The Hanbali school holds that…")] == ["hanbali"]
    assert [m for m, _ in madhahib.find("قال الإمام مالك")] == ["maliki"]
    assert madhahib.find("مالك يوم الدين") == []


def test_school_attribution_is_unverified_with_books_never_a_ruling():
    [v] = verify_madhhab("وعند المالكية لا زكاة فيه", "reader", 0)
    assert v.status == "unverified" and v.attributed_to == "madhhab"
    assert "المدونة الكبرى" in v.source_name and "لم نتحقق" in v.note_ar


def test_only_a_new_school_attribution_in_the_chain_is_flagged():
    r = Report(source=Source(text="اختلف العلماء في زكاة الحلي، فأوجبها الحنفية."), versions=[
        Version(label="en", lang="en", text="Scholars differ; the Hanafis require it."),
        Version(label="post", lang="en", text="The Shafi'i school requires zakat on all jewelry.", derived_from="en")])
    _, alerts = check_report(r)
    school = [a for a in alerts if a.type == T.madhhab_unverified]
    assert [(a.version_label, a.severity.value) for a in school] == [("post", "yellow")]


def test_sources_page_lists_official_sources_with_live_counts():
    from fastapi.testclient import TestClient

    from app.main import app
    html = TestClient(app).get("/sources").text
    for s in ("مجمع الملك فهد", "QuranEnc", "HadeethEnc", "المذهب الحنفي", "المذهب المالكي", "المذهب الشافعي",
              "المذهب الحنبلي", "المغني لابن قدامة", "dorar.net/refs/feqhia", "لا تُفتي ولا ترجّح"):
        assert s in html, s
    assert "6,236" in html
