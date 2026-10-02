"""ما يخص النسخة المنشورة: حدّ معدل الطلبات، و cache الأمثلة المحفوظ في المستودع."""
import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import ratelimit, service
from app.db import SEED_CACHE, make_engine
from app.examples import load_examples
from app.llm import LLMCache, load_seed
from app.main import app

client = TestClient(app)


def test_rate_limit_per_ip(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "2")
    ratelimit.reset()
    body = {"text": "", "lang": "ar"}  # 422 بعد اجتياز الحد: لا استدعاء للنموذج
    assert client.post("/api/locks/suggest", json=body).status_code == 422
    assert client.post("/api/locks/suggest", json=body).status_code == 422
    r = client.post("/api/locks/suggest", json=body)
    assert r.status_code == 429 and "حدّ الاستخدام" in r.json()["detail"]
    # عنوان آخر خلف الوكيل له حدّه المستقل
    assert client.post("/api/locks/suggest", json=body, headers={"x-forwarded-for": "10.0.0.9"}).status_code == 422
    # صفحة القارئ تعرض الرسالة بدل خطأ JSON
    page = client.post("/reverse", data={"text": "عبارة قرأتها"}).text
    assert "حدّ الاستخدام" in page
    # الأمثلة الجاهزة لا تُحتسب (من الـcache)
    monkeypatch.setattr(service, "run_analysis", lambda rid: None)
    assert client.post(f"/examples/{load_examples()[0].name}", follow_redirects=False).status_code == 303
    ratelimit.reset()


def test_rate_limit_off_by_zero(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "0")
    assert all(ratelimit.allow("x") for _ in range(100))


def test_seed_cache_is_loaded_without_overwriting(tmp_path):
    seed = tmp_path / "seed.jsonl"
    seed.write_text(json.dumps({"key": "k1", "model": "m", "response_text": "{}"}) + "\n"
                    + json.dumps({"key": "k2", "model": "m", "response_text": "new"}) + "\n", encoding="utf-8")
    engine = make_engine(tmp_path / "t.db")
    with Session(engine) as s:
        s.add(LLMCache(key="k2", model="m", response_text="old"))
        s.commit()
    assert load_seed(engine, seed) == 1
    assert load_seed(engine, seed) == 0
    with Session(engine) as s:
        assert s.get(LLMCache, "k2").response_text == "old"
        assert s.get(LLMCache, "k1") is not None


def test_shipped_seed_has_only_cache_rows():
    rows = [json.loads(line) for line in SEED_CACHE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows and all(set(r) == {"key", "model", "response_text", "input_tokens", "output_tokens"} for r in rows)
    assert not any("sk-ant" in r["response_text"] for r in rows)
