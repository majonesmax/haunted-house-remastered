"""NES-style text: a hand-drawn 5x7 pixel font in 8x8 cells, and a framed box. (From Adventure Forever's
shared/hud.py.)
"""

_FONT = """
A .###. #...# #...# ##### #...# #...# #...#
B ####. #...# #...# ####. #...# #...# ####.
C .#### #.... #.... #.... #.... #.... .####
D ####. #...# #...# #...# #...# #...# ####.
E ##### #.... #.... ####. #.... #.... #####
F ##### #.... #.... ####. #.... #.... #....
G .#### #.... #.... #..## #...# #...# .####
H #...# #...# #...# ##### #...# #...# #...#
I ##### ..#.. ..#.. ..#.. ..#.. ..#.. #####
J ....# ....# ....# ....# #...# #...# .###.
K #...# #..#. #.#.. ##... #.#.. #..#. #...#
L #.... #.... #.... #.... #.... #.... #####
M #...# ##.## #.#.# #.#.# #...# #...# #...#
N #...# ##..# #.#.# #..## #...# #...# #...#
O .###. #...# #...# #...# #...# #...# .###.
P ####. #...# #...# ####. #.... #.... #....
Q .###. #...# #...# #...# #.#.# #..#. .##.#
R ####. #...# #...# ####. #.#.. #..#. #...#
S .#### #.... #.... .###. ....# ....# ####.
T ##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..
U #...# #...# #...# #...# #...# #...# .###.
V #...# #...# #...# #...# #...# .#.#. ..#..
W #...# #...# #...# #.#.# #.#.# ##.## #...#
X #...# #...# .#.#. ..#.. .#.#. #...# #...#
Y #...# #...# .#.#. ..#.. ..#.. ..#.. ..#..
Z ##### ....# ...#. ..#.. .#... #.... #####
0 .###. #...# #..## #.#.# ##..# #...# .###.
1 ..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###.
2 .###. #...# ....# ...#. ..#.. .#... #####
3 ####. ....# ....# .###. ....# ....# ####.
4 ...#. ..##. .#.#. #..#. ##### ...#. ...#.
5 ##### #.... ####. ....# ....# ....# ####.
6 .###. #.... #.... ####. #...# #...# .###.
7 ##### ....# ...#. ..#.. .#... .#... .#...
8 .###. #...# #...# .###. #...# #...# .###.
9 .###. #...# #...# .#### ....# ....# .###.
! ..#.. ..#.. ..#.. ..#.. ..#.. ..... ..#..
. ..... ..... ..... ..... ..... ..... ..#..
, ..... ..... ..... ..... ..... ..#.. .#...
- ..... ..... ..... .###. ..... ..... .....
: ..... ..#.. ..... ..... ..... ..#.. .....
' ..#.. ..#.. ..... ..... ..... ..... .....
? .###. #...# ....# ...#. ..#.. ..... ..#..
< ...#. ..#.. .#... #.... .#... ..#.. ...#.
> .#... ..#.. ...#. ....# ...#. ..#.. .#...
"""
GLYPHS = {" ": "." * 35}
for _line in _FONT.strip().split("\n"):
    _ch, *_rows = _line.split(" ")
    assert len(_rows) == 7 and all(len(row) == 5 for row in _rows), _line
    GLYPHS[_ch] = "".join(_rows)
GLYPHS.update({  # a few more, for DOS prompts and paths (a backslash can't sit in the table above)
    "\\": "#...." "#...." ".#..." "..#.." "...#." "....#" "....#",
    "/": "....#" "....#" "...#." "..#.." ".#..." "#...." "#....",
    "_": "....." "....." "....." "....." "....." "....." "#####"})


def text_width(text, scale=1):
    return len(text) * 8 * scale


def draw_text(img, text, x, y, colour, scale=1, shadow=(0, 0, 0)):
    """Draw text on an HxWx3 uint8 image (NES-style: 5x7 glyphs in 8x8 cells, 1 px drop shadow)."""
    for offset, layer_colour in ((1, shadow), (0, colour)):  # the shadow first, 1 px down and right
        if layer_colour is None:
            continue
        for i, letter in enumerate(text.upper()):
            glyph = GLYPHS.get(letter, GLYPHS["?"])
            left = x + (i * 8 + offset) * scale
            draw_glyph(img, glyph, left, y + offset * scale, scale, layer_colour)


def draw_glyph(img, glyph, left, top, scale, colour):
    """One 5x7 glyph ("#" = ink, row by row) with its top-left at (left, top), each dot scale x scale."""
    for row in range(7):
        for column in range(5):
            if glyph[row * 5 + column] != "#":
                continue
            dot_x, dot_y = left + column * scale, top + row * scale
            img[max(dot_y, 0):max(dot_y + scale, 0), max(dot_x, 0):max(dot_x + scale, 0)] = colour


def frame_box(img, x0, y0, x1, y1, colour):
    """A 1 px NES-style frame with cut corners."""
    img[y0, x0 + 1:x1] = colour
    img[y1, x0 + 1:x1] = colour
    img[y0 + 1:y1, x0] = colour
    img[y0 + 1:y1, x1] = colour
