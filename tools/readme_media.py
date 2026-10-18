"""The README's pictures, made from the preview's scenes (tools/preview.py): docs/media/looks.png (the NES and
SNES looks side by side) and docs/media/endings.png (the ending in both). Only the remaster's own art - the
2600's picture comes from the ROM, so it isn't published.

Usage: python tools/readme_media.py
"""

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import preview  # noqa: E402
from lab import HERE, Lab  # noqa: E402

import looks  # noqa: E402
from game.state import Game  # noqa: E402

MEDIA = os.path.join(HERE, "docs", "media")
SCALE = 2
GAP = 8
PICTURES = {"looks.png": "floor 2", "endings.png": "escaped"}


def side_by_side(game, label):
    """The scene in every look, left to right, SCALE times size."""
    scene = dict(preview.SCENES)[label]
    pictures = []
    for platform in sorted(looks.LOOKS):
        lab = Lab()
        look = looks.make(platform, game.rom)
        pictures.append(preview.draw_scene(look, game, lab, label, scene))
        pictures.append(np.zeros((pictures[-1].shape[0], GAP, 3), np.uint8))
    joined = np.concatenate(pictures[:-1], axis=1)
    return joined.repeat(SCALE, axis=0).repeat(SCALE, axis=1)


def main():
    os.makedirs(MEDIA, exist_ok=True)
    game = Game()
    for name, label in PICTURES.items():
        path = os.path.join(MEDIA, name)
        Image.fromarray(side_by_side(game, label)).save(path)
        print(path)


if __name__ == "__main__":
    main()
