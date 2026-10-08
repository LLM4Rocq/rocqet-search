"""FastAPI search service for Rocqet."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rocqet import rerank
from rocqet.embedder import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    get_client,
    make_embedder,
)
from rocqet.schema import sparse_vector

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

app = FastAPI(
    title="Rocqet API",
    description="Semantic search over Rocq/Coq mathematical libraries",
    version="0.1.0",
)
# Public, mostly-read-only API: default to permissive CORS so any client (the
# UI, MCP servers, notebooks) can call it. Restrict to specific origins in
# production by setting CORS_ORIGINS (comma-separated). POST is only used by
# /visit (the visitor heartbeat) — everything else is GET.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_embedder = None
_client = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("rocqet")

# Simple in-memory per-IP sliding-window rate limit (ROCQET_RATE_LIMIT=0 disables).
# Fine for a single-instance deployment; protects the Qdrant quota from abuse.
RATE_LIMIT = int(os.environ.get("ROCQET_RATE_LIMIT", "60"))  # requests/min/IP
RATE_WINDOW = 60.0
_hits: dict[str, deque] = {}


def enforce_rate_limit(request: Request) -> None:
    if RATE_LIMIT <= 0:
        return
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    dq = _hits.setdefault(ip, deque())
    while dq and now - dq[0] > RATE_WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    dq.append(now)
    if len(_hits) > 10000:  # bound memory: drop IPs with no recent hits
        for k in [k for k, v in _hits.items() if not v]:
            _hits.pop(k, None)


class SearchResult(BaseModel):
    name: str
    kind: str
    type_signature: str
    statement: str = ""
    docstring: str = ""
    module_path: str = ""
    library: str
    file_path: str
    line_number: int
    github_url: str = ""
    chapter: str = ""
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    elapsed_ms: float


class StatsResponse(BaseModel):
    total_points: int
    libraries: dict[str, int]
    kinds: dict[str, int]


class VisitPing(BaseModel):
    visitor_id: str


class PageView(BaseModel):
    visitor_id: str
    path: str = "/"


class SiteStats(BaseModel):
    active_now: int
    total_visitors: int
    total_page_views: int


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = make_embedder(os.environ.get("ROCQET_EMBEDDER", "hash"))
    return _embedder


def client():
    global _client
    if _client is None:
        _client = get_client(os.environ.get("QDRANT_URL") or None)
    return _client


def build_filter(lib: str | None, kind: str | None, chapter: str | None = None):
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    conditions = []
    for key, value in (("library", lib), ("kind", kind), ("chapter", chapter)):
        if isinstance(value, str) and value.strip():
            terms = [x.strip() for x in value.split(",") if x.strip()]
            conditions.append(FieldCondition(key=key, match=MatchAny(any=terms)))
    return Filter(must=conditions) if conditions else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "collection": COLLECTION_NAME}


@app.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(..., description="Natural language search query"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    lib: str | None = Query(None),
    kind: str | None = Query(None),
    chapter: str | None = Query(None, description="GeoCoq chapter filter, e.g. Ch12"),
):
    enforce_rate_limit(request)
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    started = time.time()
    vector = embedder().embed([q])[0]
    try:
        hits = query_points(
            query=q,
            vector=vector,
            query_filter=build_filter(lib, kind, chapter),
            limit=rerank.candidate_pool(limit),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Search index unavailable: {exc}") from exc

    # Hybrid fusion already blends semantic + keyword. The optional cross-encoder
    # reranker can still reorder the fused candidates when explicitly enabled.
    scored = rerank.rerank(q, hits, limit)

    results = []
    for hit, score in scored:
        payload: dict[str, Any] = hit.payload or {}
        results.append(SearchResult(**payload, score=round(float(score), 4)))

    elapsed_ms = round((time.time() - started) * 1000, 1)
    logger.info("search q=%r lib=%s kind=%s results=%d ms=%.1f", q, lib, kind, len(results), elapsed_ms)

    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
        elapsed_ms=elapsed_ms,
    )


@app.get("/libs")
def libs() -> dict[str, dict[str, int]]:
    return {"libraries": scroll_counts("library")}


@app.get("/stats", response_model=StatsResponse)
def stats():
    try:
        info = client().get_collection(COLLECTION_NAME)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Search index unavailable: {exc}") from exc
    return StatsResponse(
        total_points=info.points_count or 0,
        libraries=scroll_counts("library"),
        kinds=scroll_counts("kind"),
    )


def scroll_counts(field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    offset = None
    while True:
        points, offset = client().scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            offset=offset,
            with_payload=[field],
            with_vectors=False,
        )
        for point in points:
            value = (point.payload or {}).get(field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        if offset is None:
            return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# FLT search — Fermat's Last Theorem page.
# Served from local artifacts (flt/data/); the index loads lazily on first
# use so the main API boots fast when the FLT data is absent.
# ---------------------------------------------------------------------------

_flt_index = None
_flt_error: str | None = None


def flt_index():
    global _flt_index, _flt_error
    if _flt_index is None and _flt_error is None:
        try:
            from rocqet import flt as flt_mod

            _flt_index = flt_mod.get_index()
        except FileNotFoundError as exc:
            _flt_error = f"FLT index not built: {exc}"
        except Exception as exc:  # noqa: BLE001
            _flt_error = f"FLT index failed to load: {exc}"
            logger.warning("FLT index failed to load: %s", exc)
    return _flt_index


class FLTSearchResponse(BaseModel):
    query: str
    mode: str
    seeds: list[dict[str, Any]]
    results: list[dict[str, Any]]
    groups: dict[str, list[str]]
    total: int
    elapsed_ms: float


@app.get("/flt/search", response_model=FLTSearchResponse)
def flt_search(
    request: Request,
    q: str = Query(..., description="Natural language query over FLT theorems"),
    mode: str = Query("what", pattern="^(what|used)$", description="'what' or 'used'"),
    limit: int = Query(10, ge=1, le=50),
):
    enforce_rate_limit(request)
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    idx = flt_index()
    if idx is None:
        raise HTTPException(status_code=503, detail=_flt_error or "FLT index unavailable")
    try:
        return idx.search(q, mode=mode, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"FLT search failed: {exc}") from exc


@app.get("/flt/theorem")
def flt_theorem(name: str = Query(..., description="Full theorem name, e.g. FreyPackage.frey_isModular")):
    idx = flt_index()
    if idx is None:
        raise HTTPException(status_code=503, detail=_flt_error or "FLT index unavailable")
    rec = idx.get_theorem(name)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Unknown theorem: {name}")
    return rec


@app.get("/flt/stats")
def flt_stats():
    idx = flt_index()
    if idx is None:
        raise HTTPException(status_code=503, detail=_flt_error or "FLT index unavailable")
    return idx.stats()


# ---------------------------------------------------------------------------
# Site stats — deliberately simple, two Qdrant collections:
#   rocqet_visits    one point per browser (client-generated UUID), a
#                    heartbeat updates its last_seen_ts. total_visitors =
#                    point count (distinct browsers); active_now = points
#                    seen in the last ACTIVE_WINDOW_SECONDS.
#   rocqet_pageviews one point per page load/navigation (random id, not
#                    keyed by visitor), so repeat views count. total_page_views
#                    = point count.
# Approximate, self-reported counters (no bot filtering, no auth on the
# ping) — not analytics-grade, but real numbers rather than none.
# ---------------------------------------------------------------------------

VISITS_COLLECTION = os.environ.get("ROCQET_VISITS_COLLECTION", "rocqet_visits")
PAGEVIEWS_COLLECTION = os.environ.get("ROCQET_PAGEVIEWS_COLLECTION", "rocqet_pageviews")
ACTIVE_WINDOW_SECONDS = 90
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_visits_ready = False
_pageviews_ready = False


def _ensure_collection(name: str, *, index_last_seen: bool) -> None:
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    qdrant = client()
    existing = {c.name for c in qdrant.get_collections().collections}
    if name not in existing:
        qdrant.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=1, distance=Distance.DOT),
        )
        if index_last_seen:
            qdrant.create_payload_index(
                name, field_name="last_seen_ts", field_schema=PayloadSchemaType.FLOAT
            )


def ensure_visits_collection() -> None:
    global _visits_ready
    if _visits_ready:
        return
    _ensure_collection(VISITS_COLLECTION, index_last_seen=True)
    _visits_ready = True


def ensure_pageviews_collection() -> None:
    global _pageviews_ready
    if _pageviews_ready:
        return
    _ensure_collection(PAGEVIEWS_COLLECTION, index_last_seen=False)
    _pageviews_ready = True


@app.post("/visit")
def visit(ping: VisitPing, request: Request) -> dict[str, bool]:
    enforce_rate_limit(request)
    vid = ping.visitor_id.strip()
    if not _UUID_RE.match(vid):
        raise HTTPException(status_code=400, detail="visitor_id must be a UUID")

    from qdrant_client.models import PointStruct

    try:
        ensure_visits_collection()
        client().upsert(
            collection_name=VISITS_COLLECTION,
            points=[PointStruct(id=vid, vector=[0.0], payload={"last_seen_ts": time.time()})],
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Visit tracking unavailable: {exc}") from exc
    return {"ok": True}


@app.post("/pageview")
def pageview(view: PageView, request: Request) -> dict[str, bool]:
    enforce_rate_limit(request)
    vid = view.visitor_id.strip()
    if not _UUID_RE.match(vid):
        raise HTTPException(status_code=400, detail="visitor_id must be a UUID")
    path = view.path.strip()[:200] or "/"

    import uuid

    from qdrant_client.models import PointStruct

    try:
        ensure_pageviews_collection()
        client().upsert(
            collection_name=PAGEVIEWS_COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.0],
                payload={"visitor_id": vid, "path": path, "ts": time.time()},
            )],
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pageview tracking unavailable: {exc}") from exc
    return {"ok": True}


@app.get("/site-stats", response_model=SiteStats)
def site_stats():
    from qdrant_client.models import FieldCondition, Filter, Range

    try:
        ensure_visits_collection()
        ensure_pageviews_collection()
        qdrant = client()
        total_visitors = qdrant.count(collection_name=VISITS_COLLECTION, exact=True).count
        active = qdrant.count(
            collection_name=VISITS_COLLECTION,
            count_filter=Filter(
                must=[FieldCondition(
                    key="last_seen_ts",
                    range=Range(gte=time.time() - ACTIVE_WINDOW_SECONDS),
                )]
            ),
            exact=True,
        ).count
        total_page_views = qdrant.count(collection_name=PAGEVIEWS_COLLECTION, exact=True).count
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Stats unavailable: {exc}") from exc
    return SiteStats(active_now=active, total_visitors=total_visitors, total_page_views=total_page_views)


SEARCH_MODE = os.environ.get("ROCQET_SEARCH", "dense").strip().lower()


def query_points(query: str, vector: list[float], query_filter, limit: int):
    """Retrieve candidates.

    Default: dense (semantic) retrieval over the named dense vector — measured best
    on natural-language queries, with lexical reordering applied afterwards by
    `rerank`. Opt-in `ROCQET_SEARCH=fusion` blends dense + BM25 sparse with RRF
    (better recall for identifier queries, but noisier on prose queries).
    """
    qdrant = client()

    if SEARCH_MODE == "fusion":
        from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

        sp_idx, sp_val = sparse_vector(query)
        prefetch_n = max(limit, 40)
        result = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                Prefetch(query=vector, using=DENSE_VECTOR_NAME, limit=prefetch_n, filter=query_filter),
                Prefetch(
                    query=SparseVector(indices=sp_idx, values=sp_val),
                    using=SPARSE_VECTOR_NAME,
                    limit=prefetch_n,
                    filter=query_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return result.points

    result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        using=DENSE_VECTOR_NAME,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    return result.points
