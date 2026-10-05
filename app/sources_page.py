"""بيانات صفحة «مصادر مِرآة» (/sources): كل ما يرجع إليه الميزان والفهم، بأعداده من المدونة نفسها لا من نص ثابت."""
from __future__ import annotations

from app import madhahib
from app.corpus import load_corpus
from app.library import load_library


def overview() -> dict:
    items = load_corpus()
    count = lambda pred: sum(1 for i in items if pred(i))  # noqa: E731
    return {
        "quran_verses": count(lambda i: i.id.endswith("-kfgqpc")),
        "hadith_he": count(lambda i: i.id.startswith("h-he-")),
        "hadith_salah": count(lambda i: i.id.startswith("h-salah-")),
        "hadith_sahih": count(lambda i: i.id.startswith("h-he-") and i.grade == "sahih"),
        "hadith_hasan": count(lambda i: i.id.startswith("h-he-") and i.grade == "hasan"),
        "terms": count(lambda i: i.type == "term"),
        "issues": len(load_library()),
        "madhahib": madhahib.madhahib(),
        "fiqh": madhahib.load(),
    }
