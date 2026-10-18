# Making a pack

A pack is who's in the game and where it happens: a **cast**, a **world**, and a soundtrack. Any look shows
any pack, adapting its pictures to the console's colour rules, so a pack made for one look plays in the
other too. The two that ship are `packs/classic` (the NES look's own) and `packs/nocturne` (the SNES look's).

A pack never changes the game. It only says what things look and sound like.

## Start with an AI assistant

The easiest way is to describe what you want to an AI coding assistant and build it together. Give it
[CLAUDE.md](../CLAUDE.md) - the rules - and this page, and point it at `packs/classic` as the example. Then
ask for what you want: "a pack where the eyes are a cat's, the monsters are moths, a spider and a raven, and
the house is a Gothic library".

## What's in one

```
packs/<name>/
    pack.json       its title, a description, the four floors' names, where the title mansion's window and
                    door are
    music.json      its soundtrack (optional)
    source/         the art, as text, and draw.py to turn it into the pictures below
    cast/           who: PNGs, made by source/draw.py
    world/          where: PNGs, made by source/draw.py
```

Your own packs can go in `private/packs/` (never published). Play one with `python play.py --pack <name>`.

Anything a pack leaves out is drawn with the original 2600 graphic, read from your ROM, so a pack can start
with one picture and grow.

## Art is text

Each picture is drawn as text art in the pack's `source/` - a character per pixel, a dot for clear - with a
table saying which colour each character is. `source/draw.py` writes the PNGs. Edit the text, never the
PNGs. In `packs/nocturne/source/paint.py` there are helpers for 16-bit-style art: colour ramps, bevels,
gradients and grain.

## The cast

A picture's frames are numbered: `ghost_down_0.png`, `ghost_down_1.png`. A look plays them in turn, a step
every 8 frames. Monsters have a picture for each way they walk; draw `_left` or `_right` and the look mirrors
it for the other.

| Name | Size (classic) | What |
|---|---|---|
| `eyes_centre`, `_left`, `_right`, `_up`, `_down`, `eyes_blink` | 14 x 6 | you: the eyes look the way you push |
| `hood`, or `hood_right` | 20 x 14 | round the eyes by matchlight (`hood_right` is lit on the match's side) |
| `match_hand_right` | 10 x 14 | the hand holding the lit match |
| `ghost_<facing>`, `bat_<facing>` | 16 x 20, 16 x 12 | the ghost and the bat |
| `tarantula2_<facing>` ... `tarantula4_<facing>` | 16 x 16 | the three tarantulas (their legs move only while they walk) |
| `key`, `scepter` | 16 x 8, 16 x 16 | the master key and the scepter |
| `urn2` ... `urn8` | | the urn: 2-4 a single piece, 5-7 two joined, 8 whole |
| `stairs_up`, `stairs_down` | 16 x 32 | the stairs |

## The world

The floors are built from the ROM's wall plan, so a world gives the materials, not the layout. Floors are
numbered 1-4.

| Name | Size (classic) | What |
|---|---|---|
| `floor<n>` | 24 x 32 | a floor tile, repeated |
| `wall<n>_top`, `wall<n>_face`, `wall<n>_trim` | 24 x 32, 24 x 20, 1 x 1 | the walls in 3/4 view: their tops, the faces you see, the edge between |
| `front_door` | 8 x 20 | the front door on floor 1 |
| `title_mansion`, `title_moon` | 64 x 40, 20 x 21 | the title screen (and, warmed, the sun at the ending) |
| `decor<n>_<kind>` | | decorations on floor n's walls: a portrait, a bookshelf, a fern |

Decorations can live:

- **Frames** flicker in turn: `decor1_sconce_0`, `_1`, `_2`.
- **Eyes that follow you:** `decor1_portrait_centre`, `_left`, `_right`, `_up`, `_down`.
- **Lightning:** `decor3_window_lightning` is shown while the lightning flashes.

`pack.json` gives the title mansion's tower window (`title_window`: x, y, width, height in the art's
pixels), where the eyes look out, and its door (`title_door`), where they leave from after a win.

## The soundtrack

`music.json` has a song for each moment: `story`, `title`, `floor1` to `floor4` (leave one out for a
quiet floor - the attic is quiet in both packs), `tension` (a monster in your room), `dying`, `game_over` and
`win`. Each song is written as text - chords, a melody in eighth notes, drums - and played on the look's
sound chip, so the same song is chiptune on the NES and an orchestra on the SNES. The notation is described
at the top of `music/chiptune.py`. `python -m music.chiptune <pack>` renders a pack's songs to listen to.

## Checking it

```sh
python packs/<name>/source/draw.py          # the PNGs from the text art
python tools/preview.py --pack <name>       # every situation in one picture - look at it
python play.py --pack <name>
```

Public packs must be original: no names, logos, likenesses or exact designs from someone else's work.
