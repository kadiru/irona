import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from .errors import Cancelled, PipelineError
from .temi import TemiPlayback


def read_response(response, limit, deadline, cancel=None):
    data = bytearray()
    for chunk in response.iter_bytes():
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if time.monotonic() > deadline:
            raise PipelineError("The service exceeded its time limit. Try again when it is available.")
        data.extend(chunk)
        if len(data) > limit:
            raise PipelineError("The service returned an unexpectedly large response. Shorten the message.")
    return bytes(data)


class Services:
    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport
        self.temi = TemiPlayback(config, transport) if config.audio_output == "temi" else None

    def client(self, seconds):
        return httpx.Client(
            timeout=httpx.Timeout(seconds, connect=5, write=10, pool=5),
            trust_env=False, follow_redirects=False, transport=self.transport,
        )

    def reply(self, history, text, cancel):
        cfg = self.config
        payload = {
            "model": cfg.llm_model,
            "messages": [{"role": "system", "content": cfg.system_prompt}, *history, {"role": "user", "content": text}],
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"num_predict": 160, "num_ctx": 4096, "temperature": 0.7},
        }
        try:
            with self.client(cfg.llm_timeout) as client:
                with client.stream("POST", f"{cfg.llm_url}/api/chat", json=payload) as response:
                    if response.status_code == 404:
                        raise PipelineError(f"Local model {cfg.llm_model} is missing. Pull it into the project's Ollama server.")
                    if response.status_code != 200:
                        raise PipelineError(f"Ollama returned HTTP {response.status_code}. Check its log and local model configuration.")
                    data = json.loads(read_response(response, 2_000_000, time.monotonic() + cfg.llm_timeout, cancel))
            if cancel.is_set():
                raise Cancelled()
            content = data["message"]["content"]
            if not isinstance(content, str):
                raise ValueError()
            # Only the final answer is spoken; thinking and tool calls are ignored.
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
            if not content or "<think>" in content or len(content) > 1000:
                raise PipelineError("The local model did not return a short spoken reply. Reset or try a simpler message.")
            return content
        except httpx.TimeoutException:
            raise PipelineError("Local inference timed out. Check Ollama and available GPU memory, then try again.") from None
        except httpx.RequestError:
            raise PipelineError("Cannot reach local Ollama. Start it with 'bash scripts/ollama.sh serve'.") from None
        except (ValueError, KeyError, TypeError):
            raise PipelineError("Ollama returned an invalid response. Check the selected local model.") from None

    def synthesize(self, text, cancel):
        cfg = self.config
        if not cfg.api_key:
            raise PipelineError("Set ELEVENLABS_API_KEY in Ubuntu's private .env and restart Irona.")
        settings = {"stability": 0.5}
        if cfg.tts_model != "eleven_v3":
            settings.update(similarity_boost=0.75, style=0.0, speed=1.0, use_speaker_boost=False)
        try:
            with self.client(cfg.tts_timeout) as client:
                with client.stream(
                    "POST", f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.voice_id}",
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": cfg.api_key},
                    json={"text": text, "model_id": cfg.tts_model, "voice_settings": settings},
                ) as response:
                    if response.status_code != 200:
                        hints = {
                            401: "Check the API key, expiry, and Text to Speech permission.",
                            402: "Check the ElevenLabs credit balance and per-key credit limit.",
                            403: "Check key permissions, voice access for your plan, and the per-key credit limit.",
                            404: "Check ELEVENLABS_VOICE_ID and access to this voice.",
                            422: "Check the voice, model, and their supported settings.",
                            429: "Check the credit limit or wait for the rate limit to clear.",
                        }
                        hint = hints.get(response.status_code, "The speech service is unavailable. Try again later.")
                        raise PipelineError(f"ElevenLabs returned HTTP {response.status_code}. {hint}")
                    data = read_response(response, 8_000_000, time.monotonic() + cfg.tts_timeout, cancel)
                    if not response.headers.get("content-type", "").startswith(("audio/", "application/octet-stream")) or not data:
                        raise PipelineError("ElevenLabs did not return audio. Check the voice and model settings.")
                    return data
        except httpx.TimeoutException:
            raise PipelineError("Speech synthesis timed out. Check internet access; a request may still have used credits.") from None
        except httpx.RequestError:
            raise PipelineError("Cannot reach ElevenLabs. Check Ubuntu's internet connection; the request was not retried.") from None

    def check_audio(self):
        if self.temi:
            return self.temi.check()
        for name in ("ffmpeg", "paplay", "pactl"):
            if not shutil.which(name):
                raise PipelineError(f"Audio requires '{name}' on Ubuntu. Install it before starting speech.")
        try:
            result = subprocess.run(["pactl", "-f", "json", "list", "sinks"], capture_output=True, timeout=5, check=True)
            sinks = json.loads(result.stdout)
            sink = next((s for s in sinks if s["name"] == self.config.audio_sink), None)
            if sink is None:
                raise PipelineError("Configured audio output is unavailable. Check IRONA_AUDIO_SINK with 'pactl list short sinks'.")
            if sink.get("mute"):
                raise PipelineError("The configured Ubuntu audio output is muted. Unmute it in Ubuntu Sound settings.")
            return sink
        except (subprocess.SubprocessError, OSError, ValueError, KeyError):
            raise PipelineError("Cannot access the Ubuntu audio session. Log into the desktop as the user running Irona.") from None

    def play(self, audio, cancel, on_speaking):
        if self.temi:
            return self.temi.play(audio, cancel, on_speaking)
        self.check_audio()
        temp_root = self.config.root / ".runtime" / "audio"
        temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix="turn-", dir=temp_root) as folder:
            source, decoded = Path(folder) / "reply.mp3", Path(folder) / "reply.wav"
            source.write_bytes(audio)
            self._run_process(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vn", "-ar", "24000", "-ac", "1", str(decoded)],
                cancel, 15, "Audio decoding failed or timed out. Check FFmpeg and the audio format.",
            )
            if cancel.is_set():
                raise Cancelled()
            self._run_process(
                ["paplay", f"--device={self.config.audio_sink}", "--client-name=Irona", "--stream-name=Irona", f"--volume={round(self.config.volume * 65536 / 100)}", str(decoded)],
                cancel, self.config.playback_timeout,
                "Ubuntu audio playback failed or timed out. Check the configured speaker connection.", on_speaking,
            )

    @staticmethod
    def _run_process(args, cancel, timeout, error, on_started=None):
        try:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            raise PipelineError(error) from None
        try:
            if on_started:
                on_started()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancel.wait(0.05):
                    raise Cancelled()
                if time.monotonic() > deadline:
                    raise PipelineError(error)
            if process.returncode:
                raise PipelineError(error)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
