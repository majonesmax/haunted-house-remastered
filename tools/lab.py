"""The research lab: Haunted House running in the Stella emulator, with the extras that experiments need.

Uses the game's own emulator wrapper (game/emulator.py, from Adventure Forever) and adds:
save states (to rewind and try again), RAM pokes (to put the player somewhere and see what the game does),
and a few helpers for holding the joystick and console switches.

Pokes are for research only. A remaster must never write the game's RAM while someone plays.

    lab = Lab()
    lab.reset()                     # press RESET: a new game in the current game number
    lab.hold(JOY_RIGHT, frames=60)  # walk right for a second
    lab.peek(POS_X)                 # read a byte, by its $80-$FF address
    saved = lab.save(); ...; lab.load(saved)
"""

import ctypes as C
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(HERE, "roms", "haunted_house.a26")
SHOTS = os.path.join(HERE, "shots")
sys.path.insert(0, HERE)

from game import emulator as E  # noqa: E402

# Stella softens this game's flicker with its "phosphor" effect: each colour channel of the picture is the
# larger of this frame and half of the previous picture (checked over 120 frames). The core keeps doing it
# for Haunted House even with its stella_phosphor option off, so picture() returns blended frames: a fading
# afterimage, and a sprite over last frame's glow can show in a mixed colour. Pixel tests must allow for it.

JOY_B, JOY_SELECT, JOY_START = E.JOY_B, E.JOY_SELECT, E.JOY_START
JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT = E.JOY_UP, E.JOY_DOWN, E.JOY_LEFT, E.JOY_RIGHT
BUTTON = JOY_B      # the joystick's one button (lights a match)
RESET = JOY_START   # the console's RESET switch
SELECT = JOY_SELECT  # the console's SELECT switch
# The left difficulty switch, as the Stella core maps it (found by experiment): L sets it to A, L2 back to
# B (the default). It stays where it was put, and save states don't record it - set it explicitly.
LEFT_DIFFICULTY_A, LEFT_DIFFICULTY_B = 10, 12


class Lab:
    def __init__(self, rom=ROM):
        self.core = E.Core()
        self.core.load(rom)
        self.frame_count = 0
        lib = self.core.lib
        lib.retro_serialize_size.restype = C.c_size_t
        lib.retro_serialize.restype = C.c_bool
        lib.retro_unserialize.restype = C.c_bool
        self.run(30)  # let the console settle after power-on

    # --- running --------------------------------------------------------------------------
    def run(self, frames=1, held=()):
        """Run some frames with the given joypad ids held."""
        for _ in range(frames):
            self.core.joy.clear()
            self.core.joy.update(held)
            self.core.run()
            self.frame_count += 1

    def hold(self, *held, frames=1):
        self.run(frames, held)

    def reset(self):
        """Press and release RESET: a new game in the current game number."""
        self.hold(RESET, frames=5)
        self.run(5)

    def run_until(self, test, limit=600, held=()):
        """Run frames until test(lab) is true; return the frames it took, or None if it never was."""
        for count in range(limit):
            if test(self):
                return count
            self.run(1, held)
        return None

    # --- memory ---------------------------------------------------------------------------
    @property
    def ram(self):
        return self.core.ram

    def peek(self, address):
        return int(self.core.ram[address - 0x80])

    def poke(self, address, value):
        self.core.ram[address - 0x80] = value & 0xFF

    def snapshot(self):
        return bytes(self.core.ram)

    # --- save states ----------------------------------------------------------------------
    def save(self):
        size = self.core.lib.retro_serialize_size()
        buffer = C.create_string_buffer(size)
        if not self.core.lib.retro_serialize(buffer, size):
            raise RuntimeError("the core would not save its state")
        return buffer.raw

    def load(self, state):
        buffer = C.create_string_buffer(state, len(state))
        if not self.core.lib.retro_unserialize(buffer, len(state)):
            raise RuntimeError("the core would not load the state")

    # --- the picture ----------------------------------------------------------------------
    def picture(self):
        """The current frame as an RGB array (rows, columns, 3)."""
        return np.array(self.core.frame)
