"""Colour palettes shared by the looks.

NES               the NES's 64 colours (the common 2C02 palette) - the NES look draws only in these, and every
                  look uses them for objects it draws as the original 2600 graphic (looks/base.py)
FLASH_CYCLE       NES colours that flashing 2600 colours (the chalice) cycle through
ORIGINAL_TO_NES   2600 object colour -> NES colour, for the original graphics
"""

import numpy as np

NES = [  # 64 colours, 4 a row: colour 0x28 is row 0x28, entry 0
    (84, 84, 84), (0, 30, 116), (8, 16, 144), (48, 0, 136),  # 0x00-0x03
    (68, 0, 100), (92, 0, 48), (84, 4, 0), (60, 24, 0),  # 0x04-0x07
    (32, 42, 0), (8, 58, 0), (0, 64, 0), (0, 60, 0),  # 0x08-0x0B
    (0, 50, 60), (0, 0, 0), (0, 0, 0), (0, 0, 0),  # 0x0C-0x0F
    (152, 150, 152), (8, 76, 196), (48, 50, 236), (92, 30, 228),  # 0x10-0x13
    (136, 20, 176), (160, 20, 100), (152, 34, 32), (120, 60, 0),  # 0x14-0x17
    (84, 90, 0), (40, 114, 0), (8, 124, 0), (0, 118, 40),  # 0x18-0x1B
    (0, 102, 120), (0, 0, 0), (0, 0, 0), (0, 0, 0),  # 0x1C-0x1F
    (236, 238, 236), (76, 154, 236), (120, 124, 236), (176, 98, 236),  # 0x20-0x23
    (228, 84, 236), (236, 88, 180), (236, 106, 100), (212, 136, 32),  # 0x24-0x27
    (160, 170, 0), (116, 196, 0), (76, 208, 32), (56, 204, 108),  # 0x28-0x2B
    (56, 180, 204), (60, 60, 60), (0, 0, 0), (0, 0, 0),  # 0x2C-0x2F
    (236, 238, 236), (168, 204, 236), (188, 188, 236), (212, 178, 236),  # 0x30-0x33
    (236, 174, 236), (236, 174, 212), (236, 180, 176), (228, 196, 144),  # 0x34-0x37
    (204, 210, 120), (180, 222, 120), (168, 226, 144), (152, 226, 180),  # 0x38-0x3B
    (160, 214, 228), (160, 162, 160), (0, 0, 0), (0, 0, 0),  # 0x3C-0x3F
]
BLACK = 0x0F
FLASH_CYCLE = (0x21, 0x24, 0x26, 0x28, 0x2A, 0x2C)
ORIGINAL_TO_NES = {0x36: 0x16, 0x1A: 0x28, 0xC8: 0x2A, 0x00: 0x2D, 0x0E: 0x30, 0x66: 0x14, 0x28: 0x27,
                   0x08: 0x10}


def flash_colour(frame_no, every=6):
    """The NES colour a flashing object shows on this frame."""
    return FLASH_CYCLE[(frame_no // every) % len(FLASH_CYCLE)]


def nearest_nes(rgb):
    """Index of the NES colour closest to (r, g, b)."""
    return int(np.argmin(((np.array(NES) - rgb) ** 2).sum(axis=1)))
