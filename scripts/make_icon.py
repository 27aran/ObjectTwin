"""Generate the application icon (PNG + multi-size ICO) into src/objecttwin/assets.

Two overlapping circles - an object and its twin. Run once; the result is committed.

    uv run python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "objecttwin" / "assets"
SIZE = 256
SS = 4  # supersampling for smooth edges

BACKGROUND = (24, 62, 80, 255)
LEFT = (255, 255, 255, 255)
RIGHT = (94, 211, 198, 215)


def render() -> Image.Image:
    s = SIZE * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=BACKGROUND)

    r = int(s * 0.25)
    cy = s // 2
    left_cx, right_cx = int(s * 0.38), int(s * 0.62)
    ring = int(s * 0.055)
    draw.ellipse((left_cx - r, cy - r, left_cx + r, cy + r), outline=LEFT, width=ring)

    overlay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).ellipse((right_cx - r, cy - r, right_cx + r, cy + r), fill=RIGHT)
    img = Image.alpha_composite(img, overlay)
    return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = render()
    icon.save(ASSETS / "objecttwin.png")
    icon.save(
        ASSETS / "objecttwin.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Icons written to {ASSETS}")


if __name__ == "__main__":
    main()
