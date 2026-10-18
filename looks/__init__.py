"""How the game is drawn: the looks (consoles). Each has its own pack, used unless another is chosen.

    LOOKS              platform id -> the look's class
    make(platform, pack_name, rom)   a look showing a pack (its own pack if pack_name is None)
"""

import content
from looks.nes.look import NesLook
from looks.snes.look import SnesLook

LOOKS = {"nes": NesLook, "snes": SnesLook}


def make(platform, rom, pack_name=None):
    look_class = LOOKS[platform]
    pack = content.load(pack_name or look_class.pack_name, rom)
    return look_class(pack, rom)
