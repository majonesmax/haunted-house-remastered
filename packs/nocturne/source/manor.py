"""The nocturne pack's world: the same Victorian manor as the classic pack, drawn for 16 bits - colour ramps
of 4-6 shades, and shading worked out on top of small text motifs (paint.py): wallpaper darkening toward the
ceiling, bevelled panels and stone blocks, veined marble, grained wood.

    1  The Foyer          blue damask, a gilded rail, a wood wainscot; veined black and white marble
    2  The Dining Hall    burgundy stripes with gold pinstripes; herringbone parquet
    3  The Conservatory   a trellis grown with ivy over stone; terracotta tiles
    4  The Attic          bare planks; rough, knotted boards
"""

from typing import Any

import numpy as np

from paint import art, bevel, brightness, ramp, repeat, shades, solid, speckle
from shared.types import Picture, Rgb

Pictures = dict[str, Picture]   # picture name -> the picture, before it's saved as <name>.png
ArtData = dict[str, Any]        # a floor's or a decoration's description, as written in FLOORS below

CELL_W, CELL_H, FACE_H = 24, 32, 20
PAPER_H = 12
CEILING_SHADOW = np.linspace(0.62, 1.0, PAPER_H)   # wallpaper darkens toward the ceiling
GOLD = ramp((90, 60, 10), (255, 225, 120), 5)
WOOD = ramp((40, 20, 10), (170, 110, 60), 5)

# --- wallpaper motifs: b base, p the pattern's shade, P its light ---------------------------------------
DAMASK = """
bbbPbbbb
bbPpPbbb
bPbpbPbb
bbPpPbbb
bbbPbbbb
bbbbbbbb
"""
STRIPES = """
bbbbPbbbbbbg
bbbbPbbbbbbg
"""
TRELLIS = """
PbbbbbbP
pPbbbbPp
bpPbbPpb
bbpPPpbb
bbpPPpbb
bpPbbPpb
pPbbbbPp
PbbbbbbP
"""
PLANKS = """
bbbbbpPbbbbp
bbbbbpPbbbbp
bbpbbpPbbbbp
bbbbbpPbbbbp
bbbbbpPbbpbp
bbbbbpPbbbbp
"""
IVY = """
................IIII....
...............IiIiI....
..II...........IIIIi....
.IiII...........iI......
.IIIi..........I........
..Ii..........I.........
...I.........I..........
....I.......iI..........
.....I.....IiII.........
......I....IIIi.........
.......I....iI..........
........I...............
"""

# --- floor motifs ---------------------------------------------------------------------------------------
HERRINGBONE = """
llllldmmmmmd
llllldmmmmmd
ddddddmmmmmd
mmmmmdlllllD
mmmmmdDDDDDD
mmmmmdllllld
"""
BOARDS = """
mmmmmmmmmmmmmmmmmmmmmmmm
mmmlmmmmmmmmmmmmmmmmmmmm
mmmmmmmmmmmmmmmmmmdmmmmm
dddddddddddddddddddddddd
llllllllllllllllllllllll
lllllllllllllkllllllllll
llllllllllllllllllllllll
dddddddddddddddddddddddd
"""

FLOORS = [
    {   # 1: the foyer
        "paper": (DAMASK, ramp((10, 18, 60), (90, 120, 220), 4)),
        "wainscot": WOOD,
        "floor": "marble",
        "stone": ramp((16, 20, 52), (70, 82, 150), 4),
        "trim": (120, 150, 230),
    },
    {   # 2: the dining hall
        "paper": (STRIPES, ramp((50, 6, 16), (190, 40, 50), 4)),
        "wainscot": WOOD,
        "floor": "parquet",
        "stone": ramp((44, 14, 12), (120, 50, 36), 4),
        "trim": (220, 90, 80),
    },
    {   # 3: the conservatory
        "paper": (TRELLIS, ramp((10, 36, 20), (70, 150, 80), 4)),
        "ivy": ramp((10, 70, 20), (120, 220, 90), 3),
        "wainscot": ramp((60, 60, 64), (170, 170, 176), 5),
        "floor": "terracotta",
        "stone": ramp((14, 40, 28), (70, 120, 84), 4),
        "trim": (110, 200, 120),
    },
    {   # 4: the attic
        "paper": (PLANKS, ramp((54, 34, 16), (176, 130, 70), 4)),
        "wainscot": ramp((40, 26, 12), (140, 96, 50), 5),
        "floor": "boards",
        "stone": ramp((34, 22, 12), (100, 70, 36), 4),
        "trim": (220, 170, 90),
    },
]


# --- the wall's face -------------------------------------------------------------------------------------
def face(floor: ArtData) -> Picture:
    """Paper (darkening toward the ceiling), a gilded rail, bevelled wainscot panels, the skirting."""
    motif, colours = floor["paper"]
    paper = art(repeat(motif, CELL_W, PAPER_H), {"b": colours[1], "p": colours[0], "P": colours[3],
                                                 "g": GOLD[2]})
    if "ivy" in floor:
        leaves = art(IVY, shades("iI", floor["ivy"][1:]))
        leafy = leaves[..., 3] > 0
        paper[leafy] = leaves[leafy]
    paper = brightness(paper, CEILING_SHADOW)
    rail = np.concatenate([solid(1, CELL_W, GOLD[4]), solid(1, CELL_W, GOLD[1])])
    wainscot = wainscot_panels(floor["wainscot"])
    wood = floor["wainscot"]
    skirting = np.concatenate([solid(1, CELL_W, wood[3]), solid(1, CELL_W, wood[0])])
    return np.concatenate([paper, rail, wainscot, skirting])


def wainscot_panels(colours: list[Rgb]) -> Picture:
    """Two raised panels, 12 x 4, in the wainscot's middle shade."""
    panels = solid(4, CELL_W, colours[2])
    for left in (0, 12):
        bevel(panels, 0, left, 4, 12)
    return panels


# --- the wall's top ---------------------------------------------------------------------------------------
def top(floor: ArtData) -> Picture:
    """Stone blocks, each bevelled, in two offset courses, with a little texture."""
    colours = floor["stone"]
    picture = solid(CELL_H, CELL_W, colours[1])
    for course, row in enumerate(range(0, CELL_H, 8)):
        offset = 6 if course % 2 else 0
        for left in range(-offset, CELL_W, 12):
            x0, width = max(left, 0), min(12, CELL_W - max(left, 0), left + 12)
            if width > 1:
                bevel(picture, row, x0, 8, width, light=1.5, dark=0.55)
    speckle(picture, 0.15, seed=floor["stone"][0][0])
    return picture


# --- the floors ---------------------------------------------------------------------------------------------
def marble() -> Picture:
    """Black and white squares (12 x 16), each with a vein and a sheen in its top corner."""
    light, dark = ramp((150, 150, 160), (235, 235, 245), 4), ramp((26, 26, 34), (90, 90, 104), 4)
    picture = solid(CELL_H, CELL_W, light[2])
    for square_row in range(2):
        for square_column in range(2):
            colours = light if (square_row + square_column) % 2 == 0 else dark
            top, left = square_row * 16, square_column * 12
            picture[top:top + 16, left:left + 12, :3] = colours[2]
            for step in range(12):  # a diagonal vein
                picture[top + 2 + step, left + 10 - (step * 3) // 4, :3] = colours[0]
            picture[top + 1:top + 3, left + 1:left + 3, :3] = colours[3]  # the sheen
            bevel(picture, top, left, 16, 12, light=1.12, dark=0.8)
    return picture


def parquet() -> Picture:
    colours = WOOD
    return art(repeat(HERRINGBONE, CELL_W, CELL_H), {"l": colours[3], "m": colours[2], "d": colours[0],
                                                    "D": colours[1]})


def terracotta() -> Picture:
    """Tiles 12 x 8, each a little different, in grout."""
    colours = ramp((90, 34, 14), (210, 110, 60), 5)
    picture = solid(CELL_H, CELL_W, colours[0])
    rng = np.random.default_rng(3)
    for top in range(0, CELL_H, 8):
        for left in range(0, CELL_W, 12):
            shade = colours[int(rng.integers(2, 5))]
            picture[top:top + 7, left:left + 11, :3] = shade
            bevel(picture, top, left, 7, 11, light=1.15, dark=0.82)
    speckle(picture, 0.08, seed=4)
    return picture


def boards() -> Picture:
    colours = ramp((40, 24, 10), (150, 100, 50), 5)
    picture = art(repeat(BOARDS, CELL_W, CELL_H), {"m": colours[2], "l": colours[3], "d": colours[0],
                                                   "k": colours[1]})
    speckle(picture, 0.1, seed=5)
    return picture


FLOOR_PICTURES = {"marble": marble, "parquet": parquet, "terracotta": terracotta, "boards": boards}

# --- decorations ------------------------------------------------------------------------------------------
PORTRAIT = """
GHHHHHHHHHHHHG
HgbbbbbbbbbbGH
HgbbbssssbbbGH
HgbbsSSSSsbbGH
HgbsSWWWSWWWsH
HgbsSWWWSWWWsH
HgbssSSSSSSssH
HgbbsSSKKSSsbH
HgbbbsSSSSsbbH
HgbccccccccccH
GHHHHHHHHHHHHG
"""
EYE_WHITES = ((4, 5), (4, 9))
PUPILS = {"centre": ((0, 1), (1, 1)), "left": ((0, 0), (1, 0)), "right": ((0, 2), (1, 2)),
          "up": ((0, 1),), "down": ((1, 1),)}
CANDELABRA_FLAMES = ("""
.y...F...y.
.F...y...F.
""", """
.F...y...F.
.y...F...y.
""", """
.y...y...F.
.F...F...y.
""")
CANDELABRA = """
.W...W...W.
.W...W...W.
.B...B...B.
.BBBBBBBBB.
.....B.....
.....B.....
....BBB....
...BBBBB...
"""
BOOKSHELF = """
DDDDDDDDDDDD
DrRbBgGyYrRD
DrRbBgGyYrRD
DrRbBgGyYrRD
DDDDDDDDDDDD
DgGrRyYbBgGD
DgGrRyYbBgGD
DgGrRyYbBgGD
DDDDDDDDDDDD
"""
FERN = """
.L...L..L..
..L.L..L...
L..LlL.L..L
.L.LlLlL.L.
..LllllLL..
....lll....
..TTTTTTT..
...TtttT...
...TtttT...
....TTT....
"""
WINDOW = """
DDDDDDDDDDDD
DnnnnnDnnnnD
DnnMMnDnnnnD
DnMMMnDnnsnD
DnnMMnDnnnnD
DDDDDDDDDDDD
DmmmmmDmmmmD
DmmmmmDmmmmD
DDDDDDDDDDDD
"""
COBWEB = """
CCCCCCCCCC
CcC..C..C.
CCcC.C.C..
C.CcCCC...
C..CCcC...
C.C..CC...
CC....C...
C.....c...
C.........
c.........
"""
CRATE = """
DDDDDDDDDDDD
DwwwDwwwDwwD
DwwwDwwwDwwD
DDDDDDDDDDDD
DwwwDwwwDwwD
DwwwDwwwDwwD
DDDDDDDDDDDD
"""
FRONT_DOOR = """
KKKKKKKK
KDDDDDDK
KDwwwwDK
KDwlwwDK
KDwlwwDK
KDwwwwDK
KDDDDDDK
KDwwwwDK
KDwlwwDK
KDwlwwYK
KDwwwwYK
KDwwwwDK
KDDDDDDK
KDwwwwDK
KDwlwwDK
KDwlwwDK
KDwwwwDK
KDDDDDDK
KKKKKKKK
"""
SKIN = ramp((120, 70, 50), (250, 200, 160), 3)
DECOR = [
    [{"kind": "portrait", "art": PORTRAIT, "eyes": True,
      "colours": {"G": GOLD[1], "H": GOLD[3], "g": GOLD[2], "b": (20, 40, 36), "c": (40, 60, 50),
                  "s": SKIN[1], "S": SKIN[2], "K": (20, 10, 10), "W": (240, 236, 220)}},
     {"kind": "candelabra", "frames": [flame.strip("\n") + "\n" + CANDELABRA.strip("\n")
                                      for flame in CANDELABRA_FLAMES],
      "colours": {"y": (255, 250, 200), "F": (250, 170, 40), "W": (235, 225, 200), "B": GOLD[2]}}],
    [{"kind": "portrait", "art": PORTRAIT, "eyes": True,
      "colours": {"G": GOLD[1], "H": GOLD[3], "g": GOLD[2], "b": (60, 14, 20), "c": (90, 30, 30),
                  "s": SKIN[1], "S": SKIN[2], "K": (20, 10, 10), "W": (240, 236, 220)}},
     {"kind": "bookshelf", "art": BOOKSHELF,
      "colours": {"D": WOOD[1], "r": (140, 30, 30), "R": (200, 60, 50), "b": (30, 50, 130),
                  "B": (70, 100, 200), "g": (30, 100, 50), "G": (70, 160, 90), "y": (160, 130, 40),
                  "Y": (220, 190, 80)}}],
    [{"kind": "fern", "art": FERN, "colours": {"L": (90, 190, 80), "l": (40, 120, 50), "T": (150, 70, 40),
                                                "t": (200, 110, 60)}},
     {"kind": "window", "art": WINDOW,
      "colours": {"D": WOOD[1], "n": (16, 26, 70), "M": (230, 230, 200), "s": (200, 200, 230),
                  "m": (10, 16, 46)},
      "lightning": {"n": (210, 220, 255), "m": (170, 180, 230)}}],
    [{"kind": "cobweb", "art": COBWEB, "colours": {"C": (170, 170, 180), "c": (110, 110, 120)}},
     {"kind": "crate", "art": CRATE, "colours": {"D": WOOD[0], "w": WOOD[2]}}],
]

# --- the title screen -------------------------------------------------------------------------------------
TITLE_MANSION = """
...............................MM...............................
...............................MM...............................
..............................MMMM..............................
.............................MMRMMM.............................
.............................MRMMMM.............................
............................MRMMMMMM............................
...........................MRMMMMMMMM...........................
...........................RMMMMMMMMM...........................
..........................RMMMMMMMMMMM..........................
.........................RMMMMMMMMMMMMM.........................
........MM...............RRRRRRRRRRRRRR...............MM........
........MM................MMMMMMMMMMMM................MM........
........MM................MMMMMMMMMMMM................MM........
........MM.RRRRRRRRR......MMMMMMMMMMMM......RRRRRRRRR.MM........
........MMMMMMMMMMMMR.....MMMggggggMMM.....RMMMMMMMMMMMM........
........MMMMMMMMMMMMMR....MMMgWWWWgMMM....RMMMMMMMMMMMMM........
........MMMMMMMMMMMMMMR...MMMgWWWWgMMM...RMMMMMMMMMMMMMM........
.......MMMMMMMMMMMMMMMMR..MMMggggggMMM..RMMMMMMMMMMMMMMMM.......
......MMMMMMMMMMMMMMMMMMR.MMMMMMMMMMMM.RMMMMMMMMMMMMMMMMMM......
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
....RRRRRRRRRRRRRRRRRRRRRRMMMMMMMMMMMMRRRRRRRRRRRRRRRRRRRRRR....
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMRRRRRRMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMggggMMMMwwwwMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMgWWgMMMMwwwwMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMggggMMMMwwwwMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
....HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH....
hhHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHhh
hhhhHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHhhhh
hhhhhhhHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHhhhhhhh
hhhhhhhhhhhHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHhhhhhhhhhhhh
hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh
"""
TITLE_MANSION_COLOURS = {"M": (22, 16, 34), "R": (96, 86, 150), "w": (50, 34, 28), "W": (255, 230, 150),
                         "g": (210, 130, 50), "D": (60, 34, 20), "H": (22, 40, 28), "h": (12, 22, 16)}
MOON = """
.......LLLLLL.......
.....LLLLLLLLLL.....
....LLLLLLLLLLLL....
...LLLLLLccLLLLLL...
..LLLLLLlccLLLLLLl..
..LLLcLLLLLLLLLLLl..
.LLLLccLLLLLLLLLLll.
.LLLLLLLLLLLLcLLLll.
LLLLLLLLLLLLccLLLLll
LLLLLLLLLLLLLLLLLLll
LLLLLLLLLLLLLLLLLLll
LLLLLLLLcLLLLLLLLLll
LLLLLLLccLLLLLLLLlll
.LLLLLLLLLLLLLLcLll.
.LLLLLLLLLLLLLccLll.
..LLLLLLLLLLLLLLll..
..LLLLcLLLLLLLLlll..
...LLLLLLLLLLLlll...
....LLLLLLLLLlll....
.....LLLLLLLlll.....
.......LLLLlll......
"""
MOON_COLOURS = {"L": (250, 245, 210), "l": (200, 195, 170), "c": (190, 185, 150)}


def world_pictures() -> Pictures:
    door_colours = {"K": (14, 8, 6), "D": WOOD[0], "w": WOOD[2], "l": WOOD[3], "Y": GOLD[3]}
    pictures: Pictures = {"front_door": art(FRONT_DOOR, door_colours),
                          "title_mansion": art(TITLE_MANSION, TITLE_MANSION_COLOURS),
                          "title_moon": art(MOON, MOON_COLOURS)}
    for number, floor in enumerate(FLOORS, start=1):
        pictures[f"floor{number}"] = FLOOR_PICTURES[floor["floor"]]()
        pictures[f"wall{number}_top"] = top(floor)
        pictures[f"wall{number}_face"] = face(floor)
        pictures[f"wall{number}_trim"] = solid(1, 1, floor["trim"])
        for decoration in DECOR[number - 1]:
            pictures.update(decoration_pictures(number, decoration))
    return pictures


def decoration_pictures(number: int, decoration: ArtData) -> Pictures:
    """A decoration's pictures, named for looks/scenery.py: frames that flicker, eyes that follow, a
    lightning version."""
    name = f"decor{number}_{decoration['kind']}"
    colours = decoration["colours"]
    if decoration.get("eyes"):
        return {f"{name}_{look}": art(with_pupils(decoration["art"], look), colours) for look in PUPILS}
    if "frames" in decoration:
        return {f"{name}_{index}": art(text, colours) for index, text in enumerate(decoration["frames"])}
    pictures = {name: art(decoration["art"], colours)}
    if "lightning" in decoration:
        pictures[f"{name}_lightning"] = art(decoration["art"], {**colours, **decoration["lightning"]})
    return pictures


def with_pupils(text: str, look: str) -> str:
    """The portrait with its pupils (K) placed in the eye whites, looking one way."""
    rows = [list(row) for row in text.strip("\n").split("\n")]
    for eye_row, eye_column in EYE_WHITES:
        for row, column in PUPILS[look]:
            rows[eye_row + row][eye_column + column] = "K"
    return "\n".join("".join(row) for row in rows)
