"""Plain names for the kinds of data that go everywhere, so a function's signature says what it takes and
gives back: `def draw(self, state: GameState, frame_no: int) -> Picture`, not a bare numpy array type.

pyright checks the type hints (pyrightconfig.json; tools/readability.py counts its findings per file, the
same ratchet as the readability rules).
"""

from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

Picture = NDArray[np.uint8]       # an image: (height, width, 3) RGB or (height, width, 4) RGBA, 0-255 each
Mask = NDArray[np.bool_]          # one True/False per pixel: (height, width)
Floats = NDArray[np.floating[Any]]   # numbers worked on: light levels, distances, sound before it's finished
Samples = NDArray[np.int16]       # sound as the sound card plays it: (count, 2), stereo
Rgb = tuple[int, int, int]        # one colour, 0-255 each
Point = tuple[int, int]           # (x, y)
RamBytes = bytes | NDArray[np.uint8]   # the game's 128 bytes of RAM, from $80: a copy, or the core's view
Instrument = Callable[[Any, int], Floats]   # instrument(pitch in Hz, one or one per sample; length) -> sound
