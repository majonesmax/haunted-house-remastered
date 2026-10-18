"""Haunted House, remastered: the Atari 2600 game running unmodified in an emulator, redrawn live in a new
look, with the original alongside.

Usage: python play.py [ROM] [--look nes|snes] [--pack <pack>]

Keys (H in the game shows them; the list is app/controls.py):
       arrows + space   the joystick: move, light a match, drop what you carry
       Tab / Enter      GAME SELECT / GAME RESET
       L   the next look: NES, SNES (each with its own pack, and its own sound chip for the music)
       D   the left difficulty switch: lightning on (B, the default) or off (A)
       M   the soundtrack on or off
       E   the sound effects: remastered (the default) or the original 2600 sound
       V   view: side by side -> remaster -> 2600      P   pause      S   screenshot
       F   fullscreen      H   help      Esc   quit
"""

import argparse
import os
import sys

import content
import looks
from game import paths


def options():
    parser = argparse.ArgumentParser(description="Atari 2600 Haunted House, remastered live.")
    parser.add_argument("rom", nargs="?", default=paths.ROM, help="your Haunted House ROM")
    parser.add_argument("--look", default="nes", choices=sorted(looks.LOOKS), help="the look to start in")
    parser.add_argument("--pack", help="a pack to show instead of the look's own (packs/)")
    args = parser.parse_args()
    if not os.path.isfile(args.rom):
        parser.error(f"no ROM at {args.rom} - give the path to your Haunted House ROM")
    if not os.path.isfile(paths.CORE):
        parser.error(f"no emulator core at {paths.CORE} - run: python tools/get_core.py")
    if args.pack and args.pack not in content.names():
        parser.error(f"no pack called {args.pack!r} (there are: {', '.join(content.names())})")
    return args


def main():
    args = options()
    from app.window import GameWindow  # after the checks: opening the window starts the sound and display
    GameWindow(args.rom, args.look, args.pack).run()


if __name__ == "__main__":
    sys.exit(main())
