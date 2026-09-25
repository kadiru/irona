import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


class ConfigError(ValueError):
    pass


def loopback_url(value, name="OLLAMA_BASE_URL"):
    try:
        url = urlsplit(value)
        host = url.hostname
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
        port = url.port
    except (ValueError, TypeError):
        local = False
    if not local or url.scheme != "http" or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        raise ConfigError(f"{name} must be a loopback HTTP address without credentials, paths, or query parameters.")
    return value.rstrip("/")


@dataclass(frozen=True)
class Config:
    root: Path
    api_key: str = field(repr=False)
    voice_id: str
    tts_model: str
    llm_url: str
    llm_model: str
    host: str
    port: int
    audio_sink: str
    volume: int
    history_turns: int
    llm_timeout: int
    tts_timeout: int
    playback_timeout: int
    system_prompt: str
    audio_output: str = "desktop"
    temi_url: str = "http://127.0.0.1:8766"
    temi_token_file: Path | None = None

    @classmethod
    def load(cls, root=None, environ=None):
        root = Path(root or Path(__file__).resolve().parent.parent)
        # Disable interpolation so dollar signs in credentials are never expanded.
        values = {**dotenv_values(root / ".env", interpolate=False), **(os.environ if environ is None else environ)}

        def value(name, default=""):
            return str(values.get(name) or default).strip()

        def integer(name, default, low, high):
            try:
                result = int(value(name, str(default)))
            except ValueError:
                raise ConfigError(f"{name} must be an integer between {low} and {high}.") from None
            if not low <= result <= high:
                raise ConfigError(f"{name} must be between {low} and {high}.")
            return result

        voice = value("ELEVENLABS_VOICE_ID", "EST9Ui6982FZPSi7gCHi")
        if not re.fullmatch(r"[A-Za-z0-9]{10,64}", voice):
            raise ConfigError("ELEVENLABS_VOICE_ID must be a voice ID from ElevenLabs.")
        tts_model = value("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", tts_model):
            raise ConfigError("ELEVENLABS_MODEL_ID is invalid.")
        model = value("OLLAMA_MODEL", "qwen3.5:4b")
        if "cloud" in model.lower() or not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,160}", model):
            raise ConfigError("OLLAMA_MODEL must name a downloaded local model; cloud models are disabled.")
        host = value("IRONA_HOST", "127.0.0.1")
        if host not in ("127.0.0.1", "localhost"):
            raise ConfigError("IRONA_HOST must be 127.0.0.1 or localhost. Use an SSH tunnel for remote access.")
        sink = value("IRONA_AUDIO_SINK", "alsa_output.pci-0000_00_1f.3.analog-stereo")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,200}", sink):
            raise ConfigError("IRONA_AUDIO_SINK must name a specific PulseAudio sink from 'pactl list short sinks'.")
        prompt_path = Path(value("IRONA_SYSTEM_PROMPT", "irona/system_prompt.txt"))
        if not prompt_path.is_absolute():
            prompt_path = root / prompt_path
        try:
            prompt = prompt_path.read_text().strip()
        except OSError:
            raise ConfigError("System prompt file is missing or unreadable. Check IRONA_SYSTEM_PROMPT.") from None
        if not prompt or len(prompt) > 16000:
            raise ConfigError("System prompt must contain 1 to 16000 characters.")
        output = value("IRONA_AUDIO_OUTPUT", "desktop")
        if output not in ("desktop", "temi"):
            raise ConfigError("IRONA_AUDIO_OUTPUT must be desktop or temi; there is no automatic fallback.")
        temi_url = loopback_url(value("IRONA_TEMI_URL", "http://127.0.0.1:8766"), "IRONA_TEMI_URL")
        token_file = root / ".runtime" / "temi" / "token"
        return cls(
            root, value("ELEVENLABS_API_KEY"), voice, tts_model,
            loopback_url(value("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
            model, host, integer("IRONA_PORT", 8000, 1024, 65535), sink,
            integer("IRONA_VOLUME", 60, 1, 100), integer("IRONA_HISTORY_TURNS", 6, 1, 12),
            integer("IRONA_LLM_TIMEOUT", 90, 5, 300),
            integer("IRONA_TTS_TIMEOUT", 45, 5, 120),
            integer("IRONA_PLAYBACK_TIMEOUT", 45, 5, 180), prompt,
            output, temi_url, token_file,
        )
