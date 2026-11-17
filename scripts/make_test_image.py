"""Run the test suite and render the REAL pytest output as docs/test-results.png.

Usage: python -m scripts.make_test_image      (needs pillow: pip install -r requirements-dev.txt)
Nothing is typed in by hand: both blocks are captured from actual pytest runs.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path("C:/Windows/Fonts")
BG, BAR, FG, DIM, GREEN, RED = "#1e1e2e", "#2b2b3d", "#cdd6f4", "#7f849c", "#a6e3a1", "#f38ba8"


def run(*args: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--color=no", "-p", "no:cacheprovider", *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    return proc.stdout.strip()


def wrap(line: str, width: int) -> list[str]:
    return [line[i:i + width] for i in range(0, len(line), width)] or [""]


def main() -> None:
    blocks = [
        ("python -m pytest -q", run("-q")),
        ("python -m pytest --collect-only -qq", run("--collect-only", "-qq")),
    ]
    mono = ImageFont.truetype(str(FONTS / "consola.ttf"), 17)
    mono_b = ImageFont.truetype(str(FONTS / "consolab.ttf"), 17)
    title_font = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), 16)
    char_w = mono.getlength("M")
    width_px, pad, line_h = 1100, 28, 25
    cols = int((width_px - 2 * pad) // char_w)

    rows: list[tuple[str, str, bool]] = []  # text, color, bold
    for cmd, out in blocks:
        rows.append((f"$ {cmd}", DIM, False))
        for raw in out.splitlines():
            for part in wrap(raw, cols):
                if " passed" in raw and " in " in raw:
                    color = RED if "failed" in raw or "error" in raw else GREEN
                    rows.append((part, color, True))
                elif "F" in raw and set(raw.strip()) <= set(".FEsx% 0123456789[]"):
                    rows.append((part, RED, False))
                else:
                    rows.append((part, FG, False))
        rows.append(("", FG, False))

    bar_h = 44
    height = bar_h + pad + len(rows) * line_h + pad
    img = Image.new("RGB", (width_px, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width_px, bar_h], fill=BAR)
    for i, c in enumerate(("#f38ba8", "#f9e2af", "#a6e3a1")):
        d.ellipse([pad + i * 24, 15, pad + i * 24 + 14, 29], fill=c)
    d.text((width_px / 2, bar_h / 2), "telegram-shop-bot  -  pytest", font=title_font, fill=FG, anchor="mm")
    y = bar_h + pad
    for text, color, bold in rows:
        d.text((pad, y), text, font=mono_b if bold else mono, fill=color)
        y += line_h
    out_path = ROOT / "docs" / "test-results.png"
    out_path.parent.mkdir(exist_ok=True)
    img.save(out_path)
    print(f"wrote {out_path} ({img.size[0]}x{img.size[1]})")
    print(blocks[0][1].splitlines()[-1])


if __name__ == "__main__":
    main()
