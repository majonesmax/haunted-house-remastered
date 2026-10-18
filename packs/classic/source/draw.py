"""The classic pack, drawn as text: one character a pixel, "." transparent. Run it to regenerate the PNGs in
cast/ and world/ - edit the art here, never the PNGs.

Colours are from the NES palette (shared/palettes.py), since this is the NES look's own pack.

Usage: python packs/classic/source/draw.py
"""

import os
import sys

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

GHOST_BODY = """
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
GHOST_TAILS = ("""
WWW.WWWWW.WWWWWS
WW...WWW...WWWS.
.W....W.....WS..
""", """
WWWW.WWWWW.WWWWS
.WW...WWW...WWS.
..W....W.....S..
""")

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

TARANTULA_LEGS_OUT = """
..L..........L..
...L..BBBB..L...
L...LBBBBBBL...L
.L..BBBBBBBB..L.
..LLBBRBBRBBLL..
....BBBBBBBB....
..LLBBBBBBBBLL..
.L..BBBBBBBB..L.
L...LBBBBBBL...L
...L..BBBB..L...
..L..........L..
................
"""
TARANTULA_LEGS_IN = """
.L............L.
..L...BBBB...L..
...LLBBBBBBLL...
L...BBBBBBBB...L
.LLLBBRBBRBBLLL.
....BBBBBBBB....
.LLLBBBBBBBBLLL.
L...BBBBBBBB...L
...LLBBBBBBLL...
..L...BBBB...L..
.L............L.
................
"""

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


def cast_pictures():
    pictures = {f"eyes_{look}": eyes(look) for look in PUPIL_AT}
    for frame, tail in enumerate(GHOST_TAILS):
        pictures[f"ghost_{frame}"] = from_ascii(GHOST_BODY + tail.strip("\n"), CAST_COLOURS, strict=True)
    for frame, art in enumerate((BAT_WINGS_UP, BAT_WINGS_DOWN)):
        pictures[f"bat_{frame}"] = from_ascii(art, {**CAST_COLOURS, **BAT_COLOURS}, strict=True)
    for number, (body, legs) in TARANTULA_COLOURS.items():
        colours = {**CAST_COLOURS, "B": body, "L": legs}
        for frame, art in enumerate((TARANTULA_LEGS_OUT, TARANTULA_LEGS_IN)):
            pictures[f"tarantula{number}_{frame}"] = from_ascii(art, colours, strict=True)
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
    os.makedirs(folder, exist_ok=True)
    for name, picture in pictures.items():
        Image.fromarray(picture, "RGBA").save(os.path.join(folder, f"{name}.png"))
    return len(pictures)


def main():
    cast = save_all(cast_pictures(), os.path.join(PACK, "cast"))
    world = save_all(world_pictures(), os.path.join(PACK, "world"))
    print(f"{cast} cast pictures, {world} world pictures")


if __name__ == "__main__":
    main()
