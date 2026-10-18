"""G's hints (game/hints.py): every line fits the screen and the font, in every game, and they point the
right way - checked in the running game, with the pieces put in known places (each new game hides them
somewhere different, so the test places them itself, as the research lab does).

Usage: python tests/test_hints.py        (exit code 1 if a check fails)
"""

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from lab import SELECT, Lab  # noqa: E402

from game import hints  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402
from game.state import Game  # noqa: E402
from shared.hud import GLYPHS  # noqa: E402

SCREEN_CHARACTERS = 30
LEVELS = 6               # more than there are steps, so every step and the wrap round are seen
failures = []


def check(claim, passed, detail=""):
    print(f"{'PASS' if passed else 'FAIL'}  {claim}" + (f"   [{detail}]" if detail else ""))
    if not passed:
        failures.append(claim)


def start_game(lab, number):
    while lab.peek(M.GAME_NUMBER) != number - 1:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(30)


def all_lines(state, rom):
    return [line for level in range(LEVELS) for line in hints.hint(state, rom, level)]


def main():
    lab, game = Lab(), Game()
    for number in range(1, 10):
        start_game(lab, number)
        lines = all_lines(game.state(lab.ram), game.rom)
        too_long = [line for line in lines if len(line) > SCREEN_CHARACTERS]
        unknown = sorted({letter for line in lines for letter in line if letter not in GLYPHS})
        check(f"game {number}: every line fits on screen", not too_long, ", ".join(too_long))
        check(f"game {number}: every letter is in the font", not unknown, "".join(unknown))
    start_game(lab, 1)
    for claim, places, expected in WAYS:
        for piece, (floor, room) in zip(URN_PIECES, places):
            put(lab, game.rom, piece, floor, room)
        way = hints.hint(game.state(lab.ram), game.rom, 1)
        check(claim, way == ["THE NEAREST PIECE IS", expected], " / ".join(way))
    return 1 if failures else 0


URN_PIECES = (2, 3, 4)
WAYS = [   # (what it should say, each piece's (floor, room), the way) - you start on floor 0, room 2
    ("a piece in the bottom-left room: down and to the left", [(0, 1), (2, 0), (3, 4)],
     "DOWN AND TO THE LEFT."),
    ("a piece in the room on the left: to the left", [(0, 3), (2, 0), (3, 4)], "TO THE LEFT."),
    ("a piece in this room", [(0, 2), (2, 0), (3, 4)], "IN THIS ROOM - LIGHT A MATCH."),
    ("all pieces two floors up: up the stairs", [(2, 1), (2, 0), (3, 4)], "UP THE STAIRS, 2 FLOORS."),
]


def put(lab, rom, item, floor, room):
    """An item in the middle of a room (test setup: the lab writes RAM; the game never does)."""
    x, y = R.room_centre(rom, room)
    lab.poke(M.ITEM_FLOOR + item, floor)
    lab.poke(M.ITEM_X + item, x)
    lab.poke(M.ITEM_Y + item, y)


if __name__ == "__main__":
    sys.exit(main())
