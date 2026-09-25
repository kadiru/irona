#!/usr/bin/env bash
set -euo pipefail
irona_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
irona_version="0.34.4"
irona_checksum="c238986e61d40c0cc5f4a9b9e40b9eea104350b77efa34741fc134e105cb9533"
irona_archive="$irona_root/.runtime/downloads/ollama-$irona_version.tar.zst"
mkdir -p "$irona_root/.runtime/downloads" "$irona_root/.runtime/ollama"
curl --fail --location --retry 2 --connect-timeout 15 --max-time 1800 \
  --output "$irona_archive" \
  "https://github.com/ollama/ollama/releases/download/v$irona_version/ollama-linux-amd64.tar.zst"
printf '%s  %s\n' "$irona_checksum" "$irona_archive" | sha256sum --check
tar --zstd -xf "$irona_archive" -C "$irona_root/.runtime/ollama"
printf 'Ollama %s installed under .runtime/ollama\n' "$irona_version"
