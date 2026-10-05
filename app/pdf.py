"""تقرير المراجعة PDF: الترتيب نفسه لتقرير HTML، بخط أميري مع تشكيل الحروف العربية واتجاهها (HarfBuzz)."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.export import LANG_AR

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
NAVY, PURPLE, TURQ, MUTED = (18, 24, 63), (97, 80, 234), (46, 242, 194), (91, 96, 128)
WHITE, LINE, PAPER, SOFT = (255, 255, 255), (221, 224, 240), (242, 244, 255), (248, 248, 252)
SEVERITY = {"red": (200, 45, 55), "yellow": (176, 120, 10), "info": (110, 116, 150)}
VERDICT = {"rubric": (180, 35, 47), "saffron": (150, 98, 10), "verified": (10, 120, 96)}
STATE = {"break": ("دخل هنا الخلل", SEVERITY["red"]), "after": ("ورثت الخلل", SEVERITY["yellow"]),
         "ok": ("سليمة", VERDICT["verified"])}
RTL = {"ar", "ur"}
PAD = 3.5


def tint(c: tuple, a: float = 0.1) -> tuple:
    return tuple(round(255 - (255 - v) * a) for v in c)


class _Doc(FPDF):
    def __init__(self, footer_text: str, ref: str):
        super().__init__(format="A4")
        self.footer_text, self.ref = footer_text, ref
        self.add_font("Amiri", "", str(FONTS / "Amiri-Regular.ttf"))
        self.add_font("Amiri", "B", str(FONTS / "Amiri-Bold.ttf"))
        self.add_font("NotoDeva", "", str(FONTS / "NotoSansDevanagari-Regular.ttf"))
        self.add_font("NotoDeva", "B", str(FONTS / "NotoSansDevanagari-Bold.ttf"))
        self.set_fallback_fonts(["NotoDeva"])  # أميري بلا حروف ديفاناغاري، فنص الحلقات الهندية يُكتب بهذا
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, 22)
        self.set_title("تقرير مراجعة مِرآة")
        self.set_creator("مِرآة MIRAAH")

    def header(self):
        if self.page_no() == 1:
            return
        y = 8
        self.set_y(y)
        _write(self, "تقرير مراجعة مِرآة", 9, MUTED, bold=True)
        self.set_y(y)
        _write(self, self.ref, 9, MUTED, rtl=False)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(self.l_margin, 14, self.l_margin + self.epw, 14)
        self.set_y(18)

    def footer(self):
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.h - 16, self.l_margin + self.epw, self.h - 16)
        self.set_y(-14)
        _write(self, self.footer_text, 8.5, MUTED)
        self.set_y(-14)
        _write(self, f"صفحة {self.page_no()}", 8.5, MUTED, align="L")


def _write(p, text: str, size: float = 11, color=NAVY, bold: bool = False, rtl: bool = True,
           x: float | None = None, w: float = 0, align: str | None = None) -> None:
    p.set_text_shaping(True, direction="rtl" if rtl else "ltr")
    p.set_font("Amiri", "B" if bold else "", size)
    p.set_text_color(*color)
    p.set_x(p.l_margin if x is None else x)
    p.multi_cell(w or p.epw, size * 0.62, text or "—", align=align or ("R" if rtl else "L"),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _height(p, text: str, size: float, bold: bool, rtl: bool, w: float) -> float:
    p.set_text_shaping(True, direction="rtl" if rtl else "ltr")
    p.set_font("Amiri", "B" if bold else "", size)
    return p.multi_cell(w, size * 0.62, text or "—", dry_run=True, output="HEIGHT")


def _cell(p, x: float, y: float, w: float, h: float, text: str, size: float = 10, color=NAVY,
          bold: bool = False, rtl: bool = True, align: str = "R") -> None:
    p.set_text_shaping(True, direction="rtl" if rtl else "ltr")
    p.set_font("Amiri", "B" if bold else "", size)
    p.set_text_color(*color)
    p.set_xy(x, y)
    p.cell(w, h, text, align=align)


def _heading(p, text: str, need: float = 40) -> None:
    """need: ارتفاع أول ما يلي العنوان، فلا يبقى العنوان وحده أسفل الصفحة."""
    if p.y + 18 + need > p.page_break_trigger:
        p.add_page()
    p.ln(6)
    top = p.y
    p.set_fill_color(*PURPLE)
    p.rect(p.l_margin + p.epw - 1.6, top + 0.8, 1.6, 6.2, style="F")
    _write(p, text, 14, NAVY, bold=True, w=p.epw - 4)
    p.ln(2.5)


def _heights(p, segments: list[tuple], inner: float) -> list[float]:
    return [2 * PAD - 1 + sum(_height(p, t, s, b, r, inner) for t, s, _, b, r in lines) for _, lines in segments]


def _card_height(p, segments: list[tuple], accent=True) -> float:
    return sum(_heights(p, segments, p.epw - 2 * PAD - (2 if accent else 0)))


def _card(p, segments: list[tuple], accent=None, border=LINE) -> None:
    """بطاقة لا تنقسم بين صفحتين، من مقاطع متتالية لكل منها لون خلفية.
    كل مقطع: (لون الخلفية أو None، [(النص، الحجم، اللون، عريض؟، rtl؟)])."""
    inner = p.epw - 2 * PAD - (2 if accent else 0)
    heights = _heights(p, segments, inner)
    total = sum(heights)
    if p.y + total > p.page_break_trigger and total < p.page_break_trigger - p.t_margin:
        p.add_page()
    top = y = p.y
    for (fill, lines), h in zip(segments, heights):
        if fill:
            p.set_fill_color(*fill)
            p.rect(p.l_margin, y, p.epw, h, style="F")
        p.set_y(y + PAD - 0.5)
        for text, size, color, bold, rtl in lines:
            _write(p, text, size, color, bold, rtl, x=p.l_margin + PAD, w=inner)
        y += h
    p.set_line_width(0.3)
    p.set_draw_color(*border)
    p.rect(p.l_margin, top, p.epw, total, style="D")
    if accent:
        p.set_fill_color(*accent)
        p.rect(p.l_margin + p.epw - 2, top, 2, total, style="F")
    p.set_y(top + total + 3)


def _cover(p, d: dict) -> None:
    band = 36
    p.set_fill_color(*NAVY)
    p.rect(0, 0, p.w, band, style="F")
    p.set_fill_color(*TURQ)
    p.rect(0, band, p.w, 1.2, style="F")
    p.set_y(9)
    _write(p, "تقرير مراجعة مِرآة", 21, WHITE, bold=True)
    _write(p, "للمراجعة قبل النشر", 11, TURQ)
    p.set_y(11)
    _write(p, "مِرآة", 20, WHITE, bold=True, align="L")
    _write(p, "MIRAAH", 9, tint(WHITE, 0.7), rtl=False)
    p.set_y(band + 7)
    _write(p, d["report_title"] or "مراجعة نص", 15, NAVY, bold=True)
    p.ln(3)

    cells = [("رقم التقرير", d["report_ref"], False),
             ("تاريخ التقرير (الرياض)", d["exported_at"].replace(" (بتوقيت الرياض)", ""), False),
             ("مستوى المحتوى", d["content_level_ar"], True),
             ("مرجع المصدر", d["source"]["source_ref"] or "غير مسجّل", True)]
    gap, n = 2.5, len(cells)
    w = (p.epw - gap * (n - 1)) / n
    h = max(6 + _height(p, v, 10.5, True, rtl, w - 4) for _, v, rtl in cells) + 3
    top = p.y
    for i, (label, value, rtl) in enumerate(cells):
        x = p.l_margin + p.epw - (i + 1) * w - i * gap
        p.set_fill_color(*PAPER)
        p.rect(x, top, w, h, style="F")
        p.set_y(top + 2)
        _write(p, label, 8.5, MUTED, x=x + 2, w=w - 4)
        _write(p, value, 10.5, NAVY, bold=True, rtl=rtl, x=x + 2, w=w - 4, align="R")
    p.set_y(top + h + 4)


def _verdict(p, d: dict) -> None:
    tone = VERDICT[d["verdict"]["tone"]]
    head, *rest = d["verdict"]["text"].split(" · ")
    counts = {k: 0 for k in ("red", "yellow", "info")}
    for a in d["alerts"]:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1
    lines = [(head, 19, tone, True, True)]
    if rest:
        lines.append(("\u200f" + " · ".join(rest), 11, NAVY, False, True))
    lines.append(("\u200f" + f"التنبيهات: {counts['red']} خطير · {counts['yellow']} متوسط · {counts['info']} للعلم",
                  10, MUTED, False, True))
    _card(p, [(tint(tone, 0.08), lines)], accent=tone, border=tint(tone, 0.35))
    _card(p, [(tint((240, 190, 60), 0.12), [(d["notice_ar"], 9.5, MUTED, False, True)])],
          border=tint((240, 190, 60), 0.4))


def _chain(p, d: dict) -> None:
    cols = [("#", 9), ("الحلقة", 44), ("اللغة", 26), ("مأخوذة عن", 70), ("الحالة", None)]
    widths = [w or p.epw - sum(c[1] for c in cols if c[1]) for _, w in cols]
    row = 8

    def draw(values, y, fill, size):
        if fill:
            p.set_fill_color(*fill)
            p.rect(p.l_margin, y, p.epw, row, style="F")
        x = p.l_margin + p.epw
        for (text, color, bold), w in zip(values, widths):
            x -= w
            p.set_font("Amiri", "B" if bold else "", size)
            while len(text) > 4 and p.get_string_width(text) > w - 3:
                text = text[:-2].rstrip() + "…"
            _cell(p, x + 1.5, y, w - 3, row, text, size, color, bold)

    if p.y + row * (len(d["chain"]) + 1) > p.page_break_trigger:
        p.add_page()
    top = y = p.y
    draw([(t, NAVY, True) for t, _ in cols], y, tint(PURPLE, 0.12), 9.5)
    for i, n in enumerate(d["chain"]):
        y += row
        label, color = STATE.get(n["state"], STATE["ok"])
        draw([(str(i + 1), MUTED, False), (n["name"], NAVY, True), (LANG_AR.get(n["lang"], n["lang"]), NAVY, False),
              (n["derived_from_name"] or "—", NAVY, False), (label, color, n["state"] != "ok")],
             y, SOFT if i % 2 else None, 10)
    p.set_draw_color(*LINE)
    p.set_line_width(0.3)
    p.rect(p.l_margin, top, p.epw, y + row - top, style="D")
    p.set_y(y + row + 3)


def render(d: dict) -> bytes:
    p = _Doc(d["disclaimer"], d["report_ref"])
    p.add_page()
    _cover(p, d)
    _verdict(p, d)

    _heading(p, "المصدر")
    _card(p, [(PAPER, [(d["source"]["text"], 13, NAVY, False, d["source"]["lang"] in RTL)])], accent=NAVY)

    _heading(p, "حلقات السلسلة", 8 * (len(d["chain"]) + 1))
    _chain(p, d)

    texts = []
    for n in d["chain"]:
        meta = [n["name"]] + ([n["medium_ar"]] if n["medium_ar"] and n["medium_ar"] not in n["name"] else []) \
            + [LANG_AR.get(n["lang"], n["lang"])]
        if n["applied_edits"]:
            meta.append(f"طُبّقت {len(n['applied_edits'])} صياغة اعتمدها المراجع")
        texts.append(([(SOFT, [("\u200f" + " · ".join(meta), 10, NAVY, True, True)]),
                       (None, [(n["approved_text"], 12, NAVY, False, n["lang"] in RTL)])],
                      SEVERITY["red"] if n["state"] == "break" else None))
    _heading(p, "نص كل حلقة", _card_height(p, texts[0][0]))
    for segs, accent in texts:
        _card(p, segs, accent=accent)

    cards = [_alert_card(a) for a in d["alerts"]]
    _heading(p, "التنبيهات", _card_height(p, cards[0][0]) if cards else 10)
    if not cards:
        _write(p, "لم تُسجَّل تنبيهات على هذا التقرير.", 11)
    for segs, accent in cards:
        _card(p, segs, accent=accent)

    if d.get("locks"):
        _heading(p, "أقفال المعنى")
        for lk in d["locks"]:
            ok = not lk["status_ar"].startswith(("انكسر", "ما زال"))
            where = "، ".join(w["name"] for w in lk["where"])
            color = VERDICT["verified"] if ok else SEVERITY["red"]
            _card(p, [(None, [(lk["status_ar"], 9.5, color, True, True),
                              ("\u200f" + f"«{lk['span_text']}» · قفل {lk['lock_type_ar']}"
                               + (f" · في {where}" if where else ""), 11, NAVY, False, True)])], accent=color)

    return bytes(p.output())


def _alert_card(a: dict) -> tuple[list, tuple]:
    sev = SEVERITY.get(a["severity"], MUTED)
    where = (f"في {a['version_name']} · دخل في {a['introduced_name']}"
             if a["version_name"] != a["introduced_name"] else f"دخل في {a['introduced_name']}")
    segs = [(tint(sev, 0.08), [("\u200f" + f"{a['severity_ar']} · {where}", 9.5, sev, True, True),
                               (a["headline_ar"], 12.5, NAVY, True, True)]),
            (None, [(a["explanation_ar"], 10.5, NAVY, False, True)])]
    if a.get("why_it_matters_ar"):
        segs.append((SOFT, [("لماذا يهم؟", 9.5, MUTED, True, True), (a["why_it_matters_ar"], 10, NAVY, False, True)]))
    for s in a.get("suggestions", [])[:1]:
        segs.append((tint(PURPLE, 0.07), [(f"صياغة مقترحة للاطلاع ({s['label_ar']})", 9.5, PURPLE, True, True),
                                          (s["text"], 10.5, NAVY, False, not s["text"].isascii())]))
    dec = a["decision"]
    if dec:
        lines = [("القرار: " + dec["action_ar"], 10, PURPLE, True, True)]
        if dec["edited_text"]:
            lines.append((dec["edited_text"], 10.5, NAVY, False, not dec["edited_text"].isascii()))
        if dec["reason"]:
            lines.append(("السبب: " + dec["reason"], 10, NAVY, False, True))
        lines.append((dec["decided_at"], 9, MUTED, False, True))
        segs.append((None, lines))
    return segs, sev
