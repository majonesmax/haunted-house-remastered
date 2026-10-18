"""Where things live. Everything else asks here instead of working out paths from its own location.

In development ROOT is the repository. In a packaged app (package/build.py) it's the app's bundled data
folder, which is read-only - so what the game writes (the remembered ROM, the emulator's folders,
screenshots, recordings, the player's own packs) goes to the player's own folders, in the usual places for
their system. (As Adventure Forever's paths.py.)
"""

import os
import sys

APP_NAME = "Haunted House"
APP_VERSION = "1.0"
FROZEN = getattr(sys, "frozen", False)
if FROZEN:  # a packaged app: everything bundled is unpacked here
    ROOT = getattr(sys, "_MEIPASS", None)
else:
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
SHOTS = os.path.join(ROOT, "shots")          # development output (screenshots, sheets)
FONTS = os.path.join(ROOT, "shared", "fonts")


def home(*parts):
    return os.path.join(os.path.expanduser("~"), *parts)


def linux_folder(name, fallback):
    """A Linux user folder (Pictures, Videos) as the desktop names it (~/.config/user-dirs.dirs), else
    ~/fallback."""
    try:
        with open(home(".config", "user-dirs.dirs")) as folders:
            for line in folders:
                if line.startswith(f"XDG_{name}_DIR="):
                    return os.path.expandvars(line.split("=", 1)[1].strip().strip('"'))
    except OSError:
        pass
    return home(fallback)


if not FROZEN:  # development: everything inside the repository (shots/ and recordings/ are git-ignored)
    USER_DIR, SCREENSHOTS, RECORDINGS = ROOT, os.path.join(SHOTS, "play"), os.path.join(ROOT, "recordings")
elif SYSTEM == "macos":
    USER_DIR = home("Library", "Application Support", APP_NAME)
    SCREENSHOTS, RECORDINGS = home("Pictures", APP_NAME), home("Movies", APP_NAME)
elif SYSTEM == "windows":
    USER_DIR = os.path.join(os.environ.get("APPDATA") or home("AppData", "Roaming"), APP_NAME)
    SCREENSHOTS, RECORDINGS = home("Pictures", APP_NAME), home("Videos", APP_NAME)
else:
    USER_DIR = os.path.join(os.environ.get("XDG_DATA_HOME") or home(".local", "share"), APP_NAME)
    SCREENSHOTS = os.path.join(linux_folder("PICTURES", "Pictures"), APP_NAME)
    RECORDINGS = os.path.join(linux_folder("VIDEOS", "Videos"), APP_NAME)

# the player's own packs: beside the remembered ROM in a packaged app, private/packs/ when running from source
USER_PACKS = os.path.join(USER_DIR, "packs") if FROZEN else os.path.join(PRIVATE, "packs")
