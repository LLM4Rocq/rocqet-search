"""Tests for the MCP server tools (mocked HTTP, no live API needed)."""

import httpx

from rocqet import mcp_server


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._payload


def test_rocqet_search_formats_results(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert url.endswith("/search")
        assert params["q"] == "commutativity of addition"
        return FakeResponse({
            "results": [{
                "name": "addnC", "kind": "Lemma", "library": "mathcomp",
                "score": 0.91, "type_signature": "commutative addn",
                "statement": "Lemma addnC : commutative addn.",
                "docstring": "Addition is commutative.",
                "github_url": "https://example.com/addnC#L1",
            }],
            "elapsed_ms": 2.5,
        })

    monkeypatch.setattr(httpx, "get", fake_get)
    out = mcp_server.rocqet_search("commutativity of addition")
    assert "addnC" in out
    assert "mathcomp" in out
    assert "1 result(s)" in out


def test_rocqet_search_no_results(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse({"results": []}))
    out = mcp_server.rocqet_search("nonexistent query xyz")
    assert "No declarations found" in out


def test_rocqet_search_clamps_limit(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(params)
        return FakeResponse({"results": []})

    monkeypatch.setattr(httpx, "get", fake_get)
    mcp_server.rocqet_search("q", limit=500)
    assert seen["limit"] == 50
    mcp_server.rocqet_search("q", limit=0)
    assert seen["limit"] == 1


def test_rocqet_search_unreachable_api(monkeypatch):
    def raise_error(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", raise_error)
    out = mcp_server.rocqet_search("q")
    assert "Could not reach the Rocqet API" in out


def test_rocqet_stats_formats_summary(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse({
        "total_points": 44440,
        "libraries": {"stdlib": 13735, "mathcomp": 19448},
        "kinds": {"Lemma": 30000},
    }))
    out = mcp_server.rocqet_stats()
    assert "44440" in out
    assert "stdlib: 13735" in out


def test_rocqet_stats_unreachable_api(monkeypatch):
    def raise_error(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", raise_error)
    out = mcp_server.rocqet_stats()
    assert "Could not reach the Rocqet API" in out
