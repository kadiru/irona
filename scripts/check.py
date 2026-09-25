"""Explicit manual integration checks. The tts mode uses ElevenLabs credits."""
import argparse
import io
import math
import struct
import sys
import wave
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from irona.config import Config, ConfigError
from irona.services import PipelineError, Services


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["audio", "tone", "tts", "llm"])
    args = parser.parse_args()
    services = Services(Config.load())
    cancel = Event()
    if args.mode == "audio":
        sink = services.check_audio()
        print("Configured output:", sink["description"])
        return
    if args.mode == "tone":
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(24000)
            samples = [int(4500 * math.sin(2 * math.pi * 523.25 * i / 24000) * min(1, i / 480, (24000 - i) / 480)) for i in range(24000)]
            sound.writeframes(struct.pack("<24000h", *samples))
        services.play(buffer.getvalue(), cancel, lambda: print("Playing a one-second test tone on the configured output.", flush=True))
        print("Playback acknowledged. Confirm audibility in the room.")
    elif args.mode == "tts":
        services.check_audio()
        destination = "Temi robot" if services.config.audio_output == "temi" else "Ubuntu desktop"
        text = f"Hello Kadir. I'm Irona. This is Elise speaking through your {destination}."
        print("Synthesizing one fixed test sentence with ElevenLabs...", flush=True)
        audio = services.synthesize(text, cancel)
        services.play(audio, cancel, lambda: print(f"Speaking through your {destination}...", flush=True))
        print("Playback completed. Confirm audibility in the room.")
    else:
        print(services.reply([], "Introduce yourself in one short sentence.", cancel))


if __name__ == "__main__":
    try:
        main()
    except (ConfigError, PipelineError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
