import copy
import threading
from dataclasses import replace

import pytest

from irona.pipeline import BusyError, Conversation
from irona.services import Cancelled, PipelineError


class FakeServices:
    def __init__(self):
        self.requests = []
        self.speeches = []
        self.fail = None
        self.hold_speech = False
        self.speaking = threading.Event()

    def check_audio(self):
        pass

    def reply(self, history, text, cancel):
        self.requests.append(copy.deepcopy(history))
        if self.fail == "llm":
            raise PipelineError("Local inference timed out.")
        return "Hello Kadir."

    def synthesize(self, text, cancel):
        self.speeches.append(text)
        if self.fail == "tts":
            raise PipelineError("ElevenLabs credit limit reached.")
        return b"test-audio"

    def play(self, audio, cancel, on_speaking):
        on_speaking()
        self.speaking.set()
        if self.hold_speech:
            if cancel.wait(2):
                raise Cancelled()
            raise AssertionError("Test did not stop playback")


def finish(conversation):
    conversation.thread.join(timeout=3)
    assert not conversation.thread.is_alive()
    return conversation.snapshot()


def test_repeated_turns_history_is_bounded_and_reset_clears_it(config):
    services = FakeServices()
    conversation = Conversation(replace(config, history_turns=2), services)
    for index in range(4):
        conversation.submit(f"Message {index}")
        state = finish(conversation)
        assert state["phase"] == "idle"
        assert state["messages"][-1]["delivery"] == "spoken"
    assert len(services.requests[-1]) == 4
    assert state["turns"] == 4
    conversation.reset()
    assert conversation.history == []
    assert conversation.snapshot()["messages"] == []


def test_busy_reset_stop_and_next_turn(config):
    services = FakeServices()
    services.hold_speech = True
    conversation = Conversation(config, services)
    conversation.submit("Hi")
    assert services.speaking.wait(2)
    with pytest.raises(BusyError):
        conversation.submit("Overlapping turn")
    with pytest.raises(BusyError):
        conversation.reset()
    conversation.stop_audio()
    state = finish(conversation)
    assert state["messages"][-1]["delivery"] == "stopped"
    assert not state["busy"]
    services.hold_speech = False
    conversation.submit("Continue")
    assert finish(conversation)["turns"] == 1


def test_tts_failure_preserves_reply_and_allows_recovery(config):
    services = FakeServices()
    services.fail = "tts"
    conversation = Conversation(config, services)
    conversation.submit("Hi")
    state = finish(conversation)
    assert state["phase"] == "error"
    assert state["messages"][-1]["text"] == "Hello Kadir."
    assert state["messages"][-1]["delivery"] == "failed"
    services.fail = None
    conversation.submit("Try the next turn")
    assert finish(conversation)["phase"] == "idle"


def test_llm_failure_does_not_commit_failed_history(config):
    services = FakeServices()
    services.fail = "llm"
    conversation = Conversation(config, services)
    conversation.submit("Hi")
    assert finish(conversation)["phase"] == "error"
    assert conversation.history == []
    assert services.speeches == []


def test_missing_key_does_not_start_inference(config):
    services = FakeServices()
    conversation = Conversation(replace(config, api_key=""), services)
    conversation.submit("Hi")
    assert "ELEVENLABS_API_KEY" in finish(conversation)["error"]
    assert services.requests == []


def test_shutdown_stops_audio_and_rejects_new_turns(config):
    services = FakeServices()
    services.hold_speech = True
    conversation = Conversation(config, services)
    conversation.submit("Hello")
    assert services.speaking.wait(2)
    conversation.close()
    assert not conversation.thread.is_alive()
    with pytest.raises(BusyError):
        conversation.submit("Late command")


def test_shutdown_during_inference_never_starts_speech(config):
    services = FakeServices()
    entered = threading.Event()
    def reply(history, text, cancel):
        entered.set()
        assert cancel.wait(2)
        return "A late reply that must not be spoken."
    services.reply = reply
    conversation = Conversation(config, services)
    conversation.submit("Hello")
    assert entered.wait(2)
    conversation.close()
    assert not conversation.thread.is_alive()
    assert services.speeches == []
    assert not conversation.history


def test_unexpected_errors_are_sanitized(config):
    services = FakeServices()
    def reply(*args):
        raise RuntimeError(config.api_key)
    services.reply = reply
    conversation = Conversation(config, services)
    conversation.submit("Hello")
    result = finish(conversation)
    assert result["phase"] == "error"
    assert config.api_key not in result["error"]
