"""طبقة موحدة لاستدعاء النماذج اللغوية.

- المزوّد الافتراضي Anthropic، وأسماء النماذج من .env (انظر app/config.py).
- temperature=0 حين يقبلها النموذج. بعض النماذج الحديثة (مثل Sonnet 5.5) ترفض أي قيمة
  غير الافتراضية بخطأ 400، فنعيد الطلب بدونها ونتذكر ذلك للنموذج. الثبات حينها يأتي من الـcache.
- مخرجات JSON يُتحقق منها بـ Pydantic، مع إعادة محاولة واحدة عند فشل التحقق.
- cache في SQLite بمفتاح sha256(النموذج + التعليمات + المدخل).
- تسجيل tokens والزمن لكل استدعاء في جدول llm_calls.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, select

T = TypeVar("T", bound=BaseModel)


# ---------- الجداول ----------
class LLMCache(SQLModel, table=True):
    __tablename__ = "llm_cache"
    key: str = Field(primary_key=True)
    model: str
    response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMCall(SQLModel, table=True):
    __tablename__ = "llm_calls"
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str
    role: str
    purpose: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    ok: bool = True
    error: str = ""


# ---------- المزوّدون ----------
@dataclass
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMError(RuntimeError):
    pass


class Provider(Protocol):
    def generate(self, model: str, system: str, user: str, max_tokens: int) -> ProviderResponse: ...


class AnthropicProvider:
    """استدعاء Anthropic عبر الـSDK الرسمي."""

    def __init__(self, api_key: str, timeout: float = 120.0):
        import anthropic

        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY غير موجود في .env")
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._no_temperature: set[str] = set()

    def generate(self, model: str, system: str, user: str, max_tokens: int) -> ProviderResponse:
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if model not in self._no_temperature:
            try:
                # SDK 1.x أزال temperature من التوقيع، فنمررها عبر extra_body
                resp = self.client.messages.create(extra_body={"temperature": 0}, **kwargs)
            except self._anthropic.BadRequestError as e:
                if "temperature" not in str(e).lower():
                    raise
                self._no_temperature.add(model)
                resp = self.client.messages.create(**kwargs)
        else:
            resp = self.client.messages.create(**kwargs)

        if resp.stop_reason == "refusal":
            raise LLMError("رفض النموذج الطلب (stop_reason=refusal)")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return ProviderResponse(text, resp.usage.input_tokens, resp.usage.output_tokens)


# ---------- أدوات ----------
def cache_key(model: str, system: str, user: str) -> str:
    payload = json.dumps([model, system, user], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> str:
    """يستخرج كائن/مصفوفة JSON من رد قد يحيطه نص أو ``` ."""
    t = _FENCE.sub("", text.strip()).strip()
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        return t
    start = min(starts)
    end = max(t.rfind("}"), t.rfind("]"))
    return t[start : end + 1] if end > start else t[start:]


JSON_SYSTEM_SUFFIX = (
    "\n\nReturn ONLY a single valid JSON value that matches this JSON Schema. "
    "No prose, no markdown fences.\nSchema:\n{schema}"
)


# ---------- الواجهة الموحدة ----------
class LLM:
    def __init__(self, engine: Engine, provider: Provider, models: dict[str, str], max_tokens: int = 16000):
        self.engine = engine
        self.provider = provider
        self.models = models
        self.max_tokens = max_tokens

    def _model(self, role: str) -> str:
        m = self.models.get(role)
        if not m:
            raise LLMError(f"لا يوجد نموذج معرّف للدور '{role}' في .env")
        return m

    def _log(self, **kw) -> None:
        with Session(self.engine) as s:
            s.add(LLMCall(**kw))
            s.commit()

    def _call(self, user: str, system: str, role: str, purpose: str, use_cache: bool):
        """يعيد (النص، دالة تخزين أو None إن كان من الـcache)."""
        model = self._model(role)
        key = cache_key(model, system, user)
        if use_cache:
            with Session(self.engine) as s:
                hit = s.get(LLMCache, key)
            if hit:
                self._log(model=model, role=role, purpose=purpose, cached=True)
                return hit.response_text, None

        t0 = time.perf_counter()
        try:
            r = self.provider.generate(model, system, user, self.max_tokens)
        except Exception as e:
            self._log(model=model, role=role, purpose=purpose, ok=False, error=str(e)[:500],
                      latency_ms=int((time.perf_counter() - t0) * 1000))
            raise
        self._log(model=model, role=role, purpose=purpose, input_tokens=r.input_tokens,
                  output_tokens=r.output_tokens, latency_ms=int((time.perf_counter() - t0) * 1000))

        def store() -> None:
            with Session(self.engine) as s:
                s.merge(LLMCache(key=key, model=model, response_text=r.text,
                                 input_tokens=r.input_tokens, output_tokens=r.output_tokens))
                s.commit()

        return r.text, store

    def complete(self, user: str, system: str = "", role: str = "main", purpose: str = "",
                 use_cache: bool = True) -> str:
        """استدعاء نصي مع cache وتسجيل."""
        text, store = self._call(user, system, role, purpose, use_cache)
        if store and use_cache:
            store()
        return text

    def complete_json(self, user: str, schema: type[T], system: str = "", role: str = "main",
                      purpose: str = "") -> T:
        """استدعاء يعيد كائن Pydantic متحقَّقاً منه، مع إعادة محاولة واحدة عند فشل التحقق.

        لا يُخزَّن في الـcache إلا الرد الذي اجتاز التحقق.
        """
        sys_full = system + JSON_SYSTEM_SUFFIX.format(
            schema=json.dumps(schema.model_json_schema(), ensure_ascii=False))
        prompt = user
        last_err: Exception | None = None
        for _ in range(2):
            text, store = self._call(prompt, sys_full, role, purpose, use_cache=True)
            try:
                obj = schema.model_validate_json(extract_json(text))
            except (ValidationError, ValueError) as e:
                last_err = e
                prompt = (f"{user}\n\nYour previous answer was invalid:\n{text}\n\n"
                          f"Validation error:\n{e}\n\nReturn corrected JSON only.")
                continue
            if store:
                store()
            return obj
        raise LLMError(f"فشل التحقق من JSON بعد إعادة المحاولة: {last_err}")


def usage_summary(engine: Engine) -> dict:
    """ملخص tokens والزمن (لتقدير التكلفة في README)."""
    with Session(engine) as s:
        rows = s.exec(select(LLMCall)).all()
    live = [r for r in rows if not r.cached and r.ok]
    return {
        "calls": len(rows),
        "live_calls": len(live),
        "cache_hits": sum(r.cached for r in rows),
        "input_tokens": sum(r.input_tokens for r in live),
        "output_tokens": sum(r.output_tokens for r in live),
        "avg_latency_ms": int(sum(r.latency_ms for r in live) / len(live)) if live else 0,
    }


def get_llm() -> LLM:
    from app.config import get_settings
    from app.db import get_engine

    st = get_settings()
    if st.llm_provider != "anthropic":
        raise LLMError(f"مزوّد غير مدعوم: {st.llm_provider}")
    provider = AnthropicProvider(st.anthropic_api_key, st.llm_timeout_seconds)
    models = {r: st.model_for(r) for r in ("main", "witness_a", "witness_b")}
    return LLM(get_engine(), provider, models, st.llm_max_tokens)
