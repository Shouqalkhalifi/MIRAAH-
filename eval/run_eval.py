"""يشغّل مِرآة على حالات التقييم ويكتب eval/results.md (CLAUDE.md القسم 9).

التشغيل:
    python eval/run_eval.py --runs 1          # تقييم أولي
    python eval/run_eval.py --runs 3          # التقييم الكامل (التشغيلان 2 و3 بلا cache لقياس الثبات)

يقيس: الاستدعاء والدقة لكل نوع تغيّر، ونسبة الإنذارات الكاذبة على الحالات السليمة، وصحة الامتناع، والثبات
عبر التشغيلات، ونسبة اتفاق الشاهدين، والتكلفة والزمن لكل جملة، ومقارنة بخط أساس أبسط (chrF ونسبة الطول).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
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

# الأنواع التي تُقاس (المزروعة)؛ والأنواع السياقية تُعرض منفصلة ولا تُحتسب إنذاراً كاذباً لنوع آخر
SCORED = {
    "condition_dropped", "exception_dropped", "certainty_raised", "attribution_upgraded", "new_prophetic_attribution",
    "ruling_shift", "scope_widened", "scope_narrowed", "hasr_lost", "consensus_inflated", "hadith_grade_dropped",
    "negation_mismatch", "number_mismatch", "term_narrowing", "unverified_attribution", "source_conflict",
    "quote_wording_differs",
}
CONTEXT = {"reader_divergence", "witness_disagreement", "sentence_dropped", "length_drop", "lock_violated"}

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
    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    return cases[:limit] if limit else cases


def analyze_case(case: dict) -> dict:
    t0 = time.perf_counter()
    req = AnalyzeRequest(title=case["id"],
                         source=Source(text=case["source"], lang="ar", content_level=case["level"]),
                         versions=[Version(label="v", lang="en", text=case["version"])])
    report = service.run_analysis(service.create_report(req).id)
    alerts = [a for a in report.alerts if a.severity.value in ("red", "yellow")]
    return {
        "id": case["id"], "status": report.status.value, "error": report.error,
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
def per_type_metrics(cases: list[dict], res: dict[str, dict]) -> dict[str, dict]:
    m = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0, "support": 0})
    for c in cases:
        pred = set(res[c["id"]]["predicted"]) & SCORED
        exp = set(c["expected"])
        allowed = exp | set().union(*(ALLOWED.get(e, set()) for e in exp)) if exp else set()
        for e in exp:
            m[e]["support"] += 1
            m[e]["tp" if e in pred else "fn"] += 1
        for p in pred - allowed:
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
        out[c["id"]] = {"chrf": round(chrf, 1), "len_ratio": round(ratio, 2),
                        "flagged": chrf < 50 or ratio < 0.65}
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
    return {"calls": len(rows), "live_calls": len(live), "cache_hits": sum(r.cached for r in rows),
            "failed_calls": sum(not r.ok for r in rows), "by_model": dict(by_model), "usd": round(usd, 4)}


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}٪"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    cases = load_cases(args.limit)
    start = datetime.now(timezone.utc)
    runs = []
    for i in range(args.runs):
        t0 = time.perf_counter()
        runs.append(run_once(cases, use_cache=(i == 0), workers=args.workers))
        print(f"run {i + 1}/{args.runs}: {len(cases)} cases in {time.perf_counter() - t0:.0f}s")
    cost = cost_since(start)
    first = runs[0]
    by_id = {c["id"]: c for c in cases}
    mut = [c for c in cases if c["kind"] == "mutation"]
    fai = [c for c in cases if c["kind"] == "faithful"]
    abst = [c for c in cases if c["kind"] == "abstention"]

    metrics = per_type_metrics(mut + fai + abst, first)
    detected_any = lambda c, r: bool(set(r[c["id"]]["predicted"]) & (set(c["expected"]) | set().union(  # noqa: E731
        *(ALLOWED.get(e, set()) for e in c["expected"]))))
    mut_recall = sum(detected_any(c, first) for c in mut) / len(mut) if mut else None
    fa_scored = sum(bool(set(first[c["id"]]["predicted"]) & SCORED) for c in fai) / len(fai) if fai else None
    fa_any = sum(bool(first[c["id"]]["predicted"]) for c in fai) / len(fai) if fai else None
    abst_ok = (sum(first[c["id"]]["verifications"] and all(v == "unverified" for v in first[c["id"]]["verifications"])
                   and first[c["id"]]["fixed_phrase_ok"] for c in abst) / len(abst)) if abst else None
    failed = [r["id"] for r in first.values() if r["status"] != "analyzed"]

    stability = None
    if len(runs) > 1:
        same = [len({tuple(sorted(set(r[c["id"]]["predicted"]) & SCORED)) for r in runs}) == 1 for c in cases]
        stability = sum(same) / len(same)
    agreements = [r["witness_agreement"] for r in first.values() if r["witness_agreement"] is not None]
    witness = statistics.mean(agreements) if agreements else None
    secs = statistics.mean(r["seconds"] for r in first.values())
    n_sent = len(cases) * len(runs)
    usd_per_1000 = cost["usd"] / n_sent * 1000 if n_sent else 0

    base = baseline(cases)
    base_recall = sum(base[c["id"]]["flagged"] for c in mut) / len(mut) if mut else None
    base_fa = sum(base[c["id"]]["flagged"] for c in fai) / len(fai) if fai else None
    chrf_mut = statistics.mean(base[c["id"]]["chrf"] for c in mut) if mut else None
    chrf_fai = statistics.mean(base[c["id"]]["chrf"] for c in fai) if fai else None

    # ---------- results.md ----------
    L = [f"# نتائج التقييم — مِرآة",
         "",
         f"- التاريخ: {start.strftime('%Y-%m-%d %H:%M UTC')} · عدد الحالات: {len(cases)} "
         f"(تغيّر مزروع {len(mut)} · سليمة المعنى {len(fai)} · امتناع {len(abst)}) · التشغيلات: {len(runs)}",
         f"- النماذج: الشاهد الأول `{os.getenv('WITNESS_A_MODEL') or os.getenv('MAIN_MODEL')}`، "
         f"الشاهد الثاني `{os.getenv('WITNESS_B_MODEL') or '—'}`",
         "- البذور مسودة لم تُراجع بعد، والحالات مولّدة آلياً: الأرقام **أولية** وتُقرأ مع قسم الحدود.",
         "",
         "## ملخص", "",
         "| المقياس | مِرآة | خط الأساس (chrF < 50 أو الطول < 65٪) |", "|---|---|---|",
         f"| كشف التغيّر المزروع (أي تنبيه مطابق) | {pct(mut_recall)} | {pct(base_recall)} |",
         f"| إنذارات كاذبة على الصياغات السليمة (أنواع مقيسة) | {pct(fa_scored)} | {pct(base_fa)} |",
         f"| إنذارات كاذبة على السليمة (أي تنبيه أحمر/أصفر، مع امتحان القارئ) | {pct(fa_any)} | — |",
         f"| صحة الامتناع (غير متحقق + العبارة الثابتة) | {pct(abst_ok)} | — |",
         f"| الثبات عبر التشغيلات (مجموعة التنبيهات نفسها) | {pct(stability) if stability is not None else 'يحتاج --runs 3'} | — |",
         f"| اتفاق الشاهدين (الحقول المؤثرة) | {pct(witness)} | — |",
         f"| متوسط chrF: حالات التغيّر / السليمة | — | {chrf_mut:.1f} / {chrf_fai:.1f} |" if mut and fai else "",
         f"| الزمن لكل جملة (متوسط) | {secs:.1f} ث | — |",
         f"| التكلفة لكل 1000 جملة (تقدير من سجل tokens) | ${usd_per_1000:.2f} | ~0 |",
         f"| تحليلات فشلت | {len(failed)} | — |",
         "",
         "## الاستدعاء والدقة لكل نوع", "",
         "| النوع | الحالات | الاستدعاء | الدقة | إنذارات كاذبة |", "|---|---|---|---|---|"]
    for t, v in sorted(metrics.items(), key=lambda kv: (kv[1]["recall"] is None, kv[1]["recall"] or 0)):
        L.append(f"| `{t}` | {v['support']} | {pct(v['recall'])} | {pct(v['precision'])} | {v['fp']} |")
    L += ["", "## خط الأساس: chrF ونسبة الطول لحالات التغيّر", "",
          "درجات chrF المرتفعة مع تغيّر المعنى تعني أن المقاييس السطحية لا ترى الخلل.", "",
          "| الحالة | التغيّر المزروع | chrF | نسبة الطول | خط الأساس كشفه؟ | مِرآة كشفته؟ |", "|---|---|---|---|---|---|"]
    for c in mut:
        b = base[c["id"]]
        L.append(f"| {c['id']} | {c['expected'][0]} | {b['chrf']} | {b['len_ratio']} | "
                 f"{'✅' if b['flagged'] else '❌'} | {'✅' if detected_any(c, first) else '❌'} |")
    L += ["", "## التكلفة", "",
          f"- استدعاءات حية: {cost['live_calls']} · من الـcache: {cost['cache_hits']} · فاشلة: {cost['failed_calls']}",
          f"- الإجمالي التقريبي: ${cost['usd']}",
          "", "| النموذج | tokens إدخال | tokens إخراج | استدعاءات |", "|---|---|---|---|"]
    for mdl, (i, o, n) in cost["by_model"].items():
        L.append(f"| `{mdl}` | {i:,} | {o:,} | {n} |")
    L += ["", "## الحدود", "",
          "- البذور مسودة كتبها المساعد البرمجي ولم تراجعها المطوّرة بعد؛ والتغيّرات المزروعة مولّدة بنموذج، فقد لا يكون"
          " التغيّر مزروعاً بدقة في كل حالة (افحص `eval/results.json`).",
          "- كل حالة جملة أو جملتان وحلقة واحدة؛ السلاسل الطويلة لا تُقاس هنا.",
          "- الأسعار تقديرية من جدول ثابت في `eval/run_eval.py`.",
          "- الثبات يُقاس فقط مع `--runs 3` (التشغيلان 2 و3 بلا cache).", ""]
    OUT_MD.write_text("\n".join(x for x in L if x is not None), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"cases": cases, "runs": runs, "baseline": base, "metrics": metrics,
                                    "cost": cost}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT_MD.relative_to(ROOT)}  (failed: {failed})")
    weakest = sorted(((t, v) for t, v in metrics.items() if v["support"]), key=lambda kv: kv[1]["recall"])[:3]
    print("weakest by recall:", [(t, pct(v["recall"]), v["support"]) for t, v in weakest])
    misses = defaultdict(list)
    for c in mut:
        for e in c["expected"]:
            if e not in first[c["id"]]["predicted"]:
                misses[e].append((c["id"], c["version"], first[c["id"]]["predicted"]))
    for t, _ in weakest:
        for m in misses.get(t, [])[:3]:
            print("  miss", t, "|", m[0], "|", m[1], "| got", m[2])
    fps = Counter(p for c in fai for p in set(first[c["id"]]["predicted"]))
    print("faithful false alarms by type:", dict(fps))


if __name__ == "__main__":
    main()
