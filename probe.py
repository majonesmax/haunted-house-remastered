"""A first look at Haunted House in the emulator: boot, press Reset, walk each way, and save what we see.

Borrows the Stella wrapper from ../adventure-nes (engine/emulator.py) without changing it.
Writes shots/probe_sheet.png (a frame every 20 game frames) and prints how the RAM bytes the disassembly
names - and every other byte that moves - change along the way.

Usage: ../adventure-nes/.venv/bin/python probe.py
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ADVENTURE = os.path.join(os.path.dirname(HERE), "adventure-nes")
sys.path.insert(0, ADVENTURE)
os.chdir(ADVENTURE)  # the wrapper finds its core relative to that project

from engine import emulator as E  # noqa: E402

ROM = os.path.join(HERE, "roms", "haunted_house.a26")
SHOTS = os.path.join(HERE, "shots")
NAMED = {0x8D: "FLOORNO", 0xAA: "POS_X", 0xB5: "POS_Y", 0x96: "LIVES", 0xCC: "GAMEMODE", 0x89: "CLOCK"}
SCRIPT = [  # (what, joystick input, frames)
    ("boot", None, 60), ("reset", E.JOY_START, 10), ("wait", None, 60),
    ("right", E.JOY_RIGHT, 120), ("up", E.JOY_UP, 120), ("left", E.JOY_LEFT, 120),
    ("down", E.JOY_DOWN, 120), ("button", E.JOY_B, 10), ("wait", None, 60),
]
EVERY = 20  # a frame on the sheet every this many game frames


def run_script(core):
    """Play SCRIPT; return the sheet's frames (with labels) and the RAM after every frame."""
    frames, ram_history = [], []
    for what, button, count in SCRIPT:
        for i in range(count):
            core.joy.clear()
            if button is not None:
                core.joy.add(button)
            core.run()
            ram_history.append((what, bytes(core.ram)))
            if len(ram_history) % EVERY == 0:
                frames.append((what, np.array(core.frame)))
    return frames, ram_history


def save_sheet(frames, path, per_row=8):
    height, width = frames[0][1].shape[:2]
    rows = -(-len(frames) // per_row)
    sheet = Image.new("RGB", (per_row * width, rows * height))
    for i, (_what, frame) in enumerate(frames):
        sheet.paste(Image.fromarray(frame), ((i % per_row) * width, (i // per_row) * height))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(path)
    return path


def report(ram_history):
    """For each step: the named bytes at its end, and which other bytes changed during it."""
    previous = ram_history[0][1]
    step_start = 0
    for index in range(1, len(ram_history) + 1):
        ended = index == len(ram_history) or ram_history[index][0] != ram_history[step_start][0]
        if not ended:
            continue
        what, ram = ram_history[index - 1]
        named = "  ".join(f"{name}={ram[address - 0x80]:02X}" for address, name in NAMED.items())
        changed = [0x80 + i for i in range(128) if ram[i] != previous[i] and 0x80 + i not in NAMED]
        print(f"{what:7s} {named}\n        changed: {' '.join(f'{address:02X}' for address in changed)}")
        previous, step_start = ram, index


def main():
    os.makedirs(SHOTS, exist_ok=True)
    core = E.Core()
    core.load(ROM)
    frames, ram_history = run_script(core)
    print(save_sheet(frames, os.path.join(SHOTS, "probe_sheet.png")))
    report(ram_history)


if __name__ == "__main__":
    main()
