import copy
import threading
import time
import uuid

from .services import Cancelled, PipelineError


class BusyError(Exception):
    pass


class Conversation:
    def __init__(self, config, services):
        self.config = config
        self.services = services
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.closed = False
        self.busy = False
        self.phase = "idle"
        self.messages = []
        self.history = []
        self.error = None
        self.timings = {}
        self.turns = 0
        self.revision = 0

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({
                "phase": self.phase, "busy": self.busy, "messages": self.messages,
                "error": self.error, "timings": self.timings, "turns": self.turns,
                "revision": self.revision,
                "config": {
                    "model": self.config.llm_model,
                    "voice": "Elise" if self.config.voice_id == "EST9Ui6982FZPSi7gCHi" else self.config.voice_id,
                    "tts_model": self.config.tts_model,
                    "audio_sink": self.config.audio_sink,
                    "audio_output": self.config.audio_output,
                    "key_ready": bool(self.config.api_key),
                },
            })

    def submit(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Enter a message of 1 to 2000 characters.")
        with self.lock:
            if self.closed:
                raise BusyError("Irona is shutting down.")
            if self.busy:
                raise BusyError("A turn is already active. Wait for it to finish or stop its audio.")
            text = text.strip()
            self.busy = True
            self.phase = "generating"
            self.error = None
            self.timings = {}
            self.cancel = threading.Event()
            self.messages.append({"id": uuid.uuid4().hex, "role": "user", "text": text, "delivery": "sent"})
            self.messages = self.messages[-39:]
            self.revision += 1
            self.thread = threading.Thread(target=self._run, args=(text, self.cancel), daemon=True, name="irona-turn")
            self.thread.start()

    def _phase(self, phase):
        with self.lock:
            self.phase = phase
            self.revision += 1

    def _run(self, text, cancel):
        assistant = None
        started = time.monotonic()
        try:
            if not self.config.api_key:
                raise PipelineError("Set ELEVENLABS_API_KEY in Ubuntu's private .env and restart Irona.")
            self.services.check_audio()
            if cancel.is_set():
                raise Cancelled()
            reply = self.services.reply(copy.deepcopy(self.history), text, cancel)
            if cancel.is_set():
                raise Cancelled()
            with self.lock:
                self.timings["generation"] = round(time.monotonic() - started, 2)
                self.history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
                self.history = self.history[-self.config.history_turns * 2:]
                assistant = {"id": uuid.uuid4().hex, "role": "assistant", "text": reply, "delivery": "pending"}
                self.messages.append(assistant)
                self.revision += 1
            self._phase("synthesizing")
            mark = time.monotonic()
            audio = self.services.synthesize(reply, cancel)
            with self.lock:
                self.timings["synthesis"] = round(time.monotonic() - mark, 2)
            if cancel.is_set():
                raise Cancelled()

            def speaking():
                with self.lock:
                    assistant["delivery"] = "speaking"
                    self._phase("speaking")

            self.services.play(audio, cancel, speaking)
            with self.lock:
                assistant["delivery"] = "spoken"
                self.turns += 1
                self.phase = "idle"
        except Cancelled:
            with self.lock:
                if assistant:
                    assistant["delivery"] = "stopped"
                self.phase = "idle"
        except Exception as error:
            with self.lock:
                if assistant:
                    assistant["delivery"] = "failed"
                self.error = str(error) if isinstance(error, PipelineError) else "The turn failed unexpectedly. Check configuration and restart Irona if it repeats."
                self.phase = "error"
        finally:
            with self.lock:
                self.timings["total"] = round(time.monotonic() - started, 2)
                self.busy = False
                self.revision += 1

    def stop_audio(self):
        with self.lock:
            if self.busy and self.phase in ("speaking", "stopping"):
                self.cancel.set()
                self._phase("stopping")
                return
            raise BusyError("No audio is currently playing.")

    def reset(self):
        with self.lock:
            if self.busy:
                raise BusyError("Wait for the active turn to finish before resetting.")
            self.history = []
            self.messages = []
            self.error = None
            self.timings = {}
            self.phase = "idle"
            self.turns = 0
            self.revision += 1

    def close(self):
        with self.lock:
            self.closed = True
            self.cancel.set()
            thread = self.thread
        if thread:
            thread.join(timeout=6)
