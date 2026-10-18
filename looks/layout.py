"""The screen layout every FloorLook shares, and how floor positions become pixels.

    +-----------------------------------+   0
    |  status: matches, carried, lives  |
    +-+-------------------------------+-+  40 = VIEW_Y
    | |  the view: the original's     | |      160 floor units across x 80 lines up, the same window
    | |  window onto the floor,       | |      as the 2600's; 1.5 px a unit across, 2 down, so a 16 x 16
    | |  240 x 160                    | |      wall cell is 24 x 32 px - room for a wall's top and face
    +-+-------------------------------+-+ 200
    |  the floor's name, the game       |
    +-----------------------------------+ 240
    0 8                              248 256

The whole floor (256 lines up) is drawn once as one 240 x 512 picture (looks/scenery.py); the view is the
80 lines of it around the eyes, exactly where the game's own camera puts them.
"""

SCREEN_W, SCREEN_H = 256, 240
UNIT_X, UNIT_Y = 1.5, 2.0           # pixels per floor unit, across and down
VIEW_LINES, VIEW_UNITS_ACROSS = 80, 160
VIEW_X, VIEW_Y = 8, 40
VIEW_W, VIEW_H = int(VIEW_UNITS_ACROSS * UNIT_X), int(VIEW_LINES * UNIT_Y)  # 240 x 160
CELL = 16                           # floor units in a wall cell
CELL_W, CELL_H = int(CELL * UNIT_X), int(CELL * UNIT_Y)  # 24 x 32
FACE_H = 20                         # px: a wall with floor below shows its front face in its bottom 20
FLOOR_LINES = 256
FLOOR_PX_H = int(FLOOR_LINES * UNIT_Y)  # 512
COLUMNS, ROWS = VIEW_UNITS_ACROSS // CELL, FLOOR_LINES // CELL  # the wall plan: 10 x 16 cells
EDGE_STRIP = 4                      # units of wall drawn at each side of the middle row (door frames)
MIDDLE_ROW = 8


def cell_top(row):
    """The floor picture's row at the top of wall-plan row `row` (row 0 is the bottom of the floor)."""
    return int((FLOOR_LINES - (row + 1) * CELL) * UNIT_Y)


def cell_left(column):
    return column * CELL_W


def view_top_row(state):
    """The row of the whole-floor picture at the top of the view: its top line is view_bottom + 79."""
    top_line = state.view_bottom + VIEW_LINES - 1
    return int((FLOOR_LINES - 1 - top_line) * UNIT_Y)


def to_view(state, x, y, height):
    """The view pixel at the middle of a thing's footprint: x..x+7 across, lines y..y+height-1 up."""
    line = y - state.view_bottom
    return (x + 4) * UNIT_X, (VIEW_LINES - line - height / 2) * UNIT_Y


def floor_point(row, column):
    """The floor (x, y) at the middle of a pixel of the whole-floor picture."""
    return (column + 0.5) / UNIT_X, FLOOR_LINES - (row + 0.5) / UNIT_Y
