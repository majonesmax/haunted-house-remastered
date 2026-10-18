"""Check where the game draws things on its 160x228 picture, given their RAM positions.

The rules being checked (all in game coordinates: x across, y up the floor):

    kernel line L of a point at y:   L = y - player y + $CB        (the view shows lines 79 down to 1)
    walls and the eyes, top of L:    scanline 15 + 2 * (79 - L)    (two scanlines per line)
    item and monster sprites:        scanline 16 + 2 * (79 - L)    (one scanline lower)
    x, for everything:               pixel column = x

Stella blends each picture with half of the one before (see tools/lab.py), so the key is found by its green
and blue channels, which that blending leaves alone. The walls drawn are the collision map (game/rom.py
wall_at) exactly, except for a 4-pixel edge strip at each side of the middle row (x 0-3 and 156-159, out of
the player's reach).

Usage: python tools/verify_screen.py      (exit code 1 if a rule fails)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, SELECT, Lab  # noqa: E402
from rom_sheet import colour_number, ntsc_palette, rgb_for  # noqa: E402

sys.path.insert(0, HERE)
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402

TOP_LINE = 79
WALL_FIRST_SCANLINE, SPRITE_FIRST_SCANLINE = 15, 16
VIEW_LAST_SCANLINE = 171       # below this the view is cut off before the status line
EDGE_STRIP = 4                 # pixels at each side drawn as wall in the middle row
MIDDLE_ROW = 8

rom = R.load()
palette = ntsc_palette()
failures = []


def check(claim, passed, detail=""):
    print(f"{'PASS' if passed else 'FAIL'}  {claim}" + (f"   [{detail}]" if detail else ""))
    if not passed:
        failures.append(claim)


def line_of(lab, y):
    return y - lab.peek(M.POS_Y) + lab.peek(0xCB)


def wall_scanline(line):
    return WALL_FIRST_SCANLINE + 2 * (TOP_LINE - line)


def sprite_scanline(line):
    return SPRITE_FIRST_SCANLINE + 2 * (TOP_LINE - line)


def park_monsters(lab):
    for monster in range(5):
        lab.poke(M.MONSTER_FLOOR + monster, (lab.peek(M.FLOOR) + 2) & 3)


def choose_game(lab, game):
    while lab.peek(M.GAME_NUMBER) != game:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(3)
    return lab.save()


# --- walls -------------------------------------------------------------------------------------------
def predicted_wall(lab, row, column):
    line = TOP_LINE - (row - WALL_FIRST_SCANLINE) // 2
    y = line - lab.peek(0xCB) + lab.peek(M.POS_Y)
    if not 0 <= y < 256:
        return False
    at_edge = column < EDGE_STRIP or column >= 160 - EDGE_STRIP
    if at_edge and y >> 4 == MIDDLE_ROW:
        return True
    return R.wall_at(rom, column, y)


def check_walls(lab, start):
    wall_rgb = np.array(rgb_for(palette, colour_number(rom, 8)))
    for player_y in (0x10, 0x40, 0x86, 0xB8, 0xF0):
        lab.load(start)
        park_monsters(lab)
        lab.poke(M.POS_Y, player_y)
        lab.run(2)
        drawn = (lab.picture() == wall_rgb).all(axis=2)
        wrong = 0
        for row in range(WALL_FIRST_SCANLINE, VIEW_LAST_SCANLINE + 1):
            for column in range(160):
                wrong += predicted_wall(lab, row, column) != drawn[row, column]
        check(f"walls with the player at y ${player_y:02X}: every pixel where the collision map says",
              wrong == 0, f"{wrong} pixels differ")


# --- the eyes ----------------------------------------------------------------------------------------
def check_eyes(lab, start):
    for player_x, player_y in ((0x80, 0x86), (0x61, 0x70), (0x74, 0x10), (0x74, 0xF0)):
        lab.load(start)
        park_monsters(lab)
        lab.poke(M.POS_X, player_x)
        lab.poke(M.POS_Y, player_y)
        lab.run(2)
        picture = lab.picture()[:VIEW_LAST_SCANLINE].astype(int)
        white = np.argwhere(picture.min(axis=2) > 180)
        top, left = white.min(axis=0)
        eyes_top_line = lab.peek(0xCB) + 2   # the eyes are 3 lines tall, from line $CB up
        expected = (wall_scanline(eyes_top_line), player_x)
        check(f"eyes at x ${player_x:02X}, y ${player_y:02X}: top-left pixel (row, column)",
              (top, left) == expected, f"drawn {(int(top), int(left))}, rule {expected}")


# --- sprites -----------------------------------------------------------------------------------------
def check_sprites(lab):
    """The master key (game 3: green, shown only by a lit match) at offsets that stay clear of the eyes."""
    start = choose_game(lab, 2)
    key_rgb = np.array(rgb_for(palette, colour_number(rom, R.table(rom, "ITEM_COLOURS")[0])))
    rows = R.sprite_rows(rom, R.item_sprite_address(0), 8)
    first_lit_row = next(index for index, row in enumerate(rows) if "#" in row)
    for dx, dy in ((-12, 3), (-14, 5), (-12, -6), (10, 4), (12, -5)):
        lab.load(start)
        park_monsters(lab)
        x, y = lab.peek(M.POS_X) + dx, lab.peek(M.POS_Y) + dy
        lab.poke(M.ITEM_FLOOR, lab.peek(M.FLOOR))
        lab.poke(M.ITEM_X, x)
        lab.poke(M.ITEM_Y, y)
        lab.hold(BUTTON, frames=2)
        found = None
        for _ in range(4):
            lab.run(1)
            picture = lab.picture()[:VIEW_LAST_SCANLINE]
            hits = np.argwhere((picture[:, :, 1:] == key_rgb[1:]).all(axis=2))
            if len(hits):
                found = (int(hits[:, 0].min()), int(hits[:, 1].min()))
                break
        top_line = line_of(lab, y) + len(rows) - 1      # a sprite's first byte is its bottom row
        expected = (sprite_scanline(top_line) + 2 * first_lit_row, x)
        check(f"key sprite at ({x}, {y}): top-left lit pixel (row, column)", found == expected,
              f"drawn {found}, rule {expected}")


def main():
    lab = Lab()
    start = choose_game(lab, 0)
    check_walls(lab, start)
    check_eyes(lab, start)
    check_sprites(lab)
    print(f"\n{'all rules hold' if not failures else f'{len(failures)} failed'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
