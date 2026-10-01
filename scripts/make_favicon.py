"""يولّد أيقونة الموقع (مرآة بألوان الهوية) بلا مكتبات خارجية: python scripts/make_favicon.py

- app/static/favicon.svg  (حادة بأي حجم)
- app/static/favicon.ico  (16 و32 و48 بكسل، صور PNG داخل حاوية ICO)
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"

NAVY, VIOLET, TEAL, PAPER = (0x12, 0x18, 0x3F), (0x61, 0x50, 0xEA), (0x2E, 0xF2, 0xC2), (0xF2, 0xF4, 0xFF)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#12183F"/>
  <ellipse cx="32" cy="32" rx="17" ry="23" fill="#F2F4FF" stroke="#6150EA" stroke-width="6"/>
  <path d="M24 26 L36 14" stroke="#2EF2C2" stroke-width="5" stroke-linecap="round"/>
  <path d="M24 38 L44 18" stroke="#2EF2C2" stroke-width="3" stroke-linecap="round" opacity=".7"/>
</svg>
"""


def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _color_at(x: float, y: float):
    """لون النقطة في إحداثيات 64×64 (نفس رسم SVG). يعيد (r, g, b, a)."""
    # مربع بزوايا مستديرة
    r = 14
    cx, cy = min(max(x, r), 64 - r), min(max(y, r), 64 - r)
    if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
        return (0, 0, 0, 0)
    for (ax, ay, bx, by, w) in ((24, 26, 36, 14, 2.5), (24, 38, 44, 18, 1.5)):
        if _seg_dist(x, y, ax, ay, bx, by) <= w:
            e = ((x - 32) / 17) ** 2 + ((y - 32) / 23) ** 2
            if e <= 1:
                return (*TEAL, 255)
    e_out = ((x - 32) / 20) ** 2 + ((y - 32) / 26) ** 2
    e_in = ((x - 32) / 14) ** 2 + ((y - 32) / 20) ** 2
    if e_in <= 1:
        return (*PAPER, 255)
    if e_out <= 1:
        return (*VIOLET, 255)
    return (*NAVY, 255)


def render(size: int, ss: int = 4) -> bytes:
    """صورة RGBA بحجم size مع تنعيم الحواف (supersampling)."""
    rows = []
    for j in range(size):
        row = bytearray([0])  # فلتر PNG: none
        for i in range(size):
            acc = [0, 0, 0, 0]
            for sj in range(ss):
                for si in range(ss):
                    c = _color_at((i + (si + .5) / ss) * 64 / size, (j + (sj + .5) / ss) * 64 / size)
                    a = c[3]
                    acc[0] += c[0] * a
                    acc[1] += c[1] * a
                    acc[2] += c[2] * a
                    acc[3] += a
            n = ss * ss
            alpha = acc[3] / n
            row += bytes([int(acc[k] / acc[3]) if acc[3] else 0 for k in range(3)] + [int(alpha)])
        rows.append(bytes(row))
    return b"".join(rows)


def png(size: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8 بت، RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(render(size), 9)) + chunk(b"IEND", b"")


def ico(sizes=(16, 32, 48)) -> bytes:
    images = [png(s) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for s, img in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset + len(data))
        data += img
    return header + entries + data


def main() -> None:
    (STATIC / "favicon.svg").write_text(SVG, encoding="utf-8")
    (STATIC / "favicon.ico").write_bytes(ico())
    (STATIC / "favicon-180.png").write_bytes(png(180))  # لأجهزة Apple
    print("written:", *(p.name for p in sorted(STATIC.glob("favicon*"))))


if __name__ == "__main__":
    main()
