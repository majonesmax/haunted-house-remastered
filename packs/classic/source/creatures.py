"""The classic pack's cast, drawn as text: one character a pixel, "." transparent. Colours are NES palette
numbers (shared/palettes.py). Run draw.py to write the PNGs.

Sizes fit the NES look's footprints (1.5 px a floor unit across, 2 down): the eyes 14 x 6, monsters 16 x 20
(or less), items 16 x 16, stairs 16 x 32. Monsters have a picture per facing (the look mirrors left for
right); the tarantulas are drawn facing up and turned for the rest.
"""

from collections.abc import Sequence

import numpy as np

from shared.palettes import NES
from shared.pixelart import from_ascii, glinting
from shared.types import Picture, Rgb

Pictures = dict[str, Picture]   # picture name -> the picture, before it's saved as <name>.png

OUTLINE = 0x0F


def colours(numbers: dict[str, int]) -> dict[str, Rgb | None]:
    return {char: NES[number] for char, number in numbers.items()}


# --- the eyes: the player -------------------------------------------------------------------------------
EYE = """
.YYYY.
YWWWWY
YWWWWY
YWWWWY
YWWWWY
.YYYY.
"""
EYE_SHUT = """
......
......
......
YYYYYY
.YYYY.
......
"""
PUPIL_AT = {"centre": (2, 2), "left": (1, 2), "right": (3, 2), "up": (2, 1), "down": (2, 3)}  # column, row
EYE_GAP = 2
EYE_COLOURS = {"Y": 0x38, "W": 0x30, "K": 0x0F}

# --- by matchlight: a glimpse of the one whose eyes they are ------------------------------------------
# A hood around the eyes (drawn behind them; they sit in the shadowed face), and a hand holding the match
# (drawn holding it up on the right; the look mirrors it for the left). Only shown while a match burns.
HOOD = """
.........CC.........
.......CCrrCC.......
.....CCrrrrrrCC.....
....CrrFFFFFFrrC....
...CrFFFFFFFFFFrC...
..CCFFFFFFFFFFFFCC..
..CFFFFFFFFFFFFFFC..
.CCFFFFFFFFFFFFFFCC.
.CFFFFFFFFFFFFFFFFC.
.CCFFFFFFFFFFFFFFCC.
..CCFFFFFFFFFFFFCC..
...CCCFFFFFFFFCCC...
....CCCCCCCCCCCC....
.....CCCCCCCCCC.....
"""
HOOD_COLOURS = {"C": 0x07, "r": 0x17, "F": 0x0F}
MATCH_HAND = ("""
....Y.....
...YYY....
..YYyYY...
..YyyyY...
..OYyYO...
...OOO....
....S.....
....S.....
....S.....
...hhh....
..hhhhh...
..hhhhhH..
..hhhhhH..
...hhhH...
""", """
...Y......
...YY.....
..YYyY....
..YyyyY...
..OYyYO...
...OOO....
....S.....
....S.....
....S.....
...hhh....
..hhhhh...
..hhhhhH..
..hhhhhH..
...hhhH...
""")
MATCH_HAND_COLOURS = {"Y": 0x28, "y": 0x30, "O": 0x27, "S": 0x17, "h": 0x37, "H": 0x27}

# --- the ghost ------------------------------------------------------------------------------------------
GHOST_FRONT = """
.....OOOOOO.....
...OOWWWWWWOO...
..OWWWWWWWWWWO..
.OWWWWWWWWWWWSO.
.OWWKKWWWWKKWSO.
OWWWKKWWWWKKWWSO
OWWWWWWWWWWWWWSO
OWWWWWWKKWWWWWSO
OWWWWWKKKKWWWWSO
OWWWWWKKKKWWWWSO
OWWWWWWKKWWWWWSO
OWWWWWWWWWWWWWSO
OWWWWWWWWWWWWWSO
OWWWWWWWWWWWWWSO
OWWWWWWWWWWWWSSO
OWWWWWWWWWWWWSSO
"""
GHOST_FRONT_TAILS = ("""
OWWWSOWWWWSOWWSO
OWWSO.OWWSO.OWO.
.OWO...OWO...O..
..O.....O.......
""", """
OWWWWSOWWWWSOWSO
.OWWSO.OWWSO.OO.
..OWO...OWO.....
...O.....O......
""")
GHOST_SIDE = """
.....OOOOO......
...OOWWWWWOO....
..OWWWWWWWWWO...
.OWWWWWWWWWWSO..
.OWKKWWWWWWWWSO.
OWWKKWWWWWWWWSO.
OWWWWWWWWWWWWWSO
OWWKWWWWWWWWWWSO
OWKKWWWWWWWWWWSO
OWWWWWWWWWWWWWSO
OWWWWWWWWWWWWWSO
.OWWWWWWWWWWWWSO
.OWWWWWWWWWWWWSO
..OWWWWWWWWWWWSO
..OWWWWWWWWWWSSO
...OWWWWWWWWWSSO
"""
GHOST_SIDE_TAILS = ("""
....OWWWSOWWWWSO
.....OWWO.OWWSO.
......OO...OWO..
............O...
""", """
....OWWWWSOWWWSO
.....OWWWO.OWO..
......OWO...O...
.......O........
""")
GHOST_COLOURS = {"W": 0x30, "S": 0x31, "K": 0x0F, "O": OUTLINE}

# --- the bat --------------------------------------------------------------------------------------------
BAT_WINGS_UP = """
O..............O
OO............OO
OMO..........OMO
OMMO..OOOO..OMMO
OMMMOOBBBBOOMMMO
.OMMMBBBBBBMMMO.
..OMMBRBBRBMMO..
...OOBBBBBBOO...
.....OBFFBO.....
......OBBO......
.......OO.......
................
"""
BAT_WINGS_DOWN = """
................
................
......OOOO......
.....OBBBBO.....
....OBRBBRBO....
...OOBBBBBBOO...
..OMMBBBBBBMMO..
.OMMMOBFFBOMMMO.
OMMMO.OBBO.OMMMO
OMMO...OO...OMMO
OMO..........OMO
OO............OO
"""
BAT_WINGS_LEVEL = """
................
................
................
......OOOO......
..OOOOBBBBOOOO..
OOMMMBBBBBBMMMOO
OMMMMBRBBRBMMMMO
.OMMOBBBBBBOMMO.
..OO.OBFFBO.OO..
......OBBO......
.......OO.......
................
"""
BAT_FLAP = (BAT_WINGS_UP, BAT_WINGS_LEVEL, BAT_WINGS_DOWN, BAT_WINGS_LEVEL)  # up, level, down, level
BAT_EYES = {  # (wing pose, its eyes row) -> the row, by facing: down shows the eyes, up hides them
    BAT_WINGS_UP: (6, {"down": "..OMMBRBBRBMMO..", "up": "..OMMBBBBBBMMO..", "left": "..OMMRBBRBBMMO.."}),
    BAT_WINGS_LEVEL: (6, {"down": "OMMMMBRBBRBMMMMO", "up": "OMMMMBBBBBBMMMMO", "left": "OMMMMRBBRBBMMMMO"}),
    BAT_WINGS_DOWN: (4, {"down": "....OBRBBRBO....", "up": "....OBBBBBBO....", "left": "....ORBBRBBO...."}),
}
BAT_COLOURS = {"B": 0x14, "M": 0x04, "R": 0x28, "F": 0x30, "O": OUTLINE}

# --- the tarantulas (seen from above, facing up) --------------------------------------------------------
TARANTULA_STEPS = ("""
...O........O...
...LO......OL...
....L.OOOO.L....
.O..LOHEEHOL..O.
.LO.OHHHHHHO.OL.
..LLOHHHHHHOLL..
....OOHHHHOO....
.LLLOAAAAAAOLLL.
L..OAAaAAaAAO..L
..OAAAAAAAAAAO..
.LOAAaAAAAaAAOL.
L.OAAAAAAAAAAO.L
..OAAAAaaAAAAO..
...OAAAAAAAAO...
....OOAAAAOO....
......OOOO......
""", """
....O......O....
..O.L......L.O..
...L..OOOO..L...
..L.LOHEEHOL.L..
.L..OHHHHHHO..L.
L.LLOHHHHHHOLL.L
....OOHHHHOO....
..LLOAAAAAAOLL..
.L.OAAaAAaAAO.L.
L.OAAAAAAAAAAO.L
..OAAaAAAAaAAO..
.LOAAAAAAAAAAOL.
L.OAAAAaaAAAAO.L
...OAAAAAAAAO...
....OOAAAAOO....
......OOOO......
""")
TARANTULA_COLOURS = {  # number -> body, markings and legs: red, orange and blue, as on the 2600
    2: {"H": 0x16, "A": 0x16, "a": 0x26, "L": 0x26},
    3: {"H": 0x17, "A": 0x17, "a": 0x27, "L": 0x27},
    4: {"H": 0x12, "A": 0x12, "a": 0x22, "L": 0x22},
}
TARANTULA_SHARED = {"E": 0x38, "O": OUTLINE}
TURNS = {"up": 0, "left": 1, "down": 2, "right": 3}  # quarter turns anticlockwise from facing up

# --- the items ------------------------------------------------------------------------------------------
KEY = """
................
.OOOO...........
OGGGGO..........
OGOOGOOOOOOOOOO.
OGOOGGGGGGGGGGGO
OGGGGOOOOOGOGOGO
.OOOO.....OOOOO.
................
"""
SCEPTER = """
..O.............
.OGO............
.OrRO...........
OrWRRO..........
ORRRRO..........
.ORRO...........
..OGGO..........
...OGGO.........
....OGGO........
.....OGGO.......
......OGGO......
.......OGGO.....
........OGGO....
.........OGGOO..
..........OGGGO.
...........OOO..
"""
ITEM_COLOURS = {"G": 0x28, "O": 0x07, "r": 0x16, "R": 0x26, "W": 0x30}
URN = """
.....OOOOOO.....
.....OHVVVO.....
......OVVO......
.....OVVVVO.....
...OOOVVVVOOO...
..OVOOVVVVvOOVO.
.OVO.OVHVVvO.OVO
.OVO.OVHVVvO.OVO
..OVOOVVVVvOOVO.
...OOOVVVVvOOO..
.....OVVVVvO....
......OVVvO.....
.......OVO......
......OVVvO.....
.....OOOOOOO....
................
"""
URN_COLOURS = {"V": 0x2C, "v": 0x1C, "H": 0x3C, "O": OUTLINE}
URN_PIECE_ROWS = {2: range(0, 5), 3: range(5, 10), 4: range(10, 16)}   # the lip and neck, the body
# with its handles, the foot: each piece a real chunk of vase (cut down its middle, the side pieces were
# just the handles - too small to find)
URN_SHAPE_PIECES = {2: (2,), 3: (3,), 4: (4,), 5: (2, 3), 6: (2, 4), 7: (3, 4), 8: (2, 3, 4)}

# --- the stairs -----------------------------------------------------------------------------------------
STEP = """
OTTTTTTTTTTTTTTO
OTTTTTTTTTTTTTTO
ORRRRRRRRRRRRRRO
ORRRRRRRRRRRRRRO
"""
STEPS = 8
STAIRS_COLOURS = {"T": 0x27, "R": 0x07, "O": OUTLINE}
STAIRS_DOWN_FADE = [0x27, 0x27, 0x17, 0x17, 0x07, 0x07, 0x0F, 0x0F]  # the treads, darker going down


# --- building the pictures ------------------------------------------------------------------------------
def eyes(look: str) -> Picture:
    """A pair of eyes looking one way."""
    rows = [list(row) for row in EYE.strip("\n").split("\n")]
    column, row = PUPIL_AT[look]
    for down in range(2):
        for across in range(2):
            rows[row + down][column + across] = "K"
    return pair([''.join(cells) for cells in rows])


def pair(eye_rows: Sequence[str]) -> Picture:
    joined = [row + "." * EYE_GAP + row for row in eye_rows]
    return from_ascii("\n".join(joined), colours(EYE_COLOURS), strict=True)


def eyes_pictures() -> Pictures:
    pictures = {f"eyes_{look}": eyes(look) for look in PUPIL_AT}
    pictures["eyes_blink"] = pair(EYE_SHUT.strip("\n").split("\n"))
    return pictures


def ghost_pictures() -> Pictures:
    """Front (walking down the floor), back (up: the front with no face) and side (left)."""
    back = GHOST_FRONT.replace("K", "W")
    views = {"down": (GHOST_FRONT, GHOST_FRONT_TAILS), "up": (back, GHOST_FRONT_TAILS),
             "left": (GHOST_SIDE, GHOST_SIDE_TAILS)}
    pictures: Pictures = {}
    for facing, (body, tails) in views.items():
        for frame, tail in enumerate(tails):
            art = body.strip("\n") + "\n" + tail.strip("\n")
            pictures[f"ghost_{facing}_{frame}"] = from_ascii(art, colours(GHOST_COLOURS), strict=True)
    return pictures


def bat_pictures() -> Pictures:
    pictures: Pictures = {}
    for frame, art in enumerate(BAT_FLAP):
        eyes_row, by_facing = BAT_EYES[art]
        for facing, eyes_art in by_facing.items():
            rows: list[str] = [*art.strip("\n").split("\n")]   # str rows, so one can be replaced
            rows[eyes_row] = eyes_art
            pictures[f"bat_{facing}_{frame}"] = from_ascii("\n".join(rows), colours(BAT_COLOURS), strict=True)
    return pictures


def tarantula_pictures() -> Pictures:
    pictures: Pictures = {}
    for number, body in TARANTULA_COLOURS.items():
        palette = colours({**body, **TARANTULA_SHARED})
        for frame, art in enumerate(TARANTULA_STEPS):
            facing_up = from_ascii(art, palette, strict=True)
            for facing, turns in TURNS.items():
                turned = np.ascontiguousarray(np.rot90(facing_up, turns))
                pictures[f"tarantula{number}_{facing}_{frame}"] = turned
    return pictures


def urn_shape(shape: int) -> Picture:
    """The urn with only the pieces of `shape` drawn."""
    keep: set[int] = set()
    for piece in URN_SHAPE_PIECES[shape]:
        keep.update(URN_PIECE_ROWS[piece])
    rows: list[str] = []
    for number, row in enumerate(URN.strip("\n").split("\n")):
        rows.append(row if number in keep else "." * len(row))
    return from_ascii("\n".join(rows), colours(URN_COLOURS), strict=True)


def stairs(going_up: bool) -> Picture:
    """Eight steps; going down, the treads fade into the dark."""
    step = STEP.strip("\n")
    picture = from_ascii("\n".join([step] * STEPS), colours(STAIRS_COLOURS), strict=True)
    if not going_up:
        tread = np.array(NES[STAIRS_COLOURS["T"]], np.uint8)
        for number, shade in enumerate(STAIRS_DOWN_FADE):
            rows = picture[number * 4:number * 4 + 2]
            is_tread = (rows[..., :3] == tread).all(axis=2)
            rows[is_tread, :3] = NES[shade]
    return picture


def cast_pictures() -> Pictures:
    pictures = {**eyes_pictures(), **ghost_pictures(), **bat_pictures(), **tarantula_pictures()}
    pictures["hood_0"] = from_ascii(HOOD, colours(HOOD_COLOURS), strict=True)
    for frame, art in enumerate(MATCH_HAND):
        pictures[f"match_hand_right_{frame}"] = from_ascii(art, colours(MATCH_HAND_COLOURS), strict=True)
    pictures["key_0"] = from_ascii(KEY, colours(ITEM_COLOURS), strict=True)
    pictures["scepter_0"] = from_ascii(SCEPTER, colours(ITEM_COLOURS), strict=True)
    for shape in URN_SHAPE_PIECES:
        for frame, picture in enumerate(glinting(urn_shape(shape), NES[0x30])):
            pictures[f"urn{shape}_{frame}"] = picture
    pictures["stairs_up_0"] = stairs(going_up=True)
    pictures["stairs_down_0"] = stairs(going_up=False)
    return pictures
