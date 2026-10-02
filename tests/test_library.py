import json

import pytest

from app.library import LibraryError, load_library

BASE = {"id": "X1", "level": "أ", "sources": [{"type": "fiqh", "text_ar": "نص", "url": "https://example.org"}]}


def write(tmp_path, *rows):
    p = tmp_path / "issues.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


def test_shipped_library_has_only_placeholders():
    issues = load_library()
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
