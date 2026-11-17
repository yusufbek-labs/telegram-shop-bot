"""One-command start:  python run.py

Creates .venv, installs dependencies, seeds the demo catalog on first run and starts the bot.
Needs Python 3.11+ and a filled-in .env (copy .env.example and paste your BotFather token).
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sh(*args: str) -> None:
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def main() -> int:
    if not (ROOT / ".env").exists():
        print("Missing .env. Run:  copy .env.example .env   (Windows)  or  cp .env.example .env")
        print("Then put your token from @BotFather into BOT_TOKEN and your Telegram id into ADMIN_IDS.")
        return 1
    if not PY.exists():
        print("Creating virtual environment...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    marker = VENV / ".deps-installed"
    req = ROOT / "requirements.txt"
    if not marker.exists() or marker.stat().st_mtime < req.stat().st_mtime:
        print("Installing dependencies...")
        sh(PY, "-m", "pip", "install", "-q", "-r", "requirements.txt")
        marker.touch()
    sh(PY, "-m", "scripts.seed")
    print("Starting the bot. Press Ctrl+C to stop.")
    try:
        return subprocess.run([str(PY), "-m", "app"], cwd=ROOT).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
