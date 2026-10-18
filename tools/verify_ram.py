"""Check the RAM map against the running game: each experiment does one thing and checks what changed.

Every byte game/ram_map.py marks "live" is checked here, and so are the ROM tables game/rom.py marks
"live" (the wall plan, the doors, the stairs). Pokes are used to set a scene up quickly (put an item next to
the player, say); what is checked is always what the game itself does next.

Usage: python tools/verify_ram.py        (prints each claim with PASS or FAIL; exit code 1 if any failed)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, SELECT, Lab  # noqa: E402

sys.path.insert(0, HERE)
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402

FRAMES_PER_SECOND = 60
MATCH_SECONDS = 20
# direction -> (joypad button, the bit it sets in $8E)
JOYSTICK = {"right": (JOY_RIGHT, 0x80), "left": (JOY_LEFT, 0x40), "down": (JOY_DOWN, 0x20),
            "up": (JOY_UP, 0x10)}
STEP = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}

results: list[tuple[str, bool, str]] = []   # (claim, held?, detail)


def check(claim: str, passed: object, detail: str = "") -> None:
    results.append((claim, bool(passed), detail))


def signed(byte: int) -> int:
    return byte - 256 if byte >= 0x80 else byte


def room_of(x: int, y: int) -> int:
    """The room a floor position is in: right column even, left odd; rows bottom, middle, top."""
    column = 1 if x < 0x50 else 0
    row = 0 if y < 0x50 else 1 if y < 0xA0 else 2
    return row * 2 + column


def new_game(lab: Lab, game: int = 0) -> bytes:
    """RESET into game number `game` (0-8), stepping SELECT as needed. Returns a save state."""
    while lab.peek(M.GAME_NUMBER) != game:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(2)
    return lab.save()


def light_match(lab: Lab) -> None:
    lab.hold(BUTTON, frames=2)
    lab.run(1)


def walk(lab: Lab, direction: str, frames: int) -> None:
    lab.hold(JOYSTICK[direction][0], frames=frames)


# --- experiments -------------------------------------------------------------------------------------
def starting_values(lab: Lab, rom: bytes) -> None:
    check("RESET: 9 lives", lab.peek(M.LIVES) == 9)
    check("RESET: carrying nothing ($FF)", lab.peek(M.CARRIED) == M.NOTHING)
    check("RESET: floor 0, room 2", (lab.peek(M.FLOOR), lab.peek(M.ROOM)) == (0, 2))
    check("RESET: player at ($80, $86), inside room 2",
          (lab.peek(M.POS_X), lab.peek(M.POS_Y)) == (0x80, 0x86) and room_of(0x80, 0x86) == 2)
    shapes = [lab.peek(M.URN_SHAPES + i) for i in range(3)]
    check("RESET: urn shapes 2, 3, 4 (three single pieces)", shapes == [2, 3, 4], str(shapes))
    check("RESET: playing ($99 = 0), 0 matches used",
          lab.peek(M.GAME_STATE) == 0 and lab.peek(M.MATCHES_USED) == 0)
    check("RESET: not in a doorway ($97 = $FF)", lab.peek(0x97) == 0xFF)
    check("game 1: monsters 0-2 in play ($EA = 2)", lab.peek(M.LAST_MONSTER) == 2)
    table = R.table(rom, "NEW_GAME")
    copied = bytes(lab.peek(0x96 + i) for i in range(10))
    check("ROM NEW_GAME table is what RESET copies to $96-$9F (lives, carried, room, urn shapes)",
          table[0] == copied[0] and table[4] == copied[4] and table[6:10] == copied[6:10], copied.hex(" "))


def clock_and_frame_flag(lab: Lab, _rom: bytes) -> None:
    before_clock, before_flags = lab.peek(M.CLOCK), lab.peek(M.FLAGS)
    lab.run(1)
    check("$89 counts +1 a frame", lab.peek(M.CLOCK) == (before_clock + 1) & 0xFF)
    check("$8A bit 7 flips every frame", (lab.peek(M.FLAGS) ^ before_flags) & 0x80 == 0x80)


def joystick(lab: Lab, _rom: bytes) -> None:
    start = lab.save()
    for direction, (button, bit) in JOYSTICK.items():
        lab.load(start)
        walk(lab, direction, 1)  # the stick is read at the end of a frame and used in the next
        x, y = lab.peek(M.POS_X), lab.peek(M.POS_Y)
        walk(lab, direction, 3)
        dx, dy = STEP[direction]
        moved = (lab.peek(M.POS_X) - x, lab.peek(M.POS_Y) - y)
        check(f"push {direction}: $8E = ${bit:02X}", lab.peek(0x8E) == bit, f"${lab.peek(0x8E):02X}")
        check(f"push {direction}: $E7/$E8 = ({dx}, {dy})",
              (signed(lab.peek(0xE7)), signed(lab.peek(0xE8))) == (dx, dy))
        check(f"push {direction}: position moves one unit a frame", moved == (3 * dx, 3 * dy), str(moved))
    lab.load(start)


def walls(lab: Lab, rom: bytes) -> None:
    """Walk until stopped, from several spots, and compare where the game stops with game.rom.can_step."""
    start = lab.save()
    for direction in ("left", "right", "up", "down"):
        lab.load(start)
        x, y = lab.peek(M.POS_X), lab.peek(M.POS_Y)
        dx, dy = STEP[direction]
        while R.can_step(rom, x, y, direction):
            x, y = x + dx, y + dy
        walk(lab, direction, 200)
        actual = (lab.peek(M.POS_X), lab.peek(M.POS_Y))
        check(f"walls: walking {direction} from the start stops where FLOOR_WALLS says",
              actual == (x, y), f"game ${actual[0]:02X},${actual[1]:02X} model ${x:02X},${y:02X}")
    lab.load(start)


def doorway_and_stairs(lab: Lab, rom: bytes) -> None:
    """Room 2 -> down through door 0 -> room 0 -> its bottom-edge stairs -> floor 1."""
    lab.run_until(lambda lab: lab.peek(M.POS_X) <= 0x74, held=[JOY_LEFT])
    frames = lab.run_until(lambda lab: lab.peek(0x88) & 0x80, held=[JOY_DOWN])
    exits = R.room_exits(rom, 2)
    check("ROM DOOR_IDS: room 2's down exit is a door", exits["down"][0] == "door", str(exits["down"]))
    check("doorway: $88 = $83 (in a doorway, going down)", frames is not None and lab.peek(0x88) == 0x83,
          f"${lab.peek(0x88):02X}")
    check("doorway: $97 = room beyond (2 - 2 = 0)", lab.peek(0x97) == 0)
    lab.run_until(lambda lab: lab.peek(M.ROOM) == 0, held=[JOY_DOWN])
    check("doorway: $9C becomes 0 and $97 goes back to $FF", lab.peek(M.ROOM) == 0 and lab.peek(0x97) == 0xFF)
    walk(lab, "down", 80)
    y = lab.peek(M.POS_Y)
    check("near the bottom of the floor the view stops: $CB = y", y < 0x26 and lab.peek(0xCB) == y,
          f"y ${y:02X} $CB ${lab.peek(0xCB):02X}")
    stairs = R.stairs(rom, 0, 0)
    stairs_byte = lab.peek(0x9B) & 0x0F
    expected = R.EDGES.index(stairs[0]["edge"]) | (4 if stairs[0]["goes"] == "up" else 0)
    check("ROM stairs tables: floor 1 room 0 has up stairs at the bottom; $9B agrees",
          stairs_byte == expected, f"$9B ${stairs_byte:X}, tables ${expected:X}")
    lab.run_until(lambda lab: lab.peek(M.POS_X) <= 0x70, held=[JOY_LEFT])
    lab.run_until(lambda lab: lab.peek(M.FLOOR) != 0, held=[JOY_DOWN], limit=60)
    check("stairs: walking off the bottom edge goes up to floor 1 ($8D = 1)", lab.peek(M.FLOOR) == 1)
    check("stairs: $9B bit 6 set (just used the stairs)", lab.peek(0x9B) & 0x40)
    above = R.stairs(rom, 1, 0)
    check("ROM stairs tables: floor 2 room 0 has the matching down stairs",
          above.get(0, {}).get("goes") == "down" and lab.peek(0x9B) & 0x0F == 3)


def rooms_follow_positions(lab: Lab, _rom: bytes) -> None:
    """Wander for a while; the player's and monsters' room bytes should match their positions."""
    moves = ["left", "up", "right", "down", "up", "up", "left", "down", "right", "up"]
    player_agree = player_total = monster_agree = monster_total = 0
    for move in moves * 6:
        walk(lab, move, 30)
        if lab.peek(0x88) & 0x80 == 0:
            player_total += 1
            player_agree += room_of(lab.peek(M.POS_X), lab.peek(M.POS_Y)) == lab.peek(M.ROOM)
        for monster in range(lab.peek(M.LAST_MONSTER) + 1):
            x, y = lab.peek(M.MONSTER_X + monster), lab.peek(M.MONSTER_Y + monster)
            monster_total += 1
            monster_agree += room_of(x, y) == lab.peek(M.MONSTER_ROOM + monster)
    check("$9C matches the room the player's x, y is in", player_agree == player_total,
          f"{player_agree}/{player_total}")
    check("$C5-$C9 match the room each monster's x, y is in (allowing doorways)",
          monster_agree >= 0.8 * monster_total, f"{monster_agree}/{monster_total}")


def park_monsters(lab: Lab) -> None:
    """Put every monster on a far floor, so none wanders in during a test."""
    far_floor = 3 - lab.peek(M.FLOOR)
    for monster in range(5):
        lab.poke(M.MONSTER_FLOOR + monster, far_floor)


def run_without_monsters(lab: Lab, frames: int) -> None:
    for _ in range(frames):
        park_monsters(lab)
        lab.run(1)


def frames_until_match_time_changes(lab: Lab, limit: int = 300) -> int | None:
    before = lab.peek(M.MATCH_TIME)
    for count in range(1, limit + 1):
        run_without_monsters(lab, 1)
        if lab.peek(M.MATCH_TIME) != before:
            return count
    return None


def match(lab: Lab, _rom: bytes) -> None:
    park_monsters(lab)
    light_match(lab)
    check("button: lights a match ($8A bit 6)", lab.peek(M.FLAGS) & 0x40)
    check("button: $DF = 20 seconds", lab.peek(M.MATCH_TIME) == MATCH_SECONDS)
    check("button: $82 matches used = 1", lab.peek(M.MATCHES_USED) == 1)
    first = frames_until_match_time_changes(lab)
    check("first match after RESET: its first second is ~256 frames ($87 starts at 0 and wraps)",
          first is not None and first > 200, str(first))
    second = frames_until_match_time_changes(lab)
    check("$DF then loses 1 every 60 frames ($87)", second == FRAMES_PER_SECOND, str(second))
    lasted = lab.run_until(lambda lab: lab.peek(M.FLAGS) & 0x40 == 0, limit=FRAMES_PER_SECOND * 20)
    check("the match goes out when $DF reaches 0", lasted is not None and lab.peek(M.MATCH_TIME) == 0,
          f"after {lasted} more frames")
    for _ in range(9):
        light_match(lab)
        lab.poke(M.MATCH_TIME, 1)
        run_without_monsters(lab, FRAMES_PER_SECOND + 2)
    check("$82 counts each match, in BCD (10 matches = $10)", lab.peek(M.MATCHES_USED) == 0x10,
          f"${lab.peek(M.MATCHES_USED):02X}")


def place_item(lab: Lab, item: int, x: int, y: int) -> None:
    lab.poke(M.ITEM_FLOOR + item, lab.peek(M.FLOOR))
    lab.poke(M.ITEM_X + item, x)
    lab.poke(M.ITEM_Y + item, y)


def items(lab: Lab, _rom: bytes) -> None:
    start = lab.save()
    place_item(lab, 1, lab.peek(M.POS_X) + 6, lab.peek(M.POS_Y) - 2)
    light_match(lab)
    lab.run(4)
    check("a lit match shows a nearby item ($86 = 1)", lab.peek(0x86) == 1)
    lab.run_until(lambda lab: lab.peek(M.CARRIED) != M.NOTHING, limit=30, held=[JOY_RIGHT])
    check("touching the scepter picks it up ($9A = 1)", lab.peek(M.CARRIED) == 1)
    walk(lab, "left", 10)
    lab.run(10)
    light_match(lab)
    check("button with a lit match drops it ($9A = $FF)", lab.peek(M.CARRIED) == M.NOTHING)
    across = abs(lab.peek(M.ITEM_X + 1) - lab.peek(M.POS_X))
    up_down = abs(lab.peek(M.ITEM_Y + 1) - lab.peek(M.POS_Y))
    distance = across + up_down
    check("the dropped item lands next to the player ($AC, $B7)", distance <= 24, f"distance {distance}")

    lab.load(start)
    lab.poke(M.CARRIED, 2)
    place_item(lab, 3, lab.peek(M.POS_X) + 6, lab.peek(M.POS_Y) - 2)
    light_match(lab)
    lab.run_until(lambda lab: lab.peek(M.URN_SHAPES) != 2, limit=30, held=[JOY_RIGHT])
    shapes = [lab.peek(M.URN_SHAPES + i) for i in range(3)]
    check("carrying piece 1 and touching piece 2 joins them: shapes 5, $FF, 4", shapes == [5, 0xFF, 4],
          str(shapes))
    lab.load(start)


def winning(lab: Lab, _rom: bytes) -> None:
    start = lab.save()
    lab.poke(M.CARRIED, 2)
    lab.poke(M.URN_SHAPES, 8)
    lab.poke(M.URN_SHAPES + 1, 0xFF)
    lab.poke(M.URN_SHAPES + 2, 0xFF)
    lab.run_until(lambda lab: lab.peek(M.GAME_STATE) != 0, limit=60, held=[JOY_RIGHT])
    check("whole urn out of the front door (floor 0, room 2, right edge): $99 = $44",
          lab.peek(M.GAME_STATE) == 0x44, f"${lab.peek(M.GAME_STATE):02X}")
    check("won: $8A bit 0 set", lab.peek(M.FLAGS) & 0x01)
    lab.load(start)
    lab.run_until(lambda lab: lab.peek(M.POS_X) == 0x94, limit=60, held=[JOY_RIGHT])
    lab.run(10, [JOY_RIGHT])
    check("without the urn the front door doesn't let you out", lab.peek(M.GAME_STATE) == 0)
    lab.load(start)


def put_monster_on_player(lab: Lab, monster: int) -> None:
    lab.poke(M.MONSTER_FLOOR + monster, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + monster, lab.peek(M.ROOM))
    lab.poke(M.MONSTER_X + monster, lab.peek(M.POS_X))
    lab.poke(M.MONSTER_Y + monster, lab.peek(M.POS_Y))


def caught(lab: Lab, monster: int, limit: int = 120) -> bool:
    """Keep a monster on the player until the game says caught (or limit frames pass)."""
    for _ in range(limit):
        put_monster_on_player(lab, monster)
        lab.run(1)
        if lab.peek(M.GAME_STATE) == 0x01:
            return True
    return False


def dying(lab: Lab, _rom: bytes) -> None:
    start = lab.save()
    put_monster_on_player(lab, 2)
    lab.run(2)
    check("a monster in the player's room: $83 >= 1", lab.peek(M.MONSTERS_HERE) >= 1)
    lab.load(start)
    park_monsters(lab)
    light_match(lab)
    lab.poke(M.MONSTER_FLOOR + 2, lab.peek(M.FLOOR))
    lab.poke(M.MONSTER_ROOM + 2, lab.peek(M.ROOM))
    lab.run(3)
    check("a monster coming into the room blows the match out", lab.peek(M.FLAGS) & 0x40 == 0)
    lab.hold(BUTTON, frames=3)
    check("...and no match can be lit while it is there", lab.peek(M.FLAGS) & 0x40 == 0)
    lab.load(start)
    check("a monster touching the player catches it: $99 = 1", caught(lab, 2))
    check("caught: $80 death timer = $FF-ish, $96 lives 8, $CA = the monster",
          lab.peek(M.DEATH_TIMER) > 0xF0 and lab.peek(M.LIVES) == 8 and lab.peek(M.KILLED_BY) == 2,
          f"$80 ${lab.peek(M.DEATH_TIMER):02X} lives {lab.peek(M.LIVES)} $CA {lab.peek(M.KILLED_BY)}")
    frames = lab.run_until(lambda lab: lab.peek(M.GAME_STATE) == 0, limit=300)
    check("after the death timer runs out, play goes on ($99 = 0)", frames is not None and frames > 200,
          str(frames))
    lab.load(start)
    lab.poke(M.CARRIED, 1)
    check("carrying the scepter, a tarantula can't catch you", not caught(lab, 2, limit=60))
    lab.load(start)
    lab.poke(M.LIVES, 1)
    caught(lab, 2)
    lab.run(300)
    check("losing the last life ends the game ($99 = $40)", lab.peek(M.GAME_STATE) == 0x40)
    lab.load(start)


def game_numbers(lab: Lab, _rom: bytes) -> None:
    start = lab.save()
    number = lab.peek(M.GAME_NUMBER)
    lab.hold(SELECT, frames=2)
    check("SELECT: next game number ($CC + 1), game select state ($99 = $40)",
          lab.peek(M.GAME_NUMBER) == number + 1 and lab.peek(M.GAME_STATE) == 0x40)
    new_game(lab, 4)
    check("game 5: five monsters ($EA = 4)", lab.peek(M.LAST_MONSTER) == 4)
    new_game(lab, 6)
    lab.poke(M.CARRIED, 0)
    caught(lab, 1)
    check("game 7: caught by the bat, $CA = 1", lab.peek(M.KILLED_BY) == 1)
    lab.run_until(lambda lab: lab.peek(M.GAME_STATE) == 0, limit=300)
    bat = (lab.peek(M.MONSTER_FLOOR + 1), lab.peek(M.MONSTER_X + 1), lab.peek(M.MONSTER_Y + 1))
    key = (lab.peek(M.ITEM_FLOOR), lab.peek(M.ITEM_X), lab.peek(M.ITEM_Y))
    check("...when play goes on, the bat has taken the key: $9A = $FF, key where the bat is",
          lab.peek(M.CARRIED) == M.NOTHING and key == bat, f"key {key} bat {bat}")
    lab.load(start)


EXPERIMENTS = [starting_values, clock_and_frame_flag, joystick, walls, doorway_and_stairs,
               rooms_follow_positions, match, items, winning, dying, game_numbers]


def main() -> None:
    lab = Lab()
    rom = R.load()
    start = new_game(lab, 0)
    for experiment in EXPERIMENTS:
        lab.load(start)
        try:
            experiment(lab, rom)
        except Exception as problem:  # report and carry on with the next experiment
            check(f"{experiment.__name__} ran", False, repr(problem))
    failures = 0
    for claim, passed, detail in results:
        failures += not passed
        mark = "PASS" if passed else "FAIL"
        print(f"{mark}  {claim}" + (f"   [{detail}]" if detail else ""))
    print(f"\n{len(results) - failures}/{len(results)} claims hold")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
