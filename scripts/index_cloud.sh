#!/usr/bin/env bash
#
# One-time: build the Rocqet index into a managed (remote) Qdrant cluster, e.g.
# Qdrant Cloud's free tier. The hosted API then connects to that cluster instead
# of holding the vector DB in-process, keeping its memory small.
#
# Usage:
#   export QDRANT_URL="https://xxxx.cloud.qdrant.io:6333"
#   export QDRANT_API_KEY="..."
#   ./scripts/index_cloud.sh
#
# Re-run after refreshing deploy/declarations.enriched.jsonl. Uses fastembed so
# the vectors match what the hosted API produces at query time.
#
# ZERO-DOWNTIME by design: this NEVER deletes the collection up front. Point ids
# are deterministic (stable_id), so re-running upserts every declaration in place
# and adds new ones — the live collection always stays fully queryable. A network
# timeout mid-upload just means some points aren't refreshed yet; re-run to finish.
# --prune then removes declarations that no longer exist, only after a clean pass.
#
# (The old --reset wiped first, so a mid-upload failure left the site empty. Don't.)
# For a true rebuild — e.g. switching embedding model/dimension — set REBUILD=1.

set -euo pipefail
cd "$(dirname "$0")/.."

: "${QDRANT_URL:?set QDRANT_URL to your managed Qdrant endpoint}"
: "${QDRANT_API_KEY:?set QDRANT_API_KEY for your managed Qdrant}"

PYTHON="${PYTHON:-}"
if [[ -z "${PYTHON}" ]]; then
  if [[ -x .venv/bin/python ]]; then PYTHON=".venv/bin/python"; else PYTHON="python3"; fi
fi

REBUILD_FLAG=""
if [[ "${REBUILD:-0}" == "1" ]]; then
  echo "!! REBUILD=1 — resetting the collection (brief downtime until upload completes)"
  REBUILD_FLAG="--reset"
fi

echo "==> Indexing deploy snapshot into ${QDRANT_URL} (fastembed, non-destructive upsert + prune)"
# shellcheck disable=SC2086
"${PYTHON}" -m rocqet.embedder \
  --input deploy/declarations.enriched.jsonl \
  --model fastembed \
  --qdrant-url "${QDRANT_URL}" \
  --no-resume \
  --prune \
  ${REBUILD_FLAG}

echo "==> Done. Ensure QDRANT_URL and QDRANT_API_KEY are set in the Railway service."
