import json
import re
import time
import uuid

import httpx

from .errors import Cancelled, PipelineError


class TemiPlayback:
    """One acknowledged playback over an explicitly configured ADB forward."""

    poll_interval = 0.2

    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport

    def client(self):
        try:
            token = self.config.temi_token_file.read_text().strip()
        except (OSError, AttributeError):
            raise PipelineError("Temi pairing is missing. Install and connect the Irona player with scripts/temi.py.") from None
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            raise PipelineError("Temi pairing token is invalid. Run the Irona player setup again.")
        return httpx.Client(
            base_url=self.config.temi_url, headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(2, connect=2, write=5, pool=2),
            trust_env=False, follow_redirects=False, transport=self.transport,
        )

    @staticmethod
    def request(client, method, path, playback_id=None, **kwargs):
        try:
            with client.stream(method, path, **kwargs) as response:
                if response.status_code in (401, 403):
                    raise PipelineError("Temi pairing was rejected. Reinstall the private pairing token with scripts/temi.py.")
                if response.status_code == 409:
                    raise PipelineError("The Temi player is busy. Stop its current audio before trying again.")
                if response.status_code != 200:
                    raise PipelineError(f"Temi returned HTTP {response.status_code}. Reconnect the Irona player.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 16_384:
                        raise ValueError()
                data = json.loads(body)
            if data["protocol"] != "irona-temi/1" or data["state"] not in {"idle", "preparing", "playing", "completed", "stopped", "error"}:
                raise ValueError()
            if not re.fullmatch(r"[a-f0-9]{32}", data["session"]):
                raise ValueError()
            if not isinstance(data["started"], bool) or (playback_id is not None and data["id"] != playback_id):
                raise ValueError()
            return data
        except (httpx.RequestError, OSError):
            raise PipelineError("Temi connection failed. Check its Wi-Fi, ADB port, forwarding, and foreground Irona player. The player stops if heartbeats are lost.") from None
        except (ValueError, KeyError, TypeError):
            raise PipelineError("Temi returned an invalid playback acknowledgement. Check the player version and ADB forward.") from None

    def check(self):
        with self.client() as client:
            data = self.request(client, "GET", "/health")
        if data["state"] in {"preparing", "playing"}:
            raise PipelineError("The Temi player is already playing audio. Stop it before starting a new turn.")
        return {"description": "Temi speakers", **data}

    def stop(self, client, playback_id):
        result = self.request(client, "POST", f"/stop/{playback_id}", playback_id)
        if result["state"] not in {"completed", "stopped", "error"}:
            raise PipelineError("Temi did not confirm that playback stopped. Check the robot before continuing.")

    def play(self, audio, cancel, on_speaking):
        if cancel.is_set():
            raise Cancelled()
        if not audio or len(audio) > 8_000_000:
            raise PipelineError("Temi audio must be nonempty and smaller than eight megabytes.")
        playback_id = uuid.uuid4().hex
        needs_stop = False
        notified = False
        with self.client() as client:
            health = self.request(client, "GET", "/health")
            try:
                needs_stop = True
                state = self.request(
                    client, "POST", f"/play/{playback_id}", playback_id,
                    content=audio, params={"volume": self.config.volume / 100},
                    headers={"Content-Type": "application/octet-stream"},
                )
                deadline = time.monotonic() + self.config.playback_timeout
                while True:
                    if state["session"] != health["session"]:
                        raise PipelineError("The Temi player restarted during playback. Reconnect and try a new turn.")
                    if cancel.is_set():
                        needs_stop = False
                        self.stop(client, playback_id)
                        raise Cancelled()
                    if state["started"] and not notified:
                        notified = True
                        on_speaking()
                    if state["state"] == "completed":
                        if not state["started"]:
                            raise PipelineError("Temi reported completion without starting playback.")
                        needs_stop = False
                        return
                    if state["state"] == "stopped":
                        needs_stop = False
                        raise Cancelled()
                    if state["state"] == "error":
                        needs_stop = False
                        hints = {
                            "audio_focus": "Another app took audio focus. Close the other audio app and retry.",
                            "lease_expired": "The connection was interrupted and Temi stopped its audio.",
                            "decode": "Android could not decode or prepare the audio.",
                        }
                        raise PipelineError("Temi playback failed. " + hints.get(state.get("error"), "Check the foreground player on the robot."))
                    if time.monotonic() > deadline:
                        needs_stop = False
                        self.stop(client, playback_id)
                        raise PipelineError("Temi playback timed out and was stopped. Shorten the reply or check the robot.")
                    cancel.wait(self.poll_interval)
                    state = self.request(client, "GET", f"/status/{playback_id}", playback_id)
            finally:
                if needs_stop:
                    try:
                        self.stop(client, playback_id)
                    except PipelineError:
                        pass
