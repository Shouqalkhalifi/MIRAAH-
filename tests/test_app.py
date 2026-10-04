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
from app.pipeline.reader_exam import SYSTEM_ANSWER, SYSTEM_QUESTIONS

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
        elif system.startswith(SYSTEM_QUESTIONS[:40]):
            reply = {"questions": [{"question_ar": "لمن تجوز الرخصة؟", "options": ["للمسافر", "لكل المسلمين"]}]}
        elif system.startswith(SYSTEM_ANSWER[:40]):
            text = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0].lower()
            reply = {"answers": [1 if ("muslims" in text or "musulmans" in text) else 0]}
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
    monkeypatch.setattr(service, "llm_factory", lambda: LLM(
        get_engine(), RouterProvider(), {"main": "fake", "witness_a": "fake", "witness_b": "fake-b"}))


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
    assert "لا تنشر · سقط شرط" in html  # الحالة نص صريح بلغة المقابلة
    # خيط السند: ينكسر عند en-summary، وما بعده بعد الخلل
    assert re.search(r'class="st-break[^"]*"[^>]*>\s*<span class="knot"[^>]*></span>\s*<button[^>]*>\s*<span class="node-name">النسخة 2</span>', html)
    assert 'class="node-name" dir="ltr"' not in html  # أسماء الحلقات بالعربية لا بالتسمية التقنية
    assert 'class="st-after' in html  # fr-translation
    # الموضع مسطّر، وعلامة «سقط» مرتفعة عنده، والرمز التقني في التلميح فقط
    assert re.search(r'<mark class="mk mk-rubric" title="سقط الشرط «للمسافر» · condition_dropped">للمسافر</mark>', html)
    assert '<sup class="sigla tone-rubric">سقط</sup>' in html
    assert 'href="#alert-' in html and 'id="alert-' in html  # الموضع يقود إلى ملاحظته في الحاشية
    assert "<b title=\"condition_dropped\">سقط الشرط «للمسافر»</b>" in html  # الملاحظة مسمّاة بالمشكلة
    assert "أعراضه (" in html  # اتساع النطاق وامتحان القارئ مطويان تحتها
    assert "راجع <b>2</b> من <b>2</b> جملة" in html
    assert "🔴" not in html and "⚠️" not in html  # لا إيموجي في الواجهة


def test_docs():
    assert client.get("/docs").status_code == 200


def test_review_alpine_state_not_inlined_in_attribute():
    # منع تكرار خطأ: JSON داخل x-data="..." يكسر السمة
    rid = client.post("/api/analyze", json=CHAIN).json()["id"]
    r = client.get(f"/review/{rid}").text
    assert 'x-data="muqabala(' in r and 'x-data="{\n' not in r


def test_examples_valid_and_runnable():
    from app.examples import load_examples

    exs = load_examples()
    assert len(exs) == 4
    trav = next(e for e in exs if e.name == "traveler-fasting").request.versions
    assert len(trav) == 2 and trav[1].derived_from == trav[0].label  # الشرط يسقط في الحلقة الثانية
    life = next(e for e in exs if e.name == "content-lifecycle")
    assert [v.medium for v in life.request.versions] == ["translation", "summary", "social_post", "video_script",
                                                         "ai_answer"]
    assert all(v.medium for e in exs for v in e.request.versions)
    r = client.post(f"/examples/{exs[0].name}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/analyze/")
    assert client.post("/examples/nope").status_code == 404
    home = client.get("/").text
    assert "جرّب:" not in home
    new = client.get("/new").text
    assert "قابِل النص" in new and exs[0].title in new


# ---------- قرار المراجع والاعتماد والتصدير ----------
def _analyzed():
    rep = client.post("/api/analyze", json=CHAIN).json()
    reds = [a["id"] for a in rep["alerts"] if a["severity"] == "red"]
    assert reds
    return rep, reds


def decide(rid, aid, **kw):
    body = {"report_id": rid, "alert_id": aid, "action": "reject", "reason": "الشرط ضروري", **kw}
    return client.post("/api/decision", json=body)


def test_learned_english_answer_uses_the_sound_translation_only():
    rid = client.post("/api/analyze", json=CHAIN).json()["id"]
    r = client.post(f"/api/report/{rid}/learned", json={"text": CHAIN["versions"][0]["text"]}).json()
    assert r["verdict"] == "great" and "لم تجد فيها خللاً" in r["basis"]
    assert client.post(f"/api/report/{rid}/learned", json={"text": SOURCE}).json()["basis"] == ""
    bad = {**CHAIN, "versions": [{**CHAIN["versions"][1], "derived_from": "source"}]}
    rid = client.post("/api/analyze", json=bad).json()["id"]
    r = client.post(f"/api/report/{rid}/learned", json={"text": "A traveler may break the fast"}).json()
    assert r["verdict"] == "lang" and "بالعربية" in r["note"]


def test_reader_exam_can_be_rerun_on_the_corrected_text():
    rep, _ = _analyzed()
    rid = rep["id"]
    fix = next(a for a in rep["alerts"] if a["version_label"] == "en-summary" and a["severity"] == "red"
               and a["version_span"]["text"])
    assert client.post(f"/api/report/{rid}/reexam").json()["corrected"] == {}  # لا تصحيح بعد
    assert decide(rid, fix["id"], action="edit", reason="",
                  edited_text="A traveler may break the fast in Ramadan.").status_code == 200
    page = client.get(f"/report/{rid}").text
    assert "أعد الامتحان على النص المصحَّح" in page and "بعد التصحيح (كان" not in page

    exam = client.post(f"/api/report/{rid}/reexam").json()
    assert exam["answers"]["en-summary"] == [1]  # النسخة كما حُلّلت: «لكل المسلمين»
    assert exam["corrected"] == {"en-summary": [0]}  # بعد التصحيح: «للمسافر» كالأصل
    page = client.get(f"/report/{rid}").text
    assert "xr xr-same" in page and "قبل التصحيح: «" in page
    assert "أعد الامتحان على النص المصحَّح" not in page


def test_not_an_error_needs_a_reason():
    rep, reds = _analyzed()
    assert decide(rep["id"], reds[0], reason="  ").status_code == 422
    assert decide(rep["id"], reds[0], reason="").status_code == 422


def test_apply_fix_needs_no_reason_and_no_role():
    rep, reds = _analyzed()
    r = decide(rep["id"], reds[0], action="edit", reason="", edited_text="A traveler may break the fast.")
    assert r.status_code == 200
    d = r.json()["decisions"][reds[0]]
    assert d["action"] == "edit" and d["reason"] == "" and "reviewer_role" not in d


def test_edit_requires_text():
    rep, reds = _analyzed()
    assert decide(rep["id"], reds[0], action="edit").status_code == 422
    r = decide(rep["id"], reds[0], action="edit", edited_text="A traveler may break the fast.")
    assert r.status_code == 200 and r.json()["decisions"][reds[0]]["action"] == "edit"


def test_unknown_alert_rejected():
    rep, _ = _analyzed()
    assert decide(rep["id"], "nope").status_code == 404


EXPORT_TITLE = "تقرير مراجعة مِرآة – للمراجعة قبل النشر، وليس شهادة اعتماد"


def approve(rid):
    return client.post("/api/approve", json={"report_id": rid})


def test_approve_locked_until_all_reds_decided_then_export_and_audit():
    rep, reds = _analyzed()
    rid = rep["id"]
    assert approve(rid).status_code == 409
    # التقرير يُشارَك ويُنزَّل دائماً، وفيه حكم مِرآة؛ الاعتماد عبر الواجهة البرمجية اختياري
    early = client.get(f"/api/report/{rid}/export.json").json()
    assert early["verdict"]["tone"] == "rubric" and early["verdict"]["text"].startswith("لا تنشر")
    assert client.get(f"/api/report/{rid}/export.pdf").status_code == 200
    for aid in reds:
        assert decide(rid, aid).status_code == 200
    r = approve(rid)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # بعد الاعتماد: القرارات مقفلة، والتصدير متاح، والسجل كامل
    assert decide(rid, reds[0]).status_code == 409
    events = [e["event"] for e in client.get(f"/api/report/{rid}/audit").json()]
    assert events == ["decision"] * len(reds) + ["approve"]

    j = client.get(f"/api/report/{rid}/export.json")
    assert j.status_code == 200 and "attachment" in j.headers["content-disposition"]
    d = j.json()
    assert d["title"] == EXPORT_TITLE
    assert d["source"] == {"text": SOURCE, "lang": "ar", "source_ref": "اصطناعي", "content_level": "B"}
    assert [n["label"] for n in d["chain"]] == ["source", "en-translation", "en-summary", "fr-translation"]
    assert all(n["approved_text"] for n in d["chain"])
    assert "reviewer_role" not in d
    assert d["approved_at"].endswith("(بتوقيت الرياض)")
    decided = [a for a in d["alerts"] if a["decision"]]
    assert {a["id"] for a in decided} >= set(reds)
    assert all(a["decision"]["reason"] == "الشرط ضروري" and a["decision"]["action_ar"] == "ليس خطأ"
               for a in decided)

    h = client.get(f"/api/report/{rid}/export.html")
    assert h.status_code == 200 and "attachment" in h.headers["content-disposition"]
    html = h.text
    assert f"<title>{EXPORT_TITLE}</title>" in html and DISCLAIMER in html
    assert "اصطناعي" in html and "صفة المراجع" not in html and "بتوقيت الرياض" in html
    assert "ليس خطأ" in html and "السبب:" in html and "window.print()" in html
    assert html.index("حكم مِرآة") < html.index("<h2>المصدر</h2>") < html.index("حلقات السلسلة") < html.index("نص كل حلقة") \
        < html.index("<h2>التنبيهات</h2>")

    p = client.get(f"/api/report/{rid}/export.pdf")
    assert p.status_code == 200 and p.headers["content-type"] == "application/pdf"
    assert f'miraah-report-{rid}.pdf' in p.headers["content-disposition"]
    assert p.content.startswith(b"%PDF") and len(p.content) > 5000
    page = client.get(f"/report/{rid}").text
    assert "download('pdf')" in page and "share()" in page and "تقرير HTML" not in page


def test_riyadh_time_is_utc_plus_3():
    from datetime import datetime, timezone

    from app.export import riyadh_time

    assert riyadh_time(datetime(2026, 10, 2, 21, 30, tzinfo=timezone.utc)) == "2026-10-03 00:30 (بتوقيت الرياض)"


def test_level_d_can_never_be_approved():
    body = dict(CHAIN, source=dict(CHAIN["source"], content_level="D"))
    rep = client.post("/api/analyze", json=body).json()
    assert rep["referral"] is True
    for a in rep["alerts"]:
        if a["severity"] == "red":
            decide(rep["id"], a["id"])
    r = approve(rep["id"])
    assert r.status_code == 409 and "مختص" in r.json()["detail"]
    d = client.get(f"/api/report/{rep['id']}/export.json").json()
    assert d["verdict"]["tone"] == "rubric" and "مختص" in d["verdict"]["text"]  # التقرير يقول بوضوح: يُحال


def test_seal_is_gone():
    rep, _ = _analyzed()
    assert client.get(f"/seal/{rep['id']}").status_code == 404
    assert client.post("/api/publish", json={"report_id": rep["id"], "reviewer_role": "مترجم"}).status_code == 404
    html = client.get(f"/report/{rep['id']}").text
    assert "/seal/" not in html and "اختِم" not in html and "شارك التقرير" in html
    assert "ختم" not in client.get("/").text


def test_legacy_published_report_loads_as_approved():
    from app.models import Report, ReportStatus

    r = Report.model_validate({"source": {"text": "نص"}, "status": "published",
                               "published_at": "2026-10-01T00:00:00Z"})
    assert r.status == ReportStatus.approved and r.approved_at is not None


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
    assert re.search(r'<span class="tag tone-rubric">انكسر</span>\s*«للمسافر» · قفل شرط', html)


def test_locks_are_rechecked_on_the_corrected_text():
    body = dict(CHAIN, locks=[{"span_text": "للمسافر", "lock_type": "condition"}])
    rep = client.post("/api/analyze", json=body).json()
    rid = rep["id"]
    fix = next(a for a in rep["alerts"] if a["version_label"] == "en-summary" and a["severity"] == "red"
               and a["version_span"]["text"])
    assert decide(rid, fix["id"], action="edit", reason="",
                  edited_text="A traveler may break the fast in Ramadan.").status_code == 200
    html = client.get(f"/report/{rid}").text
    assert "أعد فحص الأقفال على النص المصحَّح" in html

    client.post(f"/api/report/{rid}/reexam")
    saved = client.get(f"/api/report/{rid}").json()["locks_corrected"]
    assert saved["en-summary"]["still_broken"] == []
    html = client.get(f"/report/{rid}").text
    assert re.search(r'<span class="tag tone-verified">حُفظ بعد التصحيح</span>\s*«للمسافر»', html)
    assert "أعد فحص الأقفال على النص المصحَّح" not in html

    assert decide(rid, fix["id"], action="edit", reason="", edited_text="Muslims may break the fast.").status_code == 200
    client.post(f"/api/report/{rid}/reexam")
    html = client.get(f"/report/{rid}").text
    assert re.search(r'<span class="tag tone-rubric">ما زال منكسراً بعد التصحيح</span>\s*«للمسافر»', html)


def test_suggest_locks_endpoint():
    r = client.post("/api/locks/suggest", json={"text": SOURCE, "lang": "ar"})
    assert r.status_code == 200
    spans = {l["span_text"]: l["lock_type"] for l in r.json()}
    assert spans.get("للمسافر") == "condition" and all(l["origin"] == "auto" for l in r.json())


def test_reader_exam_end_to_end():
    rep = client.post("/api/analyze", json=CHAIN).json()
    assert rep["warnings"] == []
    rd = next(a for a in rep["alerts"] if a["type"] == "reader_divergence")
    assert rd["introduced_at"] == "en-summary" and rd["propagated_to"] == ["fr-translation"]
    assert "امتحان القارئ" in client.get(f"/report/{rep['id']}").text


def test_optional_stage_failure_becomes_warning_not_failure(monkeypatch):
    from app.pipeline import reader_exam

    def boom(*a):
        raise RuntimeError("x")

    monkeypatch.setattr(reader_exam, "run_exam", boom)
    rep = client.post("/api/analyze", json=CHAIN).json()
    assert rep["status"] == "analyzed" and any("امتحان القارئ" in w for w in rep["warnings"])


def test_two_witnesses_reported():
    rep = client.post("/api/analyze", json=CHAIN).json()
    w = rep["witnesses"]
    assert w["enabled"] and w["model_b"] == "fake-b" and w["agreement"] == 1.0
    assert "اتفاق الشاهدين" in client.get(f"/report/{rep['id']}").text


def test_review_page_renders_after_revisions_and_decisions():
    # منع تكرار خطأ: «Object of type Revision is not JSON serializable» في صفحة المراجعة
    rep, reds = _analyzed()
    cd = next(a for a in rep["alerts"] if a["type"] == "condition_dropped")
    assert client.post("/api/revise", json={"report_id": rep["id"], "alert_id": cd["id"]}).status_code == 200
    assert decide(rep["id"], reds[0]).status_code == 200
    r = client.get(f"/review/{rep['id']}")
    assert r.status_code == 200
    assert "A traveler may break the fast in Ramadan." in r.text  # الصياغة المحفوظة
    assert json.dumps("الشرط ضروري")[1:-1] in r.text  # القرار المحفوظ (tojson يهرّب الحروف العربية)


def test_reason_must_not_be_the_edited_wording_and_export_shows_both():
    rep, reds = _analyzed()
    wording = "A traveler may break the fast in Ramadan."
    r = decide(rep["id"], reds[0], action="edit", edited_text=wording, reason=wording)
    assert r.status_code == 422 and "سبب القرار" in r.text
    for aid in reds:
        assert decide(rep["id"], aid, action="edit", edited_text=wording, reason="أسقط الملخص شرط السفر").status_code == 200
    assert approve(rep["id"]).status_code == 200
    html = client.get(f"/api/report/{rep['id']}/export.html").text
    assert "الصياغة المعتمدة:" in html and wording in html and "أسقط الملخص شرط السفر" in html
    d = client.get(f"/api/report/{rep['id']}/export.json").json()
    assert d["chain"][0]["approved_text"] == SOURCE  # الأصل لا يُعدَّل أبداً
    summary = next(n for n in d["chain"] if n["label"] == "en-summary")
    assert summary["applied_edits"] and summary["approved_text"].startswith(wording)


def test_provider_errors_get_a_clear_arabic_message(monkeypatch):
    from app.service import friendly_error

    class BadRequestError(Exception):
        pass

    msg = friendly_error(BadRequestError("Error code: 400 - Your credit balance is too low to access the Anthropic API"))
    assert msg.startswith("نفد رصيد خدمة النموذج اللغوي") and "التفاصيل التقنية: BadRequestError" in msg
    assert friendly_error(RuntimeError("boom")).startswith("حدث خطأ غير متوقع")

    def no_credit():
        raise BadRequestError("Your credit balance is too low to access the Anthropic API")

    monkeypatch.setattr(service, "llm_factory", no_credit)
    rep = client.post("/api/analyze", json=CHAIN).json()
    assert rep["status"] == "failed" and rep["error"].startswith("نفد رصيد")


def test_favicon_served():
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.headers["content-type"] == "image/x-icon"
    assert r.content[:4] == b"\x00\x00\x01\x00"  # ترويسة ICO
    assert client.get("/static/favicon.svg").status_code == 200
    assert 'rel="icon" href="/static/favicon.svg"' in client.get("/").text


def test_export_records_rejected_red_alerts_with_reason():
    rep, reds = _analyzed()
    for aid in reds:
        assert decide(rep["id"], aid, action="reject", reason="رأيتُه إنذاراً خاطئاً").status_code == 200
    assert approve(rep["id"]).status_code == 200
    html = client.get(f"/api/report/{rep['id']}/export.html").text
    assert "ليس خطأ" in html and "رأيتُه إنذاراً خاطئاً" in html


def test_report_page_is_review_only_with_share_and_pdf():
    rep, _ = _analyzed()
    html = client.get(f"/report/{rep['id']}").text
    assert "اعرض صياغة مقترحة" in html and "لا تُطبَّق على النص" in html
    assert "شارك التقرير" in html and "نزّل PDF" in html
    for gone in ("طبّق التصحيح", "ليس خطأ", "/api/decision", "/api/approve", "صدّر التقرير",
                 "صفتك", "خلل حقيقي", "إنذار خاطئ", "أصلحه الآن", "اعتمِد وصدّر", "export.json"):
        assert gone not in html, gone

