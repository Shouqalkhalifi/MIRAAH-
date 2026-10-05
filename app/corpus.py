"""محمّل المدونة المحلية data/corpus/*.jsonl مع التحقق من الحقول (CLAUDE.md 6.5)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import ROOT

CORPUS_DIR = ROOT / "data" / "corpus"
# المدونة الرسمية (scripts/import_official_corpus.py): المصحف كاملاً من مجمع الملك فهد، وأحاديث موسوعة HadeethEnc
CORPUS_FILES = ("quran.jsonl", "hadith.jsonl", "terms.jsonl", "quran_kfgqpc.jsonl", "hadith_hadeethenc.jsonl")


class CorpusItem(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["quran", "hadith", "term"]
    text_ar: str = Field(min_length=1)
    text_en: str = ""
    # صيغة المطابقة: النص الإملائي للآية حين يكون text_ar بالرسم العثماني («الصلاة» لا «ٱلصَّلَوٰةَ»)
    text_match: str = ""
    grade: Optional[Literal["sahih", "hasan", "daif", "mawdu"]] = None
    source_name: str = Field(min_length=1)
    source_url: str = ""
    license_note: str = Field(min_length=1)
    # للمصطلحات فقط (ضابط الاستخدام): صيغ المصطلح في النص الأم، والترجمات التي تخالف ضابطه في النسخة
    trigger_forms: list[str] = Field(default_factory=list)
    avoid_renderings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _grade_for_hadith(self) -> "CorpusItem":
        if self.type == "hadith" and self.grade is None:
            raise ValueError("عنصر الحديث يجب أن يحمل درجته (grade)")
        if self.type == "term" and bool(self.trigger_forms) != bool(self.avoid_renderings):
            raise ValueError("ضابط المصطلح يحتاج trigger_forms و avoid_renderings معاً")
        return self


class CorpusError(ValueError):
    pass


def load_file(path: Path) -> list[CorpusItem]:
    items: list[CorpusItem] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            items.append(CorpusItem.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as e:
            raise CorpusError(f"{path.name}:{n}: {e}") from e
    return items


_CACHE: dict[tuple, list[CorpusItem]] = {}


def load_corpus(directory: Path = CORPUS_DIR) -> list[CorpusItem]:
    """تُقرأ الملفات مرة واحدة ما دامت لم تتغيّر (آلاف الآيات والأحاديث)، ويُعاد نسخة من القائمة."""
    stamp = tuple((n, p.stat().st_mtime_ns, p.stat().st_size) for n in CORPUS_FILES if (p := directory / n).exists())
    key = (str(directory), stamp)
    if key not in _CACHE:
        if len(_CACHE) > 8:
            _CACHE.clear()
        _CACHE[key] = _load(directory)
    return list(_CACHE[key])


def _load(directory: Path) -> list[CorpusItem]:
    items: list[CorpusItem] = []
    for name in CORPUS_FILES:
        p = directory / name
        if p.exists():
            items.extend(load_file(p))
    dupes = {i for i, n in Counter(x.id for x in items).items() if n > 1}
    if dupes:
        raise CorpusError(f"معرّفات مكررة في المدونة: {sorted(dupes)}")
    return items
