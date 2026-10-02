import json

import pytest

from app.config import ROOT
from app.library import LibraryError, load_library

BASE = {"id": "X1", "level": "أ", "sources": [{"type": "fiqh", "text_ar": "نص", "url": "https://example.org"}]}


def write(tmp_path, *rows):
    p = tmp_path / "issues.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


def test_shipped_library_is_binbaz_books():
    issues = load_library()
    assert [i.id for i in issues] == [f"BZ0{n}" for n in range(1, 10)] + [f"HJ{n:02d}" for n in range(1, 13)]
    books = {"BZ": "https://binbaz.org.sa/books/pdf/215#page=", "HJ": "https://binbaz.org.sa/books/pdf/610#page="}
    for i in issues:
        assert not i.reviewed  # تنتظر مراجعة المطوّرة على صفحات الكتاب
        assert all(s.url.startswith(books[i.id[:2]]) for s in i.sources)
        assert all(not s.translation_en for s in i.sources)  # لا ترجمة معتمدة، فلا تُخترع
        assert "TODO" not in i.title_ar
    khilaf = {i.id for i in issues if i.position.khilaf}
    assert khilaf == {"BZ03", "BZ08", "HJ11", "HJ12"}


def test_shipped_quotes_are_verbatim_from_their_sources():
    for i in load_library():
        texts = " ".join(s.text_ar for s in i.sources)
        for o in i.position.opinions:
            assert o in texts or any(o in s.text_ar for s in i.sources), (i.id, o)


def test_placeholder_fixture_still_loads():
    issues = load_library(ROOT / "tests" / "fixtures" / "placeholder_issues.jsonl")
    assert [i.id for i in issues] == ["I01", "I02"]
    assert all(i.is_placeholder and "TODO" in i.title_ar for i in issues)
    assert issues[1].position.khilaf is True and issues[0].position.khilaf is False


def test_valid_issue_loads(tmp_path):
    assert load_library(write(tmp_path, BASE))[0].id == "X1"


@pytest.mark.parametrize("field", ["text_ar", "url"])
def test_source_without_text_or_url_rejected(tmp_path, field):
    row = json.loads(json.dumps(BASE))
    del row["sources"][0][field]
    with pytest.raises(LibraryError, match="issues.jsonl:1"):
        load_library(write(tmp_path, row))


@pytest.mark.parametrize("field", ["text_ar", "url"])
def test_blank_text_or_url_rejected(tmp_path, field):
    row = json.loads(json.dumps(BASE))
    row["sources"][0][field] = "   "
    with pytest.raises(LibraryError):
        load_library(write(tmp_path, row))


def test_issue_without_level_or_sources_rejected(tmp_path):
    with pytest.raises(LibraryError):
        load_library(write(tmp_path, {k: v for k, v in BASE.items() if k != "level"}))
    with pytest.raises(LibraryError):
        load_library(write(tmp_path, dict(BASE, sources=[])))
    with pytest.raises(LibraryError):
        load_library(write(tmp_path, dict(BASE, level="د")))


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(LibraryError, match="مكررة"):
        load_library(write(tmp_path, BASE, BASE))
