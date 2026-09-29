# Benchmarks

Retrieval-quality experiments on Rocqet, with leakage-controlled methodology
and reproduce steps.

## 1. Do natural-language descriptions fix MathComp search?

MathComp identifiers are terse (`rVpoly`, `addrA`) and statements are
notation-heavy, so a generic sentence embedder has almost no prose to match a
query against. We attached one-sentence NL descriptions to 96% of the 19,448
indexed MathComp declarations and measured the retrieval delta.

**Methodology.** 292 declarations, gold = the declaration, query = an LLM
paraphrase of its description with no Coq identifier names (mirrors the
LeanSearch/Lean Finder eval style — using the description verbatim as the
query would be leaky, since that text is embedded in the doc). Two indexes,
identical except for descriptions, same model and rerank, dedicated Qdrant
collections (never the live one).

| query form | index | hit@1 | hit@5 | hit@10 | MRR@10 |
|---|---|:-:|:-:|:-:|:-:|
| paraphrase (honest) | base (no desc) | 0.065 | 0.164 | 0.205 | 0.116 |
| paraphrase (honest) | **ship (desc)** | **0.353** | **0.709** | **0.853** | **0.512** |
| verbatim (leaky ceiling) | base (no desc) | 0.003 | 0.021 | 0.048 | 0.015 |
| verbatim (leaky ceiling) | ship (desc) | 0.644 | 0.908 | 0.986 | 0.760 |

Embedding the descriptions lifts every metric roughly 4-5x on the honest
paraphrase set. But these paraphrase queries share a common ancestor with the
embedded description (the description itself), so this is a semi-circular
upper bound — see §2 for the circularity-free number (0.636 hit@10).

Reproduce:

```bash
python scripts/attach_mathcomp_nl.py
./scripts/eval_mathcomp_ab.sh
GEMINI_API_KEYS=key1,key2 python scripts/make_query_eval.py
ROCQET_COLLECTION=rocqet_mc_base ROCQET_EMBEDDER=fastembed python -m rocqet.eval --eval-type nl --eval data/eval/nl_queries_mathcomp_q.jsonl
ROCQET_COLLECTION=rocqet_mc_ship ROCQET_EMBEDDER=fastembed python -m rocqet.eval --eval-type nl --eval data/eval/nl_queries_mathcomp_q.jsonl
```

The description corpus (`data/mathcomp-natural-lang.json`) is distributed as
a release asset, not committed (see [DATA.md](DATA.md)).

## 2. Does a domain fine-tune add anything on top?

Descriptions fix the missing-surface problem — the right neighborhood lands
in top-10. What's left is discrimination: the exact lemma isn't always #1.
We fine-tuned `all-MiniLM-L6-v2` with hard negatives (same concept-stem,
different relation) and tested whether that helps, using two query sets:

- **Paraphrase** (§1) — circular: shares an ancestor with the embedded description.
- **Independent** — an LLM sees only the formal Coq statement, never the
  description or name, and writes the query. This is the honest test; the
  fine-tune was never trained on this distribution. (`--holdout-eval` also
  verified 0 of 292 eval golds leak into training.)

| query set | index | hit@1 | hit@5 | hit@10 | MRR@10 |
|---|---|:-:|:-:|:-:|:-:|
| paraphrase (circular) | base (desc only) | 0.377 | 0.723 | 0.839 | 0.523 |
| paraphrase (circular) | + fine-tune | 0.452 | 0.767 | 0.873 | 0.592 |
| **independent** (honest) | base (desc only) | **0.237** | 0.512 | **0.636** | 0.364 |
| **independent** (honest) | + fine-tune | 0.220 | 0.485 | 0.615 | 0.341 |

On the circular set the fine-tune looks like a +20% hit@1 win. On the
independent set that gain disappears — the model specialized to description
phrasing rather than learning transferable discrimination. **We don't ship
this fine-tune.** The independent eval caught it before it shipped.

What did hold up, on the same independent set:

| query set | index | hit@1 | hit@5 | hit@10 | MRR@10 |
|---|---|:-:|:-:|:-:|:-:|
| independent (honest) | no descriptions | 0.096 | 0.227 | 0.292 | 0.160 |
| independent (honest) | **+ descriptions** | **0.237** | **0.512** | **0.636** | **0.364** |
| independent (honest) | + fine-tune | 0.220 | 0.485 | 0.615 | 0.341 |

**Honest descriptions lift, circularity-free:** hit@10 0.292 → 0.636 (~2.2x),
hit@1 0.096 → 0.237 (~2.5x). Smaller than the paraphrase set's ~4x (that set
is semi-circular and inflates it), but real. This is the shipped system.

A fine-tune v2 would need diverse anchors (statement-derived queries, the
4,500 premise pairs, short query forms), not just descriptions, to
generalize — see [FINETUNE.md](FINETUNE.md).

Reproduce:

```bash
GEMINI_API_KEYS=key1,key2 python scripts/make_indep_eval.py
ROCQET_COLLECTION=<coll> EMBED_MODEL=<model> ROCQET_EMBEDDER=local \
  python -m rocqet.eval --eval-type nl --eval data/eval/nl_queries_mathcomp_indep.jsonl
```
