"""الأمثلة الجاهزة (data/examples/*.json) — اصطناعية بالكامل."""
from __future__ import annotations

import json

from pydantic import BaseModel

from app.config import ROOT
from app.service import AnalyzeRequest

EXAMPLES_DIR = ROOT / "data" / "examples"


class Example(BaseModel):
    name: str
    title: str
    description: str
    review_note: str = ""
    request: AnalyzeRequest


def load_examples() -> list[Example]:
    return [Example.model_validate(json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(EXAMPLES_DIR.glob("*.json"))]


def get_example(name: str) -> Example | None:
    return next((e for e in load_examples() if e.name == name), None)
