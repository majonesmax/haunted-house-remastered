"""Haunted House, remastered: the Atari 2600 game running unmodified in an emulator, redrawn live in a new
look, with the original alongside.

Usage: python play.py [ROM] [--look nes|snes] [--pack <pack>] [--grid]

Without a ROM it uses roms/haunted_house.a26, or the one it remembers, or asks for it to be dropped on a
window (app/rom.py).

Keys (H in the game shows them; the list is app/controls.py):
       arrows + space   the joystick: move, light a match, drop what you carry
       Tab / Enter      GAME SELECT / GAME RESET
       L   the next look: NES, SNES (each with its own pack, and its own sound chip for the music)
       D   the left difficulty switch: lightning on (B, the default) or off (A)
       M   the soundtrack on or off
       E   the sound effects: remastered (the default) or the original 2600 sound
       V   view: side by side -> remaster -> 2600 -> the grid (with the live RAM)
       R   record      P   pause      S   screenshot      F   fullscreen      H   help      Esc   quit
"""

import argparse
import os
import sys

import content
import looks
from game import paths


def options():
    parser = argparse.ArgumentParser(description="Atari 2600 Haunted House, remastered live.")
    parser.add_argument("rom", nargs="?", help="your Haunted House ROM (else it's found, or asked for)")
    parser.add_argument("--look", default="nes", choices=sorted(looks.LOOKS), help="the look to start in")
    parser.add_argument("--pack", help="a pack to show instead of the look's own (packs/)")
    parser.add_argument("--grid", action="store_true", help="start in the grid view")
    parser.add_argument("--check", action="store_true",
                        help="run itself for a few seconds, silently, and say whether it works")
    args = parser.parse_args()
    if not os.path.isfile(paths.CORE):
        parser.error(f"no emulator core at {paths.CORE} - run: python tools/get_core.py")
    if args.pack and args.pack not in content.names():
        parser.error(f"no pack called {args.pack!r} (there are: {', '.join(content.names())})")
    return args


def main():
    args = options()
    from app.rom import find_rom
    rom = find_rom(args.rom)
    if rom is None:
        return 1
    from app.window import GameWindow  # after the checks: opening the window starts the sound and display
    window = GameWindow(rom, args.look, args.pack)
    if args.check:
        from app import self_check
        return 0 if self_check.run(window) else 1
    if args.grid:
        window.view = "grid"
        window.screen = window.set_mode()
    window.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
