"""يشغّل مِرآة على حالات التقييم ويكتب eval/results.md (CLAUDE.md القسم 9).

التشغيل:
    python eval/run_eval.py --runs 1          # تقييم أولي
    python eval/run_eval.py --runs 3          # التقييم الكامل (التشغيلان 2 و3 بلا cache لقياس الثبات)
    python eval/run_eval.py --from-json       # إعادة حساب results.md من results.json بلا أي استدعاء

يقيس: الاستدعاء والدقة لكل نوع تغيّر، ونسبة الإنذارات الكاذبة على الحالات السليمة، وصحة الامتناع، والثبات
عبر التشغيلات، ونسبة اتفاق الشاهدين، والتكلفة والزمن لكل جملة، ومقارنة بخط أساس أبسط (chrF ونسبة الطول).
الحالات التي تعذّر تحليلها كاملاً (فشل أو مرحلة متعذّرة) تُستبعد من القياس وتُذكر صراحة.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_PATH", str(ROOT / "data" / "runtime" / "eval.db"))  # قاعدة منفصلة عن التطبيق

import sacrebleu  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app import service  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.llm import LLMCall, get_llm  # noqa: E402
from app.models import Source, Version  # noqa: E402
from app.service import AnalyzeRequest  # noqa: E402
from app.text.normalize import tokens  # noqa: E402

CASES = ROOT / "data" / "eval" / "cases.jsonl"
OUT_MD = ROOT / "eval" / "results.md"
OUT_JSON = ROOT / "eval" / "results.json"

# الأنواع التي تُقاس (المزروعة)؛ والأنواع السياقية لا تُحتسب إنذاراً كاذباً لنوع آخر
SCORED = {
    "condition_dropped", "exception_dropped", "certainty_raised", "attribution_upgraded", "new_prophetic_attribution",
    "ruling_shift", "scope_widened", "scope_narrowed", "hasr_lost", "consensus_inflated", "hadith_grade_dropped",
    "negation_mismatch", "number_mismatch", "term_narrowing", "unverified_attribution", "source_conflict",
    "quote_wording_differs",
}

# تنبيهات مصاحبة مقبولة لتغيّر مزروع (التغيير الواحد قد يكسر أكثر من ثابت فعلاً)
ALLOWED = {
    "condition_dropped": {"scope_widened", "scope_narrowed", "exception_dropped"},
    "exception_dropped": {"scope_widened", "condition_dropped"},
    "scope_widened": {"condition_dropped", "exception_dropped"},
    "scope_narrowed": {"condition_dropped"},
    "certainty_raised": {"attribution_upgraded"},
    "attribution_upgraded": {"certainty_raised", "new_prophetic_attribution", "unverified_attribution"},
    "new_prophetic_attribution": {"unverified_attribution", "attribution_upgraded", "quote_wording_differs", "source_conflict"},
    "ruling_shift": {"term_narrowing", "negation_mismatch", "certainty_raised"},
    "term_narrowing": {"ruling_shift"},
    "negation_mismatch": {"ruling_shift", "hasr_lost", "scope_widened"},
    "number_mismatch": set(),
    "hasr_lost": {"scope_widened"},
    "consensus_inflated": {"certainty_raised", "scope_widened"},
    "hadith_grade_dropped": {"certainty_raised"},
    "unverified_attribution": {"new_prophetic_attribution", "attribution_upgraded", "quote_wording_differs", "source_conflict"},
}

# أسعار تقريبية لكل مليون token (إدخال، إخراج) بالدولار — من وثائق Anthropic وقت الكتابة
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0), "claude-opus-5-5": (4.0, 20.0)}


def load_cases(limit: int | None) -> list[dict]:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    return cases[:limit] if limit else cases


def analyze_case(case: dict) -> dict:
    t0 = time.perf_counter()
    req = AnalyzeRequest(title=case["id"],
                         source=Source(text=case["source"], lang="ar", content_level=case["level"]),
                         versions=[Version(label="v", lang="en", text=case["version"])])
    report = service.run_analysis(service.create_report(req).id)
    alerts = [a for a in report.alerts if a.severity.value in ("red", "yellow")]
    return {
        "id": case["id"], "status": report.status.value, "error": report.error, "warnings": report.warnings,
        "predicted": sorted({a.type.value for a in alerts}),
        "verifications": [v.status for v in report.verifications],
        "fixed_phrase_ok": all("مكذوب" not in a.explanation_ar for a in report.alerts),
        "witness_agreement": report.witnesses.agreement,
        "seconds": round(time.perf_counter() - t0, 2),
    }


def run_once(cases: list[dict], use_cache: bool, workers: int) -> dict[str, dict]:
    llm = get_llm()
    llm.cache_enabled = use_cache
    service.llm_factory = lambda: llm
    with ThreadPoolExecutor(workers) as ex:
        return {r["id"]: r for r in ex.map(analyze_case, cases)}


# ---------- المقاييس ----------
def valid(r: dict) -> bool:
    """حالة صالحة للقياس: اكتمل تحليلها بلا مراحل متعذّرة (مثل نفاد الرصيد أثناء التشغيل)."""
    return r["status"] == "analyzed" and not r.get("warnings")


def allowed_for(c: dict) -> set[str]:
    exp = set(c["expected"])
    return exp | set().union(*(ALLOWED.get(e, set()) for e in exp)) if exp else set()


def per_type_metrics(pairs: list[tuple[dict, dict]]) -> dict[str, dict]:
    """pairs = [(الحالة، نتيجتها في تشغيل ما)] مجمّعة عبر كل التشغيلات الصالحة."""
    m = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0, "support": 0})
    for c, r in pairs:
        pred = set(r["predicted"]) & SCORED
        for e in c["expected"]:
            m[e]["support"] += 1
            m[e]["tp" if e in pred else "fn"] += 1
        for p in pred - allowed_for(c):
            m[p]["fp"] += 1
    out = {}
    for t, v in sorted(m.items()):
        rec = v["tp"] / v["support"] if v["support"] else None
        prec = v["tp"] / (v["tp"] + v["fp"]) if (v["tp"] + v["fp"]) else None
        out[t] = {**v, "recall": rec, "precision": prec}
    return out


def baseline(cases: list[dict]) -> dict[str, dict]:
    """خط أساس أبسط: chrF بين النسخة والترجمة المرجعية الأمينة، ونسبة الطول."""
    out = {}
    for c in cases:
        chrf = sacrebleu.sentence_chrf(c["version"], [c["reference_en"]]).score
        ratio = len(tokens(c["version"])) / max(1, len(tokens(c["reference_en"])))
        out[c["id"]] = {"chrf": round(chrf, 1), "len_ratio": round(ratio, 2), "flagged": chrf < 50 or ratio < 0.65}
    return out


def cost_since(start: datetime) -> dict:
    with Session(get_engine()) as s:
        rows = s.exec(select(LLMCall).where(LLMCall.ts >= start)).all()
    live = [r for r in rows if r.ok and not r.cached]
    by_model = defaultdict(lambda: [0, 0, 0])
    for r in live:
        b = by_model[r.model]
        b[0] += r.input_tokens
        b[1] += r.output_tokens
        b[2] += 1
    usd = sum(i / 1e6 * PRICES.get(mdl, (0, 0))[0] + o / 1e6 * PRICES.get(mdl, (0, 0))[1]
              for mdl, (i, o, _) in by_model.items())
    errors = sorted({(r.error or "")[:140] for r in rows if not r.ok})
    return {"calls": len(rows), "live_calls": len(live), "cache_hits": sum(r.cached for r in rows),
            "failed_calls": sum(not r.ok for r in rows), "errors": errors, "by_model": dict(by_model),
            "usd": round(usd, 4)}


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}٪"


def spread(values: list) -> str:
    """المتوسط (الأدنى–الأعلى) عبر التشغيلات."""
    vals = [v for v in values if v is not None]
    if not vals:
        return "—"
    if min(vals) == max(vals):
        return pct(vals[0])
    return f"{pct(statistics.mean(vals))} ({pct(min(vals))}–{pct(max(vals))})"


def rate(items: list[bool]):
    return sum(items) / len(items) if items else None


def write_results(cases: list[dict], runs: list[dict], cost: dict, start: datetime, first_run_cached: bool) -> None:
    mut = [c for c in cases if c["kind"] == "mutation"]
    fai = [c for c in cases if c["kind"] == "faithful"]
    abst = [c for c in cases if c["kind"] == "abstention"]

    def detected(c, r):
        return bool(set(r["predicted"]) & allowed_for(c))

    def per_run(group, fn):
        return [rate([fn(c, run[c["id"]]) for c in group if valid(run[c["id"]])]) for run in runs]

    mut_recall = per_run(mut, detected)
    fa_scored = per_run(fai, lambda c, r: bool(set(r["predicted"]) & SCORED))
    fa_any = per_run(fai, lambda c, r: bool(r["predicted"]))
    abst_ok = per_run(abst, lambda c, r: bool(r["verifications"]) and r["fixed_phrase_ok"]
                      and all(v == "unverified" for v in r["verifications"]))
    metrics = per_type_metrics([(c, run[c["id"]]) for run in runs for c in cases if valid(run[c["id"]])])
    degraded = [(i + 1, cid, r["status"], r.get("warnings") or [r.get("error", "")])
                for i, run in enumerate(runs) for cid, r in run.items() if not valid(r)]

    stability = None
    if len(runs) > 1:
        stable_set = [c for c in cases if all(valid(run[c["id"]]) for run in runs)]
        stability = rate([len({tuple(sorted(set(run[c["id"]]["predicted"]) & SCORED)) for run in runs}) == 1
                          for c in stable_set])
    agreements = [r["witness_agreement"] for run in runs for r in run.values()
                  if r["witness_agreement"] is not None and valid(r)]
    live_runs = runs[1:] if first_run_cached and len(runs) > 1 else runs
    secs = [r["seconds"] for run in live_runs for r in run.values() if valid(r)]
    n_live = len(cases) * len(live_runs)
    usd_per_1000 = cost["usd"] / n_live * 1000 if n_live else 0

    base = baseline(cases)
    chrf_mut = statistics.mean(base[c["id"]]["chrf"] for c in mut) if mut else 0
    chrf_fai = statistics.mean(base[c["id"]]["chrf"] for c in fai) if fai else 0

    L = ["# نتائج التقييم — مِرآة", "",
         f"- التاريخ: {start.strftime('%Y-%m-%d %H:%M UTC')} · الحالات: {len(cases)} "
         f"(تغيّر مزروع {len(mut)} · سليمة المعنى {len(fai)} · امتناع {len(abst)}) · التشغيلات: {len(runs)}",
         f"- النماذج: الشاهد الأول `{os.getenv('WITNESS_A_MODEL') or os.getenv('MAIN_MODEL')}`، "
         f"الشاهد الثاني `{os.getenv('WITNESS_B_MODEL') or '—'}`",
         "- البذور **مسودة لم تراجعها المطوّرة بعد**، والحالات مولّدة آلياً: الأرقام أولية وتُقرأ مع قسم الحدود.",
         "- الأرقام بصيغة «المتوسط (الأدنى–الأعلى)» عبر التشغيلات؛ والحالات المتأثرة بأعطال مستبعدة ومذكورة أدناه.",
         "", "## ملخص", "",
         "| المقياس | مِرآة | خط الأساس (chrF < 50 أو الطول < 65٪) |", "|---|---|---|",
         f"| كشف التغيّر المزروع (أي تنبيه مطابق) | {spread(mut_recall)} | {pct(rate([base[c['id']]['flagged'] for c in mut]))} |",
         f"| إنذارات كاذبة على الصياغات السليمة (الأنواع المقيسة) | {spread(fa_scored)} | {pct(rate([base[c['id']]['flagged'] for c in fai]))} |",
         f"| إنذارات كاذبة على السليمة (أي تنبيه أحمر/أصفر، مع امتحان القارئ) | {spread(fa_any)} | — |",
         f"| صحة الامتناع («غير متحقق» + العبارة الثابتة) | {spread(abst_ok)} | — |",
         "| الثبات: الحالة تعطي مجموعة التنبيهات نفسها في كل التشغيلات | "
         f"{pct(stability) if stability is not None else 'يحتاج --runs 3'} | — |",
         f"| اتفاق الشاهدين (الحقول المؤثرة) | {pct(statistics.mean(agreements)) if agreements else '—'} | — |",
         f"| متوسط chrF: حالات التغيّر / السليمة | — | {chrf_mut:.1f} / {chrf_fai:.1f} |",
         (f"| الزمن لكل جملة (متوسط التشغيلات بلا cache) | {statistics.mean(secs):.1f} ث | — |" if secs else None),
         f"| التكلفة لكل 1000 جملة (سجل tokens للتشغيلات بلا cache) | ${usd_per_1000:.0f} | ~0 |",
         "", "## الاستدعاء والدقة لكل نوع (مجمّعة عبر التشغيلات الصالحة)", "",
         "| النوع | المرات | الاستدعاء | الدقة | إنذارات كاذبة |", "|---|---|---|---|---|"]
    for t, v in sorted(metrics.items(), key=lambda kv: (kv[1]["recall"] is None, kv[1]["recall"] or 0)):
        L.append(f"| `{t}` | {v['support']} | {pct(v['recall'])} | {pct(v['precision'])} | {v['fp']} |")
    L += ["", "«المرات» = مرات ظهور التغيّر المزروع عبر التشغيلات (الحالة × التشغيل). الأنواع ذات المرات القليلة "
              "لا يُعتمد عليها إحصائياً.",
          "", "## خط الأساس مقابل مِرآة لكل حالة تغيّر", "",
          "درجات chrF المرتفعة مع تغيّر المعنى تعني أن المقاييس السطحية لا ترى الخلل.", "",
          "| الحالة | التغيّر المزروع | chrF | نسبة الطول | خط الأساس كشفه؟ | مِرآة كشفته (في كم تشغيل) |",
          "|---|---|---|---|---|---|"]
    for c in mut:
        b = base[c["id"]]
        hits = [detected(c, run[c["id"]]) for run in runs if valid(run[c["id"]])]
        L.append(f"| {c['id']} | {c['expected'][0]} | {b['chrf']} | {b['len_ratio']} | "
                 f"{'✅' if b['flagged'] else '❌'} | {sum(hits)}/{len(hits)} |")
    L += ["", "## التكلفة", "",
          f"- استدعاءات حية: {cost['live_calls']} · من الـcache: {cost['cache_hits']} · فاشلة: {cost['failed_calls']}",
          f"- الإجمالي التقريبي لهذا التقييم: ${cost['usd']}",
          "", "| النموذج | tokens إدخال | tokens إخراج | استدعاءات |", "|---|---|---|---|"]
    for mdl, (i, o, n) in cost["by_model"].items():
        L.append(f"| `{mdl}` | {i:,} | {o:,} | {n} |")
    if degraded:
        L += ["", "## حالات مستبعدة من القياس", "",
              "| التشغيل | الحالة | الحالة النهائية | السبب |", "|---|---|---|---|"]
        for run_no, cid, status, why in degraded:
            L.append(f"| {run_no} | {cid} | {status} | {'؛ '.join(w for w in why if w) or '—'} |")
        if cost.get("errors"):
            L += ["", "أخطاء المزوّد المسجّلة أثناء التقييم:", ""] + [f"- `{e}`" for e in cost["errors"]]
    L += ["", "## الحدود", "",
          "- البذور مسودة كتبها المساعد البرمجي ولم تراجعها المطوّرة بعد؛ والتغيّرات المزروعة مولّدة بنموذج، فقد لا يكون"
          " التغيّر مزروعاً بدقة في كل حالة (`eval/results.json` فيه النصوص والتنبؤات كاملة).",
          "- 47 حالة فقط، وبعض الأنواع ظهرت مرة واحدة لكل تشغيل: الاستدعاء والدقة لهذه الأنواع غير مستقرين إحصائياً.",
          "- كل حالة جملة أو جملتان وحلقة واحدة (عربي ← إنجليزي)؛ السلاسل الطويلة واللغات الأخرى لا تُقاس هنا.",
          "- الصياغات «السليمة» مولّدة بنموذج أيضاً؛ وبعض «الإنذارات الكاذبة» قد تكون فروقاً دقيقة حقيقية تحتاج حكماً بشرياً.",
          ("- التشغيل الأول أُعيد من cache تقييم أولي سابق؛ الزمن والتكلفة محسوبان من التشغيلات بلا cache فقط."
           if first_run_cached else None),
          "- الأسعار تقديرية من جدول ثابت في `eval/run_eval.py`.", ""]
    OUT_MD.write_text("\n".join(x for x in L if x is not None), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"cases": cases, "runs": runs, "baseline": base, "metrics": metrics, "cost": cost,
                                    "start": start.isoformat(), "first_run_cached": first_run_cached},
                                   ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT_MD.relative_to(ROOT)}  excluded: {[(d[0], d[1]) for d in degraded]}")
    weakest = sorted(((t, v) for t, v in metrics.items() if v["support"]), key=lambda kv: kv[1]["recall"])[:3]
    print("weakest by recall:", [(t, pct(v["recall"]), v["support"]) for t, v in weakest])
    print("most false alarms:", sorted(((t, v["fp"], pct(v["precision"])) for t, v in metrics.items()),
                                       key=lambda x: x[1], reverse=True)[:3])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--from-json", action="store_true", help="أعد حساب results.md من results.json بلا استدعاءات")
    args = ap.parse_args()

    if args.from_json:
        d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        write_results(d["cases"], d["runs"], d["cost"], datetime.fromisoformat(d["start"]), d["first_run_cached"])
        return

    cases = load_cases(args.limit)
    start = datetime.now(timezone.utc)
    runs, first_cached = [], False
    for i in range(args.runs):
        t0 = time.perf_counter()
        before = cost_since(start)["live_calls"]
        runs.append(run_once(cases, use_cache=(i == 0), workers=args.workers))
        if i == 0:
            first_cached = cost_since(start)["live_calls"] == before
        print(f"run {i + 1}/{args.runs}: {len(cases)} cases in {time.perf_counter() - t0:.0f}s")
    write_results(cases, runs, cost_since(start), start, first_cached)


if __name__ == "__main__":
    main()
