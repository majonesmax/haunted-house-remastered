"""Every look, with its own pack, still draws exactly the same pixels in every preview scene.

The scenes are tools/preview.py's. Each remastered picture's fingerprint (SHA-256) is kept in
tests/golden.json. Run this after any change to looks/, content/, packs/ or shared/: if only what you meant to
change differs, accept it with --update, and say what changed. Differing pictures are saved to shots/golden/
to look at.

Usage: python tests/golden.py [--update]
"""

import hashlib
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import looks  # noqa: E402
import preview  # noqa: E402
from game.state import Game  # noqa: E402
from lab import SHOTS, Lab  # noqa: E402
from looks.base import NO_EXTRAS  # noqa: E402

GOLDEN = os.path.join(HERE, "tests", "golden.json")
DIFFERENT = os.path.join(SHOTS, "golden")


def fingerprints():
    """{"look/scene": (sha256, picture)} for every look's own pack and every scene."""
    game = Game()
    lab = Lab()
    found = {}
    for platform in sorted(looks.LOOKS):
        look = looks.make(platform, game.rom)
        for label, scene in preview.SCENES:
            start, start_frame = lab.save(), lab.frame_count  # each scene from the same moment
            extras = scene(lab) or NO_EXTRAS
            picture = look.draw(game.state(lab.ram), lab.frame_count, extras)
            found[f"{platform}/{label}"] = (hashlib.sha256(picture.tobytes()).hexdigest(), picture)
            lab.load(start)
            lab.frame_count = start_frame
    return found


def main():
    update = "--update" in sys.argv
    found = fingerprints()
    if update:
        with open(GOLDEN, "w") as out:
            digests = {key: digest for key, (digest, _picture) in found.items()}
            json.dump(digests, out, indent=1, sort_keys=True)
        print(f"{len(found)} pictures accepted into {GOLDEN}")
        return 0
    with open(GOLDEN) as golden_file:
        expected = json.load(golden_file)
    differing = [key for key, (digest, _picture) in found.items() if expected.get(key) != digest]
    for key in differing:
        os.makedirs(DIFFERENT, exist_ok=True)
        Image.fromarray(found[key][1]).save(os.path.join(DIFFERENT, key.replace("/", "_") + ".png"))
        print(f"DIFFERENT  {key}")
    missing = sorted(set(expected) - set(found))
    for key in missing:
        print(f"GONE       {key}")
    print(f"{len(found) - len(differing)}/{len(found)} pictures the same")
    return 1 if differing or missing else 0


if __name__ == "__main__":
    sys.exit(main())
