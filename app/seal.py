"""6.13 ختم المعنى: بصمات SHA-256 للنصوص، وبصمة الختم، ورمز QR (SVG بلا ملفات صور)."""
from __future__ import annotations

import hashlib
import io
import json
import re

import qrcode
import qrcode.image.svg

from app.models import Report


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_hashes(r: Report) -> list[tuple[str, str]]:
    return [("source", sha256(r.source.text))] + [(v.label, sha256(v.text)) for v in r.versions]


def seal_digest(r: Report) -> str:
    """بصمة واحدة تربط النصوص بالقرارات وتاريخ النشر: أي تغيير في أي منها يغيّرها."""
    payload = {
        "texts": text_hashes(r),
        "decisions": {k: [d.action, d.reason, d.edited_text] for k, d in sorted(r.decisions.items())},
        "published_at": r.published_at.isoformat() if r.published_at else None,
        "reviewer_role": r.reviewer_role,
    }
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    svg = re.sub(r"^<\?xml[^>]*>\s*", "", svg)
    return svg.replace("<svg ", '<svg role="img" aria-label="رمز QR لصفحة الختم" ', 1)
