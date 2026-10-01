"""اختبار الواجهة البرمجية والشاشات من البداية للنهاية بمزوّد نموذج وهمي (بلا شبكة)."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from app import service
from app.db import get_engine
from app.llm import LLM, ProviderResponse
from app.main import DISCLAIMER, app
from app.pipeline.align import SYSTEM_ALIGN

client = TestClient(app)

SOURCE = "يجوز للمسافر أن يفطر في رمضان. ويجب عليه قضاء ما أفطره من أيام."
CHAIN = {
    "title": "اختبار",
    "source": {"text": SOURCE, "lang": "ar", "source_ref": "اصطناعي", "content_level": "B"},
    "versions": [
        {"label": "en-translation", "lang": "en", "derived_from": "source",
         "text": "A traveler may break the fast in Ramadan. He must make up the days he missed."},
        {"label": "en-summary", "lang": "en", "derived_from": "en-translation",
         "text": "Muslims may break the fast in Ramadan."},
        {"label": "fr-translation", "lang": "fr", "derived_from": "en-summary",
         "text": "Les musulmans peuvent rompre le jeûne pendant le Ramadan."},
    ],
}


class RouterProvider:
    """يجيب عن تعليمات المحاذاة والبصمة بقواعد بسيطة تحاكي النموذج."""

    def generate(self, model, system, user, max_tokens):
        if system.startswith(SYSTEM_ALIGN[:40]):
            parent, version = user.split("VERSION")
            np_, nv = len(re.findall(r"^\[\d+\]", parent, re.M)), len(re.findall(r"^\[\d+\]", version, re.M))
            if np_ == nv:
                pairs = [{"version": [i], "parent": [i]} for i in range(nv)]
            else:
                pairs = [{"version": [0], "parent": [0]}]
            reply = {"pairs": pairs}
        else:
            text = user.split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0].lower()
            if any(k in text for k in ("مسافر", "travel", "voyag")):
                reply = {"fingerprint": {"conditions": ["person is traveling"], "ruling": "permissible",
                                         "scope": {"quantifier": "specific", "restricted_to": "travelers"}},
                         "condition_quotes": ["للمسافر"]}
            elif any(k in text for k in ("قضاء", "make up")):
                reply = {"fingerprint": {"ruling": "obligatory"}}
            else:
                reply = {"fingerprint": {"ruling": "permissible", "scope": {"quantifier": "all"}}}
        return ProviderResponse(json.dumps(reply, ensure_ascii=False), 10, 5)


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    monkeypatch.setattr(service, "llm_factory", lambda: LLM(get_engine(), RouterProvider(), {"main": "fake"}))


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["corpus_items"] >= 9


def test_analyze_returns_full_report_with_condition_drop_at_second_link():
    r = client.post("/api/analyze", json=CHAIN)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["status"] == "analyzed" and rep["source_sentence_count"] == 2
    cd = next(a for a in rep["alerts"] if a["type"] == "condition_dropped")
    assert cd["introduced_at"] == "en-summary" and cd["propagated_to"] == ["fr-translation"]
    assert client.get(f"/api/report/{rep['id']}").json()["id"] == rep["id"]


def test_background_analysis_and_status():
    r = client.post("/api/analyze?background=true", json=CHAIN)
    rid = r.json()["id"]
    st = client.get(f"/api/report/{rid}/status").json()  # TestClient يشغّل المهمة الخلفية قبل الرجوع
    assert st["status"] == "analyzed" and st["stage_index"] == len(st["stages"])


def test_invalid_chain_rejected():
    bad = dict(CHAIN, versions=[dict(CHAIN["versions"][1])])  # الحلقة الأم غير موجودة
    assert client.post("/api/analyze", json=bad).status_code == 422


def test_failed_analysis_reported(monkeypatch):
    def boom():
        raise RuntimeError("provider down")

    monkeypatch.setattr(service, "llm_factory", boom)
    rep = client.post("/api/analyze", json=CHAIN).json()
    assert rep["status"] == "failed" and "provider down" in rep["error"]
    r = client.get(f"/report/{rep['id']}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/analyze/{rep['id']}"


def test_unknown_report_404():
    assert client.get("/api/report/nope").status_code == 404
    assert client.get("/report/nope").status_code == 404


def test_all_screens_render_with_disclaimer():
    rid = client.post("/api/analyze", json=CHAIN).json()["id"]
    for path in ["/", "/new", f"/analyze/{rid}", f"/report/{rid}", f"/review/{rid}", f"/seal/{rid}"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert DISCLAIMER in r.text, path
        assert 'dir="rtl"' in r.text


def test_report_page_colors_broken_link_and_highlights():
    rid = client.post("/api/analyze", json=CHAIN).json()["id"]
    html = client.get(f"/report/{rid}").text
    assert "🔴 لا تنشر" in html
    assert re.search(r"border-red-600 bg-red-50[^>]*>\s*<div>en-summary ⚠️", html)
    assert "ورث خللاً من حلقة سابقة" in html  # fr-translation
    assert '<mark class="mark-red">للمسافر</mark>' in html
    assert "راجع <b>2</b> جمل من أصل <b>2</b>" in html


def test_docs():
    assert client.get("/docs").status_code == 200


def test_review_alpine_state_not_inlined_in_attribute():
    # منع تكرار خطأ: JSON داخل x-data="..." يكسر السمة
    rid = client.post("/api/analyze", json=CHAIN).json()["id"]
    r = client.get(f"/review/{rid}").text
    assert 'x-data="reviewState()"' in r
