# Verification

Tested on 2026-09-24. This records observed behavior, not a guarantee for another
machine, voice, account, or audio device.

## Live Hardware And Services

- Ubuntu 22.04.5; Python 3.10.12; NVIDIA RTX 4090, driver 580.178.04.
- Ollama 0.34.4 verified after a checksummed, project-local installation.
- `qwen3.5:4b` downloaded locally. Manifest digest:
  `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
  Q4_K_M model; Ollama reported 100% GPU, 4,096-token active context. NVIDIA
  process telemetry confirmed the RTX 4090, using about 4.1 GiB VRAM.
- Local test sound played through the selected analog output; the owner
  confirmed hearing it after switching the speakers on.
- A fixed sentence was successfully synthesized using Elise with Flash v2.5 and
  passed through FFmpeg/paplay. This first test preceded the listening check.
- Three consecutive browser-submitted turns completed local generation, paid
  synthesis, and Ubuntu playback. The owner confirmed hearing the spoken replies,
  including the model recalling the name supplied in the previous turn.
- A fourth real reply was deliberately stopped during playback. The process
  stopped, the UI marked audio stopped, and a simultaneous new turn was rejected.
- Reset cleared the conversation and counter. No audio/video element or browser
  playback API was used.
- SIGTERM shutdown completed cleanly and the application restarted with an empty
  conversation. The UI was accessed from Mac through a loopback-only SSH tunnel.

Observed warm-turn timings in seconds, from three short test messages:

| Turn | Local generation | ElevenLabs synthesis | Total including playback |
| --- | ---: | ---: | ---: |
| 1 | 0.21 | 0.36 | 4.60 |
| 2 | 0.14 | 0.28 | 2.09 |
| 3 | 0.22 | 0.41 | 5.81 |

Generation includes the audio preflight check. These are small-sample timings,
not latency guarantees; cold model startup is substantially slower.

## Automated Checks

`python -m pytest -q`: **66 passed** on Ubuntu. External HTTP services are mocked.
Coverage includes configuration validation, secret redaction, local-only inference,
TTS permissions/credit errors, redirect rejection, response validation, timeouts,
bounded history, reset, single-turn locking, stop, shutdown during inference,
child-process termination, temporary-file cleanup, Host/Origin/token checks,
request limits, and recovery after errors. `pip check` and shell syntax checks pass.

Playwright with installed Chrome exercised the real browser pipeline described
above. Desktop/mobile screenshots were inspected, and real icon loading and lack
of horizontal overflow were checked. Final layout/error checks use browser-side
fixtures and make no paid calls; they do not prove hardware playback.

## Not Yet Verified Or Implemented

- Unattended Temi deployment, robot reboot recovery, and prolonged real Wi-Fi
  outage testing. The foreground ADB player is a development transport.
- Microphone input, streaming, physical interruption controls, and LAN access.
- Long-duration operation or multiple independent users/sessions.
- Installation on a different machine or desktop audio stack.
- Recovery from power loss or SIGKILL; temporary audio can survive those events.
- Selection of a project license remains pending.

## Temi Integration

- ADB identified Android 6.0.1 / API 23, model identifier rk3288. No firmware,
  system settings, navigation, microphone, or camera integration was changed.
- Installed `dev.irona.player`, using project-local Android tools and JDK 17.
  The separately approved Android identity symlink keeps credentials in ignored
  project storage. Existing build-generated analytics settings were preserved.
- The owner confirmed hearing a local tone, then a fixed Elise sentence, then
  three browser-submitted conversational replies from Temi's own speakers.
- The local model recalled the supplied name on turn two. All three replies
  reached native MediaPlayer completion. A fourth reply was stopped with the
  browser control; overlapping input was rejected and reset cleared history.
- Live turn timings (generation / synthesis / total seconds):
  3.65 / 0.38 / 8.86; 0.33 / 0.24 / 1.80; 0.38 / 0.44 / 4.60.
  This is a tiny sample, not a performance guarantee.
- Silent WAV checks exercised the real native player without paid calls:
  withheld heartbeats produced `lease_expired`, remote Stop was acknowledged,
  tapping native Stop propagated cancellation, and subsequent playback completed.
- A bad pairing token received HTTP 401. Ubuntu app, Ollama, ADB server, and the
  audio forward listened only on loopback. Temi's privileged ADB port itself
  remains open on the trusted LAN for this development session.
- Inspected the actual robot screen plus 1365px desktop, 390px and 320px browser
  layouts. No browser audio element or playback path is used.
- Added mocked tests for Temi acknowledgements, failures, restart, timeouts,
  output isolation, private legacy token transfer, and approved identity paths.
  These tests supplement, rather than substitute for, the listening checks.
- Final Android build and `lintDebug` passed with no lint issues. The final APK
  includes explicit backup exclusions for old and new Android versions.
- Removing the specific ADB audio forward produced an actionable preflight
  error without a paid call or desktop playback. Reinstall/connect restored it.

## Initial Publication Checks

- Verified the project-local Ubuntu GitHub login as `kadiru` and configured a
  repository-local author identity with the account's no-reply email.
- Created a fresh public `kadiru/irona` with default branch `main`. The owner's
  renamed `irona-legacy` repository remains private; none of its history is used.
- Re-ran all 66 Python tests without live paid calls. Public candidates contain
  application/player source, setup scripts, focused tests, and documentation.
- Verified that `.env`, runtime/models/audio, OAuth/ADB/pairing/signing keys,
  virtualenv, and Android build outputs are excluded from Git. Scanned the exact
  staged content for known local secrets, private-key and common token markers,
  unexpected symlinks, and large files before committing.
