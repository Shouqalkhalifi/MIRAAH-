"""«قابِل ما قرأت» عبر الواجهة البرمجية والصفحة، مع الخصوصية: لا يُحفظ نص المستخدم إلا باختياره."""
import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import service
from app.db import get_engine
from app.llm import LLM, LLMCache, ProviderResponse
from app.main import app
from app.models import ReverseRow
from app.pipeline import reverse as rv
from tests.test_reverse import ISSUES, FakeLLM

client = TestClient(app)
SECRET = "Zorblat is forbidden, wrote my-unique-marker-7781."


class FakeProvider:
    """مزوّد وهمي خلف طبقة LLM الحقيقية (بالـcache وسجل الاستدعاءات)، لاختبار الخصوصية فعلياً."""

    def __init__(self):
        self.fake = FakeLLM()

    def generate(self, model, system, user, max_tokens):
        return ProviderResponse(json.dumps(self.fake.reply(system, user), ensure_ascii=False), 10, 5)


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    monkeypatch.setattr(rv, "default_library", lambda: ISSUES)
    monkeypatch.setattr(service, "llm_factory", lambda: LLM(
        get_engine(), FakeProvider(), {"main": "fake", "witness_a": "fake", "witness_b": "fake-b"}))


def saved_rows():
    with Session(get_engine()) as s:
        return s.exec(select(ReverseRow)).all()


def test_api_reverse_returns_verdict():
    r = client.post("/api/reverse", json={"text": "Zorblat is forbidden."})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "contradicts" and body["issue"]["id"] == "I01" and body["id"] is None
    assert body["elapsed_ms"] >= 0


def test_api_reverse_length_limits():
    assert client.post("/api/reverse", json={"text": "ab"}).status_code == 422
    assert client.post("/api/reverse", json={"text": "x" * 1001}).status_code == 422


def test_privacy_text_not_stored_unless_saved():
    before_rows = len(saved_rows())
    r = client.post("/api/reverse", json={"text": SECRET}).json()
    assert r["id"] is None and len(saved_rows()) == before_rows
    # ولا يدخل cache الاستجابات (الـcache معطّل لهذه الميزة)
    with Session(get_engine()) as s:
        keys_before = {c.key for c in s.exec(select(LLMCache)).all()}
    client.post("/api/reverse", json={"text": SECRET})
    with Session(get_engine()) as s:
        keys_after = {c.key for c in s.exec(select(LLMCache)).all()}
    assert keys_after == keys_before


def test_saved_reverse_gets_permalink():
    r = client.post("/api/reverse", json={"text": "Zorblat is forbidden.", "save": True}).json()
    assert r["id"]
    page = client.get(f"/reverse/{r['id']}")
    assert page.status_code == 200 and "متعارض مع المصدر" in page.text
    assert client.get("/reverse/nope").status_code == 404


def test_reverse_page_form_flow():
    page = client.get("/reverse")
    assert page.status_code == 200 and 'action="/reverse"' in page.text and "<h1>تحقّق مما قرأت</h1>" in page.text
    res = client.post("/reverse", data={"text": "Zorblat is obligatory for everyone."})
    assert res.status_code == 200
    html = res.text
    assert "مِرآة تعرض المصادر وتقابلها، ولا تُصدر فتوى" in html
    assert "مطابق جزئياً" in html and "لم يُحفظ نصك" in html
    # خدمة القارئ: الحكم ثم «هكذا يقول المصدر» ثم «لماذا هذا الحكم؟» ثم ما قرأه، بلا أي زر تعديل أو تصدير
    assert html.index("rv-verdict") < html.index("هكذا يقول المصدر") < html.index("لماذا هذا الحكم؟") < html.index("ما قرأتَه")
    assert "طبّق التصحيح" not in html and "/api/decision" not in html and "صدّر" not in html
    assert "أنت في <b>تحقّق مما قرأت</b>" in html and 'href="/new"' in html  # سطر الخدمة، وجسر إلى خدمة الناشر
    assert "نص تجريبي (أ)" in html  # الأصل الحرفي معروض
    assert "مسألة تجريبية غير مراجعة" in html  # لافتة المسألة الوهمية
    saved = client.post("/reverse", data={"text": "Zorblat is forbidden.", "save": "1"}, follow_redirects=False)
    assert saved.status_code == 303 and saved.headers["location"].startswith("/reverse/")


def test_reverse_page_personal_request_and_validation():
    html = client.post("/reverse", data={"text": "I live in X, can I skip zorblat?"}).text
    assert "مِرآة لا تجيب عن حالات شخصية ولا تُصدر فتوى" in html
    assert "اكتب ما قرأته أو سؤالك" in client.post("/reverse", data={"text": "a"}).text


def test_home_offers_both_services_and_section_nav():
    html = client.get("/").text
    assert "تحقّق من مصدرها" in html and "قابِلها بمصدرها" not in html
    assert 'action="/reverse"' in html and 'href="/new"' in html
    assert ">راجِع قبل النشر</a>" in html and "حلّل بمِرآة" not in html
    nav = re.search(r'<nav class="topnav".*?</nav>', html, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', nav) == ["/", "/#about", "/#features", "/#how", "/#app", "/#faq", "/docs"]
    for anchor in ("about", "features", "how", "app", "faq"):
        assert f'id="{anchor}"' in html
    assert 'class="phone"' in html and "الاعتكاف سنة للرجال والنساء" in html
    assert "أنت في" not in html  # الرئيسية خارج الخدمتين
    r = client.get("/about", follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"] == "/#about"
    assert "أنت في <b>راجِع قبل النشر</b>" in client.get("/new").text
