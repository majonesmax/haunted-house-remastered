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
    decor<n>          decorations hung on some faces (several frames = several kinds)
    front_door        the front door, in the right-hand frame of the middle row of floor 1
"""

import numpy as np

from game import rom as R
from looks.layout import (CELL, CELL_H, CELL_W, COLUMNS, EDGE_STRIP, FACE_H, FLOOR_PX_H, MIDDLE_ROW, ROWS,
                          UNIT_X, VIEW_W, cell_left, cell_top)
from shared.pixelart import blit

SHADOW_H = 4          # px of floor darkened under a wall's face
DECOR_EVERY = 3       # about one face in three gets a decoration
DECOR_TOP = 3         # px from the top of the face to a decoration


class Scene:
    """full / dim / dark / flash: (FLOOR_PX_H, VIEW_W, 3) pictures of the floor lit, a little dimmer (the
    edge of the light), much dimmer (unlit) and in a lightning flash. walls: where the walls are (True)."""

    def __init__(self, look, floor):
        number = floor + 1
        world = look.pack.world
        self.walls = wall_mask(look.rom)
        faces = face_mask(look.rom)
        flat = world.get(f"wall{number}")
        top = tile(look, world.get(f"wall{number}_top") or flat, CELL_W, CELL_H)
        face = tile(look, world.get(f"wall{number}_face") or flat, CELL_W, FACE_H)
        floor_tile = tile(look, world.get(f"floor{number}"), CELL_W, CELL_H)
        full = np.tile(floor_tile, (ROWS, COLUMNS, 1))
        full = np.where(self.walls[..., None], np.tile(top, (ROWS, COLUMNS, 1)), full)
        paint_faces(full, faces, face)
        outline(full, self.walls, faces, look.outline_colour(), trim_colour(look, world, number))
        shade_below_faces(full, faces, self.walls, look)
        decorate(full, faces, [look.adapt(picture) for picture in world.get(f"decor{number}") or []], floor)
        if floor == 0 and world.get("front_door"):
            draw_front_door(full, self.walls, look.adapt(world.get("front_door")[0]))
        self.full = full
        self.dim = look.dimmed(full)
        self.dark = look.dimmed(self.dim)
        self.flash = look.lightning_colour(full)


def tile(look, frames, width, height):
    """A world picture, through the look's colours, scaled to width x height (RGB)."""
    return look.adapt(fit(frames[0], width, height))[..., :3]


def wall_mask(rom):
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


def face_mask(rom):
    """{(row, column): True} for each wall cell with floor directly below it on screen: those show a face."""
    faces = {}
    for row in range(1, ROWS):
        for column in range(COLUMNS):
            wall_here = R.wall_at(rom, column * CELL, row * CELL)
            floor_below = not R.wall_at(rom, column * CELL, (row - 1) * CELL)
            if wall_here and floor_below:
                faces[(row, column)] = True
    return faces


def paint_faces(full, faces, face):
    for row, column in faces:
        bottom = cell_top(row) + CELL_H
        left = cell_left(column)
        full[bottom - FACE_H:bottom, left:left + CELL_W] = face


def outline(full, walls, faces, colour, trim):
    """A line along every wall pixel that touches floor, and inside it on the wall tops a line of trim -
    the moulding that shows where a wall's top ends."""
    edge = touching(walls, ~walls) & walls
    inner = touching(walls, edge) & walls & ~edge & ~face_pixels(faces, walls.shape)
    if trim is not None:
        full[inner] = trim
    full[edge] = colour


def touching(walls, mask):
    """Pixels with a neighbour (left, right, above, below) in mask; off the picture counts as wall."""
    padded = np.pad(mask, 1, constant_values=False)
    return padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]


def face_pixels(faces, shape):
    pixels = np.zeros(shape, bool)
    for row, column in faces:
        bottom = cell_top(row) + CELL_H
        pixels[bottom - FACE_H:bottom, cell_left(column):cell_left(column) + CELL_W] = True
    return pixels


def trim_colour(look, world, number):
    frames = world.get(f"wall{number}_trim")
    if not frames:
        return None
    return look.adapt(frames[0])[0, 0, :3]


def shade_below_faces(full, faces, walls, look):
    """The floor just below each face, in its shadow (the look's own darker colours)."""
    for row, column in faces:
        top = cell_top(row) + CELL_H
        left = cell_left(column)
        band = (slice(top, top + SHADOW_H), slice(left, left + CELL_W))
        floor_part = ~walls[band]
        darker = look.dimmed(full[band])
        full[band] = np.where(floor_part[..., None], darker, full[band])


def decorate(full, faces, decorations, floor):
    """Hang a decoration on about one face in DECOR_EVERY, chosen by its place so it never changes."""
    if not decorations:
        return
    for row, column in sorted(faces):
        if (column * 7 + row * 3 + floor) % DECOR_EVERY:
            continue
        picture = decorations[(column + row + floor) % len(decorations)]
        face_top = cell_top(row) + CELL_H - FACE_H
        left = cell_left(column) + (CELL_W - picture.shape[1]) // 2
        blit(full, picture, left, face_top + DECOR_TOP)


def draw_front_door(full, walls, door):
    """The front door in the right-hand frame of the middle row, on the first floor. It shows wherever the
    walls do."""
    top = cell_top(MIDDLE_ROW)
    door_x = VIEW_W - door.shape[1]
    door_y = top + (CELL_H - door.shape[0]) // 2
    blit(full, door, door_x, door_y)
    solid = door[..., 3] > 0
    walls[door_y:door_y + door.shape[0], door_x:door_x + door.shape[1]] |= solid


def fit(picture, width, height):
    """Scale a picture to width x height by repeating pixels (nearest neighbour)."""
    rows = np.arange(height) * picture.shape[0] // height
    columns = np.arange(width) * picture.shape[1] // width
    return picture[rows][:, columns]
