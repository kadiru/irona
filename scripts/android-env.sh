#!/usr/bin/env bash
irona_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ANDROID_HOME="$irona_root/.runtime/android-sdk"
export ANDROID_USER_HOME="$irona_root/.runtime/android-user"
export GRADLE_USER_HOME="$irona_root/.runtime/gradle-cache"
export JAVA_HOME="$irona_root/.runtime/jdk17"
export ANDROID_ADB_LOG_PATH="$irona_root/.runtime/adb.log"
export ADB_MDNS_AUTO_CONNECT=0
export TMPDIR="$irona_root/.runtime/tmp"
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} -Djava.io.tmpdir=$TMPDIR -XX:-UsePerfData"
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p "$ANDROID_HOME" "$ANDROID_USER_HOME" "$GRADLE_USER_HOME" "$TMPDIR"
