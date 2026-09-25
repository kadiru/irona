#!/usr/bin/env bash
set -euo pipefail
irona_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS="$irona_root/.runtime/models"
export OLLAMA_NO_CLOUD=1
export OLLAMA_NOHISTORY=1
export OLLAMA_DEBUG_LOG_REQUESTS=0
export OLLAMA_CONTEXT_LENGTH=4096
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_MAX_QUEUE=2
export OLLAMA_LOAD_TIMEOUT=90s
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export CUDA_CACHE_PATH="$irona_root/.runtime/cuda-cache"
export TMPDIR="$irona_root/.runtime/tmp"
mkdir -p "$TMPDIR" "$CUDA_CACHE_PATH" "$OLLAMA_MODELS"
exec "$irona_root/.runtime/ollama/bin/ollama" "$@"
