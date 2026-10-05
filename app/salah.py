"""«تعلّم الصلاة · قابِل ذكرك»: خطوات الركعة من data/salah/steps.json، وكل ذكر وآية ومرجع من المدونة.

المحرك نفسه في مِرآة: النسخة (ما ينطقه المتعلّم) تُقابَل بأصلها (نص الذكر في المصدر). لذلك لا نص هنا ولا في
salah.js: الخطوة تحمل معرّفات المدونة فقط، والميزان يفحص كل ذكر قبل عرضه. ذكر لا يوجد في المدونة لا يُعرض نصه،
ويظهر مكانه NOT_FOUND_AR كما في بقية مِرآة.
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import ROOT
from app.corpus import CorpusItem, load_corpus
from app.pipeline.mizan import NOT_FOUND_AR, SUPPORTED_AT, default_mizan, in_order

STEPS_PATH = ROOT / "data" / "salah" / "steps.json"


def _ref(item: CorpusItem) -> dict:
    return {"id": item.id, "type": item.type, "text_ar": item.text_ar, "text_en": item.text_en,
            "grade": item.grade, "source_name": item.source_name, "source_url": item.source_url}


def mizan_status(item: CorpusItem) -> str:
    """يبحث الميزان عن نص الذكر في المدونة كما يبحث عن أي نص منسوب، فيتأكد أنه يجده بألفاظه وترتيبها."""
    # «الله أكبر» في مئات الأحاديث، فيكفي أن يكون عنصر الذكر بين النتائج بالتطابق الكافي، لا أن يكون أولها
    hits = default_mizan().search(item.text_ar, types=(item.type,), k=50)
    ok = any(h.item.id == item.id and h.containment >= SUPPORTED_AT for h in hits) and in_order(item.text_ar, item)
    return "supported" if ok else "unverified"


@lru_cache(maxsize=1)
def load_steps() -> list[dict]:
    corpus = {i.id: i for i in load_corpus()}
    raw = json.loads(STEPS_PATH.read_text(encoding="utf-8"))["steps"]
    steps = []
    for s in raw:
        found = [corpus[i] for i in s.get("dhikr", []) if i in corpus]
        missing = [i for i in s.get("dhikr", []) if i not in corpus]
        statuses = [mizan_status(i) for i in found]
        verified = bool(found) and not missing and all(x == "supported" for x in statuses)
        step = {k: v for k, v in s.items() if k not in ("dhikr", "refs", "wrong", "count_ref")}
        dhikr = " ".join(i.text_ar for i in found) if verified else ""
        cref = corpus.get(s.get("count_ref", ""))
        if dhikr and cref and s.get("times"):
            spoken = f" قل: {dhikr}، {s['times']}."
            step["say"] = s.get("say", "") + spoken
            if s.get("praise"):
                step["praise"] = s["praise"] + spoken
        step.update(
            dhikr=dhikr,
            count_ref=_ref(cref) if cref else None,
            dhikr_en=" ".join(i.text_en for i in found if i.text_en) if verified else "",
            sources=[_ref(i) for i in found],
            refs=[_ref(corpus[i]) for i in s.get("refs", []) if i in corpus],
            mizan="supported" if verified else "unverified",
            mizan_note="النص موجود في مدونة مِرآة بألفاظه وترتيبها" if verified else NOT_FOUND_AR,
            wrong=[{"has": w["has"], "where": w["where"], "text": corpus[w["id"]].text_ar}
                   for w in s.get("wrong", []) if w["id"] in corpus],
        )
        steps.append(step)
    return steps
