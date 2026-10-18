"""The app's icon, made from the nocturne pack's own pictures: the hooded eyes and the lit match, glowing in
the dark, on a rounded square. Drawn at 32 x 32 and scaled up without smoothing, so it's crisp pixel art at
every size.

Usage: python package/make_icon.py
    -> package/icon_preview.png (1024 x 1024; the Windows icon is made from it at build time)
       package/icon.icns (macOS; made with iconutil, so on a Mac)
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shared.pixelart import blit  # noqa: E402

PACKAGE = os.path.join(ROOT, "package")
CAST = os.path.join(ROOT, "packs", "nocturne", "cast")
SIZE = 32
DARK, GLOW = np.array([14, 8, 26]), np.array([150, 90, 40])   # the dark, and the match's warm light
GLOW_REACH = 15                  # pixels from the flame to the edge of its light
CORNER = 5                       # the rounded square's corner radius, in icon pixels
ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def cast(name):
    return np.array(Image.open(os.path.join(CAST, f"{name}.png")).convert("RGBA"))


def icon():
    """The 32 x 32 icon, RGBA."""
    picture = np.zeros((SIZE, SIZE, 4), np.uint8)
    flame_x, flame_y = 24, 12
    rows, columns = np.mgrid[:SIZE, :SIZE]
    light = np.clip(1 - np.hypot(columns - flame_x, rows - flame_y) / GLOW_REACH, 0, 1)[..., None] ** 1.5
    picture[..., :3] = (DARK * (1 - light) + GLOW * light).astype(np.uint8)
    picture[..., 3] = 255
    rgb = picture[..., :3]
    blit(rgb, cast("hood_right_0"), 5, 9)
    blit(rgb, cast("eyes_centre"), 8, 13)
    blit(rgb, cast("match_hand_right_0"), 20, 9)
    picture[..., 3] = rounded_square()
    return picture


def rounded_square():
    """255 inside a square with rounded corners, 0 outside."""
    rows, columns = np.mgrid[:SIZE, :SIZE] + 0.5
    nearest_x = np.clip(columns, CORNER, SIZE - CORNER)
    nearest_y = np.clip(rows, CORNER, SIZE - CORNER)
    inside = np.hypot(columns - nearest_x, rows - nearest_y) <= CORNER
    return np.where(inside, 255, 0).astype(np.uint8)


def scaled(picture, size):
    return Image.fromarray(picture, "RGBA").resize((size, size), Image.NEAREST)


def main():
    picture = icon()
    preview = os.path.join(PACKAGE, "icon_preview.png")
    scaled(picture, 1024).save(preview)
    print(preview)
    if shutil.which("iconutil") is None:
        print("no iconutil (it's macOS's): icon.icns not made")
        return
    with tempfile.TemporaryDirectory() as folder:
        iconset = os.path.join(folder, "icon.iconset")
        os.makedirs(iconset)
        for size in ICNS_SIZES[:-1]:
            scaled(picture, size).save(os.path.join(iconset, f"icon_{size}x{size}.png"))
            scaled(picture, size * 2).save(os.path.join(iconset, f"icon_{size}x{size}@2x.png"))
        icns = os.path.join(PACKAGE, "icon.icns")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
        print(icns)


if __name__ == "__main__":
    main()
