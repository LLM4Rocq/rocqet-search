# Fine-tuning rocqet-embed

A contrastive fine-tune that pulls a query embedding toward its lemma and
away from same-concept/different-relation siblings (e.g. `same_env` vs
`same_env_sym`) — aimed at discrimination, not just getting the right
neighborhood. Base model stays `all-MiniLM-L6-v2` (384-d), the one already
served, so serving is unchanged.

**Current status: not shipped.** Production serves the description-only
index. This pipeline exists in the codebase (`rocqet.finetune`,
`scripts/train_embed.py`, `scripts/eval_finetune.sh`), but its output isn't
deployed — the eval that would justify shipping it is being re-run.

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
productionize a model that doesn't clearly beat the description-only
baseline on a held-out, non-circular eval.

## Notes

- `data/finetune/` and `models/` are gitignored.
