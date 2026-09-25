# Irona Project Instructions

- Collaborate on design and implement small, understandable increments.
- Ubuntu is the runtime host; the Mac is the programming interface. Keep the
  canonical project under `/home/kadir/code/irona` and any persistent Mac-side
  project files under `/Users/kadir/code/irona`.
- Preserve the distinction between confirmed decisions and proposals in README.md.
- The initial plan, project-local Ollama installation, and qwen3.5:4b download
  were approved on 2026-09-24. Ask before additional large downloads,
  system-level changes, or writes outside the project. The owner also approved
  ~/.ollama as a symlink into the project's ignored .runtime/ollama-config.
- The owner subsequently approved project-local Android/JDK/Gradle tools (about
  1 GB download budget) and installing the Irona Player APK on Temi. The required
  ~/.android symlink to .runtime/android-user was separately approved and created.
  The build-created analytics settings directory was preserved in ignored
  .runtime/android-home-before-link. Do not update firmware,
  root the robot, enable motion, or infer permission for other device changes.
- Target the personal public repository `kadiru/irona`. Verify authentication
  and commit identity before publishing; do not inherit the Mac's other account.
  The fresh public repository now exists; the owner renamed the old repository
  to irona-legacy and it remains private. Do not change its visibility or history.
  Use scripts/gh.sh for the isolated Ubuntu login and repo-local Git identity.
  No project license has been chosen; do not add one without the owner's choice.
- Use a local LLM. ElevenLabs is cloud TTS, so synthesized reply text leaves
  the machine. Never describe the whole pipeline as offline.
- Play audio on the server through a configured destination. Ubuntu speakers
  are the initial development fallback and do not prove robot integration.
  Temi speaker playback is now owner-confirmed through the native Irona Player.
  Keep its app in the foreground and ADB on a trusted LAN for this development
  transport; close Temi's debugging port when finished. Never silently fall back.
- Keep keys in the private `.env`; never print its contents, put secrets in
  browser code, or commit credentials. `.env.example` contains placeholders.
- Keep services on localhost and never execute model output as commands.
- Prefer a single active turn, short responses, bounded in-memory history,
  temporary audio, explicit timeouts, and actionable errors.
- Mock paid services in automated tests. Report actual hardware verification
  separately from mocks and from successful process exit codes.
- Run `.venv/bin/python -m pytest -q` after changes. The `tts` manual check uses
  credits and makes real sound; never include it in the automated test suite.
- Keep decisions and verification evidence under docs/. Do not commit private
  keys, live transcripts, generated audio, or machine secrets.
- Avoid ROS, agent frameworks, frontend build systems, containers, and permanent
  transcripts unless an agreed requirement calls for them.
