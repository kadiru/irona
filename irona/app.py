import secrets

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .config import Config
from .pipeline import BusyError, Conversation
from .services import Services


def create_app(config=None, services=None):
    config = config or Config.load()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16_384, TRUSTED_HOSTS=["127.0.0.1", "localhost"])
    conversation = Conversation(config, services or Services(config))
    app.extensions["conversation"] = conversation
    token = secrets.token_urlsafe(32)

    @app.before_request
    def protect_commands():
        if request.method == "POST":
            supplied = request.headers.get("X-Irona-Token", "")
            origin = request.headers.get("Origin")
            if not secrets.compare_digest(supplied, token) or (origin and origin != request.host_url.rstrip("/")):
                return jsonify(error="Reload the Irona page before sending commands."), 403
            if not request.is_json:
                return jsonify(error="Send an application/json request."), 415

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.get("/")
    def index():
        return render_template("index.html", token=token)

    @app.get("/api/state")
    def state():
        return jsonify(conversation.snapshot())

    @app.post("/api/turn")
    def turn():
        body = request.get_json()
        if not isinstance(body, dict):
            return jsonify(error="Expected a message object."), 400
        conversation.submit(body.get("message"))
        return jsonify(conversation.snapshot()), 202

    @app.post("/api/stop")
    def stop():
        conversation.stop_audio()
        return jsonify(conversation.snapshot())

    @app.post("/api/reset")
    def reset():
        conversation.reset()
        return jsonify(conversation.snapshot())

    @app.errorhandler(BusyError)
    def busy(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    return app
