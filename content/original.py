"""The original 2600 graphics, as a cast and a world - the fallback for anything a pack doesn't draw.

Read from the user's ROM (game/rom.py), in the original's colours. Same names as a pack's pictures
(docs: content/__init__.py), so a look never needs to know where a picture came from.
"""

import numpy as np

from game import palette as P
from game import rom as R
from shared.types import Picture, Rgb

NamedFrames = dict[str, list[Picture]]   # picture name -> its frames

EYES_WHITES, EYES_PUPILS = 0xE7, {"centre": 0xA5, "right": 0xC6, "left": 0x63}  # constants in the code
EYES_PUPIL_ROW = {"up": 2, "down": 0}  # the row (of 3, bottom first) the pupils are on; others: the middle
WHITE = (236, 236, 236)
STAIRS_COLOUR = (160, 160, 160)
URN_COLOUR_INDEX = 6     # urn pieces: palette entry 6 (they shimmer in the original)
MONSTER_FRAMES = {"ghost": 0, "bat": 1, "tarantula2": 2, "tarantula3": 3, "tarantula4": 4}


def sprite(rows: list[str], colour: Rgb) -> Picture:
    """Rows of "#"/"." (top first) -> an RGBA array in one colour."""
    picture = np.zeros((len(rows), len(rows[0]), 4), np.uint8)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == "#":
                picture[y, x] = (*colour, 255)
    return picture


def colour_of(rom: bytes, palette: dict[int, Rgb], index: int) -> Rgb:
    return P.rgb(palette, R.table(rom, "COLOURS")[index])


def eyes(look: str) -> Picture:
    pupils = EYES_PUPILS.get(look, EYES_PUPILS["centre"])
    pupil_row = EYES_PUPIL_ROW.get(look, 1)
    data = [EYES_WHITES] * 3
    data[pupil_row] = pupils
    rows = ["".join("#" if byte & 0x80 >> bit else "." for bit in range(8)) for byte in reversed(data)]
    return sprite(rows, WHITE)


def cast(rom: bytes) -> NamedFrames:
    palette = P.load()
    pictures = {f"eyes_{look}": [eyes(look)] for look in ("centre", "left", "right", "up", "down")}
    item_colours = R.table(rom, "ITEM_COLOURS")
    pictures["key"] = [sprite(R.sprite_rows(rom, R.item_sprite_address(0), 8),
                              colour_of(rom, palette, item_colours[0]))]
    pictures["scepter"] = [sprite(R.sprite_rows(rom, R.item_sprite_address(1), 8),
                                  colour_of(rom, palette, item_colours[1]))]
    urn_colour = colour_of(rom, palette, URN_COLOUR_INDEX)
    for shape in range(2, 9):
        pictures[f"urn{shape}"] = [sprite(R.sprite_rows(rom, R.item_sprite_address(shape), 8), urn_colour)]
    for name, number in MONSTER_FRAMES.items():
        colour = colour_of(rom, palette, number + 1)
        frames = R.monster_sprite_addresses(rom, number)
        pictures[name] = [sprite(R.sprite_rows(rom, address, 10), colour) for address in frames]
    pictures["stairs_up"] = [sprite(R.sprite_rows(rom, 0xFE8C, 17), STAIRS_COLOUR)]
    pictures["stairs_down"] = [sprite(R.sprite_rows(rom, 0xFE8C + 17, 17), STAIRS_COLOUR)]
    return pictures


def world(rom: bytes) -> NamedFrames:
    """Solid walls in each floor's 2600 colour on a black floor - the original's look."""
    palette = P.load()
    pictures: NamedFrames = {}
    for floor in range(R.FLOOR_COUNT):
        wall = np.zeros((16, 16, 4), np.uint8)
        wall[:] = (*colour_of(rom, palette, 8 + floor), 255)
        floor_tile = np.zeros((16, 16, 4), np.uint8)
        floor_tile[..., 3] = 255
        pictures[f"wall{floor + 1}"] = [wall]
        pictures[f"floor{floor + 1}"] = [floor_tile]
    return pictures
