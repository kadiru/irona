#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/android-env.sh"
exec "$ANDROID_HOME/platform-tools/adb" -P 5038 "$@"
