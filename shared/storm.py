"""The storm outside: distant lightning now and then, and its thunder a moment later.

It's the remaster's own weather, not the game's. The game's lightning (dark games) shows the walls; this only
lightens the whole screen a little, the same everywhere, so it shows nothing the game hides. The window asks
it each frame and passes the flash to the look (Extras.flash) and the thunder to the sound (music/board.py).
The same strikes come every time round, so pictures repeat.
"""

import numpy as np

FIRST_STRIKE = 6 * 60               # frames from launch to the first strike: the story's first quiet stretch
GAP_FRAMES = (18 * 60, 40 * 60)     # frames between strikes, chosen at random in this range
THUNDER_DELAY = (50, 150)           # frames from the flash to its thunder: it's some way off
FLASH_SHAPE = (1.0, 0.25, 0.8, 0.35, 0.15)   # a strike's first frames: it flickers...
FLASH_FADE = 0.82                   # ...then fades by this much a frame
FLASH_FRAMES = 30
STRIKES = 2000                      # strikes worked out ahead: hours of play; then the pattern repeats


class Storm:
    def __init__(self, seed: int = 13):
        rng = np.random.default_rng(seed)
        gaps = rng.integers(*GAP_FRAMES, STRIKES)
        self.strikes = FIRST_STRIKE + np.concatenate([[0], np.cumsum(gaps[:-1])])
        self.delays = rng.integers(*THUNDER_DELAY, STRIKES)
        self.period = int(self.strikes[-1] + GAP_FRAMES[1])

    def since_strike(self, frame_no: int) -> tuple[int, int] | tuple[None, None]:
        """(frames since the latest strike, its number), or (None, None) before the first."""
        frame = frame_no % self.period if frame_no >= self.period else frame_no
        number = int(np.searchsorted(self.strikes, frame, side="right")) - 1
        if number < 0:
            return None, None
        return frame - int(self.strikes[number]), number

    def flash(self, frame_no: int) -> float:
        """How bright the sky is this frame: 0 (no lightning) to 1 (the brightest flicker)."""
        since, _number = self.since_strike(frame_no)
        if since is None or since >= FLASH_FRAMES:
            return 0.0
        if since < len(FLASH_SHAPE):
            return FLASH_SHAPE[since]
        return FLASH_SHAPE[-1] * FLASH_FADE ** (since - len(FLASH_SHAPE))

    def thunder(self, frame_no: int) -> bool:
        """Does the latest strike's thunder arrive on this frame?"""
        since, number = self.since_strike(frame_no)
        return since is not None and since == int(self.delays[number])
