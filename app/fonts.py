"""The window's text font: DejaVu Sans Mono, bundled (shared/fonts/, its licence beside it), so the overlay,
the RAM panel and the labels look the same on every system."""

import os

import pygame

from game import paths

FILES = {False: "DejaVuSansMono.ttf", True: "DejaVuSansMono-Bold.ttf"}


def mono(size, bold=False):
    """A pygame font, `size` pixels."""
    return pygame.font.Font(os.path.join(paths.FONTS, FILES[bold]), size)
