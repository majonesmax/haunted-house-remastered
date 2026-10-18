"""What the 128 bytes of Haunted House's RAM mean - the game state a remaster reads every frame.

How the monsters use their bytes is in game/monsters.py, which predicts them exactly frame by frame.

Sources: our own trace of the ROM (tools/xref.py, docs/generated/ram-xref.md), the commented disassembly by
Brandon Roberts (reference/disassembly), and experiments in the running game (tools/verify_ram.py).

How sure we are, per byte:
  "live"  - an experiment in tools/verify_ram.py checks it against the running game
  "code"  - read from the code that uses it, not yet checked live
  "guess" - a working idea; treat with care

The heart of it is a set of parallel tables, 11 bytes apart. Index 0 is the player; 1-5 are the items
(master key, scepter, three urn pieces); 6-10 are the monsters (ghost, bat, tarantulas):

            player   items 0-4   monsters 0-4
    floor     -       $A0-$A4     $A5-$A9
    x        $AA      $AB-$AF     $B0-$B4
    y        $B5      $B6-$BA     $BB-$BF
    room      $9C        -        $C5-$C9      (items have no room byte: their x, y say where they are)

Coordinates cover a whole floor (x 4-$94 across, y 1-$FB up); the screen scrolls through it. Up is +y.
"""

ITEM_FLOOR, ITEM_X, ITEM_Y = 0xA0, 0xAB, 0xB6           # + item number 0-4
MONSTER_FLOOR, MONSTER_X, MONSTER_Y = 0xA5, 0xB0, 0xBB  # + monster number 0-4
MONSTER_ROUTE, MONSTER_ROOM = 0xC0, 0xC5                # + monster number 0-4

FLOOR, ROOM = 0x8D, 0x9C
POS_X, POS_Y = 0xAA, 0xB5
CARRIED = 0x9A          # item number carried, $FF = nothing
URN_SHAPES = 0x9D       # $9D-$9F: shape of items 2, 3, 4 (see game.rom.URN_SHAPES)
LIVES = 0x96
MATCHES_USED = 0x82     # BCD, shown bottom left
MATCH_TIME = 0xDF       # seconds left on the lit match
FLAGS = 0x8A            # bit 7 item/monster frame, bit 6 match lit, bit 0 won
GAME_STATE = 0x99       # $00 playing, $01 dying, $02 just reset, $40 game over / select, $44 won
GAME_NUMBER = 0xCC      # 0-8 = games 1-9
MONSTERS_HERE = 0x83    # how many monsters share the player's room
DEATH_TIMER = 0x80
KILLED_BY = 0xCA        # the monster that took the last life
LAST_MONSTER = 0xEA     # 2 in games 1-4 (ghost, bat, one tarantula), 4 in games 5-9
CLOCK = 0x89

NOTHING = 0xFF

# address -> (name, meaning, how sure). Ranges are listed once, at their first byte.
RAM = {
    0x80: ("DEATH_TIMER", "$FF when a monster catches you, counts down to 0 while the eyes roll (monsters "
                          "keep walking, but don't chase); at 0 the monsters are scattered and play goes on, "
                          "or the game ends if no lives are left", "live"),
    0x81: ("DROP_TRIES", "5 when an item is dropped, counts down while the game looks for a free spot "
                         "for it next to the player", "code"),
    0x82: ("MATCHES_USED", "matches lit this game, BCD (the score - lower is better), shown bottom left",
           "live"),
    0x83: ("MONSTERS_HERE", "monsters in the player's room (or the doorway's other room); while not 0 you "
                            "can't light a match, a lit one blows out, and lightning may flash", "live"),
    0x84: ("COLOUR_CYCLE", "bit 4 set: attract mode - the colours drift; the rest counts every 256 frames",
           "code"),
    0x85: ("MONSTER_SHOWN", "which monster was drawn this frame (one per frame, in turn); the last slot "
                            "shows the stairs", "code"),
    0x86: ("ITEM_SHOWN", "which item was drawn this frame (one per frame, in turn)", "live"),
    0x87: ("SECOND_COUNTER", "counts down 60 frames, then the match loses a second. Runs all the time and "
                             "is not reset when a match is lit, so a match's first second is 1-60 frames "
                             "(256 for the first match after RESET, which clears it to 0)", "live"),
    0x88: ("DOORWAY", "bit 7 = in a doorway now; low bits = its direction (0 left, 1 right, 2 up, 3 down), "
                      "kept after you leave it", "live"),
    0x89: ("CLOCK", "frame counter, +1 every frame", "live"),
    0x8A: ("FLAGS", "bit 7 flips every frame (item frame / monster frame); bit 6 = match lit; "
                    "bit 0 = won", "live"),
    0x8B: ("ROOM_TOP", "the room's top y limit: with a match lit in games 2-9, nothing (glow, items) is "
                       "drawn above it", "live"),
    0x8C: ("ROOM_BOTTOM", "the room's bottom y limit (0 = none): nothing is drawn below it", "live"),
    0x8D: ("FLOOR", "floor 0-3 (shown as 1-4)", "live"),
    0x8E: ("JOYSTICK", "this frame's joystick: bit 7 right, 6 left, 5 down, 4 up (1 = pushed)", "live"),
    0x8F: ("THUNDER", "while dying: frames left of this rumble (each 16-44 frames, random)", "live"),
    0x90: ("SOUND_TIME", "frames left of the current sound effect (ROM SOUND_LENGTHS)", "live"),
    0x91: ("BLOCKED", "bits 6/7 stop sideways / up-down movement (a locked door in the way)", "code"),
    0x92: ("MOOD_DIRECTION", "whether the monster-near noise ($98) is rising (0) or falling", "live"),
    0x93: ("SOUND", "the sound effect playing: 2 blocked, 3 bump, 4 doorway, 5 drop, 6 pick up, "
                    "7 urn pieces join, 8 new room, 9 stairs up, 10 stairs down, 11 urn whole; 0 = none "
                    "(footsteps). Game 1 has no door sounds. See game/sounds.py", "live"),
    0x94: ("FOLLOWING", "a bit per monster sent after the player through a door or stairs (games 6-9); "
                        "these move at chasing speed. Replaced each time the player leaves a room", "live"),
    0x95: ("ARRIVED", "a bit per monster that reached its waypoint; one a frame (lowest number first) "
                      "gets a new plan", "live"),
    0x96: ("LIVES", "lives left, 9 at the start", "live"),
    0x97: ("ROOM_BEYOND", "while in a doorway, the room on the other side; $FF otherwise", "live"),
    0x98: ("MOOD_PITCH", "the monster-near noise: wanders while a monster is in your room, drifts back "
                         "to $7F (silent) after; lower = louder", "live"),
    0x99: ("GAME_STATE", "$00 playing, $01 dying, $02 one frame after RESET, $40 game over / game select, "
                         "$44 won", "live"),
    0x9A: ("CARRIED", "item carried: 0 master key, 1 scepter, 2-4 urn pieces; $FF = nothing", "live"),
    0x9B: ("STAIRS", "low 4 bits: this room's stairs ($F = none; bits 0-1 edge, bit 2 = going up); "
                     "bit 7 = player at the floor's edge, bit 6 = just used the stairs (step away first)",
           "live"),
    0x9C: ("ROOM", "the player's room 0-5", "live"),
    0x9D: ("URN_SHAPES", "$9D-$9F: shape of items 2, 3, 4 - 2/3/4 a single piece, 5-7 two joined, 8 the "
                         "whole urn, $FF = joined into another piece", "live"),
    0xA0: ("ITEM_FLOOR", "$A0-$A4: each item's floor", "live"),
    0xA5: ("MONSTER_FLOOR", "$A5-$A9: each monster's floor", "live"),
    0xAA: ("POS_X", "player x (4-$94)", "live"),
    0xAB: ("ITEM_X", "$AB-$AF: each item's x", "live"),
    0xB0: ("MONSTER_X", "$B0-$B4: each monster's x", "live"),
    0xB5: ("POS_Y", "player y (1-$FB), up is +", "live"),
    0xB6: ("ITEM_Y", "$B6-$BA: each item's y", "live"),
    0xBB: ("MONSTER_Y", "$BB-$BF: each monster's y", "live"),
    0xC0: ("MONSTER_ROUTE", "$C0-$C4: each monster's plan: direction << 6 | kind << 4 | target. Kind 0 = "
                            "to the centre of room `target`, 1 = to door `target`, 2/3 = down/up the stairs "
                            "of room `target`. See game/monsters.py", "live"),
    0xC5: ("MONSTER_ROOM", "$C5-$C9: each monster's room", "live"),
    0xCA: ("KILLED_BY", "the monster that caught you last (games 7-9: if it was the bat, it takes the item "
                        "you carried)", "live"),
    0xCB: ("EYES_LINE", "the line the eyes are drawn on: $26 (mid-screen) except near the floor's top and "
                        "bottom, where the view stops scrolling", "live"),
    0xCC: ("GAME_NUMBER", "0-8 = games 1-9", "live"),
    0xCD: ("LINE", "scanline counter while the screen is drawn", "code"),
    0xCE: ("UNUSED", "never touched by the code", "code"),
    0xCF: ("MASK_X", "x of the ball, one of two 8-pixel blocks put in the middle wall's gap while a match "
                     "is lit (games 2-9; the other is missile 0 at $DE). The glow never reaches them, so "
                     "nothing comes of them on screen", "code"),
    0xD0: ("SCRATCH", "$D0-$DB: working space; the same bytes mean different things at different moments "
                      "of a frame (sprite pointers for the status line, distances, ...)", "code"),
    0xDC: ("OBJECT_X", "$DC-$E0: screen x of the five TIA objects (sprite, eyes, missile, -, ball) for "
                       "this frame. $DD is the eyes; $DF is shared with MATCH_TIME", "code"),
    0xDF: ("MATCH_TIME", "seconds left on the match: 20 when lit, -1 a second", "live"),
    0xE1: ("SPRITE_POINTER", "$E1-$E2: the sprite drawn this frame (item, monster or stairs)", "code"),
    0xE3: ("EYES_POINTER", "$E3-$E4: the eyes' picture (or the match's glow)", "code"),
    0xE5: ("SELECT_DELAY", "frames until SELECT steps to the next game again (45 while held)", "live"),
    0xE6: ("BUTTON_HISTORY", "the button over the last 8 frames, one bit each (a press = $7F)", "code"),
    0xE7: ("STEP_X", "this frame's x step: 1, 0 or $FF (-1)", "live"),
    0xE8: ("STEP_Y", "this frame's y step: 1, 0 or $FF (-1)", "live"),
    0xE9: ("DROPPED", "the item being put down", "code"),
    0xEA: ("LAST_MONSTER", "number of the last monster in play: 2 (games 1-4) or 4 (games 5-9)", "live"),
    0xEB: ("RANDOM", "$EB-$EC: the random number generator, a 16-bit shift register stirred once a frame "
                     "(and more when monsters are scattered); see game.monsters.next_random", "live"),
    0xED: ("SPRITE_HEIGHT", "height of this frame's sprite", "code"),
    0xEE: ("EYES_HEIGHT", "height of the eyes (3) or of the glow (28)", "code"),
    0xEF: ("SPRITE_LINE", "line the sprite starts on", "code"),
    0xF0: ("EYES_LINE_COPY", "line the eyes start on", "code"),
    0xF1: ("COLOURS", "$F1-$F5: this frame's colours: sprite, eyes, status, status background, walls. "
                      "$F5 is black in games 2-9, and lightning grey ($0D) during a flash", "live"),
    0xF6: ("STACK", "$F6-$FF: the CPU stack (return addresses)", "code"),
}


def describe(address: int) -> tuple[str, str, str]:
    """(name, meaning, how sure) for any address, following ranges back to their first byte."""
    for start in range(address, 0x7F, -1):
        if start in RAM:
            return RAM[start]
    return ("?", "", "guess")
