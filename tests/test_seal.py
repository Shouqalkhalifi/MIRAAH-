from datetime import datetime, timezone

from app.models import Decision, Report, Source, Version
from app.seal import qr_svg, seal_digest, sha256, text_hashes


def rep(**kw):
    return Report(source=Source(text="نص"), versions=[Version(label="en", lang="en", text="text")], **kw)


def test_text_hashes_are_sha256_of_texts():
    assert text_hashes(rep()) == [("source", sha256("نص")), ("en", sha256("text"))]
    assert len(sha256("x")) == 64


def test_digest_changes_with_decisions_and_texts():
    t = datetime(2026, 10, 1, tzinfo=timezone.utc)
    a = rep(published_at=t)
    b = rep(published_at=t, decisions={"x": Decision(alert_id="x", action="accept", reason="سبب كافٍ")})
    c = Report(source=Source(text="نص آخر"), versions=a.versions, published_at=t)
    assert len({seal_digest(a), seal_digest(b), seal_digest(c)}) == 3
    assert seal_digest(a) == seal_digest(rep(published_at=t))  # حتمية


def test_qr_is_inline_svg():
    svg = qr_svg("http://localhost:8000/seal/abc")
    assert svg.startswith("<svg ") and "<path" in svg and "<?xml" not in svg
