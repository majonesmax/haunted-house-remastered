"""G: a hint, when you ask for one - it points you at what you need next, and says the same thing again until
something changes: the nearest piece of the urn (up or down the stairs, or which way across the floor),
how to take it once you're in its room, and - with the whole urn in hand - to get out of the front door,
and which way. Nothing is marked on screen and the game is unchanged (the original never shows where
anything is - the hint only points). Read from the same RAM as everything else, so it's right in every
game, wherever the house has hidden things this time.

Lines are at most 30 characters, a screen's width in the looks' 8 px font, which has no brackets
(shared/hud.py: GLYPHS has letters, digits and  !',-./:<>?).
"""

from game import rom as R
from game.state import WHOLE_URN

URN_PIECES = (2, 3, 4)          # item numbers
PIECES_IN = {2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 3}   # an urn shape -> how many pieces it is
JOINED = 0xFF                   # a piece joined into another: it isn't anywhere by itself
OTHER_FLOOR = 1000              # how far another floor counts, against distances across one (up to ~400)
FRONT_DOOR_FLOOR = 0
WHOLE_URN_NOTE = ["THE URN IS WHOLE!", "NOW GET IT OUT OF THE", "FRONT DOOR - FLOOR 1, RIGHT."]


def hint(state, rom):
    """The lines for G, for this moment."""
    if state.mode != "playing":
        return ["PRESS ENTER TO START.", "TAB CHOOSES THE GAME (1-9)."]
    if holding_whole_urn(state):
        return get_out(state)
    aim = nearest_urn(state)
    if aim is None:
        return ["NOTHING LEFT TO FIND."]
    floor, room = aim.floor, room_at(rom, aim.x, aim.y)
    if floor == state.floor and room == state.room:
        return take_it(state, aim)
    return [left_to_find(state), way(state, floor, room)]


def holding_whole_urn(state):
    return state.carried is not None and state.items[state.carried].shape == WHOLE_URN


def get_out(state):
    """With the whole urn: out of the front door, and which way."""
    lines = ["YOU HAVE THE URN! GET OUT NOW!"]
    if state.floor == FRONT_DOOR_FLOOR and state.room == R.FRONT_DOOR_ROOM:
        return lines + ["WALK OUT OF THIS ROOM'S", "RIGHT-HAND EDGE."]
    return lines + ["THE FRONT DOOR IS", way(state, FRONT_DOOR_FLOOR, R.FRONT_DOOR_ROOM)]


def take_it(state, aim):
    what = "THE URN IS" if aim.shape == WHOLE_URN else "A PIECE IS"
    if state.match_lit:
        return [f"{what} IN THIS ROOM.", "WALK INTO IT WHILE THE", "MATCH BURNS."]
    return [f"{what} IN THIS ROOM.", "LIGHT A MATCH - SPACE - AND", "WALK INTO IT."]


def nearest_urn(state):
    """The nearest piece, pieces or whole urn that isn't in your hands - an Item, or None."""
    lying = [item for item in state.items
             if item.number in URN_PIECES and item.shape != JOINED and item.number != state.carried]
    if not lying:
        return None
    def distance(item):   # another floor is always further than anywhere on this one
        across = abs(item.x - state.player[0]) + abs(item.y - state.player[1])
        return abs(item.floor - state.floor) * OTHER_FLOOR + across
    return min(lying, key=distance)


def left_to_find(state):
    """'3 PIECES LEFT. THE NEAREST IS' - counting what's in your hands as found."""
    in_hand = 0
    if state.carried in URN_PIECES:
        in_hand = PIECES_IN.get(state.items[state.carried].shape, 0)
    left = len(URN_PIECES) - in_hand
    if left == 1:
        return "1 PIECE LEFT. IT IS"
    return f"{left} PIECES LEFT. THE NEAREST IS"


def way(state, floor, room):
    """Which way: up or down the stairs, else across the floor - never which room exactly."""
    if floor != state.floor:
        climbs = abs(floor - state.floor)
        direction = "UP" if floor > state.floor else "DOWN"
        return f"{direction} THE STAIRS, {climbs} FLOOR{'S' if climbs > 1 else ''}."
    return across(state.room, room)


def room_at(rom, x, y):
    """The room (0-5) whose middle is nearest a place on the floor."""
    def distance(room):
        centre_x, centre_y = R.room_centre(rom, room)
        return (centre_x - x) ** 2 + (centre_y - y) ** 2
    return min(range(R.ROOM_COUNT), key=distance)


def across(from_room, to_room):
    """The way across a floor: up/down a row, left/right a column (rooms: even on the right, 0-1 at the
    bottom)."""
    rows = to_room // 2 - from_room // 2
    columns = (from_room % 2) - (to_room % 2)      # from the left column (odd) to the right (even): +1
    vertical = "UP" if rows > 0 else "DOWN" if rows < 0 else ""
    sideways = "TO THE RIGHT" if columns > 0 else "TO THE LEFT" if columns < 0 else ""
    return " AND ".join(part for part in (vertical, sideways) if part) + "."


def urn_just_whole(before, after):
    """Did the urn become whole in your hands between these two states? (For the note that says so.)"""
    return holding_whole_urn(after) and not holding_whole_urn(before)
