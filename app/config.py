"""إعدادات المشروع من متغيرات البيئة (.env). لا أسرار في الكود."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    anthropic_api_key: str
    main_model: str
    witness_a_model: str
    witness_b_model: str
    llm_max_tokens: int
    llm_timeout_seconds: float
    llm_effort: str
    llm_cache: bool
    database_path: Path
    port: int

    def model_for(self, role: str) -> str:
        return {
            "main": self.main_model,
            "witness_a": self.witness_a_model,
            "witness_b": self.witness_b_model,
        }[role]


def get_settings() -> Settings:
    db = Path(os.getenv("DATABASE_PATH", "data/runtime/miraah.db"))
    if not db.is_absolute():
        db = ROOT / db
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        main_model=os.getenv("MAIN_MODEL", ""),
        witness_a_model=os.getenv("WITNESS_A_MODEL", "") or os.getenv("MAIN_MODEL", ""),
        witness_b_model=os.getenv("WITNESS_B_MODEL", ""),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "16000")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        llm_effort=os.getenv("LLM_EFFORT", "medium"),
        llm_cache=os.getenv("LLM_CACHE", "on").lower() not in ("off", "0", "false"),
        database_path=db,
        port=int(os.getenv("PORT", "8000")),
    )
