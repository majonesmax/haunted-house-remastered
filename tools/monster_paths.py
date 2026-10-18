"""Draw where the monsters go: the waypoint network on each floor, and the paths they really walked.

Runs game 3 (locked doors matter there) for a few minutes of game time while the player waits in the
starting room holding the scepter, and records every monster's position each frame. Writes
shots/monster_paths.png: each floor's plan (from tools/rom_sheet.py), the waypoints (room centres, doors,
stairs) and each monster's trail in its own colour.

Usage: python tools/monster_paths.py [frames]
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import HERE, SELECT, SHOTS, Lab  # noqa: E402
from rom_sheet import BACKGROUND, DIM, FLOOR_HEIGHT, FLOOR_WIDTH, INK, MAP_SCALE  # noqa: E402
from rom_sheet import colour_number, draw_floor, ntsc_palette, rgb_for, to_map  # noqa: E402

sys.path.insert(0, HERE)
from game import monsters as model  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402
from shared.types import Point, Rgb  # noqa: E402

Trails = dict[int, list[tuple[int, int, int]]]   # monster -> its (floor, x, y) every frame

GAME = 2                 # game 3
FRAMES = 20000
WAYPOINT_COLOUR = (255, 255, 255)


def record(frames: int) -> Trails:
    """Each monster's (floor, x, y) every frame, while the player waits with the scepter."""
    lab = Lab()
    while lab.peek(M.GAME_NUMBER) != GAME:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    trails: Trails = {monster: [] for monster in range(5)}
    for _ in range(frames):
        lab.poke(M.CARRIED, model.SCEPTER)
        lab.run(1)
        for monster in range(lab.peek(M.LAST_MONSTER) + 1):
            where = (lab.peek(M.MONSTER_FLOOR + monster), lab.peek(M.MONSTER_X + monster),
                     lab.peek(M.MONSTER_Y + monster))
            trails[monster].append(where)
    return trails


def draw_waypoints(draw: ImageDraw.ImageDraw, rom: bytes, floor: int, left: int, top: int) -> None:
    """Room centres (circles), doors (squares) and this floor's stairs (diamonds), joined as monsters
    walk them: centre -> door -> next centre, centre -> stairs."""
    for door, rooms in R.doors(rom).items():
        door_point = waypoint_on_map(rom, 6 + door, left, top)
        for room in rooms:
            draw.line([waypoint_on_map(rom, room, left, top), door_point], fill=DIM, width=1)
        draw.rectangle([door_point[0] - 3, door_point[1] - 3, door_point[0] + 3, door_point[1] + 3],
                       outline=WAYPOINT_COLOUR)
    for room in R.stairs(rom, floor, GAME):
        stairs_point = waypoint_on_map(rom, 13 + room, left, top)
        draw.line([waypoint_on_map(rom, room, left, top), stairs_point], fill=DIM, width=1)
        x, y = stairs_point
        draw.polygon([(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)], outline=WAYPOINT_COLOUR)
    for room in range(R.ROOM_COUNT):
        x, y = waypoint_on_map(rom, room, left, top)
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], outline=WAYPOINT_COLOUR)


def waypoint_on_map(rom: bytes, index: int, left: int, top: int) -> Point:
    x, y = R.table(rom, "WAYPOINT_X")[index], R.table(rom, "WAYPOINT_Y")[index]
    return to_map(x + 4, y, left, top)  # +4: the middle of an 8-wide sprite


def draw_trails(draw: ImageDraw.ImageDraw, rom: bytes, palette: dict[int, Rgb], trails: Trails, floor: int,
                left: int, top: int) -> None:
    for monster, points in trails.items():
        colour = rgb_for(palette, colour_number(rom, monster + 1))
        for here_floor, x, y in points:
            if here_floor == floor:
                screen_x, screen_y = to_map(x + 4, y, left, top)
                draw.point((screen_x, screen_y), fill=colour)


def draw_sheet(rom: bytes, trails: Trails) -> Image.Image:
    palette = ntsc_palette()
    floor_width, floor_height = FLOOR_WIDTH * MAP_SCALE, FLOOR_HEIGHT * MAP_SCALE
    margin, title = 24, 22
    sheet = Image.new("RGB", (margin + R.FLOOR_COUNT * (floor_width + margin), floor_height + title + 70),
                      BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    names = ", ".join(f"{R.MONSTER_NAMES[monster]}" for monster, points in trails.items() if points)
    draw.text((margin, 8), f"game 3: monster paths over {len(trails[0])} frames ({names}); circles = room "
                           "centres, squares = doors, diamonds = stairs", fill=DIM)
    for floor in range(R.FLOOR_COUNT):
        left, top = margin + floor * (floor_width + margin), 30
        draw.text((left, top), f"floor {floor + 1}", fill=INK)
        draw_floor(draw, rom, palette, floor, GAME, left, top + title)
        draw_waypoints(draw, rom, floor, left, top + title)
        draw_trails(draw, rom, palette, trails, floor, left, top + title)
    return sheet


def main() -> None:
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else FRAMES
    rom = R.load()
    sheet = draw_sheet(rom, record(frames))
    path = os.path.join(SHOTS, "monster_paths.png")
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
