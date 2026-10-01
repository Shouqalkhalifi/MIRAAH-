"""تطبيق FastAPI: الصفحات والواجهة البرمجية."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from app import mock
from app.corpus import load_corpus

APP_DIR = Path(__file__).resolve().parent
VERSION = "0.0.1"
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


# ---------- API ----------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION, "corpus_items": len(load_corpus())}


# ---------- الشاشات (بيانات وهمية في المرحلة 0) ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "home.html")


@app.get("/new", response_class=HTMLResponse)
def new_report(request: Request):
    return page(request, "input.html")


@app.get("/analyze/{report_id}", response_class=HTMLResponse)
def analyzing(request: Request, report_id: str):
    return page(request, "analyze.html", report_id=report_id)


def _report_ctx() -> dict:
    r = mock.DEMO_REPORT
    reds = [a for a in r.alerts if a.severity.value == "red"]
    flagged = {a.source_span.sentence_index for a in r.alerts if a.source_span.sentence_index is not None}
    from app.pipeline.segment import split_sentences

    return dict(report=r, chain=mock.chain_labels(r), reds=reds,
                source_sentences=split_sentences(r.source.text), flagged=flagged,
                broken_at={a.introduced_at for a in reds})


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report_page(request: Request, report_id: str):
    return page(request, "report.html", **_report_ctx())


@app.get("/review/{report_id}", response_class=HTMLResponse)
def review_page(request: Request, report_id: str):
    return page(request, "review.html", revisions=mock.REVISIONS, **_report_ctx())


@app.get("/seal/{report_id}", response_class=HTMLResponse)
def seal_page(request: Request, report_id: str):
    r = mock.DEMO_REPORT
    hashes = [("source", mock.sha256(r.source.text))] + [(v.label, mock.sha256(v.text)) for v in r.versions]
    return page(request, "seal.html", report=r, chain=mock.chain_labels(r), hashes=hashes)
