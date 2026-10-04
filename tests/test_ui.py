"""طبقة العرض: علامات المقابلة، والتجميع بالسبب الجذري، وخيط السند، وسطر الحالة."""
from app import ui
from app.models import Alert, AlertType as T, Decision, Report, Severity, Source, Span, Version


def A(t, sev="red", at="sum", idx=(0,), src="للمسافر"):
    return Alert(type=t, severity=Severity(sev), version_label=at, introduced_at=at, explanation_ar="x",
                 source_span=Span(text=src), source_sentence_indices=list(idx))


def rep(alerts, decisions=None):
    return Report(source=Source(text="نص"), versions=[
        Version(label="en", lang="en", text="t"),
        Version(label="sum", lang="en", text="t", derived_from="en"),
        Version(label="fr", lang="fr", text="t", derived_from="sum")], alerts=alerts, decisions=decisions or {})


def test_mark_words_and_headlines():
    assert ui.mark_word("condition_dropped") == "سقط"
    assert ui.mark_word("consensus_inflated") == "زيادة"
    assert ui.mark_word("ruling_shift") == "تغيّر"
    assert ui.mark_word("unverified_attribution") == "يُنظر"
    assert ui.headline(A(T.condition_dropped)) == "سقط الشرط «للمسافر»"
    assert ui.headline(A(T.condition_dropped, src="جملة طويلة جداً " * 5)) == "سقط الشرط"


def test_symptoms_fold_under_root_cause():
    root, scope = A(T.condition_dropped), A(T.scope_widened, "yellow")
    reader = A(T.reader_divergence, "yellow", idx=())
    other_link = A(T.reader_divergence, "yellow", at="fr", idx=())
    groups = ui.group_alerts([root, scope, reader, other_link])
    assert groups[0]["root"] is root and groups[0]["symptoms"] == [scope, reader]
    assert groups[1]["root"] is other_link and groups[1]["symptoms"] == []


def test_thread_breaks_at_defect_and_marks_recheck_after_edit():
    a = A(T.condition_dropped)
    r = rep([a], {a.id: Decision(alert_id=a.id, action="edit", edited_text="A traveler may...", reason="أصلحت الشرط")})
    states = [(n["label"], n["state"], n["recheck"], n["marks"]) for n in ui.thread(r)]
    assert states == [("source", "ok", False, []), ("en", "ok", False, []),
                      ("sum", "break", False, ["سقط"]), ("fr", "after", True, [])]


def test_status_line():
    red, yellow = A(T.condition_dropped), A(T.ruling_shift, "yellow", at="en", idx=(1,))
    assert ui.status_line(rep([red, yellow])) == {"tone": "rubric", "text": "لا تنشر · سقط شرط و تغيّر الحكم"}
    decided = {red.id: Decision(alert_id=red.id, action="accept", reason="خلل حقيقي")}
    assert ui.status_line(rep([red, yellow], decided)) == {"tone": "saffron", "text": "يُنظر · تغيّر الحكم"}
    decided[yellow.id] = Decision(alert_id=yellow.id, action="reject", reason="ليس خللاً")
    assert ui.status_line(rep([red, yellow], decided))["text"] == "جاهز للنشر بعد نظرتك"


def test_status_list_counts_and_caps():
    assert ui.status_list(["سقط شرط", "سقط شرط", "سقطت جملة"]) == "سقط شرط (2) و سقطت جملة"
    assert ui.status_list(["أ", "ب", "ج", "د", "هـ"]) == "أ و ب و ج و 2 غيرها"
