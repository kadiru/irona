import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def setup_module(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts" / "temi.py"
    spec = importlib.util.spec_from_file_location("temi_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "irona"
    identity = root / ".runtime" / "android-user"
    identity.mkdir(parents=True)
    (tmp_path / ".android").symlink_to(identity, target_is_directory=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "RUNTIME", root / ".runtime" / "temi")
    monkeypatch.setattr(module.sys, "argv", ["temi.py", "connect", "--device", "192.168.1.51"])
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return module


def fake_adb(calls, valid=True):
    transferred = None

    def run(*args, input=None, timeout=30):
        nonlocal transferred
        calls.append(args)
        if args[0] == "connect":
            return "connected"
        if "get-state" in args:
            return "device"
        if "getprop" in args:
            return {"ro.build.version.release": "6.0.1", "ro.build.version.sdk": "23", "ro.product.model": "rk3288"}[args[-1]]
        if "exec-in" in args:
            assert "dd" in args and "of=files/irona-token" in args
            transferred = input
        if "exec-out" in args:
            return transferred.decode().strip() if valid else "transfer failed"
        return ""

    return run


def test_pairing_uses_legacy_raw_input_and_verifies_it(setup_module, monkeypatch, capsys):
    module = setup_module
    calls = []
    monkeypatch.setattr(module, "adb", fake_adb(calls))
    module.main()
    token = (module.RUNTIME / "token").read_text().strip()
    assert token not in capsys.readouterr().out
    assert all(token not in str(call) for call in calls)
    assert (module.RUNTIME / "token").stat().st_mode & 0o777 == 0o600
    assert (module.RUNTIME / "device.json").is_file()
    assert any("start" in call for call in calls)


def test_failed_pairing_does_not_start_player(setup_module, monkeypatch):
    calls = []
    monkeypatch.setattr(setup_module, "adb", fake_adb(calls, valid=False))
    with pytest.raises(RuntimeError, match="could not be verified"):
        setup_module.main()
    assert not any("start" in call or "forward" in call for call in calls)


def test_setup_refuses_unapproved_identity_directory(setup_module, monkeypatch):
    (Path.home() / ".android").unlink()
    (Path.home() / ".android").mkdir()
    monkeypatch.setattr(setup_module, "adb", lambda *a, **k: pytest.fail("ADB should not start"))
    with pytest.raises(RuntimeError, match="explicitly approved"):
        setup_module.main()
