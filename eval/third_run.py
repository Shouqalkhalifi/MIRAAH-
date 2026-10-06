"""يكمل تقييم 5 أكتوبر بتشغيل ثالث حيّ على الكود النهائي، ويكتب eval/results.md من التشغيلات الثلاثة.

في 5 أكتوبر اكتمل تشغيلان على الحالات الـ47 وتوقف الثالث لنفاد رصيد Anthropic (eval/results_oct5_runs.json).
بعدهما تغيّر في الكود شيئان فقط:
  1. الميزان (b72cddc): التطابق الجزئي يشترط تقارب الكلمات. الميزان قواعد حتمية بلا نموذج، فتُعاد تنبيهاته
     للتشغيلين الأولين من نص الحالة نفسه بالكود النهائي، وتبقى بقية تنبيهاتهما (من ردود النموذج) كما سُجّلت.
  2. حالة الامتناع a04 استُبدلت (6be32d6)، فنتيجتاها في التشغيلين الأولين لنص آخر وتُستبعدان منهما.
ثم يُشغَّل التشغيل الثالث حيّاً بلا cache على الكود النهائي.

    python eval/third_run.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import run_eval  # noqa: E402
from app.models import Report, Source, Version  # noqa: E402
from app.pipeline import mizan  # noqa: E402

OCT5 = ROOT / "eval" / "results_oct5_runs.json"
MIZAN_TYPES = {"unverified_attribution", "source_conflict", "quote_wording_differs", "madhhab_unverified"}


def mizan_now(case: dict) -> tuple[set[str], list[str]]:
    """تنبيهات الميزان ونتائج تحققه لنص الحالة بالكود النهائي (بلا نموذج)."""
    rep = Report(title=case["id"], source=Source(text=case["source"], lang="ar", content_level=case["level"]),
                 versions=[Version(label="v", lang="en", text=case["version"])])
    verifs, alerts = mizan.check_report(rep)
    return ({a.type.value for a in alerts if a.severity.value in ("red", "yellow")}, [v.status for v in verifs])


def refresh(old_run: dict, cases: list[dict], old_cases: dict) -> dict:
    out = {}
    for c in cases:
        r = dict(old_run[c["id"]])
        if old_cases[c["id"]]["version"] != c["version"] or old_cases[c["id"]]["source"] != c["source"]:
            r.update(status="replaced_case", warnings=["الحالة استُبدلت بعد هذا التشغيل"])
        elif run_eval.valid(r):
            types, verifs = mizan_now(c)
            r["predicted"] = sorted((set(r["predicted"]) - MIZAN_TYPES) | types)
            r["verifications"] = verifs
        out[c["id"]] = r
    return out


def main() -> None:
    cases = run_eval.load_cases(None)
    old =json.loads(OCT5.read_text(encoding="utf-8"))
    old_cases = {c["id"]: c for c in old["cases"]}
    runs = [refresh(old["runs"][0], cases, old_cases), refresh(old["runs"][1], cases, old_cases)]
    start = datetime.now(timezone.utc)
    third = run_eval.run_once(cases, use_cache=False, workers=4)
    bad = [cid for cid, r in third.items() if not run_eval.valid(r)]
    print(f"third run: {len(cases)} cases, invalid: {bad}")
    runs.append(third)
    run_eval.write_results(cases, runs, run_eval.cost_since(start), start, first_run_cached=True)
    print("-> eval/results.md")


if __name__ == "__main__":
    main()
