"""حدّ بسيط لمعدل الطلبات التي تستدعي النموذج، لكل عنوان IP، في الذاكرة.

يحمي رصيد الـAPI في النسخة المنشورة. RATE_LIMIT_PER_HOUR=0 يعطّله. الأمثلة الجاهزة لا تُحتسب لأنها من الـcache.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

MESSAGE = "بلغتَ حدّ الاستخدام في هذه النسخة التجريبية ({n} طلباً في الساعة). أعد المحاولة بعد قليل، أو جرّب الأمثلة الجاهزة."
WINDOW = 3600.0

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def per_hour() -> int:
    return int(os.getenv("RATE_LIMIT_PER_HOUR", "30") or 0)


def client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")  # خلف وكيل الاستضافة (Render / HF)
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check(request: Request) -> None:
    """يرفع 429 إن تجاوز العنوان الحد. يُستخدم Depends في مسارات الواجهة البرمجية."""
    if not allow(client_key(request)):
        raise HTTPException(429, MESSAGE.format(n=per_hour()))


def allow(key: str) -> bool:
    n = per_hour()
    if n <= 0:
        return True
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= n:
            return False
        q.append(now)
        return True


def reset() -> None:
    with _lock:
        _hits.clear()
