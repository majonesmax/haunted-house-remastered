"""Run the real game beside game/player.py and check the model predicts the game's whole state, every frame.

A bot plays all nine games: it wanders, runs errands through doors and up and down the stairs, lights
matches and presses the button, and now and then sets up a scene with a poke made between frames - items
put down beside it (to pick up, swap and join), a monster called into the room (to be caught), the whole urn
in its hands at the front door (to win), SELECT and RESET. It lets the lives run out now and then.

After each frame the model is given the RAM from before the frame and the controls held during it, and must
produce exactly the bytes the game wrote: everything from $80 to $CC, the masks' places ($CF, $DE), the
match ($DF), and $E5-$EC. Only the drawing's working bytes are left out.

Usage: python tools/verify_player.py [frames per game] [seed]      (exit code 1 on any mismatch)
"""

import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, RESET, SELECT, Lab  # noqa: E402
from verify_monsters import Bot, choose_game  # noqa: E402

sys.path.insert(0, HERE)
from game import monsters  # noqa: E402
from game import player as P  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402
from game.monsters import State  # noqa: E402

# (game, frame, RAM before, RAM after, what the model expected, the addresses it got wrong)
Mismatch = tuple[int, int, bytes, bytes, State, list[int]]

GAMES = list(range(9))
FRAMES_PER_GAME = 4000
CHECKED = list(range(0x80, 0xCD)) + [P.MASK_X, P.MASK_X_2, M.MATCH_TIME] + list(range(0xE5, 0xED))
STICK_BITS = {JOY_RIGHT: P.STICK_RIGHT, JOY_LEFT: P.STICK_LEFT, JOY_DOWN: P.STICK_DOWN, JOY_UP: P.STICK_UP}
NEAR = 14                   # how far from the player items are put down
SCENE_EVERY = 150
RARE_EVERY = 2000           # the scenes for things that hardly ever happen by chance
WALL_WALK = 50              # frames of walking one way, to end up against a wall
WIN_EVERY = 1700
SELECT_EVERY = 2300
STAIRS_EVERY = 400
LIVES_LEFT_ALONE = 0.25     # the share of each game in which the lives may run out
BUTTON_CHANCE = 0.03
DROP_CHANCE = 0.08
GIVE_ITEM_CHANCE = 0.5      # at each scene, the chance the player is handed an item to drop


def controls_for(held: list[int]) -> P.Controls:
    stick = 0
    for joypad_id, bits in STICK_BITS.items():
        if joypad_id in held:
            stick |= bits
    return P.Controls(stick, BUTTON in held, RESET in held, SELECT in held)


class PlayerBot(Bot):
    """The monster check's bot, with scenes for the player's side of the game."""

    def __init__(self, lab: Lab, seed: int, rom: bytes | None = None):
        super().__init__(lab, seed, rom)
        self.queued: list[list[int]] = []     # inputs already decided, one list per frame
        self.heading_out = False             # walking the whole urn out of the front door
        self.game = lab.peek(M.GAME_NUMBER)  # the game to go back to after a game over or a crash

    def before_frame(self, frame: int) -> list[int]:
        if self.queued:
            return self.queued.pop(0)
        lab = self.lab
        if lab.peek(M.GAME_STATE) == P.SELECTING:
            back_to_game = lab.peek(M.GAME_NUMBER) == self.game
            self.queue([RESET] * 3 + [None] * 3 if back_to_game else [SELECT, None])
            return self.queued.pop(0)
        if lab.peek(M.LIVES) < 3 and frame % 4000 > 4000 * LIVES_LEFT_ALONE:
            lab.poke(M.LIVES, 9)
        if self.heading_out:
            return [JOY_RIGHT]
        self.start_scenes(frame)
        held = self.walk_errand() if self.errand else self.wander()
        if self.dice.random() < self.button_chance():
            held.append(BUTTON)
        return held

    def button_chance(self) -> float:
        """Press more often with a match lit and something in hand: drops, often while walking into a
        wall, are what make the drop search move on."""
        lab = self.lab
        lit = lab.peek(M.FLAGS) & P.MATCH_LIT
        if lit and lab.peek(M.CARRIED) != P.NOTHING:
            return DROP_CHANCE
        return BUTTON_CHANCE

    def queue(self, frames: list[int | None]) -> None:
        self.queued += [[pressed] if pressed is not None else [] for pressed in frames]

    def start_scenes(self, frame: int) -> None:
        if frame % SELECT_EVERY == SELECT_EVERY - 1:
            held_for = self.dice.choice([1, 2, 50, 100])
            self.queue([SELECT] * held_for + [None] * 5 + [RESET] * 2)
        if frame % WIN_EVERY == WIN_EVERY - 1:
            self.go_to_front_door()
        if frame % 250 == 125:
            self.send_monster()
            self.start_errand()
        if frame % STAIRS_EVERY == STAIRS_EVERY // 3:
            self.go_to_stairs()
        if frame % SCENE_EVERY == 0:
            self.put_items_down()
        if frame % SCENE_EVERY == SCENE_EVERY // 2:
            self.drop_by_a_wall()
        if frame % RARE_EVERY == RARE_EVERY // 2:
            self.reset_under_a_monster()
        if frame % RARE_EVERY == RARE_EVERY - 100:
            self.crash_the_game()

    def wander(self) -> list[int]:
        if self.frames_left <= 0:
            self.stick = self.dice.choice([JOY_LEFT, JOY_RIGHT, JOY_UP, JOY_DOWN, None])
            self.frames_left = self.dice.randint(10, 90)
        self.frames_left -= 1
        return [self.stick] if self.stick is not None else []

    def drop_by_a_wall(self) -> None:
        """Walk one way until a wall stops the player, stand still and drop what's carried: the spots
        beside a wall are where the drop search has to move on."""
        lab = self.lab
        if lab.peek(M.CARRIED) == P.NOTHING:
            lab.poke(M.CARRIED, self.dice.choice([P.KEY, P.SCEPTER]))
        direction = self.dice.choice([JOY_LEFT, JOY_RIGHT, JOY_UP, JOY_DOWN])
        walk = [[direction]] * WALL_WALK
        light = [[BUTTON]] if not lab.peek(M.FLAGS) & P.MATCH_LIT else []
        moving_drop = [[direction, BUTTON]] if self.dice.random() < 0.5 else [[], [BUTTON]]
        self.queued += light + [[]] * 8 + walk + moving_drop + [[]] * 6

    def reset_under_a_monster(self) -> None:
        """The ghost standing where a new game puts the player, the player beside it holding the scepter
        (so it can't catch them yet), no match; then RESET. The ghost drawn last is drawn again, unseen, on
        RESET's frame, over the eyes at the start: caught at once."""
        if self.lab.peek(M.GAME_STATE) != P.PLAYING:
            return
        ground = R.ground_floor(self.rom)
        state = self.moved_to(ground, R.FRONT_DOOR_ROOM, (P.START_X - 0x18, P.START_Y))
        state[M.CARRIED] = P.SCEPTER
        P.match_out(state)
        for monster in range(5):
            state[M.MONSTER_FLOOR + monster] = (ground + 2) % R.floor_count(self.rom)
        ghost = monsters.GHOST
        state[M.MONSTER_FLOOR + ghost], state[M.MONSTER_ROOM + ghost] = ground, R.FRONT_DOOR_ROOM
        state[M.MONSTER_X + ghost], state[M.MONSTER_Y + ghost] = P.START_X, P.START_Y
        state[M.MONSTER_ROUTE + ghost] = R.FRONT_DOOR_ROOM
        self.poke_all(state)
        self.queued += [[]] * 4 + [[RESET]] * 2 + [[]] * 4

    def crash_the_game(self) -> None:
        """Games 5-9: dying with a match lit, in a room with stairs, all five monsters on the floor out of
        view. game.player.GameCrashed says the original crashes; it does."""
        lab = self.lab
        floor, game = lab.peek(M.FLOOR), lab.peek(M.GAME_NUMBER)
        rooms = list(R.stairs(self.rom, floor, game))
        if lab.peek(M.GAME_STATE) != P.PLAYING or lab.peek(M.LAST_MONSTER) < 4 or not rooms:
            return
        room = self.dice.choice(rooms)
        state = self.moved_to(floor, room, R.room_centre(self.rom, room, floor))
        state[M.GAME_STATE], state[M.DEATH_TIMER] = P.DYING, 100
        state[M.FLAGS] |= P.MATCH_LIT
        state[M.MATCH_TIME] = P.MATCH_SECONDS
        out_of_view = self.out_of_view_y(state)
        for monster in range(5):
            state[M.MONSTER_FLOOR + monster] = floor
            state[M.MONSTER_Y + monster] = out_of_view
        self.poke_all(state)
        self.errand = []

    def out_of_view_y(self, state: State) -> int:
        """A y on the floor whose line is off the screen, above or below."""
        for line in (0x60, 0xC0, 0xF0):
            y = line - state[P.EYES_LINE] + state[M.POS_Y]
            if R.FLOOR_BOTTOM <= y <= R.FLOOR_TOP:
                return y
        return R.FLOOR_TOP

    def moved_to(self, floor: int, room: int, place: tuple[int, int]) -> State:
        """The RAM with the player put somewhere, the room's bytes worked out as the game would."""
        state = State(self.lab.snapshot())
        state[M.FLOOR], state[M.ROOM] = floor, room
        state[M.POS_X], state[M.POS_Y] = place
        state[P.EYES_LINE] = P.eyes_line(state[M.POS_Y])
        state[P.DOORWAY], state[P.ROOM_BEYOND] = 0, P.NOTHING
        P.room_changed(state, self.rom)
        return state

    def poke_all(self, state: State) -> None:
        for address in range(0x80, 0x100):
            self.lab.poke(address, state[address])

    def put_items_down(self) -> None:
        """Some items beside the player, on its floor; sometimes the urn in pieces again."""
        lab = self.lab
        if self.dice.random() < 0.3:
            for offset, shape in enumerate((2, 3, 4)):
                lab.poke(M.URN_SHAPES + offset, shape)
            if lab.peek(M.CARRIED) >= P.URN:
                lab.poke(M.CARRIED, P.NOTHING)
        if lab.peek(M.CARRIED) == P.NOTHING and self.dice.random() < GIVE_ITEM_CHANCE:
            lab.poke(M.CARRIED, self.dice.choice([P.KEY, P.SCEPTER]))
        for item in self.dice.sample(range(5), self.dice.randint(1, 3)):
            if item == lab.peek(M.CARRIED):
                continue
            x = lab.peek(M.POS_X) + self.dice.randint(-NEAR, NEAR)
            y = lab.peek(M.POS_Y) + self.dice.randint(-NEAR, NEAR)
            lab.poke(M.ITEM_FLOOR + item, lab.peek(M.FLOOR))
            lab.poke(M.ITEM_X + item, max(R.FLOOR_LEFT, min(R.FLOOR_RIGHT, x)))
            lab.poke(M.ITEM_Y + item, max(R.FLOOR_BOTTOM, min(R.FLOOR_TOP, y)))

    def go_to_front_door(self) -> None:
        """The whole urn in hand, at the start position beside the front door; then walk out."""
        if self.lab.peek(M.GAME_STATE) != P.PLAYING:
            return
        state = self.moved_to(R.ground_floor(self.rom), R.FRONT_DOOR_ROOM, (P.START_X, P.START_Y))
        state[M.URN_SHAPES], state[M.URN_SHAPES + 1], state[M.URN_SHAPES + 2] = P.WHOLE_URN, 0xFF, 0xFF
        state[M.CARRIED] = P.URN
        self.poke_all(state)
        self.errand = []
        self.heading_out = True

    def go_to_stairs(self) -> None:
        """Into the centre of a room on this floor that has stairs, with an errand to walk off the edge
        there (a monster may be sent along to follow)."""
        lab = self.lab
        floor, game = lab.peek(M.FLOOR), lab.peek(M.GAME_NUMBER)
        rooms = list(R.stairs(self.rom, floor, game))
        if lab.peek(M.GAME_STATE) != P.PLAYING or not rooms:
            return
        room = self.dice.choice(rooms)
        self.poke_all(self.moved_to(floor, room, R.room_centre(self.rom, room, floor)))
        if self.dice.random() < 0.5:
            self.send_monster()
        self.errand = [self.waypoint(13 + room)]
        self.errand_frames = 300

    def after_frame(self) -> None:
        if self.lab.peek(M.GAME_STATE) != P.PLAYING:
            self.heading_out = False


def predict(before: bytes, held: list[int], rom: bytes) -> State:
    state = State(before)
    P.frame(state, rom, controls_for(held))
    return state


class Tally:
    """What a run found: the frames compared, the ones the model got wrong, and what happened."""

    def __init__(self) -> None:
        self.compared = 0
        self.mismatches: list[Mismatch] = []
        self.events: Counter[str] = Counter()


def check_game(lab: Lab, rom: bytes, game: int, frames: int, seed: int, tally: Tally) -> None:
    choose_game(lab, game)
    bot = PlayerBot(lab, seed=seed * 1000 + game, rom=rom)
    after_crash = False          # the RAM may be left corrupt: don't compare until a new game
    for frame in range(frames):
        held = bot.before_frame(frame)
        before = lab.snapshot()
        lab.run(1, held)
        after = lab.snapshot()
        bot.after_frame()
        after_crash = after_crash and RESET not in held
        if after_crash:
            tally.events["frames after a crash, not compared"] += 1
            continue
        try:
            expected = predict(before, held, rom)
        except P.GameCrashed:
            check_crash(after, tally.events)
            bot.queue([RESET] * 3)
            after_crash = True
            continue
        count_events(before, after, tally.events)
        for switch, name in ((RESET, "frames with RESET held"), (SELECT, "frames with SELECT held")):
            if switch in held:
                tally.events[name] += 1
        if RESET in held and after[M.GAME_STATE - 0x80] == P.DYING:
            tally.events["caught on RESET's frame"] += 1
        tally.compared += 1
        wrong = [address for address in CHECKED if expected[address] != after[address - 0x80]]
        if wrong:
            tally.mismatches.append((game, frame, before, after, expected, wrong))


def check_crash(after: bytes, events: Counter[str]) -> None:
    """The model says the original runs its RAM as code here; what follows isn't modelled, so count how it
    went. (A restart anywhere the model didn't predict one would show up as a mismatch.)"""
    looks_switched_on = after[M.GAME_STATE - 0x80] == P.SELECTING and after[M.GAME_NUMBER - 0x80] == 0
    outcome = "restarted" if looks_switched_on else "carried on"
    events[f"the game crashed where the model said; it {outcome}"] += 1


def count_events(before: bytes, after: bytes, events: Counter[str]) -> None:
    """Tally what happened, so a clean run shows it covered the interesting cases."""
    def was(address: int) -> int:
        return before[address - 0x80]

    def now(address: int) -> int:
        return after[address - 0x80]

    changes = {
        "match lit": now(M.MATCHES_USED) != was(M.MATCHES_USED),
        "match went out": was(M.FLAGS) & P.MATCH_LIT and not now(M.FLAGS) & P.MATCH_LIT,
        "item picked up": now(M.CARRIED) != was(M.CARRIED) and now(M.CARRIED) != P.NOTHING,
        "items swapped": was(M.CARRIED) != P.NOTHING and now(M.CARRIED) not in (P.NOTHING, was(M.CARRIED)),
        "item dropped": was(M.CARRIED) != P.NOTHING and now(M.CARRIED) == P.NOTHING,
        "drop search moved on": now(P.DROP_TRIES) and now(P.DROP_TRIES) < was(P.DROP_TRIES),
        "urn pieces joined": bytes(after[0x1D:0x20]) != bytes(before[0x1D:0x20]),
        "into a doorway": now(P.DOORWAY) & P.IN_DOORWAY and not was(P.DOORWAY) & P.IN_DOORWAY,
        "into a new room": now(M.ROOM) != was(M.ROOM),
        "stopped by a locked door": now(P.BLOCKED) != 0,
        "took the stairs": now(M.FLOOR) != was(M.FLOOR) and was(M.GAME_STATE) == P.PLAYING,
        "caught": now(M.GAME_STATE) == P.DYING and was(M.GAME_STATE) != P.DYING,
        "game over": now(M.GAME_STATE) == P.SELECTING and was(M.GAME_STATE) == P.DYING,
        "won": now(M.GAME_STATE) == P.WON and was(M.GAME_STATE) != P.WON,
        "game number changed": now(M.GAME_NUMBER) != was(M.GAME_NUMBER),
        "bat took the item": was(M.DEATH_TIMER) == 1 and was(M.KILLED_BY) == P.BAT and was(M.CARRIED) != 0xFF,
    }
    for name, happened in changes.items():
        if happened:
            events[name] += 1


def report(tally: Tally) -> None:
    mismatches = tally.mismatches
    for name, count in sorted(tally.events.items()):
        print(f"  {count:6d}  {name}")
    print(f"\n{tally.compared - len(mismatches)}/{tally.compared} frames predicted exactly")
    by_byte = Counter(address for *_, wrong in mismatches for address in wrong)
    if by_byte:
        counts = [f"${address:02X} x{count}" for address, count in by_byte.most_common()]
        print("wrong bytes:", ", ".join(counts))
    for game, frame, before, after, expected, wrong in mismatches[:8]:
        print(f"\ngame {game + 1}, frame {frame}: state ${before[M.GAME_STATE - 0x80]:02X} "
              f"floor {before[M.FLOOR - 0x80]} room {before[M.ROOM - 0x80]} "
              f"carried ${before[M.CARRIED - 0x80]:02X} flags ${before[M.FLAGS - 0x80]:02X} "
              f"drop {before[P.DROP_TRIES - 0x80]}")
        for address in wrong:
            print(f"  ${address:02X} {M.describe(address)[0]:14s} before ${before[address - 0x80]:02X} "
                  f"model ${expected[address]:02X} game ${after[address - 0x80]:02X}")


def main() -> None:
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else FRAMES_PER_GAME
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    lab = Lab()
    rom = R.load()
    tally = Tally()
    for game in GAMES:
        check_game(lab, rom, game, frames, seed, tally)
    report(tally)
    sys.exit(1 if tally.mismatches else 0)


if __name__ == "__main__":
    main()
