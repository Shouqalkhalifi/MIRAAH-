"""محمّل المدونة المحلية data/corpus/*.jsonl مع التحقق من الحقول (CLAUDE.md 6.5)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import ROOT

CORPUS_DIR = ROOT / "data" / "corpus"
CORPUS_FILES = ("quran.jsonl", "hadith.jsonl", "terms.jsonl")


class CorpusItem(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["quran", "hadith", "term"]
    text_ar: str = Field(min_length=1)
    text_en: str = ""
    grade: Optional[Literal["sahih", "hasan", "daif", "mawdu"]] = None
    source_name: str = Field(min_length=1)
    source_url: str = ""
    license_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def _grade_for_hadith(self) -> "CorpusItem":
        if self.type == "hadith" and self.grade is None:
            raise ValueError("عنصر الحديث يجب أن يحمل درجته (grade)")
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


def load_corpus(directory: Path = CORPUS_DIR) -> list[CorpusItem]:
    items: list[CorpusItem] = []
    for name in CORPUS_FILES:
        p = directory / name
        if p.exists():
            items.extend(load_file(p))
    ids = [i.id for i in items]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise CorpusError(f"معرّفات مكررة في المدونة: {sorted(dupes)}")
    return items
