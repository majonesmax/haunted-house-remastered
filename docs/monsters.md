# How the monsters move

Everything here is in `game/monsters.py`, a Python copy of the game's monster code (`$F8EC`–`$FA85`, plus
`$F0E7`, `$FB2B` and `$FCD8`). `tools/verify_monsters.py` runs the real game beside it. Across games 1, 3, 6,
8 and 9 (30,000 frames, with catches, deaths, stairs, locked doors and monsters following the player), it
predicts every monster byte exactly, every frame. Breaking any one rule in the model makes the check fail.

`shots/monster_paths.png` (from `tools/monster_paths.py`) shows the waypoints and the paths monsters really
walked in game 3.

## The cast

| Number | Monster | In play | Chasing speed, games 1–7 | Games 8–9 |
|---|---|---|---|---|
| 0 | ghost | always | 4 steps in 8 frames (30 units a second) | the same |
| 1 | bat | always | 3 in 8 (22.5 a second) | 4 in 8 |
| 2 | tarantula | always | 2 in 8 (15 a second) | 3 in 8 |
| 3, 4 | more tarantulas | games 5–9 | 2 in 8 | 3 in 8 |

Wandering, every monster takes 2 steps in 8 frames (15 units a second). A step moves one unit in x **and**
one in y, so monsters move diagonally when they need to. The player moves one unit a frame (60 a second)
and can outrun them all.

Which frames a monster steps on is fixed by the clock (`CLOCK & 7` against a bit mask), not spread out. A
remaster that wants the same rhythm should step on the same frames: wandering on frames 3 and 7 of every 8.

## Wandering: the waypoint network

Monsters don't use the walls at all. They walk straight lines between 19 waypoints in the ROM:

- **0–5:** the centre of each room
- **6–12:** each of the seven doors, in the wall between two rooms
- **13–18:** each room's stairs spot, at the floor's edge

The waypoints are placed so the straight lines between them stay in the open.

A monster's plan is one byte (`$C0`–`$C4`): `direction << 6 | kind << 4 | target`.

| Kind | Walks to | On arrival |
|---|---|---|
| 0 | centre of room `target` | picks where to go next (below) |
| 1 | door `target` | its room changes (`$C5`–`$C9`); it heads for the new room's centre |
| 2 / 3 | the stairs of room `target` | its floor goes down / up (`$A5`–`$A9`); it heads for the centre of the same room on the new floor |

**Picking where to go** (at a room centre): start at a random direction (`$EB & 3`) and try each in turn,
skipping the way it came in. A direction is fine if it leads to:

- a door that isn't locked. The ghost may use locked doors in every game; in game 9 every monster may.
- the room's outer edge, if that room has stairs on this floor.

If nothing else works, it goes back the way it came. After the stairs, "the way it came" is the stairs, so
it won't go straight back.

**One at a time:** when several monsters arrive on the same frame, only the lowest-numbered gets a new plan;
the others wait a frame each (`$95` holds who's waiting). Arriving costs a monster one step.

Monsters on other floors keep walking all the time, so they really do roam the house and come and go by the
stairs.

## Chasing

A monster on the player's floor, in the player's room, chases. While the player stands in a doorway, "the
player's room" also counts the room on the other side. A chasing monster steps towards the player at its
chasing speed instead of following its plan. `$83` counts the monsters doing this, and while it's not zero a
lit match blows out and no new one will light.

- **Not through walls, but ignoring them.** A chaser heads straight for the player, and the code never tests
  walls. So a monster in the room beyond a doorway comes straight at you through the wall, and when the
  chase ends it walks straight back to its waypoint the same way.
- **The scepter** stops the chase. Monsters in your room just carry on wandering. In games 8–9 the ghost
  ignores the scepter.
- **While you die** (the eyes rolling, about 4 seconds), monsters keep wandering but don't chase.
- **Where it aims.** Each monster subtracts an offset from the player's position (ROM `CHASE_OFFSET_X/Y`).
  The table looks meant to make them close in from different sides (−6, −2, +6). But the game subtracts
  plain bytes and falls back to the player's own position whenever that goes below 0. So $FA (−6) and $FE
  (−2) always come out as 0. In practice the ghost and bat aim at the player itself, tarantula 1 at 6 below,
  tarantula 2 at 6 to the left, and tarantula 3 at both. A faithful remaster keeps the quirk.

## Following you (games 6–9)

When the player leaves a room through a door or by the stairs, every monster in that room is given the same
exit as its plan. It's also marked in `$94` and walks at chasing speed until the plan is done. Through a
locked door only the ghost follows, even in game 9. In games 1–5 nothing follows: confirmed 31 times with a
monster in the room as the player left.

## Being scattered

On RESET and when the death timer runs out, all five monsters (even ones not in play) go to random room
centres on random floors. The rooms are a run (`base + n`, wrapping at 6), so no two share a room. One that
would land in the player's room on the player's floor goes to room `base − 1` instead. The random numbers
come from `$EB`/`$EC`, a 16-bit shift register stirred once a frame, and the model predicts it exactly too.

On RESET the ghost is then sent to the top floor, and each item is put where the monster with the same
number starts. So the master key starts on floor 4 too, except in game 3, where it starts beside you.
`game.monsters.new_game` predicted every item's start exactly after 359 RESETs across all nine games. After
a death only the monsters move.

## For a remaster

- Read the monsters' positions from RAM (`$A5`–`$BF`). There's nothing to simulate. This page is so we can
  draw and animate them sensibly: facing their direction of travel (bits 6–7 of the plan), hurrying when
  they chase, perhaps showing one coming down the stairs.
- The original draws one monster per frame, in turn, so they flicker. A remaster can draw them all, every
  frame.
- In games 2–9 the original shows a monster only when it's in your room (code at `$F59E`). Game 1 shows any
  monster on your floor that's on screen. Checked live in all nine games by `tools/verify_games.py`.
