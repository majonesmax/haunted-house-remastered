"""The nocturne pack's cast, in 16-bit colour ramps: each material a run of shades lit from the top left,
digits for the shades ("1" darkest). Same sizes as the classic cast (the looks share a layout): the eyes
14 x 6, monsters 16 x 20 or less, items 16 x 16, stairs 16 x 32.
"""

from collections.abc import Sequence

import numpy as np

from paint import art, ramp, shades
from shared.pixelart import glinting
from shared.types import Picture

Pictures = dict[str, Picture]   # picture name -> the picture, before it's saved as <name>.png

GHOST = shades("012345", [(8, 8, 20)] + ramp((50, 60, 110), (245, 248, 255), 5))
BAT = {**shades("1234", ramp((30, 6, 46), (170, 90, 210), 4)), "E": (255, 120, 40), "F": (250, 250, 240)}
EYES = {"g": (150, 110, 20), "Y": (255, 236, 140), "W": (255, 255, 250), "K": (10, 6, 16)}
TARANTULA_BODIES = {2: ((50, 6, 8), (230, 90, 70)), 3: ((60, 26, 4), (240, 150, 60)),
                    4: ((10, 14, 70), (110, 140, 250))}  # red, orange, blue, as on the 2600

# --- the eyes ----------------------------------------------------------------------------------------------
EYE = """
.gYYg.
gYWWYg
YWWWWY
YWWWWY
gYWWYg
.gYYg.
"""
EYE_SHUT = """
......
......
......
gYYYYg
.gYYg.
......
"""
PUPIL_AT = {"centre": (2, 2), "left": (1, 2), "right": (3, 2), "up": (2, 1), "down": (2, 3)}

# --- by matchlight ------------------------------------------------------------------------------------
HOOD = """
........11..........
......112321........
.....12334431r......
....1234000043rR....
...12300000000043rR.
..1230000000000043rR
..1300000000000004rR
.12300000000000004rR
.1300000000000000rRr
.12300000000000004rR
1223000000000000043r
1222330000000003432r
1222333333333344432r
.111222222222222221.
"""  # a cowl round the eyes, its peak falling back, lit (r, R) on the side the match is held - here, right
HOOD_COLOURS = {**shades("1234", ramp((24, 12, 20), (110, 70, 60), 4)), "0": (6, 4, 8),
                "r": (190, 110, 60), "R": (255, 170, 90)}
MATCH_HAND = ("""
....R.....
...RYR....
..RYWYR...
..YWWWY...
..OYWYO...
...OOO....
....S.....
....S.....
...hSh....
..hHsHh...
..hHHHhs..
..hHHhhs..
..cCCCCc..
..cccccc..
""", """
...R......
...YR.....
..RYWR....
..YWWWY...
..OYWYO...
...OOO....
....S.....
....S.....
...hSh....
..hHsHh...
..hHHHhs..
..hHHhhs..
..cCCCCc..
..cccccc..
""")
MATCH_HAND_COLOURS = {"R": (220, 60, 20), "Y": (255, 210, 60), "W": (255, 255, 230), "O": (240, 130, 30),
                      "S": (150, 100, 50), "s": (90, 60, 30), "h": (220, 160, 120), "H": (250, 205, 165),
                      "c": (40, 22, 30), "C": (110, 70, 60)}   # the sleeve: the hood's cloth

# --- the ghost ----------------------------------------------------------------------------------------
GHOST_FRONT = """
.....455554.....
...4555555554...
..455555555543..
.45555555555543.
.45500555500543.
4555005555005433
4555555555555433
4555555005555433
4555550000555433
4555550000555433
4555555005554433
4555555555554433
4455555555554433
4455555555544332
3445555555444332
3344445554443322
"""
GHOST_FRONT_TAILS = ("""
3344.34444.3432.
334...3443...32.
.3.....33.....2.
................
""", """
33443.34443.332.
.344...344...32.
..3.....3.....2.
................
""")
GHOST_SIDE = """
.....45554......
...455555554....
..45555555554...
.4555555555543..
.4500555555543..
4550055555555433
4555555555555433
4505555555555433
4005555555555433
4555555555555433
4555555555554433
.455555555554433
.445555555544433
..44555555544332
..34455554443322
...3344444333222
"""
GHOST_SIDE_TAILS = ("""
....3344.344432.
.....334..34432.
......33...343..
............3...
""", """
....33443.34432.
.....3344..3432.
.......33...32..
................
""")

# --- the bat ------------------------------------------------------------------------------------------
BAT_WINGS_UP = """
1..............1
21............12
321..........123
2321..1111..1232
2332112332112332
.23323344332332.
..2333E33E3332..
...1123333211...
.....12FF21.....
......1221......
.......11.......
................
"""
BAT_WINGS_DOWN = """
................
................
......1111......
.....123321.....
....12E33E21....
...1123333211...
..122233332221..
.123321FF123321.
1233211221123321
1231...11...1321
121..........121
11............11
"""
BAT_WINGS_LEVEL = """
................
................
................
......1111......
..111123321111..
1122332333322211
1233323E33E33321
.12321333312321.
..11.12FF21.11..
......1221......
.......11.......
................
"""
BAT_FLAP = (BAT_WINGS_UP, BAT_WINGS_LEVEL, BAT_WINGS_DOWN, BAT_WINGS_LEVEL)  # up, level, down, level
BAT_EYES = {
    BAT_WINGS_UP: (6, {"down": "..2333E33E3332..", "up": "..233333333332..",
                       "left": "..23E33E333332.."}),
    BAT_WINGS_LEVEL: (6, {"down": "1233323E33E33321", "up": "1233323333333321",
                          "left": "12333E33E3333321"}),
    BAT_WINGS_DOWN: (4, {"down": "....12E33E21....", "up": "....12333321....", "left": "....1E33E321...."}),
}

# --- the tarantulas -----------------------------------------------------------------------------------
TARANTULA_STEPS = ("""
...l........l...
...Ll......lL...
....L.1221.L....
.l..L13EE31L..l.
.Ll.l133331l.lL.
..LLl134431lLL..
....l113311l....
.LLLl123321lLLL.
L..l12343321l..L
..l1234554321l..
.Ll1235555321lL.
L.l1234554321l.L
..l1233443321l..
...l12333321l...
....ll1221ll....
......llll......
""", """
....l......l....
..l.L......L.l..
...L..1221..L...
..L.L13EE31L.L..
.L..l133331l..L.
L.LLl134431lLL.L
....l113311l....
..LLl123321lLL..
.L.l12343321l.L.
L.l1234554321l.L
..l1235555321l..
.Ll1234554321lL.
L.l1233443321l.L
...l12333321l...
....ll1221ll....
......llll......
""")
TURNS = {"up": 0, "left": 1, "down": 2, "right": 3}

# --- the items ----------------------------------------------------------------------------------------
KEY = """
................
.1221...........
1344321.........
2411432111111111
2411434444444443
1344321112121211
.1221.....11111.
................
"""
SCEPTER = """
..1.............
.132............
.1rR2...........
1rWRR2..........
1RRRR2..........
.2RR2...........
..1342..........
...1342.........
....1342........
.....1342.......
......1342......
.......1342.....
........1342....
.........13422..
..........13342.
...........222..
"""
GOLD = shades("1234", ramp((80, 50, 10), (255, 230, 130), 4))
RUBY = {"r": (120, 10, 30), "R": (220, 40, 60), "W": (255, 220, 230)}
URN = """
.....122221.....
.....134441.....
......1331......
.....123321.....
...11234432111..
..1311234431131.
.131.1245432113.
.131.1245432113.
..1311234431131.
...11G1GGG1G11..
.....1234321....
......12321.....
.......121......
......12321.....
.....1122211....
................
"""
GLINT = (255, 250, 220)   # the point of light a small thing catches
URN_COLOURS = {**shades("12345", ramp((10, 50, 50), (170, 250, 230), 5)), "G": (230, 190, 70)}
URN_PIECE_ROWS = {2: range(0, 5), 3: range(5, 10), 4: range(10, 16)}   # the lip and neck, the body
# with its handles, the foot: each piece a real chunk of vase (cut down its middle, the side pieces were
# just the handles - too small to find)
URN_SHAPE_PIECES = {2: (2,), 3: (3,), 4: (4,), 5: (2, 3), 6: (2, 4), 7: (3, 4), 8: (2, 3, 4)}
STEP = """
1444444444444441
1333333333333331
1111111111111111
1222222222222221
"""
STAIRS_STEPS = 8
WOOD = shades("1234", ramp((30, 16, 8), (210, 150, 90), 4))


# --- building the pictures ----------------------------------------------------------------------------
def eyes(look: str) -> Picture:
    rows = [list(row) for row in EYE.strip("\n").split("\n")]
    column, row = PUPIL_AT[look]
    for down in range(2):
        for across in range(2):
            rows[row + down][column + across] = "K"
    return pair(["".join(cells) for cells in rows])


def pair(rows: Sequence[str]) -> Picture:
    return art("\n".join(row + ".." + row for row in rows), EYES)


def ghost_pictures() -> Pictures:
    back = GHOST_FRONT.replace("0", "5")
    views = {"down": (GHOST_FRONT, GHOST_FRONT_TAILS), "up": (back, GHOST_FRONT_TAILS),
             "left": (GHOST_SIDE, GHOST_SIDE_TAILS)}
    pictures: Pictures = {}
    for facing, (body, tails) in views.items():
        for frame, tail in enumerate(tails):
            pictures[f"ghost_{facing}_{frame}"] = art(body.strip("\n") + "\n" + tail.strip("\n"), GHOST)
    return pictures


def bat_pictures() -> Pictures:
    pictures: Pictures = {}
    for frame, wings in enumerate(BAT_FLAP):
        row, by_facing = BAT_EYES[wings]
        for facing, eyes_row in by_facing.items():
            rows: list[str] = [*wings.strip("\n").split("\n")]   # str rows, so one can be replaced
            rows[row] = eyes_row
            pictures[f"bat_{facing}_{frame}"] = art("\n".join(rows), BAT)
    return pictures


def tarantula_pictures() -> Pictures:
    pictures: Pictures = {}
    for number, (dark, light) in TARANTULA_BODIES.items():
        body = shades("12345", ramp(dark, light, 5))
        legs = {"l": ramp(dark, light, 5)[1], "L": ramp(dark, light, 5)[3], "E": (255, 230, 90)}
        for frame, text in enumerate(TARANTULA_STEPS):
            facing_up = art(text, {**body, **legs})
            for facing, turns in TURNS.items():
                turned = np.ascontiguousarray(np.rot90(facing_up, turns))
                pictures[f"tarantula{number}_{facing}_{frame}"] = turned
    return pictures


def urn_shape(shape: int) -> Picture:
    keep: set[int] = set()
    for piece in URN_SHAPE_PIECES[shape]:
        keep.update(URN_PIECE_ROWS[piece])
    urn_rows = URN.strip("\n").split("\n")
    rows = [row if number in keep else "." * len(row) for number, row in enumerate(urn_rows)]
    return art("\n".join(rows), URN_COLOURS)


def stairs(going_up: bool) -> Picture:
    picture = art("\n".join([STEP.strip("\n")] * STAIRS_STEPS), WOOD)
    if not going_up:  # the steps fade into the dark, going down
        fade = np.linspace(1.0, 0.1, picture.shape[0])[:, None, None]
        picture[..., :3] = (picture[..., :3] * fade).astype(np.uint8)
    return picture


def cast_pictures() -> Pictures:
    pictures = {f"eyes_{look}": eyes(look) for look in PUPIL_AT}
    pictures["eyes_blink"] = pair(EYE_SHUT.strip("\n").split("\n"))
    pictures.update(ghost_pictures())
    pictures.update(bat_pictures())
    pictures.update(tarantula_pictures())
    pictures["hood_right_0"] = art(HOOD, HOOD_COLOURS)   # the look mirrors it when the match is held left
    for frame, text in enumerate(MATCH_HAND):
        pictures[f"match_hand_right_{frame}"] = art(text, MATCH_HAND_COLOURS)
    pictures["key_0"] = art(KEY, GOLD)
    pictures["scepter_0"] = art(SCEPTER, {**GOLD, **RUBY})
    for shape in URN_SHAPE_PIECES:
        for frame, picture in enumerate(glinting(urn_shape(shape), GLINT)):
            pictures[f"urn{shape}_{frame}"] = picture
    pictures["stairs_up_0"] = stairs(going_up=True)
    pictures["stairs_down_0"] = stairs(going_up=False)
    return pictures
