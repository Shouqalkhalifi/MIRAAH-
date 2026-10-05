"""يولّد حالات التقييم من data/eval/seeds.jsonl (CLAUDE.md القسم 9).

ثلاثة أنواع من الحالات:
1. mutation: لكل بذرة ولكل نوع تغيّر في targets: ترجمة إنجليزية فيها **تغيّر واحد مزروع** من ذلك النوع.
2. faithful: لكل بذرة: صياغة إنجليزية **سليمة المعنى** (مختلفة الألفاظ) لقياس الإنذارات الكاذبة.
3. abstention: أقوال تُنسب إلى النبي ﷺ وليست في المدونة المحلية، لقياس صحة الامتناع («غير متحقق»).

التشغيل:  python eval/generate_cases.py   ← يكتب data/eval/cases.jsonl
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

from app.llm import get_llm  # noqa: E402

SEEDS = ROOT / "data" / "eval" / "seeds.jsonl"
CASES = ROOT / "data" / "eval" / "cases.jsonl"

# تعليمات زرع كل نوع (تغيّر واحد فقط، وكل ما عداه أمين)
PLANT = {
    "condition_dropped": "Remove the condition or restriction on who/when the statement applies.",
    "exception_dropped": "Remove the exception (the group or case that is excluded).",
    "certainty_raised": "Present the possible/probable claim as certain and definite.",
    "attribution_upgraded": "Turn the reported/weakened attribution ('it is reported', 'it is said') into a direct, certain assertion.",
    "new_prophetic_attribution": "Attribute the statement to the Prophet ﷺ ('The Prophet ﷺ said: ...') although the source does not attribute it to him.",
    "ruling_shift": "Change the ruling category (e.g. recommended -> obligatory, disliked -> forbidden, permissible -> obligatory, forbidden -> permissible).",
    "scope_widened": "Make the statement apply to everyone / all Muslims instead of the specific group or the 'some' in the source.",
    "scope_narrowed": "Restrict the statement to a narrower group than the source.",
    "hasr_lost": "Remove the exclusive restriction ('only') while keeping the rest.",
    "consensus_inflated": "Claim scholarly consensus ('all scholars agree') instead of the majority / some scholars.",
    "hadith_grade_dropped": "Omit the stated grade of the hadith.",
    "negation_mismatch": "Remove one negation (or add one) so that part of the meaning flips.",
    "number_mismatch": "Change the number to a different number.",
    "term_narrowing": "Render the key term with a stronger forbidden equivalent (e.g. 'disliked' -> 'forbidden', 'sunnah' -> 'obligatory').",
}

SYSTEM_MUTATE = """You create evaluation data for a meaning-preservation checker. Given an Arabic passage and a faithful English translation, write ONE English version that contains exactly ONE meaning change of the requested kind, and is otherwise faithful and natural. Do not add any other change. Return JSON {"text": "...", "change": "short description of what you changed"}."""

SYSTEM_PARAPHRASE = """You create evaluation data. Given an Arabic passage and a faithful English translation, write a DIFFERENT English translation that preserves the meaning exactly (all conditions, exceptions, scope, certainty, attribution form, ruling, numbers, negations, grades, consensus claims), using different wording and sentence structure. Return JSON {"text": "..."}."""

# أقوال تُنسب كثيراً إلى النبي ﷺ وليست في المدونة المحلية (تراجعها المطوّرة). الامتناع الصحيح: «غير متحقق».
ABSTENTION = [
    ("a01", "من الأقوال المشهورة: «العلم في الصغر كالنقش على الحجر».", "Knowledge in childhood is like engraving on stone."),
    ("a02", "من العبارات المتداولة: «حب الوطن من الإيمان».", "Love of one's homeland is part of faith."),
    ("a03", "من العبارات المتداولة: «النظافة من الإيمان».", "Cleanliness is part of faith."),
    # a04 كانت «الطهور شطر الإيمان»، وهو حديث صحيح (مسلم 223) دخل المدونة مع موسوعة HadeethEnc في 10-05، فصار الامتناع
    # فيه خطأً لا صواباً؛ استُبدل بقول متداول ليس في المدونة.
    ("a04", "من العبارات المتداولة: «اطلبوا العلم ولو في الصين».", "Seek knowledge even if it is in China."),
]


class _Mutation(BaseModel):
    text: str
    change: str = ""


class _Paraphrase(BaseModel):
    text: str


def _prompt(seed: dict, extra: str) -> str:
    return f"ARABIC:\n{seed['text_ar']}\n\nFAITHFUL ENGLISH:\n{seed['faithful_en']}\n\n{extra}"


def mutation(llm, seed: dict, kind: str) -> dict:
    res = llm.complete_json(_prompt(seed, f"REQUESTED CHANGE ({kind}): {PLANT[kind]}"), _Mutation,
                            system=SYSTEM_MUTATE, purpose="eval_generate")
    return {"id": f"{seed['id']}-{kind}", "seed": seed["id"], "kind": "mutation", "expected": [kind],
            "source": seed["text_ar"], "level": seed["content_level"], "reference_en": seed["faithful_en"],
            "version": res.text.strip(), "change": res.change}


def faithful(llm, seed: dict) -> dict:
    res = llm.complete_json(_prompt(seed, "Write the meaning-preserving paraphrase."), _Paraphrase,
                            system=SYSTEM_PARAPHRASE, purpose="eval_generate")
    return {"id": f"{seed['id']}-faithful", "seed": seed["id"], "kind": "faithful", "expected": [],
            "source": seed["text_ar"], "level": seed["content_level"], "reference_en": seed["faithful_en"],
            "version": res.text.strip(), "change": ""}


def abstention_cases() -> list[dict]:
    return [{"id": aid, "seed": aid, "kind": "abstention", "expected": ["unverified_attribution"],
             "source": ar, "level": "A", "reference_en": en,
             "version": f'The Prophet ﷺ said: "{en}"', "change": "attributed to the Prophet ﷺ"}
            for aid, ar, en in ABSTENTION]


def main() -> None:
    seeds = [json.loads(l) for l in SEEDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    unknown = {t for s in seeds for t in s["targets"]} - set(PLANT)
    if unknown:
        raise SystemExit(f"أنواع غير معروفة في targets: {unknown}")
    llm = get_llm()
    jobs = [(mutation, s, k) for s in seeds for k in s["targets"]] + [(faithful, s, None) for s in seeds]
    with ThreadPoolExecutor(4) as ex:
        cases = list(ex.map(lambda j: j[0](llm, j[1], j[2]) if j[2] else j[0](llm, j[1]), jobs))
    cases += abstention_cases()
    with CASES.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    kinds = {k: sum(c["kind"] == k for c in cases) for k in ("mutation", "faithful", "abstention")}
    print(f"{len(cases)} cases -> {CASES.relative_to(ROOT)}  {kinds}")


if __name__ == "__main__":
    main()
