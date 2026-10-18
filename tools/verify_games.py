"""Check, in every one of the nine games, the rules that change with the game number.

For each game it plays out small scenes and compares what happens with what we expect from the ROM tables
(game/rom.py) and the code:

- walls: seen without a match, and with one lit (only game 1 shows them)
- doors: every door on every floor, without and with the master key - locked exactly where LOCKED_DOORS says
- stairs: every room on every floor - the game's own stairs byte, and a walk up or down them
- the master key: shown (and so can be picked up) from game 3; starts beside the player in game 3
- starting places: after RESET every item is where game.monsters.new_game says (key and ghost on floor 4)
- monsters: how many; shown outside your room (game 1 only); the bat steals (games 7-9); the ghost
  ignores the scepter (games 8-9)
- sounds: doors make sounds in games 2-9 only
- lightning: flashes when a monster is in your room, with the left difficulty switch at B, in every game

Monsters are kept on another floor during each scene unless the scene needs one, so none gets in the way.

Usage: python tools/verify_games.py        (prints a table of rules by game; exit code 1 if any is wrong)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, LEFT_DIFFICULTY_A, LEFT_DIFFICULTY_B  # noqa: E402
from lab import RESET, SELECT, Lab  # noqa: E402
from rom_sheet import colour_number, ntsc_palette, rgb_for  # noqa: E402

sys.path.insert(0, HERE)
from game import monsters as model  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402

GAMES = range(9)
JOYSTICK = {"left": JOY_LEFT, "right": JOY_RIGHT, "up": JOY_UP, "down": JOY_DOWN}
OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}
KEY = 0
PLAY_AREA_ROWS = 160           # screen rows above the status line
WALL_PIXELS = 500              # more than this many wall-coloured pixels = walls are showing
SPRITE_HEIGHT, MONSTER_HEIGHT = 0xED, 10
WALK_LIMIT = 200

rom = R.load()
palette = ntsc_palette()
results = {}                   # rule -> {game: (as expected?, detail)}


def record(rule, game, expected, actual, detail=""):
    results.setdefault(rule, {})[game] = (expected == actual, f"expected {expected}, got {actual} {detail}")


# --- scene helpers -----------------------------------------------------------------------------------
def park_monsters(lab, keep=()):
    far_floor = (lab.peek(M.FLOOR) + 2) & 3
    for monster in range(5):
        if monster not in keep:
            lab.poke(M.MONSTER_FLOOR + monster, far_floor)


def run(lab, frames=1, held=(), keep=()):
    for _ in range(frames):
        park_monsters(lab, keep)
        lab.run(1, held)


def walk_until(lab, direction, test, limit=WALK_LIMIT):
    for _ in range(limit):
        if test(lab):
            return True
        run(lab, 1, [JOYSTICK[direction]])
    return test(lab)


def place_player(lab, floor, room, carried=M.NOTHING):
    """Put the player at a room's centre (a poke, for setting the scene)."""
    lab.poke(M.FLOOR, floor)
    lab.poke(M.ROOM, room)
    lab.poke(0x97, 0xFF)
    lab.poke(0x88, 0)
    x, y = R.room_centre(rom, room)
    lab.poke(M.POS_X, x)
    lab.poke(M.POS_Y, y)
    lab.poke(M.CARRIED, carried)
    run(lab, 2)


def light_match(lab):
    run(lab, 2, [BUTTON])


def choose_game(lab, game):
    while lab.peek(M.GAME_NUMBER) != game:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    run(lab, 3)
    return lab.save()


# --- the rules ---------------------------------------------------------------------------------------
def wall_pixels(lab):
    wall_rgb = np.array(rgb_for(palette, colour_number(rom, 8 + lab.peek(M.FLOOR))))
    play_area = lab.picture()[:PLAY_AREA_ROWS]
    return int((play_area == wall_rgb).all(axis=2).sum())


def check_walls(lab, game):
    run(lab, 2)
    dark = wall_pixels(lab)
    light_match(lab)
    lit = 0
    for _ in range(2):  # items and monsters take turns frame by frame, so look at both
        run(lab)
        lit = max(lit, wall_pixels(lab))
    record("walls seen without a match", game, game == 0, dark > WALL_PIXELS, f"({dark} px)")
    record("walls seen with a match lit", game, game == 0, lit > WALL_PIXELS, f"({lit} px)")


def door_passes(lab, start, floor, door, carried):
    """Walk from the door's first room towards the second; does the player get through?"""
    lab.load(start)
    first, second = R.doors(rom)[door]
    direction = "up" if second - first == 2 else "left"
    place_player(lab, floor, first, carried)
    return walk_until(lab, direction, lambda l: l.peek(M.ROOM) == second)


def check_doors(lab, game, start):
    wrong_without, wrong_with = [], []
    for floor in range(R.FLOOR_COUNT):
        locked = R.locked_doors(rom, floor, game)
        for door in range(R.DOOR_COUNT):
            if door_passes(lab, start, floor, door, M.NOTHING) == (door in locked):
                wrong_without.append(f"floor {floor + 1} door {door}")
            if door in locked and not door_passes(lab, start, floor, door, KEY):
                wrong_with.append(f"floor {floor + 1} door {door}")
    record("doors locked exactly as LOCKED_DOORS says", game, [], wrong_without)
    record("the master key opens every locked door", game, [], wrong_with)


def enter_room(lab, start, floor, room):
    """Come into `room` through one of its doors, so the game works out its stairs itself."""
    lab.load(start)
    for direction, (kind, _number) in R.room_exits(rom, room).items():
        if kind == "door":
            step = R.table(rom, "ROOM_STEP")[R.DIRECTIONS.index(direction)]
            neighbour = (room + step) & 0xFF
            place_player(lab, floor, neighbour, KEY)
            return walk_until(lab, OPPOSITE[direction], lambda l: l.peek(M.ROOM) == room)
    return False


def expected_stairs_byte(floor, room, game):
    stairs = R.stairs(rom, floor, game).get(room)
    if stairs is None:
        return 0x0F
    return R.EDGES.index(stairs["edge"]) | (4 if stairs["goes"] == "up" else 0)


def check_stairs(lab, game, start):
    wrong_byte, wrong_walk = [], []
    for floor in range(R.FLOOR_COUNT):
        for room in range(R.ROOM_COUNT):
            if not enter_room(lab, start, floor, room):
                wrong_byte.append(f"floor {floor + 1} room {room}: couldn't get in")
                continue
            expected = expected_stairs_byte(floor, room, game)
            actual = lab.peek(0x9B) & 0x0F
            if actual != expected:
                wrong_byte.append(f"floor {floor + 1} room {room}: ${actual:X} not ${expected:X}")
            if expected != 0x0F and not stairs_walk_works(lab, floor, room, game):
                wrong_walk.append(f"floor {floor + 1} room {room}")
    record("each room's stairs as the stairs tables say", game, [], wrong_byte)
    record("walking off at the stairs changes floor that way", game, [], wrong_walk)


def go_to_centre(lab, room):
    """Walk to the room's centre: across first, then up or down (doors line up with the centre)."""
    x, y = R.room_centre(rom, room)
    across = "right" if lab.peek(M.POS_X) < x else "left"
    walk_until(lab, across, lambda l: l.peek(M.POS_X) == x)
    up_down = "up" if lab.peek(M.POS_Y) < y else "down"
    walk_until(lab, up_down, lambda l: l.peek(M.POS_Y) == y)


def stairs_walk_works(lab, floor, room, game):
    stairs = R.stairs(rom, floor, game)[room]
    go_to_centre(lab, room)
    direction = {"left": "left", "right": "right", "top": "up", "bottom": "down"}[stairs["edge"]]
    walk_until(lab, direction, lambda l: l.peek(M.FLOOR) != floor)
    change = 1 if stairs["goes"] == "up" else -1
    return lab.peek(M.FLOOR) == floor + change


def check_key(lab, game, start):
    lab.load(start)
    at_start = (lab.peek(M.ITEM_FLOOR), lab.peek(M.ITEM_X), lab.peek(M.ITEM_Y))
    record("master key starts beside the player", game, game == 2, at_start == (0, 0x74, 0x84),
           f"{at_start}")
    lab.poke(M.ITEM_FLOOR, lab.peek(M.FLOOR))
    lab.poke(M.ITEM_X, lab.peek(M.POS_X) + 6)
    lab.poke(M.ITEM_Y, lab.peek(M.POS_Y) - 2)
    light_match(lab)
    walk_until(lab, "right", lambda l: l.peek(M.CARRIED) == KEY, limit=30)
    record("master key shown (and can be picked up)", game, game >= 2, lab.peek(M.CARRIED) == KEY)


def put_monster_on_player(lab, monster):
    lab.poke(M.MONSTER_FLOOR + monster, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + monster, lab.peek(M.ROOM))
    lab.poke(M.MONSTER_X + monster, lab.peek(M.POS_X))
    lab.poke(M.MONSTER_Y + monster, lab.peek(M.POS_Y))


def caught_by(lab, monster, frames=120):
    for _ in range(frames):
        put_monster_on_player(lab, monster)
        run(lab, 1, keep=[monster])
        if lab.peek(M.GAME_STATE) == 0x01:
            return True
    return False


def check_monsters(lab, game, start):
    lab.load(start)
    record("monsters in play", game, 3 if game < 4 else 5, lab.peek(M.LAST_MONSTER) + 1)
    lab.load(start)
    lab.poke(M.CARRIED, model.SCEPTER)
    record("the ghost ignores the scepter", game, game >= 7, caught_by(lab, model.GHOST))
    lab.load(start)
    lab.poke(M.CARRIED, KEY)
    caught_by(lab, model.BAT)
    lab.run_until(lambda l: l.peek(M.GAME_STATE) == 0, limit=300)
    record("the bat steals what you carry", game, game >= 6, lab.peek(M.CARRIED) == M.NOTHING)
    record("a monster in the next room is shown", game, game == 0, monster_shown(lab, start, room=3))
    record("a monster in your room is shown", game, True, monster_shown(lab, start, room=2))


def monster_shown(lab, start, room):
    """Put the bat at (or just left of) a room's centre on the player's floor, level with the player in
    room 2, and watch a few frames for the game drawing a monster-sized sprite."""
    lab.load(start)
    lab.poke(M.CARRIED, model.SCEPTER)  # so it can share the room without catching the player
    x, y = R.room_centre(rom, room)
    lab.poke(M.MONSTER_FLOOR + model.BAT, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + model.BAT, room)
    lab.poke(M.MONSTER_ROUTE + model.BAT, room)
    lab.poke(M.MONSTER_X + model.BAT, x - 0x18 if room == 2 else x)
    lab.poke(M.MONSTER_Y + model.BAT, lab.peek(M.POS_Y) if room == 2 else y)
    shown = False
    for _ in range(8):
        run(lab, 1, keep=[model.BAT])
        shown = shown or lab.peek(SPRITE_HEIGHT) == MONSTER_HEIGHT
    return shown


def check_start_places(lab, game, start, presses=10):
    """Press RESET at different moments; the items must land where the model says."""
    lab.load(start)
    wrong = 0
    item_bytes = [base + number for base in (M.ITEM_FLOOR, M.ITEM_X, M.ITEM_Y) for number in range(5)]
    for press in range(presses):
        run(lab, 17 + 23 * press, [JOY_LEFT if press % 2 else JOY_RIGHT])
        lab.poke(M.LIVES, 5)  # so a fresh 9 shows the RESET took effect
        before = lab.snapshot()
        lab.run(1, [RESET])
        if lab.peek(M.LIVES) != 9:
            wrong += 1
            continue
        state = model.State(before)
        model.new_game(state, rom)
        wrong += any(state[address] != lab.peek(address) for address in item_bytes)
    record("items start where the RESET model says", game, 0, wrong, f"({presses} presses)")


def check_door_sound(lab, game, start):
    """Through door 0 (with the key, in case it's locked): is there a doorway or new-room sound?"""
    lab.load(start)
    lab.poke(M.CARRIED, KEY)
    walk_until(lab, "left", lambda l: l.peek(M.POS_X) <= 0x74)
    heard = set()
    for _ in range(WALK_LIMIT):
        run(lab, 1, [JOY_DOWN])
        heard.add(lab.peek(0x93))
        if lab.peek(M.ROOM) == 0:
            break
    record("doors make sounds (doorway, new room)", game, game >= 1, bool(heard & {4, 8}), f"{sorted(heard)}")


def lightning_frames(lab, start, switch):
    lab.load(start)
    lab.run(5, [switch])  # the switch stays put (and isn't part of the save state)
    flashes = 0
    for _ in range(600):
        lab.poke(M.CARRIED, model.SCEPTER)
        put_monster_on_player(lab, 2)
        run(lab, 1, keep=[2])
        flashes += lab.peek(0xF5) == R.table(rom, "COLOURS")[1]  # the walls turn lightning grey
    return flashes


def check_lightning(lab, game, start):
    on_b = lightning_frames(lab, start, LEFT_DIFFICULTY_B)
    on_a = lightning_frames(lab, start, LEFT_DIFFICULTY_A)
    lab.run(5, [LEFT_DIFFICULTY_B])
    record("lightning with a monster near, left switch B", game, True, on_b > 0, f"({on_b} frames)")
    record("no lightning with the left switch at A", game, True, on_a == 0, f"({on_a} frames)")


# --- report ------------------------------------------------------------------------------------------
def print_table():
    print(f"{'rule':52s}" + "".join(f"{game + 1:>3d}" for game in GAMES))
    wrong = 0
    for rule, by_game in results.items():
        marks = "".join(f"{'ok' if by_game[game][0] else 'XX':>3s}" for game in GAMES)
        print(f"{rule:52s}{marks}")
        wrong += sum(not ok for ok, _detail in by_game.values())
    for rule, by_game in results.items():
        for game, (ok, detail) in by_game.items():
            if not ok:
                print(f"\nWRONG: {rule}, game {game + 1}: {detail}")
    print(f"\n{sum(len(by_game) for by_game in results.values()) - wrong} of "
          f"{sum(len(by_game) for by_game in results.values())} checks as expected")
    return wrong


def main():
    lab = Lab()
    for game in GAMES:
        start = choose_game(lab, game)
        check_walls(lab, game)
        check_key(lab, game, start)
        check_monsters(lab, game, start)
        check_start_places(lab, game, start)
        check_door_sound(lab, game, start)
        check_lightning(lab, game, start)
        check_doors(lab, game, start)
        check_stairs(lab, game, start)
        print(f"game {game + 1} done", flush=True)
    sys.exit(1 if print_table() else 0)


if __name__ == "__main__":
    main()
