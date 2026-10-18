"""How the monsters move: the game's monster code, rewritten in Python so we can check we understand it.

Each function names the routine it follows. tools/verify_monsters.py runs the real game beside this model and
checks that, frame after frame, the model predicts exactly the monster bytes the game produces.

The rules, in short (docs/monsters.md has the long version):

- Monsters walk between waypoints (ROM WAYPOINT_X/Y): room centres (0-5), doors (6-12, door n at 6+n)
  and each room's stairs (13-18). They walk in straight lines, a unit in x and y at once, and never test
  walls - the waypoints are placed so the straight lines stay in the open.
- Each monster's plan is one byte (RAM $C0-$C4): direction << 6 | kind << 4 | target, where kind 0 = go
  to the centre of room `target`, 1 = go to door `target`, 2 / 3 = go down / up the stairs of room `target`.
- At a room centre a monster picks a random direction, never the way it came unless there's nothing else:
  a door (locked doors only for the ghost, or anyone in game 9) or stairs. Through a door its room changes;
  up or down the stairs its floor does; then it heads for the centre of the room it's in.
- A monster in the player's room (or the room beyond the doorway the player is in) chases the player
  instead, faster - unless the player holds the scepter (the ghost ignores it in games 8-9).
- From game 6 on, monsters in the player's room follow the player through doors and up or down stairs, at
  chasing speed.
- They move only on some frames, by a bit mask over CLOCK & 7: wandering on 2 frames in 8; chasing at a speed
  per monster (ROM MONSTER_SPEED, faster table in games 8-9).
- On RESET and after every death, all five are scattered to random room centres, never the player's.
"""

from game import ram_map as M
from game import rom as R
from shared.types import Point

GHOST, BAT = 0, 1
WANDER_FRAMES = 0x88        # the frames (of 8) on which a wandering monster takes a step: 3 and 7
KIND_CENTRE, KIND_DOOR, KIND_STAIRS_DOWN, KIND_STAIRS_UP = 0, 1, 2, 3
SCEPTER = 1
FAST_FROM_GAME = 7          # games 8-9 (0-based 7, 8): faster chase table, ghost ignores the scepter
FOLLOW_FROM_GAME = 5        # games 6-9: monsters follow the player through doors and stairs
LOCKS_FROM_GAME = 2         # games 3-9 have locked doors
WALL, EDGE = 0xFF, 0x80
RANDOM_LOW, RANDOM_HIGH = 0xEB, 0xEC


def bit(number: int) -> int:
    return 1 << number


class State:
    """The 128 bytes of RAM as a bytearray, read and written by $80-$FF address."""

    def __init__(self, ram: bytes):
        self.ram: bytearray = bytearray(ram)

    def __getitem__(self, address: int) -> int:
        return self.ram[address - 0x80]

    def __setitem__(self, address: int, value: int) -> None:
        self.ram[address - 0x80] = value & 0xFF


# --- the random number generator ($F4C9) ------------------------------------------------------------
def next_random(state: State) -> int:
    """Stir $EB/$EC (a 16-bit shift register fed by the XOR of two bits); return the new $EB."""
    mixed = state[RANDOM_HIGH] ^ state[RANDOM_LOW]
    carry_in = mixed >> 6 & 1          # ASL ASL leaves bit 6 in the carry
    low, high = state[RANDOM_LOW], state[RANDOM_HIGH]
    state[RANDOM_LOW] = low << 1 | carry_in
    state[RANDOM_HIGH] = high << 1 | low >> 7
    return state[RANDOM_LOW]


# --- one frame of monster movement ($F8EC) -----------------------------------------------------------
def move_monsters(state: State, rom: bytes) -> None:
    """Everything the game does for the monsters in one frame of play (not while the player dies)."""
    phase = state[M.CLOCK] & 7
    wander_step = WANDER_FRAMES & bit(phase)
    state[M.MONSTERS_HERE] = 0
    for monster in range(state[M.LAST_MONSTER], -1, -1):
        target = choose_target(state, rom, monster, phase, wander_step)
        if target is not None:
            step_towards(state, monster, target)
    handle_one_arrival(state, rom)


def in_players_room(state: State, monster: int) -> bool:
    if state[M.MONSTER_FLOOR + monster] != state[M.FLOOR]:
        return False
    return state[M.MONSTER_ROOM + monster] in (state[M.ROOM], state[0x97])


def ignores_scepter(state: State, monster: int) -> bool:
    return monster == GHOST and state[M.GAME_NUMBER] >= FAST_FROM_GAME


def choose_target(state: State, rom: bytes, monster: int, phase: int, wander_step: int) -> Point | None:
    """Where the monster steps towards this frame, or None if it stands still."""
    if in_players_room(state, monster):
        state[M.MONSTERS_HERE] += 1
        dying = state[M.DEATH_TIMER] != 0
        scepter = state[M.CARRIED] == SCEPTER and not ignores_scepter(state, monster)
        if not dying and not scepter:
            if not chase_step(state, rom, monster, phase):
                return None
            return chase_point(state, rom, monster)
        moving = wander_step
    elif state[0x94] & bit(monster):
        moving = chase_step(state, rom, monster, phase)
    else:
        moving = wander_step
    if not moving:
        return None
    return route_point(state, rom, monster)


def chase_step(state: State, rom: bytes, monster: int, phase: int) -> bool:
    """Does a chasing monster step on this frame? ($FA6F)"""
    speeds = "MONSTER_SPEED_FAST" if state[M.GAME_NUMBER] >= FAST_FROM_GAME else "MONSTER_SPEED"
    return R.table(rom, speeds)[monster] & bit(phase) != 0


def chase_point(state: State, rom: bytes, monster: int) -> Point:
    """The point near the player a chasing monster heads for. The offsets look meant to be signed (-6, -2,
    +6), but the game subtracts them as plain bytes and falls back to the player's own x or y whenever
    that borrows - so $FA and $FE always come out as 0."""
    x = state[M.POS_X] - R.table(rom, "CHASE_OFFSET_X")[monster]
    y = state[M.POS_Y] - R.table(rom, "CHASE_OFFSET_Y")[monster]
    if x < 0:
        x = state[M.POS_X]
    if y < 0:
        y = state[M.POS_Y]
    return x, y


def waypoint(rom: bytes, route: int) -> Point:
    kind = (route & 0x3F) >> 4
    index = R.table(rom, "WAYPOINT_START")[kind] + (route & 0x0F)
    return R.table(rom, "WAYPOINT_X")[index], R.table(rom, "WAYPOINT_Y")[index]


def route_point(state: State, rom: bytes, monster: int) -> Point | None:
    """The waypoint of the monster's plan; if it's already there, mark it arrived and stand still."""
    target = waypoint(rom, state[M.MONSTER_ROUTE + monster])
    here = state[M.MONSTER_X + monster], state[M.MONSTER_Y + monster]
    if here == target:
        state[0x95] |= bit(monster)
        return None
    return target


def step_towards(state: State, monster: int, target: Point) -> None:
    """One unit towards the target in x and in y at once ($F983). A step left that would reach x = 0 is
    undone by the code's shape - harmless, as no waypoint is that far left."""
    x, y = state[M.MONSTER_X + monster], state[M.MONSTER_Y + monster]
    target_x, target_y = target
    if x > target_x:
        x -= 1
        if x == 0:
            x += 1
    elif x < target_x:
        x += 1
    if y > target_y:
        y -= 1
    elif y < target_y:
        y += 1
    state[M.MONSTER_X + monster], state[M.MONSTER_Y + monster] = x, y


# --- arriving at a waypoint ($F9A6) ------------------------------------------------------------------
def handle_one_arrival(state: State, rom: bytes) -> None:
    """Only the lowest-numbered arrived monster gets a new plan this frame; the others wait their turn."""
    for monster in range(state[M.LAST_MONSTER] + 1):
        if state[0x95] & bit(monster):
            state[0x95] ^= bit(monster)
            new_plan(state, rom, monster)
            return


def new_plan(state: State, rom: bytes, monster: int) -> None:
    route = state[M.MONSTER_ROUTE + monster]
    kind = (route & 0x30) >> 4
    direction_bits = route & 0xC0
    room = state[M.MONSTER_ROOM + monster]
    if kind == KIND_CENTRE:
        pick_direction(state, rom, monster)
    elif kind == KIND_DOOR:
        step = R.table(rom, "ROOM_STEP")[direction_bits >> 6]
        state[M.MONSTER_ROOM + monster] = room + step
        state[M.MONSTER_ROUTE + monster] = state[M.MONSTER_ROOM + monster] | direction_bits
    else:
        floor_change = 1 if kind == KIND_STAIRS_UP else -1
        state[M.MONSTER_FLOOR + monster] += floor_change
        # the direction is flipped up <-> down (or left <-> right), so the stairs count as "the way it came"
        state[M.MONSTER_ROUTE + monster] = room | direction_bits ^ 0x40


def pick_direction(state: State, rom: bytes, monster: int) -> None:
    """At a room centre: try directions in turn from a random one, skipping the way it came; if none will
    do, go back the way it came ($F9F3)."""
    came_from = state[M.MONSTER_ROUTE + monster] >> 6 ^ 1
    first = state[RANDOM_LOW] & 3
    direction = first
    while True:
        if direction != came_from and try_direction(state, rom, monster, direction):
            return
        direction = (direction + 1) & 3
        if direction == first:
            try_direction(state, rom, monster, came_from)
            return


def floor_index(state: State, floor: int) -> int:
    return floor + 4 if state[M.GAME_NUMBER] == R.GAME_9 else floor


def try_direction(state: State, rom: bytes, monster: int, direction: int) -> bool:
    """Set a plan to leave the room this way, if the monster may; return whether it did ($FA1F)."""
    room = state[M.MONSTER_ROOM + monster]
    floor = state[M.MONSTER_FLOOR + monster]
    neighbour = R.table(rom, "DOOR_IDS")[room * 4 + direction]
    if neighbour == WALL:
        return False
    if neighbour & EDGE:
        index = floor_index(state, floor)
        if not R.table(rom, "STAIRS_HERE")[index] & bit(room):
            return False
        going_up = R.byte_at(rom, R.TABLES["STAIRS_GO_UP"][0] + index) & bit(room)
        kind, target = (KIND_STAIRS_UP if going_up else KIND_STAIRS_DOWN), room
    else:
        if door_locked(state, rom, floor, neighbour) and not may_pass_locks(state, monster):
            return False
        kind, target = KIND_DOOR, neighbour
    state[M.MONSTER_ROUTE + monster] = direction << 6 | kind << 4 | target
    return True


def door_locked(state: State, rom: bytes, floor: int, door: int) -> bool:
    if state[M.GAME_NUMBER] < LOCKS_FROM_GAME:
        return False
    return R.table(rom, "LOCKED_DOORS")[floor_index(state, floor)] & bit(door) != 0


def may_pass_locks(state: State, monster: int) -> bool:
    return monster == GHOST or state[M.GAME_NUMBER] == R.GAME_9


# --- following the player (games 6-9) ----------------------------------------------------------------
def follow_through_door(state: State, rom: bytes, room: int, direction: int) -> None:
    """The player just went through a door out of `room`: monsters there follow ($FCD8). Through a locked
    door only the ghost follows."""
    if state[M.GAME_NUMBER] < FOLLOW_FROM_GAME:
        return
    door = R.table(rom, "DOOR_IDS")[room * 4 + direction]
    plan = direction << 6 | KIND_DOOR << 4 | door
    followers = [GHOST] if door_locked(state, rom, state[M.FLOOR], door) else None
    send_followers(state, room, plan, followers)


def follow_up_stairs(state: State, room: int, stairs_byte: int) -> None:
    """The player just took the stairs out of `room`: monsters there follow ($FB2B). stairs_byte is $9B."""
    if state[M.GAME_NUMBER] < FOLLOW_FROM_GAME:
        return
    edge = stairs_byte & 3
    going_up = stairs_byte >> 2 & 1
    plan = edge << 6 | (KIND_STAIRS_DOWN + going_up) << 4 | room
    send_followers(state, room, plan, None)


def send_followers(state: State, room: int, plan: int, only: list[int] | None) -> None:
    """Give every monster in the player's floor and `room` the plan, and mark them chasing ($FB47)."""
    state[0x94] = 0
    candidates = only if only is not None else range(state[M.LAST_MONSTER], -1, -1)
    for monster in candidates:
        same_floor = state[M.MONSTER_FLOOR + monster] == state[M.FLOOR]
        if same_floor and state[M.MONSTER_ROOM + monster] == room:
            state[M.MONSTER_ROUTE + monster] = plan
            state[0x94] |= bit(monster)


# --- scattering ($F0E7) ------------------------------------------------------------------------------
def scatter(state: State, rom: bytes) -> None:
    """Put all five monsters at random room centres on random floors - never in the player's room."""
    base = next_random(state) & 7
    while base >= R.ROOM_COUNT:
        base = next_random(state) & 7
    for monster in range(4, -1, -1):
        floor = next_random(state) & 3
        state[M.MONSTER_FLOOR + monster] = floor
        room = (monster + base) % R.ROOM_COUNT
        if room == state[M.ROOM] and floor == state[M.FLOOR]:
            room = (5 + base) % R.ROOM_COUNT
        state[M.MONSTER_ROOM + monster] = room
        state[M.MONSTER_ROUTE + monster] = room
        state[M.MONSTER_X + monster], state[M.MONSTER_Y + monster] = R.room_centre(rom, room)


# --- a new game ($F082) ------------------------------------------------------------------------------
GHOST_START_FLOOR = 3        # the ghost always starts on the top floor ($F0A1 forces it after scattering)
GAME_3 = 2
GAME_3_KEY = (0, 0x74, 0x84)  # in game 3 the master key starts beside the player


def new_game(state: State, rom: bytes) -> None:
    """What RESET does to the monsters and items: stir the random numbers by swapping their bytes, scatter
    the monsters (the player is in room 2 of the first floor), send the ghost to the top floor, then put
    each item where the monster with the same number starts."""
    state[RANDOM_LOW], state[RANDOM_HIGH] = state[RANDOM_HIGH], state[RANDOM_LOW]
    state[M.FLOOR], state[M.ROOM] = 0, R.FRONT_DOOR_ROOM
    scatter(state, rom)
    state[M.MONSTER_FLOOR + GHOST] = GHOST_START_FLOOR
    for number in range(5):
        state[M.ITEM_FLOOR + number] = state[M.MONSTER_FLOOR + number]
        state[M.ITEM_X + number] = state[M.MONSTER_X + number]
        state[M.ITEM_Y + number] = state[M.MONSTER_Y + number]
    if state[M.GAME_NUMBER] == GAME_3:
        state[M.ITEM_FLOOR], state[M.ITEM_X], state[M.ITEM_Y] = GAME_3_KEY
