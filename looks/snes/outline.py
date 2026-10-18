"""The SNES look's outline rule for sprites: a sprite's silhouette edge in a dark shade of the colour beside
it (DS-style coloured line art), and at most 15 colours (a SNES sprite palette)."""

import numpy as np
from PIL import Image

from shared.pixelart import shade, snes_rgb


DARK = 70  # brightness (0-255) below which a pixel counts as line art rather than fill


def recolour_outline(sprite, dark=0.45, max_colours=15):
    """Silhouette-edge pixels -> a dark shade of the fill colour next to them (DS-style coloured line art);
    interior dark pixels (eyes, mouths) keep their colour. Then cap the sprite at max_colours."""
    out = sprite.copy()
    solid = sprite[..., 3] > 0
    padded = np.pad(solid, 1)
    inside = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]  # all 4 neighbours
    edge = solid & ~inside
    rgb = sprite[..., :3].astype(int)
    brightness = rgb @ [0.299, 0.587, 0.114]
    fill = solid & (brightness > DARK)
    for y, x in zip(*np.nonzero(edge & (brightness <= DARK))):
        rows, cols = slice(max(0, y - 2), y + 3), slice(max(0, x - 2), x + 3)  # the 5x5 around it
        nearby_fill = fill[rows, cols]
        if nearby_fill.any():
            colours, counts = np.unique(rgb[rows, cols][nearby_fill], axis=0, return_counts=True)
            most_common = colours[np.argmax(counts)]
            out[y, x, :3] = snes_rgb(np.array(shade(most_common, dark), np.uint8))
    return capped(out, solid, max_colours)


def capped(sprite, solid, max_colours):
    """At most max_colours colours among the solid pixels (a SNES sprite palette): merged by median cut."""
    pixels = sprite[..., :3][solid]
    if len(np.unique(pixels, axis=0)) <= max_colours:
        return sprite
    as_image = Image.fromarray(pixels.reshape(1, -1, 3))
    reduced = as_image.quantize(colors=max_colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    sprite[solid, :3] = snes_rgb(np.array(reduced.convert("RGB"))[0])
    return sprite
