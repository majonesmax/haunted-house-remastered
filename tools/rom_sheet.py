"""Draw what's in the ROM, as the game's own tables describe it: one sheet for the cast, one for the mansion.

shots/rom_cast.png    every sprite (items, urn shapes, monsters, stairs, the match's glow, digits, eyes)
                      in its own colour, plus the palette
shots/rom_mansion.png each floor's plan for games 1-2, 3-8 and 9: walls, room numbers, doors (locked ones
                      in red), stairs (up / down) and the front door

Everything is read from the user's ROM through game/rom.py; nothing is drawn by hand. Look at both after
changing game/rom.py - they are the quickest way to see a decoding mistake.

Usage: python tools/rom_sheet.py
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import HERE, SHOTS  # noqa: E402

sys.path.insert(0, HERE)
from game import palette  # noqa: E402
from game import rom as R  # noqa: E402

PIXEL = 6            # sprite pixels are drawn this big on the cast sheet
MAP_SCALE = 2        # floor units -> pixels on the mansion sheet
FLOOR_WIDTH, FLOOR_HEIGHT = 0xA0, 0x100
BACKGROUND, INK, DIM = (16, 16, 24), (230, 230, 230), (120, 120, 130)
LOCKED, STAIRS_UP, STAIRS_DOWN, FRONT_DOOR = (230, 60, 60), (90, 220, 120), (240, 190, 60), (120, 200, 255)
WALL_COLOUR_FIRST = 8   # floor f's walls use palette entry 8 + f
ITEM_COLOURS = "ITEM_COLOURS"


def ntsc_palette():
    return palette.load()


def rgb_for(palette, colour_byte):
    return palette[colour_byte & 0xFE]


def colour_number(rom, index):
    return R.table(rom, "COLOURS")[index]


# --- the cast ----------------------------------------------------------------------------------------
def draw_sprite(draw, rows, left, top, colour, width=1):
    for row_number, row in enumerate(rows):
        for column, cell in enumerate(row):
            if cell == "#":
                x = left + column * PIXEL * width
                y = top + row_number * PIXEL
                draw.rectangle([x, y, x + PIXEL * width - 1, y + PIXEL - 1], fill=colour)


def cast_entries(rom, palette):
    """(label, rows, colour, width) for every sprite, in sheet order, grouped into lines."""
    item_colours = R.table(rom, ITEM_COLOURS)
    items = []
    for shape in range(9):
        label = R.ITEM_NAMES[shape] if shape < 2 else R.URN_SHAPES[shape]
        colour_index = item_colours[min(shape, 2)]
        rows = R.sprite_rows(rom, R.item_sprite_address(shape), 8)
        items.append((label, rows, rgb_for(palette, colour_number(rom, colour_index)), 1))
    monsters = []
    for monster in range(3):
        colour = rgb_for(palette, colour_number(rom, monster + 1))
        for frame, address in enumerate(R.monster_sprite_addresses(rom, monster)):
            label = f"{R.MONSTER_NAMES[monster]} {frame + 1}"
            monsters.append((label, R.sprite_rows(rom, address, 10), colour, 1))
    stairs = []
    for number in range(4):
        stairs.append((f"stairs {number}", R.sprite_rows(rom, 0xFE8C + 17 * number, 17), DIM, 1))
    glow = [("glow big", R.sprite_rows(rom, 0xFF50, 28), (192, 97, 47), 4),
            ("glow small", R.sprite_rows(rom, 0xFF6C, 28), (192, 97, 47), 4)]
    digits = [(str(digit), R.sprite_rows(rom, 0xFF00 + 8 * digit, 8), INK, 1) for digit in range(10)]
    return [items, monsters + stairs, glow + eyes_entries(), digits]


def eyes_entries():
    """The eyes are built in RAM each frame from constants in the code ($F318-$F336): whites $E7 on all
    three rows, and one row swapped for a pupil row - which row and which pupils follow the joystick."""
    whites, centre, right, left = 0xE7, 0xA5, 0xC6, 0x63
    looks = {"eyes": (centre, 1), "eyes right": (right, 1), "eyes left": (left, 1),
             "eyes up": (centre, 2), "eyes down": (centre, 0)}
    entries = []
    for label, (pupils, pupil_row) in looks.items():
        data = [whites, whites, whites]
        data[pupil_row] = pupils
        rows = ["".join("#" if byte & 0x80 >> bit else "." for bit in range(8)) for byte in reversed(data)]
        entries.append((label, rows, INK, 1))
    return entries


def draw_cast(rom, palette):
    lines = cast_entries(rom, palette)
    cell_width, gap = 8 * PIXEL * 4 + 24, 40
    width = max(sum(8 * PIXEL * entry[3] + 24 for entry in line) for line in lines) + 24
    heights = [max(len(entry[1]) for entry in line) * PIXEL + gap for line in lines]
    palette_height = 80
    palette_width = 12 + 12 * 70
    sheet = Image.new("RGB", (max(width, cell_width, palette_width), sum(heights) + palette_height + 24),
                      BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    top = 12
    for line, height in zip(lines, heights):
        left = 12
        for label, rows, colour, sprite_width in line:
            draw.text((left, top), label, fill=DIM)
            draw_sprite(draw, rows, left, top + 14, colour, sprite_width)
            left += 8 * PIXEL * sprite_width + 24
        top += height
    draw_palette(draw, rom, palette, top)
    return sheet


def draw_palette(draw, rom, palette, top):
    draw.text((12, top), "palette (COLOURS): entry, colour byte - 1 lightning/ghost, 6 urn, 8-11 walls of "
                         "floors 1-4", fill=DIM)
    for index in range(12):
        value = colour_number(rom, index)
        left = 12 + index * 70
        draw.rectangle([left, top + 18, left + 60, top + 50], fill=rgb_for(palette, value), outline=DIM)
        draw.text((left, top + 54), f"{index}: ${value:02X}", fill=DIM)


# --- the mansion -------------------------------------------------------------------------------------
def to_map(x, y, left, top):
    """Floor units -> sheet pixels. Up is +y in the game, so it is flipped for the picture."""
    return left + x * MAP_SCALE, top + (FLOOR_HEIGHT - 1 - y) * MAP_SCALE


def draw_walls(draw, rom, left, top, colour):
    for y in range(FLOOR_HEIGHT):
        for x in range(FLOOR_WIDTH):
            if R.wall_at(rom, x, y):
                screen_x, screen_y = to_map(x, y, left, top)
                draw.rectangle([screen_x, screen_y, screen_x + MAP_SCALE - 1, screen_y + MAP_SCALE - 1],
                               fill=colour)


def door_bar(rom, door, rooms):
    """The rectangle (in floor units) of a door's opening: x0, y0, x1, y1."""
    first_x, first_y = R.room_centre(rom, rooms[0])
    second_x, second_y = R.room_centre(rom, rooms[1])
    if first_x == second_x:  # one above the other: the gap is in the wall row between them
        row = (first_y + second_y) // 2 >> 4
        column_left = first_x >> 4 << 4
        return column_left, row * 16, column_left + 15, row * 16 + 15
    row = first_y >> 4       # side by side: the gap is in the middle wall
    return 0x40, row * 16, 0x5F, row * 16 + 15


def draw_floor(draw, rom, palette, floor, game, left, top):
    wall_colour = rgb_for(palette, colour_number(rom, WALL_COLOUR_FIRST + floor))
    draw_walls(draw, rom, left, top, wall_colour)
    for room in range(R.ROOM_COUNT):
        x, y = R.room_centre(rom, room)
        draw.text(to_map(x - 3, y + 4, left, top), str(room), fill=INK)
    locked = R.locked_doors(rom, floor, game)
    for door, rooms in R.doors(rom).items():
        if door in locked:
            x0, y0, x1, y1 = door_bar(rom, door, rooms)
            first, second = to_map(x0, y1, left, top), to_map(x1, y0, left, top)
            draw.rectangle([first, second], outline=LOCKED, width=2)
    for room, stair in R.stairs(rom, floor, game).items():
        colour = STAIRS_UP if stair["goes"] == "up" else STAIRS_DOWN
        x, y = to_map(stair["x"], stair["y"], left, top)
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=colour)
        draw.text((x - 3, y - 6), "U" if stair["goes"] == "up" else "D", fill=BACKGROUND)
    if floor == 0:
        x, y = to_map(0x94, 0x86, left, top)
        draw.rectangle([x, y - 8, x + 16, y + 8], fill=FRONT_DOOR)


def draw_mansion(rom, palette):
    games = [(0, "games 1-2 (no locks)"), (2, "games 3-8"), (R.GAME_9, "game 9")]
    floor_width, floor_height = FLOOR_WIDTH * MAP_SCALE, FLOOR_HEIGHT * MAP_SCALE
    margin, title = 24, 22
    width = margin + R.FLOOR_COUNT * (floor_width + margin)
    height = 40 + len(games) * (floor_height + title + margin)
    sheet = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 10), "red box = locked door   green U = stairs up   yellow D = stairs down   "
                            "blue = front door (floor 1, room 2)", fill=DIM)
    for row, (game, label) in enumerate(games):
        top = 40 + row * (floor_height + title + margin)
        for floor in range(R.FLOOR_COUNT):
            left = margin + floor * (floor_width + margin)
            draw.text((left, top), f"{label}, floor {floor + 1}", fill=INK)
            draw_floor(draw, rom, palette, floor, game, left, top + title)
    return sheet


def main():
    os.makedirs(SHOTS, exist_ok=True)
    rom = R.load()
    palette = ntsc_palette()
    sheets = {"rom_cast.png": draw_cast(rom, palette), "rom_mansion.png": draw_mansion(rom, palette)}
    for name, sheet in sheets.items():
        path = os.path.join(SHOTS, name)
        sheet.save(path)
        print(path)


if __name__ == "__main__":
    main()
