"""Run the real game beside game/monsters.py and check the model predicts every monster byte, every frame.

A bot plays: it walks in random directions, lights matches, now and then holds the scepter. Every few hundred
frames a monster is put into the player's room (a poke, made between frames) so that chases, catches and
follows happen often. After each frame the model is given the RAM from before the frame and must produce
exactly the monster bytes the game wrote: floor, x, y, plan and room of all five, the chasing and arrived
masks ($94, $95), the monsters-here count ($83) and the random number generator ($EB, $EC).

Usage: python tools/verify_monsters.py [frames per game]      (exit code 1 on any mismatch)
"""

import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, SELECT, Lab  # noqa: E402

sys.path.insert(0, HERE)
from game import monsters as model  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402
from shared.types import Point  # noqa: E402

# (game, frame, RAM before, RAM after, what the model expected, the addresses it got wrong)
Mismatch = tuple[int, int, bytes, bytes, model.State, list[int]]

GAMES = [0, 2, 5, 7, 8]                  # games 1, 3, 6, 8, 9: each adds a rule
FRAMES_PER_GAME = 6000
SEND_MONSTER_EVERY = 250
CHECKED = list(range(0xA5, 0xAA)) + list(range(0xB0, 0xB5)) + list(range(0xBB, 0xC0)) + \
    list(range(0xC0, 0xCA)) + [0x94, 0x95, M.MONSTERS_HERE, model.RANDOM_LOW, model.RANDOM_HIGH]
DYING, NO_MONSTERS = 0x01, 0x40          # GAME_STATE bits: dying; game over / won / select
STICK = [JOY_LEFT, JOY_RIGHT, JOY_UP, JOY_DOWN, None]


def predict(before: bytes, after: bytes, rom: bytes) -> model.State:
    """The RAM the model expects after one frame, given the RAM before it (and, from `after`, the few
    things the game updates earlier in the frame than the monster code: clock and player position)."""
    state = model.State(before)
    model.next_random(state)                       # stirred once while the frame is set up
    for address in (M.CLOCK, M.POS_X, M.POS_Y):
        state[address] = after[address - 0x80]
    game_state = before[M.GAME_STATE - 0x80]
    if game_state & NO_MONSTERS:
        return state
    if game_state & DYING:
        state[M.DEATH_TIMER] -= 1
        if state[M.DEATH_TIMER] == 0:
            model.scatter(state, rom)
            return state
    model.move_monsters(state, rom)
    apply_follows(state, rom, before, after)
    return state


def apply_follows(state: model.State, rom: bytes, before: bytes, after: bytes) -> None:
    """Games 6-9: monsters follow the player if, later in this frame, the player took stairs or a door."""
    def was(address: int) -> int:
        return before[address - 0x80]

    def now(address: int) -> int:
        return after[address - 0x80]

    if now(M.FLOOR) != was(M.FLOOR):
        model.follow_up_stairs(state, was(M.ROOM), was(0x9B))
    left_doorway = was(0x88) & 0x80 and not now(0x88) & 0x80
    if left_doorway:
        direction = now(0x88) & 3
        went_on = was(0x88) == direction | 0x80
        room = was(M.ROOM) if went_on else was(0x97)  # turning back counts from the room beyond
        model.follow_through_door(state, rom, room, direction)


class Bot:
    """Plays like a restless person: random walks, a match now and then, sometimes the scepter. Every few
    hundred frames it calls a monster over and runs an errand - out through a door or up the stairs - so the
    monster has the chance to follow."""

    def __init__(self, lab: Lab, seed: int, rom: bytes | None = None):
        self.lab = lab
        self.rom = rom if rom is not None else R.load()   # (or a port's own mansion: an R.Floors)
        self.dice = random.Random(seed)
        self.stick: int | None = None
        self.frames_left = 0
        self.errand: list[Point] = []        # waypoints still to reach
        self.errand_frames = 0
        self.summoned = 0

    def before_frame(self, frame: int) -> list[int]:
        lab = self.lab
        if lab.peek(M.GAME_STATE) & NO_MONSTERS:   # game over or won: start again
            lab.reset()
        if lab.peek(M.LIVES) < 3:
            lab.poke(M.LIVES, 9)
        if frame % SEND_MONSTER_EVERY == SEND_MONSTER_EVERY // 2:
            self.send_monster()
            self.start_errand()
        if self.errand:
            return self.walk_errand()
        if frame % 1500 == 0:
            scepter = self.dice.random() < 0.4
            lab.poke(M.CARRIED, model.SCEPTER if scepter else M.NOTHING)
        held: list[int] = []
        if self.frames_left <= 0:
            self.stick = self.dice.choice(STICK)
            self.frames_left = self.dice.randint(10, 90)
        self.frames_left -= 1
        if self.stick is not None:
            held.append(self.stick)
        if self.dice.random() < 0.01:
            held.append(BUTTON)
        return held

    def start_errand(self) -> None:
        """Plan a way out of the room: its centre, then a door or the stairs, then a bit beyond."""
        room, floor = self.lab.peek(M.ROOM), self.lab.peek(M.FLOOR)
        exits: list[list[Point]] = []
        for direction, (kind, number) in R.room_exits(self.rom, room, floor).items():
            if kind == "door" and number is not None:
                beyond = room + R.table(self.rom, "ROOM_STEP")[R.DIRECTIONS.index(direction)]
                exits.append([self.waypoint(6 + number), R.room_centre(self.rom, beyond % 256, floor)])
            elif kind == "edge" and room in R.stairs(self.rom, floor, self.lab.peek(M.GAME_NUMBER)):
                exits.append([self.waypoint(13 + room)])
        self.errand = [R.room_centre(self.rom, room, floor)] + self.dice.choice(exits) if exits else []
        self.errand_frames = 600
        if self.dice.random() < 0.5:  # with the scepter, monsters stay near without catching the player
            self.lab.poke(M.CARRIED, model.SCEPTER)

    def waypoint(self, index: int) -> Point:
        """A waypoint on the player's floor."""
        floor = self.lab.peek(M.FLOOR)
        return R.table(self.rom, "WAYPOINT_X", floor)[index], R.table(self.rom, "WAYPOINT_Y", floor)[index]

    def walk_errand(self) -> list[int]:
        """Push the stick towards the next waypoint (diagonally if need be); give up after a while."""
        self.errand_frames -= 1
        target_x, target_y = self.errand[0]
        x, y = self.lab.peek(M.POS_X), self.lab.peek(M.POS_Y)
        held: list[int] = []
        if abs(x - target_x) > 1:
            held.append(JOY_RIGHT if target_x > x else JOY_LEFT)
        if abs(y - target_y) > 1:
            held.append(JOY_UP if target_y > y else JOY_DOWN)
        stuck_at_edge = not held or x in (R.FLOOR_LEFT, R.FLOOR_RIGHT) or y in (R.FLOOR_BOTTOM, R.FLOOR_TOP)
        if stuck_at_edge and len(self.errand) == 1:
            held = held or [JOY_DOWN if target_y < 0x80 else JOY_UP]
        if not held or self.errand_frames <= 0:
            self.errand.pop(0)
            self.send_monster()  # keep a monster close behind, ready to follow
        if self.errand_frames <= 0:
            self.errand = []
        return held

    def send_monster(self) -> None:
        lab = self.lab
        self.summoned += 1
        monster = self.summoned % (lab.peek(M.LAST_MONSTER) + 1)  # each in turn, so all of them chase
        room = lab.peek(M.ROOM)
        lab.poke(M.MONSTER_FLOOR + monster, lab.peek(M.FLOOR))
        lab.poke(M.MONSTER_ROOM + monster, room)
        lab.poke(M.MONSTER_ROUTE + monster, room)
        centre_x, centre_y = R.room_centre(self.rom, room, lab.peek(M.FLOOR))
        lab.poke(M.MONSTER_X + monster, centre_x)
        lab.poke(M.MONSTER_Y + monster, centre_y)


def choose_game(lab: Lab, game: int) -> None:
    while lab.peek(M.GAME_NUMBER) != game:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()


def check_game(lab: Lab, rom: bytes, game: int, frames: int, mismatches: list[Mismatch],
               events: Counter[str]) -> None:
    choose_game(lab, game)
    bot = Bot(lab, seed=game)
    for frame in range(frames):
        held = bot.before_frame(frame)
        before = lab.snapshot()
        lab.run(1, held)
        after = lab.snapshot()
        expected = predict(before, after, rom)
        count_events(before, after, events, game)
        wrong = [address for address in CHECKED if expected[address] != after[address - 0x80]]
        if wrong:
            mismatches.append((game, frame, before, after, expected, wrong))


def count_events(before: bytes, after: bytes, events: Counter[str], game: int) -> None:
    """Tally what happened, so a clean run shows it covered the interesting cases."""
    for monster in range(5):
        if before[M.MONSTER_FLOOR + monster - 0x80] != after[M.MONSTER_FLOOR + monster - 0x80]:
            events["monster took stairs"] += 1
        if before[M.MONSTER_ROOM + monster - 0x80] != after[M.MONSTER_ROOM + monster - 0x80]:
            events["monster went through a door"] += 1
    took_exit = before[M.FLOOR - 0x80] != after[M.FLOOR - 0x80] or (
        before[0x88 - 0x80] & 0x80 and not after[0x88 - 0x80] & 0x80)
    monster_there = before[M.MONSTERS_HERE - 0x80] > 0
    if took_exit and after[0x94 - 0x80]:
        events[f"game {game + 1}: player left a room, monsters followed"] += 1
    elif took_exit and monster_there:
        events[f"game {game + 1}: player left a room with a monster in it, none followed"] += 1
    if after[M.GAME_STATE - 0x80] == DYING and before[M.GAME_STATE - 0x80] != DYING:
        events["player caught"] += 1
    if before[M.DEATH_TIMER - 0x80] == 1:
        events["monsters scattered after a death"] += 1
    if after[M.MONSTERS_HERE - 0x80]:
        events["frames with a monster in the player's room"] += 1


def report(mismatches: list[Mismatch], events: Counter[str], total: int) -> None:
    for name, count in sorted(events.items()):
        print(f"  {count:6d}  {name}")
    print(f"\n{total - len(mismatches)}/{total} frames predicted exactly")
    by_byte = Counter(address for *_, wrong in mismatches for address in wrong)
    if by_byte:
        counts = [f"${address:02X} x{count}" for address, count in by_byte.most_common()]
        print("wrong bytes:", ", ".join(counts))
    for game, frame, before, after, expected, wrong in mismatches[:6]:
        print(f"\ngame {game + 1}, frame {frame}: state ${before[M.GAME_STATE - 0x80]:02X} "
              f"floor {before[M.FLOOR - 0x80]} room {before[M.ROOM - 0x80]} "
              f"carried ${before[M.CARRIED - 0x80]:02X} clock&7 {after[M.CLOCK - 0x80] & 7}")
        for address in wrong:
            print(f"  ${address:02X} {M.describe(address)[0]:14s} before ${before[address - 0x80]:02X} "
                  f"model ${expected[address]:02X} game ${after[address - 0x80]:02X}")


def main() -> None:
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else FRAMES_PER_GAME
    lab = Lab()
    rom = R.load()
    mismatches: list[Mismatch] = []
    events: Counter[str] = Counter()
    for game in GAMES:
        check_game(lab, rom, game, frames, mismatches, events)
    report(mismatches, events, frames * len(GAMES))
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
