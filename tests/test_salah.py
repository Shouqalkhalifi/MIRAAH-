"""«تعلّم الصلاة · قابِل ذكرك»: كل ذكر وآية من المدونة بعد فحص الميزان، ولا نص في salah.js."""
import json

from fastapi.testclient import TestClient

from app import salah
from app.config import ROOT
from app.corpus import load_corpus
from app.main import app
from app.pipeline.mizan import NOT_FOUND_AR, verify

client = TestClient(app)


def test_every_step_dhikr_comes_from_corpus_and_mizan_finds_it():
    corpus = {i.id: i for i in load_corpus()}
    steps = salah.load_steps()
    assert len(steps) == 10
    for s in steps:
        assert s["mizan"] == "supported", s["name"]
        assert s["dhikr"] == " ".join(src["text_ar"] for src in s["sources"])
        for ref in s["sources"] + s["refs"]:
            assert ref["id"] in corpus and ref["source_url"].startswith("https://")


def test_wrong_dhikr_is_named_from_the_source():
    ruku = next(s for s in salah.load_steps() if s["name"] == "الركوع")
    assert ruku["wrong"] == [{"has": "الاعلي", "where": "السجود", "text": "سُبْحَانَ رَبِّيَ الأَعْلَى"}]


def test_step_with_unknown_corpus_id_shows_not_found_and_no_text(tmp_path, monkeypatch):
    f = tmp_path / "steps.json"
    f.write_text(json.dumps({"steps": [{"name": "x", "pose": None, "dhikr": ["h-not-in-corpus"]}]}), encoding="utf-8")
    monkeypatch.setattr(salah, "STEPS_PATH", f)
    salah.load_steps.cache_clear()
    try:
        [step] = salah.load_steps()
        assert step["dhikr"] == "" and step["mizan"] == "unverified" and step["mizan_note"] == NOT_FOUND_AR
    finally:
        salah.load_steps.cache_clear()


def test_salah_js_holds_no_dhikr_or_quran_text():
    js = (ROOT / "app" / "static" / "salah.js").read_text(encoding="utf-8")
    for word in ("سُبْحَانَ", "الْحَمْدُ", "التَّحِيَّاتُ", "أَحَدٌ", "رَبِّ اغْفِرْ"):
        assert word not in js


def test_salah_hadith_attributions_are_supported_in_review():
    for text in ["قال رسول الله ﷺ: «سبحان ربي العظيم»",
                 'The Prophet said: "I have been commanded to prostrate on seven bones"']:
        assert [v.status for v in verify(text, "x", 0)] == ["supported"]


def test_salah_api_and_page():
    r = client.get("/api/salah/steps")
    assert r.status_code == 200 and len(r.json()) == 10
    html = client.get("/salah").text
    assert "window.SALAH_STEPS" in html and "قابِل ذكرك بمصدره" in html and "ولا يُحفظ" in html
