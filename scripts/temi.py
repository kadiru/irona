"""Explicit setup for one owner-selected Temi. Never scans, roots, or updates it."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "dev.irona.player"
RUNTIME = ROOT / ".runtime" / "temi"


def adb(*args, input=None, timeout=30):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "adb.sh"), *args],
        input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )
    if result.returncode:
        # Arguments and stdin can contain private data; report only ADB's result.
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or result.stdout.decode(errors="replace").strip() or "ADB command failed.")
    return result.stdout.decode(errors="replace").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "install", "connect", "disconnect"])
    parser.add_argument("--device", help="Temi's private IPv4 address; saved privately after connection")
    args = parser.parse_args()
    identity = Path.home() / ".android"
    if identity.resolve() != (ROOT / ".runtime" / "android-user").resolve() or not identity.is_dir():
        raise RuntimeError("ADB needs the explicitly approved ~/.android symlink to .runtime/android-user. Do not replace an existing directory.")
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    saved = RUNTIME / "device.json"
    device = args.device
    if not device and saved.exists():
        device = json.loads(saved.read_text())["address"]
    if not device:
        raise RuntimeError("Provide --device with Temi's IP address from its developer screen.")
    address = ipaddress.ip_address(device)
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast:
        raise RuntimeError("Use Temi's private IPv4 address on the trusted local network.")
    serial = f"{address}:5555"
    if args.action == "disconnect":
        adb("-s", serial, "shell", "am", "force-stop", PACKAGE)
        expected = f"{serial} tcp:8766 tcp:8766"
        if expected in adb("forward", "--list").splitlines():
            adb("-s", serial, "forward", "--remove", "tcp:8766")
        adb("disconnect", serial)
        print("Irona player stopped and its ADB forward removed. Close the ADB port on Temi's developer screen when finished.")
        return
    print(adb("connect", serial))
    if adb("-s", serial, "get-state") != "device":
        raise RuntimeError("Temi is not authorized. Check its developer screen for an authorization prompt.")
    version = adb("-s", serial, "shell", "getprop", "ro.build.version.release")
    api = int(adb("-s", serial, "shell", "getprop", "ro.build.version.sdk"))
    model = adb("-s", serial, "shell", "getprop", "ro.product.model")
    print(f"Connected Android device: {model}; Android {version}; API {api}")
    if args.action == "inspect":
        return
    if api < 23:
        raise RuntimeError("This build requires Android API 23 or newer. No application was installed.")
    if args.action == "install":
        apk = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        if not apk.is_file():
            raise RuntimeError("Build the APK first with bash scripts/build-temi.sh.")
        print(adb("-s", serial, "install", "-r", str(apk), timeout=90))
    token_path = RUNTIME / "token"
    if not token_path.exists():
        with token_path.open("x") as file:
            os.chmod(token_path, 0o600)
            file.write(secrets.token_urlsafe(32) + "\n")
    adb("-s", serial, "shell", "am", "force-stop", PACKAGE)
    adb("-s", serial, "shell", "run-as", PACKAGE, "mkdir", "-p", "files")
    # Copy over the authenticated debug channel into app-private storage, never
    # shared storage, a command argument, or console output.
    token = token_path.read_bytes()
    adb("-s", serial, "exec-in", "run-as", PACKAGE, "dd", "of=files/irona-token", input=token)
    # Legacy ADB exec-in has no remote exit status. Verify privately after EOF.
    for attempt in range(5):
        received = adb("-s", serial, "exec-out", "run-as", PACKAGE, "cat", "files/irona-token")
        if secrets.compare_digest(received, token.decode().strip()):
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Temi pairing token transfer could not be verified.")
    adb("-s", serial, "shell", "run-as", PACKAGE, "chmod", "600", "files/irona-token")
    expected = f"{serial} tcp:8766 tcp:8766"
    if expected not in adb("forward", "--list").splitlines():
        adb("-s", serial, "forward", "--no-rebind", "tcp:8766", "tcp:8766")
    adb("-s", serial, "shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
    with saved.open("w") as file:
        os.chmod(saved, 0o600)
        json.dump({"address": str(address)}, file)
    print("Irona Player started. Audio bridge: Ubuntu 127.0.0.1:8766 -> Temi loopback. Pairing token was not displayed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Temi setup: {error}", file=sys.stderr)
        sys.exit(1)
