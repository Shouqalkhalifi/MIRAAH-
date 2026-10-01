from fastapi.testclient import TestClient

from app.main import DISCLAIMER, app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["corpus_items"] >= 9


def test_all_screens_render_with_disclaimer():
    for path in ["/", "/new", "/analyze/demo", "/report/demo", "/review/demo", "/seal/demo"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert DISCLAIMER in r.text, path
        assert 'dir="rtl"' in r.text


def test_report_shows_broken_link_and_highlight():
    r = client.get("/report/demo").text
    assert "🔴 لا تنشر" in r
    assert "border-red-600 bg-red-50" in r  # الحلقة التي دخل فيها الخلل
    assert '<mark class="mark-red">للمسافر</mark>' in r


def test_docs():
    assert client.get("/docs").status_code == 200


def test_review_alpine_state_not_inlined_in_attribute():
    # منع تكرار خطأ: JSON داخل x-data="..." يكسر السمة
    r = client.get("/review/demo").text
    assert 'x-data="reviewState()"' in r
    assert 'x-data="{\n' not in r
