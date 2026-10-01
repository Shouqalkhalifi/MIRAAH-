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
from app.pipeline.fingerprint import SYSTEM_PRESENCE
from app.pipeline.revise import SYSTEM_REVISE

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
        elif system.startswith(SYSTEM_REVISE[:40]):
            reply = {"precise": "A traveler may break the fast in Ramadan.",
                     "balanced": "Travelers may break their fast in Ramadan.",
                     "clear": "Muslims can skip fasting in Ramadan."}
        elif system.startswith(SYSTEM_PRESENCE[:40]):
            version = user.split("VERSION", 1)[1].split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]
            hit = next((w for w in ("traveler", "voyageur") if w in version.lower()), None)
            reply = {"present": bool(hit), "quote": hit}
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
    for path in ["/", "/new", f"/analyze/{rid}", f"/report/{rid}", f"/review/{rid}"]:
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


def test_examples_valid_and_runnable():
    from app.examples import load_examples

    exs = load_examples()
    assert len(exs) == 3
    assert any(len(e.request.versions) == 3 for e in exs)
    r = client.post(f"/examples/{exs[0].name}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/analyze/")
    assert client.post("/examples/nope").status_code == 404
    assert "جرّب مثالاً" in client.get("/").text


# ---------- قرار المراجع والنشر ----------
def _analyzed():
    rep = client.post("/api/analyze", json=CHAIN).json()
    reds = [a["id"] for a in rep["alerts"] if a["severity"] == "red"]
    assert reds
    return rep, reds


def decide(rid, aid, **kw):
    body = {"report_id": rid, "alert_id": aid, "action": "accept", "reason": "الشرط ضروري", **kw}
    return client.post("/api/decision", json=body)


def test_reason_is_mandatory():
    rep, reds = _analyzed()
    assert decide(rep["id"], reds[0], reason="  ").status_code == 422
    assert decide(rep["id"], reds[0], reason="").status_code == 422


def test_edit_requires_text():
    rep, reds = _analyzed()
    assert decide(rep["id"], reds[0], action="edit").status_code == 422
    r = decide(rep["id"], reds[0], action="edit", edited_text="A traveler may break the fast.")
    assert r.status_code == 200 and r.json()["decisions"][reds[0]]["action"] == "edit"


def test_unknown_alert_rejected():
    rep, _ = _analyzed()
    assert decide(rep["id"], "nope").status_code == 404


def test_publish_locked_until_all_reds_decided_then_seal_and_audit():
    rep, reds = _analyzed()
    rid = rep["id"]
    assert client.post("/api/publish", json={"report_id": rid, "reviewer_role": "مترجم"}).status_code == 409
    assert client.get(f"/seal/{rid}").status_code == 404  # لا ختم قبل النشر
    for aid in reds:
        assert decide(rid, aid, reviewer_role="مترجم").status_code == 200
    r = client.post("/api/publish", json={"report_id": rid, "reviewer_role": "مترجم"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    # بعد النشر: القرارات مقفلة، والختم متاح، والسجل كامل
    assert decide(rid, reds[0]).status_code == 409
    seal = client.get(f"/seal/{rid}").text
    assert "مترجم" in seal and "قُبل التنبيه" in seal and DISCLAIMER in seal
    events = [e["event"] for e in client.get(f"/api/report/{rid}/audit").json()]
    assert events == ["decision"] * len(reds) + ["publish"]


def test_level_d_cannot_be_published():
    body = dict(CHAIN, source=dict(CHAIN["source"], content_level="D"))
    rep = client.post("/api/analyze", json=body).json()
    assert rep["referral"] is True
    for a in rep["alerts"]:
        if a["severity"] == "red":
            decide(rep["id"], a["id"])
    r = client.post("/api/publish", json={"report_id": rep["id"], "reviewer_role": "مترجم"})
    assert r.status_code == 409 and "مختص" in r.json()["detail"]


def test_revise_endpoint_self_checks_and_caches():
    rep, _ = _analyzed()
    cd = next(a for a in rep["alerts"] if a["type"] == "condition_dropped")
    r = client.post("/api/revise", json={"report_id": rep["id"], "alert_id": cd["id"]})
    assert r.status_code == 200, r.text
    assert [x["passed"] for x in r.json()] == [True, True, False]
    saved = client.get(f"/api/report/{rep['id']}").json()["revisions"][cd["id"]]
    assert len(saved) == 3
    assert client.post("/api/revise", json={"report_id": rep["id"], "alert_id": "nope"}).status_code == 404


def test_locks_end_to_end_and_validation():
    bad = dict(CHAIN, locks=[{"span_text": "غير موجود", "lock_type": "condition"}])
    assert client.post("/api/analyze", json=bad).status_code == 422
    body = dict(CHAIN, locks=[{"span_text": "للمسافر", "lock_type": "condition"}])
    rep = client.post("/api/analyze", json=body).json()
    lv = next(a for a in rep["alerts"] if a["type"] == "lock_violated")
    assert lv["introduced_at"] == "en-summary" and lv["propagated_to"] == ["fr-translation"]
    html = client.get(f"/report/{rep['id']}").text
    assert "🔓 «للمسافر» · شرط" in html


def test_suggest_locks_endpoint():
    r = client.post("/api/locks/suggest", json={"text": SOURCE, "lang": "ar"})
    assert r.status_code == 200
    spans = {l["span_text"]: l["lock_type"] for l in r.json()}
    assert spans.get("للمسافر") == "condition" and all(l["origin"] == "auto" for l in r.json())
