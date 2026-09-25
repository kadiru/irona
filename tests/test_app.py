import re

from irona.app import create_app
from test_pipeline import FakeServices, finish


def setup(config):
    app = create_app(config, FakeServices())
    client = app.test_client()
    page = client.get("/")
    token = re.search(rb'name="irona-token" content="([^"]+)"', page.data)[1].decode()
    return app, client, {"X-Irona-Token": token}


def test_requests_require_same_origin_token(config):
    app, client, headers = setup(config)
    assert client.post("/api/turn", json={"message": "Hi"}).status_code == 403
    assert client.post("/api/turn", json={"message": "Hi"}, headers={**headers, "Origin": "https://other.test"}).status_code == 403
    assert client.get("/api/state", headers={"Host": "other.test"}).status_code == 400


def test_request_validation_and_no_secret_exposure(config):
    app, client, headers = setup(config)
    for message in ("", " " * 4, 42, "x" * 2001):
        assert client.post("/api/turn", json={"message": message}, headers=headers).status_code == 400
    assert client.post("/api/turn", json=[], headers=headers).status_code == 400
    assert client.post("/api/turn", data="plain text", headers=headers).status_code == 415
    assert client.post("/api/turn", json={"message": "x" * 20000}, headers=headers).status_code == 413
    response = client.get("/api/state")
    assert config.api_key.encode() not in response.data
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_web_turn_and_reset(config):
    app, client, headers = setup(config)
    assert client.post("/api/turn", json={"message": "Hello"}, headers=headers).status_code == 202
    finish(app.extensions["conversation"])
    assert client.get("/api/state").json["turns"] == 1
    assert client.post("/api/reset", json={}, headers=headers).json["messages"] == []
