"""Where things live. Everything else asks here instead of working out paths from its own location.

In development ROOT is the repository. (A packaged app would put its bundled data elsewhere - as Adventure
Forever's paths.py does - but there's no package yet.)
"""

import os
import sys

APP_NAME = "Haunted House"
FROZEN = getattr(sys, "frozen", False)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")

ROM = os.path.join(ROOT, "roms", "haunted_house.a26")
CORE_FILES = {"macos": "stella_libretro.dylib", "windows": "stella_libretro.dll",
              "linux": "stella_libretro.so"}
CORE_FILE = CORE_FILES[SYSTEM]
CORE = (os.environ.get("HAUNTED_CORE")  # another core to try, e.g. a newer Stella build
        or os.path.join(ROOT, "cores", CORE_FILE))  # the emulator (tools/get_core.py downloads it)
PRIVATE = os.path.join(ROOT, "private")      # personal packs - git-ignored, never published
PACKS = os.path.join(ROOT, "packs")          # the packs that ship with the game
USER_PACKS = os.path.join(PRIVATE, "packs")  # the player's own packs
SHOTS = os.path.join(ROOT, "shots")          # development output (screenshots, sheets)
FONTS = os.path.join(ROOT, "shared", "fonts")
USER_DIR = ROOT
SCREENSHOTS = os.path.join(SHOTS, "play")
RECORDINGS = os.path.join(ROOT, "recordings")   # R in the game: videos, sound, RAM and a log (git-ignored)
