# Temi Audio Integration

Status: working and owner-confirmed on the actual robot, 2026-09-24.
The owner approved project-local Android tools and installation of the Irona app.
The robot's ADB TCP port is reachable from Ubuntu. Its photos show Launcher OS
16405, Robox OS 128.12, and firmware 20201216.154352. ADB reports Android 6.0.1,
API 23, and model identifier rk3288. No firmware was updated. Do not copy robot serial
numbers, MAC addresses, or the owner's photos into the public repository.

The owner separately approved `/home/kadir/.android` as a symlink to the project's
`.runtime/android-user`; it is now created. A build-generated directory containing
analytics.settings appeared before linking and was preserved intact under ignored
`.runtime/android-home-before-link`. The APK is installed and privately paired.
The owner heard the test tone, Elise's fixed sentence, and three conversational
replies from Temi. Ubuntu's private configuration now selects `temi`.

## Confirmed Baseline

- Keep the local LLM and ElevenLabs requests on Ubuntu; keep the API key there.
- Retain typed input and the browser controller for this milestone.
- Preserve the existing desktop output as an explicitly selected development
  option. Never silently fall back to desktop or browser audio if Temi fails.
- All 66 Python tests pass, including desktop regression coverage, setup/token
  transfer checks, and mocked
  Temi start/completion/stop/disconnection/restart/timeout behavior. These mocks
  do not prove that the robot plays audio.
- Ubuntu had Java 11. ADB, Gradle, and sdkmanager were not found on PATH;
  no SDK was found in the common directories checked. Check any owner-provided
  existing project/toolchain before downloading another one.

## Implemented Path

```text
Browser -> Ubuntu: local LLM -> ElevenLabs audio
                            -> small Android player on Temi -> Temi speakers
```

Temi's official app development route is Android. Its built-in speak(TtsRequest)
accepts text for Temi TTS, not an ElevenLabs MP3. Preserve the selected Elise voice
by playing the generated audio through Android's media APIs. Use a proven
platform player, not a custom audio decoder. Add the Temi SDK only for features
the integration actually needs; no navigation, camera, microphone, or actuator
permissions are required for this playback milestone.

The Android player binds only to robot loopback port 8766. A device-specific ADB
forward maps Ubuntu loopback port 8766 to it. Keep the Ubuntu app and Ollama
listeners on loopback. ADB over Wi-Fi
itself enables privileged debugging on the robot: use only a trusted network,
verify device authorization, never forward that port through the router, and
disable debugging when development is finished. This is a development transport,
not the final unattended deployment design. If it is unsuitable, discuss an
authenticated network transport before exposing any application listener.

The receiver uses Android MediaPlayer and NanoHTTPD 2.3.1. It accepts at most an
eight-megabyte audio body, authenticates every request with a private per-project
token, and handles one playback at a time. Status comes from player callbacks.
Ubuntu polls every 200 ms; a 3.5-second heartbeat expiry stops/releases playback.
Loss of focus or leaving the player also stops audio. Temporary app-private audio
is deleted on completion/stop/error and stale files are removed on next startup.
The ElevenLabs key never goes to the APK. Tokens/signing keys/build tools are
ignored files. Native backups are disabled. Native Stop and browser Stop share
the same terminal playback state. No automatic output fallback is implemented.

## Setup And Commands

Run these commands from `/home/kadir/code/irona` on Ubuntu. The approved tools are
already downloaded: project-local JDK 17, Gradle 8.9, Android command-line tools
12.0, Platform Tools 37.0.1, API 35, and Build Tools 34.0.0. AGP 8.7.3 builds a
small debug APK with minimum Android API 23. It uses no Temi SDK or ROS dependency.

For a fresh setup, `bash scripts/install-android.sh` downloads checksummed tools
and prompts for the Android SDK license. It does not create the outside-project
identity link. Only after explicit approval, and only if no directory/link exists:

```bash
mkdir -p .runtime/android-user
if [ ! -e "$HOME/.android" ] && [ ! -L "$HOME/.android" ]; then
  ln -s "$PWD/.runtime/android-user" "$HOME/.android"
fi
```

Never replace an existing Android identity directory. The helper intentionally
checks this project-contained identity path before starting ADB. Its dedicated
ADB server uses host loopback port 5038, separate from a normal 5037 server.

```bash
bash scripts/build-temi.sh lintDebug
.venv/bin/python scripts/temi.py inspect --device ROBOT_IP
.venv/bin/python scripts/temi.py install --device ROBOT_IP
IRONA_AUDIO_OUTPUT=temi .venv/bin/python scripts/check.py audio
IRONA_AUDIO_OUTPUT=temi .venv/bin/python scripts/check.py tone
```

`ROBOT_IP` is the IP shown on Temi's developer screen, not Ubuntu's address.
Installation targets only `dev.irona.player`; it neither roots the robot nor
updates firmware. The private token is copied over ADB into app-private storage
without putting it in command arguments or shared storage. A conflicting local
port forward is not overwritten. The helper saves the selected IP only in
ignored `.runtime/temi/device.json`.

Android 6 lacks the modern `adb shell -T` protocol. The helper uses `exec-in`
with `run-as` and `dd` for token transfer, then verifies the received value
privately via `exec-out`. A raw exec return code alone is not treated as success.

After a person confirms the tone, the explicit paid check is:

```bash
IRONA_AUDIO_OUTPUT=temi .venv/bin/python scripts/check.py tts
```

After successful hardware checks, set `IRONA_AUDIO_OUTPUT=temi` in Ubuntu's private
`.env` and restart with `.venv/bin/python -m irona`. Restart clears in-memory chat.
The browser will label the selected destination Temi. A failed/missing robot
connection prevents inference and paid synthesis at preflight.

After a robot reboot or closed player, reconnect using the privately saved IP:

```bash
.venv/bin/python scripts/temi.py connect
```

Finish the development session with:

```bash
.venv/bin/python scripts/temi.py disconnect
```

Then close the ADB port on Temi's developer screen. An ADB disconnect alone does
not close the robot's debugging listener. The app must stay in the foreground
for this development milestone; unattended background operation is not supported.

## Milestones

1. Identify model, Android/Temi software versions, IP, and existing developer setup.
2. Inspect and authorize a connection to that specific robot. Do not scan the LAN
   or install into an unidentified device. Request permission before substantial
   SDK downloads, system changes, or writes outside the project.
3. Build/reuse a small receiver and play a short local test sound on Temi. Confirm
   physical audibility before sending any paid TTS requests.
4. Play a fixed ElevenLabs sentence on Temi and confirm its speaker is the output.
5. Connect the existing typed-input pipeline; preserve history and reset behavior.
6. Verify repeated turns, Stop, connection loss, cleanup, and startup/shutdown.
   Mock robot/network failures in automated tests and document real hardware
   evidence separately. Do not mark integration complete until heard on Temi.

## Verified Hardware Checks

- APK installation and app-private token pairing on Android 6.0.1.
- Owner-confirmed tone, fixed Elise speech, and three browser conversation turns.
- Name recall, overlapping-turn rejection, browser Stop, and conversation reset.
- Silent WAV tests on the real MediaPlayer: remote Stop, native Stop button,
  heartbeat expiry after deliberately withholding polls, and subsequent recovery.
- Unauthorized request rejection, robot-screen inspection, desktop/mobile browser
  layout, and loopback-only Ubuntu application/ADB-forward listeners.
- Missing-forward preflight failure and restoration using the setup helper.
- Final native build and lint pass without issues.

These are development-session checks, not an unattended reliability soak test.
Wi-Fi outages/reconnection under varied conditions, robot reboot, and background
operation remain unverified or unsupported. See `verification.md` for evidence.

## Official References

- [Temi Android application development](https://github.com/robotemi/sdk/wiki)
- [Temi app installation and ADB connection](https://github.com/robotemi/sdk/wiki/Installing-and-Uninstalling-temi-Applications)
- [Temi speech API](https://github.com/robotemi/sdk/wiki/Speech)
- [Android MediaPlayer](https://developer.android.com/media/platform/mediaplayer/basics)
- [Android Debug Bridge](https://developer.android.com/tools/adb)
