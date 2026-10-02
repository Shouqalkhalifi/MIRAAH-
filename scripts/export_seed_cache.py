"""يحلل الأمثلة الاصطناعية الجاهزة ويحفظ ردود النموذج التي استُخدمت فيها في data/seed/llm_cache.jsonl.

يُحمَّل الملف في الـcache عند تشغيل التطبيق (app/db.py)، فيعمل «جرّب مثالاً» فوراً وبلا تكلفة في النسخة المنشورة.
الملف لا يحوي إلا نصوص الأمثلة الاصطناعية وردود النموذج عليها: لا مفاتيح ولا بيانات مستخدمين.

التشغيل (يحتاج ANTHROPIC_API_KEY إن لم تكن الردود في الـcache المحلي):
    python scripts/export_seed_cache.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlmodel import Session  # noqa: E402

from app import service  # noqa: E402
from app.db import SEED_CACHE, get_engine  # noqa: E402
from app.examples import load_examples  # noqa: E402
from app.llm import LLM, LLMCache, cache_key  # noqa: E402


def main() -> None:
    used: list[str] = []
    original = LLM._call

    def recording(self, user, system, role, purpose, use_cache):
        used.append(cache_key(self._model(role), system, user))
        return original(self, user, system, role, purpose, use_cache)

    LLM._call = recording
    try:
        for ex in load_examples():
            report = service.create_report(ex.request)
            done = service.run_analysis(report.id)
            print(f"{ex.name}: {done.status.value} · {len(done.alerts)} تنبيهات · {len(set(used))} رداً حتى الآن")
    finally:
        LLM._call = original

    SEED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with Session(get_engine()) as s:
        for key in dict.fromkeys(used):
            hit = s.get(LLMCache, key)
            if hit:
                rows.append({"key": hit.key, "model": hit.model, "response_text": hit.response_text,
                             "input_tokens": hit.input_tokens, "output_tokens": hit.output_tokens})
    SEED_CACHE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"-> {SEED_CACHE.relative_to(ROOT)}: {len(rows)} رداً")


if __name__ == "__main__":
    main()
