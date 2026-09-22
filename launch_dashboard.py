"""One-click Windows launcher for the agent and its browser dashboard."""

import ctypes
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent


def dashboard_url() -> str:
    with open(ROOT / "config.yaml", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    port = config.get("dashboard", {}).get("port", 5001)
    return f"http://localhost:{port}"


def dashboard_is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/auth/status", timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def start_agent() -> None:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(executable), str(ROOT / "run.py")],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        close_fds=True,
    )


def show_error(message: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, message, "AI Email Agent", 0x10)
    else:
        print(message, file=sys.stderr)


def main() -> int:
    url = dashboard_url()
    if not dashboard_is_ready(url):
        start_agent()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if dashboard_is_ready(url):
                break
            time.sleep(0.5)
        else:
            show_error("The AI Email Agent could not start. Please check the project setup and try again.")
            return 1

    webbrowser.open(url, new=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
