"""تقرير المقابلة PDF: الترتيب نفسه لتقرير HTML، بخط أميري مع تشكيل الحروف العربية واتجاهها (HarfBuzz)."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.export import LANG_AR

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
NAVY, PURPLE, MUTED = (18, 24, 63), (97, 80, 234), (91, 96, 128)
LINE, BANNER_LINE = (221, 224, 240), (240, 214, 138)
SEVERITY = {"red": (229, 72, 77), "yellow": (217, 162, 27), "info": (138, 144, 176)}
RTL = {"ar", "ur"}
PAD = 3.5


class _Doc(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4")
        self.footer_text = footer_text
        self.add_font("Amiri", "", str(FONTS / "Amiri-Regular.ttf"))
        self.add_font("Amiri", "B", str(FONTS / "Amiri-Bold.ttf"))
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, 20)
        self.set_title("تقرير مقابلة")
        self.set_creator("مِرآة MIRAAH")

    def footer(self):
        self.set_y(-14)
        _write(self, f"{self.footer_text} · صفحة {self.page_no()}", 8.5, MUTED, align="C")


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


def _heading(p, text: str) -> None:
    if p.y > p.page_break_trigger - 65:  # لا يبقى العنوان وحده أسفل الصفحة
        p.add_page()
    p.ln(5)
    _write(p, text, 13.5, NAVY, bold=True)
    p.set_draw_color(*PURPLE)
    p.set_line_width(0.6)
    p.line(p.l_margin, p.y + 0.5, p.l_margin + p.epw, p.y + 0.5)
    p.ln(3)


def _box(p, lines: list[tuple], border=LINE, accent=None) -> None:
    """صندوق لا ينقسم بين صفحتين: يُقاس ارتفاعه أولاً. كل سطر: (النص، الحجم، اللون، عريض؟، rtl؟)."""
    inner = p.epw - 2 * PAD
    h = 2 * PAD - 1 + sum(_height(p, t, s, b, rtl, inner) for t, s, _, b, rtl in lines)
    if p.y + h > p.page_break_trigger:
        p.add_page()
    top = p.y
    p.set_line_width(0.3)
    p.set_draw_color(*border)
    p.rect(p.l_margin, top, p.epw, h, style="D")
    if accent:
        p.set_fill_color(*accent)
        p.rect(p.l_margin + p.epw - 1.4, top, 1.4, h, style="F")
    p.ln(PAD)
    for text, size, color, bold, rtl in lines:
        _write(p, text, size, color, bold, rtl, x=p.l_margin + PAD, w=inner)
    p.set_y(top + h + 2.5)


def render(d: dict) -> bytes:
    p = _Doc(d["disclaimer"])
    p.add_page()

    _write(p, d["title"], 17, NAVY, bold=True)
    _write(p, f"{d['report_title'] or 'مقابلة'} · مِرآة MIRAAH", 10.5, MUTED)
    p.ln(2)
    meta = [("مرجع المصدر", d["source"]["source_ref"] or "غير مسجّل"),
            ("مستوى المحتوى", d["source"]["content_level"]),
            ("تاريخ التصدير", d["approved_at"]),
            ("رقم التقرير", d["report_id"])]
    for label, value in meta:
        y = p.y
        _write(p, label, 10.5, MUTED, x=p.l_margin + p.epw - 32, w=32)
        p.set_y(y)
        _write(p, value, 10.5, NAVY, bold=True, w=p.epw - 35)
    p.ln(2)
    _box(p, [("هذا التقرير سجلّ داخلي لقرارات المراجعة. ليس شهادة اعتماد عامة، ولا يُصدر حكماً شرعياً.",
              10.5, NAVY, False, True)], border=BANNER_LINE, accent=BANNER_LINE)

    _heading(p, "المصدر")
    _box(p, [(d["source"]["text"], 12.5, NAVY, False, d["source"]["lang"] in RTL)])

    _heading(p, "حلقات السلسلة")
    for i, n in enumerate(d["chain"], 1):
        parts = [f"{i}. {n['name']}", LANG_AR.get(n["lang"], n["lang"])]
        if n["derived_from"]:
            parts.append("عن " + ("الأصل" if n["derived_from"] == "source" else n["derived_from"]))
        broken = n["state"] == "break"
        if broken:
            parts.append("دخل هنا الخلل")
        _write(p, "\u200f" + " · ".join(parts), 11, SEVERITY["red"] if broken else NAVY, bold=broken)

    _heading(p, "النص المصحَّح لكل حلقة")
    for n in d["chain"]:
        if n["label"] == "source":
            note = "الأصل لا يُعدَّل"
        elif n["applied_edits"]:
            note = f"طُبّقت {len(n['applied_edits'])} صياغة اعتمدها المراجع"
        else:
            note = "بلا تعديل"
        _box(p, [("\u200f" + f"{n['name']} · {LANG_AR.get(n['lang'], n['lang'])} · {note}", 9.5, MUTED, False, True),
                 (n["approved_text"], 12, NAVY, False, n["lang"] in RTL)],
             accent=PURPLE if n["applied_edits"] else None)

    _heading(p, "التنبيهات وما تم في كل منها")
    if not d["alerts"]:
        _write(p, "لم تُسجَّل تنبيهات على هذه المقابلة.", 11)
    for a in d["alerts"]:
        where = "الأصل" if a["introduced_at"] == "source" else a["introduced_at"]
        lines = [(f"[{a['severity_ar']}] {a['headline_ar']}", 11.5, NAVY, True, True),
                 ("\u200f" + f"في {a['version_label']} · دخل في {where}", 9.5, MUTED, False, True),
                 (a["explanation_ar"], 10.5, NAVY, False, True)]
        dec = a["decision"]
        if dec:
            lines.append(("القرار: " + dec["action_ar"], 10.5, PURPLE, True, True))
            if dec["edited_text"]:
                lines.append(("الصياغة المعتمدة:", 10, MUTED, False, True))
                lines.append((dec["edited_text"], 10.5, NAVY, False, not dec["edited_text"].isascii()))
            if dec["reason"]:
                lines.append(("السبب: " + dec["reason"], 10.5, NAVY, False, True))
            lines.append((dec["decided_at"], 9, MUTED, False, True))
        else:
            lines.append(("بلا قرار (ليس تنبيهاً خطيراً)", 10, (154, 107, 0), False, True))
        _box(p, lines, accent=SEVERITY.get(a["severity"]))

    return bytes(p.output())
