# Fine-tuning rocqet-embed

Descriptions lift MathComp NL search from hit@10 0.292 → 0.636
(circularity-free, see [BENCHMARKS.md](BENCHMARKS.md)). What's left is
discrimination: the right neighborhood comes back, but the exact lemma isn't
always #1. This is a contrastive fine-tune that pulls a query toward its
lemma and away from same-concept/different-relation siblings. Base model
stays `all-MiniLM-L6-v2` (384-d) — the one already served, so serving is
unchanged.

**Current status: not shipped.** The independent (circularity-free) eval
showed it doesn't generalize — see BENCHMARKS.md §2. Kept here as a pipeline
to revisit with better training data.

## Pipeline

```
rocqet.finetune        -> train.jsonl / test.jsonl   (pairs + hard negatives, cluster-safe)
scripts/train_embed.py -> models/rocqet-embed         (Colab free GPU, ~10-30 min)
scripts/eval_finetune.sh -> base vs tuned numbers      (local embedder)
[only if it wins] export to ONNX for fastembed serving
```

### 1. Build training data

```bash
python -m rocqet.finetune \
  --input data/declarations.mathcomp.ship.jsonl \
  --holdout-eval data/eval/nl_queries_mathcomp_q.jsonl
```

Anchors = NL descriptions, positives = the declaration doc text, hard
negatives = same concept-stem/different relation (e.g. `same_env` vs
`same_env_sym`). `--holdout-eval` forces every eval gold's cluster out of
training. Output: `data/finetune/{train,test}.jsonl`.

### 2. Train on Colab (free T4)

```python
!pip install -U sentence-transformers datasets
!python train_embed.py --train train.jsonl --out rocqet-embed --epochs 1 --batch-size 64
```

Download `rocqet-embed/` into `models/rocqet-embed/`.

### 3. Evaluate

```bash
export QDRANT_URL=... QDRANT_API_KEY=...
./scripts/eval_finetune.sh
```

Indexes the same corpus twice (base vs tuned) into throwaway collections and
evals both on held-out queries.

### 4. Ship (only if it wins)

Export the tuned model to ONNX, register with fastembed, re-index. Don't
productionize a model that didn't win — this one didn't (see BENCHMARKS.md).

## Notes

- MiniLM keeps serving unchanged (same 384-d, same fastembed path). A
  stronger base (bge) or distilled teacher is a later lever.
- v2 ideas: short synthesized query anchors (not just descriptions),
  embedding-based hard negatives, the 4,500 premise pairs.
- `data/finetune/` and `models/` are gitignored.
