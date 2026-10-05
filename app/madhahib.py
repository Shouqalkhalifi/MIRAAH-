"""المذاهب الفقهية الأربعة مراجعَ للتحقق، لا أحكاماً (data/sources/madhahib.json).

مِرآة لا تملك أقوال المذاهب في المسائل، ولا ترجّح بينها. فإن نُسب قول إلى مذهب («عند الحنفية»، "the Hanbali school")
فهي نسبة لم نتحقق منها، ويُحال القارئ إلى كتب المذهب كما سمّتها الموسوعة الفقهية في الدرر السنية.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from app.config import ROOT
from app.text.normalize import normalize_ar

PATH = ROOT / "data" / "sources" / "madhahib.json"

# صيغ النسبة بعد التطبيع (ة←ه، أ←ا، ى←ي). «مالك» وحده لا يكفي لأنه في «مالك يوم الدين».
_CUES = {
    "hanafi": r"الحنفيه|الاحناف|المذهب الحنفي|ابو حنيفه|ابي حنيفه|hanafis?\b|abu hanifa",
    "maliki": r"المالكيه|المذهب المالكي|الامام مالك|قال مالك|عند مالك|malikis?\b|imam malik",
    "shafii": r"الشافعيه|المذهب الشافعي|الامام الشافعي|قال الشافعي|عند الشافعي|shafi['‘’`]?i(?:s|tes?)?\b",
    "hanbali": r"الحنابله|المذهب الحنبلي|الامام احمد|ابن حنبل|hanbalis?\b|ibn hanbal|imam ahmad",
}
_RX = {k: re.compile(v, re.I) for k, v in _CUES.items()}

NOT_VERIFIED_AR = "مكتبة مِرآة لا تنقل أقوال المذاهب في المسائل، فلم نتحقق من هذه النسبة"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def madhahib() -> list[dict]:
    return load()["madhahib"]


def by_id(mid: str) -> dict:
    return next(m for m in madhahib() if m["id"] == mid)


def find(text: str) -> list[tuple[str, str]]:
    """[(id المذهب، الصيغة كما وردت)] لكل مذهب نُسب إليه شيء في النص."""
    t = normalize_ar(text)
    out = []
    for mid, rx in _RX.items():
        m = rx.search(t)
        if m:
            out.append((mid, m.group(0)))
    return out


def books_line(mid: str, n: int = 3) -> str:
    """«المذهب الحنفي — من مراجعه: المبسوط للسرخسي، …» من قائمة الدرر السنية."""
    m = by_id(mid)
    books = "، ".join(f"«{b['title']}» ({b['author'].split('،')[0]})" for b in m["books"][:n])
    return f"{m['name_ar']} — من مراجعه في الموسوعة الفقهية بالدرر السنية: {books}"
