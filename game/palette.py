"""The 2600's 128 NTSC colours as this emulator core draws them: colour byte -> (r, g, b).

Measured by Adventure Forever (its engine/palette.py probes each colour in the running core); the table is
the same for every 2600 game on the same core, so it's copied here as palette_ntsc.json.
"""

import json
import os

from shared.types import Rgb

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "palette_ntsc.json")


def load() -> dict[int, Rgb]:
    with open(TABLE) as table_file:
        return {int(colour): tuple(rgb) for colour, rgb in json.load(table_file).items()}


def rgb(palette: dict[int, Rgb], colour: int) -> Rgb:
    """A 2600 colour byte -> (r, g, b). The TIA ignores bit 0."""
    return palette[colour & 0xFE]
