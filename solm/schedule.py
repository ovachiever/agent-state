"""Install/remove the launchd job that runs the battery every morning."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from solm.config import LOGS_DIR, REPO_ROOT

LABEL = "com.erik.state-of-llm"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>solm</string>
        <string>daily</string>
    </array>
    <key>WorkingDirectory</key><string>{repo}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>{hour}</integer>
        <key>Minute</key><integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key><string>{logs}/daily.log</string>
    <key>StandardErrorPath</key><string>{logs}/daily.err.log</string>
</dict>
</plist>
"""


def install(hour: int = 5, minute: int = 45) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    # sys.executable inside the venv keeps launchd independent of shell PATH.
    PLIST_PATH.write_text(
        PLIST_TEMPLATE.format(
            label=LABEL, python=sys.executable, repo=REPO_ROOT, logs=LOGS_DIR,
            hour=hour, minute=minute,
        )
    )
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
    print(f"installed: {PLIST_PATH}")
    print(f"battery runs daily at {hour:02d}:{minute:02d}; logs in {LOGS_DIR}")


def remove() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        print(f"removed: {PLIST_PATH}")
    else:
        print("no schedule installed")


def status() -> None:
    out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    line = next((l for l in out.splitlines() if LABEL in l), None)
    if line:
        print(f"loaded: {line.strip()}")
        print(f"plist: {PLIST_PATH}")
        from solm.config import load_config

        until = load_config().auto_until
        if until:
            print(f"kill-switch: auto-runs stop after {until}")
    else:
        print("not installed (run: solm schedule install)")
