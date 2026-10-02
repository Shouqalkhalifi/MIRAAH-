"""محرك SQLite المشترك (التقارير، cache النماذج، سجل الاستدعاءات)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine


def make_engine(path: Path | str) -> Engine:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30})
    # استيراد الجداول قبل الإنشاء حتى تُسجَّل في metadata
    from app import llm, models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


SEED_CACHE = Path(__file__).resolve().parent.parent / "data" / "seed" / "llm_cache.jsonl"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    import os

    from app.config import get_settings
    from app.llm import load_seed

    engine = make_engine(get_settings().database_path)
    if os.getenv("SEED_CACHE", "on").lower() not in ("off", "0", "false"):
        load_seed(engine, SEED_CACHE)
    return engine
