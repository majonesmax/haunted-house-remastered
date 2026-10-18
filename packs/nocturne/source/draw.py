"""Write the nocturne pack's PNGs from its text art: the cast (creatures.py) into cast/, the world (manor.py)
into world/. Edit the art there, never the PNGs.

Usage: python packs/nocturne/source/draw.py
"""

import os
import sys

from PIL import Image

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(PACK)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import creatures  # noqa: E402
import manor  # noqa: E402


def save_all(pictures, folder):
    """Write the pictures as PNGs, after clearing out the old ones (so a renamed picture leaves no copy)."""
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.endswith(".png"):
            os.remove(os.path.join(folder, old))
    for name, picture in pictures.items():
        Image.fromarray(picture, "RGBA").save(os.path.join(folder, f"{name}.png"))
    return len(pictures)


def main():
    cast = save_all(creatures.cast_pictures(), os.path.join(PACK, "cast"))
    world = save_all(manor.world_pictures(), os.path.join(PACK, "world"))
    print(f"{cast} cast pictures, {world} world pictures")


if __name__ == "__main__":
    main()
