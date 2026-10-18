"""Helpers for drawing the nocturne pack in 16-bit style: colour ramps, text art in ramp shades, and shading
worked out in code (bevels, gradients, grain) on top of small text motifs.

A ramp is a run of shades of one material, darkest first (ramp(dark, light, 6)). Text art names its
shades with digits ("1" darkest...) or letters, mapped to colours per picture - the way 16-bit sprites were
made.
"""

import numpy as np

from shared.pixelart import from_ascii
from shared.types import Picture, Rgb


def ramp(dark: Rgb, light: Rgb, count: int) -> list[Rgb]:
    """count shades from dark to light, each (r, g, b)."""
    darkest, lightest = np.array(dark, float), np.array(light, float)
    colours: list[Rgb] = []
    for step in range(count):
        mixed = darkest + (lightest - darkest) * step / (count - 1)
        red, green, blue = (int(channel) for channel in mixed)
        colours.append((red, green, blue))
    return colours


def shades(characters: str, colours: list[Rgb]) -> dict[str, Rgb]:
    """{character: colour}, pairing ramp characters ("12345") with a ramp's colours."""
    return dict(zip(characters, colours))


def art(text: str, colours: dict[str, Rgb]) -> Picture:
    return from_ascii(text, colours, strict=True)


def repeat(motif: str, width: int, height: int) -> str:
    """Text art filled to width x height by repeating a motif across and down."""
    rows = motif.strip("\n").split("\n")
    filled = []
    for y in range(height):
        row = rows[y % len(rows)]
        filled.append((row * (width // len(row) + 1))[:width])
    return "\n".join(filled)


def brightness(picture: Picture, factors) -> Picture:   # factors: one number per row
    """Each row of an RGBA picture made lighter or darker by its factor (a vertical gradient)."""
    out = picture.copy()
    rgb = out[..., :3].astype(float) * np.asarray(factors, float)[:, None, None]
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def bevel(picture: Picture, top: int, left: int, height: int, width: int, light: float = 1.35,
          dark: float = 0.6) -> None:
    """A raised rectangle: its top and left edges lit, its bottom and right edges in shadow."""
    area = picture[top:top + height, left:left + width, :3].astype(float)
    area[0, :] *= light
    area[:, 0] *= light
    area[-1, :] *= dark
    area[:, -1] *= dark
    picture[top:top + height, left:left + width, :3] = np.clip(area, 0, 255).astype(np.uint8)


def speckle(picture: Picture, amount: float, seed: int, strength: float = 0.12) -> None:
    """Fine texture: a few pixels a little lighter or darker (stone, plaster, worn wood)."""
    rng = np.random.default_rng(seed)
    height, width = picture.shape[:2]
    chosen = rng.random((height, width)) < amount
    change = 1 + strength * rng.choice([-1.0, 1.0], (height, width))
    rgb = picture[..., :3].astype(float)
    rgb[chosen] *= change[chosen][:, None]
    picture[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)


def solid(height: int, width: int, colour: Rgb) -> Picture:
    picture = np.zeros((height, width, 4), np.uint8)
    picture[:] = (*colour, 255)
    return picture
