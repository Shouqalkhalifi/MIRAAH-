"""استدعاء واحد حي للنموذج للتحقق من الإعداد: python scripts/llm_smoke.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.llm import get_llm, usage_summary  # noqa: E402


class Echo(BaseModel):
    language: str
    sentence_count: int


def main() -> None:
    llm = get_llm()
    print("model:", llm.models["main"])
    out = llm.complete_json(
        "Text: «يجوز للمسافر أن يفطر في رمضان. ويجب عليه القضاء.»\n"
        "Report the language code of the text and how many sentences it has.",
        Echo, system="You are a precise text analyzer.", purpose="smoke")
    print("reply:", out.model_dump())
    print("usage:", usage_summary(get_engine()))


if __name__ == "__main__":
    main()
