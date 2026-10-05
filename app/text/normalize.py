"""تطبيع النص العربي للمقارنة والاسترجاع (لا يُستخدم لتعديل النص المعروض أبداً)."""
from __future__ import annotations

import re
import unicodedata

# التشكيل + الألف الخنجرية + علامات المصحف
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]")
_TATWEEL = "ـ"
_ALEF = re.compile(r"[آأإٱٲٳ]")  # آ أ إ ٱ ...
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹०१२३४५६७८९", "012345678901234567890123456789")
_SPACES = re.compile(r"\s+")


def strip_diacritics(text: str) -> str:
    return _DIACRITICS.sub("", text).replace(_TATWEEL, "")


def normalize_ar(text: str) -> str:
    """إزالة التشكيل والتطويل، وتوحيد الهمزات والتاء المربوطة والألف المقصورة والأرقام.

    - NFKC أولاً لتحويل أشكال العرض العربية (U+FB50..U+FEFF) إلى حروفها الأساسية.
    - أ إ آ ٱ ← ا ، ؤ ← و ، ئ ← ي ، ة ← ه ، ى ← ي
    """
    t = unicodedata.normalize("NFKC", text)
    t = strip_diacritics(t)
    t = _ALEF.sub("ا", t)
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("ة", "ه").replace("ى", "ي")
    t = t.translate(_DIGITS)
    t = _SPACES.sub(" ", t).strip()
    return t.lower()


_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    """رموز مطبّعة (للـBM25 وحساب الطول)."""
    return _TOKEN.findall(normalize_ar(text))
