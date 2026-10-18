# What's in the ROM, and what a remaster needs from it

Haunted House is a 4K cartridge: 3,446 bytes of code and 650 bytes of data (`tools/xref.py` traced it; the
split is in [generated/rom-layout.md](generated/rom-layout.md)). This page lists every piece of that data,
grouped by what a remaster preserves: the **look**, the **world** and the **cast**, plus the **rules** that
make it play the same.

Tables are read from the user's ROM at run time by `game/rom.py` (its `TABLES` list has the addresses).
Nothing from the ROM is copied into this repository. To see the tables, run `python tools/rom_sheet.py` and
open `shots/rom_cast.png` and `shots/rom_mansion.png`.

**How sure we are:** *live* = checked in the running game by `tools/verify_ram.py`; *code* = read from the
code that uses it; *guess* = a working idea.

## The world: one mansion, four floors

| Table | Address | What it is | Sure |
|---|---|---|---|
| FLOOR_WALLS | $FFD4 | The wall plan: 16 rows of 8 bits, each cell 16×16 floor units. **The same on every floor.** | live |
| DOOR_IDS | $FD82 | Per room: its left/right/up/down neighbour as a door number 0–6, the outer edge, or a wall | live |
| LOCKED_DOORS | $FDD5 | Per floor: which doors are locked (games 3–8; game 9 has its own 4 bytes) | code |
| STAIRS_HERE / STAIRS_GO_UP | $FDDD / $FDE5 | Per floor: which rooms have stairs, and which go up (game 9 has its own) | live |
| STAIRS_EDGE, STAIRS_X, STAIRS_Y | $FD46, $FF8C, $FF88 | Where each room's stairs are: which edge, and the x, y they're drawn at | live / code |
| ROOM_STEP | $FFD0 | Room number change through a door: left +1, right −1, up +2, down −2 | live |
| ROOM_BOUNDS | $FD7F | The y limits of the lit part of a room when the walls are dark | code |
| COLOURS 8–11 | $FFEC | Wall colour of floors 1–4: blue, red-brown, dark green, ochre | code |

What the tables say, drawn in `shots/rom_mansion.png`:

- **A floor is one tall map** (x 4–$94, y 1–$FB, up is +y) that scrolls past a fixed window, not a set of
  flip-screens like Adventure. The screen shows 80 units of y at a time. The player stays on line $26 except
  near the top and bottom, where the view stops.
- **Six rooms per floor**, two columns by three rows. Even numbers are on the right, odd on the left; 0/1 at
  the bottom, 4/5 at the top. The player starts in room 2 of floor 1, beside the **front door** on its right
  wall. Walking out of it carrying the whole urn wins.
- **Seven doors** join the rooms. In games 3–9 some are locked, a different set on each floor. The master
  key opens them.
- **Stairs** sit at the outer edges: rooms 0/1 at the bottom, 4/5 at the top, 2 on the right, 3 on the left.
  Each floor's stairs match the floor above and below. Game 9 moves the stairs and the locks.

## The cast

| Table | Address | What it is | Sure |
|---|---|---|---|
| ITEM_SPRITES | $FE08 | 9 pictures, 8 rows: master key, scepter, urn pieces 1–3, the three pairs, the whole urn | live |
| MONSTER_SPRITES | $FE50 | 6 pictures, 10 rows: ghost, bat, tarantula, two animation frames each | code |
| STAIRS_SPRITES | $FE8C | 4 pictures, 17 rows: the stairs, by edge and direction | code |
| LIGHT_SPRITES, LIGHT_FLICKER | $FF50, $FF9A | The match's glow, big and small, and the flicker pattern | code |
| Eyes | code, $F318–$F336 | The player is a pair of eyes, built in RAM each frame from constants in the code. The pupils follow the joystick | code |
| DYING_EYES | $FF92 | Fake joystick values fed to the eyes so they roll while you die | code |
| ITEM_COLOURS, MONSTER colours | $F4D6, code | Key green, scepter white, urn light blue; ghost white, bat green, tarantulas red, orange, blue | code |
| DIGITS | $FF00 | 0–9 for the status line: matches used, floor, lives | live |
| COLOURS | $FFE4 | 12 NTSC colours, then the same 12 for the B/W switch | code |

Every sprite is stored **bottom row first**: the kernel counts lines down the screen, so the last byte is the
top row. A live frame confirmed this (the urn's neck is at the top). The disassembly README draws the urn
upside down; `game/rom.py` gets it right.

**Who's who** (from the code, confirmed live where marked):

- **Items 0–4:** master key, scepter, urn pieces 1–3. Pieces join when you carry one and touch another (live).
  The scepter stops monsters from catching you (live), except the ghost in games 8–9 (code).
- **Monsters 0–4:** ghost, bat, then up to three tarantulas. Games 1–4 have the first three; games 5–9 all
  five (live). In games 7–9 the bat takes what you carried when it catches you (live).

## The rules

| Table | Address | What it is | Sure |
|---|---|---|---|
| NEW_GAME | $FDF6 | Copied to RAM $96–$9F on RESET: 9 lives, carrying nothing, room 2, urn shapes 2/3/4 | live |
| MONSTER_SPEED, _FAST | $FA86, $FA8B | Per monster, a bit mask of which of 8 frames it steps on when chasing | live |
| WAYPOINT_START / _X / _Y | $FFA6, $FFAA, $FFBD | 19 points monsters walk between: room centres, doors, stairs | live |
| CHASE_OFFSET_X / _Y | $FDEC, $FDF1 | Where around the player each monster aims when chasing (with a quirk) | live |
| DROP_OFFSETS | $FD02 | Where a dropped item lands next to the player | code |
| SOUND_LENGTHS, STAIRS_TONES, WIN_TUNE | $F8A0, $FFA2, $FF9E | Sound effect lengths and notes ([screen-and-sound.md](screen-and-sound.md)) | live |

Rules confirmed live: one step per frame, with the stick read one frame late. A match lasts 20 seconds,
counted on a free-running 60-frame timer. A monster in your room blows the match out and stops you lighting
another. Items show only while a match is lit and only very close by (a light distance under 17). Getting
caught costs a life, then about 4 seconds of rolling eyes. The last life ends the game.

Monster movement has its own page: [monsters.md](monsters.md).

### What changes with the game number

Every row is confirmed live, in all nine games. `tools/verify_games.py` checks 117 things: each rule in
each game, every door on every floor with and without the key, and every room's stairs. The monster
movement rows are also covered by `tools/verify_monsters.py`, frame by frame.

| Game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Walls visible (games 2–9: never, even with a match lit) | ✓ | | | | | | | | |
| Door sounds (doorway, new room, blocked) | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Monsters shown outside your room (if on screen) | ✓ | | | | | | | | |
| Locked doors; the master key shown and usable | | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Key starts beside you (floor 1, room 2) | | | ✓ | | | | | | |
| Monsters (3 or 5) | 3 | 3 | 3 | 3 | 5 | 5 | 5 | 5 | 5 |
| Monsters follow you from room to room | | | | | | ✓ | ✓ | ✓ | ✓ |
| Bat steals your item | | | | | | | ✓ | ✓ | ✓ |
| Ghost ignores the scepter; faster chasers | | | | | | | | ✓ | ✓ |
| Every monster may pass locked doors | | | | | | | | | ✓ |
| Its own stairs and locks | | | | | | | | | ✓ |

In games 2–9 a lit match shows items and your room's monsters, but never the walls; the floor's colour
moves to the status line instead. You find your way by memory, by bumping, and by lightning.

## What's left

Every question from the first pass is answered and has a check:

- Monster movement: [monsters.md](monsters.md).
- The game-number table: above, all nine games.
- The glow, the screen, the switches and the sound: [screen-and-sound.md](screen-and-sound.md).
- Start positions: the ghost and the master key start on floor 4 (the key beside you in game 3), and every
  item lands where `game.monsters.new_game` says.

Not checked live, because nothing on screen or in RAM shows them:

- `$CF`/`$DE` place the ball and missile 0 in the middle wall's gap while a match is lit in games 2–9.
  The glow never reaches that far, and a monster in the room blows the match out, so in play they never
  show (from the code).
- The B&W switch's palette. The code reads it; we've only played in colour.
