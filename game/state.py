"""The game's state, as the looks see it.

The 2600 keeps the whole game in 128 bytes of RAM (game/ram_map.py). Every frame the app takes a snapshot of
those bytes and wraps it in a GameState: named fields - which floor and room, where the eyes are, what's
carried, every item and monster - so a look never needs to know a RAM address. What may be SEEN of all that
(the dark, the match's reach) is game/visibility.py.

    game = Game()                  # once: reads the ROM's tables and the palette
    state = game.state(core.ram)   # every frame: a snapshot of the RAM, decoded
"""

from collections import namedtuple

from game import palette as P
from game import ram_map as M
from game import rom as R

Item = namedtuple("Item", "number floor x y shape")
Monster = namedtuple("Monster", "number floor room x y heading following")
Stairs = namedtuple("Stairs", "edge going_up x y")

ITEM_KINDS = ("key", "scepter", "urn", "urn", "urn")
MONSTER_KINDS = ("ghost", "bat", "tarantula", "tarantula", "tarantula")
DIRECTIONS = ("left", "right", "up", "down")
LIGHTNING_COLOUR = 1                 # the palette entry the walls flash to
DYING_EYES = 0xFF92                  # fake joystick readings that roll the eyes while you die
NO_STAIRS = 0x0F
MODES = {0x00: "playing", 0x01: "dying", 0x02: "starting", 0x40: "select", 0x44: "won"}


class GameState:
    """One frame of the game. Built by Game.state(ram); the RAM is copied, so it never changes afterwards.

    mode            "playing", "dying", "starting" (the frame after RESET), "select" (game select or game
                    over) or "won"
    game            1-9
    floor           0-3 (shown as 1-4); room 0-5 (even = right column; 0/1 bottom row, 4/5 top)
    room_beyond     while the player stands in a doorway, the room on the other side; else None
    player          (x, y) on the floor: x 4-148 across, y 1-251 up
    view_bottom     the floor y shown on the view's bottom line; the view shows 80 units up from there
    looking         (dx, dy) the eyes look: the joystick (-1, 0, 1 each; up is +1), rolling while dying
    match_lit, match_seconds, matches_used, lives
    carried         the item number carried (0 key, 1 scepter, 2-4 urn pieces), or None
    items           five Items: number, floor, x, y, and shape (urn pieces: 2-4 one piece, 5-7 two joined, 8
                    the whole urn, 0xFF joined into another; the key and scepter: their own number)
    monsters        the Monsters in play: number (0 ghost, 1 bat, 2-4 tarantulas), floor, room, x, y, heading
                    ("left"/"right"/"up"/"down": where it's walking) and following (sent after the player)
    monsters_here   how many monsters are in the player's room (they put the match out)
    stairs          this room's Stairs (edge, going_up, x, y), or None
    room_limits     (bottom y, top y) of what a lit match shows in games 2-9
    lightning       the walls are flashing this frame
    killed_by       the monster that took the last life (a number), while dying
    sound           the sound effect playing (game/sounds.py numbers them), 0 = none
    clock           the game's frame counter, 0-255
    ram             the 128 bytes themselves, indexed from $80 - for the debug view, not for looks
    """

    def __init__(self, ram, rom, palette):
        self.ram = ram
        self.mode = MODES.get(self.byte(M.GAME_STATE), "playing")
        self.game = min(self.byte(M.GAME_NUMBER), 8) + 1
        self.floor = self.byte(M.FLOOR) & 3
        self.room = self.byte(M.ROOM) % R.ROOM_COUNT
        beyond = self.byte(0x97)
        self.room_beyond = beyond if beyond < R.ROOM_COUNT else None
        self.player = (self.byte(M.POS_X), self.byte(M.POS_Y))
        self.view_bottom = self.player[1] - self.byte(0xCB)
        self.clock = self.byte(M.CLOCK)
        self.looking = self.read_looking(rom)
        self.match_lit = bool(self.byte(M.FLAGS) & 0x40)
        self.match_seconds = self.byte(M.MATCH_TIME) if self.match_lit else 0
        self.matches_used = from_bcd(self.byte(M.MATCHES_USED))
        self.lives = self.byte(M.LIVES)
        carried = self.byte(M.CARRIED)
        self.carried = carried if carried < 5 else None
        self.items = [self.read_item(number) for number in range(5)]
        self.monsters = [self.read_monster(number) for number in range(self.byte(M.LAST_MONSTER) + 1)]
        self.monsters_here = self.byte(M.MONSTERS_HERE)
        self.stairs = self.read_stairs(rom)
        self.room_limits = (self.byte(0x8C), self.byte(0x8B) or 0xFF)
        self.lightning = self.byte(0xF5) == palette_entry(rom, LIGHTNING_COLOUR)
        self.killed_by = self.byte(M.KILLED_BY) if self.mode == "dying" else None
        self.sound = self.byte(0x93)

    def byte(self, address):
        return int(self.ram[address - 0x80])

    def read_looking(self, rom):
        """Which way the eyes look: the joystick ($8E), or while dying the game's own fake readings."""
        if self.mode == "dying":
            fake = R.byte_at(rom, DYING_EYES + (self.clock >> 1 & 7))
            pushed = ~fake & 0xF0  # like the joystick port: a 0 bit means pushed
        else:
            pushed = self.byte(0x8E)
        dx = (1 if pushed & 0x80 else 0) - (1 if pushed & 0x40 else 0)
        dy = (1 if pushed & 0x10 else 0) - (1 if pushed & 0x20 else 0)
        return dx, dy

    def read_item(self, number):
        shape = self.byte(M.URN_SHAPES + number - 2) if number >= 2 else number
        return Item(number, self.byte(M.ITEM_FLOOR + number), self.byte(M.ITEM_X + number),
                    self.byte(M.ITEM_Y + number), shape)

    def read_monster(self, number):
        plan = self.byte(M.MONSTER_ROUTE + number)
        following = bool(self.byte(0x94) & 1 << number)
        return Monster(number, self.byte(M.MONSTER_FLOOR + number), self.byte(M.MONSTER_ROOM + number),
                       self.byte(M.MONSTER_X + number), self.byte(M.MONSTER_Y + number),
                       DIRECTIONS[plan >> 6], following)

    def read_stairs(self, rom):
        stairs_byte = self.byte(0x9B) & 0x0F
        if stairs_byte == NO_STAIRS:
            return None
        edge = stairs_byte & 3
        x = R.table(rom, "STAIRS_X")[self.room]
        y = R.table(rom, "STAIRS_Y")[edge]
        return Stairs(R.EDGES[edge], bool(stairs_byte & 4), x, y)

    @property
    def won(self):
        return self.mode == "won"

    @property
    def dark(self):
        """Games 2-9: the walls can't be seen (except by lightning)."""
        return self.game > 1

    def kind(self, thing):
        """"key", "scepter", "urn", "ghost", "bat" or "tarantula"."""
        if isinstance(thing, Item):
            return ITEM_KINDS[thing.number]
        return MONSTER_KINDS[thing.number]


def from_bcd(value):
    return (value >> 4) * 10 + (value & 0x0F)


def palette_entry(rom, index):
    return R.table(rom, "COLOURS")[index]


class Game:
    """What the ROM says - read once: its tables and the 2600 palette."""

    def __init__(self, rom_path=R.DEFAULT_ROM):
        self.rom = R.load(rom_path)
        self.palette = P.load()

    def state(self, ram):
        """A GameState from the 128 RAM bytes (copied - the emulator's RAM is live)."""
        return GameState(bytes(ram), self.rom, self.palette)

    def rgb(self, colour):
        """A 2600 colour byte -> (r, g, b) as the Stella core shows it."""
        return P.rgb(self.palette, colour)
