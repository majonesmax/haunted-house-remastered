"""One whole frame of Haunted House, rewritten in Python, in the game's own order: the switches, the player,
the match, what's drawn, touching, the items and the urn, doors and stairs, dying and winning. The monsters
(game/monsters.py) and the sound (game/sounds.py) have models of their own, and this one calls them where
the game does.

tools/verify_player.py runs the real game beside it and checks that, frame after frame, it predicts every
byte of the game's state. docs/spec.md describes the same rules in plain English; each function names the
routine it follows.

The one thing the 2600 doesn't do in code is touching: its hardware notes where two things overlap as the
picture is drawn. draw() works that out from the pictures and the positions, line by line, the way the
game's drawing loop puts them on the screen.
"""

from typing import NamedTuple

from game import monsters
from game import ram_map as M
from game import rom as R
from game import sounds
from game.monsters import State, bit

# --- the bytes this model uses beyond ram_map's names -------------------------------------------------
DROP_TRIES, COLOUR_CYCLE, MONSTER_SHOWN, ITEM_SHOWN = 0x81, 0x84, 0x85, 0x86
SECOND_COUNTER, DOORWAY, ROOM_TOP, ROOM_BOTTOM = 0x87, 0x88, 0x8B, 0x8C
JOYSTICK, BLOCKED, FOLLOWING, ROOM_BEYOND, STAIRS = 0x8E, 0x91, 0x94, 0x97, 0x9B
EYES_LINE, MASK_X, MASK_X_2 = 0xCB, 0xCF, 0xDE
# where this frame's sprite is drawn - working bytes, but the drop and RESET's frame use what's left in them
SPRITE_X, SPRITE_LINE, SPRITE_POINTER, SPRITE_HEIGHT = 0xDC, 0xEF, 0xE1, 0xED
SELECT_DELAY, BUTTON_HISTORY, STEP_X, STEP_Y, DROPPED = 0xE5, 0xE6, 0xE7, 0xE8, 0xE9

# --- the stick, as $8E holds it (1 = pushed) ----------------------------------------------------------
STICK_RIGHT, STICK_LEFT, STICK_DOWN, STICK_UP = 0x80, 0x40, 0x20, 0x10

# --- values the game gives its bytes ------------------------------------------------------------------
PLAYING, DYING, JUST_RESET, SELECTING, WON = 0x00, 0x01, 0x02, 0x40, 0x44
NO_PLAY = 0x43            # $99 bits that stop the player moving: dying, just reset, select/game over
NO_LOGIC = 0x40           # $99 bit that stops everything after the picture
WON_BIT = 0x04
MATCH_LIT, MONSTER_TURN, WON_FLAG = 0x40, 0x80, 0x01
KEEP_ON_MATCH_OUT = 0x07  # a match going out keeps only bits 0-2 of $8A
NO_STAIRS, AT_EDGE, JUST_USED_STAIRS, GOES_UP = 0x0F, 0x80, 0x40, 0x04
IN_DOORWAY = 0x80
NOTHING = 0xFF
KEY, SCEPTER, URN = 0, 1, 2
WHOLE_URN, JOINED = 8, 0xFF
BAT = 1
FRONT_DOOR_FLOOR = 0
MATCH_SECONDS = 20
FRAMES_PER_SECOND = 60
SELECT_REPEAT = 45        # frames between game numbers while SELECT is held
GAME_COUNT = 9
ATTRACT = 0x10            # $84 bit: the colours drift (game over and select)
PRESSED = 0x7F            # $E6 for a press: pressed now, up for the 7 frames before
DROP_SEARCH = 5
ITEM_REACH = 0x11         # items show while their light distance is under this
VIEW_LINES = 0x50         # the view is 80 lines; a sprite starting below it may still show...
LAST_LINE_BELOW = 0xF9    # ...if it starts no lower than this (its top rows reach into the view)
TOP_LINE = 79
MIDDLE_ROW = 8
EDGE_STRIP = 4            # pixels at each side drawn as wall in the middle row
SCREEN_WIDTH = 160
MIDDLE_SCREEN_LINE = 0x26  # the eyes' line while the view scrolls
SCROLL_STOPS = 0xD7       # from this y the view stops scrolling at the top...
SCROLL_TOP_OFFSET = 0xAF  # ...and the eyes' line is y minus this
DROP_TOO_HIGH = 0xF4      # a dropped item can't land this high
DROP_TOO_FAR_RIGHT = 0x97
DROP_UP = 0x0A            # the drop offset that points up
GAME_3, FIRST_FAST_GAME, FIRST_THEFT_GAME = 2, 7, 6
FIRST_FIVE_MONSTER_GAME, FIRST_LOCKED_GAME = 4, 2
SPRITE_HEIGHT_ITEM, SPRITE_HEIGHT_MONSTER, SPRITE_HEIGHT_STAIRS = 8, 10, 17
SPRITE_ROW_BYTES = 8
MONSTER_SECOND_FRAME = 10  # a monster's second picture is 10 bytes after its first
GAME_3_KEY = (0, 0x74, 0x84)
START_X, START_Y = 0x80, 0x86
MASK_WITH_LEFT_DOOR, MASK_WITHOUT = (0x47, 0x3F), (0x4F, 0x57)

# --- where the game keeps constants in its code (read from the ROM, like every table) ----------------
EYES_ROW, PUPILS_AHEAD, PUPILS_RIGHT, PUPILS_LEFT = 0xF319, 0xF321, 0xF328, 0xF32D
DOORWAY_DIRECTIONS, DIRECTION_STICK = 0xFC74, 0xFC7A   # DATA0 (6 bytes) and DATA1 (4 bytes)
BLOCK_BITS = 0xFE06       # $91 for a locked door: [across, up/down]
DROP_X, DROP_Y = 0xFD02, 0xFD03
DOORWAY_CROSSINGS = 6


class Controls(NamedTuple):
    stick: int            # pushed directions, as $8E holds them: STICK_RIGHT | STICK_LEFT | ...
    button: bool
    reset: bool
    select: bool


class Sprite(NamedTuple):
    """What the 2600 draws in a frame besides the eyes and the walls: one item, monster or stairs."""
    x: int                # its column ($DC)
    line: int             # the kernel line of its bottom row ($EF)
    address: int          # where its picture is in the ROM, bottom row first ($E1, $E2)
    height: int           # its rows ($ED)
    wide: bool = False    # drawn at double width, each pixel two (the stairs: NUSIZ0 = $35)


class Touches(NamedTuple):
    """The 2600's collision latches after the picture: what this frame's sprite overlapped."""
    eyes: bool            # CXPPMM bit 7
    walls: bool           # CXP0FB bit 7


NO_TOUCHES = Touches(False, False)


# --- one frame ---------------------------------------------------------------------------------------
def frame(state: State, rom: bytes, controls: Controls) -> None:
    """Everything the game does in one frame, in its order ($F016)."""
    state[M.CLOCK] += 1
    switches(state, rom, controls)
    if not state[M.GAME_STATE] & NO_PLAY:
        move(state, rom)
        front_door_and_match(state, rom)
    sprite = choose_sprite(state, rom)
    monsters.next_random(state)
    touches = draw(state, rom, sprite, controls.stick)
    sounds.sound_frame(state, rom, controls.stick != 0)
    if not state[M.GAME_STATE] & NO_LOGIC:
        after_picture(state, rom, controls, touches)


def after_picture(state: State, rom: bytes, controls: Controls, touches: Touches) -> None:
    """The work done below the picture ($F05E)."""
    if death_timer(state, rom):
        touches = NO_TOUCHES              # the collisions were cleared ($F8C9)
    else:
        monsters.move_monsters(state, rom)
    stairs(state, rom, controls, touches)
    button(state, rom, controls, touches)
    touching(state, rom, touches)
    doorways(state, rom)


# --- the console switches ($F079) --------------------------------------------------------------------
def switches(state: State, rom: bytes, controls: Controls) -> None:
    if controls.reset:
        new_game(state, rom)
    elif not controls.select:
        state[SELECT_DELAY] = 1
    else:
        state[SELECT_DELAY] -= 1
        if state[SELECT_DELAY] == 0:
            state[SELECT_DELAY] = SELECT_REPEAT
            state[M.GAME_NUMBER] = (state[M.GAME_NUMBER] + 1) % GAME_COUNT
            select_mode(state)


def new_game(state: State, rom: bytes) -> None:
    """RESET ($F082): done every frame the switch is held."""
    state[monsters.RANDOM_LOW], state[monsters.RANDOM_HIGH] = state[monsters.RANDOM_HIGH], \
        state[monsters.RANDOM_LOW]
    for address in range(0x80, M.LIVES):
        state[address] = 0
    for offset, value in enumerate(R.table(rom, "NEW_GAME")):
        state[M.LIVES + offset] = value
    monsters.scatter(state, rom)
    state[M.MONSTER_FLOOR + monsters.GHOST] = monsters.top_floor(rom)
    for number in range(5):
        state[M.ITEM_FLOOR + number] = state[M.MONSTER_FLOOR + number]
        state[M.ITEM_X + number] = state[M.MONSTER_X + number]
        state[M.ITEM_Y + number] = state[M.MONSTER_Y + number]
    if state[M.GAME_NUMBER] == GAME_3:
        state[M.ITEM_FLOOR], state[M.ITEM_X], state[M.ITEM_Y] = GAME_3_KEY
    room_changed(state, rom)
    five_monsters = state[M.GAME_NUMBER] >= FIRST_FIVE_MONSTER_GAME
    state[M.LAST_MONSTER] = 4 if five_monsters else 2
    state[M.POS_X], state[M.POS_Y] = START_X, START_Y
    state[EYES_LINE] = MIDDLE_SCREEN_LINE


def select_mode(state: State) -> None:
    """Game over and game select look the same ($F141): the match goes out, the colours start to drift."""
    match_out(state)
    flip_turn(state)
    state[M.GAME_STATE] = SELECTING
    state[COLOUR_CYCLE] = ATTRACT
    state[MONSTER_SHOWN] = 0
    state[M.DEATH_TIMER] = 0
    state[M.MONSTERS_HERE] = 0


# --- moving ($F1A5, $F1BF) ---------------------------------------------------------------------------
def move(state: State, rom: bytes) -> None:
    state[STEP_X] = 0
    state[STEP_Y] = 0
    state[STAIRS] &= ~AT_EDGE
    if not state[BLOCKED] & 0x40:
        move_across(state, rom)
    if not state[BLOCKED] & 0x80:
        move_up_or_down(state, rom)
    state[BLOCKED] = 0
    state[EYES_LINE] = eyes_line(state[M.POS_Y])


def move_across(state: State, rom: bytes) -> None:
    stick = state[JOYSTICK]
    x, y = state[M.POS_X], state[M.POS_Y]
    if stick & STICK_LEFT:
        step, limit, probe_x = -1, R.FLOOR_LEFT, x - 1
    elif stick & STICK_RIGHT:
        step, limit, probe_x = 1, R.FLOOR_RIGHT, x + 8
    else:
        return
    state[STEP_X] = step
    if x == limit:
        reach_edge(state, rom)
    elif R.wall_at(rom, probe_x, y + 2, state[M.FLOOR]) or R.wall_at(rom, probe_x, y, state[M.FLOOR]):
        sounds.start_effect(state, rom, sounds.BUMP)
    else:
        state[M.POS_X] = x + step


def move_up_or_down(state: State, rom: bytes) -> None:
    pushed = state[JOYSTICK] & (STICK_UP | STICK_DOWN)
    if not pushed:
        return
    x, y = state[M.POS_X], state[M.POS_Y]
    if pushed == STICK_DOWN:
        step, limit, probe_y = -1, R.FLOOR_BOTTOM, y - 1
    else:
        step, limit, probe_y = 1, R.FLOOR_TOP, y + 3
    state[STEP_Y] = step
    if y == limit:
        reach_edge(state, rom)
    elif R.wall_at(rom, x + 7, probe_y, state[M.FLOOR]) or R.wall_at(rom, x, probe_y, state[M.FLOOR]):
        sounds.start_effect(state, rom, sounds.BUMP)
    else:
        state[M.POS_Y] = y + step


def reach_edge(state: State, rom: bytes) -> None:
    """At the floor's limit: mark it (the stairs or the front door may take it from here); with no stairs
    in the room, it's a bump ($F254)."""
    state[STAIRS] |= AT_EDGE
    if state[STAIRS] == AT_EDGE | NO_STAIRS:
        sounds.start_effect(state, rom, sounds.BUMP)


def eyes_line(y: int) -> int:
    """The kernel line the eyes are drawn on: mid-screen, except near the floor's ends ($F1AD)."""
    if y < MIDDLE_SCREEN_LINE:
        return y
    if y >= SCROLL_STOPS:
        return y - SCROLL_TOP_OFFSET
    return MIDDLE_SCREEN_LINE


# --- the front door and the match ($F155) ------------------------------------------------------------
def front_door_and_match(state: State, rom: bytes) -> None:
    at_front_door = state[STAIRS] & AT_EDGE and state[M.FLOOR] == FRONT_DOOR_FLOOR \
        and state[M.ROOM] == R.FRONT_DOOR_ROOM
    if at_front_door:
        if state[M.CARRIED] == URN and state[M.URN_SHAPES] == WHOLE_URN:
            state[M.CLOCK] = 1
            state[M.FLAGS] = WON_FLAG
            state[M.GAME_STATE] = WON
        else:
            sounds.start_effect(state, rom, sounds.BLOCKED)
    state[SECOND_COUNTER] -= 1
    if state[SECOND_COUNTER] == 0:
        state[SECOND_COUNTER] = FRAMES_PER_SECOND
        state[M.MATCH_TIME] -= 1
    if state[M.FLAGS] & MATCH_LIT and (state[M.MONSTERS_HERE] or state[M.MATCH_TIME] == 0):
        match_out(state)
    flip_turn(state)


def match_out(state: State) -> None:
    state[MONSTER_SHOWN] = 0
    state[M.FLAGS] &= KEEP_ON_MATCH_OUT


def flip_turn(state: State) -> None:
    """Items and monsters take turns to be drawn while a match is lit."""
    state[M.FLAGS] ^= MONSTER_TURN


# --- what's drawn ($F2B7) ----------------------------------------------------------------------------
def choose_sprite(state: State, rom: bytes) -> Sprite | None:
    """The one item, monster or stairs drawn this frame, and the turn bytes ($85, $86) it moves on."""
    mode = state[M.GAME_STATE]
    if mode == JUST_RESET or mode & WON_BIT:
        if mode & WON_BIT and state[M.CLOCK] == 0:
            select_mode(state)
        drift_colours(state)
        return leftover_sprite(state)
    if state[M.DEATH_TIMER]:
        sprite = next_monster(state, rom)
    elif state[DROP_TRIES]:
        sprite = dropped_item(state, rom)
    elif state[M.FLAGS] & MATCH_LIT and not state[M.FLAGS] & MONSTER_TURN:
        sprite = next_item(state, rom)
    else:
        sprite = next_monster(state, rom)
    remember(state, sprite)
    drift_colours(state)
    return sprite


def remember(state: State, sprite: Sprite | None) -> None:
    """The kernel draws from these bytes; nothing found leaves no picture ($F4FE)."""
    if sprite is None:
        state[SPRITE_X], state[SPRITE_HEIGHT] = 0, 0
        return
    state[SPRITE_X], state[SPRITE_LINE], state[SPRITE_HEIGHT] = sprite.x, sprite.line, sprite.height
    state[SPRITE_POINTER], state[SPRITE_POINTER + 1] = sprite.address & 0xFF, sprite.address >> 8


def leftover_sprite(state: State) -> Sprite | None:
    """On RESET's frame and while won the game chooses nothing, and the kernel draws again whatever its
    bytes still hold: last frame's sprite, where it was, in black, and at normal width even if it was the
    stairs. On RESET's frame the eyes have just moved to the start, so an invisible monster left there can
    catch the player at once ($F2D8)."""
    if not state[SPRITE_HEIGHT]:
        return None
    address = state[SPRITE_POINTER + 1] << 8 | state[SPRITE_POINTER]
    return Sprite(state[SPRITE_X], state[SPRITE_LINE], address, state[SPRITE_HEIGHT])


def sprite_rows(rom: bytes, sprite: Sprite) -> bytes:
    """The sprite's picture, bottom row first."""
    start = sprite.address - R.ROM_START
    if start < 0:
        return bytes(sprite.height)
    return bytes(rom[(start + row) % len(rom)] for row in range(sprite.height))


def drift_colours(state: State) -> None:
    """Game over and select: $84 counts every 256 frames, and the colours drift with it ($F3E8)."""
    if not state[COLOUR_CYCLE] & ATTRACT:
        return
    if state[M.CLOCK] == 0:
        state[COLOUR_CYCLE] += 1
    state[COLOUR_CYCLE] |= ATTRACT


def line_of(state: State, y: int) -> int:
    """The kernel line a floor y is drawn on ($F4DB)."""
    return (y + state[EYES_LINE] - state[M.POS_Y]) & 0xFF


def on_screen(line: int) -> bool:
    """Does a sprite whose bottom row is on this line show at all? ($F56D)"""
    return line < VIEW_LINES or line >= LAST_LINE_BELOW


def item_address(state: State, item: int) -> int:
    """Where an item's picture is: $FE00 + shape * 8 + 8, in one byte ($F4E2). The carry out of the
    shifts is added too, which only matters for a joined piece (shape $FF): the drop search draws one
    when it puts down the piece the player held as it joined another, and its picture is at $FE01."""
    shape = item if item < URN else state[M.URN_SHAPES + item - URN]
    shifted = shape << 3
    low = (shifted + SPRITE_ROW_BYTES + (shifted >> 8 & 1)) & 0xFF
    return R.ITEM_SPRITES_PAGE << 8 | low


def item_sprite(state: State, item: int) -> Sprite:
    return Sprite(state[M.ITEM_X + item], line_of(state, state[M.ITEM_Y + item]), item_address(state, item),
                  SPRITE_HEIGHT_ITEM)


def dropped_item(state: State, rom: bytes) -> Sprite:
    """The item being put down, drawn (in black) where the search is trying it ($F2ED, $F526). Its place
    on the screen is the one the search worked out last frame ($DC, $EF), before the player moved."""
    item = state[DROPPED]
    state[M.ITEM_FLOOR + item] = state[M.FLOOR]
    state[ITEM_SHOWN] = item
    return Sprite(state[SPRITE_X], state[SPRITE_LINE], item_address(state, item), SPRITE_HEIGHT_ITEM)


def light_distance(state: State, item: int) -> int:
    """The game's cheap distance: the larger difference plus half the smaller ($F53D)."""
    across = abs(state[M.POS_X] - state[M.ITEM_X + item])
    up_down = abs(state[M.POS_Y] - state[M.ITEM_Y + item])
    if up_down >= across:
        return (up_down + (across >> 1)) & 0xFF
    return (across + (up_down >> 1)) & 0xFF


def item_may_show(state: State, item: int) -> bool:
    if item == state[M.CARRIED]:
        return False
    if item >= URN and state[M.URN_SHAPES + item - URN] & 0x80:
        return False
    if state[M.GAME_NUMBER] < FIRST_LOCKED_GAME and item == KEY:
        return False
    if state[M.ITEM_FLOOR + item] != state[M.FLOOR]:
        return False
    return light_distance(state, item) < ITEM_REACH and on_screen(line_of(state, state[M.ITEM_Y + item]))


def next_item(state: State, rom: bytes) -> Sprite | None:
    """The next item in turn that may show, counting down from the last one shown ($F4F1)."""
    last = state[ITEM_SHOWN]
    item = last
    while True:
        item = item - 1 if item > 0 else 4
        if item_may_show(state, item):
            state[ITEM_SHOWN] = item
            return item_sprite(state, item)
        if item == last:
            return None


class GameCrashed(Exception):
    """The original game goes wrong on this frame, in a way this model doesn't follow.

    Choosing which monster to draw, the game jumps out of a subroutine instead of returning from it each
    time a monster on the player's floor is off the screen ($F5C4 to $F591), leaving two bytes on the
    stack. Five of those reach down to $F2, and the stairs routine then writes 0 into $F1 ($F622), which is
    by then the high byte of its own return address: it returns to $008C and runs the RAM as code. What
    happens next depends on those bytes - usually the game restarts as if just switched on, but if they
    happen to return (the joystick byte $8E is $60, an RTS, while left and down are pushed) it carries on.
    It can happen while the player is dying with a match lit, in a room with stairs, with all five
    monsters on the floor out of view."""


LOST_RETURNS_TO_CRASH = 5   # return addresses left on the stack before $F1 is one of them
ROUNDS_TO_HANG = 3          # times round every slot without finding the one it started from


def monster_rules_allow(state: State, monster: int) -> bool:
    """Is this monster one that may be drawn, wherever it is on the screen? ($F59E)"""
    if state[M.MONSTER_FLOOR + monster] != state[M.FLOOR]:
        return False
    if state[M.GAME_NUMBER] == 0 or state[M.DEATH_TIMER]:
        return True
    in_room = state[M.MONSTER_ROOM + monster] in (state[M.ROOM], state[ROOM_BEYOND])
    return state[M.MONSTERS_HERE] != 0 and in_room


def monster_sprite(state: State, rom: bytes, monster: int) -> Sprite:
    first, second = R.monster_sprite_addresses(rom, monster)
    address = first if state[monsters.RANDOM_LOW] & 0x40 else second
    return Sprite(state[M.MONSTER_X + monster], line_of(state, state[M.MONSTER_Y + monster]), address,
                  SPRITE_HEIGHT_MONSTER)


def stairs_sprite(state: State, rom: bytes) -> Sprite:
    """This room's stairs: the picture by edge and direction, drawn at the edge's line ($F5E7)."""
    here = state[STAIRS] & NO_STAIRS
    picture = (here & 3) ^ 1 if here >= GOES_UP else here
    address = R.TABLES["STAIRS_SPRITES"][0] + picture * SPRITE_HEIGHT_STAIRS
    line = line_of(state, R.table(rom, "STAIRS_Y", state[M.FLOOR])[here & 3])
    stairs_x = R.table(rom, "STAIRS_X", state[M.FLOOR])[state[M.ROOM]]
    return Sprite(stairs_x, line, address, SPRITE_HEIGHT_STAIRS, wide=True)


def next_monster(state: State, rom: bytes) -> Sprite | None:
    """The next monster in turn that may show; with a match lit, the stairs take the slot after the last
    monster ($F57D)."""
    last = state[MONSTER_SHOWN]
    slot = last
    lost_returns = 0
    for _ in range(ROUNDS_TO_HANG * (state[M.LAST_MONSTER] + 2)):
        slot -= 1
        if slot < 0:
            slot = state[M.LAST_MONSTER]
            if state[M.FLAGS] & MATCH_LIT:
                slot += 1
                if state[STAIRS] & NO_STAIRS != NO_STAIRS:
                    crash_if(lost_returns)
                    state[MONSTER_SHOWN] = slot
                    return stairs_sprite(state, rom)
                if slot == last:
                    return None
                continue
        if monster_rules_allow(state, slot):
            crash_if(lost_returns)
            if on_screen(line_of(state, state[M.MONSTER_Y + slot])):
                state[MONSTER_SHOWN] = slot
                return monster_sprite(state, rom, slot)
            lost_returns += 1
        if slot == last:
            return None
    raise GameCrashed("the game goes round its monsters for ever: the turn byte is past the last slot")


def crash_if(lost_returns: int) -> None:
    """The next step writes $F1: fatal if a return address is there by now."""
    if lost_returns >= LOST_RETURNS_TO_CRASH:
        raise GameCrashed()


# --- the picture: what touched ($F62C) ---------------------------------------------------------------
def eyes_picture(rom: bytes, stick: int) -> list[int]:
    """The eyes' three rows, bottom first; the pupils look the way the stick is pushed now ($F318)."""
    rows = [R.byte_at(rom, EYES_ROW)] * 3
    pupils = R.byte_at(rom, PUPILS_AHEAD)
    if stick & STICK_RIGHT:
        pupils = R.byte_at(rom, PUPILS_RIGHT)
    if stick & STICK_LEFT:
        pupils = R.byte_at(rom, PUPILS_LEFT)
    row = 1 - (1 if stick & STICK_DOWN else 0) + (1 if stick & STICK_UP else 0)
    rows[row] = pupils
    return rows


def drawn_lines(state: State) -> tuple[int, int]:
    """The first line drawn and the line below the last ($F46D): the whole view, or with a match lit in
    games 2-9, only the player's room."""
    top, below = TOP_LINE, 0
    limited = state[M.FLAGS] & MATCH_LIT and not state[DOORWAY] & IN_DOORWAY and state[M.GAME_NUMBER]
    if limited and state[ROOM_BOTTOM]:
        bottom_line = line_of(state, state[ROOM_BOTTOM])
        if bottom_line < 0x80:
            below = bottom_line
    if limited and state[ROOM_TOP]:
        top_line = line_of(state, state[ROOM_TOP])
        if top_line < VIEW_LINES:
            top = top_line
    return top, below


def columns(picture_row: int, x: int, wide: bool = False) -> int:
    """One row of an 8-pixel picture at column x, as a bit per screen column."""
    scale = 2 if wide else 1
    start = x + 1 if wide else x       # the TIA starts a stretched player a pixel later
    lit = 0
    for pixel in range(8):
        if picture_row & 0x80 >> pixel:
            for copy in range(scale):
                lit |= 1 << (start + pixel * scale + copy) % SCREEN_WIDTH
    return lit


def wall_columns(state: State, rom: bytes, line: int) -> int:
    """The walls drawn on a line, as a bit per screen column (the collision map, plus the middle row's
    edge strips)."""
    y = line - state[EYES_LINE] + state[M.POS_Y]
    if not 0 <= y < 256:
        return 0
    walls = 0
    for column in range(SCREEN_WIDTH):
        at_edge = column < EDGE_STRIP or column >= SCREEN_WIDTH - EDGE_STRIP
        if (at_edge and y >> 4 == MIDDLE_ROW) or R.wall_at(rom, column, y, state[M.FLOOR]):
            walls |= 1 << column
    return walls


def picture_row(rows: bytes | list[int], line: int, bottom_line: int) -> int:
    """The row of a picture drawn on a kernel line, or 0 where it isn't."""
    index = (line - bottom_line) & 0xFF
    return rows[index] if index < len(rows) else 0


def draw(state: State, rom: bytes, sprite: Sprite | None, stick: int) -> Touches:
    """Draw the view's lines as the kernel does, two scanlines a line, and note what overlapped.

    On each line's first scanline the eyes' row is this line's and the sprite's is the line above's; on
    the second both are this line's. The first line drawn has no eyes, and the last only its first
    scanline. (On the glow's frames the glow stands in for the eyes; the game ignores what it touches.)
    """
    if sprite is None or not sprite.height:
        return NO_TOUCHES
    rows = sprite_rows(rom, sprite)
    eyes = eyes_picture(rom, stick)
    need_walls = state[DROP_TRIES] != 0
    line, below = drawn_lines(state)
    sprite_now, eyes_now = 0, 0
    touched_eyes = touched_walls = False
    while True:
        walls = wall_columns(state, rom, line) if need_walls else 0
        sprite_columns = columns(sprite_now, sprite.x, sprite.wide)
        touched_eyes |= sprite_columns & columns(eyes_now, state[M.POS_X]) != 0
        touched_walls |= sprite_columns & walls != 0
        sprite_now = picture_row(rows, line, sprite.line)
        line -= 1
        if line == below or line < 0:
            return Touches(touched_eyes, touched_walls)
        sprite_columns = columns(sprite_now, sprite.x, sprite.wide)
        touched_eyes |= sprite_columns & columns(eyes_now, state[M.POS_X]) != 0
        touched_walls |= sprite_columns & walls != 0
        eyes_now = picture_row(eyes, line, state[EYES_LINE])


# --- below the picture: dying ($F8AC) ----------------------------------------------------------------
def death_timer(state: State, rom: bytes) -> bool:
    """Count down a death. True on the frame it ends, when the monsters don't move."""
    state[M.GAME_STATE] &= ~JUST_RESET
    if not state[M.GAME_STATE] & DYING:
        return False
    state[M.DEATH_TIMER] -= 1
    if state[M.DEATH_TIMER]:
        return False
    state[M.GAME_STATE] = PLAYING
    state[sounds.EFFECT] = 0
    if state[M.LIVES] == 0:
        select_mode(state)
    monsters.scatter(state, rom)
    bat_takes_item(state)
    return True


def bat_takes_item(state: State) -> None:
    """Games 7-9: the bat leaves what it took where it is."""
    carried = state[M.CARRIED]
    if state[M.KILLED_BY] != BAT or state[M.GAME_NUMBER] < FIRST_THEFT_GAME or carried == NOTHING:
        return
    state[M.ITEM_FLOOR + carried] = state[M.MONSTER_FLOOR + BAT]
    state[M.ITEM_X + carried] = state[M.MONSTER_X + BAT]
    state[M.ITEM_Y + carried] = state[M.MONSTER_Y + BAT]
    state[M.CARRIED] = NOTHING


# --- stairs ($FB68) ----------------------------------------------------------------------------------
def stairs(state: State, rom: bytes, controls: Controls, touches: Touches) -> None:
    """Take the stairs if the player is at the edge of a room that has them. In games 1-5 the routine that
    sends monsters after the player jumps into the button's code instead of returning, so on that frame
    the button is read twice ($FB2B)."""
    here = state[STAIRS]
    if here & NO_STAIRS == NO_STAIRS:
        return
    if not here & AT_EDGE:
        state[STAIRS] = here & NO_STAIRS
        return
    if here & JUST_USED_STAIRS:
        return
    if state[M.GAME_NUMBER] < monsters.FOLLOW_FROM_GAME:
        button(state, rom, controls, touches)
    else:
        monsters.follow_up_stairs(state, state[M.ROOM], here)
    going_up = here & GOES_UP
    state[M.FLOOR] += 1 if going_up else -1
    sounds.start_effect(state, rom, sounds.STAIRS_UP if going_up else sounds.STAIRS_DOWN)
    room_changed(state, rom)
    state[STAIRS] |= JUST_USED_STAIRS


# --- the button ($FB92) ------------------------------------------------------------------------------
def button(state: State, rom: bytes, controls: Controls, touches: Touches) -> None:
    """Read the stick for next frame; a press lights a match, or with one lit drops what's carried; and
    move the drop search on."""
    state[JOYSTICK] = controls.stick
    if not state[M.MONSTERS_HERE]:
        state[BUTTON_HISTORY] = state[BUTTON_HISTORY] >> 1 | (0 if controls.button else 0x80)
        if state[BUTTON_HISTORY] == PRESSED:
            if not state[M.FLAGS] & MATCH_LIT:
                light_match(state)
                return
            if state[M.CARRIED] != NOTHING:
                sounds.start_effect(state, rom, sounds.DROP)
                start_drop(state, rom)
                state[M.CARRIED] = NOTHING
                return
    if state[DROP_TRIES]:
        if touches.walls:
            next_drop_spot(state, rom)
        else:
            state[DROP_TRIES] = 0


def light_match(state: State) -> None:
    state[M.MATCH_TIME] = MATCH_SECONDS
    state[M.MATCHES_USED] = bcd_plus_one(state[M.MATCHES_USED])
    state[M.FLAGS] |= MATCH_LIT


def bcd_plus_one(number: int) -> int:
    """Two decimal digits in a byte, plus one (the 6502 in decimal mode)."""
    ones, tens = (number & 0x0F) + 1, number >> 4
    if ones > 9:
        ones, tens = ones - 10, tens + 1
    return (tens % 10) << 4 | ones


# --- dropping ($FBE2) --------------------------------------------------------------------------------
def start_drop(state: State, rom: bytes) -> None:
    """Put the carried item down: first behind the player, if they tried to move this frame."""
    state[DROP_TRIES] = DROP_SEARCH
    state[DROPPED] = state[M.CARRIED]
    step_x, step_y = state[STEP_X], state[STEP_Y]
    if step_x | step_y:
        if try_drop_spot(state, rom, (step_y + 1) & 0xFF, (step_x + 2) & 0xFF):
            return
    next_drop_spot(state, rom)


def next_drop_spot(state: State, rom: bytes) -> None:
    """Try the next spots in turn - left, below, right, above - until one is on the floor ($FBFB)."""
    while True:
        state[DROP_TRIES] -= 1
        if state[DROP_TRIES] == 0:
            return
        spot = state[DROP_TRIES] - 1
        if try_drop_spot(state, rom, spot, spot):
            return


def try_drop_spot(state: State, rom: bytes, y_index: int, x_index: int) -> bool:
    """Move the dropped item to an offset from the player; False if that's off the floor ($FC0B). The y
    is written even when the x fails."""
    item = state[DROPPED]
    offset_y = R.byte_at(rom, DROP_Y + y_index)
    if state[M.POS_Y] >= DROP_TOO_HIGH and offset_y == DROP_UP:
        return False
    new_y = offset_y + state[M.POS_Y]
    if new_y & 0xFF >= DROP_TOO_HIGH:
        return False
    state[M.ITEM_Y + item] = new_y
    state[SPRITE_LINE] = line_of(state, state[M.ITEM_Y + item])
    new_x = (R.byte_at(rom, DROP_X + x_index) + state[M.POS_X]) & 0xFF
    if new_x >= DROP_TOO_FAR_RIGHT:
        return False
    state[M.ITEM_X + item] = new_x
    state[SPRITE_X] = new_x
    return True


# --- touching ($FA90) --------------------------------------------------------------------------------
def touching(state: State, rom: bytes, touches: Touches) -> None:
    if state[M.DEATH_TIMER] or not touches.eyes or state[DROP_TRIES]:
        return
    if not state[M.FLAGS] & MATCH_LIT:
        if state[MONSTER_SHOWN] <= state[M.LAST_MONSTER]:
            maybe_caught(state)
    elif not state[M.FLAGS] & MONSTER_TURN:
        pick_up(state, rom)


def maybe_caught(state: State) -> None:
    """The scepter saves the player, except from the ghost in games 8-9 ($FB0C)."""
    monster = state[MONSTER_SHOWN]
    ghost_ignores_scepter = state[M.GAME_NUMBER] >= FIRST_FAST_GAME and monster == monsters.GHOST
    if state[M.CARRIED] == SCEPTER and not ghost_ignores_scepter:
        return
    state[M.GAME_STATE] = DYING
    state[M.DEATH_TIMER] = 0xFF
    state[M.LIVES] -= 1
    state[M.KILLED_BY] = monster


def pick_up(state: State, rom: bytes) -> None:
    """Take the item touched; an urn piece touching the carried one joins it; anything else carried is
    put down ($FAAC)."""
    sounds.start_effect(state, rom, sounds.PICK_UP)
    carried, touched = state[M.CARRIED], state[ITEM_SHOWN]
    joins = carried != NOTHING and carried != touched and carried >= URN and touched >= URN
    now_carried = join(state, rom, carried + touched) if joins else touched
    if carried != NOTHING:
        start_drop(state, rom)
    state[M.CARRIED] = now_carried


def join(state: State, rom: bytes, pieces: int) -> int:
    """Two urn pieces join; `pieces` is the sum of their item numbers. Returns the item now carried."""
    sounds.start_effect(state, rom, sounds.JOIN)
    shapes = M.URN_SHAPES
    if (state[shapes + 1] | state[shapes + 2]) & 0x80:
        sounds.start_effect(state, rom, sounds.URN_WHOLE)
        state[shapes] = WHOLE_URN
        state[shapes + 1] = JOINED
        state[shapes + 2] = JOINED
        return URN
    state[shapes + (1 if pieces == 5 else 2)] = JOINED
    holder = 1 if pieces == 7 else 0
    state[shapes + holder] = pieces
    return URN + holder


# --- doors ($FC3C) -----------------------------------------------------------------------------------
def doorways(state: State, rom: bytes) -> None:
    """Test the six crossings in order; the first whose start or end the player is on, pushing that way,
    ends the search."""
    lines = R.table(rom, "DOORWAY_LINES", state[M.FLOOR])
    for crossing in range(DOORWAY_CROSSINGS):
        direction = R.byte_at(rom, DOORWAY_DIRECTIONS + DOORWAY_CROSSINGS - 1 - crossing)
        if not state[JOYSTICK] & R.byte_at(rom, DIRECTION_STICK + direction):
            continue
        across = direction < 2
        where = state[M.POS_X] if across else state[M.POS_Y]
        if where == lines[crossing * 2]:
            enter_doorway(state, rom, direction)
            return
        if where == lines[crossing * 2 + 1]:
            leave_doorway(state, rom, direction)
            return


def door_sound(state: State, rom: bytes, effect: int) -> None:
    """Game 1 has no door sounds ($FCD1)."""
    if state[M.GAME_NUMBER]:
        sounds.start_effect(state, rom, effect)


def enter_doorway(state: State, rom: bytes, direction: int) -> None:
    """($FCA5)"""
    if state[DOORWAY] & IN_DOORWAY:
        return
    if door_shut(state, rom, direction) and state[M.CARRIED] != KEY:
        state[BLOCKED] = R.byte_at(rom, BLOCK_BITS + (direction >> 1))
        door_sound(state, rom, sounds.BLOCKED)
        return
    state[ROOM_BEYOND] = state[M.ROOM] + R.table(rom, "ROOM_STEP")[direction]
    state[DOORWAY] = direction | IN_DOORWAY
    door_sound(state, rom, sounds.DOORWAY)


def door_shut(state: State, rom: bytes, direction: int) -> bool:
    """Is the way out of this room locked (or not a door at all)? ($FDA6)"""
    neighbour = R.table(rom, "DOOR_IDS", state[M.FLOOR])[state[M.ROOM] * 4 + direction]
    if neighbour & 0x80:
        return True
    return monsters.door_locked(state, rom, state[M.FLOOR], neighbour)


def leave_doorway(state: State, rom: bytes, direction: int) -> None:
    """Out of the far side of a doorway: into the next room ($FC7E). Turning back counts from the room
    beyond, so the step lands back where the player came from."""
    if not state[DOORWAY] & IN_DOORWAY:
        return
    if state[DOORWAY] != direction | IN_DOORWAY:
        state[M.ROOM] = state[ROOM_BEYOND]
    monsters.follow_through_door(state, rom, state[M.ROOM], direction)
    state[DOORWAY] = direction
    state[M.ROOM] += R.table(rom, "ROOM_STEP")[direction]
    state[ROOM_BEYOND] = NOTHING
    room_changed(state, rom)
    door_sound(state, rom, sounds.NEW_ROOM)


# --- a room's limits and stairs ($FD0A) --------------------------------------------------------------
def room_bound(state: State, rom: bytes, direction: int) -> int:
    """The y limit through the door this way, or 0 for none ($FD6C). For the doors at the side the game
    reads past the end of its table, but only asks whether the answer is 0, and it never is."""
    neighbour = R.table(rom, "DOOR_IDS", state[M.FLOOR])[state[M.ROOM] * 4 + direction]
    if neighbour & 0x80:
        return 0
    return R.byte_at(rom, R.TABLES["ROOM_BOUNDS"][0] + (neighbour >> 1), state[M.FLOOR])


def room_changed(state: State, rom: bytes) -> None:
    state[ROOM_TOP] = room_bound(state, rom, 2)
    state[ROOM_BOTTOM] = room_bound(state, rom, 3)
    has_left_door = room_bound(state, rom, 0) != 0
    state[MASK_X], state[MASK_X_2] = MASK_WITH_LEFT_DOOR if has_left_door else MASK_WITHOUT
    state[STAIRS] = stairs_here(state, rom)


def stairs_here(state: State, rom: bytes) -> int:
    """$9B for the room: $0F for none, else the edge plus 4 if they go up ($FD4C)."""
    room = state[M.ROOM]
    index = monsters.floor_index(state, rom, state[M.FLOOR])
    if not R.table(rom, "STAIRS_HERE")[index] & bit(room):
        return NO_STAIRS
    going_up = R.table(rom, "STAIRS_GO_UP")[index] & bit(room)
    return (GOES_UP if going_up else 0) | R.table(rom, "STAIRS_EDGE", state[M.FLOOR])[room]
