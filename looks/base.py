"""What a LOOK is: the contract every way of drawing the game implements, and shared machinery for looks
that show the original's view of the floor.

The game runs unmodified in the emulator. Every frame the app hands a look a GameState (game/state.py) and
the look returns a picture. A look never changes the game - it only draws it.

A look is the console: the screen layout, the colour rules, the status line, the title and win screens.
What's drawn comes from a pack (content/): a CAST (who) and a WORLD (where). Any look shows any pack,
adapting its pictures to its own rules (adapt()).

    Look        the contract - what the app needs from any look.
    FloorLook   a Look that shows the original's window onto the floor (looks/layout.py), scrolling with
                the eyes exactly as the game's own camera does, with everything about placing things done:
                the floor in 3/4 view from the ROM's wall plan (looks/scenery.py), the cast at the game's
                positions, darkness and the match's flickering light by the original's rules
                (game/visibility.py). A subclass supplies the PLATFORM methods: its colours and screens.
"""

from abc import ABC, abstractmethod
from collections import deque, namedtuple

import numpy as np

from game import visibility as V
from looks.layout import (FLOOR_LINES, SCREEN_H, SCREEN_W, UNIT_X, UNIT_Y, VIEW_H, VIEW_W, VIEW_X, VIEW_Y,
                          floor_point, to_view, view_top_row)
from looks.scenery import Scene, decoration_now
from shared.pixelart import blit

HEIGHTS = {"eyes": 3, "item": 8, "monster": 10, "stairs": 17}  # each kind's height on the floor, in lines
FACING_MEMORY = 16            # frames of movement a monster's facing is judged over
JUMP = 8                      # moved further than this between frames: put somewhere new, not walking
WALK_MEMORY = 8               # a monster that hasn't moved in this many frames is standing still
LEGGED = ("tarantula",)       # monsters whose legs move only while they walk (the bat and ghost never stop)
OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}
LIGHT_CORE = 0.8              # inside this much of the light's reach, fully lit
LIGHT_EDGE = 1.3              # from the reach out to this, a dithered fade
FLICKER = 0.06                # the match's light grows and shrinks by up to this much...
FLICKER_EVERY = 4             # ...changing every this many frames
FLICKER_STEPS = (0.0, 0.7, -0.4, 1.0, -0.9, 0.3, -0.2, 0.8)  # a fixed wobble, so pictures repeat
BLINK_EVERY, BLINK_FRAMES = 200, 6   # the eyes blink for 6 frames in every 200
BANNER_FRAMES = 150           # how long a floor's name shows as you arrive on it
SKY_FLASH = np.array([70, 80, 120])   # distant lightning at its brightest lightens the screen by this
HAND_OFFSET = 10              # floor units from the eyes to the hand holding a lit match (left or right)
HAND_DROP = 2                 # ...and how far below them
DIM = 0.45                    # brightness of what's seen but not lit (looks may do it their own way)


Extras = namedtuple("Extras", "intro flash", defaults=(False, 0.0))
Extras.__doc__ = """What the app adds to the game: the story showing at launch (intro, until a key is
pressed), and distant lightning (flash, 0-1: shared/storm.py)."""
NO_EXTRAS = Extras()


class Look(ABC):
    """THE LOOK CONTRACT. The app uses a look only through these.

    platform   the look's short id: `play.py --look <platform>`
    name       its label in the window ("NES REMASTER")
    """

    platform = "?"
    name = "?"
    synth = "chiptune"   # the console's sound chip: plays any pack's songs (music/)

    @abstractmethod
    def draw(self, state, frame_no, extras=NO_EXTRAS):
        """The screen for this frame: a (240, 256, 3) uint8 RGB array. frame_no counts up once a frame;
        extras: the story and the storm (Extras)."""


class FloorLook(Look):
    """The original's view of the floor, redrawn. A subclass supplies the PLATFORM methods at the bottom."""

    def __init__(self, pack, rom):
        self.pack, self.rom = pack, rom
        self.scenes = {}       # floor -> its pictures, built once (looks/scenery.py)
        self.adapted = {}      # (name, frame) -> a cast picture through adapt()
        self.decor_patches = {}  # (name, frame) -> a living decoration's picture in each layer
        self.facing = Facing()
        self.banner_floor, self.banner_frames = None, 0   # the floor whose name is showing, and for how long
        self.hand_side = 1     # which side the match is held: +1 right, -1 left (the way you last went)
        self.checker = np.add.outer(np.arange(VIEW_H), np.arange(VIEW_W)) % 2 == 0

    def draw(self, state, frame_no, extras=NO_EXTRAS):
        screen = np.zeros((SCREEN_H, SCREEN_W, 3), np.uint8)
        screen[:] = self.background()
        if extras.intro:
            self.draw_intro(screen, frame_no)
        elif state.mode == "select":
            self.banner_floor = None  # a new game shows its first floor's name
            self.draw_title(screen, state, frame_no)  # the title has its own lightning
            return screen
        else:
            screen[VIEW_Y:VIEW_Y + VIEW_H, VIEW_X:VIEW_X + VIEW_W] = self.view(state, frame_no)
            self.draw_status(screen, state, frame_no)
            self.follow_floor(screen, state)
            if state.won:
                self.draw_win(screen, state, frame_no)
        if extras.flash:
            screen = self.distant_flash(screen, extras.flash)
        return screen

    def follow_floor(self, screen, state):
        """Arriving on a floor (by the stairs, or starting a game) shows its name for a moment."""
        if state.floor != self.banner_floor:
            self.banner_floor, self.banner_frames = state.floor, BANNER_FRAMES
        if self.banner_frames and state.mode == "playing":
            floors = self.pack.info.get("floors") or [f"FLOOR {number}" for number in range(1, 5)]
            self.draw_banner(screen, floors[state.floor].upper(), f"FLOOR {state.floor + 1}",
                             self.banner_frames / BANNER_FRAMES)
            self.banner_frames -= 1

    # --- the view ------------------------------------------------------------------------------------
    def view(self, state, frame_no):
        """The view: the floor around the eyes, lit by the original's rules, and who's there."""
        scene = self.scene(state.floor)
        top = view_top_row(state)
        rows = slice(top, top + VIEW_H)
        layers = scene.layers(rows)
        self.animate(scene, layers, rows, state, frame_no)
        picture = self.light(state, layers, rows, frame_no)
        self.facing.update(state.monsters)
        for name, facing, x, y, height, clock in self.who_is_there(state, frame_no):
            sprite = self.facing_picture(name, facing, clock)
            if sprite is not None:
                centre_x, centre_y = to_view(state, x, y, height)
                left, top = centre_x - sprite.shape[1] / 2, centre_y - sprite.shape[0] / 2
                opacity = self.opacity(name)
                if opacity < 1:
                    blend(picture, sprite, left, top, opacity)
                else:
                    blit(picture, sprite, left, top)
        return picture

    def animate(self, scene, layers, rows, state, frame_no):
        """Draw this frame's living decorations (flickering candles, portraits' eyes, windows in the
        lightning) into every layer, so they're lit exactly like the wall they hang on."""
        player_pixel = ((state.player[0] + 4) * UNIT_X, (FLOOR_LINES - 2 - state.player[1]) * UNIT_Y)
        for decoration in scene.decorations:
            if decoration.top + 16 < rows.start or decoration.top > rows.stop:
                continue
            name, frame = decoration_now(self.pack.world, decoration, state, frame_no, player_pixel)
            for layer, patch in self.decoration_patch(name, frame).items():
                blit(getattr(layers, layer), patch, decoration.left, decoration.top - rows.start)

    def decoration_patch(self, name, frame):
        """A decoration's picture as it looks lit, dim, dark and in a lightning flash (made once)."""
        key = (name, frame)
        if key not in self.decor_patches:
            picture = self.adapt_scenery(self.pack.world.get(name)[frame])
            patches = {"full": picture}
            for layer, change in (("dim", self.dimmed), ("flash", self.lightning_colour)):
                patch = picture.copy()
                patch[..., :3] = change(picture[..., :3])
                patches[layer] = patch
            dark = picture.copy()
            dark[..., :3] = self.dimmed(patches["dim"][..., :3])
            patches["dark"] = dark
            self.decor_patches[key] = patches
        return self.decor_patches[key]

    def light(self, state, layers, rows, frame_no):
        """Choose, per pixel, how the floor shows (the original's rules): fully lit near the match, a
        dithered fade at the edge of its reach, and outside it dim (game 1), black (games 2-9) or the walls
        in a lightning flash."""
        full, dim, flash, walls = layers.full, layers.dim, layers.flash, layers.walls
        reach = light_reach_grid(state, rows) / flicker(frame_no)
        if not state.dark:  # game 1: the walls are always seen; the floor is dark until lit
            unlit = np.where(walls[..., None], full, layers.dark)
        elif state.lightning:
            unlit = np.where(walls[..., None], flash, 0)
        else:
            unlit = np.zeros_like(full)
        core = reach <= LIGHT_CORE
        inner = (reach > LIGHT_CORE) & (reach <= 1)
        outer = (reach > 1) & (reach <= LIGHT_EDGE)
        checker = self.checker[..., None]
        picture = np.where((outer & self.checker)[..., None], np.maximum(unlit, dim), unlit)
        picture = np.where(inner[..., None], np.where(checker, full, dim), picture)
        return np.where(core[..., None], full, picture).astype(np.uint8)

    def who_is_there(self, state, frame_no):
        """(cast name, facing, x, y, height, clock) of everything to draw, back to front: stairs, items,
        monsters, eyes. Only monsters have a facing; the rest have None. The clock runs the picture's
        animation: frame_no, or 0 for a legged monster standing still."""
        found = []
        if V.stairs_visible(state):
            stairs = state.stairs
            name = "stairs_up" if stairs.going_up else "stairs_down"
            found.append((name, None, stairs.x, stairs.y, HEIGHTS["stairs"], frame_no))
        for item in state.items:
            if V.item_visible(state, item):
                found.append((item_name(item), None, item.x, item.y, HEIGHTS["item"], frame_no))
        for monster in state.monsters:
            if V.monster_visible(state, monster):
                name = monster_name(monster)
                facing = self.facing.of(monster)
                standing = name.startswith(LEGGED) and not self.facing.walking(monster)
                clock = 0 if standing else frame_no
                found.append((name, facing, monster.x, monster.y, HEIGHTS["monster"], clock))
        found += self.you(state, frame_no)
        return found

    def you(self, state, frame_no):
        """The eyes - and by matchlight, a hood around them and a hand holding up the match (if the cast
        draws them). The eyes are where the game has the player; the hood and hand stay close, so they
        never seem to touch what the eyes don't."""
        x, y = state.player
        eyes = (self.eyes_name(state, frame_no), None, x, y, HEIGHTS["eyes"], frame_no)
        if not state.match_lit:
            return [eyes]
        if state.looking[0]:
            self.hand_side = 1 if state.looking[0] > 0 else -1
        hand_side = "right" if self.hand_side > 0 else "left"
        hand_x = x + self.hand_side * HAND_OFFSET
        return [("hood", None, x, y, HEIGHTS["eyes"], frame_no), eyes,
                ("match_hand", hand_side, hand_x, y - HAND_DROP, HEIGHTS["eyes"], frame_no)]

    def eyes_name(self, state, frame_no):
        """The eyes look the way the joystick pushes, and now and then blink (if the cast draws a blink)."""
        blinking = frame_no % BLINK_EVERY < BLINK_FRAMES and state.mode == "playing"
        if blinking and self.pack.cast.get("eyes_blink"):
            return "eyes_blink"
        return f"eyes_{eyes_look(state.looking)}"

    def facing_picture(self, name, facing, frame_no):
        """The cast's picture of `name` facing that way: its own "<name>_<facing>" if the pack draws one;
        else the opposite side, mirrored (left <-> right); else the plain "<name>"."""
        if facing is None:
            return self.picture(name, frame_no)
        if self.pack.cast.get(f"{name}_{facing}"):
            return self.picture(f"{name}_{facing}", frame_no)
        opposite = f"{name}_{OPPOSITE[facing]}"
        if facing in ("left", "right") and self.pack.cast.get(opposite):
            return self.picture(opposite, frame_no)[:, ::-1]
        return self.picture(name, frame_no)

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

    def scene(self, floor):
        if floor not in self.scenes:
            self.scenes[floor] = Scene(self, floor)
        return self.scenes[floor]

    # --- PLATFORM: a subclass supplies these --------------------------------------------------------
    def background(self):
        """(r, g, b) behind everything."""
        return (0, 0, 0)

    def adapt(self, picture):
        """A cast picture through the console's colour rules. Default: unchanged."""
        return picture

    def adapt_scenery(self, picture):
        """A world picture (tiles, decorations) through the console's rules. Default: as the cast."""
        return self.adapt(picture)

    def opacity(self, name):
        """How solid a cast picture is drawn: 1 solid; less, see-through (a console with colour math)."""
        return 1.0

    def dimmed(self, rgb):
        """What's seen but not lit, given the lit colours (an array). Default: darker."""
        return (rgb * DIM).astype(np.uint8)

    def lightning_colour(self, rgb):
        """The colours of the walls in a lightning flash, given their normal colours (an array)."""
        return np.clip(rgb.astype(int) // 2 + 128, 0, 255).astype(np.uint8)

    def outline_colour(self):
        """The line drawn where walls meet floor."""
        return (0, 0, 0)

    def draw_status(self, screen, state, frame_no):
        """The status line: matches used, floor, what's carried, lives."""

    def draw_title(self, screen, state, frame_no):
        """Game select (and game over): the title screen."""

    def distant_flash(self, screen, level):
        """The whole screen lightened by distant lightning (level 0-1), evenly, so it shows nothing."""
        return np.clip(screen + SKY_FLASH * level, 0, 255).astype(np.uint8)

    def draw_intro(self, screen, frame_no):
        """At launch, before the title: the story (game/guide.py)."""

    def draw_banner(self, screen, name, subtitle, left):
        """A floor's name as you arrive; `left` runs from 1 (just arrived) down to 0."""

    def draw_win(self, screen, state, frame_no):
        """Drawn over the screen once the urn is out of the front door."""


class Facing:
    """Which way each monster faces, worked out from how it moves: the game keeps only where a monster is
    and where it's heading next (and while it chases, that plan isn't where it's going). Judged over the
    last FACING_MEMORY frames, as monsters step only on some frames."""

    def __init__(self):
        self.trails = {}   # monster number -> its recent (floor, x, y)
        self.facings = {}  # monster number -> "left" / "right" / "up" / "down"

    def update(self, monsters):
        for monster in monsters:
            here = (monster.floor, monster.x, monster.y)
            trail = self.trails.setdefault(monster.number, deque(maxlen=FACING_MEMORY))
            if trail and jumped(trail[-1], here):
                trail.clear()
            trail.append(here)
            previous = self.facings.get(monster.number, monster.heading)
            self.facings[monster.number] = judge_facing(trail, previous)

    def of(self, monster):
        """Its facing; until it's been seen moving, the way its plan says it's heading."""
        return self.facings.get(monster.number, monster.heading)

    def walking(self, monster):
        """Has it moved in the last WALK_MEMORY frames?"""
        recent = list(self.trails.get(monster.number, ()))[-WALK_MEMORY:]
        return len(set(recent)) > 1


def jumped(before, after):
    """Did a monster move further than walking could take it (scattered after a death, up the stairs)?"""
    if before[0] != after[0]:
        return True
    return abs(after[1] - before[1]) > JUMP or abs(after[2] - before[2]) > JUMP


def judge_facing(trail, previous):
    """The way a trail of positions goes: along its longer side. Exactly diagonal keeps the previous facing
    if that's one of the two ways it's going; standing still keeps it too."""
    _floor, first_x, first_y = trail[0]
    _floor, last_x, last_y = trail[-1]
    dx, dy = last_x - first_x, last_y - first_y
    across = "right" if dx > 0 else "left"
    up_down = "up" if dy > 0 else "down"   # the game's y counts up the floor
    if abs(dx) > abs(dy):
        return across
    if abs(dy) > abs(dx):
        return up_down
    if dx == 0:
        return previous
    return previous if previous in (across, up_down) else across


def blend(picture, sprite, left, top, opacity):
    """Paste a sprite part see-through: its solid pixels mixed with what's under them."""
    left, top = int(round(left)), int(round(top))
    height, width = sprite.shape[:2]
    x0, y0 = max(left, 0), max(top, 0)
    x1, y1 = min(left + width, picture.shape[1]), min(top + height, picture.shape[0])
    if x0 >= x1 or y0 >= y1:
        return
    part = sprite[y0 - top:y1 - top, x0 - left:x1 - left]
    solid = part[..., 3:4] > 0
    under = picture[y0:y1, x0:x1].astype(float)
    mixed = under * (1 - opacity) + part[..., :3] * opacity
    picture[y0:y1, x0:x1] = np.where(solid, mixed, under).astype(np.uint8)


def flicker(frame_no):
    """How big the match's light is this frame, as a fraction of its reach."""
    step = FLICKER_STEPS[(frame_no // FLICKER_EVERY) % len(FLICKER_STEPS)]
    return 1 + FLICKER * step


def light_reach_grid(state, rows):
    """light_reach for every pixel of the view."""
    row_numbers = np.arange(rows.start, rows.stop)[:, None]
    columns = np.arange(VIEW_W)[None, :]
    xs, ys = floor_point(row_numbers, columns)
    return V.light_reach(state, xs, ys)


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
