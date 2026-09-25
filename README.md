# Irona

Irona is a small conversational application with a robot audio endpoint. Type a
message in a browser, generate a reply on an Ubuntu desktop, convert it into
speech with ElevenLabs, and hear it through a Temi robot.

The project connects existing AI and audio components; it does not train a new
model or introduce a full robotics framework. Its own code consists of a browser
interface, a Python coordinator, a small Android player, setup scripts, and tests.

**Ubuntu generates and coordinates, ElevenLabs synthesizes, Temi speaks, and
the browser controls.** Reply text leaves the machine for ElevenLabs, so this
is **not fully offline**. Ubuntu speakers are an explicitly selected development
output, never an automatic fallback when Temi is unavailable.

[How it works](#architecture) | [Ubuntu setup](#setup-on-ubuntu) |
[Launch](#launch) | [Temi setup](docs/temi-integration.md) |
[Verification](docs/verification.md)

## Architecture

```text
Browser on the Mac
        |
        | HTTP through an SSH tunnel
        v
Irona Python application on Ubuntu
        |
        +--> Ollama --> Qwen model on the Ubuntu GPU
        |                 |
        |<----------------+ reply text
        |
        +--> ElevenLabs cloud
        |          |
        |<---------+ speech audio
        |
        +--> ADB connection over Wi-Fi
                   |
                   v
            Irona Player on Temi
                   |
              Temi speakers
```

The browser can also run directly on Ubuntu without the SSH tunnel. In either
case it only sends commands and displays state; it never plays the audio.

| Component | Responsibility | Runs on |
| --- | --- | --- |
| Browser interface | Message input, transcript, status, Stop, and Reset | Controller browser |
| Irona backend | Coordinates the conversation, service calls, and playback | Ubuntu, using Python and Flask |
| Ollama | Loads and runs the language model; provides a local API | Ubuntu |
| Qwen `qwen3.5:4b` | Generates the actual response text | Ubuntu's GPU |
| ElevenLabs | Converts the reply into Elise's voice | ElevenLabs cloud |
| Irona Player | Receives audio, plays it, and reports playback state | Temi's Android tablet |

### Ollama And The Model

**Ollama runs the model; Qwen is the model.** Ollama downloads model files,
loads the selected model, and accepts requests from applications. Irona calls its
local HTTP chat API at `127.0.0.1:11434`. Our wrapper disables cloud features.

Qwen is the pretrained neural network that produces the reply. The current
configuration uses `qwen3.5:4b` on the tested desktop's RTX 4090, with a
4,096-token context and thinking disabled. Generating an answer with that model
is called inference. Irona does not train or fine-tune it during conversation.

### A Conversation Turn

1. You type a message. The browser sends it to Irona's Flask application on
   Ubuntu. Flask is the lightweight web server serving the UI and its API.
2. Irona checks that the selected audio output is reachable before making an
   inference request or spending speech credits.
3. Irona sends Ollama the system prompt, recent conversation, and new message.
   Qwen generates a short reply, which Irona adds to the transcript.
4. Irona sends that reply text to ElevenLabs over HTTPS, using the Elise voice
   and `eleven_flash_v2_5` speech model. ElevenLabs returns MP3 audio.
5. Ubuntu sends the audio to Irona Player on Temi. The player reports when
   playback actually starts and finishes.
6. The browser polls Ubuntu for state, displaying generating, synthesizing,
   speaking, or an actionable error. When the turn finishes, another can begin.

One background worker handles one turn at a time to prevent overlapping speech.
The initial implementation waits for the full text reply and synthesized audio
before playback; it does not stream partial speech.

### The Temi Connection

Temi runs Android. Irona Player is a small Java application, installed as an APK,
that uses Android's `MediaPlayer` to play the received audio. It does not run the
LLM, contact ElevenLabs, or use Temi's built-in text-to-speech voice.

ADB, or Android Debug Bridge, installs the app and provides the current
development connection over Wi-Fi. A device-specific port forward connects
Ubuntu's loopback port 8766 to the player's loopback HTTP endpoint on Temi.
Requests need a private pairing token. The ElevenLabs API key stays on Ubuntu.

Ubuntu checks playback about every 200 milliseconds. If these heartbeats stop,
Temi stops playback after roughly 3.5 seconds. Browser Stop and the native Stop
button both stop audio. There is no silent fallback to another speaker.

**This is a development transport, not an unattended deployment.** The player
must stay in the foreground. ADB enables privileged device access: use a trusted
LAN and close Temi's debugging port when finished. No firmware update, Temi SDK,
ROS dependency, or movement integration is required for this audio milestone.
See [Temi integration](docs/temi-integration.md) for setup and reconnect commands.

### Memory, Personality, And Privacy

- **Conversation context:** Irona includes the latest six user/reply pairs in
  subsequent model requests. This is temporary context in RAM, not learning or
  permanent memory. The UI retains up to 40 messages. Reset or restarting the
  application clears the conversation; transcripts are not written to disk.
- **Personality:** [The system prompt](irona/system_prompt.txt) sets warmth,
  brevity, and conversational habits. Edit it and restart to change behavior.
  Replies are normally one or two sentences. The prompt shapes what Irona says;
  the selected voice and speech settings shape how it sounds.
- **Voice:** The current voice is Elise - Warm, Natural and Engaging
  (`EST9Ui6982FZPSi7gCHi`). The voice ID and speech model are configurable.
- **Cloud boundary:** Inference stays on Ubuntu, but the generated reply is
  sent to ElevenLabs and can contain personal details from the conversation.
  Local cleanup does not control the provider's retention policies.
- **Temporary audio:** Temi uses app-private temporary files. Desktop mode uses
  ignored `.runtime/audio/` MP3/WAV files with FFmpeg and paplay. Normal
  completion, stop, and failures trigger cleanup; forced termination or power
  loss can leave files behind.
- **Stop behavior:** Stop acts during playback, not generation or synthesis.
  Stopped or failed replies remain visible and in model context, with delivery
  state marked. Reset is available when no turn is active.

### Current Scope

The owner confirmed hearing Elise and three consecutive conversational replies
from the actual Temi speakers. Context recall, reset, browser/native Stop, and
heartbeat expiry passed live checks; 66 automated tests cover the application
and mocked services. [Verification notes](docs/verification.md) distinguish
hardware evidence from automated tests.

There is no microphone input, vision, navigation, autonomous movement, or
LLM-generated actuator command execution. There is also no database, long-term
memory, frontend build system, or agent framework. GitHub stores the source and
history; it does not run the application.

### Code Map

| File or directory | Purpose |
| --- | --- |
| [irona/app.py](irona/app.py) | Browser page, JSON endpoints, and command checks |
| [irona/pipeline.py](irona/pipeline.py) | Turn ordering, history, status, Stop, and Reset |
| [irona/services.py](irona/services.py) | Ollama, ElevenLabs, and desktop audio calls |
| [irona/temi.py](irona/temi.py) | Ubuntu-side robot playback and acknowledgements |
| [irona/config.py](irona/config.py) | Environment configuration and validation |
| [android/](android/) | Native Temi player and build configuration |
| [tests/](tests/) | Focused tests with external services mocked |

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
