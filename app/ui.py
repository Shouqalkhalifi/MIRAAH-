"""بيانات العرض: الوحدات الثلاث (الميزان / الأثر / الفهم) وعنوان عربي لكل نوع تنبيه."""
from __future__ import annotations

from app.models import AlertType as T

MODULES = {
    "mizan": {"ar": "الميزان", "en": "MIZAN", "sub_ar": "دليل وإسناد", "sub_en": "Evidence & Attribution",
              "desc": "يبحث عن كل نص منسوب إلى الله أو رسوله ﷺ في مدونة محلية موثّقة، وما لا يجده يُحال إلى المراجع ولا يُحكم عليه."},
    "athar": {"ar": "الأثر", "en": "ATHAR", "sub_ar": "سلسلة المعنى", "sub_en": "Meaning Lineage",
              "desc": "يتتبّع ثوابت المعنى من الأصل عبر الترجمات والملخصات، ويحدد الحلقة التي دخل فيها الخلل."},
    "fahm": {"ar": "الفهم", "en": "FAHM", "sub_ar": "فهم سياقي وثقافي", "sub_en": "Contextual & Cultural Understanding",
             "desc": "يفحص ضوابط المصطلحات، ويمتحن ما يفهمه قارئ النسخة مقارنة بقارئ الأصل."},
}

# نوع إعادة الإنتاج لكل حلقة (Version.medium)
MEDIUM_AR = {"translation": "ترجمة", "summary": "ملخص", "edited": "نسخة محرّرة", "social_post": "منشور تواصل",
             "video_script": "نص فيديو", "infographic": "نص إنفوغرافيك", "ai_answer": "إجابة ذكاء اصطناعي",
             "other": "أخرى"}

# النوع ← (الوحدة، العنوان العربي)
ALERT_META: dict[str, tuple[str, str]] = {
    # الميزان: النسبة والدليل
    T.unverified_attribution: ("mizan", "نسبة غير متحقق منها"),
    T.source_conflict: ("mizan", "تعارض مع المصدر"),
    T.quote_wording_differs: ("mizan", "اختلاف لفظ النص المنسوب"),
    T.new_prophetic_attribution: ("mizan", "نسبة جديدة إلى النبي ﷺ"),
    T.attribution_upgraded: ("mizan", "جزم بعد تمريض"),
    T.hadith_grade_dropped: ("mizan", "حذف درجة الحديث"),
    T.consensus_inflated: ("mizan", "تضخيم دعوى الإجماع"),
    T.attribution_generalized: ("mizan", "تعميم النسبة إلى الإسلام"),
    T.disagreement_collapsed: ("athar", "انهيار الخلاف إلى قطع"),
    # الأثر: ثوابت المعنى عبر السلسلة
    T.condition_dropped: ("athar", "سقوط شرط"),
    T.exception_dropped: ("athar", "سقوط استثناء"),
    T.certainty_raised: ("athar", "ارتفاع درجة اليقين"),
    T.ruling_shift: ("athar", "تغيّر نوع الحكم"),
    T.scope_widened: ("athar", "اتساع النطاق"),
    T.scope_narrowed: ("athar", "تضييق النطاق"),
    T.hasr_lost: ("athar", "سقوط الحصر"),
    T.negation_mismatch: ("athar", "اختلاف النفي"),
    T.number_mismatch: ("athar", "اختلاف الأرقام"),
    T.sentence_dropped: ("athar", "جملة بلا مقابل"),
    T.length_drop: ("athar", "اختصار شديد"),
    T.lock_violated: ("athar", "كسر قفل معنى"),
    T.witness_disagreement: ("athar", "مختلف فيه بين الشاهدين"),
    # الفهم
    T.term_narrowing: ("fahm", "مخالفة ضابط مصطلح"),
    T.reader_divergence: ("fahm", "اختلاف فهم القارئ"),
}
ALERT_META = {k.value: v for k, v in ALERT_META.items()}

# سطر إنجليزي قصير لكل نوع (كما في التصميم: "Meaning: Constraint Loss")
ALERT_EN = {
    "unverified_attribution": "Evidence: Not Verified", "source_conflict": "Evidence: Source Conflict",
    "quote_wording_differs": "Evidence: Wording Differs", "new_prophetic_attribution": "Evidence: New Attribution",
    "attribution_upgraded": "Evidence: Attribution Upgraded", "hadith_grade_dropped": "Evidence: Grade Dropped",
    "consensus_inflated": "Evidence: Consensus Inflated",
    "attribution_generalized": "Evidence: Attribution Generalized",
    "disagreement_collapsed": "Meaning: Disagreement Lost", "condition_dropped": "Meaning: Constraint Loss",
    "exception_dropped": "Meaning: Exception Loss", "certainty_raised": "Meaning: Certainty Raised",
    "ruling_shift": "Meaning: Ruling Shift", "scope_widened": "Meaning: Scope Widened",
    "scope_narrowed": "Meaning: Scope Narrowed", "hasr_lost": "Meaning: Restriction Lost",
    "negation_mismatch": "Meaning: Negation Mismatch", "number_mismatch": "Meaning: Number Mismatch",
    "sentence_dropped": "Meaning: Sentence Dropped", "length_drop": "Style: Heavy Shortening",
    "lock_violated": "Meaning: Lock Broken", "witness_disagreement": "Witnesses Disagree",
    "term_narrowing": "Context: Term Misuse", "reader_divergence": "Context: Reader Divergence",
}


def meta(alert_type: str) -> tuple[str, str, str]:
    """(الوحدة، العنوان العربي، السطر الإنجليزي)"""
    mod, ar = ALERT_META.get(alert_type, ("athar", alert_type))
    return mod, ar, ALERT_EN.get(alert_type, alert_type)


# ---------- لغة المقابلة: علامات النسّاخ ----------
# «سقط»: شيء سقط · «زيادة»: شيء أُضيف · «تغيّر»: معنى تحوّل · «يُنظر»: يحتاج مختصاً أو مرجعاً
MARK_WORD = {
    "condition_dropped": "سقط", "exception_dropped": "سقط", "sentence_dropped": "سقط", "hasr_lost": "سقط",
    "hadith_grade_dropped": "سقط", "lock_violated": "سقط",
    "new_prophetic_attribution": "زيادة", "consensus_inflated": "زيادة", "attribution_generalized": "زيادة",
    "disagreement_collapsed": "سقط",
    "certainty_raised": "تغيّر", "ruling_shift": "تغيّر", "scope_widened": "تغيّر", "scope_narrowed": "تغيّر",
    "negation_mismatch": "تغيّر", "number_mismatch": "تغيّر", "term_narrowing": "تغيّر",
    "attribution_upgraded": "تغيّر", "quote_wording_differs": "تغيّر", "source_conflict": "تغيّر",
    "unverified_attribution": "يُنظر", "witness_disagreement": "يُنظر", "reader_divergence": "يُنظر",
    "length_drop": "يُنظر",
}

# عنوان الملاحظة: المشكلة نفسها بصيغة الفعل
_HEADLINE = {
    "condition_dropped": "سقط الشرط «{src}»", "exception_dropped": "سقط الاستثناء «{src}»",
    "sentence_dropped": "سقطت جملة من الأصل", "hasr_lost": "سقطت أداة الحصر", "hadith_grade_dropped": "سقطت درجة الحديث",
    "lock_violated": "انكسر القفل «{src}»", "new_prophetic_attribution": "زيدت نسبة القول إلى النبي ﷺ",
    "consensus_inflated": "زيدت دعوى الإجماع", "disagreement_collapsed": "سقط ذكر الخلاف فصار القول قطعياً",
    "attribution_generalized": "نُسب رأيٌ إلى الإسلام كله", "certainty_raised": "ارتفعت درجة اليقين", "ruling_shift": "تغيّر نوع الحكم",
    "scope_widened": "اتسع النطاق", "scope_narrowed": "ضاق النطاق", "negation_mismatch": "تغيّر النفي",
    "number_mismatch": "تغيّر الرقم", "term_narrowing": "خالف المصطلحُ ضابطه", "attribution_upgraded": "صار المرويّ جازماً",
    "quote_wording_differs": "تغيّر لفظ النص المنسوب", "source_conflict": "خالف النصُّ مصدره",
    "unverified_attribution": "نسبةٌ لم نجد مصدرها", "witness_disagreement": "اختلف الشاهدان",
    "reader_divergence": "فهم قارئ النسخة مختلف", "length_drop": "اختُصرت الحلقة كثيراً",
}
# أعراض تُطوى تحت سببها الجذري إن وُجد في الحلقة نفسها
SYMPTOM_TYPES = {"scope_widened", "scope_narrowed", "reader_divergence", "length_drop", "witness_disagreement"}


def mark_word(alert_type: str) -> str:
    return MARK_WORD.get(alert_type, "يُنظر")


def tone(alert) -> str:
    """لون العلامة: الحُمرة للخطير، والزعفران للمتوسط وما يُنظر فيه."""
    return "rubric" if alert.severity.value == "red" else "saffron"


def headline(alert) -> str:
    src = (alert.source_span.text or "").strip()
    tpl = _HEADLINE.get(alert.type.value, meta(alert.type.value)[1])
    if "{src}" in tpl:
        return tpl.format(src=src) if src and len(src) <= 40 else tpl.split(" «")[0]
    return tpl


def group_alerts(alerts) -> list[dict]:
    """يجمع التنبيهات حسب السبب الجذري: {"root": تنبيه، "symptoms": [...]}.

    العَرَض (اتساع النطاق، امتحان القارئ...) يُلحق بأول سبب في الحلقة نفسها يشاركه جملة الأصل،
    وإلا بأول سبب في الحلقة؛ وإن لم يوجد سبب صار هو نفسه ملاحظة مستقلة.
    """
    groups: list[dict] = []
    for a in alerts:
        if a.type.value not in SYMPTOM_TYPES:
            groups.append({"root": a, "symptoms": []})
    for a in alerts:
        if a.type.value not in SYMPTOM_TYPES:
            continue
        same_link = [g for g in groups if g["root"].introduced_at == a.introduced_at
                     and g["root"].type.value not in SYMPTOM_TYPES]
        shared = [g for g in same_link if set(g["root"].source_sentence_indices) & set(a.source_sentence_indices)]
        target = (shared or same_link or [None])[0]
        if target:
            target["symptoms"].append(a)
        else:
            groups.append({"root": a, "symptoms": []})
    return groups


LANG_ADJ = {"ar": "عربية", "en": "إنجليزية", "fr": "فرنسية", "id": "إندونيسية", "ur": "أردية"}
ORDINAL = ["", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة"]


def version_names(report) -> dict[str, str]:
    """اسم عربي لكل حلقة من نوعها ولغتها («ترجمة إنجليزية»، «ملخص»)، بدل التسمية التقنية التي كتبها المستخدم."""
    names = {"source": "الأصل"}
    base = {}
    for i, v in enumerate(report.versions, 1):
        m = MEDIUM_AR.get(v.medium or "", "")
        if not m or v.medium == "other":
            base[v.label] = f"النسخة {i}"
        elif v.medium == "translation":
            base[v.label] = f"ترجمة {LANG_ADJ.get(v.lang, v.lang)}".strip()
        else:
            base[v.label] = m
    seen: dict[str, int] = {}
    for v in report.versions:
        b = base[v.label]
        k = seen[b] = seen.get(b, 0) + 1
        names[v.label] = b if k == 1 else f"{b} {ORDINAL[k - 1] if k <= len(ORDINAL) else k}"
    return names


def name_text(report, text: str) -> str:
    """يستبدل التسميات التقنية داخل نصوص محفوظة («قارئ summary يفهم») بأسماء الحلقات العربية."""
    for lb, nm in sorted(version_names(report).items(), key=lambda x: -len(x[0])):
        if lb != "source":
            text = text.replace(f"قارئ {lb} ", f"قارئ {nm} ").replace(f"، {lb}: ", f"، {nm}: ")
    return text


def thread(report) -> list[dict]:
    """عقد خيط السند: الأصل ثم الحلقات، وحالة كل عقدة.

    state: ok (المعنى سليم) | break (دخل الخلل هنا) | after (بعد الخلل) ؛ recheck: بعد حلقة عُدّلت صياغتها.
    """
    broken = {a.introduced_at for a in report.alerts if a.severity.value != "info"}
    edited = {a.version_label for a in report.alerts
              if (d := report.decisions.get(a.id)) and d.action == "edit"}
    marks: dict[str, list[str]] = {}
    for a in report.alerts:
        if a.severity.value != "info":
            w = mark_word(a.type.value)
            if w not in marks.setdefault(a.introduced_at, []):
                marks[a.introduced_at].append(w)
    nodes = [{"label": "source", "name": "الأصل", "lang": report.source.lang, "parent": None, "medium": "",
              "state": "break" if "source" in broken else "ok", "recheck": False, "marks": marks.get("source", [])}]
    by_label = {"source": nodes[0]}
    names = version_names(report)
    for v in report.versions:
        parent = by_label.get(v.derived_from, nodes[0])
        state = "break" if v.label in broken else ("after" if parent["state"] != "ok" else "ok")
        node = {"label": v.label, "name": names[v.label], "lang": v.lang, "parent": v.derived_from,
                "parent_name": names.get(v.derived_from or "source", ""), "state": state,
                "medium": MEDIUM_AR.get(v.medium or "", ""),
                "recheck": parent["label"] in edited or parent["recheck"], "marks": marks.get(v.label, [])}
        nodes.append(node)
        by_label[v.label] = node
    return nodes


def status_line(report) -> dict:
    """حالة التقرير نصاً صريحاً: «لا تنشر · 2 سقط» أو «يُنظر · 3 مواضع» أو «جاهز للنشر بعد نظرتك»."""
    pending = [g for g in group_alerts(report.alerts)
               if any(x.id not in report.decisions for x in [g["root"], *g["symptoms"]])]
    red = [g for g in pending if any(x.severity.value == "red" for x in [g["root"], *g["symptoms"]])]
    if red:
        counts: dict[str, int] = {}
        for g in red:
            w = mark_word(g["root"].type.value)
            counts[w] = counts.get(w, 0) + 1
        return {"tone": "rubric", "text": "لا تنشر · " + " · ".join(f"{n} {w}" for w, n in counts.items())}
    yellow = [g for g in pending if any(x.severity.value == "yellow" for x in [g["root"], *g["symptoms"]])]
    if yellow:
        n = len(yellow)
        return {"tone": "saffron", "text": f"يُنظر · {n} {'موضع' if n == 1 else 'مواضع'}"}
    return {"tone": "verified", "text": "جاهز للنشر بعد نظرتك"}


def lock_rows(report) -> dict:
    """حالة كل قفل في كل حلقة كسرته: منكسر، أو محفوظ بعد التصحيح، أو ما زال منكسراً بعد التصحيح.
    stale = حلقة صُحّحت ولم يُعد فحص أقفالها على نصها الحالي."""
    from app.export import approved_text

    texts = {v.label: approved_text(report, v.label, v.text) for v in report.versions}
    rows, stale = [], False
    for lock in report.locks:
        labels = [a.version_label for a in report.alerts
                  if a.type == T.lock_violated and a.source_span and a.source_span.text == lock.span_text]
        where = []
        for lb in labels:
            text, applied = texts.get(lb, ("", False))
            rc = report.locks_corrected.get(lb)
            if applied and rc and rc.text == text:
                state = "still" if lock.span_text in rc.still_broken else "fixed"
            else:
                state = "broken"
                stale = stale or applied
            where.append({"label": lb, "state": state})
        if not where:
            tag = ("verified", "صح")
        elif all(w["state"] == "fixed" for w in where):
            tag = ("verified", "حُفظ بعد التصحيح")
        elif any(w["state"] == "still" for w in where):
            tag = ("rubric", "ما زال منكسراً بعد التصحيح")
        else:
            tag = ("rubric", "انكسر")
        rows.append({"lock": lock, "tone": tag[0], "tag": tag[1], "where": where})
    return {"rows": rows, "stale": stale}


def _exam_state(q, src: int | None, ans: int | None) -> str:
    """same = فهم كقارئ الأصل · silent = النسخة سكتت عمّا يذكره الأصل · diff = فهم مختلف · none = لا إجابة."""
    from app.pipeline.reader_exam import NOT_STATED

    if ans is None or src is None:
        return "none"
    if ans == src:
        return "same"
    return "silent" if q.options[ans] == NOT_STATED else "diff"


def exam_view(report) -> dict:
    """امتحان القارئ مرتباً للعرض: لكل سؤال إجابة قارئ الأصل وإجابة قارئ كل حلقة وحالتها،
    ولكل حلقة عدد ما فهمه قارئها كما فهمه قارئ الأصل (قبل التصحيح وبعده إن أُعيد الامتحان)."""
    from app.export import approved_text

    ex = report.reader_exam
    if not ex or not ex.questions:
        return {"questions": [], "versions": [], "stale": False}
    src = ex.answers.get("source") or []
    versions, stale = [], False
    for v in report.versions:
        text, applied = approved_text(report, v.label, v.text)
        fresh = bool(applied) and ex.corrected_text.get(v.label) == text and v.label in ex.corrected
        stale = stale or (bool(applied) and not fresh)
        versions.append({"label": v.label, "medium": MEDIUM_AR.get(v.medium or "", ""),
                         "answers": ex.answers.get(v.label) or [],
                         "after": (ex.corrected.get(v.label) or []) if fresh else None})
    questions = []
    for i, q in enumerate(ex.questions):
        s = src[i] if i < len(src) else None
        rows = []
        for v in versions:
            a = v["answers"][i] if i < len(v["answers"]) else None
            row = {"label": v["label"], "medium": v["medium"], "state": _exam_state(q, s, a),
                   "answer": q.options[a] if a is not None else "", "after": None}
            if v["after"] is not None:
                b = v["after"][i] if i < len(v["after"]) else None
                row["after"] = {"state": _exam_state(q, s, b), "answer": q.options[b] if b is not None else ""}
            rows.append(row)
        questions.append({"text": q.question_ar, "source": q.options[s] if s is not None else "", "rows": rows})
    total = len(questions)
    for k, v in enumerate(versions):
        v["same"] = sum(1 for q in questions if q["rows"][k]["state"] == "same")
        v["same_after"] = (sum(1 for q in questions if (q["rows"][k]["after"] or {}).get("state") == "same")
                           if v["after"] is not None else None)
        v["total"] = total
    return {"questions": questions, "versions": versions, "stale": stale}


# الدليل بلغة يفهمها المراجع: لا أسماء حقول داخلية ولا أسطر فارغة
FIELD_AR = {
    "certainty": "درجة اليقين", "ruling": "نوع الحكم", "attribution.to": "نسبة القول",
    "attribution.form": "صيغة النسبة", "scope.restricted_to": "نطاق الحكم", "restriction_hasr": "أداة الحصر",
    "consensus_claim": "دعوى الإجماع", "disagreement_stated": "ذكر الخلاف بين العلماء",
    "hadith_mentions.grade_stated": "درجة الحديث", "negations": "عدد أدوات النفي", "numbers": "الأرقام",
    "conditions": "الشرط", "exceptions": "الاستثناء",
}
VALUE_AR = {
    "definite": "قطعي", "probable": "راجح", "possible": "محتمل", "unstated": "غير مذكور",
    "obligatory": "واجب", "recommended": "مستحب", "permissible": "مباح", "disliked": "مكروه",
    "forbidden": "محرّم", "allah": "الله تعالى", "prophet": "النبي ﷺ", "companion": "صحابي",
    "scholar": "عالم", "author": "الكاتب", "religion": "الإسلام نفسه", "tamrid": "صيغة تمريض (رُوي، قيل)",
    "assertive": "صيغة جزم", "some_scholars": "بعض العلماء", "majority": "الجمهور", "ijma": "الإجماع",
    "all": "الجميع", "some": "بعضهم", "specific": "فئة محددة", "unspecified": "غير محدد",
    "sahih": "صحيح", "hasan": "حسن", "daif": "ضعيف", "true": "موجود", "false": "غير موجود", "none": "لا يوجد",
}


def _val(field: str, v: str) -> str:
    v = (v or "").strip()
    if v in ("", "—"):
        return "غير مذكور"
    if field == "disagreement_stated" and v != "true":
        return "غير مذكور"
    return VALUE_AR.get(v, v)


def evidence_rows(alert, alert_report=None) -> list[dict]:
    """كل دليل ← {label, text}؛ يُسقط الأسطر التقنية التي لا تضيف للمراجع شيئاً."""
    rows = []
    for e in alert.evidence:
        detail = (e.detail or "").strip()
        if e.kind == "fingerprint" and " → " in detail:
            if e.ref not in FIELD_AR:
                continue
            before, after = detail.split(" → ", 1)
            rows.append({"label": FIELD_AR[e.ref],
                         "text": f"في الحلقة الأم: {_val(e.ref, before)} ← في النسخة: {_val(e.ref, after)}"})
        elif e.kind == "text_span" and e.ref.startswith("source:"):
            rows.append({"label": "في الأصل", "text": f"«{detail}»"})
        elif e.kind == "corpus":
            text = ("بحثنا في المدونة فلم نجد نصاً قريباً بما يكفي من هذه العبارة"
                    if e.ref in ("", "—") else detail or "لا مرجع في المدونة")
            rows.append({"label": "من مدونة مِرآة", "text": text})
        elif e.kind == "reader_exam":
            rows.append({"label": "امتحان القارئ", "text": name_text(alert_report, detail.replace(" | ", "، "))
                         if alert_report else detail.replace(" | ", "، ")})
        elif detail:
            rows.append({"label": "ملاحظة", "text": detail})
    return rows
