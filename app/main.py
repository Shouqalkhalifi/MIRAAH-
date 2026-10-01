"""تطبيق FastAPI: الصفحات والواجهة البرمجية."""
from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from app import service
from app.corpus import load_corpus
from app.examples import get_example, load_examples
from app.models import Report, ReportStatus
from app.service import STAGES
from app.pipeline.segment import split_sentences
from app.service import AnalyzeRequest
from app.store import load_report

APP_DIR = Path(__file__).resolve().parent
VERSION = "0.1.0"
DISCLAIMER = "أداة مدعومة بالذكاء الاصطناعي للمساعدة في المراجعة، ولا تُصدر فتوى"

app = FastAPI(title="مِرآة MIRAAH", version=VERSION,
              description="تتبّع أثر المعنى في المحتوى الإسلامي عبر سلسلة النسخ. " + DISCLAIMER)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["DISCLAIMER"] = DISCLAIMER

_SEV_ORDER = {"red": 0, "yellow": 1, "info": 2}


def highlight(text: str, alerts, side: str, label: str | None = None) -> Markup:
    """يظلّل مقاطع التنبيهات في النص (الأحمر يغلب عند التداخل)."""
    spans: list[tuple[int, int, str]] = []
    for a in sorted(alerts, key=lambda a: _SEV_ORDER[a.severity.value]):
        if a.severity.value == "info":
            continue
        if side == "version" and a.version_label != label:
            continue
        frag = (a.source_span if side == "source" else a.version_span).text
        i = text.find(frag) if frag else -1
        if i < 0 or any(i < e and s < i + len(frag) for s, e, _ in spans):
            continue
        spans.append((i, i + len(frag), a.severity.value))
    out, pos = [], 0
    for s, e, sev in sorted(spans):
        out += [escape(text[pos:s]), Markup(f'<mark class="mark-{sev}">'), escape(text[s:e]), Markup("</mark>")]
        pos = e
    out.append(escape(text[pos:]))
    return Markup("").join(out)


templates.env.filters["hl"] = highlight


def page(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


def _get(report_id: str) -> Report:
    r = load_report(report_id)
    if r is None:
        raise HTTPException(404, "التقرير غير موجود")
    return r


# ---------- API ----------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION, "corpus_items": len(load_corpus())}


@app.post("/api/analyze", response_model=None)
def api_analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, background: bool = False):
    """يحلل الأصل ونسخه. افتراضياً يعيد التقرير كاملاً؛ ومع `background=true` يعيد المعرّف فوراً."""
    report = service.create_report(req)
    if background:
        background_tasks.add_task(service.run_analysis, report.id)
        return {"id": report.id, "status": report.status.value}
    return service.run_analysis(report.id)


@app.get("/api/report/{report_id}", response_model=Report)
def api_report(report_id: str):
    return _get(report_id)


@app.get("/api/report/{report_id}/status")
def api_status(report_id: str) -> dict:
    r = _get(report_id)
    keys = [k for k, _ in STAGES]
    return {"id": r.id, "status": r.status.value, "stage": r.stage,
            "stage_index": keys.index(r.stage) if r.stage in keys else (len(keys) if r.stage == "done" else -1),
            "stages": [label for _, label in STAGES], "error": r.error}


@app.get("/api/examples")
def api_examples() -> list[dict]:
    return [e.model_dump(mode="json") for e in load_examples()]


# ---------- الشاشات ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "home.html", examples=load_examples())


@app.post("/examples/{name}")
def run_example(name: str, background_tasks: BackgroundTasks):
    ex = get_example(name)
    if ex is None:
        raise HTTPException(404, "المثال غير موجود")
    report = service.create_report(ex.request)
    background_tasks.add_task(service.run_analysis, report.id)
    return RedirectResponse(f"/analyze/{report.id}", status_code=303)


@app.get("/new", response_class=HTMLResponse)
def new_report(request: Request):
    return page(request, "input.html")


@app.get("/analyze/{report_id}", response_class=HTMLResponse)
def analyzing(request: Request, report_id: str):
    r = _get(report_id)
    return page(request, "analyze.html", report=r, stages=[label for _, label in STAGES])


def _report_ctx(r: Report) -> dict:
    by_sev = lambda sev: {a.introduced_at for a in r.alerts if a.severity.value == sev}  # noqa: E731
    flagged = {i for a in r.alerts if a.severity.value != "info" for i in a.source_sentence_indices}
    return dict(report=r, chain=["source"] + [v.label for v in r.versions],
                reds=[a for a in r.alerts if a.severity.value == "red"],
                broken_at=by_sev("red"), warn_at=by_sev("yellow") - by_sev("red"),
                inherited={lb for a in r.alerts if a.severity.value != "info" for lb in a.propagated_to},
                source_sentences=split_sentences(r.source.text), flagged=flagged)


def _ready_report(report_id: str):
    r = _get(report_id)
    if r.status in (ReportStatus.analyzing, ReportStatus.failed):
        return None, RedirectResponse(f"/analyze/{report_id}", status_code=303)
    return r, None


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report_page(request: Request, report_id: str):
    r, redirect = _ready_report(report_id)
    return redirect or page(request, "report.html", **_report_ctx(r))


@app.get("/review/{report_id}", response_class=HTMLResponse)
def review_page(request: Request, report_id: str):
    r, redirect = _ready_report(report_id)
    return redirect or page(request, "review.html", revisions={}, **_report_ctx(r))


@app.get("/seal/{report_id}", response_class=HTMLResponse)
def seal_page(request: Request, report_id: str):
    import hashlib

    r, redirect = _ready_report(report_id)
    if redirect:
        return redirect
    sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()  # noqa: E731
    hashes = [("source", sha(r.source.text))] + [(v.label, sha(v.text)) for v in r.versions]
    return page(request, "seal.html", report=r, chain=["source"] + [v.label for v in r.versions], hashes=hashes)
