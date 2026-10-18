"""Monsters face the way they walk: looks/base.py's Facing, checked on made-up walks.

Usage: python tests/test_facing.py        (exit code 1 if a check fails)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.state import Monster  # noqa: E402
from looks.base import FACING_MEMORY, Facing  # noqa: E402
from shared.types import Point  # noqa: E402

failures: list[str] = []


def check(claim: str, passed: bool, detail: object = "") -> None:
    print(f"{'PASS' if passed else 'FAIL'}  {claim}" + (f"   [{detail}]" if detail else ""))
    if not passed:
        failures.append(claim)


def walk(steps: list[tuple[int, int]], heading: str = "left", start: Point = (80, 80),
         floor: int = 0) -> list[str | None]:
    """A monster stepping by each (dx, dy) in turn, one step a frame; returns the facing after each."""
    facing = Facing()
    x, y = start
    seen: list[str | None] = []
    for dx, dy in [(0, 0)] + steps:
        x, y = x + dx, y + dy
        facing.update([Monster(2, floor, 0, x, y, heading, False)])
        seen.append(facing.of(Monster(2, floor, 0, x, y, heading, False)))
    return seen


def main() -> int:
    check("before it moves, a monster faces where its plan heads", walk([], heading="up")[-1] == "up")
    check("walking right faces right", walk([(1, 0)] * 4)[-1] == "right")
    check("walking left faces left", walk([(-1, 0)] * 4, heading="right")[-1] == "left")
    check("walking up the floor (+y) faces up", walk([(0, 1)] * 4)[-1] == "up")
    check("walking down faces down", walk([(0, -1)] * 4)[-1] == "down")
    mostly_right = [(1, 1), (1, 0), (1, 1), (1, 0)]
    check("mostly right, partly up: faces right", walk(mostly_right)[-1] == "right")
    diagonal = walk([(0, 1)] * 3 + [(1, 1)] * (FACING_MEMORY * 2), heading="left")
    check("exactly diagonal keeps a facing it's already going (up)", diagonal[-1] == "up", diagonal[-1])
    standing = walk([(1, 0)] * 4 + [(0, 0)] * (FACING_MEMORY * 2))
    check("standing still keeps its facing", standing[-1] == "right", standing[-1])
    turned = walk([(1, 0)] * FACING_MEMORY + [(-1, 0)] * FACING_MEMORY)
    check("turning round faces the new way once it's walked a while", turned[-1] == "left", turned[-1])
    facing = Facing()
    facing.update([Monster(2, 0, 0, 80, 80, "left", False)])
    facing.update([Monster(2, 0, 0, 81, 80, "left", False)])
    facing.update([Monster(2, 1, 4, 36, 196, "down", False)])  # up the stairs: a new floor, a new place
    after_jump = facing.of(Monster(2, 1, 4, 36, 196, "down", False))
    check("after a jump (stairs, scattering) the old trail is forgotten; it keeps its last facing until it "
          "walks again", after_jump == "right", after_jump)
    print(f"\n{'all hold' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
