"""What a LOOK is: the contract every way of drawing the game implements, and shared machinery for looks
that show the original's view of the floor.

The game runs unmodified in the emulator. Every frame the app hands a look a GameState (game/state.py) and
the look returns a picture. A look never changes the game - it only draws it.

A look is the console: the screen layout, the colour rules, the status line, the title and win screens.
What's drawn comes from a pack (content/): a CAST (who) and a WORLD (where). Any look shows any pack,
adapting its pictures to its own rules (adapt()).

    Look        the contract - what the app needs from any look.
    FloorLook   a Look that shows the original's window onto the floor - 160 x 80 floor units, scrolling
                with the eyes exactly as the game's own camera does - with everything about placing things
                done: the walls from the ROM's wall plan, the world's tiles on them, the cast at the game's
                positions, darkness and the match's light by the original's rules (game/visibility.py).
                A subclass supplies the PLATFORM methods: its colour rule, status line and screens.
"""

from abc import ABC, abstractmethod

import numpy as np

from game import rom as R
from game import visibility as V
from shared.pixelart import blit

SCREEN_W, SCREEN_H = 256, 240
UNIT = 1.5                    # pixels per floor unit, across and down: one 16-unit wall cell = 24 px
VIEW_X, VIEW_Y = 8, 32        # where the view sits on the screen
VIEW_LINES, VIEW_UNITS_ACROSS = 80, 160
VIEW_W, VIEW_H = int(VIEW_UNITS_ACROSS * UNIT), int(VIEW_LINES * UNIT)  # 240 x 120
CELL = 16                     # floor units in a wall cell
CELL_PX = int(CELL * UNIT)    # 24
FLOOR_LINES = 256
FLOOR_PX_H = int(FLOOR_LINES * UNIT)  # 384: the whole floor, top to bottom, as one picture
EDGE_STRIP = 4                # units of wall drawn at each side of the middle row (door frames)
MIDDLE_ROW = 8
HEIGHTS = {"eyes": 3, "item": 8, "monster": 10, "stairs": 17}  # each kind's height on the floor, in lines
LIGHT_EDGE = 1.25             # past the light's reach, up to this, things show dimly (a soft edge)
DIM = 0.45                    # brightness of what's seen but not lit


class Look(ABC):
    """THE LOOK CONTRACT. The app uses a look only through these.

    platform   the look's short id: `play.py --look <platform>`
    name       its label in the window ("NES REMASTER")
    """

    platform = "?"
    name = "?"

    @abstractmethod
    def draw(self, state, frame_no):
        """The screen for this frame: a (240, 256, 3) uint8 RGB array. frame_no counts up once a frame."""


class FloorLook(Look):
    """The original's view of the floor, redrawn. A subclass supplies the PLATFORM methods at the bottom."""

    def __init__(self, pack, rom):
        self.pack, self.rom = pack, rom
        self.scenes = {}       # floor -> its pictures, built once (Scene)
        self.adapted = {}      # (name, frame) -> a cast picture through adapt()

    def draw(self, state, frame_no):
        screen = np.zeros((SCREEN_H, SCREEN_W, 3), np.uint8)
        screen[:] = self.background()
        if state.mode == "select":
            self.draw_title(screen, state, frame_no)
            return screen
        screen[VIEW_Y:VIEW_Y + VIEW_H, VIEW_X:VIEW_X + VIEW_W] = self.view(state, frame_no)
        self.draw_status(screen, state, frame_no)
        if state.won:
            self.draw_win(screen, state, frame_no)
        return screen

    # --- the view ------------------------------------------------------------------------------------
    def view(self, state, frame_no):
        """The 240 x 120 view: the floor around the eyes, lit by the original's rules, and who's there."""
        scene = self.scene(state.floor)
        top = view_top_row(state)
        rows = slice(top, top + VIEW_H)
        picture = self.light(state, scene, rows)
        for name, x, y, height in self.who_is_there(state, frame_no):
            sprite = self.picture(name, frame_no)
            if sprite is not None:
                place(picture, sprite, state, x, y, height)
        return picture

    def light(self, state, scene, rows):
        """Choose, per pixel, how the floor shows: lit, dim or dark (the original's rules)."""
        full, dim, flash, walls = scene.full[rows], scene.dim[rows], scene.flash[rows], scene.walls[rows]
        reach = light_reach_grid(state, rows)
        lit = reach <= 1
        edge = (reach > 1) & (reach <= LIGHT_EDGE)
        if not state.dark:  # game 1: the walls are always seen; the floor is dim until lit
            base = np.where(walls[..., None], full, dim)
        elif state.lightning:
            base = np.where(walls[..., None], flash, 0)
        else:
            base = np.zeros_like(full)
        base = np.where(edge[..., None], np.maximum(base, dim), base)
        return np.where(lit[..., None], full, base).astype(np.uint8)

    def who_is_there(self, state, frame_no):
        """(cast name, x, y, height) of everything to draw, back to front: stairs, items, monsters, eyes."""
        found = []
        if V.stairs_visible(state):
            stairs = state.stairs
            name = "stairs_up" if stairs.going_up else "stairs_down"
            found.append((name, stairs.x, stairs.y, HEIGHTS["stairs"]))
        for item in state.items:
            if V.item_visible(state, item):
                found.append((item_name(item), item.x, item.y, HEIGHTS["item"]))
        for monster in state.monsters:
            if V.monster_visible(state, monster):
                found.append((monster_name(monster), monster.x, monster.y, HEIGHTS["monster"]))
        found.append((f"eyes_{eyes_look(state.looking)}", *state.player, HEIGHTS["eyes"]))
        return found

    def picture(self, name, frame_no):
        """A cast picture, through the look's adapt(), animating at 8 frames a step."""
        frames = self.pack.cast.get(name)
        if not frames:
            return None
        index = (frame_no // 8) % len(frames)
        key = (name, index)
        if key not in self.adapted:
            self.adapted[key] = self.adapt(frames[index])
        return self.adapted[key]

    # --- the floor's pictures, built once a floor ---------------------------------------------------
    def scene(self, floor):
        if floor not in self.scenes:
            self.scenes[floor] = Scene(self, floor)
        return self.scenes[floor]

    def tile(self, name):
        """A world tile scaled to one 24 x 24 wall cell."""
        frames = self.pack.world.get(name)
        return fit(frames[0], CELL_PX, CELL_PX)

    # --- PLATFORM: a subclass supplies these --------------------------------------------------------
    def background(self):
        """(r, g, b) behind everything."""
        return (0, 0, 0)

    def adapt(self, picture):
        """A cast or world picture through the console's colour rules. Default: unchanged."""
        return picture

    def dimmed(self, rgb):
        """What's seen but not lit, given the lit colours (an array). Default: darker."""
        return (rgb * DIM).astype(np.uint8)

    def lightning_colour(self, rgb):
        """The colours of the walls in a lightning flash, given their normal colours (an array)."""
        return np.clip(rgb.astype(int) // 2 + 128, 0, 255).astype(np.uint8)

    def draw_status(self, screen, state, frame_no):
        """The status line: matches used, floor, what's carried, lives."""

    def draw_title(self, screen, state, frame_no):
        """Game select (and game over): the title screen."""

    def draw_win(self, screen, state, frame_no):
        """Drawn over the screen once the urn is out of the front door."""


class Scene:
    """A whole floor as pictures (FLOOR_PX_H x VIEW_W): fully lit, dim, in a lightning flash, and a mask of
    where the walls are. Built once a floor, from the ROM's wall plan and the world's tiles."""

    def __init__(self, look, floor):
        wall_tile = look.adapt(look.tile(f"wall{floor + 1}"))[..., :3]
        floor_tile = look.adapt(look.tile(f"floor{floor + 1}"))[..., :3]
        self.walls = wall_mask(look.rom)
        full = np.zeros((FLOOR_PX_H, VIEW_W, 3), np.uint8)
        for top in range(0, FLOOR_PX_H, CELL_PX):
            for left in range(0, VIEW_W, CELL_PX):
                full[top:top + CELL_PX, left:left + CELL_PX] = floor_tile
        tiled_walls = np.tile(wall_tile, (FLOOR_PX_H // CELL_PX, VIEW_W // CELL_PX, 1))
        full = np.where(self.walls[..., None], tiled_walls, full)
        if floor == 0:
            door = look.pack.world.get("front_door")
            if door:
                draw_front_door(full, self.walls, look.adapt(door[0]))
        self.full = full
        self.dim = look.dimmed(full)
        self.flash = look.lightning_colour(full)


# --- placing things ----------------------------------------------------------------------------------
def view_top_row(state):
    """The row of the whole-floor picture at the top of the view. The view's top line is floor line
    view_bottom + 79; the picture's row 0 is floor line 255."""
    top_line = state.view_bottom + VIEW_LINES - 1
    return int(round((FLOOR_LINES - 1 - top_line) * UNIT))


def light_reach_grid(state, rows):
    """light_reach for every pixel of the view."""
    row_numbers = np.arange(rows.start, rows.stop)[:, None]
    columns = np.arange(VIEW_W)[None, :]
    ys = FLOOR_LINES - 1 - (row_numbers + 0.5) / UNIT
    xs = (columns + 0.5) / UNIT
    return V.light_reach(state, xs, ys)


def place(picture, sprite, state, x, y, height):
    """Draw `sprite` centred on a thing's footprint: x..x+7 across, lines y..y+height-1 up."""
    line = y - state.view_bottom
    centre_x = (x + 4) * UNIT
    centre_y = (VIEW_LINES - line - height / 2) * UNIT
    blit(picture, sprite, centre_x - sprite.shape[1] / 2, centre_y - sprite.shape[0] / 2)


def item_name(item):
    if item.number == 0:
        return "key"
    if item.number == 1:
        return "scepter"
    return f"urn{item.shape}"


def monster_name(monster):
    if monster.number == 0:
        return "ghost"
    if monster.number == 1:
        return "bat"
    return f"tarantula{monster.number}"


def eyes_look(looking):
    """Where the pupils go: sideways first (the 2600 moves them across for left/right, then up/down)."""
    dx, dy = looking
    if dx:
        return "right" if dx > 0 else "left"
    if dy:
        return "up" if dy > 0 else "down"
    return "centre"


def wall_mask(rom):
    """Where the walls are on the whole-floor picture: the ROM's wall plan, one 24 px square a cell, plus
    the thin door frames at each side of the middle row."""
    walls = np.zeros((FLOOR_PX_H, VIEW_W), bool)
    for row in range(FLOOR_LINES // CELL):
        top = int((FLOOR_LINES - (row + 1) * CELL) * UNIT)
        for column in range(VIEW_UNITS_ACROSS // CELL):
            if R.wall_at(rom, column * CELL, row * CELL):
                walls[top:top + CELL_PX, column * CELL_PX:(column + 1) * CELL_PX] = True
        if row == MIDDLE_ROW:
            strip = int(EDGE_STRIP * UNIT)
            walls[top:top + CELL_PX, :strip] = True
            walls[top:top + CELL_PX, VIEW_W - strip:] = True
    return walls


def draw_front_door(full, walls, door):
    """The front door in the right-hand frame of the middle row, on the first floor. It shows wherever the
    walls do."""
    top = int((FLOOR_LINES - (MIDDLE_ROW + 1) * CELL) * UNIT)
    door_x = VIEW_W - door.shape[1]
    door_y = top + (CELL_PX - door.shape[0]) // 2
    blit(full, door, door_x, door_y)
    solid = door[..., 3] > 0
    walls[door_y:door_y + door.shape[0], door_x:door_x + door.shape[1]] |= solid


def fit(picture, width, height):
    """Scale a picture to width x height by repeating pixels (nearest neighbour)."""
    rows = (np.arange(height) * picture.shape[0] // height)
    columns = (np.arange(width) * picture.shape[1] // width)
    return picture[rows][:, columns]
