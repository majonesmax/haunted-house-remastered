"""What just happened, worked out from two frames of the game's state - for the remastered sound effects
(music/effects.py names them).

Most events come from the state itself, so they're heard in every game (the 2600 makes no door sounds in game
1, for one): a match lit or going out, through a doorway, up or down the stairs, picking things up and putting
them down, urn pieces joining, a monster coming into the room, being caught, lightning. Two only the game
knows, so they come from its sound byte: bumping into a wall, and being refused at a locked door (or at the
front door without the urn).
"""

from game.state import MONSTER_KINDS, GameState

URN_PIECES = {2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 3}   # urn shape -> how many pieces it is
BUMP, BLOCKED = 3, 2                                      # the game's own sound effect numbers
STEP_EVERY = 14         # frames of walking between footsteps
THUNDER_GAP = 90        # frames: lightning flickers, but one roll of thunder per strike
PICKUPS = {0: "pickup_key", 1: "pickup_scepter"}         # item number -> its sound; urn pieces: pickup_urn


class EventWatcher:
    def __init__(self):
        self.before: GameState | None = None
        self.walking = 0
        self.since_thunder = THUNDER_GAP

    def update(self, state: GameState) -> list[str]:
        """The events between the last frame and this one, as effect names (music/effects.py)."""
        before, self.before = self.before, state
        self.since_thunder += 1
        if before is None or state.mode in ("select", "starting") or before.mode == "select":
            self.walking = 0
            return []
        events = []
        for check in (self.match, self.moving, self.carrying, self.urn, self.danger, self.game_sounds):
            events += check(before, state)
        return events

    def match(self, before: GameState, state: GameState) -> list[str]:
        if state.matches_used > before.matches_used:
            return ["match_strike"]
        if before.match_lit and not state.match_lit:
            return ["match_out"]
        return []

    def moving(self, before: GameState, state: GameState) -> list[str]:
        """Stairs, doorways, rooms, footsteps."""
        if state.floor != before.floor:
            self.walking = 0
            return ["stairs_up" if state.floor > before.floor else "stairs_down"]
        events = []
        if state.room_beyond is not None and before.room_beyond is None:
            events.append("door_open")
        if state.room != before.room:
            events.append("door_close")
        if state.player != before.player and state.mode == "playing":
            self.walking += 1
            if self.walking % STEP_EVERY == 1:
                events.append("footstep")
        else:
            self.walking = 0
        return events

    def carrying(self, before: GameState, state: GameState) -> list[str]:
        """Picking something up, or putting it down (not when it's taken from you, or joined)."""
        if state.carried == before.carried:
            return []
        if state.carried is not None and before.carried is None:
            return [PICKUPS.get(state.carried, "pickup_urn")]
        put_down = state.carried is None and before.carried is not None
        if put_down and before.mode == "playing" and state.mode == "playing":  # not taken while you die
            return ["drop"]
        return []

    def urn(self, before: GameState, state: GameState) -> list[str]:
        """Pieces joining: a bigger group than there was."""
        biggest = max(URN_PIECES.get(item.shape, 0) for item in state.items[2:])
        was = max(URN_PIECES.get(item.shape, 0) for item in before.items[2:])
        if biggest > was:
            return ["urn_whole" if biggest == 3 else "urn_join"]
        return []

    def danger(self, before: GameState, state: GameState) -> list[str]:
        """Caught; a monster coming into the room; lightning (and its thunder)."""
        events = []
        if state.mode == "dying" and before.mode != "dying":
            events.append("caught")
        elif state.monsters_here and not before.monsters_here:
            events.append(monster_sound(state))
        if state.lightning and not before.lightning and self.since_thunder >= THUNDER_GAP:
            self.since_thunder = 0
            events.append("thunder")
        return events

    def game_sounds(self, before: GameState, state: GameState) -> list[str]:
        """What only the game knows: a bump into a wall, a door that won't open."""
        if state.sound == before.sound:
            return []
        if state.sound == BUMP:
            return ["bump"]
        if state.sound == BLOCKED:
            return ["locked"]
        return []


def monster_sound(state: GameState) -> str:
    """The sound of whichever monster is in the room: the ghost, the bat or a tarantula."""
    for monster in state.monsters:
        in_room = monster.floor == state.floor and monster.room in (state.room, state.room_beyond)
        if in_room:
            return f"monster_{MONSTER_KINDS[monster.number]}"
    return "monster_tarantula"
