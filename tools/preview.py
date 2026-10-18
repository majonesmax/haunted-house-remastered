"""A look, in every situation worth seeing, as one picture: each scene drawn by the look beside the 2600
original, then every monster in every facing, as the look draws them. Look at it after changing a look or a
pack.

Scenes are set up with the lab's RAM pokes (tools/lab.py) - for previews only; play never writes the RAM.
Monsters are kept away unless a scene wants one.

Usage: python tools/preview.py [--look nes] [--pack classic]     -> shots/preview_<look>_<pack>.png
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, LEFT_DIFFICULTY_B, SELECT, SHOTS, Lab  # noqa: E402

sys.path.insert(0, HERE)
import looks  # noqa: E402
from game import ram_map as M  # noqa: E402
from game.state import Game  # noqa: E402
from shared import hud  # noqa: E402

ORIGINAL_W, HEIGHT = 320, 240
LABEL_H = 14
PER_ROW = 3


def park_monsters(lab, keep=()):
    for monster in range(5):
        if monster not in keep:
            lab.poke(M.MONSTER_FLOOR + monster, (lab.peek(M.FLOOR) + 2) & 3)


def run(lab, frames, held=(), keep=()):
    for _ in range(frames):
        park_monsters(lab, keep)
        lab.run(1, held)


def new_game(lab, game):
    while lab.peek(M.GAME_NUMBER) != game - 1:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    run(lab, 3)


def place_item(lab, item, dx, dy):
    lab.poke(M.ITEM_FLOOR + item, lab.peek(M.FLOOR))
    lab.poke(M.ITEM_X + item, lab.peek(M.POS_X) + dx)
    lab.poke(M.ITEM_Y + item, lab.peek(M.POS_Y) + dy)


def place_monster(lab, monster, dx, dy):
    lab.poke(M.MONSTER_FLOOR + monster, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + monster, lab.peek(M.ROOM))
    lab.poke(M.MONSTER_X + monster, lab.peek(M.POS_X) + dx)
    lab.poke(M.MONSTER_Y + monster, lab.peek(M.POS_Y) + dy)


# --- the scenes: each leaves the lab on the frame to draw --------------------------------------------
def title(lab):
    lab.hold(SELECT, frames=2)
    run(lab, 2)


def game_1_start(lab):
    new_game(lab, 1)


def game_1_lit(lab):
    new_game(lab, 1)
    place_item(lab, 1, -12, 3)
    place_item(lab, 2, 10, 4)
    run(lab, 2, [BUTTON])
    run(lab, 3)


def game_1_monsters(lab):
    new_game(lab, 1)
    lab.poke(M.CARRIED, 1)  # the scepter: so they don't catch the player
    place_monster(lab, 0, -40, 4)
    place_monster(lab, 1, -20, -24)
    place_monster(lab, 2, 8, 18)
    run(lab, 2, keep=(0, 1, 2))


def on_floor(number):
    """Game 1 on another floor, a match lit: each floor is its own part of the house."""
    def scene(lab):
        new_game(lab, 1)
        lab.poke(M.FLOOR, number - 1)
        lab.run_until(lambda l: l.peek(M.POS_Y) <= 0x70, held=[JOY_DOWN], limit=40)
        run(lab, 2, [BUTTON])
        run(lab, 3)
    return scene


def game_3_dark(lab):
    new_game(lab, 3)
    run(lab, 2)


def game_3_lit(lab):
    new_game(lab, 3)
    lab.run_until(lambda l: l.peek(M.POS_Y) <= 0x64, held=[JOY_DOWN], limit=60)
    run(lab, 2, [BUTTON])
    run(lab, 3)


def game_3_stairs(lab):
    new_game(lab, 3)
    lab.poke(M.CARRIED, 0)  # the key, for the locked door on the way
    lab.run_until(lambda l: l.peek(M.POS_X) <= 0x74, held=[JOY_LEFT], limit=60)
    lab.run_until(lambda l: l.peek(M.ROOM) == 0, held=[JOY_DOWN], limit=200)
    run(lab, 30, [JOY_DOWN])
    run(lab, 2, [BUTTON])
    run(lab, 3)


def game_3_monster_near(lab):
    new_game(lab, 3)
    lab.poke(M.CARRIED, 1)
    place_monster(lab, 2, -24, 2)
    run(lab, 2, keep=(2,))


def lightning(lab):
    new_game(lab, 3)
    lab.run(5, [LEFT_DIFFICULTY_B])
    lab.poke(M.CARRIED, 1)
    for _ in range(600):
        place_monster(lab, 2, -30, 0)
        run(lab, 1, keep=(2,))
        if lab.peek(0xF5) == 0x0D:
            return


def dying(lab):
    new_game(lab, 1)
    for _ in range(120):
        place_monster(lab, 1, 0, 0)
        run(lab, 1, keep=(1,))
        if lab.peek(M.GAME_STATE) == 1:
            break
    run(lab, 20, keep=(1,))


def won(lab):
    new_game(lab, 1)
    lab.poke(M.CARRIED, 2)
    for offset, shape in enumerate((8, 0xFF, 0xFF)):
        lab.poke(M.URN_SHAPES + offset, shape)
    lab.run_until(lambda l: l.peek(M.GAME_STATE) == 0x44, held=[JOY_RIGHT], limit=60)
    run(lab, 20)


def game_over(lab):
    new_game(lab, 1)
    lab.poke(M.LIVES, 1)
    for _ in range(120):
        place_monster(lab, 2, 0, 0)
        run(lab, 1, keep=(2,))
        if lab.peek(M.GAME_STATE) == 1:
            break
    run(lab, 300)


SCENES = [("title", title), ("game 1", game_1_start), ("game 1, match lit", game_1_lit),
          ("game 1, monsters", game_1_monsters), ("floor 2", on_floor(2)), ("floor 3", on_floor(3)),
          ("floor 4", on_floor(4)), ("game 3, dark", game_3_dark),
          ("game 3, match lit", game_3_lit), ("game 3, stairs", game_3_stairs),
          ("game 3, monster near", game_3_monster_near), ("lightning", lightning), ("caught", dying),
          ("won", won), ("game over", game_over)]


def render(look, game, lab, label, scene):
    scene(lab)
    remaster = look.draw(game.state(lab.ram), lab.frame_count)
    original = np.array(Image.fromarray(lab.picture()).resize((ORIGINAL_W, HEIGHT), Image.NEAREST))
    tile = np.zeros((HEIGHT + LABEL_H, remaster.shape[1] + 4 + ORIGINAL_W, 3), np.uint8)
    tile[LABEL_H:, :remaster.shape[1]] = remaster
    tile[LABEL_H:, remaster.shape[1] + 4:] = original
    hud.draw_text(tile, label, 2, 3, (236, 238, 236))
    return tile


MONSTERS = ("ghost", "bat", "tarantula2", "tarantula3", "tarantula4")
FACINGS = ("left", "right", "up", "down")
STRIP_SCALE = 3
CELL = 20 * STRIP_SCALE


def facing_strip(look, width):
    """Every monster (a row each) in every facing, both frames, at STRIP_SCALE times size."""
    height = LABEL_H + len(MONSTERS) * CELL
    strip = np.zeros((height, width, 3), np.uint8)
    hud.draw_text(strip, "monsters, facing: left / right / up / down, two frames each", 2, 3, (236, 238, 236))
    for row, monster in enumerate(MONSTERS):
        top = LABEL_H + row * CELL
        hud.draw_text(strip, monster, 2, top + CELL // 2 - 4, (152, 150, 152))
        for column, (facing, frame) in enumerate((f, n) for f in FACINGS for n in (0, 1)):
            sprite = look.facing_picture(monster, facing, frame * 8)
            if sprite is None:
                continue
            big = sprite.repeat(STRIP_SCALE, axis=0).repeat(STRIP_SCALE, axis=1)
            left = 120 + column * CELL
            area = strip[top:top + big.shape[0], left:left + big.shape[1]]
            solid = big[:area.shape[0], :area.shape[1], 3:4] > 0
            area[:] = np.where(solid, big[:area.shape[0], :area.shape[1], :3], area)
    return strip


def sheet(tiles):
    rows = []
    for start in range(0, len(tiles), PER_ROW):
        row = tiles[start:start + PER_ROW]
        while len(row) < PER_ROW:
            row.append(np.zeros_like(tiles[0]))
        rows.append(np.concatenate([np.pad(tile, ((4, 4), (4, 4), (0, 0))) for tile in row], axis=1))
    return np.concatenate(rows, axis=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--look", default="nes")
    parser.add_argument("--pack")
    args = parser.parse_args()
    game = Game()
    look = looks.make(args.look, game.rom, args.pack)
    lab = Lab()
    tiles = []
    for label, scene in SCENES:
        start = lab.save()
        tiles.append(render(look, game, lab, label, scene))
        lab.load(start)
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, f"preview_{args.look}_{look.pack.name}.png")
    scenes = sheet(tiles)
    picture = np.concatenate([scenes, facing_strip(look, scenes.shape[1])], axis=0)
    Image.fromarray(picture).save(path)
    print(path)


if __name__ == "__main__":
    main()
