"""G: a hint, when you ask for one - the goal, then which way to go, then a tip. Each press says a little
more; none of it changes the game, and nothing is ever marked on screen (the original never shows where
anything is - the hint only points). Read from the same RAM as everything else, so it's right in the later
games too, where the house hides things in different places.

Lines are at most 30 characters, a screen's width in the looks' 8 px font, which has no brackets
(shared/hud.py: GLYPHS has letters, digits and  !',-./:<>?).
"""

from game import rom as R
from game.state import WHOLE_URN

URN_PIECES = (2, 3, 4)          # item numbers
KEY, SCEPTER = 0, 1
FEARLESS_GHOST_FROM = 8         # from game 8 the ghost isn't kept off by the scepter (game/guide.py)
LOCKS_FROM = 3                  # games 3-9 have locked doors
OTHER_FLOOR = 1000              # how far another floor counts, against distances across one (up to ~400)


def hint(state, rom, level):
    """The lines for the `level`-th press (0, 1, 2...: the goal, the way, then tips in turn)."""
    if state.mode != "playing":
        return ["PRESS ENTER TO START.", "TAB CHOOSES THE GAME (1-9)."]
    steps = [goal(state), way(state, rom), *tips(state)]
    return steps[level % len(steps)]


def target(state):
    """What you're after now: the front door if you hold the whole urn, else the nearest piece -
    (floor, x, y), or None."""
    if holding_whole_urn(state):
        return None
    pieces = [item for item in state.items
              if item.number in URN_PIECES and item.shape != 0xFF and item.number != state.carried]
    if not pieces:
        return None
    def distance(item):   # another floor is always further than anywhere on this one
        across = abs(item.x - state.player[0]) + abs(item.y - state.player[1])
        return abs(item.floor - state.floor) * OTHER_FLOOR + across
    nearest = min(pieces, key=distance)
    return nearest.floor, nearest.x, nearest.y


def holding_whole_urn(state):
    return state.carried is not None and state.items[state.carried].shape == WHOLE_URN


def goal(state):
    if holding_whole_urn(state):
        return ["YOU HAVE THE WHOLE URN!", "TAKE IT OUT OF THE FRONT", "DOOR: FLOOR 1, ON THE RIGHT."]
    here = sum(1 for item in state.items if item.number in URN_PIECES and item.shape != 0xFF
               and item.floor == state.floor and item.number != state.carried)
    lines = ["FIND THE 3 PIECES OF THE URN."]
    if state.carried in URN_PIECES:
        lines.append("WALK INTO A PIECE TO JOIN IT.")
    on_this_floor = {0: "NONE ARE ON THIS FLOOR.", 1: "ONE IS ON THIS FLOOR."}
    lines.append(on_this_floor.get(here, f"{here} ARE ON THIS FLOOR."))
    return lines


def way(state, rom):
    """Which way to the target: up or down the stairs, else across the floor - never which room exactly."""
    if holding_whole_urn(state):
        floor, room = 0, R.FRONT_DOOR_ROOM
    else:
        aim = target(state)
        if aim is None:
            return ["NOTHING LEFT TO FIND."]
        floor, room = aim[0], room_at(rom, aim[1], aim[2])
    what = "THE FRONT DOOR IS" if holding_whole_urn(state) else "THE NEAREST PIECE IS"
    if floor != state.floor:
        climbs = abs(floor - state.floor)
        direction = "UP" if floor > state.floor else "DOWN"
        return [what, f"{direction} THE STAIRS, {climbs} FLOOR{'S' if climbs > 1 else ''}."]
    return [what, across(state.room, room)]


def room_at(rom, x, y):
    """The room (0-5) whose middle is nearest a place on the floor."""
    def distance(room):
        centre_x, centre_y = R.room_centre(rom, room)
        return (centre_x - x) ** 2 + (centre_y - y) ** 2
    return min(range(R.ROOM_COUNT), key=distance)


def across(from_room, to_room):
    """'IN THIS ROOM.', or the way: up/down a row, left/right a column (rooms: even on the right, 0-1 at
    the bottom)."""
    if from_room == to_room:
        return "IN THIS ROOM - LIGHT A MATCH."
    rows = to_room // 2 - from_room // 2
    columns = (from_room % 2) - (to_room % 2)      # from the left column (odd) to the right (even): +1
    vertical = "UP" if rows > 0 else "DOWN" if rows < 0 else ""
    sideways = "TO THE RIGHT" if columns > 0 else "TO THE LEFT" if columns < 0 else ""
    both = " AND ".join(part for part in (vertical, sideways) if part)
    return f"{both}."


def tips(state):
    """Practical help, the most useful first."""
    found = [["TO PICK SOMETHING UP, LIGHT", "A MATCH AND WALK INTO IT."]]
    if state.game >= LOCKS_FROM and state.carried != KEY:
        found.append(["LOCKED DOORS OPEN FOR THE", f"MASTER KEY - ON FLOOR {state.items[KEY].floor + 1}."])
    if state.carried != SCEPTER:
        scepter = ["THE SCEPTER KEEPS MONSTERS", f"OFF YOU - IT'S ON FLOOR {state.items[SCEPTER].floor + 1}."]
        if state.game >= FEARLESS_GHOST_FROM:
            scepter.append("BUT NOT THIS GAME'S GHOST.")
        found.append(scepter)
    found.append(["THINGS ONLY SHOW CLOSE TO", "A LIT MATCH: SPACE LIGHTS ONE.",
                  "YOU CAN HOLD ONE AT A TIME."])
    return found
