"""Tests for the visit-counter endpoints, against a throwaway on-disk Qdrant."""

import uuid

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rocqet import api

VISITOR_A = "11111111-1111-1111-1111-111111111111"
VISITOR_B = "22222222-2222-2222-2222-222222222222"


def make_client(tmp_path, monkeypatch):
    # QDRANT_PATH is read once at rocqet.embedder import time, so setting the env
    # var here wouldn't take effect - construct a throwaway client directly and
    # monkeypatch api.client() to return it, keeping every test's on-disk store
    # and collection name unique regardless of tmp_path folder-name reuse across
    # separate pytest invocations.
    fresh_client = QdrantClient(path=str(tmp_path / "qdrant"))
    monkeypatch.setattr(api, "client", lambda: fresh_client)
    monkeypatch.setattr(api, "_visits_ready", False)
    monkeypatch.setattr(api, "VISITS_COLLECTION", f"rocqet_visits_test_{uuid.uuid4().hex}")
    return TestClient(api.app)


def test_visit_rejects_non_uuid(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    resp = client.post("/visit", json={"visitor_id": "not-a-uuid"})
    assert resp.status_code == 400


def test_visit_and_site_stats_count_distinct_visitors(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    resp = client.post("/visit", json={"visitor_id": VISITOR_A})
    assert resp.status_code == 200

    stats = client.get("/site-stats").json()
    assert stats["total_visitors"] == 1
    assert stats["active_now"] == 1

    client.post("/visit", json={"visitor_id": VISITOR_B})
    stats = client.get("/site-stats").json()
    assert stats["total_visitors"] == 2
    assert stats["active_now"] == 2

    # Same visitor again doesn't inflate total_visitors, only refreshes last_seen.
    client.post("/visit", json={"visitor_id": VISITOR_A})
    stats = client.get("/site-stats").json()
    assert stats["total_visitors"] == 2
