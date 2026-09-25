#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/android-env.sh"
exec "$irona_root/.runtime/gradle-8.9/bin/gradle" --no-daemon --console=plain -p "$irona_root/android" assembleDebug "$@"
