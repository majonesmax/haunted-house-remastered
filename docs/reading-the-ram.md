# Reading the RAM

The grid view (press **V** until it shows, or start with `python play.py --grid`) has four panes: what
you're playing, the other look, the 2600 original, and **INTERNALS** - the game's entire state, live.

The Atari 2600 has 128 bytes of RAM, at addresses `$80` to `$FF`. That's all of it: there's no screen
memory, so everything the game knows - where you are, where every monster is, what you carry, how long the
match will burn - is in these bytes, and the remasters draw everything from them.

## The bytes

Eight rows of sixteen, `$80` at the top left. Each byte is shown in hexadecimal (`00` to `FF`).

- A byte **flashes pale yellow when it changes**, and cools back to green over a second.
- **Dim** bytes are zero.

Some bytes change every frame: the frame counter (`$89`), the random number (`$EB`-`$EC`), most of the
drawing's workings (`$CD`-`$F5`), the CPU's stack (`$F6`-`$FF`). Walk about and the positions change
(`$AA` your x, `$B5` your y). Light a match and watch `$DF` count the seconds down.

Where things are kept, in short:

| Bytes | What |
|---|---|
| `$82` | matches used (the score - lower is better) |
| `$8D` | the floor (0-3) |
| `$96` | lives |
| `$99` | the game's mode: playing, dying, game select, won |
| `$9A` | what you carry ($FF: nothing) |
| `$9C` | the room (0-5) |
| `$9D`-`$9F` | the urn pieces' shapes: single, two joined, or whole |
| `$A0`-`$C9` | parallel tables: the floor, x and y of each item and monster, each monster's plan and room |
| `$CC` | the game number (0-8 = games 1-9) |
| `$DF` | seconds left on the match |

The whole list, with how sure we are of each, is `game/ram_map.py`.

## The spotlight

Below the bytes, one is named and explained: the last of the game's story bytes to change - the floor, the
room, lives, what you carry, the urn, a monster's floor or plan, the game's mode. It skips bytes that change
all the time, so it's what just *happened*: pick up the key and it shows `$9A CARRIED`; let a tarantula
into the room and it shows `$83 MONSTERS_HERE`.

## Decoded

The bytes put into words: the mode, game, lives and matches; the floor, room and where the eyes are; the
match; what you hold and the urn's pieces; then each monster - its floor, room, position, the way it's
heading, whether it's been sent after you, and, in amber, if it's in your room.

## What happened

A log of events, read from how the bytes change from one frame to the next (the same reading that triggers
the remastered sound effects, `music/events.py`): matches lit and blown out, doors, stairs, pick-ups and
drops, the urn joining, monsters arriving, lightning, being caught, the game starting and ending. Each has
the time since you launched.

## Recording it

Press **R** to record. The RAM of every frame is saved as `ram.bin`, and `python -m app.recorder
recordings/<folder>` turns it into `ram.mp4`, this pane exactly as the grid draws it, frame for frame.
