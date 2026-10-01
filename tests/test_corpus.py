import json

import pytest

from app.corpus import CorpusError, load_corpus, load_file


def test_shipped_corpus_valid():
    items = load_corpus()
    by_type = {t: [i for i in items if i.type == t] for t in ("quran", "hadith", "term")}
    assert all(len(v) >= 3 for v in by_type.values())
    assert all(i.grade for i in by_type["hadith"])


def _write(tmp_path, rows, name="hadith.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return p


BASE = {"id": "x", "type": "hadith", "text_ar": "نص", "grade": "sahih",
        "source_name": "مصدر", "license_note": "ترخيص"}


def test_missing_field_rejected(tmp_path):
    row = {k: v for k, v in BASE.items() if k != "license_note"}
    with pytest.raises(CorpusError, match="hadith.jsonl:1"):
        load_file(_write(tmp_path, [row]))


def test_hadith_needs_grade(tmp_path):
    with pytest.raises(CorpusError):
        load_file(_write(tmp_path, [dict(BASE, grade=None)]))


def test_bad_type_rejected(tmp_path):
    with pytest.raises(CorpusError):
        load_file(_write(tmp_path, [dict(BASE, type="poem")]))


def test_duplicate_ids_rejected(tmp_path):
    _write(tmp_path, [BASE, BASE])
    with pytest.raises(CorpusError, match="مكررة"):
        load_corpus(tmp_path)
