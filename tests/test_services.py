import json
import subprocess
import sys
import threading
import time

import httpx
import pytest

from irona.services import Cancelled, PipelineError, Services


def test_local_chat_uses_history_and_only_final_answer(config):
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.host == "127.0.0.1"
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["messages"][1]["content"] == "My name is Kadir."
        assert payload["options"]["num_ctx"] == 4096
        return httpx.Response(200, json={"message": {"content": "Hello Kadir!", "thinking": "do not speak this"}})
    services = Services(config, httpx.MockTransport(handler))
    assert services.reply([{"role": "user", "content": "My name is Kadir."}], "Hello", threading.Event()) == "Hello Kadir!"


@pytest.mark.parametrize("status", [401, 402, 403, 404, 422, 429, 500])
def test_tts_errors_are_actionable_and_do_not_leak_or_retry(config, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": config.api_key})
    with pytest.raises(PipelineError) as error:
        Services(config, httpx.MockTransport(handler)).synthesize("Hello", threading.Event())
    assert str(status) in str(error.value)
    assert config.api_key not in str(error.value)
    assert len(calls) == 1


def test_voice_and_synthesis_contract(config):
    def handler(request):
        assert request.headers["xi-api-key"] == config.api_key
        assert request.url.path.endswith(config.voice_id)
        assert request.url.params["output_format"] == "mp3_44100_128"
        assert json.loads(request.content)["model_id"] == "eleven_flash_v2_5"
        return httpx.Response(200, content=b"audio", headers={"content-type": "audio/mpeg"})
    assert Services(config, httpx.MockTransport(handler)).synthesize("Hello", threading.Event()) == b"audio"


def test_timeout_is_clear(config):
    def handler(request):
        raise httpx.ReadTimeout("private detail", request=request)
    with pytest.raises(PipelineError, match="inference timed out"):
        Services(config, httpx.MockTransport(handler)).reply([], "Hello", threading.Event())


@pytest.mark.parametrize("data", [{}, {"message": {"content": ""}}, {"message": {"content": ["bad"]}}, {"message": {"content": "x" * 1001}}])
def test_invalid_model_output_never_reaches_speech(config, data):
    with pytest.raises(PipelineError):
        Services(config, httpx.MockTransport(lambda _: httpx.Response(200, json=data))).reply([], "Hello", threading.Event())


def test_audio_cancellation_reaps_real_child_process(config, monkeypatch):
    processes = []
    real_popen = subprocess.Popen
    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(subprocess, "Popen", popen)
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            Services._run_process([sys.executable, "-c", "import time; time.sleep(10)"], cancel, 5, "failed")
    finally:
        timer.join()
    assert processes[0].poll() is not None


def test_audio_timeout_reaps_child():
    start = time.monotonic()
    with pytest.raises(PipelineError, match="deadline"):
        Services._run_process([sys.executable, "-c", "import time; time.sleep(10)"], threading.Event(), 0.1, "deadline")
    assert time.monotonic() - start < 3


def test_temp_audio_removed_on_playback_failure(config, monkeypatch):
    services = Services(config)
    monkeypatch.setattr(services, "check_audio", lambda: None)
    def process(args, *rest):
        if args[0] == "ffmpeg":
            from pathlib import Path
            Path(args[-1]).write_bytes(b"wav")
        else:
            raise PipelineError("output disconnected")
    monkeypatch.setattr(services, "_run_process", process)
    with pytest.raises(PipelineError, match="disconnected"):
        services.play(b"mp3", threading.Event(), lambda: None)
    assert list((config.root / ".runtime" / "audio").iterdir()) == []


def test_audio_output_failure_is_actionable(config, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/tool")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b"[]"))
    with pytest.raises(PipelineError, match="audio output is unavailable"):
        Services(config).check_audio()


def test_tts_rejects_redirect_without_forwarding_credentials(config):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://untrusted.example/audio"})
    with pytest.raises(PipelineError, match="302"):
        Services(config, httpx.MockTransport(handler)).synthesize("Hello", threading.Event())
    assert len(calls) == 1
    assert calls[0].url.host == "api.elevenlabs.io"
