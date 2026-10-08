"""Tests for the FLT endpoints, with a mocked index (no 213MB data file needed)."""

from fastapi.testclient import TestClient

from rocqet import api


def make_client(monkeypatch):
    monkeypatch.setattr(api, "_flt_index", None)
    monkeypatch.setattr(api, "_flt_error", None)
    return TestClient(api.app)


def test_flt_search_503_when_index_unavailable(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(api, "flt_index", lambda: None)
    monkeypatch.setattr(api, "_flt_error", "FLT index not built: no such file")

    resp = client.get("/flt/search", params={"q": "Frey curve"})
    assert resp.status_code == 503
    assert "FLT index not built" in resp.json()["detail"]


def test_flt_search_rejects_empty_query(monkeypatch):
    client = make_client(monkeypatch)
    resp = client.get("/flt/search", params={"q": "  "})
    assert resp.status_code == 400


def test_flt_search_returns_mocked_results(monkeypatch):
    client = make_client(monkeypatch)

    class FakeIndex:
        def search(self, query, mode="what", limit=10):
            return {
                "query": query, "mode": mode, "seeds": [], "results": [],
                "groups": {}, "total": 29511, "elapsed_ms": 1.0,
            }

    monkeypatch.setattr(api, "flt_index", lambda: FakeIndex())
    resp = client.get("/flt/search", params={"q": "Frey curve", "mode": "what"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 29511
    assert body["mode"] == "what"


def test_flt_theorem_404_when_unknown(monkeypatch):
    client = make_client(monkeypatch)

    class FakeIndex:
        def get_theorem(self, name):
            return None

    monkeypatch.setattr(api, "flt_index", lambda: FakeIndex())
    resp = client.get("/flt/theorem", params={"name": "NotReal.theorem"})
    assert resp.status_code == 404


def test_flt_stats_503_when_index_unavailable(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(api, "flt_index", lambda: None)
    monkeypatch.setattr(api, "_flt_error", "FLT index not built: no such file")

    resp = client.get("/flt/stats")
    assert resp.status_code == 503
