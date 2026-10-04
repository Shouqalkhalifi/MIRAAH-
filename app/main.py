"""تطبيق FastAPI: الصفحات والواجهة البرمجية."""
from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from pydantic import BaseModel, Field

from app import export, ratelimit, review, service
from app.corpus import load_corpus
from app.examples import get_example, load_examples
from app.library import load_library
from app.models import MAX_VERSIONS, Decision, Lock, Report, ReportStatus, Revision
from app.service import STAGES
from app.pipeline.segment import split_sentences
from app.pipeline.locks import LOCK_TYPE_AR
from app.pipeline.severity import TIER_LABELS_AR
from app.service import AnalyzeRequest
from app.store import load_report
from app import ui
from app.ui import MODULES, meta

APP_DIR = Path(__file__).resolve().parent
VERSION = "0.1.0"
LIMITED = [Depends(ratelimit.check)]  # المسارات التي تستدعي النموذج
DISCLAIMER = "أداة مدعومة بالذكاء الاصطناعي للمساعدة في المراجعة، ولا تُصدر فتوى"

app = FastAPI(title="مِرآة MIRAAH", version=VERSION,
              description="تتبّع أثر المعنى في المحتوى الإسلامي عبر سلسلة النسخ. " + DISCLAIMER)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["DISCLAIMER"] = DISCLAIMER
templates.env.globals["tier_labels"] = TIER_LABELS_AR
templates.env.globals["lock_types"] = LOCK_TYPE_AR
templates.env.globals["modules"] = MODULES
templates.env.globals["meta"] = meta
# طبقة العرض للمقابلة (علامات النسّاخ، والتجميع بالسبب الجذري، وخيط السند) وتقسيم الجمل للمرآة
templates.env.globals["ui"] = ui
templates.env.globals["sentences"] = split_sentences
templates.env.globals["approved_text"] = export.approved_text
templates.env.globals["medium_ar"] = ui.MEDIUM_CHOICES
templates.env.globals["max_versions"] = MAX_VERSIONS
templates.env.globals["footer_ar"] = "مِرآة تعرض المصادر وتقابلها، ولا تُصدر فتوى"

_SEV_ORDER = {"red": 0, "yellow": 1, "info": 2}


def highlight(text: str, alerts, side: str, label: str | None = None) -> Markup:
    """يظلّل مقاطع التنبيهات في النص (الأحمر يغلب عند التداخل)."""
    spans: list[tuple[int, int, str, object]] = []
    for a in sorted(alerts, key=lambda a: _SEV_ORDER[a.severity.value]):
        if a.severity.value == "info":
            continue
        if side == "version" and a.version_label != label:
            continue
        frag = (a.source_span if side == "source" else a.version_span).text
        i = text.find(frag) if frag else -1
        if i < 0 or any(i < e and s < i + len(frag) for s, e, _, _ in spans):
            continue
        spans.append((i, i + len(frag), a.severity.value, a))
    out, pos = [], 0
    for s, e, sev, a in sorted(spans, key=lambda x: x[0]):
        word, tone = ui.mark_word(a.type.value), ui.tone(a)
        tip = escape(f"{ui.headline(a)} · {a.type.value}")  # الرمز التقني في التلميح فقط
        out += [escape(text[pos:s]),
                Markup(f'<a href="#alert-{a.id}" class="anchor" data-alert="{a.id}">'
                       f'<mark class="mk mk-{tone}" title="{tip}">'), escape(text[s:e]), Markup("</mark>")]
        if side == "version":  # علامة النسّاخ مرتفعة عند حدّ الموضع: «سقط» / «زيادة» / «تغيّر» / «يُنظر»
            out.append(Markup(f'<sup class="sigla tone-{tone}">{escape(word)}</sup>'))
        out.append(Markup("</a>"))
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


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(APP_DIR / "static" / "favicon.ico", media_type="image/x-icon")


# ---------- API ----------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION, "corpus_items": len(load_corpus())}


@app.post("/api/analyze", response_model=None, dependencies=LIMITED)
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


class DecisionIn(Decision):
    report_id: str


class ApproveIn(BaseModel):
    report_id: str


def _review_call(fn, *args):
    try:
        return fn(*args)
    except review.ReviewError as e:
        raise HTTPException(e.status, str(e))


@app.post("/api/decision", response_model=Report)
def api_decision(body: DecisionIn):
    """قرار المراجع على تنبيه: accept / reject / edit، والسبب إلزامي. يُسجَّل في سجل التدقيق."""
    decision = Decision.model_validate(body.model_dump(exclude={"report_id"}))
    return _review_call(review.decide, body.report_id, decision)


@app.post("/api/approve", response_model=Report)
def api_approve(body: ApproveIn):
    """يعتمد المراجع التقرير فيصير قابلاً للتصدير. يُرفض ما لم تُحسم كل التنبيهات الحمراء، ودائماً في المستوى D."""
    return _review_call(review.approve, body.report_id)


def _exportable(report_id: str) -> Report:
    r = _get(report_id)
    if r.status in (ReportStatus.analyzing, ReportStatus.failed):
        raise HTTPException(409, "لم يكتمل تحليل هذا التقرير بعد")
    return r


def _download(name: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{name}"'}


@app.get("/api/report/{report_id}/export.json")
def api_export_json(report_id: str):
    """تقرير المراجعة بصيغة JSON: للمراجعة قبل النشر، وليس شهادة اعتماد."""
    r = _exportable(report_id)
    return JSONResponse(export.build(r, DISCLAIMER), headers=_download(f"miraah-report-{r.id}.json"))


@app.get("/api/report/{report_id}/export.html", response_class=HTMLResponse)
def api_export_html(request: Request, report_id: str):
    """تقرير المراجعة صفحةً مستقلة قابلة للطباعة."""
    r = _exportable(report_id)
    html = templates.get_template("export.html").render(d=export.build(r, DISCLAIMER), lang_ar=export.LANG_AR)
    return HTMLResponse(html, headers=_download(f"miraah-report-{r.id}.html"))


@app.get("/api/report/{report_id}/export.pdf")
def api_export_pdf(report_id: str):
    """تقرير المراجعة ملف PDF: الحكم، والمصدر، ونص كل حلقة، والتنبيهات مع سببها وما يُقترح فيها."""
    from app import pdf

    r = _exportable(report_id)
    return Response(pdf.render(export.build(r, DISCLAIMER)), media_type="application/pdf",
                    headers=_download(f"miraah-report-{r.id}.pdf"))


class ReverseIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    save: bool = False  # لا يُحفظ النص إلا باختيار المستخدم


@app.post("/api/reverse", dependencies=LIMITED)
def api_reverse(body: ReverseIn):
    """«قابِل ما قرأت»: يقابل عبارة أو سؤالاً بنص المصدر في مكتبة مِرآة. لا يُصدر فتوى ولا يرجّح."""
    try:
        return service.reverse_trace(body.text, body.save).model_dump(mode="json")
    except Exception as e:
        raise HTTPException(503, service.friendly_error(e).split("\n")[0])


class SuggestLocksIn(BaseModel):
    text: str = Field(min_length=1)
    lang: str = "ar"


@app.post("/api/locks/suggest", response_model=list[Lock], dependencies=LIMITED)
def api_suggest_locks(body: SuggestLocksIn):
    """أقفال مقترحة من الأصل: الشروط والاستثناءات من البصمة، وصيغ اليقين والنسبة والدرجات والنفي والأرقام والمصطلحات."""
    return service.suggest_locks(body.text, body.lang)


class ReviseIn(BaseModel):
    report_id: str
    alert_id: str


@app.post("/api/revise", response_model=list[Revision], dependencies=LIMITED)
def api_revise(body: ReviseIn):
    """ثلاث صياغات آمنة (الأدق / المتوازنة / الأوضح) بلغة النسخة، كل منها مُعاد فحصها؛ passed=false تعني أنها استُبعدت."""
    from app.pipeline.revise import RevisionError

    try:
        return service.revise_alert(body.report_id, body.alert_id)
    except KeyError:
        raise HTTPException(404, "التقرير أو التنبيه غير موجود")
    except RevisionError as e:
        raise HTTPException(409, str(e))


@app.post("/api/report/{report_id}/reexam", dependencies=LIMITED)
def api_reexam(report_id: str):
    """يعيد امتحان القارئ على نص كل حلقة بعد تصحيحاتها المعتمدة، بالأسئلة نفسها."""
    try:
        r = service.reexam_corrected(report_id)
    except KeyError:
        raise HTTPException(404, "التقرير غير موجود")
    return r.reader_exam.model_dump(mode="json") if r.reader_exam else {}


@app.get("/api/report/{report_id}/audit")
def api_audit(report_id: str) -> list[dict]:
    _get(report_id)
    return [e.model_dump(mode="json") for e in review.audit_log(report_id)]


@app.get("/api/examples")
def api_examples() -> list[dict]:
    return [e.model_dump(mode="json") for e in load_examples()]


# ---------- الشاشات ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    verse = next((c for c in load_corpus() if c.id == "q-2-185-yusr"), None)
    sample = next((i for i in load_library() if i.id == "BZ09"), None)
    return page(request, "home.html", examples=load_examples(), verse=verse, sample=sample)


@app.get("/about")
def about():
    return RedirectResponse("/#about", status_code=308)


@app.get("/reverse", response_class=HTMLResponse)
def reverse_page(request: Request):
    """«تحقّق مما قرأت»: خدمة القارئ. عرض فقط، بلا تعديل ولا تصحيح."""
    return page(request, "reverse.html", result=None, text="", error="")


@app.post("/reverse", response_class=HTMLResponse)
def reverse_submit(request: Request, text: str = Form(""), save: str | None = Form(None)):
    text = text.strip()
    if not 3 <= len(text) <= 1000:
        return page(request, "reverse.html", result=None, text=text,
                    error="اكتب ما قرأته أو سؤالك في 3 أحرف إلى 1000 حرف.")
    if not ratelimit.allow(ratelimit.client_key(request)):
        return page(request, "reverse.html", result=None, text=text,
                    error=ratelimit.MESSAGE.format(n=ratelimit.per_hour()))
    try:
        result = service.reverse_trace(text, bool(save))
    except Exception as e:
        return page(request, "reverse.html", result=None, text=text, error=service.friendly_error(e).split("\n")[0])
    if result.id:
        return RedirectResponse(f"/reverse/{result.id}", status_code=303)
    return page(request, "reverse.html", result=result, text=text, error="")


@app.get("/reverse/{rid}", response_class=HTMLResponse)
def reverse_saved(request: Request, rid: str):
    result = service.load_reverse(rid)
    if result is None:
        raise HTTPException(404, "لم تُحفظ هذه المقابلة، أو حُذفت.")
    return page(request, "reverse.html", result=result, text=result.text, error="")


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
    return page(request, "input.html", examples=load_examples())


@app.get("/analyze/{report_id}", response_class=HTMLResponse)
def analyzing(request: Request, report_id: str):
    r = _get(report_id)
    return page(request, "analyze.html", report=r, stages=[label for _, label in STAGES])


def _report_ctx(r: Report) -> dict:
    by_sev = lambda sev: {a.introduced_at for a in r.alerts if a.severity.value == sev}  # noqa: E731
    flagged = {i for a in r.alerts if a.severity.value != "info" for i in a.source_sentence_indices}
    counts = {m: {"red": 0, "yellow": 0, "info": 0} for m in MODULES}
    for a in r.alerts:
        counts[meta(a.type.value)[0]][a.severity.value] += 1  # noqa: E501
    version_index = {v.label: i for i, v in enumerate(r.versions)}
    entered = [a.introduced_at for a in r.alerts if a.severity.value != "info" and a.introduced_at in version_index]
    first_tab = version_index[entered[0]] if entered else 0  # افتح النسخة التي دخل فيها أخطر خلل
    return dict(report=r, chain=["source"] + [v.label for v in r.versions], module_counts=counts,
                version_index=version_index, first_tab=first_tab,
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
    if redirect:
        return redirect
    # tojson في القالب لا يفهم كائنات Pydantic: نمرّر قواميس جاهزة
    saved = {"decisions": {k: d.model_dump(mode="json") for k, d in r.decisions.items()},
             "revisions": {k: [x.model_dump(mode="json") for x in v] for k, v in r.revisions.items()}}
    return page(request, "review.html", blockers=review.blockers(r), saved=saved,
                **_report_ctx(r))
