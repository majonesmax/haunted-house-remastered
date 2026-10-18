"""G's hints (game/hints.py): they fit the screen and the font in every game, point the right way, say the
same again until something changes, and send you out of the front door with the whole urn - checked in
the running game, with the pieces put in known places (each new game hides them somewhere different, so
the test places them itself, as the research lab does).

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
URN_PIECES = (2, 3, 4)
SOMEWHERE_ELSE = [(2, 0), (3, 4)]     # the other two pieces, out of the way (floor, room)
WAYS = [   # (what it should say, piece 1's (floor, room), the lines) - you start on floor 0, room 2
    ("a piece in the bottom-left room: down and to the left", (0, 1),
     ["3 PIECES LEFT. THE NEAREST IS", "DOWN AND TO THE LEFT."]),
    ("a piece in the room on the left: to the left", (0, 3),
     ["3 PIECES LEFT. THE NEAREST IS", "TO THE LEFT."]),
    ("a piece in this room: how to take it", (0, 2),
     ["A PIECE IS IN THIS ROOM.", "LIGHT A MATCH - SPACE - AND", "WALK INTO IT."]),
    ("the nearest piece two floors up: up the stairs", (2, 1),
     ["3 PIECES LEFT. THE NEAREST IS", "UP THE STAIRS, 2 FLOORS."]),
]
failures: list[str] = []


def check(claim: str, passed: bool, detail: object = "") -> None:
    print(f"{'PASS' if passed else 'FAIL'}  {claim}" + (f"   [{detail}]" if detail else ""))
    if not passed:
        failures.append(claim)


def start_game(lab: Lab, number: int) -> None:
    while lab.peek(M.GAME_NUMBER) != number - 1:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(30)


def put(lab: Lab, rom: bytes, item: int, floor: int, room: int) -> None:
    """An item in the middle of a room (test setup: the lab writes RAM; the game never does)."""
    x, y = R.room_centre(rom, room)
    lab.poke(M.ITEM_FLOOR + item, floor)
    lab.poke(M.ITEM_X + item, x)
    lab.poke(M.ITEM_Y + item, y)


def hold_whole_urn(lab: Lab) -> None:
    lab.poke(M.CARRIED, 2)
    for offset, shape in enumerate((8, 0xFF, 0xFF)):
        lab.poke(M.URN_SHAPES + offset, shape)


def fits(lines: list[str]) -> list[str]:
    too_long = [line for line in lines if len(line) > SCREEN_CHARACTERS]
    unknown = sorted({letter for line in lines for letter in line if letter not in GLYPHS})
    return too_long + unknown


def check_every_game(lab: Lab, game: Game) -> None:
    for number in range(1, 10):
        start_game(lab, number)
        problems = fits(hints.hint(game.state(lab.ram), game.rom))
        check(f"game {number}: the hint fits the screen and the font", not problems, ", ".join(problems))
    problems = fits(hints.WHOLE_URN_NOTE)
    check("the whole-urn note fits the screen and the font", not problems, ", ".join(problems))


def check_ways(lab: Lab, game: Game) -> None:
    start_game(lab, 1)
    for claim, first, expected in WAYS:
        for piece, (floor, room) in zip(URN_PIECES, [first] + SOMEWHERE_ELSE):
            put(lab, game.rom, piece, floor, room)
        said = hints.hint(game.state(lab.ram), game.rom)
        check(claim, said == expected, " / ".join(said))
        again = hints.hint(game.state(lab.ram), game.rom)
        check(f"{claim} - and the same again", again == said)


def check_get_out(lab: Lab, game: Game) -> None:
    start_game(lab, 1)
    before = game.state(lab.ram)
    hold_whole_urn(lab)
    after = game.state(lab.ram)
    check("the note comes when the urn becomes whole", hints.urn_just_whole(before, after))
    said = hints.hint(after, game.rom)
    check("whole urn, in the front door's room: out of its right-hand edge",
          said[0] == "YOU HAVE THE URN! GET OUT NOW!" and "RIGHT-HAND EDGE." in said, " / ".join(said))
    lab.poke(M.FLOOR, 2)
    said = hints.hint(game.state(lab.ram), game.rom)
    down = said[-1] == "DOWN THE STAIRS, 2 FLOORS."
    check("whole urn, two floors up: down the stairs", down, " / ".join(said))


def check_swap(lab: Lab, game: Game) -> None:
    """Taking the scepter while holding a piece says the piece was put down (the game swaps them)."""
    start_game(lab, 1)
    lab.poke(M.CARRIED, 2)
    before = game.state(lab.ram)
    lab.poke(M.CARRIED, 1)
    said = hints.swap_note(before, game.state(lab.ram)) or []
    expected = ["YOU PUT DOWN THE PIECE", "TO TAKE THE SCEPTER.", "YOU HOLD ONE THING AT A TIME."]
    check("taking the scepter while holding a piece: it says the piece was put down", said == expected,
          " / ".join(said))
    problems = fits(said)
    check("the swap note fits the screen and the font", not problems, ", ".join(problems))
    same = game.state(lab.ram)
    check("no note when nothing changed hands", hints.swap_note(same, same) is None)


def main() -> int:
    lab, game = Lab(), Game()
    check_every_game(lab, game)
    check_ways(lab, game)
    check_get_out(lab, game)
    check_swap(lab, game)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
