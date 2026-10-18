"""The window's views (V), each laid out as one picture at its own size:

    both       the remaster beside the 2600 original                         584 x 240
    remaster   the remaster alone                                            256 x 240
    2600       the original alone, at the TV's shape                         320 x 240
    grid       four panes, each 512 x 480: what you're playing (top left)   1024 x 960
               over the other look (bottom left), the 2600 (top right) over its live RAM (bottom right)

The window shows the picture scaled to fit (fit_into), keeping its shape.
"""

from functools import lru_cache

import numpy as np
import pygame
from PIL import Image

from looks.layout import SCREEN_H, SCREEN_W
from shared import hud
from shared.types import Mask, Picture, Rgb

GridExtras = tuple[Picture, Picture | None, tuple[str, str]]   # the other look's screen, the RAM pane, the
                                                               # two looks' names

VIEWS = ("both", "remaster", "2600", "grid")
ORIGINAL_W = 320                # the 2600's 160 x 228 picture, shown at the TV's shape
GAP = 8
PANE_W, PANE_H = 512, 480       # a grid pane: a look's screen at twice its size
DIVIDER: Rgb = (60, 60, 80)
BACKGROUND: Rgb = (0, 0, 0)
LABEL: Rgb = (235, 235, 245)


def size(view: str) -> tuple[int, int]:
    """(width, height) of a view's picture."""
    sizes = {"both": (SCREEN_W + GAP + ORIGINAL_W, SCREEN_H), "remaster": (SCREEN_W, SCREEN_H),
             "2600": (ORIGINAL_W, SCREEN_H), "grid": (2 * PANE_W, 2 * PANE_H)}
    return sizes[view]


def compose(view: str, playing: Picture, original: Picture,
            grid_extras: GridExtras | None = None) -> Picture:
    """The view's picture. playing: your look's screen (with any overlays); original: the 2600's frame;
    grid_extras: (the other look's screen, the RAM pane, the two looks' names) for the grid."""
    if view == "remaster":
        return playing
    if view == "2600":
        return tv_shape(original, ORIGINAL_W, SCREEN_H)
    if view == "both":
        gap = np.zeros((SCREEN_H, GAP, 3), np.uint8)
        return np.concatenate([playing, gap, tv_shape(original, ORIGINAL_W, SCREEN_H)], axis=1)
    assert grid_extras is not None, "the grid needs the other look, the RAM pane and the names"
    return grid(playing, original, *grid_extras)


def tv_shape(frame: Picture, width: int, height: int) -> Picture:
    """The 2600's picture resized to width x height, nearest-neighbour (its pixels are twice as wide)."""
    return np.array(Image.fromarray(np.asarray(frame)).resize((width, height), Image.Resampling.NEAREST))


def grid(playing: Picture, original: Picture, other: Picture, ram_pane: Picture | None,
         names: tuple[str, str]) -> Picture:
    canvas = np.zeros((2 * PANE_H, 2 * PANE_W, 3), np.uint8)
    double_into(canvas[:PANE_H, :PANE_W], playing)
    double_into(canvas[PANE_H:, :PANE_W], other)
    scale = min(PANE_W / ORIGINAL_W, PANE_H / 228)          # the 2600 picture, as big as fits, centred
    width, height = int(ORIGINAL_W * scale), int(228 * scale)
    left, top = PANE_W + (PANE_W - width) // 2, (PANE_H - height) // 2
    canvas[top:top + height, left:left + width] = tv_shape(original, width, height)
    if ram_pane is not None:   # none until the first frame has been read
        canvas[PANE_H:, PANE_W:] = ram_pane
    playing_name, other_name = names
    for text, x, y in ((f"PLAYING - {playing_name}", 0, 0), (f"COMPARE - {other_name}", 0, PANE_H),
                       ("ATARI 2600 - 1982", PANE_W, 0)):
        label(canvas, text, x, y)
    canvas[:, PANE_W - 1:PANE_W + 1] = DIVIDER
    canvas[PANE_H - 1:PANE_H + 1, :] = DIVIDER
    return canvas


def double_into(pane: Picture, picture: Picture) -> None:
    """The picture at twice its size, written straight into the pane: each row widened once, then written
    to both of the pane's rows for it."""
    widened = picture.repeat(2, axis=1)
    pane[0::2] = widened
    pane[1::2] = widened


def label(canvas: Picture, text: str, pane_x: int, pane_y: int) -> None:
    """A pane's name at the bottom, in the middle (clear of the looks' game and floor numbers), on a dark
    box."""
    letters, inked = label_picture(text)
    height, width = inked.shape
    left, top = pane_x + (PANE_W - width) // 2, pane_y + PANE_H - 4 - height
    area = canvas[top:top + height, left:left + width]
    area //= 4
    area[inked] = letters[inked]


@lru_cache(maxsize=16)
def label_picture(text: str) -> tuple[Picture, Mask]:
    """(the label's letters, where they're inked): drawn once per text - the labels hardly change."""
    width = hud.text_width(text) + 8
    letters = np.zeros((14, width, 3), np.uint8)
    hud.draw_text(letters, text, 4, 3, LABEL)
    return letters, letters.any(axis=2)


def fit_into(surface: pygame.Surface, screen: pygame.Surface) -> None:
    """Paint `surface` into `screen` as big as fits with its shape kept, centred, bars around it: pixel art
    stays sharp when it's made bigger, and is smoothed when it's made smaller."""
    picture_w, picture_h = surface.get_size()
    screen_w, screen_h = screen.get_size()
    scale = min(screen_w / picture_w, screen_h / picture_h)
    width, height = int(picture_w * scale), int(picture_h * scale)
    resize = pygame.transform.scale if scale >= 1 else pygame.transform.smoothscale
    screen.fill(BACKGROUND)
    screen.blit(resize(surface, (width, height)), ((screen_w - width) // 2, (screen_h - height) // 2))
