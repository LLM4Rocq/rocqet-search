# Search engineering

How Rocqet retrieves declarations, and the measured quality behind the
choices — including approaches that were tried and rejected.

Retrieval is a dense semantic vector (MiniLM, 384-d, cosine, via Qdrant),
reordered by a dependency-free lexical Reciprocal-Rank-Fusion pass. A BM25
sparse vector is also indexed and a full dense+sparse fusion mode exists, but
equal-weight fusion measured worse on natural-language queries, so
dense+lexical is the default.

## What gets embedded

[`declaration_text`](rocqet/schema.py) flattens a declaration to one string:

```
{kind} {name} | {type_signature} | {docstring} | {statement} | module {module_path} | library {library}
```

e.g. `Lemma addnC | commutative addn | Addition is commutative. | Lemma addnC : commutative addn. | module ssreflect.ssrnat | library mathcomp`

The sparse (keyword) side uses a tighter field set —
[`sparse_text`](rocqet/schema.py) = name + type_signature + statement + docstring.

Many records only have an auto-generated docstring that restates the
signature — thin signal for terse, symbolic declarations. Attaching a real
natural-language description is the biggest lever here (see
[docs/BENCHMARKS.md](docs/BENCHMARKS.md)).

## Indexing

[`rocqet.embedder`](rocqet/embedder.py) writes each declaration as one Qdrant
point with two named vectors: `dense` (cosine) and `text` (sparse, BM25-style
term frequencies, IDF-weighted by Qdrant at query time). Point id is a
deterministic hash of `library:file:line:name`, so re-indexing upserts in
place instead of duplicating.

Dense embedder, chosen with `--model` at index time (API must serve the same one):

| Model | Backend | Dim | Notes |
|-------|---------|-----|-------|
| `hash` | none | 384 | Lexical bag-of-words. Smoke tests only. |
| `local` | sentence-transformers (torch) | 384 | Best quality; heavy RAM. |
| `fastembed` | fastembed (ONNX) | 384 | Same weights via ONNX. Used in production. |
| `openai` | OpenAI API | 1536/3072 | Highest quality; paid, network. |

## Query time

`/search` embeds the query, retrieves a candidate pool (`ROCQET_SEARCH=dense`
by default, or `fusion` for dense+sparse RRF), reranks it down to `limit`
([`rocqet.rerank`](rocqet/rerank.py)), and applies `lib`/`kind` filters.

Reranking (`ROCQET_RERANK=auto`, the default) fuses the dense rank with a
lexical rank (token overlap + targeted prefix match) via RRF. Since it only
reorders dense's already-relevant pool, it sharpens keyword matches without
pulling in off-topic results. Modes: `auto`/`lexical` (default), `cross`
(cross-encoder), `off`.

## Measured quality

15 hand-picked queries, hit@1 / hit@5 (directional, not a benchmark):

| Configuration | hit@1 | hit@5 |
|---|:-:|:-:|
| Dense only (torch MiniLM) | 26% | 66% |
| **Dense + lexical RRF** (torch MiniLM) | **40%** | **80%** |
| Dense + lexical RRF (fastembed MiniLM — prod) | 33% | 60% |
| Equal-weight dense+sparse fusion | 26% | 53% |
| Cross-encoder rerank | regressed | regressed |

### Premise-selection benchmark (automated, leakage-free)

Mined from proof scripts ([`rocqet.mine_eval`](rocqet/mine_eval.py)): for each
theorem, the lemmas referenced in its proof are its premises. 4,500 pairs,
balanced across stdlib/mathcomp/geocoq. Run: `python -m rocqet.eval --limit 600`.

| recall@5 | recall@10 | MRR@10 | MAP@10 | r@10 mathcomp / stdlib / geocoq |
|:-:|:-:|:-:|:-:|:-:|
| 0.129 | 0.168 | 0.162 | 0.097 | 0.223 / 0.188 / 0.091 |

Premise selection is intentionally hard — a floor to improve against, not a
verdict.

## Tried and rejected

- **Cross-encoder reranking** regressed quality: generic cross-encoders are
  trained on prose and score terse Coq declarations near-zero, scrambling
  correct dense hits. Kept as opt-in (`ROCQET_RERANK=cross`), off by default.
- **Equal-weight BM25 + dense fusion** scored worse (hit@5 53% vs 80%) — the
  sparse side injects keyword-matchy but wrong candidates that outvote
  correct dense hits. Available as `fusion` mode, not the default.

## Known failure modes

- **Variant-family bias** — near-identical lemma families (`Qplus_0_l` vs
  `add_0_l`) cluster together and the canonical one can lose.
- **Abstract logic principles** with weak textual signal miss (`False_rect`,
  `NNPP`).
- **Compound-name over-reward** from the lexical pass.
- **Relational precision is soft** — `length_concat` over `in_app` for
  "membership in a concatenated list".

Most trace back to terse names + thin/auto docstrings.

## Config

| Variable | Default | Effect |
|---|---|---|
| `ROCQET_EMBEDDER` | `hash` | Dense model (must match index). Prod: `fastembed`. |
| `ROCQET_SEARCH` | `dense` | `dense` or `fusion` (dense+BM25 RRF). |
| `ROCQET_RERANK` | `auto` | `auto`/`lexical`, `cross`, or `off`. |
| `ROCQET_RERANK_CANDIDATES` | `40` | Candidate pool size before rerank. |
| `ROCQET_RRF_K` | `60` | RRF constant. |

## Next, roughly by impact

1. Stronger embedding model + query/passage prefixes (e.g. bge-base/bge-small).
2. Weighted (dense-favoring) fusion to recover BM25 recall for identifier queries.
3. Cleaner indexed text — replace restate-the-signature docstrings.
4. Canonical-form boosting for variant-family bias.
5. Type-aware / structural search via coq-lsp/SerAPI.
