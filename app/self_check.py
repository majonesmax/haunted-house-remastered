"""play.py --check: the app runs itself for a few seconds and says whether it works - from the source, or
inside a built download (the way to check a build, on any system, without playing).

It loads everything, shows the story, presses a key for the title, starts game 1, lights a match and walks,
with every look drawing; then it saves the grid view as a picture and says what it saw - printed, and in
self-check.txt beside the picture (a built Windows app has no console to print to). The sound is held silent
throughout.
"""

import os
import time

import numpy as np
import pygame
from PIL import Image

from game import paths

LOADING_LIMIT = 60          # seconds: longer than this to load is a failure
STEPS = [("story", 90, ()), ("title", 60, ("any key",)), ("start", 30, (pygame.K_RETURN,)),
         ("playing", 120, ()), ("match", 10, (pygame.K_SPACE,)), ("walk", 60, (pygame.K_LEFT,))]
# (what, frames, keys held)


def run(window):
    """Run the checks on a GameWindow. True if all went well."""
    window.audio.mixer = lambda block: np.zeros_like(block)   # silent
    os.makedirs(paths.SCREENSHOTS, exist_ok=True)
    with open(os.path.join(paths.SCREENSHOTS, "self-check.txt"), "w") as log:
        def say(line):
            print(line, flush=True)
            log.write(line + "\n")
        say(f"{paths.APP_NAME} {paths.APP_VERSION} on {paths.SYSTEM}")
        return load(window, say) and play(window, say)


def load(window, say):
    start = time.perf_counter()
    while window.loading:
        window.handle_input()
        if time.perf_counter() - start > LOADING_LIMIT:
            say(f"FAIL: still loading after {LOADING_LIMIT} s")
            return False
        time.sleep(0.05)
    say(f"loaded in {time.perf_counter() - start:.1f} s")
    return True


def play(window, say):
    for _what, frames, pressed in STEPS:
        if "any key" in pressed:
            window.intro, window.keys_held_off = False, True
        window.pressed_by_check = {key for key in pressed if key != "any key"}
        for _ in range(frames):
            window.play_frame()
    window.pressed_by_check = set()
    return report(window, say)


def report(window, say):
    state = window.state
    window.view = "grid"
    window.other_picture = window.other_look.draw(state, window.frame_no)
    path = os.path.join(paths.SCREENSHOTS, "self-check.png")
    Image.fromarray(window.canvas()).save(path)
    say(f"game {state.game}, mode {state.mode}, floor {state.floor + 1}, "
        f"matches used {state.matches_used}, eyes at {state.player}")
    say(f"picture: {path}")
    ok = state.mode == "playing" and state.matches_used >= 1
    say("OK" if ok else "FAIL: the game didn't start, or the match wasn't lit")
    return ok
