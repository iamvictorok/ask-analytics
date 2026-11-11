"""Regenerate the app icons (needs Pillow): python scripts/make_icon.py

Draws the same artwork as assets/icon.svg: a speech bubble with rising bars.
Original artwork; does not use the DHIS2 logo.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
S = 4  # supersample
N = 512 * S


def s(*v):
    return [x * S for x in v]


im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle(s(0, 0, 511, 511), radius=104 * S, fill="#0F6E6E")
d.rounded_rectangle(s(72, 136, 440, 368), radius=40 * S, fill="white")
d.polygon([(152 * S, 360 * S), (152 * S, 432 * S), (244 * S, 360 * S)], fill="white")
d.rounded_rectangle(s(152, 268, 200, 328), radius=10 * S, fill="#F2A541")
d.rounded_rectangle(s(232, 224, 280, 328), radius=10 * S, fill="#0F6E6E")
d.rounded_rectangle(s(312, 180, 360, 328), radius=10 * S, fill="#0F6E6E")

im.resize((512, 512), Image.LANCZOS).save(ROOT / "assets" / "icon-512.png")
im.resize((512, 512), Image.LANCZOS).save(ROOT / "public" / "icon-512.png")
for name, size in [
    ("dhis2-app-icon.png", 48), ("favicon-16x16.png", 16), ("favicon-32x32.png", 32),
    ("favicon-48x48.png", 48), ("android-chrome-192x192.png", 192),
    ("android-chrome-384x384.png", 384), ("apple-touch-icon.png", 180), ("mstile-150x150.png", 150),
]:
    im.resize((size, size), Image.LANCZOS).save(ROOT / "public" / name)
im.resize((64, 64), Image.LANCZOS).save(ROOT / "public" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print("icons written")
