import pytest

from irona.config import Config, ConfigError, loopback_url


@pytest.mark.parametrize("url", ["https://api.example.com", "http://192.168.1.2:11434", "http://localhost.evil.test", "http://user:secret@localhost", "http://127.0.0.1/?key=secret", "not-a-url"])
def test_remote_inference_is_rejected(url):
    with pytest.raises(ConfigError):
        loopback_url(url)


def test_local_url_supported():
    assert loopback_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert loopback_url("http://[::1]:11434") == "http://[::1]:11434"


def test_config_precedence_and_secret_redaction(config):
    (config.root / ".env").write_text('ELEVENLABS_API_KEY="literal-${NOT_EXPANDED}"\nIRONA_PORT=8001\n')
    loaded = Config.load(config.root, {"IRONA_PORT": "8010"})
    assert loaded.api_key == "literal-${NOT_EXPANDED}"
    assert loaded.port == 8010
    assert loaded.api_key not in repr(loaded)


@pytest.mark.parametrize("setting,value", [("IRONA_PORT", "zero"), ("IRONA_VOLUME", "0"), ("IRONA_HISTORY_TURNS", "1000"), ("IRONA_HOST", "0.0.0.0"), ("OLLAMA_MODEL", "qwen3.5:cloud"), ("ELEVENLABS_VOICE_ID", "../secret"), ("IRONA_AUDIO_SINK", "@DEFAULT_SINK@")])
def test_invalid_configuration_is_actionable(config, setting, value):
    with pytest.raises(ConfigError, match=setting):
        Config.load(config.root, {setting: value})
