"""The classic pack's world: a Victorian manor, a floor of the house per floor of the game.

    1  The Foyer          blue damask paper over a wood wainscot; black and white marble
    2  The Dining Hall    red striped paper; parquet
    3  The Conservatory   green trellis with ivy over stone; terracotta tiles
    4  The Attic          bare planks; rough boards

Each floor has a floor tile (24 x 32, one wall cell), a wall top (24 x 32) and a wall face (24 x 20: paper,
a rail, the wainscot, the skirting), built from small text motifs repeated, plus decorations hung on the
faces. Colours are NES palette numbers (shared/palettes.py). Run draw.py to write the PNGs.
"""

from typing import Any

from shared.palettes import NES
from shared.pixelart import from_ascii
from shared.types import Picture, Rgb

Pictures = dict[str, Picture]   # picture name -> the picture, before it's saved as <name>.png
ArtData = dict[str, Any]        # a floor's or a decoration's description, as written in FLOORS below

CELL_W, CELL_H, FACE_H = 24, 32, 20
PAPER_H, RAIL_H, WAINSCOT_H, SKIRTING_H = 12, 1, 5, 2   # the face, top to bottom: 20 px


def repeat(motif: str, width: int, height: int) -> str:
    """Text art filled to width x height by repeating a motif across and down."""
    rows = motif.strip("\n").split("\n")
    filled = []
    for y in range(height):
        row = rows[y % len(rows)]
        filled.append((row * (width // len(row) + 1))[:width])
    return "\n".join(filled)


def stack(*parts: str) -> str:
    return "\n".join(part.strip("\n") for part in parts)


def colours(numbers: dict[str, int]) -> dict[str, Rgb | None]:
    return {char: NES[number] for char, number in numbers.items()}


# --- 1: the foyer --------------------------------------------------------------------------------------
DAMASK = """
bbbPbbbb
bbPPPbbb
bPbPbPbb
bbPPPbbb
bbbPbbbb
bbbbbbbb
"""
WAINSCOT_PANEL = """
DDDDDDDDDDDD
DwwwwwwwwwwD
DwwwwwwwwwwD
DwwwwwwwwwwD
DDDDDDDDDDDD
"""
SKIRTING = """
DDDDDDDDDDDD
KKKKKKKKKKKK
"""
MARBLE = """
LLLLLvdddddd
LLLLvLdddddd
LLLvLLdddddd
LLvLLLdddddd
LvLLLLdddedd
LLLLLLddeddd
LLLLLLdedddd
LLLLLLdddddd
dddddeLLLLLL
ddddedLLLLLL
dddeddLLLLvL
ddeddddLLvLL
ddddddLLvLLL
ddddddLvLLLL
ddddddLLLLLL
ddddddLLLLLL
"""
MASONRY = """
nnnnnnnnnnnm
nnnnnnnnnnnm
mmmmmmmmmmmm
nnnnnmnnnnnn
nnnnnmnnnnnn
mmmmmmmmmmmm
"""

# --- 2: the dining hall --------------------------------------------------------------------------------
STRIPES = """
bbPbbbPb
bbPbbbPb
"""
PARQUET = """
wwwwwDwwwwwD
wwwwwDwwwwwD
DDDDDDwwwwwD
wwwwwDwwwwwD
wwwwwDDDDDDD
wwwwwDwwwwwD
"""
# --- 3: the conservatory -------------------------------------------------------------------------------
TRELLIS = """
PbbbbbbP
bPbbbbPb
bbPbbPbb
bbbPPbbb
bbbPPbbb
bbPbbPbb
bPbbbbPb
PbbbbbbP
"""
IVY = """
................IIII....
...............IIiII....
..II...........IIII.....
.IiII...........II......
.IIII..........I........
..II..........I.........
...I.........I..........
....I.......II..........
.....I.....IiII.........
......I....IIII.........
.......I....II..........
........I...............
"""
STONE = """
SSSSSDSSSSSD
SSSSSDSSSSSD
DDDDDDDDDDDD
SSDSSSSSDSSS
SSDSSSSSDSSS
"""
TERRACOTTA = """
TTTTTTTTTTTg
TtTTTTTTTTTg
TTTTTTTTTTTg
TTTTTTTTtTTg
TTTTTTTTTTTg
TTTTTTTTTTTg
TTTtTTTTTTTg
TTTTTTTTTTTg
gggggggggggg
"""
# --- 4: the attic --------------------------------------------------------------------------------------
PLANKS = """
wwwwwDwwwwwD
wwwwwDwwwwwD
wwkwwDwwwwwD
wwwwwDwwwwwD
wwwwwDwwwkwD
wwwwwDwwwwwD
"""
BOARDS = """
wwwwwwwwwwwwwwwwwwwwwwww
wwwwwkwwwwwwwwwwwwwwwwww
wwwwwwwwwwwwwwwwwwwkwwww
DDDDDDDDDDDDDDDDDDDDDDDD
wwwwwwwwwwwwwwwwwwwwwwww
wwwwwwwwwwwwwkwwwwwwwwww
wwwwwwwwwwwwwwwwwwwwwwww
DDDDDDDDDDDDDDDDDDDDDDDD
"""
# --- the title screen -------------------------------------------------------------------------------
TITLE_MANSION = """
...............................MM...............................
...............................MM...............................
..............................MMMM..............................
.............................MMMMMM.............................
.............................MMMMMM.............................
............................MMMMMMMM............................
...........................MMMMMMMMMM...........................
...........................MMMMMMMMMM...........................
..........................MMMMMMMMMMMM..........................
.........................MMMMMMMMMMMMMM.........................
........MM...............RRRRRRRRRRRRRR...............MM........
........MM................MMMMMMMMMMMM................MM........
........MM................MMMMMMMMMMMM................MM........
........MM.MMMMMMMMM......MMMMMMMMMMMM......MMMMMMMMM.MM........
........MMMMMMMMMMMMM.....MMMWWWWWWMMM.....MMMMMMMMMMMMM........
........MMMMMMMMMMMMMM....MMMWWWWWWMMM....MMMMMMMMMMMMMM........
........MMMMMMMMMMMMMMM...MMMWWWWWWMMM...MMMMMMMMMMMMMMM........
.......MMMMMMMMMMMMMMMMM..MMMWWWWWWMMM..MMMMMMMMMMMMMMMMM.......
......MMMMMMMMMMMMMMMMMMM.MMMMMMMMMMMM.MMMMMMMMMMMMMMMMMMM......
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
....RRRRRRRRRRRRRRRRRRRRRRMMMMMMMMMMMMRRRRRRRRRRRRRRRRRRRRRR....
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMMMMMMMMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMwwwwMMMwwwwMMMMMMMMMMRRRRRRMMMMMMMwwwwMMMMMwwwwMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMWWWWMMMMwwwwMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMWWWWMMMMwwwwMMMM.....
.....MMMwwwwMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMWWWWMMMMwwwwMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
.....MMMMMMMMMMMMMMMMMMMMMMMMDDDDDDMMMMMMMMMMMMMMMMMMMMMMMM.....
....HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH....
HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH
"""
TITLE_MANSION_COLOURS = {"M": 0x0F, "R": 0x03, "w": 0x07, "W": 0x28, "D": 0x07, "H": 0x09}
TITLE_WINDOW = (29, 14, 6, 4)   # the lit tower window (x, y, width, height): the eyes look out of it
MOON = """
.......LLLLLL.......
.....LLLLLLLLLL.....
....LLLLLLLLLLLL....
...LLLLLLccLLLLLL...
..LLLLLLLccLLLLLLL..
..LLLcLLLLLLLLLLLL..
.LLLLccLLLLLLLLLLLL.
.LLLLLLLLLLLLcLLLLL.
LLLLLLLLLLLLccLLLLLL
LLLLLLLLLLLLLLLLLLLL
LLLLLLLLLLLLLLLLLLLL
LLLLLLLLcLLLLLLLLLLL
LLLLLLLccLLLLLLLLLLL
.LLLLLLLLLLLLLLcLLL.
.LLLLLLLLLLLLLccLLL.
..LLLLLLLLLLLLLLLL..
..LLLLcLLLLLLLLLLL..
...LLLLLLLLLLLLLL...
....LLLLLLLLLLLL....
.....LLLLLLLLLL.....
.......LLLLLL.......
"""
MOON_COLOURS = {"L": 0x38, "c": 0x28}


# --- decorations ---------------------------------------------------------------------------------------
PORTRAIT = """
GGGGGGGGGGGGGG
GddddddddddddG
GdddqqqqqqdddG
GddqffffffqddG
GdqfWWWfWWWfdG
GdqfWWWfWWWfdG
GdqffffffffqdG
GddqffKKffqddG
GdddqffffqdddG
GddccccccccddG
GGGGGGGGGGGGGG
"""
EYE_WHITES = ((4, 4), (4, 8))          # (row, column) of each eye's white, top-left: 3 wide, 2 tall
PUPILS = {"centre": ((0, 1), (1, 1)), "left": ((0, 0), (1, 0)), "right": ((0, 2), (1, 2)),
          "up": ((0, 1),), "down": ((1, 1),)}   # (row, column) inside an eye's white
SCONCE_FLAMES = ("""
...F....
..FyF...
...F....
""", """
...F....
...yF...
..FF....
""", """
..F.....
..Fy....
...F....
""")
SCONCE = """
...W....
...W....
...W....
.GGGGG..
..GGG...
...G....
"""
BOOKSHELF = """
DDDDDDDDDD
DrRbBgGrRD
DrRbBgGrRD
DrRbBgGrRD
DDDDDDDDDD
DgGrRrRbBD
DgGrRrRbBD
DgGrRrRbBD
DDDDDDDDDD
"""
FERN = """
.I...I..I..
..I.I..I...
I..III.I..I
.I.IIIII.I.
..IIIIIII..
....III....
..TTTTTTT..
...TTTTT...
...TTTTT...
....TTT....
"""
WINDOW = """
DDDDDDDDDD
DnnnnDnnnD
DnnWWDnnnD
DnWWWDnnnD
DnnWWDnnnD
DDDDDDDDDD
DnnnnDnnnD
DnnnnDnnnD
DnnnnDnnnD
DDDDDDDDDD
"""
COBWEB = """
CCCCCCCCCC
C.C..C..C.
CC.C.C.C..
C.C.CCC...
C..CC.C...
C.C..CC...
CC....C...
C.....C...
C.........
C.........
"""
CRATE = """
DDDDDDDDDD
DwwDwwDwwD
DwwDwwDwwD
DDDDDDDDDD
DwwDwwDwwD
DwwDwwDwwD
DDDDDDDDDD
"""
FRONT_DOOR = """
KKKKKKKK
KDDDDDDK
KDwwwwDK
KDwwwwDK
KDwwwwDK
KDwwwwDK
KDDDDDDK
KDwwwwDK
KDwwwwDK
KDwwwwGK
KDwwwwGK
KDwwwwDK
KDwwwwDK
KDDDDDDK
KDwwwwDK
KDwwwwDK
KDwwwwDK
KDwwwwDK
KDDDDDDK
KKKKKKKK
"""

WOOD = {"D": 0x07, "w": 0x17, "K": 0x0F, "G": 0x27, "k": 0x07}
FLOORS = [
    {   # 1: the foyer
        "paper": (DAMASK, {"b": 0x01, "P": 0x11}),
        "floor": ("motif", MARBLE, {"L": 0x10, "v": 0x00, "d": 0x00, "e": 0x2D}),
        "top": (MASONRY, {"n": 0x02, "m": 0x01}),
        "trim": 0x12,
        "decor": [{"kind": "portrait", "art": PORTRAIT, "eyes": True,
                   "colours": {"G": 0x27, "d": 0x07, "q": 0x17, "f": 0x37, "K": 0x0F, "W": 0x30, "c": 0x16}},
                  {"kind": "sconce", "frames": [flame.strip("\n") + "\n" + SCONCE.strip("\n")
                                                for flame in SCONCE_FLAMES],
                   "colours": {"F": 0x28, "y": 0x30, "W": 0x30, "G": 0x27}}],
    },
    {   # 2: the dining hall
        "paper": (STRIPES, {"b": 0x06, "P": 0x16}),
        "floor": ("motif", PARQUET, {"w": 0x17, "D": 0x07}),
        "top": (MASONRY, {"n": 0x06, "m": 0x05}),
        "trim": 0x16,
        "decor": [{"kind": "portrait", "art": PORTRAIT, "eyes": True,
                   "colours": {"G": 0x27, "d": 0x0C, "q": 0x1C, "f": 0x37, "K": 0x0F, "W": 0x30, "c": 0x11}},
                  {"kind": "bookshelf", "art": BOOKSHELF,
                   "colours": {"D": 0x07, "r": 0x16, "R": 0x26, "b": 0x11, "B": 0x21, "g": 0x1A, "G": 0x2A}}],
    },
    {   # 3: the conservatory
        "paper": (TRELLIS, {"b": 0x0B, "P": 0x1A}),
        "ivy": (IVY, {"I": 0x2A, "i": 0x1A}),
        "wainscot": (STONE, {"S": 0x10, "D": 0x00}),
        "floor": ("motif", TERRACOTTA, {"T": 0x17, "t": 0x27, "g": 0x07}),
        "top": (MASONRY, {"n": 0x0B, "m": 0x09}),
        "trim": 0x1B,
        "decor": [{"kind": "fern", "art": FERN, "colours": {"I": 0x2A, "T": 0x17}},
                  {"kind": "window", "art": WINDOW, "colours": {"D": 0x07, "n": 0x01, "W": 0x30},
                   "lightning": {"n": 0x31}}],
    },
    {   # 4: the attic
        "paper": (PLANKS, {"w": 0x17, "D": 0x07, "k": 0x08}),
        "wainscot": (PLANKS, {"w": 0x17, "D": 0x07, "k": 0x08}),
        "floor": ("motif", BOARDS, {"w": 0x17, "D": 0x07, "k": 0x08}),
        "top": (MASONRY, {"n": 0x07, "m": 0x08}),
        "trim": 0x27,
        "decor": [{"kind": "cobweb", "art": COBWEB, "colours": {"C": 0x10}},
                  {"kind": "crate", "art": CRATE, "colours": {"D": 0x07, "w": 0x17}}],
    },
]


def face(floor: ArtData) -> Picture:
    """The front face of a wall: paper, a gold rail, the wainscot, the skirting (24 x 20)."""
    paper_motif, paper_colours = floor["paper"]
    wainscot_motif, wainscot_colours = floor.get("wainscot", (WAINSCOT_PANEL, WOOD))
    art = stack(repeat(paper_motif, CELL_W, PAPER_H), "G" * CELL_W,
                repeat(wainscot_motif, CELL_W, WAINSCOT_H), repeat(SKIRTING, CELL_W, SKIRTING_H))
    palette = colours({**WOOD, **wainscot_colours, **paper_colours, "G": 0x27})
    picture = from_ascii(art, palette, strict=True)
    if "ivy" in floor:
        ivy_art, ivy_colours = floor["ivy"]
        ivy = from_ascii(ivy_art, colours(ivy_colours), strict=True)
        solid = ivy[..., 3] > 0
        picture[:ivy.shape[0]][solid] = ivy[solid]
    return picture


def floor_tile(floor: ArtData) -> Picture:
    _kind, motif, numbers = floor["floor"]
    return from_ascii(repeat(motif, CELL_W, CELL_H), colours(numbers), strict=True)


def top(floor: ArtData) -> Picture:
    motif, numbers = floor["top"]
    return from_ascii(repeat(motif, CELL_W, CELL_H), colours(numbers), strict=True)


def world_pictures() -> Pictures:
    pictures: Pictures = {"front_door": from_ascii(FRONT_DOOR, colours(WOOD), strict=True),
                "title_mansion": from_ascii(TITLE_MANSION, colours(TITLE_MANSION_COLOURS), strict=True),
                "title_moon": from_ascii(MOON, colours(MOON_COLOURS), strict=True)}
    for number, floor in enumerate(FLOORS, start=1):
        pictures[f"floor{number}"] = floor_tile(floor)
        pictures[f"wall{number}_top"] = top(floor)
        pictures[f"wall{number}_face"] = face(floor)
        pictures[f"wall{number}_trim"] = from_ascii("T", colours({"T": floor["trim"]}), strict=True)
        for decoration in floor["decor"]:
            pictures.update(decoration_pictures(number, decoration))
    return pictures


def decoration_pictures(number: int, decoration: ArtData) -> Pictures:
    """A decoration's pictures, named for scenery.py: frames that flicker, eyes that follow, a lightning
    version."""
    name = f"decor{number}_{decoration['kind']}"
    palette = colours(decoration["colours"])
    if decoration.get("eyes"):
        return {f"{name}_{look}": from_ascii(with_pupils(decoration["art"], look), palette, strict=True)
                for look in PUPILS}
    if "frames" in decoration:
        return {f"{name}_{index}": from_ascii(art, palette, strict=True)
                for index, art in enumerate(decoration["frames"])}
    pictures = {name: from_ascii(decoration["art"], palette, strict=True)}
    if "lightning" in decoration:
        flashed = colours({**decoration["colours"], **decoration["lightning"]})
        pictures[f"{name}_lightning"] = from_ascii(decoration["art"], flashed, strict=True)
    return pictures


def with_pupils(art: str, look: str) -> str:
    """The portrait with its pupils (K) placed in the eye whites, looking one way."""
    rows = [list(row) for row in art.strip("\n").split("\n")]
    for eye_row, eye_column in EYE_WHITES:
        for row, column in PUPILS[look]:
            rows[eye_row + row][eye_column + column] = "K"
    return "\n".join("".join(row) for row in rows)
