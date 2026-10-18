"""Pixel-art helpers shared by every look.

Sprites in this project are drawn as text - one character per pixel, a palette saying what each character
means - so they can be read, edited and diffed like code:

    KNIGHT = '''
    ..KK..
    .KSSK.
    KSSSSK
    '''
    sprite = from_ascii(KNIGHT, {"K": (0, 0, 0), "S": (200, 200, 200)})   # -> 3x6 RGBA array

Arrays are numpy uint8: sprites are RGBA (alpha 0 = transparent, 255 = solid), screens are RGB.
"""

import numpy as np


def from_ascii(art, colours, strict=False):
    """Text art -> RGBA sprite. colours: character -> (r, g, b); "." is always transparent. A character that
    isn't in `colours` is transparent too, or an error with strict=True (catches typos in hand-drawn art).
    Rows must all be the same width - a ragged row is reported with its number."""
    rows = art.strip("\n").split("\n")
    bad = [(i, len(row)) for i, row in enumerate(rows) if len(row) != len(rows[0])]
    if bad:
        raise ValueError(f"ragged sprite rows (row, width): {bad} - expected {len(rows[0])}")
    img = np.zeros((len(rows), len(rows[0]), 4), np.uint8)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char == ".":
                continue
            if char in colours and colours[char] is not None:
                img[y, x] = (*colours[char], 255)
            elif strict:
                raise KeyError(f"no colour for {char!r} (row {y}, column {x})")
    return img


def mirrored(left, shade=None):
    """Text art for a left-right symmetric sprite, from its left half (each row is mirrored onto the right).
    shade: {fill: shade character} - on each row the right-most run of that fill gets its last pixel
    shaded, so the sprite looks lit from the left."""
    rows = []
    for half in left.strip("\n").split("\n"):
        row = list(half + half[::-1])
        if shade:
            for x in range(len(row) - 1, 0, -1):
                if row[x] in shade and row[x - 1] == row[x]:
                    row[x] = shade[row[x]]
                    break
        rows.append("".join(row))
    return "\n" + "\n".join(rows)


def edited(art, edits):
    """A copy of text art with parts of some rows replaced: {row: [(column, "text"), ...]}.
    Handy for poses: an attack pose is the normal pose with the arms redrawn."""
    rows = art.strip("\n").split("\n")
    for row_number, changes in edits.items():
        row = list(rows[row_number])
        for column, text in changes:
            row[column:column + len(text)] = list(text)
        rows[row_number] = "".join(row)
    return "\n" + "\n".join(rows)


def blit(dst, src, x, y):
    """Paste RGBA sprite `src` onto RGB image `dst` with its top-left at (x, y); clipped at the edges,
    transparent pixels skipped. x, y may be fractional (rounded)."""
    x, y = int(round(x)), int(round(y))
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x0 >= x1 or y0 >= y1:
        return
    visible = src[y0 - y:y1 - y, x0 - x:x1 - x]  # the part of src inside dst
    solid = visible[..., 3:4] > 0
    dst[y0:y1, x0:x1] = np.where(solid, visible[..., :3], dst[y0:y1, x0:x1])


def snes_rgb(rgb):
    """Snap colours to the SNES's 15-bit range (5 bits per channel), expanded back to 8 bits."""
    five_bits = np.asarray(rgb, np.uint8) >> 3
    return (five_bits << 3) | (five_bits >> 2)  # the top bits repeated in the bottom, so 31 -> 255


def shade(rgb, factor):
    """An (r, g, b) colour made lighter (factor > 1) or darker (< 1), capped at 255."""
    return tuple(int(min(255, channel * factor)) for channel in rgb)
