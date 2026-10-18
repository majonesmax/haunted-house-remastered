"""Helpers for drawing the nocturne pack in 16-bit style: colour ramps, text art in ramp shades, and shading
worked out in code (bevels, gradients, grain) on top of small text motifs.

A ramp is a run of shades of one material, darkest first (ramp(dark, light, 6)). Text art names its
shades with digits ("1" darkest...) or letters, mapped to colours per picture - the way 16-bit sprites were
made.
"""

import numpy as np

from shared.pixelart import from_ascii


def ramp(dark, light, count):
    """count shades from dark to light, each (r, g, b)."""
    dark, light = np.array(dark, float), np.array(light, float)
    colours = []
    for step in range(count):
        mixed = dark + (light - dark) * step / (count - 1)
        colours.append(tuple(int(channel) for channel in mixed))
    return colours


def shades(characters, colours):
    """{character: colour}, pairing ramp characters ("12345") with a ramp's colours."""
    return dict(zip(characters, colours))


def art(text, colours):
    return from_ascii(text, colours, strict=True)


def repeat(motif, width, height):
    """Text art filled to width x height by repeating a motif across and down."""
    rows = motif.strip("\n").split("\n")
    filled = []
    for y in range(height):
        row = rows[y % len(rows)]
        filled.append((row * (width // len(row) + 1))[:width])
    return "\n".join(filled)


def brightness(picture, factors):
    """Each row of an RGBA picture made lighter or darker by its factor (a vertical gradient)."""
    out = picture.copy()
    rgb = out[..., :3].astype(float) * np.asarray(factors, float)[:, None, None]
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def bevel(picture, top, left, height, width, light=1.35, dark=0.6):
    """A raised rectangle: its top and left edges lit, its bottom and right edges in shadow."""
    area = picture[top:top + height, left:left + width, :3].astype(float)
    area[0, :] *= light
    area[:, 0] *= light
    area[-1, :] *= dark
    area[:, -1] *= dark
    picture[top:top + height, left:left + width, :3] = np.clip(area, 0, 255).astype(np.uint8)


def speckle(picture, amount, seed, strength=0.12):
    """Fine texture: a few pixels a little lighter or darker (stone, plaster, worn wood)."""
    rng = np.random.default_rng(seed)
    height, width = picture.shape[:2]
    chosen = rng.random((height, width)) < amount
    change = 1 + strength * rng.choice([-1.0, 1.0], (height, width))
    rgb = picture[..., :3].astype(float)
    rgb[chosen] *= change[chosen][:, None]
    picture[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)


def solid(height, width, colour):
    picture = np.zeros((height, width, 4), np.uint8)
    picture[:] = (*colour, 255)
    return picture
