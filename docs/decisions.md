# Day-One Decisions

Accepted 2026-09-24.

1. **Ubuntu owns the runtime.** Inference, TTS requests, and playback run in the
   same desktop user's session. The Mac is a controller via SSH. Project storage
   is `/home/kadir/code/irona`; no runtime installation is needed on Mac.
2. **One background worker.** Flask serves static assets and JSON endpoints;
   browser polling exposes stages without a streaming transport. One active turn
   prevents overlapping speech.
3. **Ollama and a four-billion-parameter model.** No suitable server existed during
   inspection. Project-local Ollama 0.34.4 and qwen3.5:4b fit the RTX 4090. Cloud
   inference is disabled. No generalized provider framework is needed.
4. **Direct ElevenLabs HTTP.** httpx handles both service calls without an extra
   SDK. Elise with Flash v2.5 provides short conversational speech. Voice and
   models are configurable; paid requests are never automatically retried.
5. **Explicit server-side audio.** Existing FFmpeg decodes responses and paplay
   targets a named PulseAudio sink. Stop terminates/reaps playback. Desktop
   speakers remain a development output, not a completed robot transport.
6. **Bounded memory and privacy.** Six reply pairs, no transcript persistence,
   temporary audio, server-side keys, localhost-only listeners. Reply text leaves
   the machine for ElevenLabs. Provider-side retention depends on account/service
   settings; deleting local audio does not remove provider-side records.
7. **Project-contained installation.** Runtime, models, caches, logs, and venv are
   ignored. The initially approved outside-project filesystem change was `~/.ollama`
   pointing to `.runtime/ollama-config` for identity files. No system service or
   startup automation was installed.
8. **Publication is separate.** Target the personal `kadiru` account. Verify Git
   identity, authentication, and ignored secrets before the first push. Do not
   inherit another account's authentication. Ask for the project's license choice.

## Temi Milestone

Accepted and hardware-tested 2026-09-24; these extend the desktop baseline above.

1. **Keep inference and TTS on Ubuntu.** Only playback moves to Temi. The browser
   remains a controller and the ElevenLabs key never reaches the robot.
2. **Small native player, no Temi SDK yet.** Android MediaPlayer preserves Elise's
   generated voice without introducing movement or robot command APIs. NanoHTTPD
   supplies the bounded authenticated loopback receiver.
3. **ADB is a development transport.** A device-specific loopback forward avoids
   opening an unauthenticated application listener on the LAN. ADB itself is
   privileged and must be closed on Temi when finished. The foreground app is not
   an unattended deployment solution.
4. **Acknowledge playback and fail closed.** Select desktop or Temi explicitly,
   never fall back automatically. Native start/completion/stop callbacks and a
   3.5-second heartbeat lease keep the UI honest and bound orphaned playback.
5. **Approved local tools and app installation.** Android tools, JDK, Gradle,
   signing keys, and pairing token stay under ignored `.runtime/`. The separately
   approved `~/.android` symlink points there. No Mac tools or firmware updates
   were installed. Public repository creation remains a separate step.

## First Public Checkpoint

The owner requested publication after the working Temi milestone and renamed
their older private repository to `irona-legacy`. Create a fresh public
`kadiru/irona` without importing or exposing that history. GitHub authentication
is isolated in ignored project storage on Ubuntu; commits use a no-reply email.
The initial source snapshot leaves the project license undecided pending the
owner's choice. Keep all bundled third-party license notices.

## References

- [Ollama Linux installation](https://docs.ollama.com/linux)
- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Qwen3.5 4B model](https://ollama.com/library/qwen3.5:4b)
- [Ollama GPU selection](https://docs.ollama.com/gpu)
- [ElevenLabs TTS API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)

Bundled icons are from Lucide; their license is in `irona/static/icons/LICENSE`.
