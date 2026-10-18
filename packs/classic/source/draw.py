"""The classic pack, drawn as text: one character a pixel, "." transparent. Run it to regenerate the PNGs in
cast/ and world/ - edit the art here, never the PNGs.

Colours are from the NES palette (shared/palettes.py), since this is the NES look's own pack.

Usage: python packs/classic/source/draw.py
"""

import os
import sys

import numpy as np
from PIL import Image

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(PACK)))
from shared.palettes import NES  # noqa: E402
from shared.pixelart import from_ascii  # noqa: E402

# --- the cast ----------------------------------------------------------------------------------------
EYE = """
.WWW.
WWWWW
WWWWW
.WWW.
"""
PUPIL_AT = {"centre": (1, 1), "left": (0, 1), "right": (3, 1), "up": (1, 0), "down": (1, 2)}
EYE_GAP = 2

# The ghost: seen from the front (walking down the floor), from behind (walking up) and from the side
# (walking left; walking right is the same, mirrored by the look). Two frames each: the tail waves.
GHOST_FRONT = """
.....WWWWWW.....
...WWWWWWWWWS...
..WWWWWWWWWWWS..
.WWWWWWWWWWWWWS.
.WWKKWWWWWKKWWS.
.WWKKWWWWWKKWWS.
WWWWWWWWWWWWWWWS
WWWWWWWKKWWWWWWS
WWWWWWKKKKWWWWWS
WWWWWWWKKWWWWWWS
WWWWWWWWWWWWWWWS
WWWWWWWWWWWWWWWS
WWWWWWWWWWWWWWWS
"""
GHOST_FRONT_TAILS = ("""
WWW.WWWWW.WWWWWS
WW...WWW...WWWS.
.W....W.....WS..
""", """
WWWW.WWWWW.WWWWS
.WW...WWW...WWS.
..W....W.....S..
""")
GHOST_SIDE = """
.....WWWWW......
...WWWWWWWWS....
..WWWWWWWWWWS...
.WWWWWWWWWWWWS..
.WKKWWWWWWWWWS..
.WKKWWWWWWWWWWS.
WWWWWWWWWWWWWWS.
WWKWWWWWWWWWWWWS
WKKWWWWWWWWWWWWS
WWWWWWWWWWWWWWWS
WWWWWWWWWWWWWWWS
.WWWWWWWWWWWWWWS
..WWWWWWWWWWWWWS
"""
GHOST_SIDE_TAILS = ("""
...WWWWW.WWWWWWS
.....WW...WWW.WS
...........W..W.
""", """
...WWWW.WWWWWWWS
......W..WWW.WWS
..........W...W.
""")

# The bat: wings up and wings down. From the front (flying down) its red eyes show; from behind (flying up)
# they don't; flying left, they're to the left (right is the same, mirrored by the look).
BAT_WINGS_UP = """
K..............K
KK............KK
KKK..........KKK
.KKKK..KK..KKKK.
..KKKKKKKKKKKK..
...KKKRKKRKKK...
....KKKKKKKK....
.....KK..KK.....
................
................
"""
BAT_WINGS_DOWN = """
................
................
.....KK..KK.....
....KKKKKKKK....
...KKKRKKRKKK...
..KKKKKKKKKKKK..
.KKKK..KK..KKKK.
KKK..........KKK
KK............KK
K..............K
"""
BAT_EYES_ROW = {BAT_WINGS_UP: 5, BAT_WINGS_DOWN: 4}
BAT_EYES = {"down": "...KKKRKKRKKK...", "up": "...KKKKKKKKKK...", "left": "...KRKKRKKKKK..."}

# A tarantula, seen from above, walking up the floor (its head and red eyes at the top). The look turns it
# for the other directions. Two frames: the legs step.
TARANTULA_STEP_1 = """
.....L....L.....
......L..L......
..L...BRRB...L..
...L..BBBB..L...
L...LBBBBBBL...L
.LL..BBBBBB..LL.
...LLBBBBBBLL...
.....BBBBBB.....
...LLBBBBBBLL...
.LL.BBBBBBBB.LL.
L..LBBBBBBBBL..L
...LBBBBBBBBL...
..L.BBBBBBBB.L..
.L...BBBBBB...L.
......BBBB......
................
"""
TARANTULA_STEP_2 = """
....L......L....
.....L....L.....
...L..BRRB..L...
..L...BBBB...L..
.L..LBBBBBBL..L.
L..L.BBBBBB.L..L
....LBBBBBBL....
.....BBBBBB.....
..LLLBBBBBBLLL..
.L..BBBBBBBB..L.
L...BBBBBBBB...L
..LLBBBBBBBBLL..
.L..BBBBBBBB..L.
L....BBBBBB....L
......BBBB......
................
"""
TARANTULA_EYES = NES[0x38]  # pale yellow: the head shows on any body colour
TURNS = {"up": 0, "left": 1, "down": 2, "right": 3}  # quarter turns anticlockwise from facing up

KEY = """
................
..YYYY..........
.YDDDDY.........
YD....DYYYYYYYYY
YD....DYYYYYYYYD
.YDDDDY.....Y.YD
..YYYY......Y.Y.
................
"""

SCEPTER = """
.RR.............
RWRR............
RRRRG...........
.RRGGG..........
...GGGG.........
....GYG.........
.....Y..........
......Y.........
.......Y........
........Y.......
.........Y......
..........Y.....
...........Y....
............Y...
.............Y..
..............Y.
"""

URN = """
......VVVV......
.......VV.......
......VVVV......
...VVVVVVVVVv...
.VV.VVVVVVVVv.VV
V...VVVVVVVVv..V
V...VVVVVVVVv..V
.VV.VVVVVVVVv.VV
...VVVVVVVVVv...
....VVVVVVVv....
.....VVVVVv.....
......VVVV......
.......VV.......
......VVVV......
.....VVVVVv.....
................
"""
URN_PIECE_COLUMNS = {2: range(0, 5), 3: range(5, 11), 4: range(11, 16)}  # piece -> its columns of URN
URN_SHAPE_PIECES = {2: (2,), 3: (3,), 4: (4,), 5: (2, 3), 6: (2, 4), 7: (3, 4), 8: (2, 3, 4)}

STAIRS_UP = """
............GGGG
............GggG
........GGGGGggG
........GgggggG.
....GGGGGggggG..
....GggggggG....
GGGGGgggggG.....
GggggggggG......
GgggggggG.......
GggggggG........
GgggggG.........
GggggG..........
GgggG...........
GggG............
GgG.............
GG..............
"""
STAIRS_DOWN = """
GGGG............
GggG............
GggGGGGG........
.GgggggG........
..GggggGGGGG....
....GgggggggG...
.....GggggggGGGG
......GgggggggKG
.......GgggggKKG
........GggggKKG
.........GgggKKG
..........GggKKG
...........GgKKG
............GKKG
.............KKG
..............GG
"""

FRONT_DOOR = """
OOOOOOOO
ODDDDDDO
ODDDDDDO
ODdDDdDO
ODdDDdDO
ODdDDdDO
ODDDDDDO
ODDDDDDO
ODDDDDDO
ODDDDDYO
ODDDDDYO
ODDDDDDO
ODDDDDDO
ODdDDdDO
ODdDDdDO
ODdDDdDO
ODDDDDDO
OOOOOOOO
"""

CAST_COLOURS = {
    "W": NES[0x30], "S": NES[0x10], "K": NES[0x0F], "R": NES[0x16], "Y": NES[0x28], "D": NES[0x18],
    "G": NES[0x2D], "g": NES[0x00], "V": NES[0x2C], "v": NES[0x1C],
}
BAT_COLOURS = {"K": NES[0x14], "R": NES[0x26]}
# body and legs: red, orange and blue, as on the 2600; the legs a shade lighter, to show on the dark floor
TARANTULA_COLOURS = {2: (NES[0x16], NES[0x26]), 3: (NES[0x17], NES[0x27]), 4: (NES[0x12], NES[0x21])}
DOOR_COLOURS = {"O": NES[0x17], "D": NES[0x07], "d": NES[0x0F], "Y": NES[0x28]}

# --- the world ---------------------------------------------------------------------------------------
BRICK = """
HHHHHHHM
BBBBBBBM
BBBBBBBM
MMMMMMMM
HHHMHHHH
BBBMBBBB
BBBMBBBB
MMMMMMMM
"""
BOARDS = """
DDDDDDDl
DdDDDDDl
DDDDDDDl
DDDDdDDl
DDDDDDDl
DDDDDDDl
DDdDDDDl
DDDDDDDl
"""
TILE_REPEAT = 3  # 8x8 motifs -> 24x24 tiles: one 16x16-unit cell of the floor in the NES look
WALL_COLOURS = [  # floors 1-4: the original's blue, red-brown, green and ochre walls
    {"H": NES[0x21], "B": NES[0x11], "M": NES[0x01]},
    {"H": NES[0x26], "B": NES[0x16], "M": NES[0x06]},
    {"H": NES[0x2B], "B": NES[0x1B], "M": NES[0x0B]},
    {"H": NES[0x37], "B": NES[0x27], "M": NES[0x17]},
]
FLOOR_COLOURS = {"D": NES[0x17], "d": NES[0x07], "l": NES[0x0F]}


# --- building the pictures ---------------------------------------------------------------------------
def eyes(look):
    """A pair of eyes looking one way: two EYEs with their pupils moved."""
    left = [list(row) for row in EYE.strip("\n").split("\n")]
    column, row = PUPIL_AT[look]
    for down in range(2):
        for across in range(2):
            if 0 <= row + down < len(left):
                left[row + down][column + across] = "K"
    rows = ["".join(cells) + "." * EYE_GAP + "".join(cells) for cells in left]
    return from_ascii("\n".join(rows), CAST_COLOURS, strict=True)


def urn_shape(shape):
    """The urn with only the pieces of `shape` drawn."""
    keep = set()
    for piece in URN_SHAPE_PIECES[shape]:
        keep.update(URN_PIECE_COLUMNS[piece])
    rows = []
    for row in URN.strip("\n").split("\n"):
        rows.append("".join(cell if column in keep else "." for column, cell in enumerate(row)))
    return from_ascii("\n".join(rows), CAST_COLOURS, strict=True)


def tiled(motif, colours):
    rows = motif.strip("\n").split("\n") * TILE_REPEAT
    return from_ascii("\n".join(row * TILE_REPEAT for row in rows), colours, strict=True)


def ghost_pictures():
    """Front (down), back (up: the front with no face) and side (left)."""
    back = GHOST_FRONT.replace("K", "W")
    views = {"down": (GHOST_FRONT, GHOST_FRONT_TAILS), "up": (back, GHOST_FRONT_TAILS),
             "left": (GHOST_SIDE, GHOST_SIDE_TAILS)}
    pictures = {}
    for facing, (body, tails) in views.items():
        for frame, tail in enumerate(tails):
            art = body + tail.strip("\n")
            pictures[f"ghost_{facing}_{frame}"] = from_ascii(art, CAST_COLOURS, strict=True)
    return pictures


def bat_pictures():
    """Each wing pose with the eyes for down (front), up (back) and left."""
    colours = {**CAST_COLOURS, **BAT_COLOURS}
    pictures = {}
    for facing, eyes_row in BAT_EYES.items():
        for frame, art in enumerate((BAT_WINGS_UP, BAT_WINGS_DOWN)):
            rows = art.strip("\n").split("\n")
            rows[BAT_EYES_ROW[art]] = eyes_row
            pictures[f"bat_{facing}_{frame}"] = from_ascii("\n".join(rows), colours, strict=True)
    return pictures


def tarantula_pictures():
    """Each tarantula's colours, both steps, turned to face each way."""
    pictures = {}
    for number, (body, legs) in TARANTULA_COLOURS.items():
        colours = {**CAST_COLOURS, "B": body, "L": legs, "R": TARANTULA_EYES}
        for frame, art in enumerate((TARANTULA_STEP_1, TARANTULA_STEP_2)):
            facing_up = from_ascii(art, colours, strict=True)
            for facing, turns in TURNS.items():
                turned = np.ascontiguousarray(np.rot90(facing_up, turns))
                pictures[f"tarantula{number}_{facing}_{frame}"] = turned
    return pictures


def cast_pictures():
    pictures = {f"eyes_{look}": eyes(look) for look in PUPIL_AT}
    pictures.update(ghost_pictures())
    pictures.update(bat_pictures())
    pictures.update(tarantula_pictures())
    pictures["key_0"] = from_ascii(KEY, CAST_COLOURS, strict=True)
    pictures["scepter_0"] = from_ascii(SCEPTER, CAST_COLOURS, strict=True)
    for shape in URN_SHAPE_PIECES:
        pictures[f"urn{shape}_0"] = urn_shape(shape)
    pictures["stairs_up_0"] = from_ascii(STAIRS_UP, CAST_COLOURS, strict=True)
    pictures["stairs_down_0"] = from_ascii(STAIRS_DOWN, CAST_COLOURS, strict=True)
    return pictures


def world_pictures():
    pictures = {"front_door": from_ascii(FRONT_DOOR, DOOR_COLOURS, strict=True)}
    for floor, colours in enumerate(WALL_COLOURS):
        pictures[f"wall{floor + 1}"] = tiled(BRICK, colours)
        pictures[f"floor{floor + 1}"] = tiled(BOARDS, FLOOR_COLOURS)
    return pictures


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
    cast = save_all(cast_pictures(), os.path.join(PACK, "cast"))
    world = save_all(world_pictures(), os.path.join(PACK, "world"))
    print(f"{cast} cast pictures, {world} world pictures")


if __name__ == "__main__":
    main()
