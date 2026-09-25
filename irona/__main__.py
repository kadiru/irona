import logging
import signal
import sys
import threading

from werkzeug.serving import make_server

from .app import create_app
from .config import ConfigError


def main():
    try:
        app = create_app()
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1
    conversation = app.extensions["conversation"]
    config = conversation.config
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    server = make_server(config.host, config.port, app, threaded=True)
    server.timeout = 0.5
    print(f"Irona: http://{config.host}:{config.port}", flush=True)
    output = "Temi speakers via ADB" if config.audio_output == "temi" else f"{config.audio_sink} (Ubuntu development output)"
    print(f"Audio output: {output}", flush=True)
    try:
        while not stop.is_set():
            server.handle_request()
    finally:
        conversation.close()
        server.server_close()
        print("Irona stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
