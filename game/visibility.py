"""What the player may see - the original's rules, so a remaster reveals exactly as much as the 2600 does.

The RAM says where everything is; these rules say what's visible. All were checked in the running game
(docs/screen-and-sound.md, tools/verify_games.py), and the line numbers are the code they come from.

- Walls: always in game 1; in games 2-9 only during a lightning flash.
- The match's light: around the eyes while a match is lit, never past the room's top and bottom limits in
  games 2-9 (the 2600 stops drawing there), and not through walls.
- Items: only with a match lit, close by (a "light distance" under 17), not carried, and not joined into
  another urn piece. The master key never shows in games 1-2 (they have no locked doors).
- Monsters: in game 1 any on your floor; in games 2-9 only those in your room (or the room beyond the
  doorway you stand in) - lit or not - and all on your floor while you die.
- Stairs: this room's, while a match is lit.
"""

import numpy as np

ITEM_REACH = 0x11        # items show while their light distance is under this ($F53D)
VIEW_LINES = 80          # the view is 80 lines tall
KEY = 0
JOINED = 0xFF
LIGHT_HALF_WIDTH, LIGHT_HALF_HEIGHT = 16, 14   # the 2600 glow: 32 wide, 28 tall, centred on the eyes


def walls_visible(state):
    return not state.dark or state.lightning


def on_screen(state, y, height=1):
    """Is any of the lines y .. y + height - 1 inside the view?"""
    bottom = y - state.view_bottom
    return bottom + height > 0 and bottom < VIEW_LINES


def light_distance(state, x, y):
    """The game's cheap distance: the larger difference plus half the smaller ($F53D)."""
    across = abs(state.player[0] - x)
    up_down = abs(state.player[1] - y)
    if up_down >= across:
        return up_down + (across >> 1)
    return across + (up_down >> 1)


def item_visible(state, item):
    if not state.match_lit or item.floor != state.floor or item.number == state.carried:
        return False
    if item.number == KEY and state.game < 3:
        return False
    if item.number >= 2 and item.shape == JOINED:
        return False
    return light_distance(state, item.x, item.y) < ITEM_REACH


def monster_visible(state, monster):
    if monster.floor != state.floor:
        return False
    if not state.dark or state.mode == "dying":
        return on_screen(state, monster.y, 10)
    in_room = state.monsters_here > 0 and monster.room in (state.room, state.room_beyond)
    return in_room and on_screen(state, monster.y, 10)


def stairs_visible(state):
    return state.match_lit and state.stairs is not None


def light_reach(state, xs, ys):
    """How far floor points are from the match, as a fraction of the light's reach: <= 1 is lit. Works on
    single numbers or numpy arrays. Points beyond the room's limits (games 2-9) are given infinity.
    (Walls block the light too - the look decides how to show that, since it draws the walls.)"""
    centre_x = state.player[0] + 4      # the middle of the 8-wide eyes
    centre_y = state.player[1] + 1
    across = (np.asarray(xs, float) - centre_x) / LIGHT_HALF_WIDTH
    up_down = (np.asarray(ys, float) - centre_y) / LIGHT_HALF_HEIGHT
    reach = np.sqrt(across * across + up_down * up_down)
    if not state.match_lit:
        return np.full(np.shape(reach), np.inf)
    if state.dark:
        bottom, top = state.room_limits
        outside = (np.asarray(ys) < bottom) | (np.asarray(ys) > top)
        reach = np.where(outside, np.inf, reach)
    return reach


def lit(state, x, y):
    """Is the floor point (x, y) inside the match's light?"""
    return bool(light_reach(state, x, y) <= 1)
