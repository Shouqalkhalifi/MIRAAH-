"""اختبارات طبقة النماذج بمزوّد وهمي (بلا شبكة)، واختبار حي يُتخطّى إن غاب المفتاح."""
import os

import pytest
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import make_engine
from app.llm import LLM, LLMCall, LLMError, ProviderResponse, extract_json, usage_summary


class Answer(BaseModel):
    ok: bool
    n: int


class FakeProvider:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate(self, model, system, user, max_tokens):
        self.calls.append((model, system, user))
        return ProviderResponse(self.replies.pop(0), input_tokens=10, output_tokens=5)


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path / "t.db")


def make(engine, replies):
    p = FakeProvider(replies)
    return LLM(engine, p, {"main": "fake-model"}), p


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json('Here: {"a": [1]} done') == '{"a": [1]}'
    assert extract_json("[1, 2]") == "[1, 2]"


def test_complete_json_and_cache(engine):
    llm, p = make(engine, ['{"ok": true, "n": 3}'])
    assert llm.complete_json("q", Answer) == Answer(ok=True, n=3)
    # الاستدعاء الثاني من الـcache بلا مزوّد
    assert llm.complete_json("q", Answer) == Answer(ok=True, n=3)
    assert len(p.calls) == 1
    s = usage_summary(engine)
    assert s["live_calls"] == 1 and s["cache_hits"] == 1 and s["input_tokens"] == 10


def test_retry_once_on_invalid_json(engine):
    llm, p = make(engine, ["not json", '{"ok": false, "n": 1}'])
    assert llm.complete_json("q", Answer).n == 1
    assert len(p.calls) == 2
    assert "Validation error" in p.calls[1][2]


def test_invalid_reply_not_cached(engine):
    llm, p = make(engine, ['{"ok": 1}', '{"n": "x"}'])
    with pytest.raises(LLMError):
        llm.complete_json("q", Answer)
    llm2, p2 = make(engine, ['{"ok": true, "n": 2}'])
    assert llm2.complete_json("q", Answer).n == 2  # لم يُخزَّن الرد الفاسد
    assert len(p2.calls) == 1


def test_cache_key_depends_on_model(engine):
    p = FakeProvider(["a", "b"])
    LLM(engine, p, {"main": "m1"}).complete("q")
    LLM(engine, p, {"main": "m2"}).complete("q")
    assert len(p.calls) == 2


def test_failed_call_is_logged(engine):
    class Boom:
        def generate(self, *a):
            raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        LLM(engine, Boom(), {"main": "m"}).complete("q")
    with Session(engine) as s:
        row = s.exec(select(LLMCall)).one()
    assert not row.ok and "down" in row.error


def test_missing_model_role(engine):
    with pytest.raises(LLMError):
        LLM(engine, FakeProvider([]), {"main": ""}).complete("q")


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY") and not os.path.exists(".env"),
                    reason="لا يوجد ANTHROPIC_API_KEY")
def test_live_call():
    from app.config import get_settings
    from app.llm import get_llm

    if not get_settings().anthropic_api_key:
        pytest.skip("لا يوجد ANTHROPIC_API_KEY")
    llm = get_llm()
    out = llm.complete_json('Return {"ok": true, "n": 7}', Answer, purpose="pytest-live")
    assert out == Answer(ok=True, n=7)


def test_cache_can_be_disabled(engine):
    p = FakeProvider(['{"ok": true, "n": 1}', '{"ok": true, "n": 2}'])
    llm = LLM(engine, p, {"main": "m"}, cache_enabled=False)
    assert llm.complete_json("q", Answer).n == 1
    assert llm.complete_json("q", Answer).n == 2  # بلا cache: استدعاء جديد
    assert len(p.calls) == 2
