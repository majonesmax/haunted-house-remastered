"""What Haunted House keeps in its ROM, read from the user's own copy: the mansion's plan, its doors and
stairs, the sprites, the colours and the game's tuning tables.

Every table is listed in TABLES with its address and what we know about it. Addresses are in the 2600's
cartridge space ($F000-$FFFF); the 4K ROM file starts at $F000. Nothing here is copied into this repository:
the bytes are always read from the ROM file at run time.

The mansion, as the tables describe it (see docs/rom-elements.md for the evidence):
- 4 floors with the same wall plan (FLOOR_WALLS). Each floor is one tall map, 6 rooms in 2 columns x 3 rows.
  Rooms: even = right column, odd = left; 0/1 bottom row, 2/3 middle, 4/5 top. Up is +y.
- 7 doors between rooms (DOOR_IDS). In games 3-9 some are locked, per floor (LOCKED_DOORS).
- Stairs at the outer edge of some rooms (STAIRS_HERE, STAIRS_GO_UP, STAIRS_EDGE). Game 9 has its own
  stairs and locks (the second half of those tables). Room 2 of the
  first floor has the front door, the way out. Floors are 0-3 in RAM and shown as 1-4 on screen.
"""

import os

from shared.types import Point

ROM_START = 0xF000
DEFAULT_ROM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "roms",
                           "haunted_house.a26")

# name -> (address, length, what it is, how sure we are: "live" checked in the running game,
#          "code" read from the code that uses it, "guess")
TABLES = {
    # --- the world ---------------------------------------------------------------------------------
    "FLOOR_WALLS": (0xFFD4, 16, "wall plan, one byte per 16-unit row (y>>4), bit c = column c "
                                "(x 16(c+1)..16(c+2)-1); the same on every floor", "live"),
    "COLUMN_BITS": (0xFE00, 8, "bit mask for each wall-plan column (also used as 'bit n' everywhere)",
                    "code"),
    "DOOR_IDS": (0xFD82, 24, "per room, its [left, right, up, down] neighbour: a door number 0-6, "
                             "$80+room = the room's outer edge (stairs or the front door), $FF = wall",
                  "live"),
    "LOCKED_DOORS": (0xFDD5, 8, "per floor, a bit for each locked door number; [0-3] games 3-8, "
                                "[4-7] game 9 (games 1-2 have no locks)", "live"),
    "STAIRS_HERE": (0xFDDD, 8, "per floor, a bit for each room that has stairs; [4-7] game 9", "live"),
    "STAIRS_GO_UP": (0xFDE5, 8, "per floor, a bit for each room whose stairs go up (else down); "
                                "[4-7] game 9 (the last byte is shared with the next table)", "live"),
    "STAIRS_EDGE": (0xFD46, 6, "per room, which edge its stairs are on: 0 left, 1 right, 2 top, 3 bottom",
                    "live"),
    "STAIRS_X": (0xFF8C, 6, "per room, the x where its stairs are drawn", "code"),
    "STAIRS_Y": (0xFF88, 4, "per edge, the y where stairs are drawn", "code"),
    "ROOM_BOUNDS": (0xFD7F, 3, "y limits of what's drawn while a match is lit (games 2-9)", "live"),
    "ROOM_STEP": (0xFFD0, 4, "room number change for a door going left, right, up, down", "live"),
    "DIRECTION_BITS": (0xFD06, 4, "direction 0-3 shifted into bits 6-7 of a monster's plan", "live"),
    "DOORWAY_LINES": (0xFC68, 12, "x or y where a doorway starts and ends, per direction", "code"),
    "WAYPOINT_START": (0xFFA6, 4, "first waypoint for each kind of monster plan: centres, doors, stairs",
                       "live"),
    "WAYPOINT_X": (0xFFAA, 19, "monster waypoints, x: 0-5 room centres, 6-12 doors 0-6, 13-18 each room's "
                               "stairs", "live"),
    "WAYPOINT_Y": (0xFFBD, 19, "monster waypoints, y (same order)", "live"),
    # --- the cast ----------------------------------------------------------------------------------
    "ITEM_SPRITES": (0xFE08, 64, "8 rows each: key, scepter, urn pieces 1-3, pieces 1+2, 1+3, 2+3, "
                                 "whole urn", "live"),
    "MONSTER_SPRITES": (0xFE50, 60, "10 rows each, 2 frames each: ghost, bat, tarantula", "code"),
    "STAIRS_SPRITES": (0xFE8C, 68, "17 rows each: the 4 stairs pictures (by edge and up/down)", "code"),
    "LIGHT_SPRITES": (0xFF50, 56, "the match's glow, 28 rows each: big and small (it flickers)", "code"),
    "LIGHT_FLICKER": (0xFF9A, 4, "which glow to show, by frame (low byte of the sprite address)", "code"),
    "DIGITS": (0xFF00, 80, "the numbers 0-9, 8 rows each", "live"),
    "DYING_EYES": (0xFF92, 8, "fake joystick readings that make the eyes roll while you die", "code"),
    "ITEM_COLOURS": (0xF4D6, 5, "colour number for each item", "live"),
    "MONSTER_FRAMES": (0xF5E2, 5, "sprite offset for each monster (which picture it uses)", "code"),
    "COLOURS": (0xFFE4, 24, "the palette: 12 NTSC colours, then the same 12 for the B/W switch", "live"),
    # --- rules and timing ---------------------------------------------------------------------------
    "NEW_GAME": (0xFDF6, 10, "copied to RAM $96-$9F by RESET: lives, carried item, urn shapes...", "live"),
    "MONSTER_SPEED": (0xFA86, 5, "per monster, the frames (bits of CLOCK & 7) it steps on when chasing, "
                                 "games 1-7: ghost 4 in 8, bat 3, tarantulas 2", "live"),
    "MONSTER_SPEED_FAST": (0xFA8B, 5, "the same for games 8-9: ghost and bat 4 in 8, tarantulas 3", "live"),
    "CHASE_OFFSET_X": (0xFDEC, 5, "per monster, subtracted from the player's x to give the point it "
                                  "chases; $FA comes out as 0 (see game.monsters.chase_point)", "live"),
    "CHASE_OFFSET_Y": (0xFDF1, 5, "the same for y; $FE comes out as 0", "live"),
    "DROP_OFFSETS": (0xFD02, 4, "where a dropped item lands relative to the player", "code"),
    "SOUND_LENGTHS": (0xF8A0, 12, "how long each sound effect plays (frames)", "live"),
    "STAIRS_TONES": (0xFFA2, 4, "the notes of the stairs sound", "live"),
    "WIN_TUNE": (0xFF9E, 4, "the notes of the win tune", "live"),
}

ITEM_NAMES = ("master key", "scepter", "urn piece 1", "urn piece 2", "urn piece 3")
MONSTER_NAMES = ("ghost", "bat", "tarantula", "tarantula 2", "tarantula 3")
URN_SHAPES = {2: "piece 1", 3: "piece 2", 4: "piece 3", 5: "pieces 1+2", 6: "pieces 1+3",
              7: "pieces 2+3", 8: "whole urn", 0xFF: "(joined to another piece)"}
DIRECTIONS = ("left", "right", "up", "down")
EDGES = ("left", "right", "top", "bottom")
FLOOR_COUNT, ROOM_COUNT, DOOR_COUNT = 4, 6, 7
FRONT_DOOR_ROOM = 2  # on the first floor; walk out of its right edge with the whole urn to win
GAME_9 = 8           # game numbers are 0-8 in RAM
FLOOR_LEFT, FLOOR_RIGHT, FLOOR_BOTTOM, FLOOR_TOP = 0x04, 0x94, 0x01, 0xFB  # how far the player can go


Exit = tuple[str, int | None]   # a room's way out: ("door", its number), ("edge", None) or ("wall", None)


def load(path: str = DEFAULT_ROM) -> bytes:
    with open(path, "rb") as rom_file:
        rom = rom_file.read()
    if len(rom) != 4096:
        raise ValueError(f"{path} is {len(rom)} bytes; Haunted House is a 4K cartridge")
    return rom


def table(rom: bytes, name: str) -> bytes:
    address, length, _what, _sure = TABLES[name]
    return rom[address - ROM_START: address - ROM_START + length]


def byte_at(rom: bytes, address: int) -> int:
    return rom[address - ROM_START]


# --- walls -------------------------------------------------------------------------------------------
def wall_at(rom: bytes, x: int, y: int) -> bool:
    """Is the point (x, y) inside a wall? The game's own test (its routine at $F2A1), for one point.

    Columns are 16 units wide and start at x=16 (column 0); rows are 16 units tall. Outside columns 0-7
    there is solid wall, except in row 8 - the middle row, where the front door and side stairs are.
    """
    column = ((x & 0xFF) >> 4) - 1 & 0xFF
    row = (y & 0xFF) >> 4
    if column & 0x08:
        return row != 8
    return table(rom, "FLOOR_WALLS")[row] & table(rom, "COLUMN_BITS")[column] != 0


def can_step(rom: bytes, x: int, y: int, direction: str) -> bool:
    """Could the player at (x, y) take one step in direction? The same points the game tests ($F1BF).
    The player's body is 8 wide and 3 tall: x..x+7, y..y+2. At the floor's limits the game stops you
    (stepping off there is the stairs or the front door, handled elsewhere)."""
    at_limit = {"right": x >= FLOOR_RIGHT, "left": x <= FLOOR_LEFT, "up": y >= FLOOR_TOP,
                "down": y <= FLOOR_BOTTOM}
    if at_limit[direction]:
        return False
    probes = {"right": ((x + 8, y + 2), (x + 8, y)), "left": ((x - 1, y + 2), (x - 1, y)),
              "up": ((x + 7, y + 3), (x, y + 3)), "down": ((x + 7, y - 1), (x, y - 1))}
    return not any(wall_at(rom, probe_x, probe_y) for probe_x, probe_y in probes[direction])


# --- rooms, doors and stairs -------------------------------------------------------------------------
def room_centre(rom: bytes, room: int) -> Point:
    return table(rom, "WAYPOINT_X")[room], table(rom, "WAYPOINT_Y")[room]


def room_exits(rom: bytes, room: int) -> dict[str, Exit]:
    """{direction: ("door", number) | ("edge", None) | ("wall", None)} for one room."""
    exits: dict[str, Exit] = {}
    entries = table(rom, "DOOR_IDS")[room * 4: room * 4 + 4]
    for direction, value in zip(DIRECTIONS, entries):
        if value == 0xFF:
            exits[direction] = ("wall", None)
        elif value & 0x80:
            exits[direction] = ("edge", None)
        else:
            exits[direction] = ("door", value)
    return exits


def doors(rom: bytes) -> dict[int, tuple[int, ...]]:
    """{door number: (room, room)}: which two rooms each door joins."""
    joins: dict[int, set[int]] = {}
    for room in range(ROOM_COUNT):
        for _direction, (kind, number) in room_exits(rom, room).items():
            if kind == "door" and number is not None:
                joins.setdefault(number, set()).add(room)
    return {number: tuple(sorted(rooms)) for number, rooms in sorted(joins.items())}


def locked_doors(rom: bytes, floor: int, game: int) -> list[int]:
    """Door numbers locked on this floor in this game (game 0-8). Games 1 and 2 (0, 1) have no locks."""
    if game < 2:
        return []
    index = floor + 4 if game == GAME_9 else floor
    mask = table(rom, "LOCKED_DOORS")[index]
    return [number for number in range(DOOR_COUNT) if mask & 1 << number]


def stairs(rom: bytes, floor: int, game: int) -> dict[int, dict]:
    """{room: dict(goes="up"|"down", edge=..., x=..., y=...)} for the rooms of a floor that have stairs.
    Room 2 of the first floor is the front door, not stairs."""
    index = floor + 4 if game == GAME_9 else floor
    here = byte_at(rom, TABLES["STAIRS_HERE"][0] + index)
    going_up = byte_at(rom, TABLES["STAIRS_GO_UP"][0] + index)
    found: dict[int, dict] = {}
    for room in range(ROOM_COUNT):
        if not here & 1 << room:
            continue
        edge = table(rom, "STAIRS_EDGE")[room]
        found[room] = {"goes": "up" if going_up & 1 << room else "down", "edge": EDGES[edge],
                       "x": table(rom, "STAIRS_X")[room], "y": table(rom, "STAIRS_Y")[edge]}
    return found


# --- pictures ----------------------------------------------------------------------------------------
def sprite_rows(rom: bytes, address: int, height: int) -> list[str]:
    """A sprite as a list of 8-character strings, top row first ('#' = lit). The 2600 draws these
    from the last byte to the first, so the last byte in the ROM is the top row on screen."""
    data = rom[address - ROM_START: address - ROM_START + height]
    return ["".join("#" if byte & 0x80 >> bit else "." for bit in range(8)) for byte in reversed(data)]


def item_sprite_address(shape_or_item: int) -> int:
    """Sprite address for item 0 (key), 1 (scepter), or an urn shape 2-8 (see URN_SHAPES)."""
    return 0xFE08 + shape_or_item * 8


def monster_sprite_addresses(rom: bytes, monster: int) -> tuple[int, int]:
    """The two animation frames of a monster (0 ghost, 1 bat, 2-4 tarantulas)."""
    first = 0xFE50 + table(rom, "MONSTER_FRAMES")[monster]
    return first, first + 10
