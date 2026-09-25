#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version=2.101.0
archive="$root/.runtime/downloads/gh_${version}_linux_amd64.tar.gz"
expected=9bca2d1c16825f109907a23307628a2f0698fbf99662b73a5cf0b020293072b8
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
    printf '%s\n' 'This installer targets Linux x86-64 only.' >&2
    exit 1
fi
mkdir -p "$root/.runtime/downloads" "$root/.runtime/gh"
if [[ ! -f "$archive" ]]; then
    curl --fail --location --retry 2 --connect-timeout 15 --max-time 180 \
        "https://github.com/cli/cli/releases/download/v${version}/gh_${version}_linux_amd64.tar.gz" \
        --output "$archive.part"
    mv "$archive.part" "$archive"
fi
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status
tar -xzf "$archive" --strip-components=1 -C "$root/.runtime/gh"
"$root/.runtime/gh/bin/gh" --version
