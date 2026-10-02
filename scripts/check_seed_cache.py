"""يتحقق أن الأمثلة الجاهزة تُحلَّل كاملة من data/seed/llm_cache.jsonl وحده، بلا مفتاح API وفي قاعدة جديدة.

    python scripts/check_seed_cache.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "seed-check.db")
os.environ["ANTHROPIC_API_KEY"] = "sk-no-network"  # أي استدعاء حي سيفشل، فيظهر فوراً

from app import service  # noqa: E402
from app.examples import load_examples  # noqa: E402


def main() -> int:
    bad = 0
    for ex in load_examples():
        r = service.run_analysis(service.create_report(ex.request).id)
        ok = r.status.value == "analyzed" and not r.warnings
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {ex.name}: {r.status.value} · {len(r.alerts)} تنبيهات · {r.warnings or r.error or ''}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
