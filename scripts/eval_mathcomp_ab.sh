#!/usr/bin/env bash
#
# A/B the mathcomp NL descriptions, leakage-free, WITHOUT touching production.
#
# Both indexes hold the SAME 19,448 mathcomp decls; the only difference is whether
# the natural-language descriptions are embedded. Eval golds are held out of the
# enriched index (scripts/attach_mathcomp_nl.py), so a lift is real, not leaked.
#
# Uses dedicated collections (rocqet_mc_base / rocqet_mc_enriched) so the live
# `rocqet_declarations` collection is never modified.
#
# Prereqs:
#   python scripts/attach_mathcomp_nl.py          # builds the corpora + eval set
#   export QDRANT_URL="https://xxxx.cloud.qdrant.io:6333"
#   export QDRANT_API_KEY="..."
#
# Usage:
#   ./scripts/eval_mathcomp_ab.sh                  # index both + eval both
#   STEP=eval ./scripts/eval_mathcomp_ab.sh        # re-eval only (skip re-index)

set -euo pipefail
cd "$(dirname "$0")/.."

: "${QDRANT_URL:?set QDRANT_URL}"
: "${QDRANT_API_KEY:?set QDRANT_API_KEY}"

PY="${PYTHON:-}"; [[ -z "$PY" && -x .venv/bin/python ]] && PY=".venv/bin/python"; PY="${PY:-python3}"
EVAL="data/eval/nl_queries_mathcomp.jsonl"
STEP="${STEP:-all}"

index() {  # $1 collection  $2 input file
  echo "==> indexing $2 -> collection $1"
  ROCQET_COLLECTION="$1" "$PY" -m rocqet.embedder \
    --input "$2" --model fastembed --qdrant-url "$QDRANT_URL" --no-resume --reset
}

evaluate() {  # $1 collection  $2 label
  echo
  echo "################  $2  (collection: $1)  ################"
  ROCQET_COLLECTION="$1" ROCQET_EMBEDDER=fastembed "$PY" -m rocqet.eval \
    --eval-type nl --eval "$EVAL"
}

if [[ "$STEP" != "eval" ]]; then
  index rocqet_mc_base     data/declarations.mathcomp.base.jsonl
  index rocqet_mc_enriched data/declarations.mathcomp.enriched.jsonl
fi

evaluate rocqet_mc_base     "A) BASELINE  — no descriptions"
evaluate rocqet_mc_enriched "B) ENRICHED  — mathcomp NL descriptions (eval golds held out)"

echo
echo "Compare hit@1 / hit@5 / hit@10 / MRR between A and B. B-A = the description lift."
