#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/android-env.sh"
downloads="$irona_root/.runtime/downloads"
mkdir -p "$downloads"

download() {
  local name="$1" algorithm="$2" checksum="$3" url="$4"
  if [ -f "$downloads/$name" ] && printf '%s  %s\n' "$checksum" "$downloads/$name" | "${algorithm}sum" --check --status; then
    return
  fi
  printf 'Downloading %s\n' "$name"
  curl --fail --location --silent --show-error --retry 2 --connect-timeout 15 --max-time 1800 --output "$downloads/$name.part" "$url"
  printf '%s  %s\n' "$checksum" "$downloads/$name.part" | "${algorithm}sum" --check
  mv "$downloads/$name.part" "$downloads/$name"
}

download platform-tools-37.0.1.zip sha1 477254aa5f903c15cf51001717bdf347fb6b53e0 https://dl.google.com/android/repository/platform-tools_r37.0.1-linux.zip
unzip -q -o "$downloads/platform-tools-37.0.1.zip" -d "$ANDROID_HOME"
if [ "${1:-}" = "adb-only" ]; then exit 0; fi

download jdk17.tar.gz sha256 3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz'
mkdir -p "$JAVA_HOME"
tar -xzf "$downloads/jdk17.tar.gz" --strip-components=1 -C "$JAVA_HOME"

download gradle-8.9-bin.zip sha256 d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab https://services.gradle.org/distributions/gradle-8.9-bin.zip
unzip -q -o "$downloads/gradle-8.9-bin.zip" -d "$irona_root/.runtime"

download commandlinetools-12.0.zip sha1 d313adb7aedccf6cf0cfca51ec180f0059f5f8f8 https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
mkdir -p "$ANDROID_HOME/cmdline-tools/12.0"
unzip -q -o "$downloads/commandlinetools-12.0.zip" -d "$irona_root/.runtime/android-extract"
cp -a "$irona_root/.runtime/android-extract/cmdline-tools/." "$ANDROID_HOME/cmdline-tools/12.0/"
"$ANDROID_HOME/cmdline-tools/12.0/bin/sdkmanager" --sdk_root="$ANDROID_HOME" 'platforms;android-35' 'build-tools;34.0.0'
