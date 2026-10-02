"""مكتبة المسائل لميزة «قابِل ما قرأت» (data/library/issues.jsonl).

كل مسألة: عنوانها، ومستواها، وكلماتها المفتاحية، ومصادرها الحرفية، والموقف كما تذكره المصادر.
يُرفض تحميل أي مسألة ينقصها level، أو ينقص أحد مصادرها text_ar أو url.
المحتوى الحقيقي تملؤه المطوّرة من المصادر الرسمية؛ ولا يُكتب فيها شيء من ذاكرة النموذج.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import ROOT

LIBRARY_PATH = ROOT / "data" / "library" / "issues.jsonl"

Ruling = Literal["wajib", "mustahab", "mubah", "makruh", "haram", "none"]
# رموز المكتبة ← قيم بصمة المعنى
RULING_TO_FP = {"wajib": "obligatory", "mustahab": "recommended", "mubah": "permissible",
                "makruh": "disliked", "haram": "forbidden", "none": "none"}
RULING_AR = {"wajib": "واجباً", "mustahab": "مستحباً", "mubah": "مباحاً", "makruh": "مكروهاً",
             "haram": "محرّماً", "none": "غير مذكور"}


class LibrarySource(BaseModel):
    type: Literal["quran", "hadith", "fiqh", "term"]
    text_ar: str = Field(min_length=1)  # نص حرفي من المصدر
    translation_en: str = ""  # الترجمة المعتمدة
    translation_source: str = ""
    url: str = Field(min_length=1)
    grade: str = ""

    @field_validator("text_ar", "url")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("حقل إلزامي فارغ")
        return v


class Position(BaseModel):
    ruling: Ruling = "none"
    scope: str = ""
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    khilaf: bool = False
    opinions: list[str] = Field(default_factory=list)  # كما تذكرها المصادر فقط


class Issue(BaseModel):
    id: str = Field(min_length=1)
    title_ar: str = ""
    title_en: str = ""
    level: Literal["أ", "ب", "ج"]
    keywords_ar: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    sources: list[LibrarySource] = Field(min_length=1)
    position: Position = Field(default_factory=Position)
    reviewed: bool = False
    reviewed_by: str = ""

    @property
    def is_placeholder(self) -> bool:
        return not self.reviewed or "TODO" in (self.title_ar + self.title_en)


class LibraryError(ValueError):
    pass


def load_library(path: Path = LIBRARY_PATH) -> list[Issue]:
    if not path.exists():
        return []
    issues: list[Issue] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            issues.append(Issue.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as e:
            raise LibraryError(f"{path.name}:{n}: مسألة مرفوضة: {e}") from e
    ids = [i.id for i in issues]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise LibraryError(f"معرّفات مكررة في المكتبة: {dupes}")
    return issues


@lru_cache(maxsize=1)
def default_library() -> tuple[Issue, ...]:
    return tuple(load_library())
