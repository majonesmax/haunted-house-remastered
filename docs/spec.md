# Haunted House: a specification for ports

What the Atari 2600 *Haunted House* (James Andreasen, 1982) does, frame by frame, written so that someone
could rebuild it on another machine and have it play the same. It gathers what the other pages found and
adds the player's side of the game, read from the code.

The game itself is the final authority. Where this page and the real game disagree, the game is right and
this page has a bug.

## How sure each rule is

Every rule carries one of three marks:

- **proved**: a Python model of the rule predicts the real game's RAM exactly, frame after frame, and its
  check fails if any part of the rule is broken. The model is the precise statement; this page is the summary.
- **checked**: an experiment in the running game confirms it (`tools/verify_ram.py`,
  `tools/verify_games.py`, `tools/verify_screen.py`), but no model replays it frame by frame.
- **code**: read from the game's code and consistent with play, but not yet checked on its own.

The models and checks:

| Part | Model | Check | Mark |
|---|---|---|---|
| Monsters, the random numbers, a new game's starting places | `game/monsters.py` | `tools/verify_monsters.py`, 30,000 frames | proved |
| Sound, both channels, every frame | `game/sounds.py` | `tools/verify_sounds.py` | proved |
| The nine games' rules, every door, every stairway | `game/rom.py` | `tools/verify_games.py`, 117 checks | checked |
| Where everything is drawn | `game/visibility.py`, the formulas below | `tools/verify_screen.py` | checked |
| Everything else, as one whole frame: the switches, moving, doors, stairs, the match, the button, what's drawn, touching, items and the urn, dropping, dying, winning | `game/player.py` | `tools/verify_player.py`, 449,945 frames | proved |

`game/player.py` is the whole game, frame by frame, in the game's own order; it calls the monster and sound
models where the game does. Its check plays all nine games with a bot that wanders, runs through doors and
up and down stairs, lights matches, picks up, swaps, joins and drops things, walks into walls and drops
things there, gets caught, loses every life, wins, and presses SELECT and RESET. Before each frame the
model is given the real RAM, and it must produce every byte of the game's state exactly; across five
seeds of 90,000 frames it does, except on the frames where it says the original crashes ([A crash in
the original](#a-crash-in-the-original)). Breaking any one rule in it, even one that only shows once in thousands of
frames, makes the check fail ([How the check was tested](#how-the-check-was-tested)).

## The ROM's tables: bring your own ROM

The mansion's plan, the sprites, the monsters' waypoints and the game's tuning tables are part of the
cartridge, and this project doesn't copy them. This page names each table by its address and says what it
holds and how to read it; a port reads the bytes from the player's own ROM file at run time, as the remaster
does (`game/rom.py` is a working reader, and its `TABLES` list has every address). Constants written into
the code itself (a limit such as `$94`, a count such as 20 seconds) are given here, as the other pages do.

The ROM checked is the NTSC cartridge (4,096 bytes; `game/rom.py` rejects other sizes). The PAL version
hasn't been looked at.

## Words

- **Frame**: one picture, 1/60 of a second (NTSC). Everything in the game moves in whole frames.
- **Unit**: the game's measure of distance. One unit across is one pixel; one unit up is one *line*, two
  scanlines tall.
- **Floor**: one of four, 0-3 in RAM, shown as 1-4.
- **Room**: one of six on each floor, 0-5.
- **The eyes**: the player.
- **Items**: 0 master key, 1 scepter, 2-4 the urn's three pieces.
- **Monsters**: 0 ghost, 1 bat, 2-4 tarantulas.
- **Game number**: 1-9 here; 0-8 in RAM (`$CC`).

## The state

The whole game is the 128 bytes of RAM. [generated/ram-xref.md](generated/ram-xref.md) lists all of them;
these are the ones a port must keep, and keep exactly, because the rules below read them:

| What | RAM | Notes |
|---|---|---|
| Game number | `$CC` | 0-8 |
| Mode | `$99` | `$00` playing, `$01` dying, `$02` the frame after RESET, `$40` game over or game select, `$44` won |
| Frame clock | `$89` | +1 every frame; many rules key off its low bits |
| Random numbers | `$EB`, `$EC` | a 16-bit shift register; see [Random numbers](#random-numbers) |
| Player | floor `$8D`, room `$9C`, x `$AA`, y `$B5` | |
| Joystick | `$8E` | read once a frame; bit 7 right, 6 left, 5 down, 4 up |
| Items | floor `$A0`-`$A4`, x `$AB`-`$AF`, y `$B6`-`$BA` | items have no room byte |
| Urn shapes | `$9D`-`$9F` | the shape of items 2, 3, 4 |
| Carried | `$9A` | an item number, `$FF` for nothing |
| Monsters | floor `$A5`-`$A9`, x `$B0`-`$B4`, y `$BB`-`$BF`, room `$C5`-`$C9`, plan `$C0`-`$C4` | |
| Monsters following, arrived | `$94`, `$95` | a bit per monster |
| Monsters in your room | `$83` | counted every frame |
| Last monster in play | `$EA` | 2 in games 1-4, 4 in games 5-9 |
| Match | lit: `$8A` bit 6; seconds left `$DF`; frame countdown `$87` | |
| Matches used | `$82` | BCD; the score, lower is better |
| Lives | `$96` | |
| Death timer, killed by | `$80`, `$CA` | |
| Doorway | `$88`, room beyond `$97` | |
| Stairs here | `$9B` | |
| Blocked | `$91` | a locked door in the way |
| Drop search | `$81`, `$E9` | |
| Sound | effect `$93`, its time `$90`, mood `$98`/`$92`, thunder `$8F` | |
| Screen line of the eyes | `$CB` | |

A port that keeps these bytes, with the same values at the same moments, can be checked against the real
game byte for byte (see [Checking a port](#checking-a-port)).

## One frame, in order

The order matters: some rules read what an earlier step wrote in the same frame, and some read what was
written the frame before. **proved**: `game.player.frame` follows it.

1. **Before the picture** (vertical blank):
   1. The clock goes up by one (`$89`).
   2. The switches: RESET, then SELECT ([The switches](#the-switches-game-select-and-reset)).
   3. Only while playing (`$99` is `$00`): the player moves, using the joystick read last frame
      ([Moving](#moving)); then the front door, the match's clock, and the item/monster turn
      ([The match](#the-match), [Winning](#winning)).
   4. Choose what to draw this frame ([What's drawn each frame](#whats-drawn-each-frame)), the eyes' picture,
      the colours and the lightning; then stir the random numbers once ([Random numbers](#random-numbers)).
2. **The picture.** The 2600 draws it line by line, and its hardware notes every pixel where two things
   overlap. Those *collisions* are cleared at the start of each picture, so they say what touched in this
   frame's picture. Then the sound for the frame ([Sound](#sound)).
3. **After the picture** (overscan), unless the mode is game over, select or won:
   1. The death timer; then, unless a death has just ended, the monsters ([Monsters](#monsters)).
   2. The stairs ([Stairs](#stairs)); read the joystick into `$8E`; the button
      ([The button](#the-button-lighting-a-match-and-dropping)); the drop search.
   3. Touching: being caught or picking up ([Touching](#touching)).
   4. Doorways and rooms ([Doors](#doors-and-rooms)).

One consequence: **the eyes move by the joystick of the frame before** (**proved**). The eyes' pupils, which
are only a picture, follow the joystick of this frame.

## The mansion

Read from `FLOOR_WALLS` ($FFD4), `DOOR_IDS` ($FD82), `LOCKED_DOORS` ($FDD5), `STAIRS_HERE` ($FDDD),
`STAIRS_GO_UP` ($FDE5), `STAIRS_EDGE` ($FD46), `ROOM_STEP` ($FFD0). **checked**: every wall pixel, door and
stairway in every game.

- **A floor is one tall map**, not a set of screens. x runs from 4 to `$94` (left to right), y from 1 to
  `$FB` (bottom to top: **up is +y**). The screen scrolls through it.
- **The wall plan is the same on every floor**: 16 rows of 8 bits, one byte per row, from `FLOOR_WALLS`.
  Each cell is 16×16 units. Rows are `y >> 4`. The columns start at x = 16: column `c` covers x
  `16(c+1)` to `16(c+2) - 1`, and bit `c` of the row's byte (by the mask in `COLUMN_BITS`, $FE00) is set
  for wall.
- **Outside the 8 columns** (x below 16 or from 144) everything is wall, except in row 8, the middle row,
  which is open at both sides: the front door and the side stairs are there.
- **The wall test** for a point (x, y), exactly as the game does it ($F2A1; `game.rom.wall_at`):
  `column = ((x >> 4) - 1) & $FF`; `row = y >> 4`; if column has bit 3 set it's wall unless row is 8;
  otherwise it's wall if the row's bit for that column is set.
- **Six rooms per floor**, two columns by three rows. Even rooms are on the right, odd on the left; rooms
  0 and 1 at the bottom, 2 and 3 in the middle, 4 and 5 at the top.
- **Seven doors**, numbered 0-6, join neighbouring rooms. `DOOR_IDS` gives each room four entries (left,
  right, up, down): a door number, `$80` + room for the floor's outer edge, or `$FF` for wall. Going
  through a door changes the room number by `ROOM_STEP`: left +1, right -1, up +2, down -2.
- **Locked doors** (games 3-9): `LOCKED_DOORS` has a byte per floor, a bit per door. Games 3-8 use the
  first four bytes; game 9 uses the other four. Games 1 and 2 have no locks.
- **Stairs** sit at the floor's outer edge. `STAIRS_HERE` has a byte per floor with a bit per room that has
  stairs; `STAIRS_GO_UP` a bit per room whose stairs go up. Game 9 uses the second half of each. Each
  room's stairs are on a fixed edge (`STAIRS_EDGE`): rooms 0 and 1 the bottom, room 2 the right, room 3 the
  left, rooms 4 and 5 the top. Each floor's stairs match the floor above and below.
- **The front door** is the right edge of room 2 on floor 1.

Game 9's stairs and locks differ from the other games'; nothing else about the mansion changes with the
game number.

## A new game

What RESET does ($F082). **proved**.

1. Swap the two random bytes (`$EB` and `$EC`).
2. Clear `$80`-`$95` to 0. That includes the clock, the floor (floor 1), the matches used, the match, the
   flags and the match's frame countdown `$87`.
3. Copy `NEW_GAME` ($FDF6, 10 bytes) to `$96`-`$9F`: 9 lives, no room beyond, the mood sound silent, mode
   `$02`, carrying nothing, no stairs, room 2, urn shapes 2, 3, 4 (three single pieces).
4. Scatter the monsters ([Scattering](#scattering)), then put the ghost on the top floor.
5. Put each item where the monster with the same number now is: the master key with the ghost (so on the top
   floor), the scepter with the bat, each urn piece with a tarantula. In game 3 the master key goes beside
   the player instead: floor 1, x `$74`, y `$84`.
6. The room's limits and stairs are worked out ([Doors](#doors-and-rooms)), `$EA` is set (4 from game 5,
   else 2), and the player is placed at x `$80`, y `$86`: room 2, beside the front door.

RESET does all of this **every frame it's held**. On each of those frames the mode is `$02` while the
picture is set up, so the player doesn't move, and the rest of the frame (monsters, the button, touching,
doors) runs as in play, with the mode back to `$00`. So the game really starts on the frame after RESET is
let go. One more thing happens on RESET's frames: see [the leftover sprite](#the-leftover-sprite).

## Moving

Each frame of play ($F1BF; `game.player.move`). **proved**.

The player is a box 8 units wide and 3 tall: x to x + 7, y to y + 2.

1. Clear this frame's steps (`$E7`, `$E8`) and the "at the edge" bit (bit 7 of `$9B`).
2. **Across**, unless `$91` bit 6 blocks it. If the stick (from `$8E`) is pushed left, try left; otherwise,
   if right, try right. (Left wins if both are set.)
   - Note the step (`$E7` = -1 or +1) even if it fails.
   - At the floor's limit (x is 4 going left, `$94` going right): set "at the edge". If this room has no
     stairs, it's a **bump** instead.
   - Otherwise test two points one unit beyond the box's side, at its top and bottom rows:
     right `(x + 8, y + 2)` and `(x + 8, y)`; left `(x - 1, y + 2)` and `(x - 1, y)`. If either is wall,
     it's a **bump**; if neither, x moves one unit.
3. **Up or down**, unless `$91` bit 7 blocks it. Down if only down is pushed; up if up is pushed.
   - Note the step (`$E8`).
   - At the floor's limit (y is `$FB` going up, 1 going down): set "at the edge"; with no stairs here, a bump.
   - Otherwise test two points one unit beyond the box's top or bottom, at its left and right columns: up
     `(x + 7, y + 3)` and `(x, y + 3)`; down `(x + 7, y - 1)` and `(x, y - 1)`. Wall: a bump; open: y
     moves one unit.
4. A bump starts the bump sound.
5. Clear `$91`.
6. **Scroll**: the eyes' screen line `$CB` is `$26` (the middle of the view), except near the ends: for y
   below `$26` it's y itself, and for y from `$D7` it's `y - $AF`.

So the eyes move across and up in the same frame, one unit each way at most: 60 units a second. Every
monster is slower.

Only row 8 is open at the sides, so x reaches 4 or `$94` only in rooms 2 and 3, and y reaches 1 or `$FB` only
in the bottom and top rooms. The edge the player stands at is always the edge the room's stairs (or the front
door) are on.

## Doors and rooms

The room number changes only as the player walks through a doorway ($FC3C). **proved**; and every door on
every floor, with and without the key, in all nine games, by `tools/verify_games.py`.

**Doorway lines.** `DOORWAY_LINES` ($FC68) holds six pairs of numbers, for six crossings: up between the bottom
and middle rows, up between the middle and top rows, the same two going down, left between the columns, right
between the columns. Each pair is a coordinate where the doorway starts and one where it ends: y for up and
down, x for left and right. They're tested in that order, and the first that matches ends the step.

Each frame, for each crossing, if the stick is pushed that way:

- **Coordinate equals the start, and not already in a doorway**: look up this room's neighbour that way.
  - If the door is locked on this floor in this game, and the player isn't carrying the master key: set
    `$91` to stop movement along that axis next frame (bit 6 across, bit 7 up and down) and start the
    **blocked** sound. Pushing on, the player stays put.
  - Otherwise: the room beyond (`$97`) is this room plus `ROOM_STEP`; `$88` is the direction with bit 7
    set (in a doorway); start the **doorway** sound.
- **Coordinate equals the end, and in a doorway**: the player is through.
  - If the direction differs from the one the doorway was entered by (the player turned back), the room
    first becomes the room beyond, so the step below lands back in the room they came from.
  - Monsters follow (games 6-9; [Following](#following)).
  - `$88` is the direction without bit 7; the room changes by `ROOM_STEP`; `$97` is `$FF`; start the
    **new room** sound; work out the room's limits and stairs (below).

Game 1 makes no door sounds (doorway, new room, blocked).

**A room's limits and stairs** ($FD0A), whenever the room or floor changes:

- `$8B` (top) and `$8C` (bottom): the y limits of the room, from `ROOM_BOUNDS` ($FD7F) by the door above and
  the door below (door number / 2); 0 where the room has the floor's edge instead. In games 2-9 nothing lit
  by the match is drawn beyond them.
- `$CF` and `$DE`, where two blocks are put in the middle wall's gap: one pair of values if the room has a
  door on its left, another if not. (The game finds out by looking the left door up in the same table,
  which reads past its end; it only asks whether the answer is 0, and it never is.)
- `$9B`, the stairs here: `$0F` if the room has no stairs on this floor; otherwise the edge (0 left, 1 right,
  2 top, 3 bottom) plus 4 if they go up.

## Stairs

($FB68) **proved**; and every room's stairs on every floor, in every game, by `tools/verify_games.py`.

After moving, if this room has stairs, the player is at the edge (bit 7 of `$9B`) and hasn't just used the
stairs (bit 6):

1. Monsters follow (games 6-9; [Following](#following)).
2. The floor goes up or down by one, and the **stairs up** or **stairs down** sound starts.
3. The room's limits and stairs are worked out for the new floor, and bit 6 ("just used") is set.

The player keeps the same x, y and room number, on the new floor. Bit 6 stays set until a frame where the
player isn't at the edge; only then can the stairs be used again.

**A quirk in games 1-5**: the routine that sends monsters after the player (step 1) starts by checking the
game number, and for games 1-5 it jumps into the button's code ([below](#the-button-lighting-a-match-and-dropping))
instead of returning. That runs the button's code, then the stairs carry on, then the button's code runs
again as usual. So on the frame the player takes the stairs, the button is read twice.

## Winning

($F155) **proved**.

While playing, if the player is at the edge in room 2 of floor 1 (the front door):

- Carrying item 2 whose shape is 8 (the whole urn: see [The urn](#the-urn)): **won**. The clock is set to 1,
  the flags to 1 (bit 0 is "won") and the mode to `$44`.
- Otherwise the **blocked** sound starts, and the player stays inside.

While won, the game draws only the eyes, plays the win tune ([Sound](#sound)) and does nothing else. When the
clock comes round to 0 (255 frames later) the mode becomes game over (`$40`).

## The match

**proved**.

- **The button** ([below](#the-button-lighting-a-match-and-dropping)) lights a match when none is lit:
  `$DF` = 20 seconds, the matches used (`$82`) go up by one in BCD, and `$8A` bit 6 is set.
- **Its clock.** Every frame of play `$87` counts down; when it reaches 0 it's set to 60 and the match
  loses a second (`$DF`). `$87` runs all the time and isn't reset by lighting, so a match's first second is
  1 to 60 frames. After RESET it starts at 0, so the first match's first second is 256 frames.
- **It goes out** when `$DF` reaches 0, or on the first frame a monster is in the player's room (`$83` not
  0). Going out clears bits 3-7 of `$8A` and `$85`.
- While a monster is in the room, the button isn't even read: no match can be lit.
- **The item/monster turn**: after the match's clock, bit 7 of `$8A` flips. It decides, while a match
  is lit, whether this frame shows an item or a monster ([What's drawn](#whats-drawn-each-frame)).

## The button: lighting a match and dropping

(`$FB92`) **proved**.

Only while no monster is in the player's room; while one is, the button isn't read at all. Otherwise the
button's state is shifted into `$E6` each frame (bit 7 is
this frame; 0 means pressed). A **press** is `$E6` = `$7F`: pressed now, and up for the 7 frames before.
Holding the button does nothing more; quick presses less than 8 frames apart are ignored.

On a press:

- No match lit: light one ([The match](#the-match)).
- A match lit and carrying something: start the **drop** sound, drop it ([Dropping](#dropping)) and carry
  nothing.
- A match lit and carrying nothing: nothing.

So a match can't be put out, and **an item can only be dropped in the light**.

## Items

**proved**.

**What shows.** An item is drawn only while a match is lit, on the player's floor, not carried, not joined
into another piece, and close: its *light distance* is under 17 (`$11`). The light distance is the larger of
the two differences (|x - item x|, |y - item y|) plus half the smaller, rounded down ($F53D). The master key
never shows in games 1-2, which have no locks. Carried items aren't drawn at all, and their x and y mean
nothing until dropped. And like any sprite it must be on screen ([What's drawn](#whats-drawn-each-frame)).

**Picking up** happens by touching ([Touching](#touching)), so **only in the light**. Touching item *n*:

- Start the **pick up** sound.
- If the player carries an urn piece and *n* is a different urn piece, they join (below).
- Otherwise, if the player carries something, it's dropped ([Dropping](#dropping)): the items swap.
- The player now carries *n*.

### The urn

The three pieces are items 2, 3 and 4. Their shapes (`$9D`-`$9F`) pick their pictures from `ITEM_SPRITES`
($FE08): 2, 3, 4 are the single pieces; 5 is pieces 1+2, 6 is 1+3, 7 is 2+3; 8 is the whole urn; `$FF` means
this piece is now part of another and is never drawn. **proved**.

Carrying piece *a* and touching piece *b* (`$FAAC`); `sum` = *a* + *b*:

- Start the **pieces join** sound.
- If item 3 or item 4 is already joined into another (its shape is `$FF`), this is the third piece: start the
  **urn whole** sound; item 2's shape becomes 8, items 3 and 4 become `$FF`, and the player carries item 2.
- Otherwise the two make a pair:
  - sum 5 (items 2 and 3): item 3 becomes `$FF`, item 2 becomes shape 5; the player carries item 2.
  - sum 6 (items 2 and 4): item 4 becomes `$FF`, item 2 becomes shape 6; the player carries item 2.
  - sum 7 (items 3 and 4): item 4 becomes `$FF`, item 3 becomes shape 7; the player carries item 3.
- The drop search then runs on the piece the player was carrying. It moves that piece's x and y,
  but the piece is carried again, so nothing comes of it except that touching is paused while it runs.

The whole urn is therefore always item 2, which is what [Winning](#winning) tests.

### Dropping

The game looks for a free spot next to the player, one candidate a frame, using the 2600's own collision
between the dropped item's picture and the walls ($FBE2). **proved**.

1. `$81` = 5, `$E9` = the item.
2. If the player tried to move this frame (`$E7` or `$E8` not 0), the first spot is **behind** them: the
   offsets come from `DROP_OFFSETS` ($FD02), indexed by the steps, so moving right puts it to the left,
   moving up puts it below, and so on. A spot is rejected if its y would be `$F4` or more (or the player is
   that high and the offset is upwards) or its x `$97` or more. If the spot is accepted, the search waits
   for the next frame.
3. Otherwise (or if rejected), count `$81` down and try the next spot, in this order: left, below, right,
   above. When `$81` reaches 0 the search stops where it is.
4. While `$81` isn't 0, every frame draws the dropped item (in black, so it can't be seen) on the player's
   floor. If the sprite drawn that frame overlaps a wall, try the next spot as in step 3; if not, the search
   is over (`$81` = 0) and the item stays there.

While the search runs, nothing else is drawn and no touching happens. Four details matter for the wall
test:

- The item is drawn where the search put it **as the player stood last frame**: when it tries a spot it
  also works out the sprite's screen column and line (`$DC`, `$EF`), and the next frame draws from those,
  after the player has moved. If the player has moved up or down meanwhile, the item is tested a line off.
- While the player is dying, the frame's sprite is a monster (or the stairs), not the item, but the search
  still asks whether *the sprite* touched a wall.
- The test only sees the lines that are drawn: with a match lit in games 2-9, not those beyond the room's
  limits ([Touching](#touching)).
- When a join puts down the piece the player held, that piece's shape is already `$FF`. Its picture's
  address is worked out as for any item - the shape shifted left three times, plus 8, in one byte, after
  `$FE00` - and the carry out of the shifts is added too, so a shape of `$FF` gives `$FE01`: eight bytes
  that are no picture at all, but that's what's tested against the walls.

## Monsters

All **proved**: [monsters.md](monsters.md) is the description and `game/monsters.py` is the rule. In short:

- They walk between 19 waypoints (`WAYPOINT_X`/`_Y`, $FFAA/$FFBD): the six room centres, the seven doors and
  the six stairs spots. They never test walls.
- Each has a plan (`$C0`-`$C4`): a direction, a kind (to a room centre, a door, stairs down, stairs up) and a
  target.
- At a room centre a monster picks a direction at random, never the way it came unless nothing else will do.
  Only the ghost may use locked doors, except in game 9 where all may.
- **Speed** by the clock's low 3 bits against a bit mask: wandering on frames 3 and 7 of every 8; chasing per
  monster from `MONSTER_SPEED` ($FA86), or `MONSTER_SPEED_FAST` ($FA8B) in games 8-9.
- **Chasing**: a monster on the player's floor, in the player's room or the room beyond the doorway the
  player stands in, heads straight for the player (through walls), unless the player carries the scepter
  (the ghost ignores it in games 8-9) or is dying. Where it aims has a quirk worth keeping (monsters.md).
- Several arriving in one frame: the lowest-numbered gets its new plan; the others wait a frame each.
- Each frame of play the monsters in the player's room are counted into `$83`.

### Following

Games 6-9 (**proved**). When the player leaves a room through a door or by the stairs, every monster on that
floor in that room is given the same exit as its plan and marked in `$94`, so it moves at chasing speed until
it gets there. Through a locked door only the ghost follows, even in game 9.

### Scattering

On RESET and when the death timer runs out (**proved**): pick a random room `base` (0-5); then for each
monster from 4 down to 0, a random floor (0-3) and room `(monster + base) mod 6`, or `(5 + base) mod 6` if
that's the player's room on the player's floor. Each goes to its room's centre, with that centre as its
plan. All five are placed, even in games with three.

### Random numbers

`$EB`/`$EC` is a 16-bit shift register ($F4C9; `game.monsters.next_random`, **proved**): `t` = (`$EC` XOR
`$EB`) bit 6; shift `$EB` left with `t` coming in at bit 0; shift `$EC` left with `$EB`'s old bit 7 coming in.
It's stirred when the kernel uses it each frame and more times when monsters are scattered; the model has
every call. Wherever a rule says "random", it's a bit of `$EB`.

## What's drawn each frame

The 2600 can draw one item or monster per frame (one *sprite*), besides the eyes and the walls. Which one is
shown matters for more than looks: **touching is tested only against the sprite drawn that frame**. ($F2B7,
$F4F1, $F57D) **proved**.

In order:

1. RESET's frame and won: nothing new is chosen ([the leftover sprite](#the-leftover-sprite)).
2. **Dying**: each monster on the floor in turn, and the eyes roll: their pupils follow fake stick readings
   from `DYING_EYES` ($FF92), indexed by bits 1-3 of the clock.
3. **The drop search** running: the dropped item, in black.
4. **A match lit, item turn** (`$8A` bit 7 clear): the next item in turn after the last one shown (`$86`,
   counting down from 4 and wrapping) that may show ([Items](#items)) and is on screen. The eyes are drawn.
5. **A match lit, monster turn**: the next monster in turn (`$85`), or the stairs, which take the slot after
   the last monster. The eyes are replaced by the match's glow.
6. **No match**: the next monster in turn that may show. The eyes are drawn.

**Which monsters may show:** on the player's floor and on screen. In game 1, any. In games 2-9, only one in
the player's room or the room beyond, and only while `$83` isn't 0; and while dying, any on the floor.
While dying with a match lit, the stairs take their slot too.

**On screen** means the line of the sprite's bottom row is under 80, or `$F9` or more (just below the view,
with its top rows reaching into it).

If nothing qualifies, no sprite is drawn that frame.

The turn moves on in `$85` and `$86`, and the sprite's place and picture go into working bytes the drawing
reads: column `$DC`, the line of its bottom row `$EF` (the floor y + `$CB` - the player's y), its height
`$ED`, its picture's address `$E1`/`$E2`. A port needs these only for the leftover sprite and the drop.

### The leftover sprite

On RESET's frames and while won the game doesn't choose a sprite, but the drawing still draws one: whatever
the working bytes hold from the frame before, at normal width, in black. While won this does nothing, since
touching isn't tested. But on RESET's frame touching *is* tested ([A new game](#a-new-game)), and the eyes
have just moved to the start position: **if the last sprite drawn was a monster where the eyes now are, the
new game's player is caught at once**, by an invisible monster, and loses a life. (**proved**: it happened
to the check's bot.)

### Pictures

All stored bottom row first; `game/rom.py` reads them.

- The eyes: 8 wide, 3 lines, built from constants in the code ($F318): two eyes in every row, and in one
  row the pupils - the middle row, the bottom one while the stick is pushed down, the top one while it's
  pushed up - drawn looking ahead, right or left (left wins), by the stick held this frame.
- Items: `ITEM_SPRITES` ($FE08), 8 lines each; colour from `ITEM_COLOURS` ($F4D6).
- Monsters: `MONSTER_SPRITES` ($FE50), 10 lines, two frames each, chosen by bit 6 of `$EB` (so a monster's
  picture flickers between its frames at random); the ghost, the bat and the tarantulas each have
  their own, and the three tarantulas share one. Each monster's colour is colour number monster + 1.
- Stairs: `STAIRS_SPRITES` ($FE8C), 17 lines, at `STAIRS_X` and the line of `STAIRS_Y` for its edge. The
  picture is number `edge` going down, `(edge XOR 1)` going up. They're drawn **at double width** (16
  pixels) and, as the TIA does for any stretched player, **starting one pixel to the right** of x.
- The glow: `LIGHT_SPRITES` ($FF50), 28 lines, drawn four times wide (32 pixels) and centred on the eyes;
  big or small by bits 1-2 of the clock through `LIGHT_FLICKER` ($FF9A).

## Touching

($FA90) **proved**.

Touching is the 2600's collision between the eyes' picture and this frame's sprite (and, for the drop
search, between the sprite and the walls): some lit pixel of each on the same scanline and column. A port
must reproduce what the drawing loop puts on each scanline ($F647):

- The lines drawn: from line 79 down to line 1. With a match lit in games 2-9, outside a doorway, only from
  the line of the room's top limit (`$8B`, if it's not 0 and its line is under 80) down to the line above
  its bottom limit (`$8C`, if not 0 and its line is under `$80`).
- Each line is two scanlines. On the **first**, the eyes show their row for this line and the sprite shows
  its row for the line above; on the **second**, both show their rows for this line. So a sprite row touches
  the eyes' row on the same line or the line below.
- The first line drawn shows no eyes, and the last line only its first scanline. (The first can't matter in
  play: the eyes never reach the top line drawn.)
- Columns: the eyes start at the player's x, a sprite at its x (one further right if stretched), bit 7 of a
  row leftmost. The walls on a line are the wall plan at that line's y, with the middle row's edge strips
  ([The screen](#the-screen)).
- The eyes' rows come from the stick held *this* frame (their pupils). On the glow's frames the glow
  replaces the eyes, and what it touches is ignored.

Touching the eyes does nothing while dying or while the drop search runs (the search uses the sprite's
touch with the walls instead). Otherwise:

- **No match lit** (a monster frame): if `$85` names a monster (it isn't past the last one), the player is
  **caught** by that monster.
- **A match lit, item turn**: the player **picks up** the item ([Items](#items)).
- **A match lit, monster turn**: nothing. The glow stands in for the eyes, and its touches are ignored.

A monster in the room puts the match out ([The match](#the-match)), so in practice a monster can only reach
the player in the dark.

**Caught**:

- In games 1-7, carrying the scepter saves the player. In games 8-9 it saves them from every monster but the
  ghost.
- Otherwise: mode `$01` (dying), death timer `$80` = `$FF`, one life lost, `$CA` = the monster.

**Dying** ($F8AC): the timer counts down a frame at a time, about 4.25 seconds. Monsters keep wandering but
don't chase. When it reaches 0:

1. Play goes on (mode `$00`) and the sound effect stops.
2. If no lives are left, the game is over (mode `$40`).
3. The monsters are scattered ([Scattering](#scattering)); the player stays where they were.
4. Games 7-9: if the bat (`$CA` = 1) caught a player carrying something, that item is put where the bat is,
   and the player carries nothing.

## Lightning

(code; that the left difficulty switch turns it off is **checked** in all nine games)

On a frame where the walls flash, they're drawn in colour 1 (grey, `$0D`) instead of their usual colour:

- While dying: on frames where the clock's two low bits are 0, if bit 0 of `$EB` is set.
- While a monster is in the room and the left difficulty switch is on B: on frames where the clock AND `$27`
  is 0 (4 frames in every 64), if bit 0 of `$EB` is set.

## The screen

Everything below is in [screen-and-sound.md](screen-and-sound.md) with its evidence (**checked** pixel for
pixel by `tools/verify_screen.py`); here it is as rules.

- The picture is 160×228 (NTSC). The view of the floor is 80 lines, on scanlines 15-171; the status line is
  below it.
- A game y is drawn on kernel line `L = y - player y + $CB`; line L starts on scanline `15 + 2 × (79 - L)`.
  Walls and the eyes start there; items and monsters one scanline lower. Columns are x.
- **Walls**: the wall plan as above, plus a 4-pixel strip at each edge of the middle row (x 0-3 and
  156-159). Game 1 draws them in the floor's colour (`COLOURS` 8-11, from $FFEC: one per floor) all the
  time. Games 2-9 draw them black, in front of the glow, so the glow lights only open floor; the floor's
  colour moves to the status line's background. Lightning flashes them grey.
- **The glow** (games 2-9): drawn on alternate frames, around the eyes, never past the room's limits.
- **Flicker**: one sprite a frame, in turn. The urn pieces' colour comes from the frame clock, so they shimmer.
- **The status line**: matches used, the floor (1-4) and lives, in `DIGITS` ($FF00).
- **Colours**: `COLOURS` ($FFE4), 12 NTSC colours and then 12 for the B/W switch; the 2600's NTSC palette
  values are in `game/palette_ntsc.json`, measured from the emulator.
- **Game over and game select**: the colours drift slowly (the 2600's way of saving the TV screen; `$84`,
  code).

## Sound

**proved**: `game/sounds.py` gives both channels' registers every frame, from RAM; fed to a TIA sound
emulator they sound like the original. [screen-and-sound.md](screen-and-sound.md) describes them. In short:

- **Channel 0, the mood**: a monster in the room makes a noise that wanders in pitch and loudness (`$98`),
  fading after it's gone; dying is thunder, rumbles of 16-44 frames with a silent frame between; winning is
  a four-note tune (`WIN_TUNE`, $FF9E), 16 frames a note.
- **Channel 1, the effects**: blocked (2), bump (3), doorway (4), drop (5), pick up (6), pieces join (7), new
  room (8), stairs up (9), stairs down (10), urn whole (11), each for its length in `SOUND_LENGTHS` ($F8A0).
  A new effect replaces the one playing, except that the same one isn't restarted and a bump never cuts
  another short. With no effect playing, footsteps: a click on 3 frames in 8 while the stick is pushed.

## The switches, game select and RESET

**checked**.

- **RESET** starts a new game ([A new game](#a-new-game)).
- **SELECT** steps the game number (9 wraps to 1) and puts the game in select mode (`$40`): the first frame
  it's pressed, then every 45 frames while held (`$E5`). Select mode also puts out any match.
- **Left difficulty**: B lets lightning flash; A stops it. Nothing else, in every game.
- **Right difficulty**: unused.
- **Colour / B&W**: the second half of the palette (code; not checked).

At power-on the game sets itself up as if RESET had been pressed, then goes to select mode with game 1.

## The nine games

**checked**: every row, in every game (`tools/verify_games.py`).

| Game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Walls visible (games 2-9: never, even with a match lit) | ✓ | | | | | | | | |
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

## A crash in the original

The game can crash. `game.player.GameCrashed` says when, and in the check every crash came exactly where it
said, and nowhere else.

Choosing which monster to draw, the game jumps out of a subroutine instead of returning from it each time a
monster that may be drawn turns out to be off the screen ($F5C4 to $F591). Each leaves two bytes on the
stack. The stack is the top of the 128 bytes of RAM, and five of those reach down to `$F2`. If the stairs are
then chosen, their routine writes 0 to `$F1` ($F622) - by then the high byte of its own return address. It
returns to `$008C`, and the 6502 runs the game's RAM as code.

What happens next depends on those bytes. Usually the game ends up restarting as if just switched on (game
1, select mode). But `$8C` is the room's bottom limit and `$8E` the joystick, and if the player is pushing
left and down, `$8E` is `$60` - the 6502's return instruction - and the game returns into its loop and
carries on, sometimes with a byte or two of RAM left wrong. The check saw both (in five runs, 46 restarts and
5 carry-ons); after a crash it presses RESET and doesn't compare until the new game.

In play this needs a match lit while the player is dying (the button works while dying once the monster
has left the room), a room with stairs, and all five monsters on the player's floor and out of view
(games 5-9). A port shouldn't copy the crash, but now knows it's there. If its RAM can also get into a state
the game itself never reaches (the monster turn byte `$85` past the last slot with no match lit), the
original would go round its monsters for ever; the model raises the same exception rather than hang.

## Not proved

- The B&W palette, and the PAL cartridge: never looked at.
- The two blocks the drawing puts in the middle wall's gap while a match is lit (the ball and missile 0,
  `$CF`/`$DE`): the bytes are proved, but the blocks never show in play and nothing tests against them.
- Power-on: the check starts after it.
- The stick's diagonals that a real joystick can't make (left with right, up with down): the model follows
  the code, but nothing has tried them.
- After a crash where the game carries on: the RAM may be left wrong, and the model isn't meant for that.

## How the check was tested

A check that passes proves little unless breaking the model makes it fail. So single rules were broken in
`game/player.py`, one at a time, and the check run (6,000 frames a game, seed 1). Fourteen of sixteen were
caught: the touching scanlines (either half), the drop search's order, where the dropped item is drawn
from, the stairs' width and their pixel to the right, the leftover sprite, reading the button once on the
stairs, the pupils, the 8-frame press, the items' reach, the scepter and the ghost, turning back in a
doorway, and the crash. Two weren't:

- The joined piece's picture address ([Dropping](#dropping)). It matters only when a join's drop search
  meets a wall, which that run never produced; a 10,000-frame run did, and that's how it was found.
- Eyes on the first line drawn, which can't happen in play ([Touching](#touching)).

## Checking a port

The test for a port is the same as for the models: give the real game and the port the same switches and the
same stick, frame by frame, and compare the state.

- `play.py` records RAM every frame (`R`: `ram.bin`, 128 bytes a frame, with `log.jsonl`), and
  `tools/lab.py` runs the real game with no window, so a port's author can produce traces of the real game
  for any input they like.
- Better still, `game/player.py` is a reference implementation: a port can run it beside itself, frame by
  frame, from the same start and the same controls, and compare. It needs the ROM only for its tables.
- A port that keeps the RAM layout above can compare byte for byte. One that doesn't should compare the
  bytes in [The state](#the-state) through its own names.
- Bytes that only the 2600's drawing uses (`$D0`-`$E4`, `$ED`-`$F5`, the stack) can be left out.
