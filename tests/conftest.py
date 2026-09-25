from pathlib import Path

import pytest

from irona.config import Config


@pytest.fixture
def config(tmp_path):
    prompt = tmp_path / "irona" / "system_prompt.txt"
    prompt.parent.mkdir()
    prompt.write_text("Reply briefly.")
    return Config.load(tmp_path, {"ELEVENLABS_API_KEY": "test-only-secret"})
