import threading
from dataclasses import replace

import httpx
import pytest

from irona.errors import Cancelled, PipelineError
from irona.services import Services
from irona.temi import TemiPlayback
from irona.config import Config, ConfigError


@pytest.fixture
def temi_config(config):
    token = config.root / ".runtime" / "temi" / "token"
    token.parent.mkdir(parents=True)
    token.write_text("t" * 43)
    return replace(config, audio_output="temi", temi_token_file=token)


class Robot:
    def __init__(self):
        self.calls = []
        self.session = "b" * 32
        self.id = ""
        self.state = "idle"
        self.started = False
        self.complete = True
        self.fail_stop = False
        self.disconnect = False
        self.restart = False

    def response(self):
        return httpx.Response(200, json={"protocol": "irona-temi/1", "session": self.session, "id": self.id, "state": self.state, "started": self.started, "error": ""})

    def __call__(self, request):
        self.calls.append(request)
        assert request.headers["authorization"] == "Bearer " + "t" * 43
        assert request.url.host == "127.0.0.1"
        path = request.url.path
        if path.startswith("/play/"):
            assert request.content == b"audio"
            self.id = path.rsplit("/", 1)[1]
            self.state = "preparing"
            return self.response()
        if path.startswith("/status/"):
            if self.disconnect:
                raise httpx.ConnectError("sensitive transport detail", request=request)
            if self.restart:
                self.session = "c" * 32
            self.state = "completed" if self.started and self.complete else "playing"
            self.started = True
        if path.startswith("/stop/"):
            if self.fail_stop:
                raise httpx.ReadTimeout("secret", request=request)
            self.state = "stopped"
        return self.response()


def player(config, robot):
    result = TemiPlayback(config, httpx.MockTransport(robot))
    result.poll_interval = 0.001
    return result


def test_temi_waits_for_start_and_completion(temi_config):
    robot = Robot()
    observed = []
    player(temi_config, robot).play(b"audio", threading.Event(), lambda: observed.append(robot.state))
    assert observed == ["playing"]
    assert robot.state == "completed"
    assert len([r for r in robot.calls if r.url.path.startswith("/play/")]) == 1


def test_temi_stop_waits_for_acknowledgement(temi_config):
    robot = Robot()
    robot.complete = False
    cancel = threading.Event()
    with pytest.raises(Cancelled):
        player(temi_config, robot).play(b"audio", cancel, cancel.set)
    assert robot.state == "stopped"


def test_temi_failed_stop_is_error_not_false_success(temi_config):
    robot = Robot()
    robot.complete = False
    robot.fail_stop = True
    cancel = threading.Event()
    with pytest.raises(PipelineError, match="connection failed"):
        player(temi_config, robot).play(b"audio", cancel, cancel.set)


def test_temi_disconnect_stops_and_does_not_report_success(temi_config):
    robot = Robot()
    robot.disconnect = True
    with pytest.raises(PipelineError, match="connection failed"):
        player(temi_config, robot).play(b"audio", threading.Event(), lambda: pytest.fail("No playback acknowledgement"))
    assert robot.state == "stopped"


def test_temi_restart_invalidates_playback(temi_config):
    robot = Robot()
    robot.restart = True
    with pytest.raises(PipelineError, match="restarted"):
        player(temi_config, robot).play(b"audio", threading.Event(), lambda: None)
    assert robot.state == "stopped"


def test_temi_local_stop_is_reported(temi_config):
    robot = Robot()
    robot.complete = False
    def handler(request):
        response = robot(request)
        if request.url.path.startswith("/status/"):
            robot.state = "stopped"
            return robot.response()
        return response
    with pytest.raises(Cancelled):
        player(temi_config, handler).play(b"audio", threading.Event(), lambda: None)


def test_temi_timeout_sends_stop(temi_config):
    robot = Robot()
    robot.complete = False
    with pytest.raises(PipelineError, match="timed out"):
        player(replace(temi_config, playback_timeout=0), robot).play(b"audio", threading.Event(), lambda: None)
    assert robot.state == "stopped"


def test_cancelled_audio_is_not_uploaded(temi_config):
    cancel = threading.Event()
    cancel.set()
    robot = Robot()
    with pytest.raises(Cancelled):
        player(temi_config, robot).play(b"audio", cancel, lambda: None)
    assert not robot.calls


def test_temi_never_uses_desktop_output(temi_config, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("Desktop playback was used"))
    robot = Robot()
    services = Services(temi_config, httpx.MockTransport(robot))
    services.temi.poll_interval = 0.001
    assert services.check_audio()["description"] == "Temi speakers"
    services.play(b"audio", threading.Event(), lambda: None)


@pytest.mark.parametrize("status", [401, 403, 302, 409, 500])
def test_temi_http_errors_are_safe(temi_config, status):
    def handler(request):
        return httpx.Response(status, json={"error": temi_config.api_key}, headers={"Location": "https://example.test"})
    with pytest.raises(PipelineError) as error:
        player(temi_config, handler).check()
    assert temi_config.api_key not in str(error.value)


def test_wrong_player_protocol_is_rejected(temi_config):
    with pytest.raises(PipelineError, match="invalid playback acknowledgement"):
        player(temi_config, lambda _: httpx.Response(200, json={"protocol": "other"})).check()


def test_missing_pairing_token_is_actionable(temi_config):
    temi_config.temi_token_file.unlink()
    with pytest.raises(PipelineError, match="pairing is missing"):
        player(temi_config, Robot()).check()


@pytest.mark.parametrize("values", [{"IRONA_AUDIO_OUTPUT": "auto"}, {"IRONA_TEMI_URL": "http://192.168.68.51:8766"}])
def test_output_must_be_explicit_and_tunneled(config, values):
    with pytest.raises(ConfigError):
        Config.load(config.root, values)
