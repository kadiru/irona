#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -x "$root/.runtime/gh/bin/gh" ]]; then
    printf '%s\n' 'Run bash scripts/install-gh.sh first.' >&2
    exit 1
fi
umask 077
export GH_CONFIG_DIR="$root/.runtime/github"
export GH_HOST=github.com
export GH_NO_UPDATE_NOTIFIER=1
# Do not inherit another account's environment token or machine-wide config.
unset GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN
mkdir -p "$GH_CONFIG_DIR"
chmod 700 "$GH_CONFIG_DIR"
exec "$root/.runtime/gh/bin/gh" "$@"
