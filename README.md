# Irona

Type a message, generate a reply locally, synthesize it with ElevenLabs, and play
it through an explicitly configured Temi robot or Ubuntu speaker.

The browser is a controller, never an audio destination. **Ubuntu desktop
speakers are a development fallback, not robot integration.** ElevenLabs
receives reply text, so this is **not fully offline**.

## Architecture

```text
Browser -> Ubuntu localhost Flask app -> local Ollama -> ElevenLabs HTTPS
                                     -> ADB forward -> Temi player -> speakers
                                     OR FFmpeg -> paplay -> Ubuntu sink
```

Ubuntu runs inference, TTS requests, and the controller; a small native Android
app plays audio on Temi. A Mac can control Irona through an SSH tunnel.
The owner confirmed Elise and three consecutive conversational replies from
Temi's speakers. Stop, context recall, and reset passed live checks.
See `docs/temi-integration.md` before selecting `IRONA_AUDIO_OUTPUT=temi`.
There is no frontend build, browser audio, ROS, database, or agent framework.
One worker handles one turn at a time. The browser polls for stage changes.

- Local model: `qwen3.5:4b`, thinking disabled, 4,096-token context.
- Voice: Elise - Warm, Natural and Engaging (`EST9Ui6982FZPSi7gCHi`).
- TTS model: `eleven_flash_v2_5`, chosen for short conversational replies.
- Personality: edit `irona/system_prompt.txt` and restart. Replies are normally
  one or two sentences.
- History: last six reply pairs in memory; UI retains up to 40 messages. Reset
  clears both; a restart starts a fresh conversation.
- Temporary MP3/WAV files live under ignored `.runtime/audio/` and are removed
  after playback, failure, or stop. Power loss or forced termination can leave
  temporary files. Irona does not write transcript files.
- Stop applies during playback, not generation or synthesis. Stopped/failed
  speech remains visible and in model context, with its delivery state marked.

## Setup On Ubuntu

The development checkout is `/home/kadir/code/irona`. Run commands from the
project root. Tested host: Ubuntu 22.04, Python 3.10, RTX 4090, and a logged-in
desktop PulseAudio session. Temi was tested on Android 6.0.1 (API 23).
The Mac is not the inference or playback host.

Prerequisites: Python 3.10+ with venv/pip, `curl`, `tar`, `zstd`, and a suitable GPU
driver. Desktop output additionally uses `ffmpeg`, `paplay`, and `pactl`.
These already existed on the tested
desktop. No script installs system packages or services.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
```

`requirements.lock` pins the tested application and test dependencies on Python
3.10. `pyproject.toml` declares direct dependencies. Editable installation is
intentional: configuration and the prompt live in the checkout.

### Private Configuration

If `.env` does not exist yet:

```bash
(umask 077; cp -n .env.example .env)
chmod 600 .env
nano .env
```

Enter `ELEVENLABS_API_KEY` in the editor, never a shell command, chat, screenshot,
browser code, or Git. Restrict the key to Text to Speech; Voices read is optional
for lookup. Set a finite expiry and credit cap. Other permissions are unnecessary.
The voice ID is configuration, not a credential.

Set `IRONA_AUDIO_OUTPUT=temi` for the paired robot, following
`docs/temi-integration.md`. The verified development machine now selects Temi;
the portable example defaults to desktop and never selects an unknown robot.

For `IRONA_AUDIO_OUTPUT=desktop`, choose an output with `pactl list short sinks`, then set
`IRONA_AUDIO_SINK` to its full name. The example uses this desktop's analog
line-out and is machine-specific. `IRONA_VOLUME=60` is stream volume, not master
volume. Keep speakers on and start at a moderate level. Environment variables
override `.env`; restart the app after changes.

### Local Inference

Reuse a suitable local Ollama server if one already exists. Configure
`OLLAMA_BASE_URL` and `OLLAMA_MODEL`; do not start another server on an occupied
port. Irona accepts only loopback inference URLs. Keep cloud models disabled on
the selected server.

For the project-contained Linux x86-64 installation:

```bash
bash scripts/install-ollama.sh
```

This downloads Ollama 0.34.4 (about 1.4 GB), verifies its pinned SHA-256 checksum,
and unpacks it into `.runtime/ollama/`, without sudo.

Ollama requires `~/.ollama` for identity files. The owner approved a symlink to
`.runtime/ollama-config` on this desktop. On a fresh machine, only create that
link after checking for an existing installation; never replace existing files.
The optional Temi setup also uses a separately approved `~/.android` symlink:

```bash
mkdir -p .runtime/ollama-config
if [ ! -e "$HOME/.ollama" ] && [ ! -L "$HOME/.ollama" ]; then
  ln -s "$PWD/.runtime/ollama-config" "$HOME/.ollama"
fi
```

Start the inference server in a separate terminal:

```bash
bash scripts/ollama.sh serve
```

Download the model once, about 3.4 GB:

```bash
bash scripts/ollama.sh pull qwen3.5:4b
```

The wrapper binds to `127.0.0.1:11434`, disables Ollama cloud features, keeps
models/cache in `.runtime/`, and selects GPU 0 by default. Override
`CUDA_VISIBLE_DEVICES` before launching to select another GPU. The first cold
request can take substantially longer than subsequent requests.

## Launch

With Ollama running, the application launch command is:

```bash
.venv/bin/python -m irona
```

Open **http://127.0.0.1:8000** on Ubuntu. Ctrl+C stops the application and active
playback. Stop the separate Ollama terminal with Ctrl+C when finished. Neither
process is installed as an automatic startup service.

For a Mac controller, keep an SSH tunnel open, substituting your host and SSH
identity configuration:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8000:127.0.0.1:8000 user@ubuntu-host
```

Open the same localhost URL on the Mac; audio uses the configured Temi or Ubuntu
output, never the Mac browser. If the Mac port
is occupied, change only the first `8000` and open that local port. Do not expose
either server on the LAN without first designing authentication/access controls.
Irona rejects non-loopback bind addresses and unexpected Host headers.

## Verification

Automated tests mock external services and spend no ElevenLabs credits:

```bash
.venv/bin/python -m pytest -q
```

Manual component checks:

```bash
.venv/bin/python scripts/check.py audio
.venv/bin/python scripts/check.py tone
.venv/bin/python scripts/check.py llm
.venv/bin/python scripts/check.py tts
```

`audio` checks output availability (and desktop mute state) without playing
anything. `tone` plays a short, credit-free sound on the explicitly selected
output. `llm`
makes one local inference request. **`tts` spends credits** on a fixed sentence
and plays it through the configured output; a person must confirm audibility.
See `docs/verification.md` for observed results and remaining limitations.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Playback completed but no sound | Physical power/volume, Ubuntu Sound output, and `IRONA_AUDIO_SINK`; process success alone does not prove audibility. |
| Audio session unavailable | Log into Ubuntu's desktop as the same user running Irona. Do not run the app with sudo. |
| Temi connection failed | Keep Irona Player foreground, open Temi's ADB port on the trusted LAN, then run `.venv/bin/python scripts/temi.py connect`. No desktop fallback occurs. |
| Temi completes silently | Check Temi's own media volume. `IRONA_VOLUME` scales the stream and does not override a muted robot. |
| Cannot reach Ollama | Start the server, check `OLLAMA_BASE_URL`, run the `llm` check. |
| Missing model or slow reply | Pull the configured tag; check `bash scripts/ollama.sh ps` and free GPU memory. Cold loading can be slow. |
| ElevenLabs 401/403 | Check key expiry, TTS permission, voice access, and per-key limits. |
| ElevenLabs 402/429 | Check credits and rate limits. Requests are not automatically retried because they may incur charges. |
| Voice/model rejected | Check voice ID and model access. Voice settings differ for `eleven_v3`. |
| Port in use | Set `IRONA_PORT` to a free port and update the SSH tunnel destination. |
| Commands fail after restart | Reload the browser for the new per-process command token. |

Inference, TTS, decoding, and playback have timeouts. Common failures appear in
the UI without raw service bodies or credentials. A synthesis timeout may still
consume credits. Shutdown stops playback and prevents late inference results
from beginning speech. This local development server is not for an untrusted
network or multiple independent conversations.

## Repository And Next Steps

The public repository is [kadiru/irona](https://github.com/kadiru/irona), under the
owner's personal account. This is a fresh repository for the working typed-input
and Temi-speaking demo, separate from the owner's older private project.
Runtime binaries, model weights, keys, private configuration, and audio are
excluded. See `docs/publishing.md` for account checks and the push workflow.

A project license has not yet been selected. Bundled third-party components and
icons retain their included license notices.

Next: tune conversation personality, then agree on push-to-talk input or a
production transport before extending the demo. The current Temi app requires
foreground operation and a development ADB connection. Microphone input,
streaming, browser LAN access, motion, ROS, retrieval, and
long-term memory are outside this first demo. See `AGENTS.md` and
`docs/decisions.md` before extending the project.
