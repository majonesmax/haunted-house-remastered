"""What's drawn: a CAST (who - the eyes, monsters, items, stairs) and a WORLD (where - each floor's walls and
floor, the front door). Both come in PACKS: folders in packs/ (and private/packs/ for your own) holding a
pack.json and the pictures. Whatever a pack leaves out is the original 2600 graphic, read from the ROM
(content/original.py) - so even an empty pack plays.

    names()            the packs there are
    load(name, rom)    a Pack: .cast and .world (each a Pictures, with the original as fallback)
"""

import json
import os

import numpy as np
from PIL import Image

from content import original
from game import paths

FOLDERS = (paths.PACKS, paths.USER_PACKS)


class Pictures:
    """Named pictures, each a list of frames (RGBA arrays); a name the pack lacks comes from `fallback`."""

    def __init__(self, folder, fallback):
        self.frames = read_folder(folder)
        self.fallback = fallback

    def get(self, name):
        """The frames for `name`: the pack's own, else the fallback's, else None."""
        if name in self.frames:
            return self.frames[name]
        return self.fallback.get(name)

    def frame(self, name, count):
        """Frame `count` of `name`, cycling through its frames."""
        frames = self.get(name)
        if not frames:
            return None
        return frames[count % len(frames)]

    def own(self, name):
        return name in self.frames

    def names(self):
        """Every picture name there is: the pack's own and the fallback's."""
        return sorted(set(self.frames) | set(self.fallback))


class Pack:
    """A pack: .cast and .world (Pictures), and .info - its pack.json: "title", "description", and "floors",
    a name for each of the four floors. Its soundtrack, if it has one, is music.json in .folder."""

    def __init__(self, folder, rom):
        with open(os.path.join(folder, "pack.json")) as about:
            info = json.load(about)
        self.name = os.path.basename(folder)
        self.folder = folder
        self.info = info
        self.title = info.get("title", self.name)
        self.cast = Pictures(os.path.join(folder, "cast"), original.cast(rom))
        self.world = Pictures(os.path.join(folder, "world"), original.world(rom))


def read_folder(folder):
    """PNG files -> {name: [frames]}: "ghost_0.png", "ghost_1.png" -> "ghost": [two frames]. A file
    without a frame number ("front_door.png") is a single frame."""
    frames = {}
    if not os.path.isdir(folder):
        return frames
    for file_name in sorted(os.listdir(folder)):
        if not file_name.endswith(".png"):
            continue
        stem = file_name[:-4]
        name, _, number = stem.rpartition("_")
        if not name or not number.isdigit():
            name = stem
        picture = np.array(Image.open(os.path.join(folder, file_name)).convert("RGBA"))
        frames.setdefault(name, []).append(picture)
    return frames


def names():
    found = []
    for folder in FOLDERS:
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if os.path.isfile(os.path.join(folder, name, "pack.json")):
                    found.append(name)
    return found


def load(name, rom):
    for folder in FOLDERS:
        path = os.path.join(folder, name)
        if os.path.isfile(os.path.join(path, "pack.json")):
            return Pack(path, rom)
    raise ValueError(f"no pack called {name!r} (there are: {', '.join(names())})")
