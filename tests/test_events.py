"""The remastered sound effects fire on the right events: music/events.py, checked in the running game.

Each scene plays a moment of the game (set up with the lab's pokes, as the research did), feeding every
frame's state to an EventWatcher, and checks the effects it asks for - and that it doesn't ask for wrong ones.

Usage: python tests/test_events.py        (exit code 1 if a check fails)
"""

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
from game import ram_map as M  # noqa: E402
from game.state import Game  # noqa: E402
from lab import BUTTON, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, LEFT_DIFFICULTY_B, SELECT, Lab  # noqa: E402
from music.events import EventWatcher  # noqa: E402

game = Game()
failures = []
SCEPTER, KEY = 1, 0


def check(claim, passed, detail=""):
    print(f"{'PASS' if passed else 'FAIL'}  {claim}" + (f"   [{detail}]" if detail else ""))
    if not passed:
        failures.append(claim)


class Scene:
    """The lab, with every frame's state fed to an EventWatcher; .heard is every event so far."""

    def __init__(self, lab):
        self.lab, self.watcher, self.heard = lab, EventWatcher(), []
        self.keep = ()

    def frame(self, held=()):
        far = (self.lab.peek(M.FLOOR) + 2) & 3
        for monster in range(5):
            if monster not in self.keep:
                self.lab.poke(M.MONSTER_FLOOR + monster, far)
        self.lab.run(1, held)
        self.heard += self.watcher.update(game.state(self.lab.ram))

    def run(self, frames, held=()):
        for _ in range(frames):
            self.frame(held)

    def walk_until(self, button, test, limit=300):
        for _ in range(limit):
            if test(self.lab):
                return
            self.frame([button])

    def count(self, name):
        return self.heard.count(name)


def new_game(lab, number):
    while lab.peek(M.GAME_NUMBER) != number - 1:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(3)
    scene = Scene(lab)
    scene.run(2)
    scene.heard = []
    return scene


def matches(lab):
    scene = new_game(lab, 1)
    scene.run(2, [BUTTON])
    scene.run(3)
    check("lighting a match: match_strike", scene.count("match_strike") == 1, scene.heard)
    lab.poke(M.MATCH_TIME, 1)
    scene.run(300)  # the first match after RESET has a long first second (docs/screen-and-sound.md)
    check("the match going out: match_out", scene.count("match_out") == 1, scene.heard)


def doors_and_stairs(lab):
    scene = new_game(lab, 1)
    scene.walk_until(JOY_LEFT, lambda l: l.peek(M.POS_X) <= 0x74)
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.ROOM) == 0)
    check("into a doorway (game 1, where the 2600 is silent): door_open", "door_open" in scene.heard)
    check("into the next room: door_close", "door_close" in scene.heard)
    steps = scene.count("footstep")
    check("walking makes footsteps, not too many", 3 <= steps <= 20, f"{steps} footsteps")
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.FLOOR) == 1)
    check("up the stairs: stairs_up", scene.count("stairs_up") == 1, scene.heard[-3:])
    scene.run(20, [JOY_UP])
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.FLOOR) == 0)
    check("down the stairs: stairs_down", scene.count("stairs_down") == 1, scene.heard[-3:])


def walls_and_locks(lab):
    scene = new_game(lab, 1)
    scene.run(90, [JOY_UP])
    check("walking into a wall: bump", "bump" in scene.heard, scene.heard[-4:])
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.POS_Y) <= 0x86)  # back to the front door's level
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.POS_X) >= 0x94)
    scene.run(10, [JOY_RIGHT])
    check("the front door without the urn: locked", "locked" in scene.heard, scene.heard[-4:])
    scene = new_game(lab, 3)
    scene.walk_until(JOY_LEFT, lambda l: l.peek(M.POS_X) <= 0x74)
    scene.run(60, [JOY_DOWN])
    check("a locked door (game 3): locked", "locked" in scene.heard, scene.heard[-4:])


def place_item(lab, item, dx, dy):
    lab.poke(M.ITEM_FLOOR + item, lab.peek(M.FLOOR))
    lab.poke(M.ITEM_X + item, lab.peek(M.POS_X) + dx)
    lab.poke(M.ITEM_Y + item, lab.peek(M.POS_Y) + dy)


def items(lab):
    scene = new_game(lab, 3)
    place_item(lab, KEY, 6, -2)
    scene.run(2, [BUTTON])
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.CARRIED) == KEY, limit=30)
    check("picking up the key: pickup_key", "pickup_key" in scene.heard, scene.heard)
    scene.run(10, [JOY_LEFT])
    scene.run(2, [BUTTON])
    scene.run(5)
    check("putting it down: drop", "drop" in scene.heard, scene.heard)
    scene = new_game(lab, 1)
    lab.poke(M.CARRIED, 2)
    place_item(lab, 3, 6, -2)
    scene.run(2, [BUTTON])
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.URN_SHAPES) == 5, limit=30)
    check("two urn pieces joining: urn_join", scene.count("urn_join") == 1, scene.heard)
    place_item(lab, 4, 6, -2)
    lab.poke(M.MATCH_TIME, 20)
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.URN_SHAPES) == 8, limit=40)
    check("the urn whole: urn_whole", scene.count("urn_whole") == 1, scene.heard)


def put_monster_here(lab, monster):
    lab.poke(M.MONSTER_FLOOR + monster, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + monster, lab.peek(M.ROOM))


def monsters(lab):
    scene = new_game(lab, 1)
    lab.poke(M.CARRIED, SCEPTER)
    scene.run(1)
    scene.heard = []
    scene.keep = (0,)
    put_monster_here(lab, 0)
    scene.run(3)
    check("the ghost coming into the room: monster_ghost", scene.heard == ["monster_ghost"], scene.heard)
    scene = new_game(lab, 1)
    scene.keep = (2,)
    for _ in range(120):
        put_monster_here(lab, 2)
        lab.poke(M.MONSTER_X + 2, lab.peek(M.POS_X))
        lab.poke(M.MONSTER_Y + 2, lab.peek(M.POS_Y))
        scene.frame()
        if lab.peek(M.GAME_STATE) == 1:
            break
    check("caught: caught", "caught" in scene.heard, scene.heard)


def bat_steals(lab):
    scene = new_game(lab, 7)
    lab.poke(M.CARRIED, KEY)
    scene.keep = (1,)
    for _ in range(120):
        put_monster_here(lab, 1)
        lab.poke(M.MONSTER_X + 1, lab.peek(M.POS_X))
        lab.poke(M.MONSTER_Y + 1, lab.peek(M.POS_Y))
        scene.frame()
        if lab.peek(M.GAME_STATE) == 1:
            break
    scene.run(300)
    stolen = lab.peek(M.CARRIED) == M.NOTHING
    check("the bat taking the key makes no 'drop'", stolen and "drop" not in scene.heard, scene.heard)


def lightning(lab):
    scene = new_game(lab, 3)
    lab.run(5, [LEFT_DIFFICULTY_B])
    lab.poke(M.CARRIED, SCEPTER)
    scene.keep = (2,)
    flashes = 0
    for _ in range(600):
        put_monster_here(lab, 2)
        scene.frame()
        flashes += game.state(lab.ram).lightning
    thunders = scene.count("thunder")
    check("lightning brings thunder, but not one per flash", 1 <= thunders < flashes,
          f"{flashes} flash frames, {thunders} thunders")


def title_is_quiet(lab):
    scene = Scene(lab)
    lab.hold(SELECT, frames=2)
    scene.run(120)
    check("nothing on the title screen", scene.heard == [], scene.heard)


def main():
    lab = Lab()
    start = lab.save()
    for test in (matches, doors_and_stairs, walls_and_locks, items, monsters, bat_steals, lightning,
                 title_is_quiet):
        lab.load(start)
        test(lab)
    print(f"\n{'all hold' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
