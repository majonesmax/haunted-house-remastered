"""A whole floor as pictures, built once a floor: the walls from the ROM's wall plan, drawn in 3/4 view with
the world's tiles.

Each wall cell is 24 x 32 px. A wall with floor below it shows its front face in the bottom FACE_H px of its
own cell - wallpaper, wainscoting, skirting - and its top surface above that; other walls show only their
top. Everything stays inside the wall cells, so the edges the player bumps into are exactly where the game
has them. Where walls meet floor they're outlined; the floor just below a face is in its shadow; some faces
carry a decoration (a portrait, a sconce...).

The world's pictures, by name (any can be left out):
    floor<n>          the floor tile of floor n (1-4), one 24 x 32 cell
    wall<n>_top       the top of a wall, one cell
    wall<n>_face      the front face, 24 x FACE_H
    wall<n>           a flat wall, for worlds without top and face (used for both)
    wall<n>_trim      the colour of the moulding along a wall's top where it meets floor (its top-left pixel)
    decor<n>_<kind>   decorations hung on some faces, one kind per name (decor1_portrait, decor1_sconce...).
                      Several frames (decor1_sconce_0, _1, _2): it flickers, each on its own beat.
                      decor<n>_<kind>_left / _right / _up / _down / _centre: its eyes follow the player.
                      decor<n>_<kind>_lightning: what it looks like in a lightning flash (a window).
    decor<n>          (older packs) decorations as frames of one picture, each a kind
    front_door        the front door, in the right-hand frame of the middle row of the ground floor
"""

from typing import TYPE_CHECKING, Any, NamedTuple

import numpy as np

from game import rom as R
from looks.layout import (CELL, CELL_H, CELL_W, COLUMNS, EDGE_STRIP, FACE_H, FLOOR_PX_H, MIDDLE_ROW, ROWS,
                          UNIT_X, VIEW_W, cell_left, cell_top)
from shared.pixelart import blit
from shared.types import Mask, Picture, Rgb

if TYPE_CHECKING:
    from content import Pictures
    from game.state import GameState
    from looks.base import FloorLook

SHADOW_H = 4          # px of floor darkened under a wall's face
DECOR_EVERY = 3       # about one face in three gets a decoration
DECOR_TOP = 1         # px from the top of the face to a decoration
EYE_LOOKS = ("centre", "left", "right", "up", "down")
FLAME_EVERY = 5       # frames a flickering decoration holds each picture
EYES_NEAR = 30        # px: closer than this, a portrait looks straight out

Variants = dict[str, Any]   # a decoration's pictures: variant ("frames", an eye look, "lightning") -> picture
                            # name; an older pack's also has "frame" -> which frame of its one picture


class Decoration(NamedTuple):
    """A living decoration: its pictures, where it hangs, and its beat (neighbours don't flicker as one)."""
    variants: Variants
    left: int
    top: int
    phase: int


class Layers(NamedTuple):
    """One frame's rows of the floor picture, in each light, to draw living decorations into."""
    full: Picture
    dim: Picture
    dark: Picture
    flash: Picture
    walls: Mask


class Scene:
    """full / dim / dark / flash: (FLOOR_PX_H, VIEW_W, 3) pictures of the floor lit, a little dimmer (the
    edge of the light), much dimmer (unlit) and in a lightning flash. walls: where the walls are (True)."""

    def __init__(self, look: "FloorLook", floor: int):
        number = floor + 1
        world = look.pack.world
        self.walls: Mask = wall_mask(look.rom)
        faces = face_mask(look.rom)
        flat = world.must(f"wall{number}")   # the original draws every floor's wall and floor
        top = tile(look, world.get(f"wall{number}_top") or flat, CELL_W, CELL_H)
        face = tile(look, world.get(f"wall{number}_face") or flat, CELL_W, FACE_H)
        floor_tile = tile(look, world.must(f"floor{number}"), CELL_W, CELL_H)
        full = np.tile(floor_tile, (ROWS, COLUMNS, 1))
        full = np.where(self.walls[..., None], np.tile(top, (ROWS, COLUMNS, 1)), full)
        paint_faces(full, faces, face)
        outline(full, self.walls, faces, look.outline_colour(), trim_colour(look, world, number))
        shade_below_faces(full, faces, self.walls, look)
        kinds = decoration_kinds(world, number)
        self.decorations: list[Decoration] = decorate(full, faces, kinds, floor, look)
        if floor == R.ground_floor(look.rom) and world.get("front_door"):
            draw_front_door(full, self.walls, look.adapt_scenery(world.must("front_door")[0]))
        self.full: Picture = full
        self.dim: Picture = look.dimmed(full)
        self.dark: Picture = look.dimmed(self.dim)
        self.flash: Picture = look.lightning_colour(full)

    def layers(self, rows: slice) -> Layers:
        """Copies of the pictures for these rows, to draw this frame's living decorations into."""
        return Layers(full=self.full[rows].copy(), dim=self.dim[rows].copy(), dark=self.dark[rows].copy(),
                      flash=self.flash[rows].copy(), walls=self.walls[rows])


def tile(look: "FloorLook", frames: list[Picture], width: int, height: int) -> Picture:
    """A world picture, through the look's colours, scaled to width x height (RGB)."""
    return look.adapt_scenery(fit(frames[0], width, height))[..., :3]


def wall_mask(rom: bytes) -> Mask:
    """Where the walls are on the floor picture: the ROM's wall plan, plus the thin door frames at each
    side of the middle row."""
    walls = np.zeros((FLOOR_PX_H, VIEW_W), bool)
    for row in range(ROWS):
        top = cell_top(row)
        for column in range(COLUMNS):
            if R.wall_at(rom, column * CELL, row * CELL):
                walls[top:top + CELL_H, cell_left(column):cell_left(column) + CELL_W] = True
        if row == MIDDLE_ROW:
            strip = int(EDGE_STRIP * UNIT_X)
            walls[top:top + CELL_H, :strip] = True
            walls[top:top + CELL_H, VIEW_W - strip:] = True
    return walls


def face_mask(rom: bytes) -> dict[tuple[int, int], bool]:
    """{(row, column): True} for each wall cell with floor directly below it on screen: those show a face."""
    faces = {}
    for row in range(1, ROWS):
        for column in range(COLUMNS):
            wall_here = R.wall_at(rom, column * CELL, row * CELL)
            floor_below = not R.wall_at(rom, column * CELL, (row - 1) * CELL)
            if wall_here and floor_below:
                faces[(row, column)] = True
    return faces


def paint_faces(full: Picture, faces: dict[tuple[int, int], bool], face: Picture) -> None:
    for row, column in faces:
        bottom = cell_top(row) + CELL_H
        left = cell_left(column)
        full[bottom - FACE_H:bottom, left:left + CELL_W] = face


def outline(full: Picture, walls: Mask, faces: dict[tuple[int, int], bool], colour: Rgb,
            trim: Picture | None) -> None:
    """A line along every wall pixel that touches floor, and inside it on the wall tops a line of trim -
    the moulding that shows where a wall's top ends."""
    edge = touching(walls, ~walls) & walls
    inner = touching(walls, edge) & walls & ~edge & ~face_pixels(faces, walls.shape)
    if trim is not None:
        full[inner] = trim
    full[edge] = colour


def touching(walls: Mask, mask: Mask) -> Mask:
    """Pixels with a neighbour (left, right, above, below) in mask; off the picture counts as wall."""
    padded = np.pad(mask, 1, constant_values=False)
    return padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]


def face_pixels(faces: dict[tuple[int, int], bool], shape: tuple[int, ...]) -> Mask:
    pixels = np.zeros(shape, bool)
    for row, column in faces:
        bottom = cell_top(row) + CELL_H
        pixels[bottom - FACE_H:bottom, cell_left(column):cell_left(column) + CELL_W] = True
    return pixels


def trim_colour(look: "FloorLook", world: "Pictures", number: int) -> Picture | None:
    frames = world.get(f"wall{number}_trim")
    if not frames:
        return None
    return look.adapt_scenery(frames[0])[0, 0, :3]


def shade_below_faces(full: Picture, faces: dict[tuple[int, int], bool], walls: Mask,
                      look: "FloorLook") -> None:
    """The floor just below each face, in its shadow (the look's own darker colours)."""
    for row, column in faces:
        top = cell_top(row) + CELL_H
        left = cell_left(column)
        band = (slice(top, top + SHADOW_H), slice(left, left + CELL_W))
        floor_part = ~walls[band]
        darker = look.dimmed(full[band])
        full[band] = np.where(floor_part[..., None], darker, full[band])


def decoration_kinds(world: "Pictures", number: int) -> list[Variants]:
    """[variants, ...]: each kind of decoration for floor `number`, as {variant: picture name}."""
    kinds: dict[str, Variants] = {}
    for name in world.names():
        if not name.startswith(f"decor{number}_"):
            continue
        base, _, last = name.rpartition("_")
        if last in EYE_LOOKS or last == "lightning":
            kinds.setdefault(base, {})[last] = name
        else:
            kinds.setdefault(name, {})["frames"] = name
    found = [kinds[kind] for kind in sorted(kinds)]
    for index in range(len(world.get(f"decor{number}") or [])):  # an older pack: one picture, many kinds
        found.append({"frames": f"decor{number}", "frame": index})
    return found


def decorate(full: Picture, faces: dict[tuple[int, int], bool], kinds: list[Variants], floor: int,
             look: "FloorLook") -> list[Decoration]:
    """Hang a decoration on about one face in DECOR_EVERY, chosen by its place so it never changes. Static
    ones are painted in; living ones are painted as they first look and returned, to redraw each frame."""
    living: list[Decoration] = []
    if not kinds:
        return living
    world = look.pack.world
    for row, column in sorted(faces):
        if (column * 7 + row * 3 + floor) % DECOR_EVERY:
            continue
        variants = kinds[(column + row + floor) % len(kinds)]
        picture = look.adapt_scenery(first_picture(world, variants))
        face_top = cell_top(row) + CELL_H - FACE_H
        left = cell_left(column) + (CELL_W - picture.shape[1]) // 2
        top = face_top + DECOR_TOP
        blit(full, picture, left, top)
        if is_living(world, variants):
            living.append(Decoration(variants, left, top, phase=column * 3 + row))
    return living


def first_picture(world: "Pictures", variants: Variants) -> Picture:
    if "centre" in variants:
        return world.must(variants["centre"])[0]
    return world.must(variants["frames"])[variants.get("frame", 0)]


def is_living(world: "Pictures", variants: Variants) -> bool:
    flickers = "frames" in variants and "frame" not in variants and len(world.must(variants["frames"])) > 1
    return flickers or "centre" in variants or "lightning" in variants


def decoration_now(world: "Pictures", decoration: Decoration, state: "GameState", frame_no: int,
                   player_pixel: tuple[float, float]) -> tuple[str, int]:
    """(picture name, frame) a living decoration shows this frame."""
    variants = decoration.variants
    if "centre" in variants:
        return variants[eyes_toward(decoration, player_pixel)], 0
    if "lightning" in variants and state.lightning:
        return variants["lightning"], 0
    frames = world.must(variants["frames"])
    return variants["frames"], (frame_no // FLAME_EVERY + decoration.phase) % len(frames)


def eyes_toward(decoration: Decoration, player_pixel: tuple[float, float]) -> str:
    """Which way a portrait's eyes look to follow the player (pixels on the floor picture)."""
    player_x, player_y = player_pixel
    dx, dy = player_x - (decoration.left + 6), player_y - (decoration.top + 5)
    if dx * dx + dy * dy < EYES_NEAR * EYES_NEAR:
        return "centre"
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def draw_front_door(full: Picture, walls: Mask, door: Picture) -> None:
    """The front door in the right-hand frame of the middle row, on the ground floor (the original's floor 1;
    a mansion with a cellar has floors below it). It shows wherever the walls do."""
    top = cell_top(MIDDLE_ROW)
    door_x = VIEW_W - door.shape[1]
    door_y = top + (CELL_H - door.shape[0]) // 2
    blit(full, door, door_x, door_y)
    solid = door[..., 3] > 0
    walls[door_y:door_y + door.shape[0], door_x:door_x + door.shape[1]] |= solid


def fit(picture: Picture, width: int, height: int) -> Picture:
    """Scale a picture to width x height by repeating pixels (nearest neighbour)."""
    rows = np.arange(height) * picture.shape[0] // height
    columns = np.arange(width) * picture.shape[1] // width
    return picture[rows][:, columns]
