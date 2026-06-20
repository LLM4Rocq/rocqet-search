"""Hybrid re-ranking of search results.

Dense vector search is a good *candidate generator* but a mediocre *ranker* for
this domain: math/Coq declarations are terse and symbolic, and pure semantic
vectors miss exact keyword/identifier overlap (a query "commutative" should
strongly prefer a lemma whose signature literally says `commutative`).

Default strategy ("auto"): take the dense top-N candidates and fuse the dense
ranking with a lexical ranking via Reciprocal Rank Fusion (RRF). This is
dependency-free (pure Python), needs no re-index, and runs on the existing index.
It reliably lifts keyword/identifier matches without discarding semantic recall.

Optional ("cross"): a cross-encoder reranker. Note that generic cross-encoders are
trained on natural-language web text and tend to *underperform* on terse Coq
declarations, so it is off by default.
"""

from __future__ import annotations

import os
import re

RERANK_CANDIDATES = int(os.environ.get("ROCQET_RERANK_CANDIDATES", "40"))
_MODE = os.environ.get("ROCQET_RERANK", "auto").strip().lower()
RRF_K = int(os.environ.get("ROCQET_RRF_K", "60"))

# Common English filler that carries no retrieval signal for these queries.
_STOP = {
    "a", "an", "the", "of", "on", "in", "is", "are", "for", "to", "and", "or",
    "that", "with", "as", "be", "by", "it", "its", "this", "these", "from",
    "has", "have", "between", "over", "into", "every", "all", "any", "no",
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAMEL_RE = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


_LEXICAL_MODES = {"auto", "1", "true", "yes", "on", "lexical", "hybrid"}
_PASSTHROUGH_MODES = {"0", "false", "no", "off", "none", "dense"}


def candidate_pool(limit: int) -> int:
    """How many candidates to retrieve before reranking.

    Reranking modes (lexical/cross) over-fetch a larger pool to reorder; the
    passthrough mode fetches exactly `limit`. Measured best: dense retrieval +
    lexical reorder of the pool (equal-weight dense+sparse fusion did worse on
    natural-language queries).
    """
    return limit if _MODE in _PASSTHROUGH_MODES else max(limit, RERANK_CANDIDATES)


def _split_identifier(tok: str) -> list[str]:
    # addnC -> [addn, c]; mulrA -> [mulr, a]; snake_case handled by _TOKEN_RE upstream
    return [p.lower() for p in _CAMEL_RE.findall(tok)]


def _query_terms(query: str) -> list[str]:
    terms = [t.lower() for t in _TOKEN_RE.findall(query)]
    return [t for t in terms if len(t) >= 2 and t not in _STOP]


def _doc_tokens(payload: dict) -> set[str]:
    fields = [
        str(payload.get("name") or ""),
        str(payload.get("type_signature") or ""),
        str(payload.get("docstring") or ""),
        str(payload.get("statement") or ""),
    ]
    toks: set[str] = set()
    for field in fields:
        for raw in _TOKEN_RE.findall(field):
            low = raw.lower()
            toks.add(low)
            toks.update(_split_identifier(raw))
    return {t for t in toks if len(t) >= 2}


def _lexical_score(terms: list[str], doc: set[str]) -> float:
    if not terms:
        return 0.0
    hits = 0.0
    for term in terms:
        if term in doc:
            hits += 1.0
        elif len(term) >= 5 and any(d.startswith(term) or term.startswith(d) for d in doc if len(d) >= 5):
            hits += 0.5  # targeted partial: commut <-> commutative, inject <-> injective
    return hits


def _rrf_fuse(hits: list, query: str, limit: int) -> list[tuple]:
    n = len(hits)
    terms = _query_terms(query)

    # Dense rank = current order (best first).
    dense_rank = {id(h): i for i, h in enumerate(hits)}

    # Lexical rank: higher lexical score first; ties keep dense order.
    lex = [(_lexical_score(terms, _doc_tokens(h.payload or {})), -dense_rank[id(h)], h) for h in hits]
    lex.sort(reverse=True)
    lex_rank = {id(h): i for i, (_, _, h) in enumerate(lex)}

    fused = []
    for h in hits:
        score = 1.0 / (RRF_K + dense_rank[id(h)]) + 1.0 / (RRF_K + lex_rank[id(h)])
        fused.append((score, -dense_rank[id(h)], h))
    fused.sort(reverse=True)

    top = fused[:limit]
    best = top[0][0] if top else 1.0
    return [(h, score / best) for score, _, h in top]  # normalize display score to (0,1]


def _cross_encoder(query: str, hits: list, limit: int) -> list[tuple]:
    import math

    from sentence_transformers import CrossEncoder

    model = CrossEncoder(os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"), max_length=512)
    pairs = [(query, _doc_text(h.payload or {})) for h in hits]
    raw = model.predict(pairs)
    order = sorted(range(len(hits)), key=lambda i: float(raw[i]), reverse=True)[:limit]
    return [(hits[i], 1.0 / (1.0 + math.exp(-float(raw[i])))) for i in order]


def _doc_text(payload: dict) -> str:
    if payload.get("search_text"):
        return str(payload["search_text"])
    parts = [
        f"{payload.get('kind', '')} {payload.get('name', '')}".strip(),
        str(payload.get("type_signature") or ""),
        str(payload.get("docstring") or ""),
        str(payload.get("statement") or ""),
    ]
    return " | ".join(p for p in parts if p)


def _passthrough(hits: list, limit: int) -> list[tuple]:
    """Trust upstream (hybrid fusion) order; normalize scores to (0, 1] for display."""
    top = hits[:limit]
    if not top:
        return []
    best = max((float(h.score) for h in top), default=1.0) or 1.0
    return [(h, float(h.score) / best) for h in top]


def rerank(query: str, hits: list, limit: int) -> list[tuple]:
    """Return a list of (hit, display_score).

    Default ("auto") trusts the hybrid dense+sparse fusion done in Qdrant. Optional
    modes reorder: "cross" (cross-encoder) or "lexical"/"hybrid" (in-process RRF of
    dense + lexical). Falls back to upstream order on any failure.
    """
    if not hits:
        return []
    try:
        if _MODE == "cross":
            return _cross_encoder(query, hits, limit)
        if _MODE in _PASSTHROUGH_MODES:
            return _passthrough(hits, limit)
        return _rrf_fuse(hits, query, limit)  # default: dense + lexical reorder
    except Exception as exc:  # noqa: BLE001 - never let ranking break search
        print(f"[rocqet.rerank] fell back to retrieval order: {exc}")
        return _passthrough(hits, limit)
